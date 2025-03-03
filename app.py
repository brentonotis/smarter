import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, send_from_directory, g
import requests
import json
import openai
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import time
from collections import defaultdict
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import redis
import functools
import logging
from logging.handlers import RotatingFileHandler
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from flask_wtf import FlaskForm
import re
import gc
import threading
from db_config import init_db_pool, get_db_connection, release_db_connection, db_pool
import werkzeug.exceptions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
logger.addHandler(handler)

app = Flask(__name__)
app.logger.addHandler(handler)  # Add the handler to Flask's logger
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Extend session timeout to 24 hours
app.config['OPENAI_DAILY_LIMIT'] = 100000  # Define limits as config values
app.config['NEWS_API_DAILY_LIMIT'] = 95

# Initialize Redis and caching
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url, 
    ssl=True,  # Enable SSL
    ssl_cert_reqs=None,  # Don't verify SSL certificates
    decode_responses=True,  # Decode responses to save memory
    socket_timeout=2,  # Add timeout
    socket_connect_timeout=2,
    max_connections=10  # Limit connections
)

# Cache settings
CACHE_TIMEOUT = {
    'news': 900,    # 15 minutes for news
    'status': 60,   # 1 minute for status
    'default': 300  # 5 minutes default
}

# Cache decorator
def cache_with_timeout(timeout):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Create a cache key from the function name and arguments
                cache_key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
                
                # Try to get the cached result
                cached_result = redis_client.get(cache_key)
                if cached_result is not None:
                    return json.loads(cached_result)
                
                # If no cached result, call the function
                result = f(*args, **kwargs)
                
                # Cache the result
                redis_client.setex(cache_key, timeout, json.dumps(result))
                
                return result
            except redis.exceptions.RedisError as e:
                print(f"Redis error: {e}")
                # If Redis fails, just execute the function without caching
                return f(*args, **kwargs)
        return decorated_function
    return decorator

# Initialize Flask-Mail
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

mail = Mail(app)

# Initialize token serializer for password reset
serializer = URLSafeTimedSerializer(app.secret_key)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, email, password_hash):
        self.id = id
        self.email = email
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            cursor.close()
            
            if user_data:
                return User(user_data['id'], user_data['email'], user_data['password_hash'])
    except Exception as e:
        print(f"Error loading user: {e}")
    return None

# Configure OpenAI API
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Rate limiting data structures
ip_request_counts = defaultdict(int)
ip_last_reset = defaultdict(float)

# Rate limiting for login attempts
login_attempts = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_TIMEOUT = 900  # 15 minutes in seconds

# Cleanup function for data structures
def cleanup_data_structures():
    current_time = time.time()
    # Cleanup login attempts older than timeout
    for email in list(login_attempts.keys()):
        login_attempts[email] = [t for t in login_attempts[email] if current_time - t < LOGIN_TIMEOUT]
        if not login_attempts[email]:
            del login_attempts[email]
    
    # Cleanup IP request counts older than 1 hour
    for ip in list(ip_request_counts.keys()):
        if current_time - ip_last_reset[ip] > 3600:
            del ip_request_counts[ip]
            del ip_last_reset[ip]
    
    # Force garbage collection
    gc.collect()

# Schedule cleanup every hour
def schedule_cleanup():
    cleanup_data_structures()
    threading.Timer(3600, schedule_cleanup).start()

def init_app():
    init_db_pool()
    schedule_cleanup()

# Initialize the app when it starts
with app.app_context():
    init_app()

@app.teardown_appcontext
def teardown_db(exception):
    conn = getattr(g, '_database', None)
    if conn is not None:
        release_db_connection(conn)

# Update tracking functions to include user_id
def track_openai_usage(user_id, token_count):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        today = datetime.now().date()
        
        cursor.execute('''
            INSERT INTO api_usage (user_id, date, openai_tokens_used)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, date)
            DO UPDATE SET openai_tokens_used = api_usage.openai_tokens_used + EXCLUDED.openai_tokens_used
        ''', (user_id, today, token_count))
        
        cursor.close()
        conn.commit()

def track_news_api_call(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        today = datetime.now().date()
        
        cursor.execute('''
            INSERT INTO api_usage (user_id, date, news_api_calls)
            VALUES (%s, %s, 1)
            ON CONFLICT (user_id, date)
            DO UPDATE SET news_api_calls = api_usage.news_api_calls + 1
        ''', (user_id, today))
        
        cursor.close()
        conn.commit()

@cache_with_timeout(CACHE_TIMEOUT['news'])  # Use 15 minutes for news cache
def fetch_company_news(company_name, user_id):
    # Check limits first
    limits = check_api_limits(user_id)
    if limits["news_api_limit_reached"]:
        return [
            {
                "title": f"[DAILY LIMIT REACHED] Mock news about {company_name}",
                "description": f"We've reached our daily API limit. Using mock data for {company_name}.",
                "url": "https://example.com/news"
            }
        ]

    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        # Return mock data for testing if no API key
        return [
            {
                "title": f"Recent news about {company_name}",
                "description": f"{company_name} has been growing rapidly in the tech sector.",
                "url": "https://example.com/news"
            }
        ]
    
    url = f"https://newsapi.org/v2/everything?q={company_name}&sortBy=publishedAt&apiKey={api_key}"
    response = requests.get(url)

    # Track this API call
    track_news_api_call(user_id)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("articles"):
            return data["articles"][:3]  # Return top 3 most recent articles
    
    # Return mock data if API call fails
    return [
        {
            "title": f"Recent news about {company_name}",
            "description": f"{company_name} has been growing rapidly in the tech sector.",
            "url": "https://example.com/news"
        }
    ]

# Generate personalized snippet using OpenAI
def generate_snippet(name, entity_type, context_data, user_id):
    # Check limits first
    limits = check_api_limits(user_id)
    if limits["openai_limit_reached"]:
        return f"[DAILY LIMIT REACHED] Using template response for {name}. Our solution could help you optimize operations and increase efficiency."

    try:
        if not os.environ.get("OPENAI_API_KEY"):
            # Return mock response if no API key
            return f"I noticed that {name} has been expanding in the industry recently, which aligns perfectly with how our solution could help streamline operations and increase efficiency."

        prompt = f"""
        Generate a personalized cold outreach snippet for {entity_type} named {name}.
        
        Recent information about {name}:
        {json.dumps(context_data, indent=2)}
        
        The snippet should be 2-3 sentences, mention specific information about {name},
        and suggest how our product could help them based on their recent activities.
        Be conversational and avoid generic statements.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that generates personalized sales outreach messages."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        # Estimate token usage (approximate)
        prompt_tokens = len(prompt) // 4  # rough estimate
        completion_tokens = len(response.choices[0].message["content"]) // 4
        total_tokens = prompt_tokens + completion_tokens
        
        # Track usage
        track_openai_usage(user_id, total_tokens)
        
        return response.choices[0].message["content"].strip()
    except Exception as e:
        print(f"Error generating snippet: {e}")
        return f"I noticed that {name} has been making waves in the industry lately. Our solution could help you capitalize on this momentum by streamlining your operations."

# Authentication routes
def is_login_allowed(email):
    """Check if login is allowed based on previous attempts"""
    current_time = time.time()
    # Remove attempts older than timeout
    login_attempts[email] = [t for t in login_attempts[email] if current_time - t < LOGIN_TIMEOUT]
    
    # Check number of recent attempts
    if len(login_attempts[email]) >= MAX_LOGIN_ATTEMPTS:
        return False
    return True

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            # Check if this is a login from the extension
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'success'})
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password')
    
    # If this is a login request from the extension, return a special template
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('extension_login.html')
    return render_template('login.html')

def validate_password(password):
    """
    Validate password complexity:
    - At least 8 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one number
    - Contains at least one special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, "Password is valid"

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = FlaskForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not email or not password:
                flash('Email and password are required')
                return render_template('register.html', form=form)
            
            # Validate password complexity
            is_valid, message = validate_password(password)
            if not is_valid:
                flash(message)
                return render_template('register.html', form=form)
            
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Check if user already exists
                    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if cursor.fetchone():
                        flash('Email already registered')
                        return render_template('register.html', form=form)
                    
                    # Create new user
                    cursor.execute(
                        "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                        (email, generate_password_hash(password))
                    )
                    user_id = cursor.fetchone()[0]
                    conn.commit()
                    
                    # Log the user in
                    user = User(user_id, email, generate_password_hash(password))
                    login_user(user)
                    
                    cursor.close()
                    
                    return redirect(url_for('index'))
            except Exception as e:
                print(f"Registration error: {e}")
                flash('An error occurred during registration. Please try again.')
                
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        session.clear()  # Clear the session data
        flash('You have been logged out successfully.', 'info')  # Add a success message
        return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

def log_performance(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        duration = time.time() - start_time
        logger.info(f'Performance: {f.__name__} took {duration:.2f} seconds')
        
        # Store in Redis for monitoring
        try:
            key = f'perf:{f.__name__}:{datetime.now().strftime("%Y-%m-%d")}'
            redis_client.lpush(key, duration)
            redis_client.ltrim(key, 0, 999)  # Keep last 1000 measurements
            redis_client.expire(key, 86400)  # Expire after 24 hours
        except redis.exceptions.RedisError as e:
            logger.error(f'Redis performance logging error: {e}')
        
        return result
    return decorated_function

@app.route('/api/generate', methods=['POST'])
@login_required
@log_performance
def generate():
    # Rate limiting
    client_ip = request.remote_addr
    current_time = time.time()
    
    # Reset counter if it's been more than an hour
    if current_time - ip_last_reset[client_ip] > 3600:
        ip_request_counts[client_ip] = 0
        ip_last_reset[client_ip] = current_time
    
    # Check if rate limit exceeded (10 requests per hour)
    if ip_request_counts[client_ip] >= 10:
        return jsonify({
            "error": "Rate limit exceeded. Please try again later.",
            "remaining_time": int(3600 - (current_time - ip_last_reset[client_ip]))
        }), 429
    
    # Increment request counter
    ip_request_counts[client_ip] += 1
    
    data = request.json
    if not data or 'targets' not in data:
        return jsonify({"error": "No targets provided"}), 400
    
    results = []
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            for target in data['targets']:
                name = target.get('name', '').strip()
                entity_type = target.get('type', 'company').lower()
                
                if not name:
                    continue
                    
                # Insert target into database with user_id
                cursor.execute(
                    "INSERT INTO targets (user_id, name, type) VALUES (%s, %s, %s) RETURNING id",
                    (current_user.id, name, entity_type)
                )
                target_id = cursor.fetchone()['id']
                
                # Fetch contextual data
                if entity_type == 'company':
                    context_data = fetch_company_news(name, current_user.id)
                else:
                    context_data = [{"description": f"{name} is a professional in the industry."}]
                
                # Generate the snippet
                snippet = generate_snippet(name, entity_type, context_data, current_user.id)
                
                # Save the snippet
                cursor.execute(
                    "INSERT INTO snippets (target_id, content, source_data) VALUES (%s, %s, %s)",
                    (target_id, snippet, json.dumps(context_data))
                )
                
                results.append({
                    "name": name,
                    "type": entity_type,
                    "snippet": snippet
                })
            
            conn.commit()
        except Exception as e:
            print(f"Error processing request: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
    
    return jsonify({"results": results})

@app.route('/api/status')
@login_required
@log_performance
def api_status():
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        today = datetime.now().date()
        
        cursor.execute("""
            SELECT openai_tokens_used, news_api_calls 
            FROM api_usage 
            WHERE user_id = %s AND date = %s
        """, (current_user.id, today))
        usage = cursor.fetchone()
        
        cursor.close()
    
    # Set your daily limits
    openai_daily_limit = 100000  # tokens
    news_api_daily_limit = 95    # calls
    
    if not usage:
        usage = {'openai_tokens_used': 0, 'news_api_calls': 0}
    
    return jsonify({
        "openai_tokens_used": usage['openai_tokens_used'],
        "news_api_calls": usage['news_api_calls'],
        "openai_daily_limit": openai_daily_limit,
        "news_api_daily_limit": news_api_daily_limit,
        "within_limits": (
            usage['openai_tokens_used'] < openai_daily_limit and 
            usage['news_api_calls'] < news_api_daily_limit
        )
    })

def send_password_reset_email(user_email):
    token = serializer.dumps(user_email, salt='password-reset-salt')
    reset_url = url_for('reset_password', token=token, _external=True)
    
    msg = Message('Password Reset Request',
                 recipients=[user_email])
    msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email.
'''
    mail.send(msg)

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            send_password_reset_email(email)
        flash('Check your email for instructions to reset your password')
        return redirect(url_for('login'))
    
    return render_template('reset_password_request.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hour expiration
    except:
        flash('The password reset link is invalid or has expired')
        return redirect(url_for('reset_password_request'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        
        # Validate password complexity
        is_valid, message = validate_password(password)
        if not is_valid:
            flash(message)
            return render_template('reset_password.html')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE email = %s",
            (generate_password_hash(password), email)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Your password has been reset')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html')

@app.before_request
def before_request():
    session.permanent = True  # Enable session timeout
    session.modified = True   # Reset the session timeout on each request
    
    if current_user.is_authenticated:
        # Check rate limits and warn if approaching
        limits = check_api_limits(current_user.id)
        openai_usage = limits.get('openai_tokens_used', 0)
        news_api_usage = limits.get('news_api_calls', 0)
        
        if (openai_usage / app.config['OPENAI_DAILY_LIMIT'] >= RATE_LIMIT_WARNING_THRESHOLD or
            news_api_usage / app.config['NEWS_API_DAILY_LIMIT'] >= RATE_LIMIT_WARNING_THRESHOLD):
            flash('Warning: You are approaching your daily API usage limits', 'warning')

@cache_with_timeout(CACHE_TIMEOUT['status'])  # Use 1 minute for status cache
def check_api_limits(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        today = datetime.now().date()
        
        cursor.execute("""
            SELECT openai_tokens_used, news_api_calls 
            FROM api_usage 
            WHERE user_id = %s AND date = %s
        """, (user_id, today))
        usage = cursor.fetchone()
        
        cursor.close()
        
        return {
            "openai_limit_reached": usage['openai_tokens_used'] >= app.config['OPENAI_DAILY_LIMIT'] if usage else False,
            "news_api_limit_reached": usage['news_api_calls'] >= app.config['NEWS_API_DAILY_LIMIT'] if usage else False
        }

# Rate limit warning threshold (80% of limit)
RATE_LIMIT_WARNING_THRESHOLD = 0.8

# Custom error handler
@app.errorhandler(Exception)
def handle_error(error):
    # Don't log or show errors for normal redirects
    if isinstance(error, werkzeug.exceptions.HTTPException) and error.code in [301, 302]:
        return error
    
    logger.error(f'Unhandled exception: {str(error)}', exc_info=True)
    if request.is_json:
        return jsonify({
            'error': 'An internal error occurred',
            'message': str(error) if app.debug else 'Please try again later'
        }), 500
    flash('An unexpected error occurred. Please try again later.', 'error')
    return redirect(url_for('index'))

csrf = CSRFProtect(app)

@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self' *; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' *; "
        "style-src 'self' 'unsafe-inline' *; "
        "font-src 'self' *; "
        "img-src 'self' data: *; "
        "connect-src 'self' *; "
        "frame-src *; "
        "frame-ancestors *; "
        "form-action 'self' *; "
        "base-uri 'self' *"
    )
    return response

# Serve static files in production
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder or 'static', filename)

# Add cache cleanup for Redis
def cleanup_redis_cache():
    try:
        # Delete keys older than 24 hours
        for key_pattern in ['perf:*', 'cache:*']:
            keys = redis_client.keys(key_pattern)
            for key in keys:
                if redis_client.ttl(key) == -1:  # No expiration set
                    redis_client.expire(key, 86400)  # Set 24h expiration
    except redis.exceptions.RedisError as e:
        logger.error(f'Redis cleanup error: {e}')

# Add Redis cleanup to the schedule
def schedule_redis_cleanup():
    cleanup_redis_cache()
    threading.Timer(3600, schedule_redis_cleanup).start()

@app.route('/bookmarklet')
def bookmarklet():
    return render_template('bookmarklet.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

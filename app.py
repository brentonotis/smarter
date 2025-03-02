import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)  # Session timeout after 1 hour

# Initialize Flask-Mail
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

mail = Mail(app)

# Initialize Redis
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url)

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
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
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

# Configure database
def get_db_connection():
    try:
        database_url = os.environ.get('DATABASE_URL')
        if database_url and database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
        if database_url:
            connection = psycopg2.connect(database_url)
        else:
            # Local development fallback
            connection = psycopg2.connect(
                database="outreach_db",
                user="postgres",
                password="postgres",
                host="localhost",
                port="5432"
            )
        
        connection.autocommit = True
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        raise

# Initialize database tables
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tables exist and create them if they don't
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            );
        """)
        users_exists = cursor.fetchone()[0]
        
        if not users_exists:
            cursor.execute('''
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE targets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE snippets (
                id SERIAL PRIMARY KEY,
                target_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                source_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (target_id) REFERENCES targets(id) ON DELETE CASCADE
            )
            ''')

            cursor.execute('''
            CREATE TABLE api_usage (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                date DATE NOT NULL,
                openai_tokens_used INTEGER DEFAULT 0,
                news_api_calls INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, date)
            )
            ''')
        else:
            # Check if user_id column exists in targets table
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'targets' AND column_name = 'user_id'
                );
            """)
            user_id_exists = cursor.fetchone()[0]
            
            if not user_id_exists:
                cursor.execute('''
                    ALTER TABLE targets 
                    ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
                ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        if 'conn' in locals():
            conn.close()

# Update tracking functions to include user_id
def track_openai_usage(user_id, token_count):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().date()
    
    cursor.execute('''
        INSERT INTO api_usage (user_id, date, openai_tokens_used)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, date)
        DO UPDATE SET openai_tokens_used = api_usage.openai_tokens_used + EXCLUDED.openai_tokens_used
    ''', (user_id, today, token_count))
    
    cursor.close()
    conn.close()

def track_news_api_call(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().date()
    
    cursor.execute('''
        INSERT INTO api_usage (user_id, date, news_api_calls)
        VALUES (%s, %s, 1)
        ON CONFLICT (user_id, date)
        DO UPDATE SET news_api_calls = api_usage.news_api_calls + 1
    ''', (user_id, today))
    
    cursor.close()
    conn.close()

def check_api_limits(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.now().date()
    
    cursor.execute("""
        SELECT openai_tokens_used, news_api_calls 
        FROM api_usage 
        WHERE user_id = %s AND date = %s
    """, (user_id, today))
    usage = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not usage:
        return {"openai_limit_reached": False, "news_api_limit_reached": False}
    
    # Set your daily limits - adjust as needed
    openai_daily_limit = 100000  # tokens
    news_api_daily_limit = 95    # calls
    
    return {
        "openai_limit_reached": usage['openai_tokens_used'] >= openai_daily_limit,
        "news_api_limit_reached": usage['news_api_calls'] >= news_api_daily_limit
    }

# Call init_db on startup
with app.app_context():
    init_db()

# Cache decorator
def cache_with_timeout(timeout=300):  # 5 minutes default
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Create a cache key from the function name and arguments
            cache_key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get the cached result
            result = redis_client.get(cache_key)
            if result is not None:
                return json.loads(result)
            
            # If not cached, call the function
            result = f(*args, **kwargs)
            
            # Cache the result
            redis_client.setex(cache_key, timeout, json.dumps(result))
            return result
        return wrapper
    return decorator

# Rate limit warning threshold (80% of limit)
RATE_LIMIT_WARNING_THRESHOLD = 0.8

# Cache the news API results
@cache_with_timeout(300)  # Cache for 5 minutes
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
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user_data and check_password_hash(user_data['password_hash'], password):
                user = User(user_data['id'], user_data['email'], user_data['password_hash'])
                login_user(user)
                return redirect(url_for('index'))
            
            flash('Invalid email or password')
        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred during login. Please try again.')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Email and password are required')
            return render_template('register.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long')
            return render_template('register.html')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email already registered')
                return render_template('register.html')
            
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
            conn.close()
            
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Registration error: {e}")
            flash('An error occurred during registration. Please try again.')
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# Update API routes to use current_user
@app.route('/api/generate', methods=['POST'])
@login_required
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
    conn = get_db_connection()
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
    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
    
    return jsonify({"results": results})

@app.route('/api/status')
@login_required
def api_status():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.now().date()
    
    cursor.execute("""
        SELECT openai_tokens_used, news_api_calls 
        FROM api_usage 
        WHERE user_id = %s AND date = %s
    """, (current_user.id, today))
    usage = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
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
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long')
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

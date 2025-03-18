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
from flask_cors import CORS
import re
import gc
import threading
from db_config import init_db_pool, get_db_connection, release_db_connection, db_pool
import werkzeug.exceptions

# Initialize Flask app first
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this-in-production')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
logger.addHandler(handler)
app.logger.addHandler(handler)

def is_xhr():
    """Check if the request is an AJAX request"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json'

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Initialize Flask-Mail
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
mail = Mail(app)

# Initialize token serializer
serializer = URLSafeTimedSerializer(app.secret_key)

# Configure session
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_DOMAIN'] = None
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_NAME'] = 'smarter_session'

# Configure API limits
app.config['OPENAI_DAILY_LIMIT'] = 100000
app.config['NEWS_API_DAILY_LIMIT'] = 95
RATE_LIMIT_WARNING_THRESHOLD = 0.8

# Rate limiting data structures
ip_request_counts = defaultdict(int)
ip_last_reset = defaultdict(float)
login_attempts = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_TIMEOUT = 900

# Initialize Redis
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
parsed_url = urlparse(redis_url)
use_ssl = parsed_url.scheme == 'rediss'

redis_host = parsed_url.hostname or 'localhost'
redis_port = parsed_url.port or 6379
redis_password = parsed_url.password
redis_db = int(parsed_url.path.lstrip('/')) if parsed_url.path else 0

redis_pool = redis.ConnectionPool(
    host=redis_host,
    port=redis_port,
    password=redis_password,
    db=redis_db,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    max_connections=5,
    retry_on_timeout=True,
    health_check_interval=30,
    connection_class=redis.SSLConnection if use_ssl else redis.Connection,
    ssl_cert_reqs=None  # Disable SSL certificate verification
)
redis_client = redis.Redis(connection_pool=redis_pool)

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": ["https://smarter-865bc5a924ea.herokuapp.com", "chrome-extension://*", "https://www.linkedin.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Requested-With", "Authorization", "Origin", "Accept"],
        "supports_credentials": True,
        "expose_headers": ["Content-Type", "X-CSRFToken"],
        "max_age": 600
    }
})

# Configure OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Configure News API
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
NEWS_API_BASE_URL = "https://newsapi.org/v2"

# Initialize database
try:
    init_db_pool()
    logger.info("Database pool initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database pool: {e}")
    raise

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

def init_db():
    """Initialize database tables"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_companies (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    name VARCHAR(255) NOT NULL,
                    description TEXT NOT NULL,
                    target_industries VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS targets (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    name VARCHAR(255) NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS snippets (
                    id SERIAL PRIMARY KEY,
                    target_id INTEGER REFERENCES targets(id),
                    content TEXT NOT NULL,
                    source_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_usage (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    date DATE NOT NULL,
                    openai_tokens_used INTEGER DEFAULT 0,
                    news_api_calls INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, date)
                )
            ''')
            
            conn.commit()
            cursor.close()
            logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

def init_app():
    """Initialize the application"""
    try:
        # Initialize database pool
        init_db_pool()
        logger.info("Database pool initialized successfully")
        
        # Initialize database tables
        init_db()
        logger.info("Database tables initialized successfully")
        
        # Start cleanup scheduler
        schedule_cleanup()
        logger.info("Cleanup scheduler started successfully")
        
        logger.info("Application initialization completed successfully")
    except Exception as e:
        logger.error(f"Application initialization error: {e}")
        raise

# Initialize the application
with app.app_context():
    init_app()

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
                logger.error(f"Redis error in cache: {e}")
                # If Redis fails, just execute the function without caching
                return f(*args, **kwargs)
            finally:
                # Ensure we're not keeping connections open
                try:
                    redis_client.connection_pool.reset()
                except:
                    pass
        return decorated_function
    return decorator

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

@app.before_request
def before_request():
    session.permanent = True  # Enable session timeout
    session.modified = True   # Reset the session timeout on each request
    
    # Ensure database pool is initialized
    if db_pool is None:
        try:
            init_db_pool()
        except Exception as e:
            logger.error(f"Failed to initialize database pool in before_request: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Database connection error'
            }), 500
    
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

@app.after_request
def add_security_headers(response):
    # Get the origin from the request
    origin = request.headers.get('Origin')
    
    # Only set CORS headers if there's an origin
    if origin and (origin in ["https://smarter-865bc5a924ea.herokuapp.com", "https://www.linkedin.com"] or 
                  origin.startswith("chrome-extension://")):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With, Authorization, Origin, Accept'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    
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
        "base-uri 'self' *; "
        "trusted-types 'allow-duplicates' default jSecure highcharts dompurify goog#html"
    )
    return response

# Configure static file serving
app.static_folder = 'static'
app.static_url_path = '/static'

@app.route('/static/<path:filename>')
def serve_static(filename):
    try:
        response = send_from_directory(app.static_folder, filename)
        response.headers['Cache-Control'] = 'public, max-age=31536000'
        return response
    except Exception as e:
        app.logger.error(f"Error serving static file {filename}: {str(e)}")
        return jsonify({'error': 'File not found'}), 404

@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except Exception as e:
        app.logger.error(f"Error serving favicon: {str(e)}")
        return '', 204

# Add error handler for 404
@app.errorhandler(404)
def not_found_error(error):
    if request.is_json:
        return jsonify({'error': 'Not found'}), 404
    return render_template('404.html'), 404

# Add error handler for 500
@app.errorhandler(500)
def internal_error(error):
    if request.is_json:
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('500.html'), 500

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

def fetch_company_news(company_name):
    """Fetch recent news articles about a company using News API"""
    try:
        # Check if we've hit the daily limit
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            today = datetime.now().date()
            
            cursor.execute("""
                SELECT news_api_calls 
                FROM api_usage 
                WHERE user_id = %s AND date = %s
            """, (current_user.id, today))
            usage = cursor.fetchone()
            
            if usage and usage['news_api_calls'] >= app.config['NEWS_API_DAILY_LIMIT']:
                logger.warning(f"News API daily limit reached for user {current_user.id}")
                return []
            
            # Update usage count
            cursor.execute("""
                INSERT INTO api_usage (user_id, date, news_api_calls)
                VALUES (%s, %s, 1)
                ON CONFLICT (user_id, date)
                DO UPDATE SET news_api_calls = api_usage.news_api_calls + 1
            """, (current_user.id, today))
            conn.commit()
            cursor.close()
        
        # Make request to News API
        params = {
            'q': company_name,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 5,  # Get 5 most recent articles
            'apiKey': NEWS_API_KEY
        }
        
        response = requests.get(f"{NEWS_API_BASE_URL}/everything", params=params)
        response.raise_for_status()
        
        articles = response.json().get('articles', [])
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching news for {company_name}: {str(e)}")
        return []

@app.route('/api/analyze', methods=['POST'])
@login_required
def analyze_page():
    try:
        data = request.json
        if not data or 'url' not in data:
            return jsonify({
                'status': 'error',
                'message': 'No URL provided'
            }), 400

        url = data['url']
        
        # Here you would implement your page analysis logic
        # For now, we'll return a mock response
        return jsonify({
            'status': 'success',
            'message': f'Successfully analyzed {url}. This is a placeholder response.'
        })
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred during analysis.'
        }), 500

@app.route('/api/extension/login', methods=['POST'])
def extension_login():
    try:
        logger.info("Extension login attempt received")
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            logger.warning("Missing email or password in login attempt")
            return jsonify({
                'status': 'error',
                'message': 'Email and password are required'
            }), 400
        
        # Check if login is allowed
        if not is_login_allowed(email):
            remaining_time = int(LOGIN_TIMEOUT - (time.time() - login_attempts[email][0]))
            logger.warning(f"Too many login attempts for email: {email}")
            return jsonify({
                'status': 'error',
                'message': f'Too many login attempts. Please try again in {remaining_time//60} minutes.'
            }), 429
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_data = cursor.fetchone()
            cursor.close()
            
            if user_data and check_password_hash(user_data['password_hash'], password):
                user = User(user_data['id'], user_data['email'], user_data['password_hash'])
                login_user(user, remember=True)  # Enable remember me
                session.permanent = True
                
                # Clear login attempts on successful login
                login_attempts[email] = []
                
                logger.info(f"Successful login for user: {email}")
                return jsonify({
                    'status': 'success',
                    'message': 'Login successful',
                    'user': {
                        'email': user.email,
                        'id': user.id
                    }
                })
            
            # Record failed attempt
            login_attempts[email].append(time.time())
            logger.warning(f"Failed login attempt for email: {email}")
            
            return jsonify({
                'status': 'error',
                'message': 'Invalid email or password'
            }), 401
            
    except Exception as e:
        logger.error(f"Extension login error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred during login. Please try again.'
        }), 500

@app.route('/api/extension/login-form', methods=['GET'])
def extension_login_form():
    try:
        # If user is already logged in, return success
        if current_user.is_authenticated:
            return jsonify({
                'status': 'success',
                'message': 'Already logged in',
                'user': {
                    'email': current_user.email,
                    'id': current_user.id
                }
            })
        
        # Generate a new CSRF token
        form = FlaskForm()
        csrf_token = form.csrf_token.current_token
        
        # Return the login form HTML with the CSRF token
        return jsonify({
            'status': 'success',
            'html': render_template('extension_login.html', form=form),
            'csrf_token': csrf_token
        })
    except Exception as e:
        logger.error(f"Extension login form error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while loading the login form.'
        }), 500

@app.route('/api/company-info', methods=['GET', 'POST'])
@login_required
def company_info():
    # Ensure database pool is initialized
    global db_pool
    if db_pool is None:
        try:
            init_db_pool()
            logger.info("Database pool initialized in company_info route")
        except Exception as e:
            logger.error(f"Failed to initialize database pool in company_info: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Database connection error'
            }), 500

    if request.method == 'GET':
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(
                    "SELECT name, description, target_industries FROM user_companies WHERE user_id = %s",
                    (current_user.id,)
                )
                company = cursor.fetchone()
                cursor.close()
                
                return jsonify({
                    'status': 'success',
                    'company': company
                })
        except Exception as e:
            logger.error(f"Error fetching company info: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Error fetching company information'
            }), 500
    
    else:  # POST
        try:
            # Validate content type
            if not request.is_json:
                logger.warning("Invalid content type in company info update")
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid content type. Expected application/json'
                }), 400

            data = request.json
            logger.info(f"Received company info update request: {data}")
            
            if not data:
                logger.warning("No JSON data received in company info update")
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400
                
            if not data.get('name') or not data.get('description'):
                logger.warning(f"Missing required fields in company info update: {data}")
                return jsonify({
                    'status': 'error',
                    'message': 'Company name and description are required'
                }), 400
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                try:
                    logger.info(f"Updating company info for user {current_user.id}")
                    cursor.execute('''
                        INSERT INTO user_companies (user_id, name, description, target_industries)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (user_id)
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            target_industries = EXCLUDED.target_industries,
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id
                    ''', (
                        current_user.id,
                        data['name'],
                        data['description'],
                        data.get('target_industries', '')
                    ))
                    company_id = cursor.fetchone()[0]
                    conn.commit()
                    logger.info(f"Successfully updated company info for user {current_user.id}")
                    return jsonify({
                        'status': 'success',
                        'message': 'Company information saved successfully'
                    })
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Database error during company info update: {str(e)}", exc_info=True)
                    return jsonify({
                        'status': 'error',
                        'message': 'Error saving company information'
                    }), 500
                finally:
                    cursor.close()
        except Exception as e:
            logger.error(f"Error in company info update: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Error processing company information update'
            }), 500

@app.route('/')
@login_required
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}", exc_info=True)
        return render_template('500.html'), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not email or not password:
                message = 'Email and password are required'
                if is_xhr():
                    return jsonify({'status': 'error', 'message': message}), 400
                flash(message, 'error')
                return render_template('login.html')
            
            # Check if login is allowed
            if not is_login_allowed(email):
                remaining_time = int(LOGIN_TIMEOUT - (time.time() - login_attempts[email][0]))
                message = f'Too many login attempts. Please try again in {remaining_time//60} minutes.'
                if is_xhr():
                    return jsonify({'status': 'error', 'message': message}), 429
                flash(message, 'error')
                return render_template('login.html')
            
            with get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user_data = cursor.fetchone()
                cursor.close()
                
                if user_data and check_password_hash(user_data['password_hash'], password):
                    user = User(user_data['id'], user_data['email'], user_data['password_hash'])
                    login_user(user, remember=True)
                    
                    # Clear login attempts on successful login
                    login_attempts[email] = []
                    
                    next_page = request.args.get('next')
                    if not next_page or urlparse(next_page).netloc != '':
                        next_page = url_for('index')
                    
                    if is_xhr():
                        return jsonify({
                            'status': 'success',
                            'message': 'Login successful',
                            'redirect': next_page
                        })
                    return redirect(next_page)
                
                # Record failed attempt
                login_attempts[email].append(time.time())
                message = 'Invalid email or password'
                if is_xhr():
                    return jsonify({'status': 'error', 'message': message}), 401
                flash(message, 'error')
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}", exc_info=True)
            message = 'An error occurred during login. Please try again.'
            if is_xhr():
                return jsonify({'status': 'error', 'message': message}), 500
            flash(message, 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if not email or not password or not confirm_password:
                flash('All fields are required', 'error')
                return render_template('register.html')
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('register.html')
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('Email already registered', 'error')
                    return render_template('register.html')
                
                # Create new user
                password_hash = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                    (email, password_hash)
                )
                user_id = cursor.fetchone()[0]
                conn.commit()
                cursor.close()
                
                # Log in the new user
                user = User(user_id, email, password_hash)
                login_user(user)
                
                flash('Registration successful!', 'success')
                return redirect(url_for('index'))
                
        except Exception as e:
            logger.error(f"Registration error: {str(e)}", exc_info=True)
            flash('An error occurred during registration. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def is_login_allowed(email):
    """Check if login is allowed for the given email"""
    current_time = time.time()
    # Remove attempts older than timeout
    login_attempts[email] = [t for t in login_attempts[email] if current_time - t < LOGIN_TIMEOUT]
    # Check if number of recent attempts exceeds limit
    return len(login_attempts[email]) < MAX_LOGIN_ATTEMPTS

@app.route('/api/generate', methods=['POST'])
@login_required
def generate_snippets():
    try:
        data = request.json
        if not data or 'targets' not in data or 'userCompany' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required data'
            }), 400

        targets = data['targets']
        user_company = data['userCompany']

        # Save targets to database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            results = []
            
            for target in targets:
                # Insert target
                cursor.execute(
                    "INSERT INTO targets (user_id, name, type) VALUES (%s, %s, %s) RETURNING id",
                    (current_user.id, target['name'], target['type'])
                )
                target_id = cursor.fetchone()[0]
                
                # Fetch recent news about the target company
                news_articles = []
                if target['type'] == 'company':
                    news_articles = fetch_company_news(target['name'])
                
                # Prepare news context for the prompt
                news_context = ""
                if news_articles:
                    news_context = "\nRecent News:\n"
                    for article in news_articles:
                        news_context += f"- {article['title']} ({article['publishedAt']})\n"
                
                # Generate snippet using OpenAI
                prompt = f"""Generate a personalized outreach message for {target['name']} ({target['type']}) from {user_company['name']}.
                
                Company Information:
                Name: {user_company['name']}
                Description: {user_company['description']}
                Target Industries: {user_company['target_industries']}
                
                Target:
                Name: {target['name']}
                Type: {target['type']}
                {news_context}
                
                Generate a professional, personalized outreach message that:
                1. References recent news about the target company (if available)
                2. Highlights how your company's solution aligns with their current needs
                3. Demonstrates understanding of their industry and challenges
                4. Provides specific value proposition and potential benefits
                
                Make the message conversational and engaging while maintaining professionalism."""
                
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a professional sales outreach specialist who creates personalized, engaging messages based on company information and recent news."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )
                
                snippet = response.choices[0].message.content.strip()
                
                # Save snippet with source data
                cursor.execute(
                    "INSERT INTO snippets (target_id, content, source_data) VALUES (%s, %s, %s)",
                    (target_id, snippet, json.dumps({'news_articles': news_articles}))
                )
                
                results.append({
                    'name': target['name'],
                    'type': target['type'],
                    'snippet': snippet,
                    'news_articles': news_articles
                })
            
            conn.commit()
            cursor.close()
            
            return jsonify({
                'status': 'success',
                'results': results
            })
            
    except Exception as e:
        logger.error(f"Generate snippets error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while generating snippets.'
        }), 500

@app.route('/api/status')
@login_required
def get_api_status():
    try:
        limits = check_api_limits(current_user.id)
        return jsonify({
            'openai_tokens_used': limits.get('openai_tokens_used', 0),
            'openai_daily_limit': app.config['OPENAI_DAILY_LIMIT'],
            'news_api_calls': limits.get('news_api_calls', 0),
            'news_api_daily_limit': app.config['NEWS_API_DAILY_LIMIT'],
            'within_limits': not (limits.get('openai_limit_reached', False) or limits.get('news_api_limit_reached', False))
        })
    except Exception as e:
        logger.error(f"Error getting API status: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Failed to get API status'
        }), 500

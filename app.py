import os
from flask import Flask, request, jsonify, render_template
import requests
import json
import openai
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import time
from collections import defaultdict

app = Flask(__name__)

# Configure OpenAI API
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Rate limiting data structures
ip_request_counts = defaultdict(int)
ip_last_reset = defaultdict(float)

# Configure database
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        result = urlparse(database_url)
        username = result.username
        password = result.password
        database = result.path[1:]
        hostname = result.hostname
        port = result.port
        connection = psycopg2.connect(
            database=database,
            user=username,
            password=password,
            host=hostname,
            port=port
        )
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

# Initialize database tables
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS targets (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
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
        date DATE NOT NULL,
        openai_tokens_used INTEGER DEFAULT 0,
        news_api_calls INTEGER DEFAULT 0
    )
    ''')
    
    cursor.close()
    conn.close()

def track_openai_usage(token_count):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().date()
    
    # Check if we have a record for today
    cursor.execute("SELECT id FROM api_usage WHERE date = %s", (today,))
    record = cursor.fetchone()
    
    if record:
        # Update existing record
        cursor.execute("UPDATE api_usage SET openai_tokens_used = openai_tokens_used + %s WHERE date = %s", 
                     (token_count, today))
    else:
        # Create new record
        cursor.execute("INSERT INTO api_usage (date, openai_tokens_used) VALUES (%s, %s)", 
                     (today, token_count))
    
    cursor.close()
    conn.close()

def track_news_api_call():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().date()
    
    # Check if we have a record for today
    cursor.execute("SELECT id FROM api_usage WHERE date = %s", (today,))
    record = cursor.fetchone()
    
    if record:
        # Update existing record
        cursor.execute("UPDATE api_usage SET news_api_calls = news_api_calls + 1 WHERE date = %s", (today,))
    else:
        # Create new record
        cursor.execute("INSERT INTO api_usage (date, news_api_calls) VALUES (%s, 1)", (today,))
    
    cursor.close()
    conn.close()

def check_api_limits():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.now().date()
    
    cursor.execute("SELECT openai_tokens_used, news_api_calls FROM api_usage WHERE date = %s", (today,))
    usage = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not usage:
        return {"openai_limit_reached": False, "news_api_limit_reached": False}
    
    # Set your daily limits - adjust as needed
    openai_daily_limit = 100000  # tokens
    news_api_daily_limit = 95    # calls (free tier limit is 100)
    
    return {
        "openai_limit_reached": usage['openai_tokens_used'] >= openai_daily_limit,
        "news_api_limit_reached": usage['news_api_calls'] >= news_api_daily_limit
    }

# Call init_db on startup
with app.app_context():
    init_db()

# API endpoint to fetch company news
def fetch_company_news(company_name):
    # Check limits first
    limits = check_api_limits()
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
    track_news_api_call()
    
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
def generate_snippet(name, entity_type, context_data):
    # Check limits first
    limits = check_api_limits()
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
        track_openai_usage(total_tokens)
        
        return response.choices[0].message["content"].strip()
    except Exception as e:
        print(f"Error generating snippet: {e}")
        return f"I noticed that {name} has been making waves in the industry lately. Our solution could help you capitalize on this momentum by streamlining your operations."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
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
                
            # Insert target into database
            cursor.execute(
                "INSERT INTO targets (name, type) VALUES (%s, %s) RETURNING id",
                (name, entity_type)
            )
            target_id = cursor.fetchone()['id']
            
            # Fetch contextual data
            if entity_type == 'company':
                context_data = fetch_company_news(name)
            else:  # person
                # This is a placeholder - in a real app, you'd fetch person-specific data
                context_data = [{"description": f"{name} is a professional in the industry."}]
            
            # Generate the snippet
            snippet = generate_snippet(name, entity_type, context_data)
            
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
def api_status():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.now().date()
    
    cursor.execute("SELECT openai_tokens_used, news_api_calls FROM api_usage WHERE date = %s", (today,))
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

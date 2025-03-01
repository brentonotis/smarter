import os
from flask import Flask, request, jsonify, render_template
import requests
import json
import openai
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

app = Flask(__name__)

# Configure OpenAI API
openai.api_key = os.environ.get("OPENAI_API_KEY")

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
    
    cursor.close()
    conn.close()

# Call init_db on startup
with app.app_context():
    init_db()

# API endpoint to fetch company news
def fetch_company_news(company_name):
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
        
        return response.choices[0].message["content"].strip()
    except Exception as e:
        print(f"Error generating snippet: {e}")
        return f"I noticed that {name} has been making waves in the industry lately. Our solution could help you capitalize on this momentum by streamlining your operations."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate():
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

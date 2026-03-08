"""
Serverless API endpoint for generating personalized outreach snippets using Claude.
Deploy to Vercel (or adapt for Cloudflare Workers / AWS Lambda).

Environment variables required:
  ANTHROPIC_API_KEY - Your Anthropic API key
  NEWS_API_KEY      - (Optional) News API key for fetching recent company news
"""

import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.parse

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-4-20250514"


def call_claude(system, user_prompt, max_tokens=400):
    """Call the Anthropic Messages API directly via urllib."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode()

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data["content"][0]["text"].strip()


def fetch_company_news(company_name):
    """Fetch recent news articles about a company using News API (optional)."""
    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        return []

    try:
        params = urllib.parse.urlencode({
            "q": f'"{company_name}"',
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": api_key,
            "searchIn": "title,description",
        })
        url = f"https://newsapi.org/v2/everything?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("articles", [])
    except Exception:
        return []


def build_prompt(target, company, news_articles):
    """Build the Claude prompt for generating an outreach snippet."""
    news_context = ""
    if news_articles:
        news_context = "\nRecent News:\n"
        for article in news_articles:
            news_context += f"Title: {article.get('title', '')}\n"
            if article.get("description"):
                news_context += f"Description: {article['description']}\n"
            if article.get("content"):
                news_context += f"Content: {article['content']}\n"
            source_name = article.get("source", {}).get("name", "Unknown")
            news_context += f"Source: {source_name} ({article.get('publishedAt', '')})\n\n"

    return f"""Generate a personalized outreach message for {target['name']} ({target['type']}) from {company['name']}.

Company Information:
Name: {company['name']}
Description: {company['description']}
Target Industries: {company.get('target_industries', 'N/A')}

Target:
Name: {target['name']}
Type: {target['type']}
{news_context}

Generate a concise, data-driven outreach message that:
1. Opens with a specific metric or insight (from news if available, or a relevant industry observation)
2. Makes a clear connection between their current situation and the sender's solution
3. Includes a specific value proposition based on the sender's actual capabilities
4. Ends with a clear next step

Requirements:
- Keep the message under 3-4 sentences
- Be direct and avoid corporate jargon
- Focus on concrete benefits rather than features
- If you have recent news about their company, lead with that specific data point
- After the message, add a line with "Source: [News Source Name] ([Date])" for any metrics cited
- Value propositions should be realistic and based on the company's actual capabilities"""


SYSTEM_PROMPT = (
    "You are a data-driven sales professional who creates concise, impactful "
    "outreach messages. You focus on specific metrics, recent news, and concrete "
    "value propositions. Your messages are short, direct, and designed for busy "
    "executives. You always cite sources when available and make realistic claims "
    "based on actual capabilities."
)


def generate_snippets(targets, company):
    """Call Claude to generate outreach snippets for each target."""
    results = []

    for target in targets:
        news_articles = []
        if target.get("type") == "company":
            news_articles = fetch_company_news(target["name"])

        prompt = build_prompt(target, company, news_articles)
        snippet = call_claude(SYSTEM_PROMPT, prompt, max_tokens=400)

        results.append({
            "name": target["name"],
            "type": target["type"],
            "snippet": snippet,
        })

    return results


def add_cors_headers(handler):
    """Add CORS headers to allow cross-origin requests from the frontend."""
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        add_cors_headers(self)
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))

            targets = body.get("targets", [])
            company = body.get("company", {})

            if not targets:
                self.send_response(400)
                add_cors_headers(self)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"message": "No targets provided"}).encode())
                return

            if not company.get("name") or not company.get("description"):
                self.send_response(400)
                add_cors_headers(self)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Company name and description are required"}).encode())
                return

            results = generate_snippets(targets, company)

            self.send_response(200)
            add_cors_headers(self)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "results": results}).encode())

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.readable() else str(e)
            self.send_response(502)
            add_cors_headers(self)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": f"Claude API error ({e.code}): {error_body}"}).encode())

        except Exception as e:
            self.send_response(500)
            add_cors_headers(self)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": f"Internal error: {type(e).__name__}: {str(e)}"}).encode())

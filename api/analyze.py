"""
Serverless API endpoint for analyzing a web page URL using Claude.
Used by the Chrome extension to generate insights about any page you're viewing.

Environment variables required:
  ANTHROPIC_API_KEY - Your Anthropic API key
"""

import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-4-20250514"


def call_claude(system, user_prompt, max_tokens=500):
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


def fetch_page_text(url):
    """Fetch the text content of a URL (basic extraction)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SalesCopilot/1.0)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Basic HTML-to-text: strip tags and collapse whitespace
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        # Limit to ~4000 chars to stay within reasonable token limits
        return text[:4000]
    except Exception:
        return ""


def analyze_page(url, page_text, company):
    """Use Claude to analyze the page and generate sales-relevant insights."""
    company_context = ""
    if company and company.get("name"):
        company_context = f"""
Your Company Context:
Name: {company['name']}
Description: {company.get('description', 'N/A')}
Target Industries: {company.get('target_industries', 'N/A')}
"""

    prompt = f"""Analyze this web page and provide sales-relevant insights.

URL: {url}

Page Content:
{page_text}
{company_context}

Provide a brief analysis including:
1. Who/what is this page about?
2. Key insights relevant for sales outreach
3. Potential pain points or opportunities you can identify
4. A suggested opening line for outreach based on what you see

Keep your response concise and actionable."""

    system = (
        "You are a sales intelligence analyst. You analyze web pages and extract "
        "insights that help sales professionals craft personalized outreach. Be "
        "specific, concise, and focus on actionable intelligence."
    )
    return call_claude(system, prompt, max_tokens=500)


def add_cors_headers(handler):
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

            url = body.get("url", "")
            company = body.get("company", {})

            if not url:
                self.send_response(400)
                add_cors_headers(self)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"message": "No URL provided"}).encode())
                return

            page_text = fetch_page_text(url)

            if not page_text:
                # Even without page text, Claude can infer from the URL
                page_text = "(Could not fetch page content; analyze based on URL alone)"

            analysis = analyze_page(url, page_text, company)

            self.send_response(200)
            add_cors_headers(self)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "analysis": analysis,
                "url": url
            }).encode())

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

"""
Serverless API endpoint for analyzing a web page and returning structured
sales intelligence. The Chrome extension sends page text directly
(extracted client-side), so it sees JS-rendered content.

Falls back to server-side fetch if page_text is not provided.

Environment variables required:
  ANTHROPIC_API_KEY - Your Anthropic API key
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-4-20250514"
MAX_BODY_BYTES = 200_000
MAX_PAGE_TEXT_CHARS = 6000


def call_claude(system, user_prompt, max_tokens=600):
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return data["content"][0]["text"].strip()


def add_cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def send_json(handler, status, data):
    handler.send_response(status)
    add_cors_headers(handler)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())


# ---------------------------------------------------------------------------
# Server-side page fetch (fallback)
# ---------------------------------------------------------------------------

def fetch_page_text(url):
    """Fetch the text content of a URL (basic extraction)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SalesCopilot/2.0)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_PAGE_TEXT_CHARS]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Prompt & analysis
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a sales intelligence analyst. You analyze web pages and extract "
    "actionable insights for sales professionals. You MUST respond with valid "
    "JSON only — no markdown, no commentary outside the JSON."
)


def build_analyze_prompt(url, page_text, company):
    company_context = ""
    if company and company.get("name"):
        company_context = f"""
Your Company Context (the seller):
  Name: {company['name']}
  Description: {company.get('description', 'N/A')}
  Target Industries: {company.get('target_industries', 'N/A')}
"""

    return f"""Analyze this web page and return a JSON object with exactly these keys:

{{
  "overview": "1-2 sentence summary of who/what this page is about",
  "insights": ["insight 1", "insight 2", "insight 3"],
  "pain_points": ["pain point or opportunity 1", "pain point or opportunity 2"],
  "outreach_line": "A ready-to-use opening line for a sales email or LinkedIn message",
  "tags": ["tag1", "tag2"]
}}

Rules:
- "insights" should contain 2-4 bullets of sales-relevant intelligence (funding, growth, tech stack, hiring signals, recent news, leadership changes)
- "pain_points" should contain 1-3 potential problems or opportunities the seller could address
- "outreach_line" should be specific, personalized, and reference something concrete from the page
- "tags" should contain 2-4 short labels (e.g., "SaaS", "Series B", "Hiring", "Enterprise")
- Return ONLY the JSON object, nothing else

URL: {url}

Page Content:
{page_text[:MAX_PAGE_TEXT_CHARS]}
{company_context}"""


def analyze_page(url, page_text, company):
    """Call Claude and parse the structured JSON response."""
    prompt = build_analyze_prompt(url, page_text, company)
    raw = call_claude(SYSTEM_PROMPT, prompt, max_tokens=600)

    # Strip ```json ... ``` markers if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        result = {
            "overview": cleaned[:300],
            "insights": [],
            "pain_points": [],
            "outreach_line": "",
            "tags": [],
        }
    return result


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        add_cors_headers(self)
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_BODY_BYTES:
                return send_json(self, 413, {"message": "Request body too large"})

            body = json.loads(self.rfile.read(content_length))
            url = body.get("url", "").strip()
            company = body.get("company", {})
            page_text = body.get("page_text", "").strip()

            if not url:
                return send_json(self, 400, {"message": "No URL provided"})

            # Prefer client-supplied page text; fall back to server fetch
            if not page_text:
                page_text = fetch_page_text(url)
            if not page_text:
                page_text = "(Could not fetch page content; analyze based on URL alone)"

            analysis = analyze_page(url, page_text, company)
            send_json(self, 200, {"status": "success", "analysis": analysis, "url": url})

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.readable() else str(e)
            send_json(self, 502, {"message": f"Claude API error ({e.code}): {error_body}"})

        except Exception as e:
            send_json(self, 500, {"message": f"Internal error: {type(e).__name__}: {str(e)}"})

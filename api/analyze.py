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
    "You are an elite B2B sales copywriter. You write ultra-short cold outreach "
    "messages (25-50 words) at a 5th-grade reading level. No jargon, no fluff, "
    "no filler words. Every word earns its place. You MUST respond with valid "
    "JSON only — no markdown, no commentary outside the JSON."
)


def build_analyze_prompt(url, page_text, company, attempt=0):
    company_context = ""
    if company and company.get("name"):
        company_context = f"""
Seller Context:
  Company: {company['name']}
  What they do: {company.get('description', 'N/A')}
  Target Industries: {company.get('target_industries', 'N/A')}
"""

    # Vary the angle on each regeneration to avoid repeating the same message
    angle_instructions = ""
    if attempt > 0:
        angles = [
            "Focus on a DIFFERENT observation than before. Try a hiring signal or team growth angle.",
            "Focus on a DIFFERENT observation than before. Try a competitive landscape or market timing angle.",
            "Focus on a DIFFERENT observation than before. Try a technology stack or product launch angle.",
            "Focus on a DIFFERENT observation than before. Try a leadership change or company milestone angle.",
            "Focus on a DIFFERENT observation than before. Try an industry trend or customer pain angle.",
        ]
        angle_instructions = f"\nIMPORTANT: {angles[attempt % len(angles)]}\n"

    return f"""Analyze this web page and return a JSON object with exactly these keys:

{{
  "overview": "1 sentence: who is this company/person and what do they do",
  "tags": ["tag1", "tag2", "tag3"],
  "insights": ["insight 1", "insight 2", "insight 3"],
  "outreach": {{
    "observation": "1 sentence: a specific, personalized detail showing you did research (recent news, role change, funding, hiring, product launch)",
    "problem": "1 sentence: connect that observation to a pain point or opportunity relevant to their role",
    "credibility": "1 sentence: briefly state how the seller has solved this for similar companies (social proof)",
    "solution": "1 sentence: quick explanation of the seller's unique approach or value",
    "ctc": "1 open-ended question that starts a dialogue — easy to reply to, NOT asking to book a meeting (e.g., 'Curious if this resonates?', 'Is this on your radar?', 'How are you thinking about this?')"
  }}
}}

STRICT RULES FOR THE OUTREACH (THESE ARE HARD LIMITS):
- The ENTIRE outreach (all 5 parts combined) MUST be 25-50 words total. NOT 50+. Count each word before responding. If over 50, cut words until you're under.
- Each part should be 5-10 words. Aim for 8 words average per part (5 parts x 8 words = 40 words).
- Write at a 5th-grade reading level. Simple words. Short sentences. No jargon.
- No filler: "I hope this finds you well", "I wanted to reach out", "I noticed that"
- No buzzwords: "synergy", "leverage", "optimize", "streamline", "cutting-edge", "empower"
- The CTC must be easy to answer — NOT "Can we schedule a call?" or "Do you have 15 minutes?"
- Be specific. Reference real details from the page.
- Shorter is ALWAYS better. Every word must earn its place.
{angle_instructions}
RULES FOR OTHER FIELDS:
- "overview" should be 1 concise sentence
- "tags" should be 2-4 short labels (e.g., "SaaS", "Series B", "Hiring", "Enterprise")
- "insights" should be 2-4 bullets of sales intelligence (funding, growth, hiring, tech stack, news, leadership)
- Return ONLY the JSON object, nothing else

URL: {url}

Page Content:
{page_text[:MAX_PAGE_TEXT_CHARS]}
{company_context}"""


def analyze_page(url, page_text, company, attempt=0):
    """Call Claude and parse the structured JSON response."""
    prompt = build_analyze_prompt(url, page_text, company, attempt)
    raw = call_claude(SYSTEM_PROMPT, prompt, max_tokens=700)

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
            "tags": [],
            "outreach": {
                "observation": "",
                "problem": "",
                "credibility": "",
                "solution": "",
                "ctc": "",
            },
        }

    # Ensure outreach is structured (handle old-format responses gracefully)
    if "outreach_line" in result and "outreach" not in result:
        result["outreach"] = {
            "observation": result.pop("outreach_line", ""),
            "problem": "",
            "credibility": "",
            "solution": "",
            "ctc": "",
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

            attempt = body.get("attempt", 0)
            analysis = analyze_page(url, page_text, company, attempt)
            send_json(self, 200, {"status": "success", "analysis": analysis, "url": url})

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.readable() else str(e)
            send_json(self, 502, {"message": f"Claude API error ({e.code}): {error_body}"})

        except Exception as e:
            send_json(self, 500, {"message": f"Internal error: {type(e).__name__}: {str(e)}"})

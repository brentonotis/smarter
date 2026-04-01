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

def _strip_html(html):
    """Strip script/style tags and HTML markup, returning plain text."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_page_text(url):
    """Fetch the text content of a URL (basic extraction)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SalesCopilot/2.0)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        return _strip_html(html)[:MAX_PAGE_TEXT_CHARS]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Leadership page discovery — crawl /about, /team, etc. to find executives
# ---------------------------------------------------------------------------

LEADERSHIP_PATHS = [
    "/about", "/about-us", "/about/team", "/about/leadership",
    "/team", "/our-team", "/leadership", "/management",
    "/company", "/company/team", "/company/leadership",
    "/people", "/executives", "/management-team",
]

def fetch_leadership_text(base_url, max_chars=4000):
    """Try common leadership/about pages and return combined text."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(base_url)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))

    combined = []
    chars_so_far = 0

    for path in LEADERSHIP_PATHS:
        if chars_so_far >= max_chars:
            break
        try:
            target = origin + path
            req = urllib.request.Request(target, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SalesCopilot/2.0)"
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                # Only process if we got a 200 and it's HTML
                if resp.status == 200:
                    ctype = resp.headers.get("Content-Type", "")
                    if "html" in ctype.lower():
                        html = resp.read().decode("utf-8", errors="ignore")
                        text = _strip_html(html)
                        if len(text) > 100:  # skip near-empty pages
                            chunk = text[:max_chars - chars_so_far]
                            combined.append(f"[Page: {path}]\n{chunk}")
                            chars_so_far += len(chunk)
        except Exception:
            continue

    return "\n\n".join(combined)


# ---------------------------------------------------------------------------
# Web search for leadership — LinkedIn + general web
# ---------------------------------------------------------------------------

def _search_web(query, max_results=5):
    """Search DuckDuckGo HTML and return snippet text from results."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Extract result snippets from DuckDuckGo HTML results
        results = []
        # DuckDuckGo HTML uses class="result__snippet" for snippets
        # and class="result__title" for titles
        snippets = re.findall(
            r'class="result__(?:title|snippet)"[^>]*>(.*?)</(?:a|td)>',
            html, re.DOTALL
        )
        for s in snippets[:max_results * 2]:
            text = re.sub(r"<[^>]+>", "", s).strip()
            if text and len(text) > 10:
                results.append(text)

        return " | ".join(results[:max_results * 2])
    except Exception:
        return ""


def search_leadership_web(company_name, max_chars=3000):
    """Search LinkedIn and the web for company leadership info."""
    results = []

    queries = [
        (f'{company_name} CEO OR president OR COO OR "VP of operations" site:linkedin.com', "LinkedIn"),
        (f'{company_name} "chief executive officer" OR "brand president" OR "chief operating officer" OR "VP operations"', "Executive Titles"),
        (f'{company_name} leadership team management executive', "Leadership Team"),
        (f'{company_name} org chart OR "management team" OR executives', "Org Chart"),
        (f'site:linkedin.com/in {company_name} CEO OR president OR COO OR operations', "LinkedIn Profiles"),
    ]

    for query, label in queries:
        text = _search_web(query)
        if text:
            results.append(f"[{label}]\n{text}")

    combined = "\n\n".join(results)
    return combined[:max_chars]


# ---------------------------------------------------------------------------
# Case study knowledge base — real metrics for credibility statements
# ---------------------------------------------------------------------------

CASE_STUDIES = """
CASE STUDY 1: Green Home Solutions (Mold Remediation)
- 200 franchise locations, 60 franchisees, 50+ employees
- Won 5 Franchisee Satisfaction Awards
- Pain: managing lead capture, scheduling, invoicing across distributed locations
- Result: eliminated workflow bottlenecks, enhanced vendor integration via open API
- Quote (Al Winnick, COO): "The people made it an obvious choice. We knew the team would support us not only launching, but as we grow."

CASE STUDY 2: Cabinet IQ (Cabinet & Countertop Remodeling)
- Grew from 4 to 6 locations within 11 months of launch
- Consolidated 5 separate software platforms into 1 unified CRM
- Pain: unmanageable operations across five separate tools
- Result: unified scheduling, sales automation, texting, QuickBooks integration, mobile access
- Quote (Jacob Collums, VP Franchise Development): "ServiceMinder was able to solve problems we didn't even know we had!"

CASE STUDY 3: Kitchen Solvers (Kitchen & Bathroom Remodeling)
- Grew from 20 to 42 locations in 3 years (110% growth)
- Pain: outgrown existing CRM, lacked scalability for expanding franchise network
- Result: streamlined workflows, improved customer service, contact management, email campaigns, proposal creation, scheduling
- Quote (Joanne DuCharme, Onboarding Specialist): "I have been amazed at the helpfulness of the client success team."

CASE STUDY 4: Mosquito Squad (Pest & Mosquito Control, Authority Brands)
- 116 locations, 116 franchise owners
- Tripled business efficiency
- 5 years on the platform
- Pain: manual, non-digital workflows; lack of consistency across locations
- Result: dispatch/scheduling improvements, call tracking, texting, reputation management, digital marketing
- Quote (Hugh Jones, Director of Product, Authority Brands): "Our franchise owners depend on ServiceMinder to communicate with clients while improving their daily service delivery."

CASE STUDY 5: Home Clean Heroes (Cleaning)
- 17 franchise locations, 160+ field users
- 92% of business from recurring clients
- 5+ years on the platform
- Pain: previous system was designed for pest control, not cleaning — created admin obstacles
- Result: streamlined scheduling, automated routine tasks, real-time analytics, reduced admin overhead
- Quote (Brittany Potter, Operations Manager): "It's not just about the software—it's about the partnership."

CASE STUDY 6: Empower Brands (Multi-Brand Home & Commercial Services)
- 7 brands on the platform, 292+ franchisees, 1,300+ total users
- 10+ years using the platform
- Pain: needed standardization with brand-specific flexibility across hundreds of locations
- Result: boosted operational efficiency, accelerated franchisee onboarding, smarter cross-brand scaling
- Quote (Erich Johnston, Franchise Technology Solutions Manager): "Other platforms didn't understand our need for standardized reporting, onboarding, and multi-location visibility. ServiceMinder gets it."
- Quote: "It was literally built by a franchisee, for franchisees."
"""

# ---------------------------------------------------------------------------
# Prompt & analysis
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an elite B2B sales intelligence analyst and copywriter. You research "
    "companies deeply, identify key decision-makers, score prospect relevance, "
    "and build pre-meeting briefs. You also write ultra-short cold outreach "
    "messages (25-50 words) at a 5th-grade reading level. No jargon, no fluff, "
    "no filler words. Every word earns its place. You MUST respond with valid "
    "JSON only — no markdown, no commentary outside the JSON."
)


def build_analyze_prompt(url, page_text, company, attempt=0, leadership_text=""):
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
  "key_contacts": [
    {{
      "name": "Full Name",
      "title": "Their exact title (e.g., Brand President, COO, VP of Operations)",
      "relevance_score": 85,
      "why_relevant": "1 sentence: why this person is a high-priority prospect for the seller"
    }}
  ],
  "pre_meeting_brief": {{
    "company_news": ["Recent news item 1", "Recent news item 2"],
    "hiring_updates": ["Hiring signal 1", "Hiring signal 2"],
    "business_signals": ["Business signal 1 (funding, expansion, M&A, partnerships)"],
    "industry_events": ["Relevant industry event or trend"],
    "conversation_context": "2-3 sentences: What the seller should know going into a first conversation — key themes, timing, and likely priorities based on all available signals",
    "sales_shaping_insights": ["Insight that shapes the sales approach 1", "Insight 2"]
  }},
  "outreach": {{
    "observation": "1 sentence: a specific, personalized detail showing you did research (recent news, role change, funding, hiring, product launch)",
    "problem": "1 sentence: connect that observation to a pain point or opportunity relevant to their role",
    "credibility": "1 sentence: cite a REAL result from the case studies below — use the specific company name, metric, and outcome that is MOST relevant to the prospect's industry or pain point",
    "solution": "1 sentence: quick explanation of the seller's unique approach or value",
    "ctc": "1 open-ended question that starts a dialogue — easy to reply to, NOT asking to book a meeting (e.g., 'Curious if this resonates?', 'Is this on your radar?', 'How are you thinking about this?')"
  }}
}}

KEY CONTACTS RULES:
- ONLY include people who hold one of these FOUR roles (or a very close equivalent):
  1. CEO (Chief Executive Officer)
  2. Brand President / President
  3. COO (Chief Operating Officer)
  4. VP of Operations / SVP Operations / Director of Operations / Head of Operations
- Do NOT include any other roles. Specifically EXCLUDE: VP of Franchise Development, VP of Marketing, VP of Sales, CFO, CTO, HR, Legal, Franchise Development, Business Development, or any non-operations executive role.
- Search ALL provided content — the page text, the leadership research from LinkedIn/web, and any about/team pages — for people matching ONLY the 4 target roles above.
- Only include contacts you can actually find evidence of by name in the provided content. Do not fabricate names.
- If NO contacts matching the 4 target roles are found, return an empty array: "key_contacts": []
- For each contact, assign a relevance_score from 0-100 based on role alignment (CEO=80+, President=85+, COO=90+, VP Ops=95)
- Sort by relevance_score descending (highest first)

PRE-MEETING BRIEF RULES:
- Research deeply: extract every signal from the page content about what this company is doing, planning, or struggling with
- "company_news": recent announcements, press releases, product launches, leadership changes visible on the page
- "hiring_updates": any evidence of hiring, team growth, new roles, or workforce changes
- "business_signals": funding rounds, expansion plans, new markets, partnerships, M&A activity, revenue milestones
- "industry_events": relevant trade shows, conferences, regulatory changes, or market shifts affecting their industry
- "conversation_context": synthesize ALL signals into a concise brief — what should the seller know before walking into a meeting? What's top of mind for this company right now?
- "sales_shaping_insights": the 2-3 insights that should actually shape the sales conversation — not generic observations, but specific angles that connect the prospect's situation to the seller's value
- If no information is available for a field, use an empty array [] or empty string ""

SELLER'S PROVEN RESULTS (use these for the credibility sentence — pick the most relevant one):
{CASE_STUDIES}

STRICT RULES FOR THE OUTREACH (THESE ARE HARD LIMITS):
- The ENTIRE outreach (all 5 parts combined) MUST be 25-50 words total. NOT 50+. Count each word before responding. If over 50, cut words until you're under.
- Each part should be 5-10 words. Aim for 8 words average per part (5 parts x 8 words = 40 words).
- Write at a 5th-grade reading level. Simple words. Short sentences. No jargon.
- No filler: "I hope this finds you well", "I wanted to reach out", "I noticed that"
- No buzzwords: "synergy", "leverage", "optimize", "streamline", "cutting-edge", "empower"
- The CTC must be easy to answer — NOT "Can we schedule a call?" or "Do you have 15 minutes?"
- Be specific. Reference real details from the page.
- The credibility sentence MUST reference a real case study company and metric from the list above. Pick the one closest to the prospect's industry, size, or pain point.
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
{f"""
Leadership Research (crawled from company website, LinkedIn, and web search — use this to find executive contacts):
{leadership_text[:6000]}
""" if leadership_text else ""}
{company_context}"""


def analyze_page(url, page_text, company, attempt=0, leadership_text=""):
    """Call Claude and parse the structured JSON response."""
    prompt = build_analyze_prompt(url, page_text, company, attempt, leadership_text)
    raw = call_claude(SYSTEM_PROMPT, prompt, max_tokens=1500)

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

            # Fetch leadership/about pages to find executive contacts
            leadership_text = fetch_leadership_text(url)

            # Client-side search results (from extension, not blocked by DDG)
            client_search = body.get("leadership_search", "").strip()

            # Server-side search fallback
            from urllib.parse import urlparse
            parsed_domain = urlparse(url)
            domain_name = parsed_domain.netloc.replace("www.", "").split(".")[0]
            company_name = domain_name.capitalize()
            server_search = search_leadership_web(company_name)

            # Combine all leadership intel
            all_leadership_parts = []
            if leadership_text:
                all_leadership_parts.append(leadership_text)
            if client_search:
                all_leadership_parts.append(client_search)
            if server_search and not client_search:
                # Only use server search if client search didn't return anything
                all_leadership_parts.append(server_search)
            all_leadership = "\n\n".join(all_leadership_parts)

            attempt = body.get("attempt", 0)
            analysis = analyze_page(url, page_text, company, attempt, all_leadership)
            send_json(self, 200, {"status": "success", "analysis": analysis, "url": url})

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.readable() else str(e)
            send_json(self, 502, {"message": f"Claude API error ({e.code}): {error_body}"})

        except Exception as e:
            send_json(self, 500, {"message": f"Internal error: {type(e).__name__}: {str(e)}"})

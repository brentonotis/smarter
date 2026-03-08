# Sales Copilot

AI-powered Chrome extension and web app that generates personalized sales outreach snippets. Enter your company info, add target companies/people, and get tailored outreach messages powered by Claude.

## Architecture

- **Frontend** — Static HTML/CSS/JS, hosted on GitHub Pages
- **Serverless API** — Python functions (Vercel), calls Anthropic Claude API
- **Chrome Extension** — Side panel that analyzes any web page for sales insights

## Setup

### Frontend (GitHub Pages)

The static frontend in the repo root (`index.html`, `css/`, `js/`) can be served directly by GitHub Pages. Enable it in your repo settings under Pages → Source → main branch.

### Serverless API (Vercel)

1. Install the [Vercel CLI](https://vercel.com/cli): `npm i -g vercel`
2. Set your environment variables:
   - `ANTHROPIC_API_KEY` — your Anthropic API key
   - `NEWS_API_KEY` — (optional) News API key for company news
3. Deploy: `vercel --prod`
4. Copy the deployment URL and paste it into the app's "API Base URL" field

### Chrome Extension

1. Open `chrome://extensions/` in Chrome
2. Enable "Developer mode"
3. Click "Load unpacked" and select the `extension/` folder
4. Click the extension icon on any page to open the analysis panel
5. Enter your API URL in the extension popup settings

## Project Structure

```
├── index.html          # Main web app (static)
├── css/style.css       # Styles
├── js/app.js           # Frontend logic (localStorage for data)
├── api/                # Serverless functions (deploy to Vercel)
│   ├── generate.py     # POST /api/generate — outreach snippet generation
│   ├── analyze.py      # POST /api/analyze — web page analysis
│   └── requirements.txt
├── extension/          # Chrome extension (Manifest V3)
│   ├── manifest.json
│   ├── content.js      # Side panel injected into pages
│   ├── background.js   # Service worker
│   ├── popup.html/js   # Extension popup (settings)
│   └── styles.css
└── vercel.json         # Vercel deployment config
```

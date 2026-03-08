// --- Sales Copilot Content Script ---

chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    if (request.action === 'togglePanel') {
        const panel = document.getElementById('salescopilot-panel');
        if (panel) {
            panel.remove();
            sendResponse({ success: true, action: 'removed' });
        } else {
            createPanel();
            sendResponse({ success: true, action: 'created' });
        }
        return true;
    }
});

// ---------------------------------------------------------------------------
// Page text extraction (runs client-side, so it sees JS-rendered content)
// ---------------------------------------------------------------------------

function extractPageText(maxChars) {
    maxChars = maxChars || 6000;
    // Grab the main content area or fall back to body
    const root = document.querySelector('main, article, [role="main"]') || document.body;
    // Clone so we can strip without affecting the live page
    const clone = root.cloneNode(true);
    // Remove scripts, styles, nav, footer, hidden elements
    clone.querySelectorAll('script, style, noscript, nav, footer, header, [aria-hidden="true"], [hidden]').forEach(el => el.remove());
    let text = (clone.innerText || clone.textContent || '').trim();
    // Collapse whitespace
    text = text.replace(/\s+/g, ' ');
    return text.substring(0, maxChars);
}

// ---------------------------------------------------------------------------
// Panel creation
// ---------------------------------------------------------------------------

function createPanel() {
    const existing = document.getElementById('salescopilot-panel');
    if (existing) existing.remove();

    const panel = document.createElement('div');
    panel.id = 'salescopilot-panel';

    const header = document.createElement('div');
    header.id = 'salescopilot-header';
    header.innerHTML = '<span>Sales Copilot</span>';

    const close = document.createElement('button');
    close.id = 'salescopilot-close';
    close.innerHTML = '&times;';
    close.onclick = () => panel.remove();
    header.appendChild(close);

    const content = document.createElement('div');
    content.id = 'salescopilot-content';

    panel.appendChild(header);
    panel.appendChild(content);
    document.body.appendChild(panel);

    makeDraggable(panel, header);

    chrome.storage.local.get(['salescopilot_api_url', 'salescopilot_company'], function (data) {
        if (!data.salescopilot_api_url) {
            showConfigUI(content);
        } else {
            showAnalysisUI(content, data.salescopilot_api_url, data.salescopilot_company || {});
        }
    });
}

// ---------------------------------------------------------------------------
// Config UI (first-run)
// ---------------------------------------------------------------------------

function showConfigUI(container) {
    container.innerHTML = `
        <div style="padding: 10px;">
            <p style="margin-bottom: 12px; color: #333; font-size: 14px;">
                Enter your API URL to get started.
            </p>
            <input type="url" id="salescopilot-api-input"
                placeholder="https://your-app.vercel.app"
                style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 10px; font-size: 13px;">
            <button id="salescopilot-save-config"
                style="width: 100%; padding: 8px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">
                Save & Analyze This Page
            </button>
        </div>
    `;

    document.getElementById('salescopilot-save-config').addEventListener('click', function () {
        const url = document.getElementById('salescopilot-api-input').value.trim().replace(/\/+$/, '');
        if (!url) return;
        chrome.storage.local.set({ salescopilot_api_url: url }, function () {
            showAnalysisUI(container, url, {});
        });
    });
}

// ---------------------------------------------------------------------------
// Analysis UI — shows spinner then structured results
// ---------------------------------------------------------------------------

function showAnalysisUI(container, apiUrl, company) {
    const currentUrl = window.location.href;
    container.innerHTML = `
        <div style="padding: 10px;">
            <p style="color: #666; font-size: 11px; margin-bottom: 8px; word-break: break-all;">
                ${escapeHtml(currentUrl.substring(0, 80))}${currentUrl.length > 80 ? '...' : ''}
            </p>
            <div id="salescopilot-result" style="margin-top: 10px;">
                <div style="text-align: center; padding: 20px;">
                    <div class="salescopilot-spinner"></div>
                    <p style="color: #666; margin-top: 10px; font-size: 13px;">Analyzing page...</p>
                </div>
            </div>
            <div style="margin-top: 12px; border-top: 1px solid #eee; padding-top: 8px;">
                <button id="salescopilot-reanalyze"
                    style="width: 100%; padding: 6px; background: #f8f9fa; color: #333; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 12px;">
                    ↻ Re-analyze
                </button>
            </div>
        </div>
    `;

    analyzeCurrentPage(apiUrl, currentUrl, company);

    document.getElementById('salescopilot-reanalyze').addEventListener('click', function () {
        analyzeCurrentPage(apiUrl, currentUrl, company);
    });
}

// ---------------------------------------------------------------------------
// API call — sends client-extracted page text for best results
// ---------------------------------------------------------------------------

async function analyzeCurrentPage(apiUrl, pageUrl, company) {
    const resultDiv = document.getElementById('salescopilot-result');
    if (!resultDiv) return;

    resultDiv.innerHTML = `
        <div style="text-align: center; padding: 20px;">
            <div class="salescopilot-spinner"></div>
            <p style="color: #666; margin-top: 10px; font-size: 13px;">Analyzing page...</p>
        </div>
    `;

    try {
        const pageText = extractPageText(6000);

        const response = await fetch(apiUrl + '/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: pageUrl,
                page_text: pageText,
                company: company
            })
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.message || 'API returned status ' + response.status);
        }

        const data = await response.json();

        if (data.status === 'success' && data.analysis) {
            renderStructuredResults(resultDiv, data.analysis);
        } else {
            throw new Error(data.message || 'Analysis failed');
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div style="color: #dc3545; text-align: center; padding: 10px; font-size: 13px;">
                <p><strong>Error:</strong> ${escapeHtml(error.message)}</p>
                <p style="margin-top: 8px; color: #666;">Check that your API URL is correct and the server is running.</p>
            </div>
        `;
    }
}

// ---------------------------------------------------------------------------
// Render structured analysis results
// ---------------------------------------------------------------------------

function renderStructuredResults(container, analysis) {
    // Handle both structured (JSON) and plain-text (fallback) responses
    if (typeof analysis === 'string') {
        container.innerHTML = `<div class="sc-section"><div class="sc-text">${escapeHtml(analysis)}</div></div>`;
        return;
    }

    let html = '';

    // Overview
    if (analysis.overview) {
        html += `
            <div class="sc-section">
                <div class="sc-label">Overview</div>
                <div class="sc-text">${escapeHtml(analysis.overview)}</div>
            </div>`;
    }

    // Tags
    if (analysis.tags && analysis.tags.length > 0) {
        html += '<div class="sc-tags">';
        analysis.tags.forEach(tag => {
            html += `<span class="sc-tag">${escapeHtml(tag)}</span>`;
        });
        html += '</div>';
    }

    // Insights
    if (analysis.insights && analysis.insights.length > 0) {
        html += `<div class="sc-section"><div class="sc-label">Key Insights</div><ul class="sc-list">`;
        analysis.insights.forEach(item => {
            html += `<li>${escapeHtml(item)}</li>`;
        });
        html += '</ul></div>';
    }

    // Pain Points
    if (analysis.pain_points && analysis.pain_points.length > 0) {
        html += `<div class="sc-section"><div class="sc-label">Pain Points & Opportunities</div><ul class="sc-list">`;
        analysis.pain_points.forEach(item => {
            html += `<li>${escapeHtml(item)}</li>`;
        });
        html += '</ul></div>';
    }

    // Outreach Line (with copy button)
    if (analysis.outreach_line) {
        html += `
            <div class="sc-section sc-outreach">
                <div class="sc-label">Suggested Outreach</div>
                <div class="sc-outreach-text">${escapeHtml(analysis.outreach_line)}</div>
                <button class="sc-copy-btn" id="salescopilot-copy-outreach">Copy</button>
            </div>`;
    }

    container.innerHTML = html;

    // Wire up copy button
    const copyBtn = document.getElementById('salescopilot-copy-outreach');
    if (copyBtn) {
        copyBtn.addEventListener('click', function () {
            navigator.clipboard.writeText(analysis.outreach_line).then(() => {
                copyBtn.textContent = 'Copied!';
                copyBtn.classList.add('sc-copy-success');
                setTimeout(() => {
                    copyBtn.textContent = 'Copy';
                    copyBtn.classList.remove('sc-copy-success');
                }, 2000);
            });
        });
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeDraggable(panel, handle) {
    let x = 0, y = 0, ox = 0, oy = 0, dragging = false;

    handle.addEventListener('mousedown', function (e) {
        if (e.target.id === 'salescopilot-close') return;
        dragging = true;
        ox = e.clientX - x;
        oy = e.clientY - y;
    });

    document.addEventListener('mousemove', function (e) {
        if (!dragging) return;
        e.preventDefault();
        x = e.clientX - ox;
        y = e.clientY - oy;
        panel.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)';
    });

    document.addEventListener('mouseup', function () {
        dragging = false;
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

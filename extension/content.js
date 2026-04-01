// --- Sales Copilot Content Script ---

// Track regeneration attempts so each re-analyze gets a fresh angle
let _scAttempt = 0;

chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    if (request.action === 'togglePanel') {
        const panel = document.getElementById('salescopilot-panel');
        if (panel) {
            panel.remove();
            sendResponse({ success: true, action: 'removed' });
        } else {
            _scAttempt = 0; // reset on new panel open
            createPanel();
            sendResponse({ success: true, action: 'created' });
        }
        return true;
    }
});

// ---------------------------------------------------------------------------
// Page text extraction (runs client-side, sees JS-rendered content)
// ---------------------------------------------------------------------------

function extractPageText(maxChars) {
    maxChars = maxChars || 6000;
    const root = document.querySelector('main, article, [role="main"]') || document.body;
    const clone = root.cloneNode(true);
    clone.querySelectorAll('script, style, noscript, nav, footer, header, [aria-hidden="true"], [hidden]').forEach(el => el.remove());
    let text = (clone.innerText || clone.textContent || '').trim();
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
// Analysis UI
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
                    &#x21bb; New Angle
                </button>
            </div>
        </div>
    `;

    analyzeCurrentPage(apiUrl, currentUrl, company);

    document.getElementById('salescopilot-reanalyze').addEventListener('click', function () {
        _scAttempt++;
        analyzeCurrentPage(apiUrl, currentUrl, company);
    });
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Leadership search — delegates to background script (has host_permissions)
// ---------------------------------------------------------------------------

function searchLeadership(companyName) {
    return new Promise(function (resolve) {
        chrome.runtime.sendMessage(
            { action: 'searchLeadership', companyName: companyName },
            function (response) {
                if (chrome.runtime.lastError || !response) {
                    resolve('');
                } else {
                    resolve(response.result || '');
                }
            }
        );
    });
}

function getCompanyNameFromUrl(url) {
    try {
        var hostname = new URL(url).hostname.replace('www.', '');
        return hostname.split('.')[0].charAt(0).toUpperCase() + hostname.split('.')[0].slice(1);
    } catch (e) {
        return '';
    }
}

// ---------------------------------------------------------------------------
// Progress UI helpers
// ---------------------------------------------------------------------------

var SC_STEPS = [
    'Extracting page content...',
    'Researching contacts on LinkedIn...',
    'Scanning leadership pages...',
    'Finding key insights...',
    'Building pre-meeting brief...',
    'Developing point of view...',
];

function renderProgressUI(container) {
    var stepsHtml = '';
    for (var i = 0; i < SC_STEPS.length; i++) {
        stepsHtml += '<div class="sc-step" id="sc-step-' + i + '">' +
            '<span class="sc-step-icon"></span>' +
            '<span class="sc-step-text">' + SC_STEPS[i].replace('...', '') + '</span>' +
            '</div>';
    }
    container.innerHTML =
        '<div class="sc-progress-container">' +
            '<div class="sc-status-text" id="sc-status-text">' + SC_STEPS[0] + '</div>' +
            '<div class="sc-progress-bar-track">' +
                '<div class="sc-progress-bar-fill" id="sc-progress-fill"></div>' +
            '</div>' +
            '<div class="sc-progress-steps">' + stepsHtml + '</div>' +
        '</div>';
}

function setProgress(stepIndex) {
    var total = SC_STEPS.length;

    // Update shimmer status text
    var statusText = document.getElementById('sc-status-text');
    if (statusText) statusText.textContent = SC_STEPS[stepIndex] || '';

    // Mark previous steps as done
    for (var i = 0; i < stepIndex; i++) {
        var prev = document.getElementById('sc-step-' + i);
        if (prev) {
            prev.querySelector('.sc-step-icon').className = 'sc-step-icon sc-step-done';
            prev.querySelector('.sc-step-icon').textContent = '✓';
            var txt = prev.querySelector('.sc-step-text');
            txt.className = 'sc-step-text sc-step-text-done';
        }
    }

    // Mark current step as active
    var current = document.getElementById('sc-step-' + stepIndex);
    if (current) {
        current.querySelector('.sc-step-icon').className = 'sc-step-icon sc-step-active';
        current.querySelector('.sc-step-text').className = 'sc-step-text sc-step-text-active';
    }

    // Update progress bar
    var fill = document.getElementById('sc-progress-fill');
    if (fill) {
        var pct = Math.round(((stepIndex + 0.5) / total) * 100);
        fill.style.width = Math.min(pct, 95) + '%';
    }
}

function completeAllProgress() {
    var total = SC_STEPS.length;
    for (var i = 0; i < total; i++) {
        var step = document.getElementById('sc-step-' + i);
        if (step) {
            step.querySelector('.sc-step-icon').className = 'sc-step-icon sc-step-done';
            step.querySelector('.sc-step-icon').textContent = '✓';
            step.querySelector('.sc-step-text').className = 'sc-step-text sc-step-text-done';
        }
    }
    var fill = document.getElementById('sc-progress-fill');
    if (fill) fill.style.width = '100%';
    var statusText = document.getElementById('sc-status-text');
    if (statusText) statusText.textContent = 'Done!';
}

// Smoothly ticks progress through steps 2-4 while waiting for the API
var _progressTimer = null;
function startProgressTicker(startStep, endStep, durationMs) {
    var stepsToFill = endStep - startStep;
    var interval = durationMs / stepsToFill;
    var currentStep = startStep;
    _progressTimer = setInterval(function () {
        if (currentStep <= endStep) {
            setProgress(currentStep);
            currentStep++;
        } else {
            clearInterval(_progressTimer);
            _progressTimer = null;
        }
    }, interval);
}

function stopProgressTicker() {
    if (_progressTimer) {
        clearInterval(_progressTimer);
        _progressTimer = null;
    }
}

async function analyzeCurrentPage(apiUrl, pageUrl, company) {
    const resultDiv = document.getElementById('salescopilot-result');
    if (!resultDiv) return;

    renderProgressUI(resultDiv);

    try {
        // Step 0: Extract page content
        setProgress(0);
        const pageText = extractPageText(6000);
        await _sleep(500);

        // Step 1: Research contacts on LinkedIn (real async work)
        setProgress(1);
        var companyName = getCompanyNameFromUrl(pageUrl);
        var leadershipSearch = '';
        try {
            leadershipSearch = await searchLeadership(companyName);
        } catch (e) {
            // non-fatal
        }

        // Step 2: Start API call — tick through steps 2-4 during the wait
        setProgress(2);
        startProgressTicker(2, 4, 12000); // tick through steps over ~12s

        const response = await fetch(apiUrl + '/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: pageUrl,
                page_text: pageText,
                company: company,
                attempt: _scAttempt,
                leadership_search: leadershipSearch
            })
        });

        stopProgressTicker();

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.message || 'API returned status ' + response.status);
        }

        // Step 5: Developing point of view (parsing response)
        setProgress(5);
        const data = await response.json();
        await _sleep(600);

        // All done
        completeAllProgress();
        await _sleep(400);

        if (data.status === 'success' && data.analysis) {
            renderStructuredResults(resultDiv, data.analysis);
        } else {
            throw new Error(data.message || 'Analysis failed');
        }
    } catch (error) {
        stopProgressTicker();
        resultDiv.innerHTML = `
            <div style="color: #dc3545; text-align: center; padding: 10px; font-size: 13px;">
                <p><strong>Error:</strong> ${escapeHtml(error.message)}</p>
                <p style="margin-top: 8px; color: #666;">Check your API URL and that the server is running.</p>
            </div>
        `;
    }
}

function _sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

// ---------------------------------------------------------------------------
// Render structured results with 5-part outreach
// ---------------------------------------------------------------------------

function renderStructuredResults(container, analysis) {
    if (typeof analysis === 'string') {
        container.innerHTML = '<div class="sc-section"><div class="sc-text">' + escapeHtml(analysis) + '</div></div>';
        return;
    }

    let html = '';

    // Overview
    if (analysis.overview) {
        html += '<div class="sc-section">' +
            '<div class="sc-label">Overview</div>' +
            '<div class="sc-text">' + escapeHtml(analysis.overview) + '</div>' +
            '</div>';
    }

    // Tags
    if (analysis.tags && analysis.tags.length > 0) {
        html += '<div class="sc-tags">';
        analysis.tags.forEach(function (tag) {
            html += '<span class="sc-tag">' + escapeHtml(tag) + '</span>';
        });
        html += '</div>';
    }

    // Insights
    if (analysis.insights && analysis.insights.length > 0) {
        html += '<div class="sc-section"><div class="sc-label">Key Insights</div><ul class="sc-list">';
        analysis.insights.forEach(function (item) {
            html += '<li>' + escapeHtml(item) + '</li>';
        });
        html += '</ul></div>';
    }

    // Key Contacts with Relevance Scores
    if (analysis.key_contacts && analysis.key_contacts.length > 0) {
        html += '<div class="sc-section"><div class="sc-label">Key Contacts</div>';
        analysis.key_contacts.forEach(function (contact) {
            var score = contact.relevance_score || 0;
            var scoreClass = score >= 75 ? 'sc-score-high' : score >= 50 ? 'sc-score-med' : 'sc-score-low';
            html += '<div class="sc-contact-card">';
            html += '<div class="sc-contact-header">';
            html += '<div class="sc-contact-name">' + escapeHtml(contact.name) + '</div>';
            html += '<span class="sc-relevance-score ' + scoreClass + '">' + score + '</span>';
            html += '</div>';
            html += '<div class="sc-contact-title">' + escapeHtml(contact.title) + '</div>';
            if (contact.why_relevant) {
                html += '<div class="sc-contact-why">' + escapeHtml(contact.why_relevant) + '</div>';
            }
            html += '</div>';
        });
        html += '</div>';
    }

    // Pre-Meeting Brief
    var brief = analysis.pre_meeting_brief || {};
    var hasBrief = brief.company_news || brief.hiring_updates || brief.business_signals ||
                   brief.industry_events || brief.conversation_context || brief.sales_shaping_insights;
    if (hasBrief) {
        html += '<div class="sc-section sc-brief-card"><div class="sc-label">Pre-Meeting Brief</div>';

        var briefSections = [
            { key: 'company_news', label: 'Company News', icon: '📰' },
            { key: 'hiring_updates', label: 'Hiring Updates', icon: '👥' },
            { key: 'business_signals', label: 'Business Signals', icon: '📊' },
            { key: 'industry_events', label: 'Industry Events', icon: '🏛' },
        ];

        briefSections.forEach(function (sec) {
            var items = brief[sec.key];
            if (items && items.length > 0) {
                html += '<div class="sc-brief-section">';
                html += '<div class="sc-brief-label">' + sec.icon + ' ' + sec.label + '</div>';
                html += '<ul class="sc-list">';
                items.forEach(function (item) {
                    html += '<li>' + escapeHtml(item) + '</li>';
                });
                html += '</ul></div>';
            }
        });

        if (brief.conversation_context) {
            html += '<div class="sc-brief-section">';
            html += '<div class="sc-brief-label">💬 Conversation Context</div>';
            html += '<div class="sc-brief-text">' + escapeHtml(brief.conversation_context) + '</div>';
            html += '</div>';
        }

        if (brief.sales_shaping_insights && brief.sales_shaping_insights.length > 0) {
            html += '<div class="sc-brief-section">';
            html += '<div class="sc-brief-label">🎯 Sales-Shaping Insights</div>';
            html += '<ul class="sc-list sc-list-highlight">';
            brief.sales_shaping_insights.forEach(function (item) {
                html += '<li>' + escapeHtml(item) + '</li>';
            });
            html += '</ul></div>';
        }

        html += '</div>';
    }

    // 5-Part Outreach Message
    var outreach = analysis.outreach || {};
    var hasOutreach = outreach.observation || outreach.problem || outreach.credibility || outreach.solution || outreach.ctc;

    if (hasOutreach) {
        // Build the full message for copy
        var parts = [];
        if (outreach.observation) parts.push(outreach.observation);
        if (outreach.problem) parts.push(outreach.problem);
        if (outreach.credibility) parts.push(outreach.credibility);
        if (outreach.solution) parts.push(outreach.solution);
        if (outreach.ctc) parts.push(outreach.ctc);
        var fullMessage = parts.join(' ');

        // Count words
        var wordCount = fullMessage.split(/\s+/).filter(function (w) { return w.length > 0; }).length;

        html += '<div class="sc-section sc-outreach-card">';
        html += '<div class="sc-outreach-header">';
        html += '<div class="sc-label">Outreach Message</div>';
        html += '<span class="sc-word-count">' + wordCount + ' words</span>';
        html += '</div>';

        // Render as one clean continuous paragraph
        html += '<div class="sc-outreach-text">' + escapeHtml(fullMessage) + '</div>';

        html += '<button class="sc-copy-btn" id="salescopilot-copy-outreach">Copy</button>';
        html += '</div>';
    }

    // Legacy fallback: outreach_line (old format)
    if (!hasOutreach && analysis.outreach_line) {
        html += '<div class="sc-section sc-outreach-card">';
        html += '<div class="sc-label">Outreach Message</div>';
        html += '<div class="sc-text">' + escapeHtml(analysis.outreach_line) + '</div>';
        html += '<button class="sc-copy-btn" id="salescopilot-copy-outreach">Copy</button>';
        html += '</div>';
    }

    container.innerHTML = html;

    // Wire up copy button
    var copyBtn = document.getElementById('salescopilot-copy-outreach');
    if (copyBtn && hasOutreach) {
        copyBtn.addEventListener('click', function () {
            var parts = [];
            if (outreach.observation) parts.push(outreach.observation);
            if (outreach.problem) parts.push(outreach.problem);
            if (outreach.credibility) parts.push(outreach.credibility);
            if (outreach.solution) parts.push(outreach.solution);
            if (outreach.ctc) parts.push(outreach.ctc);
            navigator.clipboard.writeText(parts.join(' ')).then(function () {
                copyBtn.textContent = 'Copied!';
                copyBtn.classList.add('sc-copy-success');
                setTimeout(function () {
                    copyBtn.textContent = 'Copy Full Message';
                    copyBtn.classList.remove('sc-copy-success');
                }, 2000);
            });
        });
    } else if (copyBtn && analysis.outreach_line) {
        copyBtn.addEventListener('click', function () {
            navigator.clipboard.writeText(analysis.outreach_line).then(function () {
                copyBtn.textContent = 'Copied!';
                copyBtn.classList.add('sc-copy-success');
                setTimeout(function () {
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

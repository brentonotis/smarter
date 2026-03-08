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

function createPanel() {
    // Remove existing panel
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

    // Make panel draggable
    makeDraggable(panel, header);

    // Load settings and show appropriate UI
    chrome.storage.local.get(['salescopilot_api_url', 'salescopilot_company'], function (data) {
        if (!data.salescopilot_api_url) {
            showConfigUI(content);
        } else {
            showAnalysisUI(content, data.salescopilot_api_url, data.salescopilot_company || {});
        }
    });
}

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

function showAnalysisUI(container, apiUrl, company) {
    const currentUrl = window.location.href;
    container.innerHTML = `
        <div style="padding: 10px;">
            <p style="color: #666; font-size: 12px; margin-bottom: 8px; word-break: break-all;">
                Analyzing: ${currentUrl.substring(0, 80)}${currentUrl.length > 80 ? '...' : ''}
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
                    Re-analyze
                </button>
            </div>
        </div>
    `;

    analyzeCurrentPage(apiUrl, currentUrl, company);

    document.getElementById('salescopilot-reanalyze').addEventListener('click', function () {
        analyzeCurrentPage(apiUrl, currentUrl, company);
    });
}

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
        const response = await fetch(apiUrl + '/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: pageUrl, company: company })
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.message || 'API returned status ' + response.status);
        }

        const data = await response.json();

        if (data.status === 'success') {
            resultDiv.innerHTML = `
                <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; color: #333;">
                    ${escapeHtml(data.analysis)}
                </div>
            `;
        } else {
            throw new Error(data.message || 'Analysis failed');
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div style="color: #dc3545; text-align: center; padding: 10px; font-size: 13px;">
                <p>Error: ${escapeHtml(error.message)}</p>
                <p style="margin-top: 8px; color: #666;">Check that your API URL is correct and the server is running.</p>
            </div>
        `;
    }
}

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

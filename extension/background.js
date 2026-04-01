// Handle extension icon click — toggle the side panel
chrome.action.onClicked.addListener(async (tab) => {
    try {
        chrome.tabs.sendMessage(tab.id, { action: 'togglePanel' }, (response) => {
            if (chrome.runtime.lastError) {
                console.error('Error sending message:', chrome.runtime.lastError.message);
            }
        });
    } catch (error) {
        console.error('Error handling extension click:', error);
    }
});

// ---------------------------------------------------------------------------
// Leadership search — runs in background script (has host_permissions)
// ---------------------------------------------------------------------------

async function searchDDG(query) {
    try {
        const encoded = encodeURIComponent(query);
        const url = 'https://html.duckduckgo.com/html/?q=' + encoded;
        const resp = await fetch(url);
        const html = await resp.text();

        const matches = [...html.matchAll(/class="result__(?:title|snippet)"[^>]*>([\s\S]*?)<\/(?:a|td)>/g)];
        return matches.slice(0, 10).map(m => {
            return m[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
        }).filter(t => t.length > 10);
    } catch (e) {
        return [];
    }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'searchLeadership') {
        const name = request.companyName;
        Promise.all([
            // Search each target persona individually for better coverage
            searchDDG(name + ' CEO site:linkedin.com'),
            searchDDG(name + ' president site:linkedin.com'),
            searchDDG(name + ' COO "chief operating officer" site:linkedin.com'),
            searchDDG(name + ' "VP of operations" OR "vice president operations" site:linkedin.com'),
            // Broader searches
            searchDDG(name + ' CEO OR president OR COO OR "VP operations"'),
            searchDDG(name + ' leadership team management executive'),
            searchDDG(name + ' org chart OR "management team"'),
            searchDDG('site:linkedin.com/in ' + name + ' CEO OR president OR COO OR operations'),
        ]).then(results => {
            const labels = [
                'LinkedIn CEO', 'LinkedIn President', 'LinkedIn COO', 'LinkedIn VP Ops',
                'Executive Titles', 'Leadership Team', 'Org Chart', 'LinkedIn Profiles'
            ];
            const parts = [];
            results.forEach((r, i) => {
                if (r.length) parts.push('[' + labels[i] + ']\n' + r.join(' | '));
            });
            sendResponse({ result: parts.join('\n\n') });
        }).catch(() => {
            sendResponse({ result: '' });
        });
        return true; // keep message channel open for async response
    }
});

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
        // Also try with quotes for exact match
        const qname = '"' + name + '"';
        Promise.all([
            // LinkedIn per-persona searches
            searchDDG(qname + ' CEO OR president site:linkedin.com'),
            searchDDG(qname + ' COO OR "chief operating officer" site:linkedin.com'),
            searchDDG(qname + ' "VP operations" OR "vice president operations" OR "director of operations" site:linkedin.com'),
            searchDDG('site:linkedin.com/in ' + qname + ' CEO OR president OR COO OR operations OR founder'),
            // General web — founder/owner catches smaller companies
            searchDDG(qname + ' CEO OR president OR COO OR "VP operations" OR founder OR owner'),
            searchDDG(qname + ' leadership team OR "management team" OR executives'),
            // Press releases and business databases (great for smaller companies)
            searchDDG(qname + ' founder OR CEO site:crunchbase.com OR site:bloomberg.com OR site:marketwatch.com'),
            searchDDG(qname + ' "founded by" OR "led by" OR "headed by"'),
        ]).then(results => {
            const labels = [
                'LinkedIn CEO/President', 'LinkedIn COO', 'LinkedIn VP Ops',
                'LinkedIn Profiles', 'Web Executives', 'Leadership Team',
                'Business Databases', 'Press Mentions'
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

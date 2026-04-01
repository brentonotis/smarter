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
            searchDDG(name + ' CEO OR president OR COO OR "VP of operations" site:linkedin.com'),
            searchDDG(name + ' "chief executive officer" OR "brand president" OR "chief operating officer" OR "VP operations"'),
            searchDDG(name + ' leadership team management executive'),
            searchDDG(name + ' org chart OR "management team" OR executives'),
            searchDDG('site:linkedin.com/in ' + name + ' CEO OR president OR COO OR operations'),
        ]).then(([linkedin, titles, team, org, linkedinProfiles]) => {
            const parts = [];
            if (linkedin.length) parts.push('[LinkedIn Search]\n' + linkedin.join(' | '));
            if (titles.length) parts.push('[Executive Title Search]\n' + titles.join(' | '));
            if (team.length) parts.push('[Leadership Team Search]\n' + team.join(' | '));
            if (org.length) parts.push('[Org Chart Search]\n' + org.join(' | '));
            if (linkedinProfiles.length) parts.push('[LinkedIn Profiles]\n' + linkedinProfiles.join(' | '));
            sendResponse({ result: parts.join('\n\n') });
        }).catch(() => {
            sendResponse({ result: '' });
        });
        return true; // keep message channel open for async response
    }
});

// Listen for installation
chrome.runtime.onInstalled.addListener(function() {
    console.log("=== Extension Installed ===");
    // Initialize any extension data
    chrome.storage.local.get(['smarter_session'], function(result) {
        console.log("Initial session state:", result.smarter_session);
        if (!result.smarter_session) {
            chrome.storage.local.set({
                'smarter_session': null
            }, function() {
                console.log('Initialized empty session');
            });
        }
    });
});

// Listen for tab updates to inject content script only if not already injected
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url && !tab.url.startsWith('chrome://')) {
        console.log("=== Checking content script injection for tab:", tabId);
        chrome.scripting.executeScript({
            target: { tabId: tabId },
            function: () => {
                return !!document.getElementById('smarter-panel');
            }
        }).then((results) => {
            if (!results[0].result) {
                console.log("Injecting content script for tab:", tabId);
                chrome.scripting.executeScript({
                    target: { tabId: tabId },
                    files: ['content.js']
                }).catch(error => {
                    console.error('Error injecting content script:', error);
                });
            }
        }).catch(error => {
            console.error('Error checking content script:', error);
        });
    }
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    console.log("=== Background Script Message Received ===");
    console.log("Request:", request);
    console.log("Sender:", sender);
    
    if (request.action === 'checkSession') {
        chrome.storage.local.get(['smarter_session'], function(result) {
            console.log("Current session state:", result.smarter_session);
            sendResponse(result.smarter_session);
        });
        return true; // Will respond asynchronously
    }
});

// Add cookie change listener
chrome.cookies.onChanged.addListener(function(changeInfo) {
    console.log("=== Cookie Changed ===");
    console.log("Cookie change:", changeInfo);
    if (changeInfo.cookie.domain.includes('smarter-865bc5a924ea.herokuapp.com')) {
        console.log("Smarter cookie changed:", changeInfo.cookie);
    }
});

// Handle extension icon click
chrome.action.onClicked.addListener(async (tab) => {
    try {
        // Send message to content script to toggle panel
        chrome.tabs.sendMessage(tab.id, { action: 'togglePanel' }, (response) => {
            if (chrome.runtime.lastError) {
                console.error('Error sending message:', chrome.runtime.lastError);
            }
        });
    } catch (error) {
        console.error('Error handling extension click:', error);
    }
}); 
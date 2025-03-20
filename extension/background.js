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
        console.log("Extension icon clicked for tab:", tab.id);
        // Send message to content script to toggle panel
        chrome.tabs.sendMessage(tab.id, { action: 'togglePanel' }, (response) => {
            if (chrome.runtime.lastError) {
                console.error('Error sending message:', chrome.runtime.lastError);
            } else if (response) {
                console.log('Panel toggle response:', response);
            }
        });
    } catch (error) {
        console.error('Error handling extension click:', error);
    }
}); 
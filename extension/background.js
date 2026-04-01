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


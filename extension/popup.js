document.addEventListener('DOMContentLoaded', function() {
    const toggleButton = document.getElementById('togglePanel');
    const statusDiv = document.getElementById('status');

    // Check if user is logged in
    chrome.storage.local.get(['smarter_session'], function(result) {
        if (result.smarter_session && result.smarter_session.user) {
            statusDiv.textContent = `Logged in as ${result.smarter_session.user.email}`;
        } else {
            statusDiv.textContent = 'Not logged in';
        }
    });

    toggleButton.addEventListener('click', function() {
        console.log("Toggle button clicked");
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
            if (tabs[0]) {
                console.log("Sending toggle message to tab:", tabs[0].id);
                chrome.tabs.sendMessage(tabs[0].id, {action: 'togglePanel'}, function(response) {
                    if (chrome.runtime.lastError) {
                        console.error('Error:', chrome.runtime.lastError);
                        statusDiv.textContent = 'Error: Could not toggle panel';
                    } else if (response && response.success) {
                        statusDiv.textContent = 'Panel toggled successfully';
                    } else {
                        statusDiv.textContent = 'Panel toggle failed';
                    }
                });
            } else {
                console.error('No active tab found');
                statusDiv.textContent = 'Error: No active tab found';
            }
        });
    });
}); 
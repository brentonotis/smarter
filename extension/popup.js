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
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
            chrome.tabs.sendMessage(tabs[0].id, {action: 'togglePanel'});
        });
    });
}); 
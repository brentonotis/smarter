document.addEventListener('DOMContentLoaded', function () {
    const apiUrlInput = document.getElementById('apiUrl');
    const saveBtn = document.getElementById('saveBtn');
    const toggleBtn = document.getElementById('toggleBtn');
    const statusDiv = document.getElementById('status');

    // Load saved settings
    chrome.storage.local.get(['salescopilot_api_url'], function (data) {
        if (data.salescopilot_api_url) {
            apiUrlInput.value = data.salescopilot_api_url;
            statusDiv.textContent = 'API configured';
            statusDiv.className = 'saved';
        } else {
            statusDiv.textContent = 'Not configured';
        }
    });

    // Save settings
    saveBtn.addEventListener('click', function () {
        const url = apiUrlInput.value.trim().replace(/\/+$/, '');
        if (!url) {
            statusDiv.textContent = 'Please enter a valid URL';
            statusDiv.className = '';
            return;
        }
        chrome.storage.local.set({ salescopilot_api_url: url }, function () {
            statusDiv.textContent = 'Settings saved!';
            statusDiv.className = 'saved';
        });
    });

    // Toggle panel on current page
    toggleBtn.addEventListener('click', function () {
        chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { action: 'togglePanel' }, function (response) {
                    if (chrome.runtime.lastError) {
                        statusDiv.textContent = 'Error: ' + chrome.runtime.lastError.message;
                        statusDiv.className = '';
                    } else {
                        statusDiv.textContent = 'Panel toggled';
                        statusDiv.className = 'saved';
                    }
                });
            }
        });
    });
});

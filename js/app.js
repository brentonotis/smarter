document.addEventListener('DOMContentLoaded', function () {
    // --- DOM Elements ---
    const apiUrlInput = document.getElementById('apiUrl');
    const saveConfigBtn = document.getElementById('saveConfig');
    const configCard = document.getElementById('configCard');
    const companyName = document.getElementById('companyName');
    const companyDescription = document.getElementById('companyDescription');
    const targetIndustries = document.getElementById('targetIndustries');
    const saveCompanyBtn = document.getElementById('saveCompany');
    const companySaveStatus = document.getElementById('companySaveStatus');
    const targetName = document.getElementById('targetName');
    const targetList = document.getElementById('targetList');
    const addTargetBtn = document.getElementById('addTarget');
    const generateBtn = document.getElementById('generateBtn');
    const generateStatus = document.getElementById('generateStatus');
    const resultsCard = document.getElementById('resultsCard');
    const resultsContainer = document.getElementById('resultsContainer');
    const navStatus = document.getElementById('navStatus');

    let targets = [];

    // --- LocalStorage Helpers ---
    function loadConfig() {
        return localStorage.getItem('salescopilot_api_url') || '';
    }

    function saveConfigToStorage(url) {
        localStorage.setItem('salescopilot_api_url', url);
    }

    function loadCompany() {
        const data = localStorage.getItem('salescopilot_company');
        return data ? JSON.parse(data) : null;
    }

    function saveCompanyToStorage(data) {
        localStorage.setItem('salescopilot_company', JSON.stringify(data));
    }

    // --- Initialize UI from stored data ---
    function init() {
        // Load API config
        const savedUrl = loadConfig();
        if (savedUrl) {
            apiUrlInput.value = savedUrl;
            configCard.classList.add('config-saved');
        }

        // Load company info
        const company = loadCompany();
        if (company) {
            companyName.value = company.name || '';
            companyDescription.value = company.description || '';
            targetIndustries.value = company.target_industries || '';
        }

        updateGenerateButton();
        updateNavStatus();
    }

    function updateNavStatus() {
        const url = loadConfig();
        if (url) {
            navStatus.textContent = 'API Connected';
            navStatus.className = 'navbar-text text-light';
        } else {
            navStatus.textContent = 'API Not Configured';
            navStatus.className = 'navbar-text text-warning';
        }
    }

    function updateGenerateButton() {
        const hasTargets = targets.length > 0;
        const hasCompany = companyName.value.trim() && companyDescription.value.trim();
        const hasApi = !!loadConfig();
        generateBtn.disabled = !(hasTargets && hasCompany && hasApi);
    }

    // --- API Configuration ---
    saveConfigBtn.addEventListener('click', function () {
        const url = apiUrlInput.value.trim().replace(/\/+$/, ''); // strip trailing slashes
        if (!url) {
            alert('Please enter a valid API URL.');
            return;
        }
        saveConfigToStorage(url);
        configCard.classList.add('config-saved');
        updateNavStatus();
        updateGenerateButton();
    });

    // --- Company Info ---
    saveCompanyBtn.addEventListener('click', function () {
        const data = {
            name: companyName.value.trim(),
            description: companyDescription.value.trim(),
            target_industries: targetIndustries.value.trim()
        };

        if (!data.name || !data.description) {
            alert('Please enter both company name and description.');
            return;
        }

        saveCompanyToStorage(data);
        companySaveStatus.style.display = 'inline';
        setTimeout(() => { companySaveStatus.style.display = 'none'; }, 2000);
        updateGenerateButton();
    });

    // --- Target Management ---
    function renderTargets() {
        if (targets.length === 0) {
            targetList.innerHTML = '<div class="text-muted">No targets added yet</div>';
        } else {
            targetList.innerHTML = '';
            targets.forEach(function (target, index) {
                const item = document.createElement('div');
                item.className = 'target-item d-flex justify-content-between align-items-center';
                item.innerHTML =
                    '<div><strong>' + escapeHtml(target.name) + '</strong> ' +
                    '<span class="badge bg-secondary ms-2">' + escapeHtml(target.type) + '</span></div>' +
                    '<button class="btn btn-sm btn-outline-danger remove-target" data-index="' + index + '">Remove</button>';
                targetList.appendChild(item);
            });

            targetList.querySelectorAll('.remove-target').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    targets.splice(parseInt(this.dataset.index), 1);
                    renderTargets();
                    updateGenerateButton();
                });
            });
        }
    }

    addTargetBtn.addEventListener('click', function () {
        const name = targetName.value.trim();
        if (!name) return;

        const type = document.querySelector('input[name="targetType"]:checked').value;
        targets.push({ name: name, type: type });
        targetName.value = '';
        renderTargets();
        updateGenerateButton();
    });

    // Allow Enter key to add target
    targetName.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTargetBtn.click();
        }
    });

    // --- Generate Snippets ---
    generateBtn.addEventListener('click', async function () {
        const apiUrl = loadConfig();
        const company = loadCompany();

        if (!apiUrl || !company || targets.length === 0) {
            alert('Please configure your API URL, company info, and add at least one target.');
            return;
        }

        generateBtn.disabled = true;
        generateBtn.classList.add('loading');
        generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generating...';
        generateStatus.style.display = 'inline';
        generateStatus.textContent = 'This may take a moment...';
        resultsCard.style.display = 'none';
        resultsContainer.innerHTML = '';

        try {
            const response = await fetch(apiUrl + '/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    targets: targets,
                    company: company
                })
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.message || 'API returned status ' + response.status);
            }

            const data = await response.json();

            if (!data.results || data.results.length === 0) {
                resultsContainer.innerHTML = '<div class="alert alert-warning">No results generated.</div>';
            } else {
                data.results.forEach(function (result) {
                    const card = document.createElement('div');
                    card.className = 'result-card';
                    card.innerHTML =
                        '<div class="d-flex justify-content-between align-items-start mb-2">' +
                        '<div><strong>' + escapeHtml(result.name) + '</strong> ' +
                        '<span class="badge bg-secondary">' + escapeHtml(result.type) + '</span></div>' +
                        '<button class="btn btn-sm btn-outline-primary btn-copy">Copy</button>' +
                        '</div>' +
                        '<div class="snippet-text">' + escapeHtml(result.snippet) + '</div>';
                    resultsContainer.appendChild(card);

                    card.querySelector('.btn-copy').addEventListener('click', function () {
                        navigator.clipboard.writeText(result.snippet).then(() => {
                            this.textContent = 'Copied!';
                            setTimeout(() => { this.textContent = 'Copy'; }, 2000);
                        });
                    });
                });
            }

            resultsCard.style.display = 'block';
        } catch (error) {
            resultsCard.style.display = 'block';
            resultsContainer.innerHTML = '<div class="alert alert-danger">Error: ' + escapeHtml(error.message) + '</div>';
        } finally {
            generateBtn.disabled = false;
            generateBtn.classList.remove('loading');
            generateBtn.innerHTML = 'Generate Snippets';
            generateStatus.style.display = 'none';
            updateGenerateButton();
        }
    });

    // --- Utility ---
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // --- Boot ---
    init();
    renderTargets();
});

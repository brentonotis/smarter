// Initialize the extension when the content script loads
console.log("=== Smarter Extension Content Script Loaded ===");

// Set up message listener at the beginning
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    console.log("Content script received message:", request);
    if (request.action === 'togglePanel') {
        console.log("Toggling panel");
        const panel = document.getElementById('smarter-panel');
        if (panel) {
            console.log("Removing existing panel");
            panel.remove();
            sendResponse({ success: true, action: 'removed' });
        } else {
            console.log("Creating new panel");
            try {
                const newPanel = createPanel();
                if (newPanel) {
                    console.log("Panel created successfully");
                    sendResponse({ success: true, action: 'created' });
                } else {
                    console.error("Failed to create panel");
                    sendResponse({ success: false, error: 'Failed to create panel' });
                }
            } catch (error) {
                console.error("Error creating panel:", error);
                sendResponse({ success: false, error: error.message });
            }
        }
        return true; // Keep the message channel open for async response
    }
});

// Function to create and manage the panel
function createPanel() {
    console.log("Creating panel");
    try {
  const panel = document.createElement('div');
  panel.id = 'smarter-panel';
  panel.style.cssText = `
    position: fixed !important;
    top: 20px !important;
    right: 20px !important;
    width: 400px !important;
    height: 600px !important;
    background: white !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1) !important;
    z-index: 999999 !important;
    display: flex !important;
    flex-direction: column !important;
    transform: translate3d(0,0,0) !important;
    will-change: transform !important;
    contain: layout size !important;
    isolation: isolate !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
    pointer-events: auto !important;
  `;

  const header = document.createElement('div');
  header.id = 'smarter-panel-header';
  header.style.cssText = `
    padding: 10px !important;
    background: #f8f9fa !important;
    border-bottom: 1px solid #dee2e6 !important;
    border-radius: 8px 8px 0 0 !important;
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    cursor: move !important;
    position: relative !important;
    z-index: 1 !important;
  `;

  const title = document.createElement('div');
  title.id = 'smarter-panel-title';
  title.style.cssText = 'font-weight: bold; color: #333;';
  title.textContent = 'Smarter';
  header.appendChild(title);

  const close = document.createElement('button');
  close.id = 'smarter-panel-close';
  close.style.cssText = `
    background: none !important;
    border: none !important;
    font-size: 20px !important;
    cursor: pointer !important;
    color: #666 !important;
    padding: 0 5px !important;
  `;
  close.innerHTML = '×';
        close.onclick = () => {
            console.log("Closing panel");
            panel.remove();
        };
  header.appendChild(close);

  const content = document.createElement('div');
  content.id = 'smarter-panel-content';
  content.style.cssText = `
    flex: 1 !important;
    border-radius: 0 0 8px 8px !important;
    overflow: auto !important;
    padding: 20px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: flex-start !important;
    position: relative !important;
    isolation: isolate !important;
    contain: content !important;
    background: white !important;
    pointer-events: auto !important;
  `;
  
  const loginButton = document.createElement('button');
  loginButton.style.cssText = `
    padding: 10px 20px !important;
    background: #007bff !important;
    color: white !important;
    border: none !important;
    border-radius: 5px !important;
    cursor: pointer !important;
    font-size: 16px !important;
  `;
  loginButton.textContent = 'Login to Smarter';
  loginButton.onclick = async () => {
    try {
      const data = await loadLoginForm();
                content.innerHTML = data;
        } catch (error) {
                console.error('Error loading login form:', error);
      content.innerHTML = `
        <div style="text-align: center; color: red;">
          <p>Error loading login form: ${error.message}</p>
          <p>Please try again or contact support if the issue persists.</p>
        </div>
      `;
    }
  };
  
  content.appendChild(loginButton);

  const resize = document.createElement('div');
  resize.id = 'smarter-panel-resize';
  resize.style.cssText = `
    position: absolute;
    bottom: 0;
    right: 0;
    width: 20px;
    height: 20px;
    cursor: se-resize;
    background: linear-gradient(135deg, transparent 50%, #ddd 50%);
  `;

  panel.appendChild(header);
  panel.appendChild(content);
  panel.appendChild(resize);
  document.body.appendChild(panel);

        // Add drag functionality
  let x = 0;
  let y = 0;
  let ox = 0;
  let oy = 0;
  let dr = false;
  let rs = false;
  let sw = 0;
  let sh = 0;

  header.addEventListener('mousedown', (e) => {
    if (e.target === header || e.target === title) {
      dr = true;
      ox = e.clientX - x;
      oy = e.clientY - y;
    }
  });

  document.addEventListener('mousemove', (e) => {
    if (dr) {
      e.preventDefault();
      x = e.clientX - ox;
      y = e.clientY - oy;
      panel.style.transform = `translate3d(${x}px,${y}px,0)`;
    }
    if (rs) {
      const w = sw + (e.clientX - sw);
      const h = sh + (e.clientY - sh);
      if (w > 300 && h > 200) {
        panel.style.width = w + 'px';
        panel.style.height = h + 'px';
      }
    }
  });

  document.addEventListener('mouseup', () => {
    dr = false;
    rs = false;
  });

  resize.addEventListener('mousedown', (e) => {
    rs = true;
    sw = panel.offsetWidth;
    sh = panel.offsetHeight;
    e.preventDefault();
  });

        console.log("Panel created successfully");
        return panel;
    } catch (error) {
        console.error("Error creating panel:", error);
        return null;
    }
}

// Add this function to initialize the main functionality
function initializeSmarterFunctionality() {
  // Get the current tab's URL
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    const currentUrl = tabs[0].url;
    
    // Update the panel content with the main interface
    const content = document.getElementById('smarter-panel-content');
    content.innerHTML = `
      <div style="text-align: center; padding: 20px;">
        <h3 style="margin-bottom: 15px;">Smarter Assistant</h3>
        <p style="color: #333; margin-bottom: 20px;">Analyzing: ${currentUrl}</p>
        <div id="smarter-analysis-result" style="margin-top: 20px;"></div>
      </div>
    `;

    // Start the analysis
    analyzeCurrentPage(currentUrl);
  });
}

// Add this function to analyze the current page
async function analyzeCurrentPage(url) {
  try {
    const response = await fetch('https://smarter-865bc5a924ea.herokuapp.com/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'include',
      body: JSON.stringify({ url })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const resultDiv = document.getElementById('smarter-analysis-result');
    
    if (data.status === 'success') {
      resultDiv.innerHTML = `
        <div style="background: #f8f9fa; padding: 15px; border-radius: 4px; text-align: left;">
          <h4 style="margin-bottom: 10px;">Analysis Results:</h4>
          <p>${data.message}</p>
        </div>
      `;
    } else {
      resultDiv.innerHTML = `
        <div style="color: red; text-align: center;">
          <p>${data.message || 'Analysis failed. Please try again.'}</p>
        </div>
      `;
    }
  } catch (error) {
    console.error('Analysis error:', error);
    const resultDiv = document.getElementById('smarter-analysis-result');
    resultDiv.innerHTML = `
      <div style="color: red; text-align: center;">
        <p>An error occurred during analysis. Please try again.</p>
      </div>
    `;
  }
}

// Add cookie debugging through background script
chrome.runtime.sendMessage({action: 'checkCookies'}, function(response) {
    console.log("=== Current Cookies ===");
    console.log("Cookies:", response);
});

// Add debugging to loadLoginForm function
async function loadLoginForm() {
    try {
        console.log("=== Loading Login Form ===");
        console.log("Extension URL:", chrome.runtime.getURL(''));
        
        const response = await fetch('https://smarter-865bc5a924ea.herokuapp.com/api/extension/login-form', {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json',
                'Origin': chrome.runtime.getURL(''),
                'Content-Type': 'application/json',
                'Referer': 'https://smarter-865bc5a924ea.herokuapp.com/'
            },
            credentials: 'include',
            mode: 'cors',
            cache: 'no-cache'
        });

        console.log("Login form response status:", response.status);
        console.log("Login form response headers:", Object.fromEntries(response.headers.entries()));

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log("Login form response data:", data);
        
        if (data.status === 'success') {
            // If user is already logged in, store session and return success message
            if (data.user) {
                console.log("User already logged in:", data.user);
                chrome.storage.local.set({
                    session: {
                        user: data.user,
                        timestamp: Date.now()
                    }
                }, function() {
                    console.log('Session data stored');
                });
                return '<div class="success-message">You are already logged in! You can close this window and use the extension.</div>';
            }
            
            // If we have HTML content, return it
            if (data.html) {
                console.log("Received login form HTML");
                // Add event listener to the form after it's inserted into the DOM
                setTimeout(() => {
                    const form = document.querySelector('#smarter-panel-content form');
                    if (form) {
                        form.addEventListener('submit', async (e) => {
                            e.preventDefault();
                            console.log("Form submitted");
                            
                            const formData = new FormData(form);
                            const email = formData.get('email');
                            const password = formData.get('password');
                            const csrfToken = formData.get('csrf_token');
                            
                            try {
                                const loginResponse = await fetch('https://smarter-865bc5a924ea.herokuapp.com/extension_login', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/x-www-form-urlencoded',
                                        'X-CSRFToken': csrfToken,
                                        'X-Requested-With': 'XMLHttpRequest'
                                    },
                                    credentials: 'include',
                                    body: new URLSearchParams({
                                        email: email,
                                        password: password,
                                        csrf_token: csrfToken
                                    })
                                });
                                
                                const loginData = await loginResponse.json();
                                console.log("Login response:", loginData);
                                
                                if (loginData.status === 'success') {
                                    // Store session data
                                    chrome.storage.local.set({
                                        session: {
                                            user: loginData.user,
                                            timestamp: Date.now()
                                        }
                                    }, function() {
                                        console.log('Session data stored after login');
                                    });
                                    
                                    // Update panel content with success message
                                    const content = document.getElementById('smarter-panel-content');
                                    content.innerHTML = `
                                        <div style="text-align: center; padding: 20px;">
                                            <h3 style="color: #28a745; margin-bottom: 15px;">Login Successful!</h3>
                                            <p>You can now close this window and use the extension.</p>
                                        </div>
                                    `;
                                    
                                    // Initialize the main functionality
                                    initializeSmarterFunctionality();
                                } else {
                                    // Show error message
                                    const content = document.getElementById('smarter-panel-content');
                                    content.innerHTML = `
                                        <div style="text-align: center; padding: 20px;">
                                            <h3 style="color: #dc3545; margin-bottom: 15px;">Login Failed</h3>
                                            <p>${loginData.message || 'Please try again.'}</p>
                                            <button id="try-again-btn" style="margin-top: 15px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                                Try Again
                                            </button>
                                        </div>
                                    `;
                                    
                                    // Add click handler for Try Again button
                                    document.getElementById('try-again-btn').addEventListener('click', async () => {
                                        const content = document.getElementById('smarter-panel-content');
                                        try {
                                            const html = await loadLoginForm();
                                            content.innerHTML = html;
                                        } catch (error) {
                                            console.error('Error reloading login form:', error);
                                            content.innerHTML = `
                                                <div style="text-align: center; padding: 20px;">
                                                    <h3 style="color: #dc3545; margin-bottom: 15px;">Error</h3>
                                                    <p>Failed to reload login form. Please try again later.</p>
                                                </div>
                                            `;
                                        }
                                    });
                                }
                            } catch (error) {
                                console.error('Login error:', error);
                                const content = document.getElementById('smarter-panel-content');
                                content.innerHTML = `
                                    <div style="text-align: center; padding: 20px;">
                                        <h3 style="color: #dc3545; margin-bottom: 15px;">Error</h3>
                                        <p>An error occurred during login. Please try again.</p>
                                        <button onclick="loadLoginForm()" style="margin-top: 15px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                            Try Again
                                        </button>
                                    </div>
                                `;
                            }
                        });
                    }
                }, 0);
                
                return data.html;
            }
            
            throw new Error('Invalid response format: missing HTML content');
        } else {
            throw new Error(data.message || 'Failed to load login form');
        }
    } catch (error) {
        console.error('Detailed login form error:', error);
        throw error;
    }
} 

// Initialize the extension functionality
console.log("Initializing Smarter functionality");
initializeSmarterFunctionality(); 
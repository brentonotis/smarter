// This file is intentionally empty as we're handling everything in the background script 

// Function to create and manage the panel
function createPanel() {
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
  close.onclick = () => panel.remove();
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
      
      // Create a temporary div to parse the HTML
      const temp = document.createElement('div');
      temp.innerHTML = data;
      
      // Extract the form and its styles
      const form = temp.querySelector('form');
      const styles = temp.querySelector('style');
      
      if (!form) {
        throw new Error('Login form not found in response');
      }
      
      // Update the panel content
      content.innerHTML = '';
      if (styles) content.appendChild(styles);
      
      // Create a new form with the same fields
      const newForm = document.createElement('form');
      newForm.method = 'POST';
      newForm.action = 'https://smarter-865bc5a924ea.herokuapp.com/api/extension/login';
      newForm.id = 'smarter-login-form';
      newForm.setAttribute('role', 'form');
      newForm.setAttribute('aria-label', 'Login Form');
      newForm.style.cssText = `
        width: 100% !important;
        max-width: 300px !important;
        margin: 0 auto !important;
      `;
      
      // Add CSRF token
      const csrfInput = document.createElement('input');
      csrfInput.type = 'hidden';
      csrfInput.id = 'csrf_token';
      csrfInput.name = 'csrf_token';
      csrfInput.value = form.querySelector('input[name="csrf_token"]').value;
      newForm.appendChild(csrfInput);
      
      // Add email field
      const emailGroup = document.createElement('div');
      emailGroup.className = 'form-group';
      emailGroup.setAttribute('role', 'group');
      emailGroup.setAttribute('aria-labelledby', 'smarter-email-label');
      emailGroup.style.cssText = 'margin-bottom: 15px !important;';
      emailGroup.innerHTML = `
        <label id="smarter-email-label" for="smarter-email-input" style="display: block; margin-bottom: 5px;">Email:</label>
        <input type="email" 
               id="smarter-email-input" 
               name="email" 
               autocomplete="username email" 
               required 
               aria-required="true"
               aria-label="Email Address"
               style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
      `;
      newForm.appendChild(emailGroup);
      
      // Add password field
      const passwordGroup = document.createElement('div');
      passwordGroup.className = 'form-group';
      passwordGroup.setAttribute('role', 'group');
      passwordGroup.setAttribute('aria-labelledby', 'smarter-password-label');
      passwordGroup.style.cssText = 'margin-bottom: 15px !important;';
      passwordGroup.innerHTML = `
        <label id="smarter-password-label" for="smarter-password-input" style="display: block; margin-bottom: 5px;">Password:</label>
        <input type="password" 
               id="smarter-password-input" 
               name="password" 
               autocomplete="current-password" 
               required 
               aria-required="true"
               aria-label="Password"
               style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
      `;
      newForm.appendChild(passwordGroup);
      
      // Add submit button
      const submitButton = document.createElement('button');
      submitButton.type = 'button';
      submitButton.id = 'smarter-submit-button';
      submitButton.textContent = 'Login';
      submitButton.setAttribute('aria-label', 'Submit login form');
      submitButton.style.cssText = `
        background: #007bff !important;
        color: white !important;
        border: none !important;
        padding: 10px 20px !important;
        border-radius: 4px !important;
        cursor: pointer !important;
        width: 100% !important;
        font-size: 14px !important;
      `;
      newForm.appendChild(submitButton);

      // Add error message div
      const errorMessage = document.createElement('div');
      errorMessage.id = 'error-message';
      errorMessage.className = 'error-message';
      errorMessage.style.cssText = 'color: #dc3545; margin-top: 10px; text-align: center; display: none;';
      newForm.appendChild(errorMessage);

      // Add loading message div
      const loadingMessage = document.createElement('div');
      loadingMessage.id = 'loading-message';
      loadingMessage.className = 'loading-message';
      loadingMessage.style.cssText = 'color: #007bff; margin-top: 10px; text-align: center; display: none;';
      loadingMessage.textContent = 'Logging in...';
      newForm.appendChild(loadingMessage);
      
      content.appendChild(newForm);
      
      // Add click event listener to the submit button
      submitButton.addEventListener('click', async function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const errorMessage = newForm.querySelector('#error-message');
        const loadingMessage = newForm.querySelector('#loading-message');
        const submitButton = newForm.querySelector('button[type="button"]');
        
        // Disable submit button and show loading message
        submitButton.disabled = true;
        loadingMessage.style.display = 'block';
        errorMessage.style.display = 'none';
        
        try {
            // Get CSRF token from the form
            const csrfToken = newForm.querySelector('input[name="csrf_token"]').value;
            
            // Log the form data being sent
            console.log('Sending login request with CSRF token:', csrfToken);
            
            // Create form data and encode it properly
            const formData = new FormData(newForm);
            const urlEncodedData = new URLSearchParams(formData).toString();
            
            // Always use the correct endpoint regardless of form action
            const response = await fetch('https://smarter-865bc5a924ea.herokuapp.com/api/extension/login', {
                method: 'POST',
                body: urlEncodedData,
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                    'Origin': chrome.runtime.getURL(''),
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': 'https://smarter-865bc5a924ea.herokuapp.com/'
                },
                credentials: 'include',
                mode: 'cors',
                cache: 'no-cache'
            });
            
            // Log the response status and headers
            console.log('Login response status:', response.status);
            console.log('Login response headers:', Object.fromEntries(response.headers.entries()));
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Login error response:', errorText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Non-JSON response:', text);
                throw new Error('Server returned non-JSON response');
            }
            
            const data = await response.json();
            console.log('Login form response:', data);
            
            if (data.status === 'success') {
                if (data.user) {
                    // User is already logged in
                    chrome.storage.local.set({
                        session: {
                            user: data.user,
                            timestamp: Date.now()
                        }
                    }, function() {
                        console.log('Session data stored');
                    });
                    
                    // Update UI to show success
                    content.innerHTML = '<div class="success-message">You are already logged in! You can close this window and use the extension.</div>';
                    return;
                }
                
                if (data.html) {
                    // Insert the HTML content into the page
                    content.innerHTML = data.html;
                    return;
                }
                
                throw new Error('Invalid response format: missing HTML content');
            }
            
            throw new Error(data.message || 'Failed to load login form');
        } catch (error) {
            console.error('Login error:', error);
            errorMessage.textContent = error.message || 'An error occurred during login. Please try again.';
            errorMessage.style.display = 'block';
        } finally {
            // Re-enable submit button and hide loading message
            submitButton.disabled = false;
            loadingMessage.style.display = 'none';
        }
      });
    } catch (error) {
      console.error('Detailed login form error:', error);
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
}

// Listen for messages from the background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'togglePanel') {
    const panel = document.getElementById('smarter-panel');
    if (panel) {
      panel.remove();
    } else {
      createPanel();
    }
  }
});

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

async function loadLoginForm() {
    try {
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

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.status === 'success') {
            return data.html;
        } else {
            throw new Error(data.message || 'Failed to load login form');
        }
    } catch (error) {
        console.error('Detailed login form error:', error);
        throw error;
    }
} 
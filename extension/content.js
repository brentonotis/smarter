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
    overflow: hidden !important;
    padding: 20px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    position: relative !important;
    isolation: isolate !important;
    contain: content !important;
    background: white !important;
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
      // Fetch the login form HTML
      const response = await fetch('https://smarter-865bc5a924ea.herokuapp.com/login', {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json'
        },
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.status !== 'success' || !data.html) {
        throw new Error('Invalid response format');
      }
      
      // Create a temporary div to parse the HTML
      const temp = document.createElement('div');
      temp.innerHTML = data.html;
      
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
      newForm.style.cssText = `
        width: 100% !important;
        max-width: 300px !important;
        margin: 0 auto !important;
      `;
      
      // Add CSRF token
      const csrfInput = document.createElement('input');
      csrfInput.type = 'hidden';
      csrfInput.name = 'csrf_token';
      const csrfToken = temp.querySelector('input[name="csrf_token"]');
      if (!csrfToken) {
        throw new Error('CSRF token not found in form');
      }
      csrfInput.value = csrfToken.value;
      newForm.appendChild(csrfInput);
      
      // Add email field
      const emailGroup = document.createElement('div');
      emailGroup.className = 'form-group';
      emailGroup.style.cssText = 'margin-bottom: 15px !important;';
      emailGroup.innerHTML = `
        <label for="email" style="display: block; margin-bottom: 5px;">Email:</label>
        <input type="email" id="email" name="email" required style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
      `;
      newForm.appendChild(emailGroup);
      
      // Add password field
      const passwordGroup = document.createElement('div');
      passwordGroup.className = 'form-group';
      passwordGroup.style.cssText = 'margin-bottom: 15px !important;';
      passwordGroup.innerHTML = `
        <label for="password" style="display: block; margin-bottom: 5px;">Password:</label>
        <input type="password" id="password" name="password" required style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
      `;
      newForm.appendChild(passwordGroup);
      
      // Add submit button
      const submitButton = document.createElement('button');
      submitButton.type = 'submit';
      submitButton.textContent = 'Login';
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
      
      content.appendChild(newForm);
      
      // Add event listener to the form
      newForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(newForm);
        try {
          const response = await fetch('https://smarter-865bc5a924ea.herokuapp.com/login', {
            method: 'POST',
            body: formData,
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'Accept': 'application/json'
            },
            credentials: 'include',
            mode: 'cors'
          });
          
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          
          const data = await response.json();
          
          if (data.status === 'success' && data.user && data.user.email) {
            // Update the panel content to show logged-in state
            content.innerHTML = `
              <div style="text-align: center;">
                <h3 style="margin-bottom: 15px;">Welcome to Smarter!</h3>
                <p style="color: #333;">You are now logged in as ${data.user.email}</p>
              </div>
            `;
          } else {
            // Show error message from server
            const errorDiv = document.createElement('div');
            errorDiv.style.cssText = 'color: red; margin-top: 10px; text-align: center;';
            errorDiv.textContent = data.message || 'Login failed. Please try again.';
            newForm.appendChild(errorDiv);
          }
        } catch (error) {
          console.error('Login error:', error);
          const errorDiv = document.createElement('div');
          errorDiv.style.cssText = 'color: red; margin-top: 10px; text-align: center;';
          errorDiv.textContent = 'An error occurred. Please try again.';
          newForm.appendChild(errorDiv);
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
// This file is intentionally empty as we're handling everything in the background script 

// Function to create and manage the panel
function createPanel() {
  const panel = document.createElement('div');
  panel.id = 'smarter-panel';
  panel.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    width: 400px;
    height: 600px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    z-index: 999999;
    display: flex;
    flex-direction: column;
  `;

  const header = document.createElement('div');
  header.id = 'smarter-panel-header';
  header.style.cssText = `
    padding: 10px;
    background: #f8f9fa;
    border-bottom: 1px solid #dee2e6;
    border-radius: 8px 8px 0 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: move;
  `;

  const title = document.createElement('div');
  title.id = 'smarter-panel-title';
  title.style.cssText = 'font-weight: bold; color: #333;';
  title.textContent = 'Smarter';
  header.appendChild(title);

  const close = document.createElement('button');
  close.id = 'smarter-panel-close';
  close.style.cssText = `
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: #666;
    padding: 0 5px;
  `;
  close.innerHTML = '×';
  close.onclick = () => panel.remove();
  header.appendChild(close);

  const content = document.createElement('div');
  content.id = 'smarter-panel-content';
  content.style.cssText = `
    flex: 1;
    border-radius: 0 0 8px 8px;
    overflow: hidden;
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  `;
  
  const loginButton = document.createElement('button');
  loginButton.style.cssText = `
    padding: 10px 20px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 16px;
  `;
  loginButton.textContent = 'Login to Smarter';
  loginButton.onclick = async () => {
    try {
      // Fetch the login form HTML
      const response = await fetch('https://smarter-865bc5a924ea.herokuapp.com/login', {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        },
        credentials: 'include'  // Important for cookies
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const html = await response.text();
      console.log('Login form HTML received:', html.substring(0, 200) + '...'); // Log first 200 chars
      
      // Create a temporary div to parse the HTML
      const temp = document.createElement('div');
      temp.innerHTML = html;
      
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
      newForm.action = 'https://smarter-865bc5a924ea.herokuapp.com/login';
      
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
      emailGroup.innerHTML = `
        <label for="email">Email:</label>
        <input type="email" id="email" name="email" required>
      `;
      newForm.appendChild(emailGroup);
      
      // Add password field
      const passwordGroup = document.createElement('div');
      passwordGroup.className = 'form-group';
      passwordGroup.innerHTML = `
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" required>
      `;
      newForm.appendChild(passwordGroup);
      
      // Add submit button
      const submitButton = document.createElement('button');
      submitButton.type = 'submit';
      submitButton.textContent = 'Login';
      submitButton.style.cssText = `
        background: #007bff;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        cursor: pointer;
        width: 100%;
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
              'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'include'  // Important for cookies
          });
          
          const data = await response.json();
          if (data.status === 'success') {
            // Update the panel content to show logged-in state
            content.innerHTML = `
              <div style="text-align: center;">
                <h3>Welcome to Smarter!</h3>
                <p>You are now logged in.</p>
              </div>
            `;
          } else {
            // Show error message
            const errorDiv = document.createElement('div');
            errorDiv.style.color = 'red';
            errorDiv.style.marginTop = '10px';
            errorDiv.textContent = 'Login failed. Please try again.';
            newForm.appendChild(errorDiv);
          }
        } catch (error) {
          console.error('Login error:', error);
          const errorDiv = document.createElement('div');
          errorDiv.style.color = 'red';
          errorDiv.style.marginTop = '10px';
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
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
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      const html = await response.text();
      
      // Create a temporary div to parse the HTML
      const temp = document.createElement('div');
      temp.innerHTML = html;
      
      // Extract the form and its styles
      const form = temp.querySelector('form');
      const styles = temp.querySelector('style');
      
      // Update the panel content
      content.innerHTML = '';
      if (styles) content.appendChild(styles);
      content.appendChild(form);
      
      // Add event listener to the form
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        try {
          const response = await fetch('https://smarter-865bc5a924ea.herokuapp.com/login', {
            method: 'POST',
            body: formData,
            headers: {
              'X-Requested-With': 'XMLHttpRequest'
            }
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
          }
        } catch (error) {
          console.error('Login error:', error);
        }
      });
    } catch (error) {
      console.error('Error loading login form:', error);
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
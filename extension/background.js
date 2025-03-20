// Listen for installation
chrome.runtime.onInstalled.addListener(function() {
    console.log("=== Extension Installed ===");
    // Initialize any extension data
    chrome.storage.local.get(['smarter_session'], function(result) {
        console.log("Initial session state:", result.smarter_session);
        if (!result.smarter_session) {
            chrome.storage.local.set({
                'smarter_session': null
            }, function() {
                console.log('Initialized empty session');
            });
        }
    });
});

// Listen for tab updates to inject content script
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url && !tab.url.startsWith('chrome://')) {
        console.log("=== Injecting content script for tab:", tabId);
        chrome.scripting.executeScript({
            target: { tabId: tabId },
            files: ['content.js']
        }).catch(error => {
            console.error('Error injecting content script:', error);
        });
    }
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    console.log("=== Background Script Message Received ===");
    console.log("Request:", request);
    console.log("Sender:", sender);
    
    if (request.action === 'checkSession') {
        chrome.storage.local.get(['smarter_session'], function(result) {
            console.log("Current session state:", result.smarter_session);
            sendResponse(result.smarter_session);
        });
        return true; // Will respond asynchronously
    }
});

// Add cookie change listener
chrome.cookies.onChanged.addListener(function(changeInfo) {
    console.log("=== Cookie Changed ===");
    console.log("Cookie change:", changeInfo);
    if (changeInfo.cookie.domain.includes('smarter-865bc5a924ea.herokuapp.com')) {
        console.log("Smarter cookie changed:", changeInfo.cookie);
    }
});

chrome.action.onClicked.addListener(async (tab) => {
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js']
    });
    
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      function: () => {
        const panel = document.getElementById('smarter-panel');
        if (panel) {
          panel.remove();
        } else {
          createPanel();
        }
      }
    });
  } catch (error) {
    console.error('Error executing script:', error);
  }
});

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
  `;
  
  const iframe = document.createElement('iframe');
  iframe.style.cssText = 'width: 100%; height: 100%; border: none;';
  iframe.src = 'https://smarter-865bc5a924ea.herokuapp.com/';
  content.appendChild(iframe);

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
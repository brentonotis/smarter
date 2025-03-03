// Smarter Bookmarklet
(function() {
    // Check if panel already exists
    if (document.getElementById('smarter-panel')) {
        document.getElementById('smarter-panel').remove();
        return;
    }

    // Create styles
    const styles = document.createElement('style');
    styles.textContent = `
        #smarter-panel {
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
        }
        #smarter-panel-header {
            padding: 10px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            border-radius: 8px 8px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        #smarter-panel-title {
            font-weight: bold;
            color: #333;
        }
        #smarter-panel-close {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #666;
            padding: 0 5px;
        }
        #smarter-panel-close:hover {
            color: #333;
        }
        #smarter-panel-content {
            flex: 1;
            border-radius: 0 0 8px 8px;
            overflow: hidden;
        }
        #smarter-panel iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        #smarter-panel-resize {
            position: absolute;
            bottom: 0;
            right: 0;
            width: 20px;
            height: 20px;
            cursor: se-resize;
            background: linear-gradient(135deg, transparent 50%, #ddd 50%);
        }
    `;
    document.head.appendChild(styles);

    // Create panel
    const panel = document.createElement('div');
    panel.id = 'smarter-panel';

    // Create header
    const header = document.createElement('div');
    header.id = 'smarter-panel-header';

    // Create title
    const title = document.createElement('div');
    title.id = 'smarter-panel-title';
    title.textContent = 'Smarter';
    header.appendChild(title);

    // Create close button
    const closeBtn = document.createElement('button');
    closeBtn.id = 'smarter-panel-close';
    closeBtn.innerHTML = '×';
    closeBtn.onclick = () => panel.remove();
    header.appendChild(closeBtn);

    // Create content
    const content = document.createElement('div');
    content.id = 'smarter-panel-content';

    // Create iframe
    const iframe = document.createElement('iframe');
    iframe.src = 'https://smarter-865bc5a924ea.herokuapp.com/';
    content.appendChild(iframe);

    // Create resize handle
    const resizeHandle = document.createElement('div');
    resizeHandle.id = 'smarter-panel-resize';

    // Add all elements to panel
    panel.appendChild(header);
    panel.appendChild(content);
    panel.appendChild(resizeHandle);

    // Add panel to page
    document.body.appendChild(panel);

    // Make panel draggable
    let isDragging = false;
    let currentX;
    let currentY;
    let initialX;
    let initialY;
    let xOffset = 0;
    let yOffset = 0;

    header.addEventListener('mousedown', dragStart);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', dragEnd);

    function dragStart(e) {
        initialX = e.clientX - xOffset;
        initialY = e.clientY - yOffset;

        if (e.target === header || e.target === title) {
            isDragging = true;
        }
    }

    function drag(e) {
        if (isDragging) {
            e.preventDefault();
            currentX = e.clientX - initialX;
            currentY = e.clientY - initialY;

            xOffset = currentX;
            yOffset = currentY;

            setTranslate(currentX, currentY, panel);
        }
    }

    function dragEnd() {
        initialX = currentX;
        initialY = currentY;
        isDragging = false;
    }

    function setTranslate(xPos, yPos, el) {
        el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
    }

    // Make panel resizable
    let isResizing = false;
    let startWidth;
    let startHeight;

    resizeHandle.addEventListener('mousedown', resizeStart);
    document.addEventListener('mousemove', resize);
    document.addEventListener('mouseup', resizeEnd);

    function resizeStart(e) {
        isResizing = true;
        startWidth = panel.offsetWidth;
        startHeight = panel.offsetHeight;
        e.preventDefault();
    }

    function resize(e) {
        if (isResizing) {
            const width = startWidth + (e.clientX - startWidth);
            const height = startHeight + (e.clientY - startHeight);

            if (width > 300 && height > 200) {
                panel.style.width = `${width}px`;
                panel.style.height = `${height}px`;
            }
        }
    }

    function resizeEnd() {
        isResizing = false;
    }
})(); 
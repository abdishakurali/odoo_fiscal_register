/** @odoo-module alias=fiscal_net.favicon_setter **/

// Set custom favicon for all pages
function setCustomFavicon() {
    const faviconPath = '/fiscal_net/static/src/img/favicon.ico';
    
    // Remove existing favicon links (be more aggressive for POS)
    const existingFavicons = document.querySelectorAll('link[rel*="icon"], link[rel*="shortcut"]');
    existingFavicons.forEach(link => {
        if (link.href && !link.href.includes('fiscal_net')) {
            link.remove();
        }
    });
    
    // Also remove any favicon links that might be in the head
    const allLinks = document.querySelectorAll('head link');
    allLinks.forEach(link => {
        if (link.rel && (link.rel.includes('icon') || link.rel.includes('shortcut')) && 
            link.href && !link.href.includes('fiscal_net')) {
            link.remove();
        }
    });
    
    // Create new favicon link
    const faviconLink = document.createElement('link');
    faviconLink.rel = 'shortcut icon';
    faviconLink.type = 'image/x-icon';
    faviconLink.href = faviconPath;
    
    // Add to head
    document.head.appendChild(faviconLink);
    
    // Also create a regular icon link for better browser support
    const iconLink = document.createElement('link');
    iconLink.rel = 'icon';
    iconLink.type = 'image/x-icon';
    iconLink.href = faviconPath;
    
    document.head.appendChild(iconLink);
    
    // For modern browsers, also set apple-touch-icon
    const appleTouchIcon = document.createElement('link');
    appleTouchIcon.rel = 'apple-touch-icon';
    appleTouchIcon.href = faviconPath;
    
    document.head.appendChild(appleTouchIcon);
}

// Set favicon immediately
setCustomFavicon();

// Set favicon when DOM is ready
document.addEventListener('DOMContentLoaded', setCustomFavicon);

// Set favicon when page loads
window.addEventListener('load', setCustomFavicon);

// Use MutationObserver to catch dynamic changes to head
if (typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.target === document.head) {
                // Check if any new favicon links were added that aren't ours
                const addedNodes = Array.from(mutation.addedNodes);
                addedNodes.forEach(node => {
                    if (node.nodeType === Node.ELEMENT_NODE && 
                        node.tagName === 'LINK' && 
                        (node.rel.includes('icon') || node.rel.includes('shortcut')) &&
                        !node.href.includes('fiscal_net')) {
                        // Remove non-custom favicons
                        node.remove();
                    }
                });
            }
        });
    });
    
    // Start observing
    observer.observe(document.head, {
        childList: true,
        subtree: true
    });
}

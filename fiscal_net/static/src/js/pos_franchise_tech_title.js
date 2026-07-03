/** @odoo-module **/

// Simple approach: just change the document title without patching App constructor
// This avoids interfering with the Owl framework lifecycle

function setFranchiseTechTitle() {
    // Check if we're on a POS page and change title
    if (window.location.pathname.includes('/pos/web') ||
        window.location.pathname.includes('/point_of_sale') ||
        document.title.includes('POS') ||
        document.title.includes('Point of Sale') ||
        document.title.includes('Odoo')) {
        document.title = 'Franchise Tech';
    }
}

// Set title immediately
setFranchiseTechTitle();

// Set title when DOM is ready
document.addEventListener('DOMContentLoaded', setFranchiseTechTitle);

// Set title when page loads (for dynamic content)
window.addEventListener('load', setFranchiseTechTitle);

// Use MutationObserver to catch dynamic title changes
if (typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' || mutation.type === 'attributes') {
                setFranchiseTechTitle();
            }
        });
    });

    // Start observing
    observer.observe(document, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['title']
    });
}

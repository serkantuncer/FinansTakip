// Text Truncation and Display Utilities for Investment Tracker

document.addEventListener('DOMContentLoaded', function() {
    // Initialize text truncation
    initTextTruncation();
    
    // Initialize expandable cells
    initExpandableCells();
    
    // Initialize responsive text handling
    initResponsiveText();
});

function initTextTruncation() {
    const truncateElements = document.querySelectorAll('.text-truncate');
    
    truncateElements.forEach(function(element) {
        const originalText = element.textContent;
        const maxLength = element.dataset.maxLength || 30;
        
        if (originalText.length > maxLength) {
            const truncatedText = originalText.substring(0, maxLength) + '...';
            element.textContent = truncatedText;
            
            // Store original text for tooltip
            element.setAttribute('title', originalText);
            element.setAttribute('data-bs-toggle', 'tooltip');
            element.setAttribute('data-bs-placement', 'top');
            
            // Initialize tooltip
            new bootstrap.Tooltip(element);
        }
    });
}

function initExpandableCells() {
    const expandableCells = document.querySelectorAll('.expandable-cell');
    
    expandableCells.forEach(function(cell) {
        const content = cell.querySelector('.cell-content');
        const expandBtn = cell.querySelector('.expand-btn');
        
        if (content && expandBtn) {
            expandBtn.addEventListener('click', function() {
                const isExpanded = content.classList.contains('expanded');
                
                if (isExpanded) {
                    content.classList.remove('expanded');
                    expandBtn.innerHTML = '<i class="fas fa-chevron-down"></i>';
                    expandBtn.setAttribute('title', 'Genişlet');
                } else {
                    content.classList.add('expanded');
                    expandBtn.innerHTML = '<i class="fas fa-chevron-up"></i>';
                    expandBtn.setAttribute('title', 'Daralt');
                }
            });
        }
    });
}

function initResponsiveText() {
    // Handle responsive text sizing
    const responsiveTexts = document.querySelectorAll('.responsive-text');
    
    function adjustTextSizes() {
        const screenWidth = window.innerWidth;
        
        responsiveTexts.forEach(function(element) {
            if (screenWidth < 768) {
                element.classList.add('text-sm');
            } else {
                element.classList.remove('text-sm');
            }
        });
    }
    
    // Initial adjustment
    adjustTextSizes();
    
    // Adjust on window resize
    window.addEventListener('resize', adjustTextSizes);
}

// Utility function to truncate text
function truncateText(text, maxLength, suffix = '...') {
    if (text.length <= maxLength) {
        return text;
    }
    return text.substring(0, maxLength) + suffix;
}

// Utility function to create expandable text element
function createExpandableText(text, maxLength = 50) {
    if (text.length <= maxLength) {
        return document.createTextNode(text);
    }
    
    const container = document.createElement('div');
    container.className = 'expandable-text';
    
    const shortText = document.createElement('span');
    shortText.className = 'short-text';
    shortText.textContent = truncateText(text, maxLength);
    
    const fullText = document.createElement('span');
    fullText.className = 'full-text d-none';
    fullText.textContent = text;
    
    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'btn btn-link btn-sm p-0 ms-1';
    toggleBtn.innerHTML = 'Daha fazla';
    
    toggleBtn.addEventListener('click', function() {
        const isExpanded = fullText.classList.contains('d-none');
        
        if (isExpanded) {
            shortText.classList.add('d-none');
            fullText.classList.remove('d-none');
            toggleBtn.innerHTML = 'Daha az';
        } else {
            shortText.classList.remove('d-none');
            fullText.classList.add('d-none');
            toggleBtn.innerHTML = 'Daha fazla';
        }
    });
    
    container.appendChild(shortText);
    container.appendChild(fullText);
    container.appendChild(toggleBtn);
    
    return container;
}

// Smart truncation for table cells
function smartTruncateTableCells() {
    const tableCells = document.querySelectorAll('td');
    
    tableCells.forEach(function(cell) {
        const text = cell.textContent.trim();
        const cellWidth = cell.offsetWidth;
        
        // Calculate approximate character limit based on cell width
        const charLimit = Math.floor(cellWidth / 8); // Rough estimate
        
        if (text.length > charLimit && charLimit > 10) {
            const truncatedText = truncateText(text, charLimit);
            cell.innerHTML = `<span title="${text}" data-bs-toggle="tooltip">${truncatedText}</span>`;
            
            // Initialize tooltip
            const tooltip = cell.querySelector('[data-bs-toggle="tooltip"]');
            if (tooltip) {
                new bootstrap.Tooltip(tooltip);
            }
        }
    });
}

// Format long numbers for display
function formatLongNumber(number, precision = 2) {
    if (Math.abs(number) >= 1000000) {
        return (number / 1000000).toFixed(precision) + 'M';
    } else if (Math.abs(number) >= 1000) {
        return (number / 1000).toFixed(precision) + 'K';
    }
    return number.toFixed(precision);
}

// Create tooltip for truncated content
function createTooltip(element, content) {
    element.setAttribute('title', content);
    element.setAttribute('data-bs-toggle', 'tooltip');
    element.setAttribute('data-bs-placement', 'top');
    return new bootstrap.Tooltip(element);
}

// Auto-resize text areas
function autoResizeTextareas() {
    const textareas = document.querySelectorAll('textarea.auto-resize');
    
    textareas.forEach(function(textarea) {
        textarea.style.overflow = 'hidden';
        
        function resize() {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        }
        
        textarea.addEventListener('input', resize);
        textarea.addEventListener('change', resize);
        
        // Initial resize
        resize();
    });
}

// Export utilities
window.TruncateUtils = {
    truncateText: truncateText,
    createExpandableText: createExpandableText,
    smartTruncateTableCells: smartTruncateTableCells,
    formatLongNumber: formatLongNumber,
    createTooltip: createTooltip,
    autoResizeTextareas: autoResizeTextareas
};

// Auto-initialize on DOM changes (for dynamic content)
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.type === 'childList') {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    // Re-initialize truncation for new elements
                    const truncateElements = node.querySelectorAll('.text-truncate');
                    if (truncateElements.length > 0) {
                        initTextTruncation();
                    }
                }
            });
        }
    });
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});

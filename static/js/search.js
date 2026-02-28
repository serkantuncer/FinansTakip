// Search and Filter JavaScript for Investment Tracker

document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    // Real-time search functionality
    const searchInput = document.getElementById('search-input') || (searchForm ? searchForm.querySelector('input[name="search"]') : null);
    const tableRows = document.querySelectorAll('.table-responsive tbody tr');
    
    if (searchInput && tableRows.length > 0) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase().trim();
            
            tableRows.forEach(function(row) {
                const text = row.textContent.toLowerCase();
                const shouldShow = searchTerm === '' || text.includes(searchTerm);
                
                row.style.display = shouldShow ? '' : 'none';
            });
            
            updateNoResultsMessage();
        });
    }

    // Filter change handlers
    const tipFilter = document.getElementById('tip-filter') || (searchForm ? searchForm.querySelector('select[name="tip"]') : null);
    const kategoriFilter = document.getElementById('kategori-filter') || (searchForm ? searchForm.querySelector('select[name="kategori"]') : null);
    
    if (tipFilter) {
        tipFilter.addEventListener('change', function() {
            applyFilters();
        });
    }
    
    if (kategoriFilter) {
        kategoriFilter.addEventListener('change', function() {
            applyFilters();
        });
    }

    // Clear filters button
    const clearFiltersButton = document.getElementById('clearFilters');
    if (clearFiltersButton) {
        clearFiltersButton.addEventListener('click', function() {
            if (searchInput) searchInput.value = '';
            if (tipFilter) tipFilter.value = '';
            if (kategoriFilter) kategoriFilter.value = '';
            
            // Show all rows
            tableRows.forEach(function(row) {
                row.style.display = '';
            });
            
            updateNoResultsMessage();
        });
    }

    function applyFilters() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const selectedTip = tipFilter ? tipFilter.value : '';
        const selectedKategori = kategoriFilter ? kategoriFilter.value : '';
        
        tableRows.forEach(function(row) {
            const text = row.textContent.toLowerCase();
            const tipCell = row.querySelector('td:first-child');
            const kategoriCell = row.querySelector('td:nth-last-child(2)');
            
            let shouldShow = true;
            
            // Apply search filter
            if (searchTerm && !text.includes(searchTerm)) {
                shouldShow = false;
            }
            
            // Apply tip filter
            if (selectedTip && tipCell) {
                const tipText = tipCell.textContent.toLowerCase().trim();
                if (!tipText.includes(selectedTip.toLowerCase())) {
                    shouldShow = false;
                }
            }
            
            // Apply kategori filter
            if (selectedKategori && kategoriCell) {
                const kategoriText = kategoriCell.textContent.trim();
                if (kategoriText === '-' || !kategoriText.includes(selectedKategori)) {
                    shouldShow = false;
                }
            }
            
            row.style.display = shouldShow ? '' : 'none';
        });
        
        updateNoResultsMessage();
    }

    function updateNoResultsMessage() {
        const table = document.querySelector('.table-responsive table');
        if (!table) return;
        
        const visibleRows = Array.from(tableRows).filter(row => 
            row.style.display !== 'none'
        );
        
        let noResultsRow = table.querySelector('.no-results-row');
        
        if (visibleRows.length === 0) {
            if (!noResultsRow) {
                noResultsRow = document.createElement('tr');
                noResultsRow.className = 'no-results-row';
                noResultsRow.innerHTML = `
                    <td colspan="13" class="text-center py-4 text-muted">
                        <i class="fas fa-search fa-2x mb-3 d-block"></i>
                        <h5>Sonuç bulunamadı</h5>
                        <p class="mb-0">Arama kriterlerinizi değiştirmeyi deneyin.</p>
                    </td>
                `;
                table.querySelector('tbody').appendChild(noResultsRow);
            }
        } else {
            if (noResultsRow) {
                noResultsRow.remove();
            }
        }
    }

    // Quick filter buttons
    const quickFilterButtons = document.querySelectorAll('.quick-filter');
    quickFilterButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const filterType = this.dataset.filter;
            const filterValue = this.dataset.value;
            
            if (filterType === 'tip' && tipFilter) {
                tipFilter.value = filterValue;
            } else if (filterType === 'kategori' && kategoriFilter) {
                kategoriFilter.value = filterValue;
            }
            
            applyFilters();
        });
    });

    // Sort functionality
    const sortableHeaders = document.querySelectorAll('.sortable-header');
    let currentSortColumn = null;
    let currentSortDirection = 'asc';
    
    sortableHeaders.forEach(function(header) {
        header.style.cursor = 'pointer';
        header.addEventListener('click', function() {
            const columnIndex = Array.from(this.parentNode.children).indexOf(this);
            
            if (currentSortColumn === columnIndex) {
                currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortColumn = columnIndex;
                currentSortDirection = 'asc';
            }
            
            sortTable(columnIndex, currentSortDirection);
            updateSortIcons(this, currentSortDirection);
        });
    });

    function sortTable(columnIndex, direction) {
        const tbody = document.querySelector('tbody');
        if (!tbody) return;
        
        const rows = Array.from(tbody.querySelectorAll('tr')).filter(row => 
            !row.classList.contains('no-results-row')
        );
        
        rows.sort(function(a, b) {
            const aCell = a.children[columnIndex];
            const bCell = b.children[columnIndex];
            
            if (!aCell || !bCell) return 0;
            
            let aValue = aCell.textContent.trim();
            let bValue = bCell.textContent.trim();
            
            // Try to parse as numbers for numeric columns
            const aNumber = parseFloat(aValue.replace(/[^\d.-]/g, ''));
            const bNumber = parseFloat(bValue.replace(/[^\d.-]/g, ''));
            
            if (!isNaN(aNumber) && !isNaN(bNumber)) {
                return direction === 'asc' ? aNumber - bNumber : bNumber - aNumber;
            }
            
            // String comparison for text columns
            if (direction === 'asc') {
                return aValue.localeCompare(bValue);
            } else {
                return bValue.localeCompare(aValue);
            }
        });
        
        rows.forEach(function(row) {
            tbody.appendChild(row);
        });
    }

    function updateSortIcons(header, direction) {
        // Remove existing sort icons
        sortableHeaders.forEach(function(h) {
            h.innerHTML = h.innerHTML.replace(/<i class="fas fa-sort.*?"><\/i>/g, '');
        });
        
        // Add sort icon to current header
        const icon = direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down';
        header.innerHTML += ` <i class="fas ${icon}"></i>`;
    }
});

// Export search utilities
window.SearchUtils = {
    applyFilters: function() {
        // Trigger filter application
        const event = new Event('input');
        const searchForm = document.getElementById('searchForm');
        const searchInput = document.getElementById('search-input') || (searchForm ? searchForm.querySelector('input[name="search"]') : null);
        if (searchInput) {
            searchInput.dispatchEvent(event);
        }
    },
    
    clearFilters: function() {
        const searchForm = document.getElementById('searchForm');
        const searchInput = document.getElementById('search-input') || (searchForm ? searchForm.querySelector('input[name="search"]') : null);
        const tipFilter = document.getElementById('tip-filter') || (searchForm ? searchForm.querySelector('select[name="tip"]') : null);
        const kategoriFilter = document.getElementById('kategori-filter') || (searchForm ? searchForm.querySelector('select[name="kategori"]') : null);
        
        if (searchInput) searchInput.value = '';
        if (tipFilter) tipFilter.value = '';
        if (kategoriFilter) kategoriFilter.value = '';
        
        this.applyFilters();
    }
};

// Investment Tracker Actions JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            if (alert && alert.parentNode) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });

    // Form validation for add investment modal
    const addForm = document.querySelector('#yatirimEkleModal form');
    if (addForm) {
        addForm.addEventListener('submit', function(e) {
            const tip = addForm.querySelector('[name="tip"]').value;
            const kod = addForm.querySelector('[name="kod"]').value;
            const alisFiyati = addForm.querySelector('[name="alis_fiyati"]').value;
            const miktar = addForm.querySelector('[name="miktar"]').value;

            if (!tip || !kod || !alisFiyati || !miktar) {
                e.preventDefault();
                alert('Lütfen zorunlu alanları doldurun!');
                return false;
            }

            if (parseFloat(alisFiyati) <= 0 || parseFloat(miktar) <= 0) {
                e.preventDefault();
                alert('Fiyat ve miktar 0\'dan büyük olmalıdır!');
                return false;
            }
        });
    }

    // Loading state for bulk price update
    const bulkUpdateForm = document.querySelector('form[action*="toplu_fiyat_guncelle"]');
    if (bulkUpdateForm) {
        bulkUpdateForm.addEventListener('submit', function() {
            const button = this.querySelector('button[type="submit"]');
            if (button) {
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Güncelleniyor...';
            }
        });
    }

    // Individual price update loading states
    const priceUpdateForms = document.querySelectorAll('form[action*="fiyat_guncelle"]');
    priceUpdateForms.forEach(function(form) {
        form.addEventListener('submit', function() {
            const button = this.querySelector('button[type="submit"]');
            if (button) {
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            }
        });
    });

    // Confirmation for delete actions
    const deleteButtons = document.querySelectorAll('[data-bs-target*="silModal"]');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const modalId = this.getAttribute('data-bs-target');
            const modal = document.querySelector(modalId);
            if (modal) {
                const deleteForm = modal.querySelector('form');
                if (deleteForm) {
                    deleteForm.addEventListener('submit', function(e) {
                        if (!confirm('Bu yatırımı silmek istediğinizden emin misiniz?')) {
                            e.preventDefault();
                        }
                    });
                }
            }
        });
    });

    // Format number inputs
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            if (this.value) {
                this.value = parseFloat(this.value).toFixed(6);
            }
        });
    });

    // Auto-uppercase kod input
    const kodInputs = document.querySelectorAll('input[name="kod"]');
    kodInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    });

    // Investment type change handler
    const tipSelect = document.querySelector('select[name="tip"]');
    if (tipSelect) {
        tipSelect.addEventListener('change', function() {
            const kodInput = document.querySelector('input[name="kod"]');
            if (kodInput) {
                // Clear previous value and set placeholder based on type
                kodInput.value = '';
                switch(this.value) {
                    case 'fon':
                        kodInput.placeholder = 'örn: AKFON, GARAN';
                        break;
                    case 'hisse':
                        kodInput.placeholder = 'örn: THYAO, AKBNK';
                        break;
                    case 'altin':
                        kodInput.placeholder = 'GA, C, Y, T';
                        break;
                    case 'doviz':
                        kodInput.placeholder = 'USD, EUR, GBP';
                        break;
                    default:
                        kodInput.placeholder = 'Yatırım kodu';
                }
            }
        });
    }
});

// Utility functions
function formatCurrency(amount) {
    return new Intl.NumberFormat('tr-TR', {
        style: 'currency',
        currency: 'TRY',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

function formatPercentage(percentage) {
    return new Intl.NumberFormat('tr-TR', {
        style: 'percent',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
        signDisplay: 'always'
    }).format(percentage / 100);
}

// Export functions for global use
window.InvestmentTracker = {
    formatCurrency: formatCurrency,
    formatPercentage: formatPercentage
};

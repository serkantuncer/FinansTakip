/**
 * Metni belirli bir uzunlukta kısaltır ve tooltip olarak tam metnin görünmesini sağlar
 * @param {string} text - Kısaltılacak metin
 * @param {number} maxLength - Maksimum karakter sayısı
 * @returns {HTMLElement} - Kısaltılmış metni içeren HTML elementi
 */
function truncateText(text, maxLength = 20) {
    if (!text) return document.createTextNode('-');
    if (text.length <= maxLength) return document.createTextNode(text);
    
    const span = document.createElement('span');
    span.className = 'truncated-text';
    span.textContent = text.substring(0, maxLength) + '...';
    span.setAttribute('data-bs-toggle', 'tooltip');
    span.setAttribute('data-bs-placement', 'top');
    span.setAttribute('title', text);
    
    return span;
}

/**
 * Tablodaki hücrelere truncate işlevselliği ekler
 * @param {HTMLElement} tableElement - İşlem yapılacak tablo elemanı
 * @param {Object} options - Kısaltma seçenekleri
 */
function initTruncateTable(tableElement, options = {}) {
    const defaults = {
        isimMaxLength: 30,    // İsim sütunu için maksimum uzunluk
        kategoriMaxLength: 15, // Kategori sütunu için maksimum uzunluk
        notlarMaxLength: 30    // Notlar sütunu için maksimum uzunluk (eğer görünürse)
    };
    
    const settings = {...defaults, ...options};
    
    // Tooltip'leri başlat
    const tooltipList = [];
    const initTooltips = () => {
        // Önceden oluşturulmuş tooltipleri imha et
        tooltipList.forEach(tooltip => tooltip.dispose());
        tooltipList.length = 0;
        
        // Yeni tooltipleri başlat
        const tooltipTriggerList = [].slice.call(tableElement.querySelectorAll('[data-bs-toggle="tooltip"]'));
        const newTooltips = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
        tooltipList.push(...newTooltips);
    };
    
    // MutationObserver ile tablodaki değişiklikleri izle
    const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            if (mutation.type === 'childList') {
                // Yeni eklenen satırları işle
                mutation.addedNodes.forEach(node => {
                    if (node.nodeName === 'TR') {
                        processRow(node);
                    }
                });
                // Tooltipleri yenile
                initTooltips();
            }
        });
    });
    
    // Tabloyu gözlemle
    observer.observe(tableElement.querySelector('tbody'), { childList: true, subtree: true });
    
    // Mevcut satırları işle
    Array.from(tableElement.querySelectorAll('tbody tr')).forEach(row => {
        processRow(row);
    });
    
    // Tooltipleri başlat
    initTooltips();
    
    // Satır işleme fonksiyonu
    function processRow(row) {
        // İsim hücresi (1. indeks)
        const isimCell = row.cells[1];
        if (isimCell && isimCell.textContent.trim() !== '-') {
            const text = isimCell.textContent;
            isimCell.textContent = '';
            isimCell.appendChild(truncateText(text, settings.isimMaxLength));
        }
        
        // Kategori hücresi (3. indeks)
        const kategoriCell = row.cells[3];
        if (kategoriCell && kategoriCell.textContent.trim() !== '-') {
            const text = kategoriCell.textContent;
            kategoriCell.textContent = '';
            kategoriCell.appendChild(truncateText(text, settings.kategoriMaxLength));
        }
    }
    
    // Observer'ı durdurma metodu
    return {
        destroy: () => {
            observer.disconnect();
            tooltipList.forEach(tooltip => tooltip.dispose());
        }
    };
}

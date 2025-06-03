/**
 * Yatırım işlemleri için ortak fonksiyonlar
 */

/**
 * İşlem düğmelerini oluşturur
 * @param {number} yatirimId - Yatırım ID
 * @param {string} kod - Yatırım kodu
 * @param {string} isim - Yatırım ismi
 * @returns {HTMLDivElement} - İşlem düğmelerini içeren HTML elementi
 */
function createActionButtons(yatirimId, kod, isim) {
    // Buton grubu oluştur
    const btnGroup = document.createElement('div');
    btnGroup.className = 'btn-group btn-action-group';
    
    // Güncelleme butonu
    const guncelleBtn = document.createElement('button');
    guncelleBtn.className = 'btn btn-sm btn-success';
    guncelleBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
    guncelleBtn.setAttribute('title', 'Güncelle');
    guncelleBtn.addEventListener('click', function() {
        yatirimGuncelle(yatirimId);
    });
    
    // Düzenleme butonu
    const duzenleBtn = document.createElement('button');
    duzenleBtn.className = 'btn btn-sm btn-primary';
    duzenleBtn.innerHTML = '<i class="bi bi-pencil"></i>';
    duzenleBtn.setAttribute('title', 'Düzenle');
    duzenleBtn.addEventListener('click', function() {
        yatirimDuzenle(yatirimId);
    });
    
    // Silme butonu
    const silBtn = document.createElement('button');
    silBtn.className = 'btn btn-sm btn-danger';
    silBtn.innerHTML = '<i class="bi bi-trash"></i>';
    silBtn.setAttribute('title', 'Sil');
    silBtn.addEventListener('click', function() {
        yatirimSil(yatirimId, kod, isim);
    });
    
    btnGroup.appendChild(guncelleBtn);
    btnGroup.appendChild(duzenleBtn);
    btnGroup.appendChild(silBtn);
    
    return btnGroup;
}
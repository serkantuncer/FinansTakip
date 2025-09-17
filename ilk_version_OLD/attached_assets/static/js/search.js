/**
 * Yatırım kodu arama ve otomatik tamamlama işlevleri
 */

function initializeSearch(options) {
    const { kodInput, kodSonuclar, tipSelect, isimInput, alisFiyatiInput } = options;
    
    if (!kodInput || !kodSonuclar || !tipSelect) {
        console.error('Arama başlatmak için gerekli elementler bulunamadı');
        return;
    }
    
    // Arama zamanlaması için değişken
    let aramaZamanlayici;
    let sonArananTerim = '';
    
    // Arama sorgusu gönder
    function aramaYap(tip, terim) {
        if (terim === sonArananTerim && terim.length < 2) {
            return;
        }
        
        sonArananTerim = terim;
        
        if (terim.length < 2) {
            // Terim çok kısaysa sonuçları gizle
            kodSonuclar.style.display = 'none';
            return;
        }
        
        // Hangi API'yi çağıracağımızı belirle
        let apiUrl;
        if (tip === 'fon') {
            apiUrl = `/api/arama/fon/${terim}`;
        } else if (tip === 'hisse') {
            apiUrl = `/api/arama/hisse/${terim}`;
        } else {
            // Diğer tipler için arama desteği yok
            kodSonuclar.style.display = 'none';
            return;
        }
        
        fetch(apiUrl)
            .then(response => response.json())
            .then(data => {
                const listGroup = kodSonuclar.querySelector('.list-group');
                listGroup.innerHTML = '';
                
                if (data.length === 0) {
                    kodSonuclar.style.display = 'none';
                    return;
                }
                
                // Sonuçları listele
                data.forEach(sonuc => {
                    const item = document.createElement('a');
                    item.className = 'list-group-item list-group-item-action';
                    item.innerHTML = `<strong>${sonuc.kod}</strong> - ${sonuc.isim}`;
                    
                    // Sonuç tıklandığında
                    item.addEventListener('click', function() {
                        kodInput.value = sonuc.kod;
                        if (isimInput) {
                            isimInput.value = sonuc.isim;
                        }
                        
                        // Yatırım bilgilerini doğrula
                        dogrulaVeDoldur(sonuc.tur, sonuc.kod);
                        
                        // Sonuçları gizle
                        kodSonuclar.style.display = 'none';
                    });
                    
                    listGroup.appendChild(item);
                });
                
                // Sonuçları göster
                kodSonuclar.style.display = 'block';
            })
            .catch(error => {
                console.error('Arama hatası:', error);
                kodSonuclar.style.display = 'none';
            });
    }
    
    // Yatırım bilgilerini doğrulama ve form doldurma
    function dogrulaVeDoldur(tip, kod) {
        console.log(`Doğrulanıyor: ${tip} - ${kod}`);
        // API'ye doğrulama isteği gönder
        fetch('/api/yatirim/dogrula', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                tip: tip,
                kod: kod
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.basarili) {
                console.log('Doğrulama başarılı:', data.veri);
                
                // İsim alanını her zaman güncelle (boş olsun olmasın)
                if (isimInput && data.veri.isim) {
                    isimInput.value = data.veri.isim;
                }
                
                // Alış fiyatı güncel fiyat ile doldur
                if (alisFiyatiInput && data.veri.guncel_fiyat) {
                    // Hassasiyet ayarı (ondalık basamak sayısı)
                    let precision = 2;
                    if (tip === 'fon') precision = 6;
                    else if (tip === 'hisse') precision = 2;
                    else if (tip === 'altin') precision = 2;
                    else if (tip === 'doviz') precision = 4;
                    
                    // Fiyatı formatla ve güncelle
                    const formattedPrice = parseFloat(data.veri.guncel_fiyat).toFixed(precision);
                    alisFiyatiInput.value = formattedPrice;
                }
            } else if (data.hata) {
                console.warn('Doğrulama başarısız:', data.hata);
            }
        })
        .catch(error => {
            console.error('Doğrulama hatası:', error);
        });
    }
    
    // Kod input alanında yazıldığında
    kodInput.addEventListener('input', function() {
        const tip = tipSelect.value;
        const terim = this.value.trim();
        
        // Önceki zamanlayıcıyı temizle
        clearTimeout(aramaZamanlayici);
        
        // Tip değiştiğinde fiyat alanını temizle 
        if (alisFiyatiInput) {
            alisFiyatiInput.value = '';
        }
        
        // Fon, hisse, altın ve döviz için doğrulama yap
        if (tip === 'fon' || tip === 'hisse') {
            // 300ms bekleyip arama yap (kullanıcı yazmayı bitirdiğinde)
            aramaZamanlayici = setTimeout(() => {
                aramaYap(tip, terim);
            }, 300);
        } else if ((tip === 'altin' || tip === 'doviz') && terim.length > 0) {
            // Altın ve döviz için doğrudan doğrula
            aramaZamanlayici = setTimeout(() => {
                dogrulaVeDoldur(tip, terim);
            }, 500);
            kodSonuclar.style.display = 'none';
        } else {
            kodSonuclar.style.display = 'none';
        }
    });
    
    // Seçili yatırım tipi değiştiğinde
    tipSelect.addEventListener('change', function() {
        const tip = this.value;
        const terim = kodInput.value.trim();
        
        // Tip değiştiğinde fiyat alanını temizle 
        if (alisFiyatiInput) {
            alisFiyatiInput.value = '';
        }
        
        // Fon ve hisse için arama, altın ve döviz için doğrulama yap
        if ((tip === 'fon' || tip === 'hisse') && terim.length >= 2) {
            aramaYap(tip, terim);
        } else if ((tip === 'altin' || tip === 'doviz') && terim.length > 0) {
            dogrulaVeDoldur(tip, terim);
            kodSonuclar.style.display = 'none';
        } else {
            kodSonuclar.style.display = 'none';
        }
    });
    
    // Dökümanda herhangi bir yere tıklandığında
    document.addEventListener('click', function(e) {
        // Eğer tıklanan element kod input alanı veya sonuçlar listesi değilse
        if (!kodInput.contains(e.target) && !kodSonuclar.contains(e.target)) {
            // Sonuçları gizle
            kodSonuclar.style.display = 'none';
        }
    });
    
    // Klavye tuşları ile navigasyon
    kodInput.addEventListener('keydown', function(e) {
        const sonuclar = kodSonuclar.querySelectorAll('.list-group-item');
        
        if (sonuclar.length === 0 || kodSonuclar.style.display === 'none') {
            return;
        }
        
        // Enter tuşu
        if (e.key === 'Enter') {
            e.preventDefault();
            const aktifEleman = kodSonuclar.querySelector('.active');
            if (aktifEleman) {
                aktifEleman.click();
            }
        }
        
        // Aşağı ok tuşu
        else if (e.key === 'ArrowDown') {
            e.preventDefault();
            const aktifEleman = kodSonuclar.querySelector('.active');
            
            if (!aktifEleman) {
                // Aktif eleman yoksa, ilk elemanı aktif yap
                sonuclar[0].classList.add('active');
            } else {
                // Sonraki elemanı aktif yap
                const index = Array.from(sonuclar).indexOf(aktifEleman);
                aktifEleman.classList.remove('active');
                
                if (index < sonuclar.length - 1) {
                    sonuclar[index + 1].classList.add('active');
                } else {
                    sonuclar[0].classList.add('active');
                }
            }
        }
        
        // Yukarı ok tuşu
        else if (e.key === 'ArrowUp') {
            e.preventDefault();
            const aktifEleman = kodSonuclar.querySelector('.active');
            
            if (!aktifEleman) {
                // Aktif eleman yoksa, son elemanı aktif yap
                sonuclar[sonuclar.length - 1].classList.add('active');
            } else {
                // Önceki elemanı aktif yap
                const index = Array.from(sonuclar).indexOf(aktifEleman);
                aktifEleman.classList.remove('active');
                
                if (index > 0) {
                    sonuclar[index - 1].classList.add('active');
                } else {
                    sonuclar[sonuclar.length - 1].classList.add('active');
                }
            }
        }
        
        // Escape tuşu
        else if (e.key === 'Escape') {
            kodSonuclar.style.display = 'none';
        }
    });
}
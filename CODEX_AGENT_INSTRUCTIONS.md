# Finans Takip Uygulaması — AI Ajan Geliştirme Kılavuzu

> Bu dosya, VSCode + Codex (veya GitHub Copilot Agent) kullanarak uygulamayı geliştirmek için AI ajana verilecek bağlam ve talimat belgesidir.

---

## Bu Dosyayı Nasıl Kullanacaksın

**Görevleri sırayla, birer birer ver.** Hepsini aynı anda verme — Codex yarım bırakır veya çakışma yaratır.

Her görev için ajana şu formatta komut ver:

```
Bu dosyayı oku. GÖREV 1a'yı uygula.
```

**Her görevin sonunda mutlaka şunu ekle:**

```
Değişiklikleri tamamladıktan sonra `python app.py` ile uygulamanın 
ayağa kalkıp kalkmadığını kontrol et ve sonucu bildir.
```

**Önerilen sıra:** Görevleri numaralı sırayla işle (1 → 2 → 3...). Güvenlik görevleri (GÖREV 1) her şeyden önce gelir.

**Bir görev bozulursa:** "GÖREV X'i geri al, sadece o değişikliği sıfırla" diyebilirsin.

---

## GitHub Workflow — Branch ve Commit Kuralları

### Başlangıçta (Sadece İlk Seferinde)

İlk göreve başlamadan önce yeni bir branch oluştur:

```bash
git checkout -b feature/gelistirme
git push -u origin feature/gelistirme
```

Bundan sonra tüm çalışmalar bu branch üzerinde ilerleyecek. `main` branch'e dokunma.

### Her Görev Sonrası Commit Akışı

Her görev tamamlandığında ve `python app.py` kontrolü geçildikten sonra bana şunu sor:

```
GÖREV [X] tamamlandı. Aşağıdaki değişiklikler commit edilecek:
- [değiştirilen dosyalar listesi]
- [ne yapıldığının özeti]

Commit mesajı: "feat: GÖREV [X] - [kısa açıklama]"

Onaylıyor musun? (evet/hayır)
```

Onay verdikten sonra:

```bash
git add .
git commit -m "feat: GÖREV [X] - [kısa açıklama]"
git push origin feature/gelistirme
```

### Commit Mesajı Formatı

```
feat: GÖREV 1a - hardcoded credentials .env dosyasına taşındı
feat: GÖREV 1b - Flask-WTF ile CSRF koruması eklendi
feat: GÖREV 2a - hesapla_portfoy_ozeti() yardımcı fonksiyonu oluşturuldu
refactor: GÖREV 2b - yatirim gruplama fonksiyona çıkarıldı
fix: GÖREV 3c - BIST fiyat parse try-except ile sarıldı
```

### Geri Alma Durumu

Eğer bir görev sonrası uygulama bozulduysa ve geri almak istersen:

```
GÖREV [X] geri alınacak. Son commit revert edilsin mi? (evet/hayır)
```

Onay verdikten sonra:

```bash
git revert HEAD
git push origin feature/gelistirme
```

---

---

## Proje Bağlamı

Flask tabanlı, çok kullanıcılı bir yatırım portföy takip uygulaması. Kullanıcılar Türk piyasasındaki yatırımlarını (hisse, fon, altın, döviz) takip edebiliyor. SQLite veritabanı, Flask-Login ile auth, Bootstrap 5 + Plotly ile frontend.

**Dosya yapısı:**
```
app.py          → Ana Flask uygulaması (route'lar + veri çekme + PDF export)
auth.py         → Login/register/logout blueprint
models.py       → SQLAlchemy modelleri (User, Yatirim, FiyatGecmisi, vb.)
main.py         → PyInstaller masaüstü wrapper (Tkinter)
templates/      → Jinja2 HTML şablonları
static/         → CSS, JS dosyaları
instance/       → SQLite DB (finans_takip.db)
```

**Teknoloji stack:**
- Python 3.x, Flask 3.1.1, SQLAlchemy 2.0, Flask-Login, Flask-Migrate
- BeautifulSoup4 (web scraping), requests (HTTP)
- Plotly (grafikler), WeasyPrint (PDF export)
- Bootstrap 5.3 dark theme, vanilla JS

**Veri kaynakları:**
- TEFAS: Yatırım fonları (web scraping + JSON API fallback)
- İş Yatırım API: BIST hisseleri (non-resmi endpoint)
- Altinkaynak SOAP: Altın fiyatları
- TCMB XML: Döviz kurları (en stabil kaynak)

---

## Genel Talimatlar

- Kod değişikliklerinde mevcut Türkçe değişken/fonksiyon adlarını koru
- Yeni fonksiyonlar için Türkçe açıklayıcı docstring ekle
- Her değişiklik sonrası uygulamanın `python app.py` ile çalışabilir olduğundan emin ol
- SQLite uyumluluğunu koru (PostgreSQL'e geçiş planlanmıyor)
- Flask 2.x/3.x uyumlu syntax kullan (`.first_or_404()`, `db.session.get()` gibi yeni metodlar tercih edilmeli)

---

## GÖREV 1: Güvenlik Düzeltmeleri

### 1a. Hardcoded Kimlik Bilgileri → .env

**Problem:** `app.py` içinde açık yazılı credentials var:
```python
username = 'AltinkaynakWebServis'
password = 'AltinkaynakWebServis'
app.secret_key = os.environ.get("SESSION_SECRET", "finanstakip2025_default_secret_key")
```

**Yapılacaklar:**
1. Proje kök dizininde `.env` dosyası oluştur (`.gitignore`'a ekle):
```
SESSION_SECRET=<güçlü_rastgele_key>
ALTINKAYNAK_USERNAME=AltinkaynakWebServis
ALTINKAYNAK_PASSWORD=AltinkaynakWebServis
```
2. `python-dotenv` kütüphanesini `requirements.txt`'e ekle
3. `app.py` başına ekle:
```python
from dotenv import load_dotenv
load_dotenv()
```
4. `app.secret_key` satırını fallback olmadan yap:
```python
secret = os.environ.get("SESSION_SECRET")
if not secret:
    raise ValueError("SESSION_SECRET ortam değişkeni tanımlanmamış!")
app.secret_key = secret
```
5. `altin_verisi_cek()` içindeki hardcoded credentials'ı env'den oku

---

### 1b. CSRF Koruması

**Problem:** Form submission'larında CSRF token yok.

**Yapılacaklar:**
1. `requirements.txt`'e `Flask-WTF` ekle
2. `app.py`'ye ekle:
```python
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)
```
3. Tüm form'ların içine `{{ form.hidden_tag() }}` veya `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` ekle
4. AJAX POST isteklerinde `X-CSRFToken` header'ı gönder (`static/js/actions.js` güncellenmeli)

---

### 1c. Cookie Güvenliği

`app.py` içinde `SESSION_COOKIE_SECURE = False` var. Bunu ortama göre dinamik yap:
```python
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
```

---

## GÖREV 2: Kod Tekrarını Kaldır

### 2a. Portföy Hesaplama Yardımcı Fonksiyonu

**Problem:** `index()`, `yatirimlar()` ve `export_portfolio_pdf()` route'larında aynı hesaplama kodu üç kez yazılmış (~150 satır tekrar). Her üç yerde de şu hesaplamalar yapılıyor:
- `toplam_yatirim` ve `guncel_deger` toplamları
- `altin_doviz_alis` / `altin_doviz_satis` ayrı hesapları  
- `kategori_dagilim` sözlüğü
- `tip_ozet` sözlüğü

**Yapılacaklar:**

`app.py` içine (route'lardan önce) şu fonksiyonu ekle:
```python
def hesapla_portfoy_ozeti(yatirimlar):
    """
    Verilen yatırım listesi için portföy özet istatistiklerini hesaplar.
    
    Returns:
        dict: toplam_yatirim, guncel_deger, kar_zarar, kar_zarar_yuzde,
              kategori_dagilim, tip_ozet, altin_doviz_alis, altin_doviz_satis
    """
    # ... hesaplama mantığı buraya taşınacak
    pass
```

Sonra `index()`, `yatirimlar()` ve `export_portfolio_pdf()` fonksiyonlarını bu yardımcıyı kullanacak şekilde refactor et.

---

### 2b. Yatırım Gruplama Yardımcı Fonksiyonu

`index()` ve `yatirimlar()` içindeki `yatirim_gruplari_liste` oluşturma kodu (~80 satır) da tekrarlıyor. Bunu da ayrı bir `grupla_yatirimlar(yatirimlar)` fonksiyonuna çıkar.

---

### 2c. YatirimPerformans Class'ını Taşı

`index()` fonksiyonu içinde tanımlı olan bu class'ı dosyanın üstüne (import'lardan sonra, route'lardan önce) taşı:
```python
class YatirimPerformans:
    def __init__(self, kod, isim, tip, kar_zarar, getiri, kalemler):
        ...
```

---

## GÖREV 3: Veri Çekme İyileştirmeleri

### 3a. In-Memory Cache Ekle

**Problem:** Her fiyat güncelleme isteği canlı HTTP isteği yapıyor. Aynı hisse 5 kez portföyde varsa aynı endpoint'e 5 istek atılıyor.

**Yapılacaklar:**

`app.py`'ye basit TTL cache ekle:
```python
import time

_fiyat_cache = {}  # {kod: (fiyat_dict, timestamp)}
CACHE_TTL = 900  # 15 dakika

def cache_den_al(kod):
    if kod in _fiyat_cache:
        veri, ts = _fiyat_cache[kod]
        if time.time() - ts < CACHE_TTL:
            return veri
    return None

def cache_kaydet(kod, veri):
    _fiyat_cache[kod] = (veri, time.time())
```

Her veri çekme fonksiyonunun başına cache kontrolü, sonuna cache kaydetme ekle.

---

### 3b. Toplu Fiyat Güncellemeyi Paralel Yap

**Problem:** `toplu_fiyat_guncelle()` sıralı çalışıyor, çok yavaş.

**Yapılacaklar:**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

@app.route('/toplu_fiyat_guncelle', methods=['POST'])
@login_required
def toplu_fiyat_guncelle():
    yatirimlar = Yatirim.query.filter_by(user_id=current_user.id).all()
    
    # Benzersiz (kod, tip) çiftlerini bul - aynı varlığı bir kez güncelle
    benzersiz = {}
    for y in yatirimlar:
        key = f"{y.kod}_{y.tip}"
        if key not in benzersiz:
            benzersiz[key] = y.id  # Grubun ilk yatırım ID'si
    
    basarili_count = 0
    hata_count = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fiyat_guncelle, yid): yid 
                   for yid in benzersiz.values()}
        for future in as_completed(futures):
            basarili, _ = future.result()
            if basarili:
                basarili_count += 1
            else:
                hata_count += 1
    
    # ... flash mesajları
```

**Dikkat:** `db.session` thread-safe değil. `fiyat_guncelle()` içindeki DB operasyonlarını thread-safe hale getir veya sonuçları ana thread'de kaydet.

---

### 3c. BIST Fiyat Parse Güvenliği

`bist_hisse_verisi_cek()` içindeki `Decimal(fiyat_text)` satırını try-except ile sar:

```python
try:
    fiyat = Decimal(str(hisse_bilgisi["last"]).replace(',', '.'))
except (InvalidOperation, ValueError, KeyError) as e:
    app.logger.error(f"BIST fiyat parse hatası ({hisse_kodu_upper}): {e}")
    return None
```

---

### 3d. HTTP Session'ı Yeniden Kullan

Her veri çekme fonksiyonu yeni `requests.get()` açıyor. Uygulama seviyesinde bir session oluştur:

```python
# app.py global düzeyde
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def http_session_olustur():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

http_session = http_session_olustur()
```

Tüm `requests.get()` / `requests.post()` çağrılarını `http_session.get()` / `http_session.post()` ile değiştir.

---

## GÖREV 4: Veritabanı Optimizasyonu

### 4a. Index Ekle

`models.py` içinde sık sorgulanan sütunlara index ekle:

```python
class Yatirim(db.Model):
    # Mevcut sütunlar...
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False,
                        index=True)  # nullable=True → False yap, index ekle
    kod = db.Column(db.String(30), nullable=False, index=True)
    
class FiyatGecmisi(db.Model):
    yatirim_id = db.Column(db.Integer, db.ForeignKey('yatirim.id'), 
                           nullable=False, index=True)
    tarih = db.Column(db.DateTime, nullable=False, index=True)
```

Migration çalıştır: `flask db migrate -m "add_indexes" && flask db upgrade`

### 4b. Yatirim.user_id nullable=True → False

Migration ile mevcut NULL kayıtları temizle, sonra constraint'i sıkılaştır.

---

## GÖREV 5: Gerçek Performans Grafiği

**Problem:** `index()` içindeki 30 günlük grafik sahte veri kullanıyor:
```python
values = [guncel_deger_float * (1 + (i-15) * 0.001) for i in range(30)]  # SAHTE!
```

**Yapılacaklar:**

`FiyatGecmisi` tablosundan gerçek veriyi çek:

```python
from datetime import datetime, timedelta
from sqlalchemy import func

def portfoy_gecmis_grafigi(user_id, gun_sayisi=30):
    """Kullanıcının son N günlük portföy değer geçmişini döndürür."""
    baslangic = datetime.now() - timedelta(days=gun_sayisi)
    
    # Her gün için son fiyatları al
    gunluk_degerler = {}
    
    yatirimlar = Yatirim.query.filter_by(user_id=user_id).all()
    for yatirim in yatirimlar:
        gecmis = FiyatGecmisi.query.filter(
            FiyatGecmisi.yatirim_id == yatirim.id,
            FiyatGecmisi.tarih >= baslangic
        ).order_by(FiyatGecmisi.tarih).all()
        
        for kayit in gecmis:
            gun = kayit.tarih.strftime('%Y-%m-%d')
            if gun not in gunluk_degerler:
                gunluk_degerler[gun] = Decimal('0')
            gunluk_degerler[gun] += kayit.fiyat * yatirim.miktar
    
    return sorted(gunluk_degerler.items())
```

`index()` route'unda `performans_grafik_html` oluşturma kısmını bu fonksiyonla güncelle.

---

## GÖREV 6: Logging İyileştirmesi

Tüm `print()` ifadelerini `logging` çağrıları ile değiştir:

```python
# Eski
print(f"Yatırım: {y.kod}, Güncel Fiyat: {y.guncel_fiyat}")

# Yeni
app.logger.debug(f"Yatırım hesaplandı: {y.kod}, güncel_fiyat={y.guncel_fiyat}")
```

`logging` seviyelerini doğru kullan:
- `DEBUG`: Hesaplama detayları, veri parse adımları
- `INFO`: Başarılı veri çekme, kullanıcı işlemleri
- `WARNING`: Veri bulunamadı, fallback kullanıldı
- `ERROR`: Exception'lar, kritik hatalar

---

## GÖREV 7: Frontend İyileştirmeleri

### 7a. Toplu Güncelleme Progress Göstergesi

`templates/yatirimlar.html` veya `templates/index.html` içinde toplu güncelleme butonu için loading state ekle:

```javascript
document.getElementById('toplu-guncelle-btn').addEventListener('click', function() {
    this.disabled = true;
    this.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Güncelleniyor...';
    // Form submit devam eder
});
```

### 7b. Hata Mesajı Dili Standardizasyonu

`app.py` içindeki tüm `flash()` mesajlarını Türkçe yap. İngilizce olanları tespit et ve çevir.

---

## Bilinen Kısıtlamalar / Dikkat Edilecekler

1. **PyInstaller uyumluluğu:** `resource_path()` ve `get_writable_db_path()` fonksiyonlarına dokunma — masaüstü paketleme için gerekli.
2. **Flask-Migrate:** Model değişikliklerinden sonra mutlaka `flask db migrate && flask db upgrade` çalıştır.
3. **Decimal kullanımı:** Finansal hesaplamalarda `float` yerine `Decimal` kullan — bu doğru bir pratik, korumaya devam et.
4. **Thread safety:** `toplu_fiyat_guncelle` paralel hale getirilirken SQLAlchemy session thread-safety'sine dikkat et. Her thread için ayrı session context kullan.
5. **TEFAS scraping:** Web scraping kırılgandır. Değişiklik yaptıktan sonra mutlaka manuel test et.

---

## Test Adımları

Her görev tamamlandıktan sonra şu senaryoları test et:

```bash
# 1. Uygulama başlatma
python app.py

# 2. Kayıt ve giriş
# → /auth/register ile yeni kullanıcı oluştur
# → /auth/login ile giriş yap

# 3. Yatırım ekleme (her tip için)
# → Fon: AK1 (veya geçerli bir TEFAS fon kodu)
# → Hisse: THYAO
# → Altın: GA (Gram Altın)
# → Döviz: USD

# 4. Fiyat güncelleme
# → Tek yatırım güncelleme
# → Toplu güncelleme

# 5. PDF export
# → /export_portfolio_pdf

# 6. Güvenlik testi
# → Başka kullanıcının yatırımına erişmeye çalış
# → SESSION_SECRET olmadan uygulamayı başlatmaya çalış
```

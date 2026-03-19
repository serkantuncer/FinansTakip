# FinansTakip — Düzeltme ve Eksik Tamamlama Planı
> AI Ajanı için Aşamalı, Onaylı İlerleme Kılavuzu  
> Her aşama tamamlandığında ✅ işaretle ve kullanıcı onayını bekle.

---

## Kurallar

- Her aşamayı tamamladıktan sonra **DUR** ve kullanıcıdan onay iste.
- Onay gelmeden bir sonraki aşamaya geçme.
- Her aşama sonunda **Kontrol Listesi**'ndeki tüm maddeleri tek tek doğrula.
- Bir dosyayı değiştirmeden önce mevcut içeriğini göster, değişiklik sonrası yeni halini göster.
- Hata oluştuysa geri al ve kullanıcıya bildir.

---

## AŞAMA 1 — Kritik Güvenlik Açıkları

**Risk:** Yüksek | **Tahmini Süre:** 30 dk

### 1.1 — Varsayılan Admin Hesabı Otomatik Oluşturma

**Sorun:** `app.py` içindeki `migrate_existing_data()` fonksiyonu `admin/admin123` şifresiyle otomatik admin hesabı oluşturuyor. Production ortamında bu hesap herkes tarafından kullanılabilir.

**Yapılacak:**
- `app.py` → `migrate_existing_data()` fonksiyonunda `default_user` oluşturan bloğu kaldır.
- Orphaned yatırım varsa kullanıcıya `flash` mesajıyla uyar, otomatik atama yapma.

**Hedef kod (kaldırılacak blok):**
```python
# BU BLOĞU KALDIR:
default_user = User.query.filter_by(username='admin').first()
if not default_user:
    default_user = User(
        username='admin',
        email='admin@example.com',
        password_hash=generate_password_hash('admin123')
    )
    db.session.add(default_user)
    db.session.commit()
    app.logger.info("Varsayılan admin kullanıcısı oluşturuldu (admin/admin123)")
```

**Yerine eklenecek:**
```python
app.logger.warning(
    f"{len(orphaned_investments)} adet kullanıcısız yatırım kaydı bulundu. "
    "Lütfen veritabanını manuel olarak düzeltin."
)
```

### 1.2 — SSL Bypass Production'da Engelleme

**Sorun:** `bist_hisse_verisi_cek()` içinde SSL hatası alınca `verify=False` ile tekrar deneniyor. Production'da bu kabul edilemez.

**Yapılacak:**
- `app.py` → `bist_hisse_verisi_cek()` içinde `FLASK_ENV == production` kontrolü zaten var ama SSL bypass bloğu production'da `return None` yapıyor, development'ta da uyarı loglanıyor — bu davranış doğru. **Sadece** `urllib3.disable_warnings()` çağrısını development'a bile koyma, loglama ile sınırla.

**Değiştirilecek:**
```python
# ESKİ — global warning disable:
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# YENİ — sadece bu session için:
# (disable_warnings satırını tamamen kaldır, log satırı yeterli)
```

### 1.3 — Redundant flask_wtf Klasörü

**Sorun:** Proje içinde `flask_wtf/` klasörü elle kopyalanmış. `requirements.txt`'te `Flask-WTF` zaten var. Bu iki kaynak çakışabilir ve güncelleme almayı engeller.

**Yapılacak:**
- `finanstakip/flask_wtf/` klasörünü ve `finanstakip/flask_wtf/__pycache__/` klasörünü sil.
- Uygulamayı test et — `Flask-WTF` paketten gelecek.

### 1.4 — dotenv.py İsim Çakışması

**Sorun:** `finanstakip/dotenv.py` adlı dosya, `python-dotenv` paketiyle isim çakışması yaratabilir. `from dotenv import load_dotenv` satırı bu dosyayı import edebilir.

**Yapılacak:**
- `dotenv.py` dosyasının içeriğini kontrol et.
- Eğer gerçek içeriği yoksa (boş veya test dosyasıysa) sil.
- Eğer içerik varsa `utils_dotenv.py` veya `env_helper.py` olarak yeniden adlandır ve referansları güncelle.

---

### ✅ Aşama 1 Kontrol Listesi

Aşağıdaki her maddeyi tek tek doğrula, sonra kullanıcıya göster:

- [ ] `migrate_existing_data()` içinde `admin/admin123` oluşturan kod yok
- [ ] `urllib3.disable_warnings()` çağrısı kaldırıldı
- [ ] `finanstakip/flask_wtf/` klasörü silindi
- [ ] `from flask_wtf.csrf import CSRFProtect` hâlâ çalışıyor (uygulama başlıyor)
- [ ] `dotenv.py` durumu netleştirildi
- [ ] `from dotenv import load_dotenv` doğru paketten geliyor

**Kullanıcıya sor:** "Aşama 1 tamamlandı. Devam edeyim mi?"

---

## AŞAMA 2 — Eksik Template Dosyaları

**Risk:** Orta (Çalışma Zamanı 500 Hatası) | **Tahmini Süre:** 45 dk

### 2.1 — Eksik Template'lerin Tespiti

`app.py`'de referans verilen ama `templates/` klasöründe olmayan dosyalar:

| Route | Beklenen Template | Durum |
|---|---|---|
| `share_portfolio()` | `share_portfolio.html` | ❌ Eksik |
| `view_shared_portfolio()` | `view_shared_portfolio.html` | ❌ Eksik |
| `my_follows()` | `my_follows.html` | ❌ Eksik |

### 2.2 — share_portfolio.html Oluştur

`base.html`'i extend eden, kullanıcının portföylerini listeleyen ve yeni paylaşım formu içeren bir template. Gerekli değişkenler: `portfolios`, `yatirimlar`.

**Minimum içerik:**
- Mevcut paylaşılan portföylerin listesi
- Yeni portföy oluşturma formu (başlık, açıklama, `is_public` toggle, yatırım seçimi)
- CSRF token: `{{ form.hidden_tag() }}` veya `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`

### 2.3 — view_shared_portfolio.html Oluştur

`portfoy` ve `yatirimlar` değişkenlerini kullanan, paylaşılan portföyün detaylarını gösteren template.

**Minimum içerik:**
- Portföy başlığı, açıklaması, sahibi
- Yatırım listesi tablosu (tip, kod, alış tarihi, miktar)
- Takip et butonu (`/portfolio/follow/<id>`)

### 2.4 — my_follows.html Oluştur

`takip_edilenler` değişkenini kullanan template.

**Minimum içerik:**
- Takip edilen portföylerin listesi
- Her portföy için görüntüle linki

### 2.5 — PaylasilanPortfoy Migration Eksikliği

**Sorun:** `PaylasilanPortfoy`, `PaylasilanYatirim`, `PortfoyTakip` modelleri var ama hiçbir migration versiyonunda yok. `db.create_all()` oluşturuyor ama migration history tutarsız kalıyor.

**Yapılacak:**
```bash
flask db migrate -m "paylasim_tablolari_ekle"
flask db upgrade
```
Oluşan migration dosyasını `migrations/versions/` altında kontrol et.

---

### ✅ Aşama 2 Kontrol Listesi

- [ ] `share_portfolio.html` oluşturuldu ve `base.html`'i extend ediyor
- [ ] `view_shared_portfolio.html` oluşturuldu
- [ ] `my_follows.html` oluşturuldu
- [ ] Tüm template'lerde CSRF token var
- [ ] `/portfolio/share` route'u 500 vermiyor
- [ ] `/community` route'u 500 vermiyor
- [ ] `/my-follows` route'u 500 vermiyor
- [ ] Migration dosyası oluşturuldu ve `flask db upgrade` çalıştırıldı

**Kullanıcıya sor:** "Aşama 2 tamamlandı. Devam edeyim mi?"

---

## AŞAMA 3 — Veri Doğrulama Eksikleri

**Risk:** Orta | **Tahmini Süre:** 30 dk

### 3.1 — Yatırım Ekleme Form Doğrulaması

**Sorun:** `yatirim_ekle` route'unda negatif/sıfır değer kontrolü yok.

**Yapılacak — `app.py` → `yatirim_ekle()` route'unda `try` bloğuna ekle:**

```python
# Fiyat ve miktar doğrulaması
if alis_fiyati <= 0:
    flash('Alış fiyatı sıfırdan büyük olmalıdır.', 'danger')
    return redirect(url_for('yatirimlar'))

if miktar <= 0:
    flash('Miktar sıfırdan büyük olmalıdır.', 'danger')
    return redirect(url_for('yatirimlar'))

# Tarih kontrolü — gelecek tarih uyarısı
if alis_tarihi.date() > datetime.now().date():
    flash('Alış tarihi bugünden ileri olamaz.', 'warning')
    return redirect(url_for('yatirimlar'))
```

### 3.2 — Satış Tarihi Doğrulaması

**Sorun:** `satis_yap()` route'unda satış tarihi alış tarihinden önce olabilir.

**Yapılacak — `app.py` → `satis_yap()` içine ekle:**

```python
# Satış tarihi kontrolü
if satis_tarihi.date() < yatirim.alis_tarihi.date():
    flash(
        f'Satış tarihi ({satis_tarihi.strftime("%d.%m.%Y")}), '
        f'alış tarihinden ({yatirim.alis_tarihi.strftime("%d.%m.%Y")}) önce olamaz.',
        'danger'
    )
    return redirect(url_for('yatirimlar'))
```

### 3.3 — Satılmış Yatırımları Portföy Toplamından Çıkar

**Sorun:** `durum='tamamen_satildi'` olan yatırımlar ana sayfada `Yatirim.query.filter_by(user_id=current_user.id)` ile çekiliyor — toplamı bozuyor.

**Yapılacak — `app.py` → `index()` ve `yatirimlar()` route'larında sorguyu güncelle:**

```python
# ESKİ:
yatirimlar = Yatirim.query.filter_by(user_id=current_user.id).order_by(...)

# YENİ — sadece aktif yatırımlar özette gösterilir:
yatirimlar_aktif = Yatirim.query.filter_by(
    user_id=current_user.id,
    durum='aktif'
).order_by(Yatirim.alis_tarihi.desc()).all()
```

> **Not:** `yatirimlar.html`'de kullanıcı tamamen satılmış kayıtları da görmek isteyebilir. Bunun için filtre seçeneği (`?durum=hepsi`) eklenebilir.

### 3.4 — Stopaj Oranı Açık Uçlu Çakışma Kontrolü

**Sorun:** `stopaj_orani_donem_cakisiyor()` fonksiyonu `donem_bitis=None` (açık uçlu) olan mevcut kayıtla çakışmayı tam tespit edemiyor.

**Yapılacak — `app.py` → `stopaj_orani_donem_cakisiyor()` fonksiyonunu güncelle:**

```python
def stopaj_orani_donem_cakisiyor(fon_grubu, donem_baslangic, donem_bitis=None, elde_tutma_gun=None):
    from sqlalchemy import or_

    adaylar = StopajOrani.query.filter(
        StopajOrani.fon_grubu == fon_grubu,
        StopajOrani.elde_tutma_gun == elde_tutma_gun  # None == None SQLAlchemy'de çalışmaz!
        if elde_tutma_gun is not None
        else StopajOrani.elde_tutma_gun.is_(None)
    ).all()

    yeni_bitis = donem_bitis or date.max
    for aday in adaylar:
        aday_bitis = aday.donem_bitis or date.max
        if donem_baslangic <= aday_bitis and aday.donem_baslangic <= yeni_bitis:
            return aday
    return None
```

---

### ✅ Aşama 3 Kontrol Listesi

- [ ] Negatif alış fiyatı girince hata mesajı görünüyor
- [ ] Sıfır miktar girince hata mesajı görünüyor
- [ ] Gelecek tarihli alış için uyarı gösteriliyor
- [ ] Alış tarihinden önce satış tarihi girince hata mesajı görünüyor
- [ ] Ana sayfa portföy toplamı artık `durum='tamamen_satildi'` kayıtlarını içermiyor
- [ ] Stopaj oranı açık uçlu çakışma kontrolü düzgün çalışıyor

**Kullanıcıya sor:** "Aşama 3 tamamlandı. Devam edeyim mi?"

---

## AŞAMA 4 — Eksik Fonksiyonellik

**Risk:** Orta | **Tahmini Süre:** 60 dk

### 4.1 — Otomatik Fiyat Güncelleme (APScheduler)

**Sorun:** Fiyat geçmişi sadece kullanıcı manuel güncelleme yaptığında kaydediliyor. Portföy performans grafiği bu yüzden büyük ihtimalle boş.

**Yapılacak — `requirements.txt`'e ekle:**
```
APScheduler==3.10.4
```

**`app.py`'e ekle (import bloğunun altına):**
```python
from apscheduler.schedulers.background import BackgroundScheduler
```

**`app.py`'e fonksiyon olarak ekle:**
```python
def otomatik_fiyat_guncelle():
    """Her 15 dakikada bir tüm aktif yatırımların fiyatlarını günceller."""
    with app.app_context():
        try:
            aktif_yatirimlar = Yatirim.query.filter_by(durum='aktif').all()
            gruplar = {}
            for y in aktif_yatirimlar:
                key = f"{y.tip}:{y.kod.upper()}"
                if key not in gruplar:
                    gruplar[key] = {'tip': y.tip, 'kod': y.kod.upper(), 'yatirimlar': []}
                gruplar[key]['yatirimlar'].append(y)

            for key, grup in gruplar.items():
                basarili, veri = fiyat_verisi_cek_by_tip_kod(grup['tip'], grup['kod'])
                if not basarili or not veri:
                    continue
                for y in grup['yatirimlar']:
                    y.guncel_fiyat = veri['guncel_fiyat']
                    y.son_guncelleme = veri['tarih']
                    if y.tip in ['altin', 'doviz']:
                        if veri.get('alis_fiyat'):
                            y.guncel_alis_fiyat = veri['alis_fiyat']
                        if veri.get('satis_fiyat'):
                            y.guncel_satis_fiyat = veri['satis_fiyat']
                    fiyat_gecmisi = FiyatGecmisi(
                        yatirim_id=y.id,
                        tarih=veri['tarih'],
                        fiyat=veri['guncel_fiyat'],
                        user_id=y.user_id
                    )
                    db.session.add(fiyat_gecmisi)
            db.session.commit()
            app.logger.info(f"Otomatik fiyat güncelleme tamamlandı: {len(gruplar)} varlık")
        except Exception as e:
            app.logger.error(f"Otomatik fiyat güncelleme hatası: {e}", exc_info=True)
```

**`init_database()` çağrısının altına ekle:**
```python
# Scheduler başlat (sadece bir kez)
if not app.config.get('SCHEDULER_RUNNING'):
    scheduler = BackgroundScheduler()
    scheduler.add_job(otomatik_fiyat_guncelle, 'interval', minutes=15, id='fiyat_guncelle')
    scheduler.start()
    app.config['SCHEDULER_RUNNING'] = True
    import atexit
    atexit.register(lambda: scheduler.shutdown())
```

> **Uyarı:** Multi-worker Gunicorn'da her worker ayrı scheduler başlatır. Production'da bunu sadece tek bir worker'da çalıştırmak için `SCHEDULER_ENABLED` ortam değişkeni kontrolü ekle.

### 4.2 — Altın İlk Fiyat Çekimi

**Sorun:** Altın eklenirken `fiyat_guncelle` atlanıyor, anlık fiyat bir sonraki otomatik güncellemeye kadar gelmiyor.

**Yapılacak — `yatirim_ekle()` içindeki altın bloğunu güncelle:**

```python
# ESKİ:
if tip != 'altin':
    basarili, mesaj = fiyat_guncelle(yatirim.id)

# YENİ — altın da dahil fiyat çek, ama timeout'ta sessizce devam et:
try:
    basarili, mesaj = fiyat_guncelle(yatirim.id)
    if not basarili:
        app.logger.warning(f"İlk fiyat güncelleme başarısız ({tip}:{kod}): {mesaj}")
except Exception as e:
    app.logger.warning(f"İlk fiyat çekme hatası ({tip}:{kod}): {e}")
```

### 4.3 — Alış Komisyonu Formu

**Sorun:** `Yatirim.alis_komisyon` modelde var ama hiçbir formda kullanılmıyor.

**Yapılacak:**

**`templates/yatirimlar.html`** → yatırım ekleme formuna ekle:
```html
<div class="mb-3">
  <label class="form-label">Alış Komisyonu (₺)</label>
  <input type="number" class="form-control" name="alis_komisyon"
         step="0.01" min="0" value="0" placeholder="0.00">
</div>
```

**`app.py` → `yatirim_ekle()` içine ekle:**
```python
alis_komisyon_str = request.form.get('alis_komisyon', '0')
alis_komisyon = Decimal(alis_komisyon_str.replace(',', '.')) if alis_komisyon_str else Decimal('0')

yatirim = Yatirim(
    ...
    alis_komisyon=alis_komisyon,
    ...
)
```

---

### ✅ Aşama 4 Kontrol Listesi

- [ ] `APScheduler` requirements.txt'e eklendi
- [ ] `otomatik_fiyat_guncelle()` fonksiyonu var ve app context içinde çalışıyor
- [ ] Scheduler 15 dakikada bir çalışıyor (log çıktısı doğruluyor)
- [ ] Uygulama kapanışında `scheduler.shutdown()` çağrılıyor
- [ ] Altın eklenirken anlık fiyat çekimi deneniyor, hata olursa sessizce devam ediyor
- [ ] Alış komisyonu formu var ve kaydediliyor
- [ ] Portföy performans grafiği veri görüntülüyor (en az 1 fiyat geçmişi kaydı oluştu)

**Kullanıcıya sor:** "Aşama 4 tamamlandı. Devam edeyim mi?"

---

## AŞAMA 5 — Performans İyileştirmeleri

**Risk:** Düşük | **Tahmini Süre:** 45 dk

### 5.1 — Ana Sayfa N+1 Query Sorunu

**Sorun:** `index()` route'unda şu üç ağır işlem aynı request'te sıralı çalışıyor:
- `hesapla_portfoy_ozeti()` — tüm yatırımları döner
- `grupla_yatirimlar()` — aynı listeyi tekrar işler
- `portfoy_gecmis_grafigi()` — `FiyatGecmisi` tablosunu tüm yatırım ID'leri için çeker

**Yapılacak:**

1. `portfoy_gecmis_grafigi()` içindeki `FiyatGecmisi` sorgusuna `limit` ekle:

```python
gecmis_kayitlar = (
    FiyatGecmisi.query
    .filter(
        FiyatGecmisi.yatirim_id.in_(yatirim_idleri),
        FiyatGecmisi.tarih >= baslangic
    )
    .order_by(FiyatGecmisi.tarih.asc())
    .limit(5000)  # Makul bir üst sınır
    .all()
)
```

2. `index()` route'unda `yatirimlar` sorgusuna `eager loading` ekle:

```python
from sqlalchemy.orm import joinedload

yatirimlar = Yatirim.query.filter_by(
    user_id=current_user.id,
    durum='aktif'
).order_by(Yatirim.alis_tarihi.desc()).all()
```

### 5.2 — In-Memory Cache'i Geliştir

**Sorun:** Mevcut `_fiyat_cache` sözlüğü multi-process deployment'ta paylaşılmıyor.

**Şimdilik yapılacak (basit iyileştirme):**

`cache_kaydet()` fonksiyonunda maksimum cache boyutu sınırla:

```python
MAX_CACHE_SIZE = 500

def cache_kaydet(varlik_tipi, kod, veri):
    if not veri:
        return
    if len(_fiyat_cache) >= MAX_CACHE_SIZE:
        # En eski kaydı sil
        oldest_key = min(_fiyat_cache, key=lambda k: _fiyat_cache[k][1])
        _fiyat_cache.pop(oldest_key, None)
    _fiyat_cache[_cache_key(varlik_tipi, kod)] = (veri, time.time())
```

> **Not:** Production multi-process deployment için Redis veya Flask-Caching önerilebilir — bu ayrı bir aşama olarak planlanabilir.

### 5.3 — Logging Seviyesini Düzenle

**Sorun:** `logging.basicConfig(level=logging.DEBUG)` production'da çok fazla log üretiyor.

**Yapılacak:**

```python
# ESKİ:
logging.basicConfig(level=logging.DEBUG)

# YENİ:
log_level = logging.DEBUG if flask_env != 'production' else logging.WARNING
logging.basicConfig(
    level=log_level,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
```

---

### ✅ Aşama 5 Kontrol Listesi

- [ ] `portfoy_gecmis_grafigi()` içinde `limit(5000)` eklendi
- [ ] Cache boyutu `MAX_CACHE_SIZE = 500` ile sınırlandırıldı
- [ ] Logging seviyesi ortama göre ayarlanıyor
- [ ] Ana sayfa yükleme süresi belirgin şekilde düşmedi ise loglar incelendi

**Kullanıcıya sor:** "Aşama 5 tamamlandı. Devam edeyim mi?"

---

## AŞAMA 6 — Son Kontrol ve Temizlik

**Risk:** Düşük | **Tahmini Süre:** 20 dk

### 6.1 — .env Güvenliği

**Yapılacak:**

`.gitignore` dosyasında `.env` satırının olduğunu doğrula. Yoksa ekle:
```
.env
*.db
instance/
__pycache__/
.venv/
```

### 6.2 — requirements.txt Temizliği

Proje artık masaüstü EXE için kullanılmıyorsa (veya web ve desktop sürümleri ayrılacaksa) gereksiz paketleri `requirements-desktop.txt`'e taşı:

| Paket | Web için gerekli? |
|---|---|
| `ttkbootstrap` | ❌ Sadece desktop |
| `pystray` | ❌ Sadece desktop |
| `psutil` | ❌ Sadece desktop |
| `weasyprint` | ✅ PDF export için gerekli |
| `pillow` | ⚠️ WeasyPrint bağımlılığı, gerekli |

**Yapılacak:**
- `requirements.txt`'ten `ttkbootstrap`, `pystray`, `psutil` kaldır
- `requirements-desktop.txt` oluştur ve bu paketleri oraya ekle

### 6.3 — Tam Fonksiyon Testi

Tüm değişiklikler tamamlandıktan sonra şu akışları test et:

```
✅ Kayıt ol → Giriş yap
✅ Fon ekle (geçerli kod: örn. AFT)
✅ Hisse ekle (örn. THYAO)
✅ Altın ekle (GA)
✅ Döviz ekle (USD)
✅ Fiyat güncelle (tek)
✅ Toplu fiyat güncelle
✅ Satış yap (tam satış)
✅ Satış yap (kısmi satış)
✅ Satışlar sayfası görünüyor
✅ Stopaj simülasyonu çalışıyor
✅ PDF export çalışıyor
✅ Negatif değer girince hata alınıyor
✅ Portföy performans grafiği veri gösteriyor
```

---

### ✅ Aşama 6 Kontrol Listesi

- [ ] `.gitignore`'da `.env` ve `*.db` var
- [ ] `requirements.txt` temizlendi
- [ ] `requirements-desktop.txt` oluşturuldu
- [ ] Tüm test akışları başarıyla geçti
- [ ] Uygulama `python app.py` ile (geliştirme modunda) hatasız başlıyor

**Kullanıcıya bildir:** "Tüm aşamalar tamamlandı. Özet rapor:"

---

## 📋 Özet — Tamamlanan Değişiklikler

| # | Başlık | Dosya | Durum |
|---|---|---|---|
| 1.1 | Admin otomatik oluşturma kaldırıldı | `app.py` | ⬜ |
| 1.2 | SSL bypass uyarısı kaldırıldı | `app.py` | ⬜ |
| 1.3 | Redundant flask_wtf klasörü silindi | Klasör | ⬜ |
| 1.4 | dotenv.py isim çakışması çözüldü | `dotenv.py` | ⬜ |
| 2.1 | share_portfolio.html oluşturuldu | `templates/` | ⬜ |
| 2.2 | view_shared_portfolio.html oluşturuldu | `templates/` | ⬜ |
| 2.3 | my_follows.html oluşturuldu | `templates/` | ⬜ |
| 2.4 | Paylaşım migration oluşturuldu | `migrations/` | ⬜ |
| 3.1 | Form doğrulama eklendi | `app.py` | ⬜ |
| 3.2 | Satış tarihi doğrulaması eklendi | `app.py` | ⬜ |
| 3.3 | Satılmış yatırımlar filtrelendi | `app.py` | ⬜ |
| 3.4 | Stopaj çakışma kontrolü düzeltildi | `app.py` | ⬜ |
| 4.1 | APScheduler otomatik güncelleme | `app.py` | ⬜ |
| 4.2 | Altın ilk fiyat çekimi düzeltildi | `app.py` | ⬜ |
| 4.3 | Alış komisyonu formu eklendi | `app.py` + template | ⬜ |
| 5.1 | Query limiti eklendi | `app.py` | ⬜ |
| 5.2 | Cache boyutu sınırlandırıldı | `app.py` | ⬜ |
| 5.3 | Logging seviyesi düzenlendi | `app.py` | ⬜ |
| 6.1 | .gitignore güncellendi | `.gitignore` | ⬜ |
| 6.2 | requirements.txt temizlendi | `requirements.txt` | ⬜ |

---

*Son güncelleme: Bu belge FinansTakip v1.x için hazırlanmıştır.*

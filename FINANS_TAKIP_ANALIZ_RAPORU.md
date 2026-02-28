# Finans Takip Uygulaması — Kod Analiz Raporu

> Tarih: 28.02.2026  
> Analiz Kapsamı: `app.py`, `models.py`, `auth.py`, `main.py`, `templates/`, `static/`

---

## 1. Genel Değerlendirme

Uygulama Flask tabanlı, çok kullanıcılı, SQLite veritabanı kullanan bir portföy takip sistemi. PyInstaller ile masaüstü uygulama olarak da paketlenebilmekte. Temel yapı sağlam olmakla birlikte, **veri çekme katmanı**, **mimari tekrarlar**, **güvenlik eksiklikleri** ve **performans sorunları** dikkat gerektiriyor.

---

## 2. Veri Çekme Yöntemi Analizi

### 2.1 TEFAS (Fon Verisi) — `tefas_fon_verisi_cek()`

**Sorunlar:**
- **Web scraping ile HTML parse etme** — TEFAS sayfa yapısını değiştirirse tüm fon veri çekimi durur. Çok kırılgan.
- Fiyat için son çare olarak "TL içeren tüm span'ları tara" mantığı var → **yanlış veri çekme riski yüksek**.
- `tefas_alternatif_arama()` fallback fonksiyonu eski bir API endpoint kullanıyor, bu endpoint aktif mi belirsiz.
- `User-Agent` sabit ve eski Chrome versiyonuna ait → ban riski.

**Öneri:**
- TEFAS'ın resmi/non-resmi JSON API'sini doğrudan kullanın: `https://www.tefas.gov.tr/api/DB/BindHistoryInfo` endpoint'i daha stabil. Alternatif olarak `tefasdata` Python kütüphanesi değerlendirilebilir.

### 2.2 BIST Hisse — `bist_hisse_verisi_cek()`

**Sorunlar:**
- İş Yatırım özel endpoint'i kullanılıyor (`isyatirim.com.tr/...Data.aspx/OneEndeks`). Bu endpoint belgelenmemiş ve herhangi bir zamanda değişebilir/kapanabilir.
- Hata durumunda `None` dönüyor, retry mekanizması yok.
- Fiyat doğrudan `Decimal(fiyat_text)` ile parse ediliyor — virgüllü formatta gelirse `InvalidOperation` fırlatır, try-catch yok.

**Öneri:**
- Yahoo Finance (`yfinance` kütüphanesi) veya investing.com API'si daha stabil alternatifler.
- Fiyat parse işlemi try-except ile sarılmalı.

### 2.3 Altın — `altin_verisi_cek()`

**Sorunlar:**
- **Hardcoded kimlik bilgileri:** `username = 'AltinkaynakWebServis'`, `password = 'AltinkaynakWebServis'` kaynak kodda açık yazıyor. Bu ciddi bir güvenlik açığı.
- SOAP servisi kullanılıyor; bu servisin ne zaman kapanacağı/değişeceği belirsiz.
- İç içe XML parse (SOAP yanıtı içinde başka bir XML string) — `ET.fromstring(inner_xml_string)` kırılgan.
- `altin_tipi_map` sadece 4 altın türünü destekliyor (ONS yorum satırında).

**Öneri:**
- Kimlik bilgilerini `.env` dosyasına taşıyın.
- Altın için TCMB XML'inden veya collectapi.com/bigpara gibi alternatif kaynaklardan veri çekilebilir.

### 2.4 Döviz — `doviz_verisi_cek()`

**Değerlendirme: En stabil veri kaynağı.** TCMB resmi XML feed'i kullanılıyor.

**Küçük sorunlar:**
- Her çağrıda yeni HTTP isteği yapılıyor, caching yok.
- Hafta sonunu atlıyor ama tatil günleri için özel mantık yok (dini/milli bayramlar).
- `for/else` döngüsü ile çalışıyor — break olmadan tamamlanan döngü `else` bloğuna giriyor, bu Python'a özgü ve okunması zor.

---

## 3. Mimari ve Kod Kalitesi Sorunları

### 3.1 Büyük Tekrarlayan Kod Blokları

`index()` ve `yatirimlar()` route'larında **neredeyse aynı gruplandırma ve hesaplama mantığı** copy-paste ile çoğaltılmış (~150 satır tekrar). Ayrıca `export_portfolio_pdf()` fonksiyonunda da aynı toplam hesaplama kodu **üçüncü kez** yazılmış.

**Çözüm:** Bir `hesapla_portfoy_ozeti(user_id)` yardımcı fonksiyonu oluşturulmalı.

### 3.2 Route İçinde Tanımlanan Class

`index()` fonksiyonu içinde `class YatirimPerformans` tanımlanıyor. Her HTTP isteğinde bu class yeniden tanımlanıyor — hem yavaş hem de kötü pratik.

### 3.3 app.py Tek Dosyada Çok Büyük

`app.py` ~82KB, ~2000+ satır. Veri çekme fonksiyonları, route handler'lar, PDF oluşturma, veritabanı migration hepsi aynı dosyada. Bu bakım ve test yazmayı zorlaştırıyor.

**Öneri:** Katmanlara ayırın:
```
services/
  price_fetcher.py    # Veri çekme fonksiyonları
  portfolio.py        # Hesaplama mantığı
routes/
  main.py
  portfolio.py
  export.py
```

### 3.4 Performans Grafiği Sahte Veri Kullanıyor

```python
values = [guncel_deger_float * (1 + (i-15) * 0.001) for i in range(30)]  # Basit trend
```
30 günlük performans grafiği gerçek `FiyatGecmisi` verilerini değil, matematiksel yaklaşım kullanıyor. Kullanıcı yanıltıcı grafik görüyor.

### 3.5 `print()` Kullanımı

Üretim kodunda çok sayıda `print()` ifadesi var. Bunlar `logging` ile değiştirilmeli.

---

## 4. Güvenlik Açıkları

| # | Sorun | Şiddet | Konum |
|---|-------|--------|-------|
| 1 | Hardcoded API şifresi (`AltinkaynakWebServis`) | 🔴 Kritik | `app.py` |
| 2 | `SESSION_SECRET` için zayıf fallback (`finanstakip2025_default_secret_key`) | 🔴 Kritik | `app.py` |
| 3 | `SESSION_COOKIE_SECURE = False` — HTTP üzerinden cookie | 🟠 Yüksek | `app.py` |
| 4 | `user_id` nullable=True — yatırımlar sahipsiz kalabilir | 🟡 Orta | `models.py` |
| 5 | PDF oluştururken HTML f-string injection riski (kısmi) | 🟡 Orta | `app.py` |
| 6 | CSRF token eksikliği (Flask-WTF kullanılmıyor) | 🟡 Orta | Genelinde |
| 7 | Rate limiting yok — fiyat güncelleme endpoint'i brute-force'a açık | 🟡 Orta | `/fiyat_guncelle` |

---

## 5. Eksik Özellikler ve İyileştirme Fırsatları

### 5.1 Kritik Eksikler
- **Caching yok:** Her fiyat güncelleme isteğinde canlı HTTP isteği atılıyor. Aynı kullanıcı birden fazla aynı varlığa sahipse aynı endpoint'e gereksiz çoklu istek gidiyor.
- **Async veri çekme yok:** `toplu_fiyat_guncelle()` sıralı (sequential) çalışıyor. 20 yatırım varsa 20x15 saniye = 5 dakika bekleyebilir.
- **Gerçek fiyat geçmişi grafiği yok:** `FiyatGecmisi` tablosu var ama ana sayfadaki grafik bunu kullanmıyor.

### 5.2 Kullanıcı Deneyimi
- Toplu fiyat güncelleme progress göstergesi yok (kullanıcı beklediğini bilmiyor)
- Yatırım ekleme sırasında kod doğrulama API çağrısı 2x yapılıyor (bir kez `fiyat_guncelle`, bir kez de `isim doğrulama`)
- Hata mesajları Türkçe/İngilizce karışık

### 5.3 Eklenebilecek Özellikler
- Otomatik fiyat güncelleme (scheduler/cron ile)
- Döviz bazında toplam portföy değeri (USD, EUR)
- Kâr/zarar vergi hesabı (FIFO/LIFO)
- CSV/Excel import ile toplu yatırım ekleme
- Fiyat uyarıları (hedef fiyata ulaşınca bildirim)
- Portföy karşılaştırma (benchmark - BIST100 vs portföy)

---

## 6. Veritabanı Sorunları

- `Yatirim.user_id` → `nullable=True` migration için yapılmış ama artık `nullable=False` yapılmalı
- `FiyatGecmisi` tablosunda `user_id` gereksiz (zaten `yatirim_id` üzerinden kullanıcıya ulaşılabilir) — veri tutarsızlığı riski
- Index eksikliği: `Yatirim.user_id`, `Yatirim.kod`, `FiyatGecmisi.yatirim_id` sütunlarında DB index tanımlı değil

---

## 7. Öncelik Sırası (Codex İle Geliştirme Planı)

### Faz 1 — Güvenlik ve Stabilite (Önce Yap)
1. Hardcoded kimlik bilgilerini `.env`'e taşı
2. Secret key ortam değişkeninden zorunlu al
3. `BIST` fiyat parse'ını try-except ile sar
4. CSRF koruması ekle (Flask-WTF)
5. `SESSION_COOKIE_SECURE` production'da `True` yap

### Faz 2 — Kod Kalitesi
6. `hesapla_portfoy_ozeti()` yardımcı fonksiyonu çıkar (tekrarı kaldır)
7. `app.py`'yi modüllere böl (`services/`, `routes/`)
8. `print()` → `logging` dönüşümü
9. `class YatirimPerformans`'ı dosya üstüne taşı

### Faz 3 — Veri Çekme İyileştirmesi
10. Fiyatlar için in-memory cache ekle (TTL: 15 dakika)
11. `toplu_fiyat_guncelle()` async hale getir (`concurrent.futures.ThreadPoolExecutor`)
12. BIST için alternatif/yedek veri kaynağı ekle
13. Altın için TCMB veya alternatif kaynak ekle (SOAP yerine)

### Faz 4 — Özellik Geliştirme
14. Gerçek fiyat geçmişi grafiği (FiyatGecmisi tablosundan)
15. Otomatik güncelleme scheduler (APScheduler)
16. DB index optimizasyonu
17. CSV import özelliği

---

## 8. Özet Tablo

| Alan | Durum | Öncelik |
|------|-------|---------|
| Güvenlik | ❌ Eksik | 🔴 Acil |
| Veri çekme stabilitesi | ⚠️ Kırılgan | 🔴 Acil |
| Kod tekrarı | ❌ Çok fazla | 🟠 Yüksek |
| Async veri çekme | ❌ Yok | 🟠 Yüksek |
| Caching | ❌ Yok | 🟠 Yüksek |
| Gerçek performans grafiği | ❌ Yok | 🟡 Orta |
| Test coverage | ❌ Yok | 🟡 Orta |
| Veritabanı indexleri | ❌ Yok | 🟡 Orta |

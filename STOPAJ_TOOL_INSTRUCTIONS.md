# Stopaj Hesaplama Tool'u — AI Ajan Geliştirme Kılavuzu

> Bu dosya, mevcut finans takip uygulamasına stopaj hesaplama özelliği eklemek için Codex/VSCode AI ajanına verilecek talimat belgesidir. FINANS_TAKIP_ANALIZ_RAPORU.md ve CODEX_AGENT_INSTRUCTIONS.md ile birlikte kullanılmalıdır.

---

## Bu Dosyayı Nasıl Kullanacaksın

Görevleri sırayla, birer birer ver:

```
STOPAJ_TOOL_INSTRUCTIONS.md dosyasını oku. GÖREV S1'i uygula.
Tamamladıktan sonra `python app.py` ile kontrol et ve commit özetini onay için sun.
```

Her görev sonrası `python app.py` çalışıyor olmalı. Bozulursa geri al.

---

## Proje Bağlamı

Mevcut sistem Flask + SQLAlchemy + SQLite. `Yatirim` modelinde `tip='fon'` olan kayıtlar var ama fon türü (hisse yoğun mu, para piyasası mı vb.) **hiç saklanmıyor**. Stopaj hesabı için bu bilgi zorunlu. Mevcut kar/zarar hesapları **brüt** olarak kalacak — stopaj ayrı bir sayfa/simülasyon alanında gösterilecek.

---

## Stopaj Mevzuatı Referansı (GVK Geçici 67. Madde)

### Fon Grupları

| Grup | Fon Türleri |
|------|-------------|
| A — Hisse Yoğun | Portföyünün min. %80'i BİST hissesi olan fonlar (HSYF), Hisse Yoğun BYF |
| B — TL Standart | Para Piyasası, Borçlanma Araçları (TL), Fon Sepeti (döviz/yabancı hariç), Kıymetli Madenler, Katılım Fonları (döviz ifadesi olmayanlar) |
| C — Dövizli / Diğer | Değişken, Karma, Serbest, Yabancı Fonlar, unvanında "Döviz" geçenler, Eurobond, Dış Borçlanma |
| D — GSYF & GYF | Girişim Sermayesi Yatırım Fonu, Gayrimenkul Yatırım Fonu |

### Stopaj Oranları (Bu Tablo DB'de Tutulacak)

**Grup A:**
| Dönem Başlangıç | Dönem Bitiş | Elde Tutma Şartı | Oran |
|---|---|---|---|
| 2000-01-01 | 2025-07-08 | Yok | %0 |
| 2025-07-09 | - | 1 yıldan fazla | %0 |
| 2025-07-09 | - | 1 yıldan az | %17.5 |

**Grup B:**
| Dönem Başlangıç | Dönem Bitiş | Oran |
|---|---|---|
| 2000-01-01 | 2020-12-22 | %10 |
| 2020-12-23 | 2024-04-30 | %0 |
| 2024-05-01 | 2024-10-31 | %7.5 |
| 2024-11-01 | 2025-01-31 | %10 |
| 2025-02-01 | 2025-07-08 | %15 |
| 2025-07-09 | - | %17.5 |

**Grup C:**
| Dönem Başlangıç | Dönem Bitiş | Oran |
|---|---|---|
| 2000-01-01 | 2025-07-08 | %10 |
| 2025-07-09 | - | %17.5 |

**Grup D:**
| Dönem Başlangıç | Dönem Bitiş | Elde Tutma Şartı | Oran |
|---|---|---|---|
| 2000-01-01 | 2025-07-08 | 2 yıldan fazla | %0 |
| 2000-01-01 | 2025-07-08 | 2 yıldan az | %10 |
| 2025-07-09 | - | 2 yıldan fazla | %0 |
| 2025-07-09 | - | 2 yıldan az | %17.5 |

> **ÖNEMLİ:** Bu oranlar ileride değişebilir. Oranlar kod içine yazılmayacak, DB'deki `StopajOrani` tablosunda tutulacak. Yeni dönem eklemek için yalnızca DB'ye yeni satır eklenir, kod değişikliği gerekmez.

---

## Fon Bilgisi Otomatik Çekme — Mimari Karar

### Mevcut Akış (Değiştirilmeyecek)

Kullanıcı "Yeni Yatırım Ekle" modalında şu adımları izliyor:
1. Tip seçer → "Yatırım Fonu"
2. Fon kodu yazar (örn. `ZBJ`)
3. Sistem otomatik olarak `/api/yatirim_dogrula` endpoint'ini çağırır
4. TEFAS'tan **fiyat + isim** çekilir, modal'da gösterilir
5. Kullanıcı kaydet der → `yatirim_ekle` route'u çalışır

### Yeni Akış (Eklentiler)

Adım 3'te `/api/yatirim_dogrula` çağrısı genişletilecek — fiyat ve ismin yanında **fon tipi bilgisi de** TEFAS'tan çekilecek. Kullanıcıya **ekstra alan gösterilmeyecek**, her şey arka planda otomatik halledilecek.

```
Fon kodu girildi
    → TEFAS'tan: fiyat + isim + FONTURKOD + KURUCUKOD + şemsiye fon türü
    → FONTURKOD'dan stopaj grubu otomatik tespit
    → Tespit başarılı: DB'ye kaydedilir, kullanıcı bilgilendirilmez
    → Tespit başarısız: DB'ye NULL kaydedilir, stopaj sayfasında "Grup belirsiz" uyarısı çıkar
```

### Mevcut Fonlar İçin Tek Seferlik Migrasyon

Sistemde zaten kayıtlı fonlar var (`fon_bilgi_guncelleme` alanı NULL olanlar). Bunlar için:

1. Migration çalışır → yeni alanlar NULL olarak eklenir
2. Uygulama ilk başladığında (veya admin tetiklediğinde) tüm mevcut fonlar için TEFAS'tan bilgi çekilir
3. Başarılı olanlar güncellenir, başarısız olanlar NULL kalır
4. Stopaj sayfasında NULL olanlar için "Grup Belirsiz" badge'i gösterilir, kullanıcı manuel seçebilir

### FONTURKOD → Stopaj Grubu Eşleştirme Tablosu

Bu eşleştirme kod içinde sabit bir dict olarak tutulacak (DB'ye gerek yok, fon türleri değişmez):

```python
FONTURKOD_STOPAJ_GRUBU = {
    # GRUP A — Hisse Senedi Yoğun
    'HIS': 'A', 'HSY': 'A', 'BYF-HIS': 'A',
    # GRUP B — TL Standart
    'PAR': 'B', 'BOR': 'B', 'KAT': 'B',
    'MAD': 'B', 'SEP': 'B', 'FON': 'B',
    # GRUP C — Dövizli / Değişken / Diğer
    'DEG': 'C', 'KAR': 'C', 'SER': 'C',
    'DOV': 'C', 'DYB': 'C', 'YAB': 'C', 'EUR': 'C',
    # GRUP D — GSYF & GYF
    'GYF': 'D', 'GSY': 'D',
}
```

Unvandan tespit fallback'i (FONTURKOD gelmezse veya listede yoksa):
```python
FON_UNVAN_STOPAJ_GRUBU = [
    (['HİSSE SENEDİ YOĞUN', 'HSYF'], 'A'),
    (['PARA PİYASASI', 'BORÇLANMA ARAÇLARI', 'KIYMETLİ MADEN', 'KATILIM'], 'B'),
    (['DÖVİZ', 'EUROBOND', 'DIŞ BORÇLANMA', 'YABANCI', 'DEĞİŞKEN', 'KARMA', 'SERBEST'], 'C'),
    (['GAYRİMENKUL YATIRIM FONU', 'GİRİŞİM SERMAYESİ'], 'D'),
]
```

---

## GÖREV S1: Veritabanı Modelleri

### S1a. StopajOrani Modeli

`models.py` dosyasına şu modeli ekle:

```python
class StopajOrani(db.Model):
    """
    Fon grubuna ve alış tarihine göre stopaj oranlarını tutar.
    Yeni mevzuat değişikliklerinde yalnızca bu tabloya satır eklenir.
    """
    id = db.Column(db.Integer, primary_key=True)
    fon_grubu = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', 'D'
    donem_baslangic = db.Column(db.Date, nullable=False)  # Bu tarih ve sonrasında alınanlar
    donem_bitis = db.Column(db.Date, nullable=True)       # None = hâlâ geçerli
    elde_tutma_gun = db.Column(db.Integer, nullable=True) # None = süre şartı yok
                                                           # Pozitif = bu günden AZ elde tutulursa bu oran
    oran = db.Column(db.Numeric(5, 2), nullable=False)    # Yüzde olarak: 17.50, 10.00, 0.00
    aciklama = db.Column(db.String(200))                   # İsteğe bağlı not

    def __repr__(self):
        return f'<StopajOrani Grup:{self.fon_grubu} {self.donem_baslangic} %{self.oran}>'
```

### S1b. Yatirim Modeline Fon Bilgisi Alanları Ekle

`models.py` içindeki `Yatirim` modeline şu alanları ekle (mevcut alanları değiştirme, sadece ekle):

```python
# Fon bilgisi alanları — sadece tip='fon' için kullanılır
fon_grubu         = db.Column(db.String(1),   nullable=True)  # 'A','B','C','D' — stopaj grubu
fon_tur_kodu      = db.Column(db.String(10),  nullable=True)  # TEFAS FONTURKOD: 'HIS','PAR','BOR' vb.
semsiye_fon_turu  = db.Column(db.String(10),  nullable=True)  # TEFAS FONTUR: 'YAT','EMK','BYF'
fon_unvan_tipi    = db.Column(db.String(100), nullable=True)  # Tam unvan tipi açıklaması
kurucu_kodu       = db.Column(db.String(20),  nullable=True)  # Portföy yöneticisi/kurucu kodu
fon_grubu_otomatik = db.Column(db.Boolean,   default=False)   # True=TEFAS'tan otomatik, False=manuel
fon_bilgi_guncelleme = db.Column(db.DateTime, nullable=True)  # Son fon bilgisi güncelleme tarihi
```

`to_dict()` metoduna da ekle:
```python
'fon_grubu': self.fon_grubu,
'fon_tur_kodu': self.fon_tur_kodu,
'semsiye_fon_turu': self.semsiye_fon_turu,
'fon_unvan_tipi': self.fon_unvan_tipi,
'kurucu_kodu': self.kurucu_kodu,
'fon_grubu_otomatik': self.fon_grubu_otomatik,
```

### S1c. Migration ve Seed Data

Migration çalıştır:
```bash
flask db migrate -m "stopaj_orani_tablosu_ve_fon_grubu_alani"
flask db upgrade
```

Ardından `app.py` içindeki `init_database()` fonksiyonuna seed data ekle — `StopajOrani` tablosu boşsa aşağıdaki verileri yükle:

```python
def stopaj_seed_data():
    """StopajOrani tablosunu başlangıç verileriyle doldurur."""
    if StopajOrani.query.count() > 0:
        return  # Zaten dolu, tekrar ekleme

    from datetime import date
    oranlar = [
        # GRUP A — Hisse Senedi Yoğun Fon
        StopajOrani(fon_grubu='A', donem_baslangic=date(2000,1,1),  donem_bitis=date(2025,7,8),  elde_tutma_gun=None, oran=0.00,  aciklama='HSYF - 09.07.2025 öncesi tüm alımlar'),
        StopajOrani(fon_grubu='A', donem_baslangic=date(2025,7,9),  donem_bitis=None,            elde_tutma_gun=365,  oran=17.50, aciklama='HSYF - 09.07.2025 sonrası, 1 yıldan az elde tutma'),
        StopajOrani(fon_grubu='A', donem_baslangic=date(2025,7,9),  donem_bitis=None,            elde_tutma_gun=None, oran=0.00,  aciklama='HSYF - 09.07.2025 sonrası, 1 yıl ve üzeri elde tutma'),
        # GRUP B — TL Standart Fonlar
        StopajOrani(fon_grubu='B', donem_baslangic=date(2000,1,1),  donem_bitis=date(2020,12,22), elde_tutma_gun=None, oran=10.00, aciklama='TL Standart - 23.12.2020 öncesi'),
        StopajOrani(fon_grubu='B', donem_baslangic=date(2020,12,23),donem_bitis=date(2024,4,30),  elde_tutma_gun=None, oran=0.00,  aciklama='TL Standart - indirimli dönem'),
        StopajOrani(fon_grubu='B', donem_baslangic=date(2024,5,1),  donem_bitis=date(2024,10,31), elde_tutma_gun=None, oran=7.50,  aciklama='TL Standart - kademeli artış 1'),
        StopajOrani(fon_grubu='B', donem_baslangic=date(2024,11,1), donem_bitis=date(2025,1,31),  elde_tutma_gun=None, oran=10.00, aciklama='TL Standart - kademeli artış 2'),
        StopajOrani(fon_grubu='B', donem_baslangic=date(2025,2,1),  donem_bitis=date(2025,7,8),   elde_tutma_gun=None, oran=15.00, aciklama='TL Standart - kademeli artış 3'),
        StopajOrani(fon_grubu='B', donem_baslangic=date(2025,7,9),  donem_bitis=None,             elde_tutma_gun=None, oran=17.50, aciklama='TL Standart - güncel oran'),
        # GRUP C — Dövizli / Değişken / Diğer
        StopajOrani(fon_grubu='C', donem_baslangic=date(2000,1,1),  donem_bitis=date(2025,7,8),   elde_tutma_gun=None, oran=10.00, aciklama='Dövizli/Değişken - 09.07.2025 öncesi'),
        StopajOrani(fon_grubu='C', donem_baslangic=date(2025,7,9),  donem_bitis=None,             elde_tutma_gun=None, oran=17.50, aciklama='Dövizli/Değişken - güncel oran'),
        # GRUP D — GSYF & GYF
        StopajOrani(fon_grubu='D', donem_baslangic=date(2000,1,1),  donem_bitis=date(2025,7,8),   elde_tutma_gun=730,  oran=10.00, aciklama='GSYF/GYF - 2 yıldan az'),
        StopajOrani(fon_grubu='D', donem_baslangic=date(2000,1,1),  donem_bitis=date(2025,7,8),   elde_tutma_gun=None, oran=0.00,  aciklama='GSYF/GYF - 2 yıl ve üzeri'),
        StopajOrani(fon_grubu='D', donem_baslangic=date(2025,7,9),  donem_bitis=None,             elde_tutma_gun=730,  oran=17.50, aciklama='GSYF/GYF - 09.07.2025 sonrası, 2 yıldan az'),
        StopajOrani(fon_grubu='D', donem_baslangic=date(2025,7,9),  donem_bitis=None,             elde_tutma_gun=None, oran=0.00,  aciklama='GSYF/GYF - 09.07.2025 sonrası, 2 yıl ve üzeri'),
    ]
    for o in oranlar:
        db.session.add(o)
    db.session.commit()
    print("Stopaj oranları seed data yüklendi.")
```

`init_database()` içine `stopaj_seed_data()` çağrısını ekle.

---

## GÖREV S2: Fon Bilgisi Çekme Servisi + Stopaj Hesaplama

### S2a. TEFAS'tan Fon Bilgisi Çekme Fonksiyonu

`app.py` içine (mevcut `tefas_fon_verisi_cek()` fonksiyonunun hemen altına) ekle:

```python
# Fon türü → stopaj grubu eşleştirme tablosu
FONTURKOD_STOPAJ_GRUBU = {
    'HIS': 'A', 'HSY': 'A', 'BYF-HIS': 'A',          # Hisse Yoğun
    'PAR': 'B', 'BOR': 'B', 'KAT': 'B',               # TL Standart
    'MAD': 'B', 'SEP': 'B', 'FON': 'B',
    'DEG': 'C', 'KAR': 'C', 'SER': 'C',               # Dövizli/Değişken
    'DOV': 'C', 'DYB': 'C', 'YAB': 'C', 'EUR': 'C',
    'GYF': 'D', 'GSY': 'D',                            # GSYF & GYF
}

# Fon unvanından stopaj grubu tahmin tablosu (fallback)
FON_UNVAN_STOPAJ_GRUBU = [
    (['HİSSE SENEDİ YOĞUN', 'HSYF'], 'A'),
    (['PARA PİYASASI', 'BORÇLANMA ARAÇLARI', 'KIYMETLİ MADEN', 'KATILIM'], 'B'),
    (['DÖVİZ', 'EUROBOND', 'DIŞ BORÇLANMA', 'YABANCI', 'DEĞİŞKEN', 'KARMA', 'SERBEST'], 'C'),
    (['GAYRİMENKUL YATIRIM FONU', 'GİRİŞİM SERMAYESİ'], 'D'),
]


def fon_bilgisi_cek(fon_kodu):
    """
    TEFAS'tan fon tipi, şemsiye fon türü ve kurucu bilgilerini çeker.
    Fiyat bilgisi bu fonksiyonda çekilmez — fiyat için tefas_fon_verisi_cek() kullanılır.

    Returns:
        dict veya None: {
            'fon_tur_kodu': str,       # HIS, PAR, BOR vb.
            'semsiye_fon_turu': str,   # YAT, EMK, BYF
            'fon_unvan_tipi': str,     # Tam unvan tipi açıklaması
            'kurucu_kodu': str,        # Portföy yöneticisi kodu
            'fon_grubu': str,          # A, B, C veya D — otomatik hesaplanmış
            'fon_grubu_otomatik': bool # True = TEFAS'tan, False = unvandan tahmin
        }
    """
    fon_kodu_upper = fon_kodu.upper()
    app.logger.info(f"Fon bilgisi çekiliyor: {fon_kodu_upper}")

    # TEFAS BindHistoryInfo endpoint — fon tip bilgisi içeriyor
    api_url = (
        f"https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
        f"?fontip=YAT&sfontur=&kurucukod=&fonkod={fon_kodu_upper}&bastarih=&bittarih="
    )
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json',
        'Referer': 'https://www.tefas.gov.tr/'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                kayit = data[0]
                fon_tur_kodu    = kayit.get('FONTURKOD') or kayit.get('SFONTUR', '')
                semsiye_turu    = kayit.get('FONTUR', '')
                unvan_tipi      = kayit.get('FONUNVANTIP') or kayit.get('FONUNVAN', '')
                kurucu_kodu     = kayit.get('KURUCUKOD', '')

                # Stopaj grubunu FONTURKOD'dan bul
                fon_grubu = FONTURKOD_STOPAJ_GRUBU.get(fon_tur_kodu.upper() if fon_tur_kodu else '')
                otomatik = fon_grubu is not None

                # Bulunamadıysa unvandan tahmin et (fallback)
                if not fon_grubu and unvan_tipi:
                    unvan_upper = unvan_tipi.upper()
                    for anahtar_kelimeler, grup in FON_UNVAN_STOPAJ_GRUBU:
                        if any(k in unvan_upper for k in anahtar_kelimeler):
                            fon_grubu = grup
                            break

                app.logger.info(
                    f"Fon bilgisi çekildi: {fon_kodu_upper} | "
                    f"TürKod={fon_tur_kodu} | Grup={fon_grubu} | Otomatik={otomatik}"
                )
                return {
                    'fon_tur_kodu': fon_tur_kodu,
                    'semsiye_fon_turu': semsiye_turu,
                    'fon_unvan_tipi': unvan_tipi,
                    'kurucu_kodu': kurucu_kodu,
                    'fon_grubu': fon_grubu,
                    'fon_grubu_otomatik': otomatik,
                }

        app.logger.warning(f"TEFAS fon bilgisi API yanıt vermedi: {fon_kodu_upper}")
        return None

    except Exception as e:
        app.logger.error(f"Fon bilgisi çekme hatası ({fon_kodu_upper}): {e}")
        return None


def fon_bilgisi_yatirima_kaydet(yatirim):
    """
    Bir Yatirim objesinin fon bilgilerini TEFAS'tan çekip DB'ye kaydeder.
    Hem yeni fon eklemede hem mevcut fonların migrasyonunda kullanılır.
    """
    if yatirim.tip != 'fon':
        return False

    bilgi = fon_bilgisi_cek(yatirim.kod)
    if bilgi:
        yatirim.fon_tur_kodu         = bilgi['fon_tur_kodu']
        yatirim.semsiye_fon_turu     = bilgi['semsiye_fon_turu']
        yatirim.fon_unvan_tipi       = bilgi['fon_unvan_tipi']
        yatirim.kurucu_kodu          = bilgi['kurucu_kodu']
        yatirim.fon_grubu            = bilgi['fon_grubu']
        yatirim.fon_grubu_otomatik   = bilgi['fon_grubu_otomatik']
        yatirim.fon_bilgi_guncelleme = datetime.now()
        db.session.commit()
        return True
    return False
```

### S2b. Mevcut Fonlar İçin Migrasyon Fonksiyonu

`app.py` içindeki `init_database()` fonksiyonuna şu çağrıyı ekle:

```python
def migrate_fon_bilgileri():
    """
    Daha önce eklenmiş fonlar için fon bilgilerini TEFAS'tan çeker.
    fon_bilgi_guncelleme alanı NULL olan fonları günceller.
    Uygulama başlarken bir kez çalışır, zaten güncellenmiş fonlara dokunmaz.
    """
    try:
        guncellenmemis_fonlar = Yatirim.query.filter(
            Yatirim.tip == 'fon',
            Yatirim.fon_bilgi_guncelleme == None
        ).all()

        if not guncellenmemis_fonlar:
            return

        app.logger.info(f"{len(guncellenmemis_fonlar)} fon için bilgi güncelleme başlatılıyor...")

        # Aynı kodu birden fazla kez sorgulamaktan kaçın
        islenmis_kodlar = {}
        for yatirim in guncellenmemis_fonlar:
            if yatirim.kod not in islenmis_kodlar:
                bilgi = fon_bilgisi_cek(yatirim.kod)
                islenmis_kodlar[yatirim.kod] = bilgi

            bilgi = islenmis_kodlar[yatirim.kod]
            if bilgi:
                yatirim.fon_tur_kodu         = bilgi['fon_tur_kodu']
                yatirim.semsiye_fon_turu     = bilgi['semsiye_fon_turu']
                yatirim.fon_unvan_tipi       = bilgi['fon_unvan_tipi']
                yatirim.kurucu_kodu          = bilgi['kurucu_kodu']
                yatirim.fon_grubu            = bilgi['fon_grubu']
                yatirim.fon_grubu_otomatik   = bilgi['fon_grubu_otomatik']
                yatirim.fon_bilgi_guncelleme = datetime.now()

        db.session.commit()
        app.logger.info(f"Fon bilgisi migrasyonu tamamlandı.")

    except Exception as e:
        app.logger.error(f"Fon bilgisi migrasyon hatası: {e}")
```

### S2c. Yatirim Ekle Route'una Entegrasyon

`yatirim_ekle()` route'unda fon kaydedildikten sonra (`db.session.commit()` çağrısının hemen ardından) fon bilgisi otomatik çekilecek şekilde güncelle:

```python
# Mevcut kod:
db.session.add(yatirim)
db.session.commit()
fiyat_guncelle(yatirim.id)   # Bu zaten var

# EKLENECEK — fiyat güncellemesinin hemen altına:
if tip == 'fon':
    fon_bilgisi_yatirima_kaydet(yatirim)
    if yatirim.fon_grubu:
        grup_aciklamalari = {'A': 'Hisse Yoğun', 'B': 'TL Standart', 'C': 'Dövizli/Değişken', 'D': 'GSYF/GYF'}
        app.logger.info(f"{kod} fonu Stopaj Grubu {yatirim.fon_grubu} ({grup_aciklamalari.get(yatirim.fon_grubu, '')}) olarak tanımlandı.")
```

### S2d. API Doğrulama Endpoint'ini Genişlet

`/api/yatirim_dogrula` route'u şu an sadece `isim` ve `guncel_fiyat` döndürüyor. Fon için fon bilgisini de döndürecek şekilde güncelle:

```python
# Mevcut return:
return jsonify({
    'success': True,
    'isim': result.get('isim', 'Bilinmeyen'),
    'guncel_fiyat': float(result.get('guncel_fiyat', 0))
})

# YENİ — fon için ek bilgi ekle:
if result:
    yanit = {
        'success': True,
        'isim': result.get('isim', 'Bilinmeyen'),
        'guncel_fiyat': float(result.get('guncel_fiyat', 0))
    }
    # Fon ise ek bilgi çek
    if tip == 'fon':
        bilgi = fon_bilgisi_cek(kod)
        if bilgi and bilgi.get('fon_grubu'):
            grup_etiketleri = {
                'A': 'Hisse Yoğun (Stopaj %0/%17.5)',
                'B': 'TL Standart',
                'C': 'Dövizli/Değişken',
                'D': 'GSYF/GYF'
            }
            yanit['fon_grubu'] = bilgi['fon_grubu']
            yanit['fon_grubu_etiket'] = grup_etiketleri.get(bilgi['fon_grubu'], '')
            yanit['fon_tur_kodu'] = bilgi.get('fon_tur_kodu', '')
            yanit['kurucu_kodu'] = bilgi.get('kurucu_kodu', '')
    return jsonify(yanit)
```

Bu sayede modal'daki `validateCode()` JS fonksiyonu fon bilgisini alır. `kodSonuc` alanında fiyatın yanında fon grubu da gösterilebilir (GÖREV S4'te template güncellenecek).

### S2e. Stopaj Hesaplama Servisi

`app.py` içine (route'lardan önce, `fon_bilgisi_cek()` fonksiyonunun altına) şu servis fonksiyonunu ekle:

```python
def stopaj_orani_bul(fon_grubu, alis_tarihi, satis_tarihi=None):
    """
    Verilen fon grubu ve alış tarihine göre uygulanacak stopaj oranını döndürür.

    Args:
        fon_grubu: 'A', 'B', 'C' veya 'D'
        alis_tarihi: datetime — fonun alındığı tarih
        satis_tarihi: datetime — satış tarihi (None ise bugün kabul edilir)

    Returns:
        Decimal — stopaj oranı (örn. Decimal('17.50'))
        None — fon_grubu None veya bilinmiyorsa
    """
    if not fon_grubu:
        return None

    if satis_tarihi is None:
        satis_tarihi = datetime.now()

    alis_date = alis_tarihi.date() if hasattr(alis_tarihi, 'date') else alis_tarihi
    satis_date = satis_tarihi.date() if hasattr(satis_tarihi, 'date') else satis_tarihi
    elde_tutma_gun = (satis_date - alis_date).days

    # Alış tarihine uyan dönemleri bul
    adaylar = StopajOrani.query.filter(
        StopajOrani.fon_grubu == fon_grubu,
        StopajOrani.donem_baslangic <= alis_date,
        db.or_(
            StopajOrani.donem_bitis >= alis_date,
            StopajOrani.donem_bitis == None
        )
    ).all()

    if not adaylar:
        return None

    # Elde tutma süresi şartına göre filtrele
    for aday in adaylar:
        if aday.elde_tutma_gun is not None:
            # Süre şartı var — elde tutma bu günden AZ mı?
            if elde_tutma_gun < aday.elde_tutma_gun:
                return Decimal(str(aday.oran))
        else:
            # Süre şartı yok — bu genel/varsayılan oran
            return Decimal(str(aday.oran))

    return None


def stopaj_hesapla(yatirim, satis_tarihi=None, satis_fiyati=None):
    """
    Bir yatırım için stopaj tutarını ve net kar/zarar hesaplar.

    Args:
        yatirim: Yatirim model objesi
        satis_tarihi: datetime — None ise bugün
        satis_fiyati: Decimal — None ise güncel fiyat kullanılır

    Returns:
        dict: {
            'brut_kar': Decimal,
            'stopaj_orani': Decimal veya None,
            'stopaj_tutari': Decimal,
            'net_kar': Decimal,
            'elde_tutma_gun': int,
            'fon_grubu': str veya None,
            'hesaplanamadi': bool  # fon_grubu bilinmiyorsa True
        }
    """
    if satis_tarihi is None:
        satis_tarihi = datetime.now()

    if satis_fiyati is None:
        satis_fiyati = yatirim.guncel_fiyat

    maliyet = yatirim.alis_fiyati * yatirim.miktar
    guncel_deger = (satis_fiyati * yatirim.miktar) if satis_fiyati else maliyet
    brut_kar = guncel_deger - maliyet

    elde_tutma_gun = (satis_tarihi.date() - yatirim.alis_tarihi.date()).days

    oran = stopaj_orani_bul(yatirim.fon_grubu, yatirim.alis_tarihi, satis_tarihi)

    if oran is None:
        return {
            'brut_kar': brut_kar,
            'stopaj_orani': None,
            'stopaj_tutari': Decimal('0'),
            'net_kar': brut_kar,
            'elde_tutma_gun': elde_tutma_gun,
            'fon_grubu': yatirim.fon_grubu,
            'hesaplanamadi': True
        }

    # Stopaj sadece KAR üzerinden hesaplanır, zarar durumunda 0
    stopaj_tutari = (brut_kar * oran / 100) if brut_kar > 0 else Decimal('0')
    net_kar = brut_kar - stopaj_tutari

    return {
        'brut_kar': brut_kar,
        'stopaj_orani': oran,
        'stopaj_tutari': stopaj_tutari,
        'net_kar': net_kar,
        'elde_tutma_gun': elde_tutma_gun,
        'fon_grubu': yatirim.fon_grubu,
        'hesaplanamadi': False
    }
```

---

## GÖREV S3: Route'lar

`app.py` içine şu route'ları ekle:

### S3a. Stopaj Sayfası (Ana Sayfa)

```python
@app.route('/stopaj')
@login_required
def stopaj_sayfasi():
    """Tüm fonların stopaj simülasyon sayfası."""
    fonlar = Yatirim.query.filter_by(
        user_id=current_user.id,
        tip='fon'
    ).order_by(Yatirim.alis_tarihi.desc()).all()

    # Her fon için stopaj hesapla
    fon_stopaj_listesi = []
    for fon in fonlar:
        hesap = stopaj_hesapla(fon)
        fon_stopaj_listesi.append({
            'yatirim': fon,
            'hesap': hesap
        })

    # Fon grubu seçenekleri (dropdown için)
    fon_gruplari = {
        'A': 'Grup A — Hisse Senedi Yoğun Fon (HSYF)',
        'B': 'Grup B — TL Standart (Para Piyasası, Borçlanma vb.)',
        'C': 'Grup C — Dövizli / Değişken / Karma / Serbest',
        'D': 'Grup D — GSYF / GYF'
    }

    # Özet istatistikler
    toplam_brut_kar = sum(
        float(f['hesap']['brut_kar']) for f in fon_stopaj_listesi
        if f['hesap']['brut_kar'] > 0
    )
    toplam_stopaj = sum(
        float(f['hesap']['stopaj_tutari']) for f in fon_stopaj_listesi
    )
    toplam_net_kar = toplam_brut_kar - toplam_stopaj

    return render_template(
        'stopaj.html',
        fon_stopaj_listesi=fon_stopaj_listesi,
        fon_gruplari=fon_gruplari,
        toplam_brut_kar=toplam_brut_kar,
        toplam_stopaj=toplam_stopaj,
        toplam_net_kar=toplam_net_kar
    )
```

### S3b. Fon Grubu Güncelleme API'si

```python
@app.route('/api/fon_grubu_guncelle/<int:yatirim_id>', methods=['POST'])
@login_required
def fon_grubu_guncelle(yatirim_id):
    """Bir fonun grubunu günceller (stopaj hesabı için gerekli)."""
    yatirim = Yatirim.query.get_or_404(yatirim_id)

    if yatirim.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Yetkisiz erişim'}), 403

    if yatirim.tip != 'fon':
        return jsonify({'success': False, 'error': 'Sadece fonlar için geçerlidir'}), 400

    data = request.get_json()
    fon_grubu = data.get('fon_grubu')

    if fon_grubu not in ['A', 'B', 'C', 'D', None]:
        return jsonify({'success': False, 'error': 'Geçersiz fon grubu'}), 400

    yatirim.fon_grubu = fon_grubu
    db.session.commit()

    # Güncellenen stopaj bilgisini döndür
    hesap = stopaj_hesapla(yatirim)
    return jsonify({
        'success': True,
        'fon_grubu': fon_grubu,
        'stopaj_orani': float(hesap['stopaj_orani']) if hesap['stopaj_orani'] else None,
        'stopaj_tutari': float(hesap['stopaj_tutari']),
        'net_kar': float(hesap['net_kar'])
    })
```

### S3c. Stopaj Simülasyon API'si

```python
@app.route('/api/stopaj_simulasyon/<int:yatirim_id>', methods=['POST'])
@login_required
def stopaj_simulasyon(yatirim_id):
    """
    Belirli bir satış fiyatı ve tarihi için stopaj simülasyonu yapar.
    Kullanıcı 'bugün şu fiyattan satarsam ne olur?' sorusunu yanıtlar.
    """
    yatirim = Yatirim.query.get_or_404(yatirim_id)

    if yatirim.user_id != current_user.id:
        return jsonify({'error': 'Yetkisiz erişim'}), 403

    data = request.get_json()

    # İsteğe bağlı parametreler
    satis_fiyati_str = data.get('satis_fiyati')
    satis_tarihi_str = data.get('satis_tarihi')

    satis_fiyati = Decimal(satis_fiyati_str) if satis_fiyati_str else None
    satis_tarihi = datetime.strptime(satis_tarihi_str, '%Y-%m-%d') if satis_tarihi_str else None

    hesap = stopaj_hesapla(yatirim, satis_tarihi=satis_tarihi, satis_fiyati=satis_fiyati)

    return jsonify({
        'success': True,
        'brut_kar': float(hesap['brut_kar']),
        'stopaj_orani': float(hesap['stopaj_orani']) if hesap['stopaj_orani'] else None,
        'stopaj_tutari': float(hesap['stopaj_tutari']),
        'net_kar': float(hesap['net_kar']),
        'elde_tutma_gun': hesap['elde_tutma_gun'],
        'fon_grubu': hesap['fon_grubu'],
        'hesaplanamadi': hesap['hesaplanamadi']
    })
```

---

## GÖREV S4: Stopaj Sayfası Template'i

`templates/stopaj.html` dosyasını oluştur. `{% extends "base.html" %}` kullan.

**Sayfanın içermesi gerekenler:**

### Üst Bölüm — Özet Kartları (3 kart yan yana)

### Yeni Yatırım Ekle Modal'ı Güncellemesi

`templates/yatirimlar.html` içindeki `validateCode()` JS fonksiyonunu güncelle — fon doğrulaması başarılı olduğunda fon grubu bilgisini de göster:

```javascript
// Mevcut başarı mesajı bloğu içine eklenecek (fon tipi için):
if (tip === 'fon' && data.fon_grubu) {
    const grupRenkleri = {'A': 'success', 'B': 'primary', 'C': 'warning', 'D': 'info'};
    const renk = grupRenkleri[data.fon_grubu] || 'secondary';
    kodSonuc.innerHTML += `
        <div class="mt-1">
            <small class="text-muted">Stopaj Grubu: </small>
            <span class="badge bg-${renk}">Grup ${data.fon_grubu} — ${data.fon_grubu_etiket}</span>
            <small class="text-muted ms-2">Fon Türü: ${data.fon_tur_kodu || '-'}</small>
        </div>
    `;
}
```

Bu sayede kullanıcı fon kodu girdiğinde fiyatın yanı sıra stopaj grubunu da anlık görür — ek bir alan doldurmak zorunda kalmaz.
- Toplam Brüt Kâr (tüm fonların pozitif kar toplamı)
- Toplam Stopaj Yükü (kırmızı)
- Toplam Net Kâr (yeşil/kırmızı)

Altına küçük uyarı notu:
```html
<div class="alert alert-warning">
    <i class="fas fa-exclamation-triangle me-2"></i>
    <strong>Bilgilendirme:</strong> Bu hesaplamalar tahmini olup yalnızca bilgilendirme amaçlıdır.
    Stopaj, satış işlemi gerçekleştiğinde aracı kurum tarafından otomatik kesilir.
    Kesin vergi hesabı için mali müşavirinize danışınız.
</div>
```

### Ana Tablo — Tüm Fonların Stopaj Durumu

| Sütun | Açıklama |
|-------|----------|
| Fon Kodu / İsim | Mevcut gösterimle aynı |
| Alış Tarihi | Fon alış tarihi |
| Elde Tutma | Kaç gündür elde tutuluyor (bugüne göre) |
| Fon Grubu | Dropdown select — A/B/C/D veya "Belirsiz" |
| Brüt Kâr | Mevcut kar hesabıyla aynı (değiştirilmez) |
| Stopaj Oranı | %X.X — fon grubu seçilmemişse "Grup seçin" uyarısı |
| Stopaj Tutarı | TL cinsinden |
| Net Kâr | Brüt - Stopaj |
| Simülasyon | "Hesapla" butonu |

**Fon Grubu dropdown davranışı:** Kullanıcı dropdown'dan grup seçtiğinde AJAX ile `/api/fon_grubu_guncelle/<id>` çağrılır, tablo satırı sayfa yenilenmeden güncellenir.

**Simülasyon butonu:** Tıklandığında o fona ait simülasyon modal'ını açar.

### Simülasyon Modal'ı (Her Fon İçin Ortak, JS ile Doldurulur)

Modal içeriği:
- Fon adı ve kodu (başlıkta)
- "Satış Fiyatı" input (boş bırakılırsa güncel fiyat kullanılır)
- "Satış Tarihi" date input (boş bırakılırsa bugün)
- "Hesapla" butonu
- Sonuç alanı:
  - Brüt Kâr
  - Stopaj Oranı ve Tutarı
  - **Net Kâr** (büyük, belirgin font)
  - Elde tutma süresi
- Küçük bilgi notu: "Aynı fonu farklı tarihlerde aldıysanız her alım için ayrı stopaj uygulanır."

---

## GÖREV S5: Navigasyona Ekleme

`templates/base.html` içindeki navbar'a Stopaj sayfası linkini ekle:

```html
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('stopaj_sayfasi') }}">
        <i class="fas fa-percent me-1"></i>Stopaj Hesapla
    </a>
</li>
```

Yatırımlar linkinden sonra, PDF İndir linkinden önce ekle.

---

## GÖREV S6: Stopaj Oranları Yönetim API'si

Gelecekte mevzuat değiştiğinde yeni oran eklemek için admin API'si:

```python
@app.route('/api/stopaj_orani_ekle', methods=['POST'])
@login_required
def stopaj_orani_ekle():
    """
    Yeni bir stopaj oranı dönemi ekler.
    Mevzuat değişikliklerinde kullanılır, kod değişikliği gerekmez.
    Sadece admin kullanıcılar erişebilir.
    """
    # Admin kontrolü (basit — ilerleyen aşamada rol sistemi eklenebilir)
    if current_user.username != 'admin':
        return jsonify({'error': 'Yetkisiz erişim'}), 403

    data = request.get_json()

    try:
        from datetime import date
        yeni_oran = StopajOrani(
            fon_grubu=data['fon_grubu'],
            donem_baslangic=datetime.strptime(data['donem_baslangic'], '%Y-%m-%d').date(),
            donem_bitis=datetime.strptime(data['donem_bitis'], '%Y-%m-%d').date() if data.get('donem_bitis') else None,
            elde_tutma_gun=data.get('elde_tutma_gun'),
            oran=Decimal(str(data['oran'])),
            aciklama=data.get('aciklama', '')
        )
        db.session.add(yeni_oran)
        db.session.commit()
        return jsonify({'success': True, 'id': yeni_oran.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
```

---

## GÖREV S7: PDF Raporuna Stopaj Sütunu Ekle

`export_portfolio_pdf()` fonksiyonundaki HTML tablo bölümüne, sadece `tip='fon'` olan satırlar için stopaj bilgisi ekle.

Fon satırlarına şu sütunları ekle:
- Fon Grubu (A/B/C/D veya "-")
- Stopaj Oranı (%X.X veya "Bilinmiyor")
- Stopaj Tutarı (₺X.XX veya "-")
- Net Kâr (₺X.XX veya "-")

Fon olmayan yatırımlar (hisse, altın, döviz) için bu sütunlar "-" gösterir.

Tablo başlığına eklenecek sütunlar:
```html
<th>Fon Grubu</th>
<th>Stopaj %</th>
<th>Stopaj ₺</th>
<th>Net Kâr</th>
```

PDF'in sonuna uyarı notu ekle:
```
* Stopaj hesaplamaları tahminidir. Kesin tutar aracı kurum tarafından belirlenir.
```

---

## Bilinen Kısıtlamalar

1. **Aynı kodda birden fazla alım:** Kullanıcı aynı fonu farklı tarihlerde almışsa her kalem için `fon_grubu` aynı kabul edilir (DB'de tek `fon_grubu` alanı var). İleride kalem bazında farklı grup tanımlanabilir — şimdilik grup fonun koduna göre belirlenir.

2. **Fon grubu otomatik tespiti:** TEFAS API'sinden `FONTUR` alanı çekilebilir ama güvenilirliği belirsiz. Şimdilik kullanıcı manuel seçer. İleride `tefas_fon_verisi_cek()` fonksiyonu geliştirilerek otomatik tespit eklenebilir.

3. **%80 hisse yoğunluk kontrolü:** Grup A muafiyeti için fonun anlık portföy kompozisyonu gerekir. Bu bilgi TEFAS'tan çekilebilir ama kapsam dışı bırakıldı — kullanıcı kendi fonunun izahnamesine bakarak grubu seçer.

4. **Bu hesap tahminidir:** Stopaj aracı kurum tarafından kesilir. Sistem yalnızca simülasyon sunar, kesin vergi hesabı değildir. Bu uyarı her ekranda görünür olmalıdır.

---

## Test Senaryoları

Her görev sonrası şunları test et:

```
1. Yeni bir fon ekle → Stopaj sayfasına git → "Grup seçin" uyarısı görünmeli
2. Fon grubunu B olarak seç → Stopaj oranı ve tutarı otomatik dolmalı
3. Simülasyon modal'ını aç → Farklı satış fiyatı gir → Net kâr değişmeli
4. 09.07.2025 sonrasında alınmış bir fon için Grup B seç → %17.5 görünmeli
5. 23.12.2020 öncesinde alınmış Grup B fonu → %10 görünmeli
6. Grup A fonu, 1 yıldan az elde tutulmuş, 09.07.2025 sonrası → %17.5 görünmeli
7. Grup A fonu, 1 yıldan fazla elde tutulmuş → %0 görünmeli
8. PDF indir → Fon satırlarında stopaj sütunları dolu, diğerlerinde "-" olmalı
```

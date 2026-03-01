# Satış Modülü — AI Ajan Geliştirme Kılavuzu

> Bu dosya, mevcut finans takip uygulamasına satış işlemi özelliği eklemek için Codex/VSCode AI ajanına verilecek talimat belgesidir. STOPAJ_TOOL_INSTRUCTIONS.md tamamlandıktan sonra uygulanmalıdır — stopaj hesaplama servisi bu modül tarafından kullanılır.

---

## Bu Dosyayı Nasıl Kullanacaksın

Görevleri sırayla, birer birer ver:

```
SATIS_MODULU_INSTRUCTIONS.md dosyasını oku ve tüm görevleri anla.
feature/stopaj-modulu dalında çalışmaya devam et.
GÖREV M1'i uygula. Tamamladıktan sonra `python app.py` ile kontrol et,
sonucu ve commit özetini onay için sun.
```

Commit format: `feat/m1a: SatisIslemi modeli eklendi`

---

## Mimari Kararlar (Değiştirilmez)

| Karar | Seçim |
|---|---|
| Kısmi satış yöntemi | FIFO varsayılan + kullanıcı manuel kayd seçebilir |
| Tamamen satılan yatırımlar | Silinmez, `durum='tamamen_satildi'` olur, `/satislar` sayfasında görünür |
| Stopaj | Otomatik hesaplanır, kullanıcı manuel düzeltebilir |
| Komisyon | Tip bazlı — fon/hisse için komisyon alanı, altın/döviz için sadece "Diğer Masraflar" |
| Satış geçmişi | Ayrı sayfa: `/satislar` |
| Alış komisyonu | `alis_komisyon` alanı ileriye dönük eklenir, mevcut kayıtlar boş kalır |

---

## GÖREV M1: Veritabanı Modelleri

### M1a. SatisIslemi Modeli

`models.py` dosyasına ekle:

```python
class SatisIslemi(db.Model):
    """
    Her satış işlemi bir kayıt olarak saklanır.
    Kısmi satışlarda aynı yatirim_id'ye birden fazla kayıt olabilir.
    Tam satışlarda Yatirim.durum='tamamen_satildi' olur ama kayıt silinmez.
    """
    id               = db.Column(db.Integer, primary_key=True)
    yatirim_id       = db.Column(db.Integer, db.ForeignKey('yatirim.id'), nullable=False, index=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id'),    nullable=False, index=True)
    satis_tarihi     = db.Column(db.DateTime, nullable=False)
    satis_fiyati     = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    satilan_miktar   = db.Column(db.Numeric(precision=20, scale=6), nullable=False)

    # Maliyet — FIFO veya manuel seçimle belirlenen alış fiyatı
    alis_fiyati_baz  = db.Column(db.Numeric(precision=20, scale=6), nullable=False)  # Kullanılan alış fiyatı
    fifo_mi          = db.Column(db.Boolean, default=True)   # True=FIFO, False=manuel seçim

    # Masraflar
    komisyon         = db.Column(db.Numeric(precision=20, scale=6), default=0)  # Aracı kurum komisyonu
    diger_masraf     = db.Column(db.Numeric(precision=20, scale=6), default=0)  # Serbest masraf alanı
    diger_masraf_aciklama = db.Column(db.String(200))                            # Masraf açıklaması

    # Stopaj — otomatik hesaplanır, kullanıcı düzeltebilir
    stopaj_orani     = db.Column(db.Numeric(5, 2))    # % cinsinden: 17.50, 10.00, 0.00
    stopaj_tutari    = db.Column(db.Numeric(precision=20, scale=6), default=0)
    stopaj_manuel_mi = db.Column(db.Boolean, default=False)  # True=kullanıcı düzeltti

    # Hesaplanmış sonuçlar (kayıt anında hesaplanıp saklanır)
    brut_kar         = db.Column(db.Numeric(precision=20, scale=6))  # (satış - alış) × miktar
    net_kar          = db.Column(db.Numeric(precision=20, scale=6))  # brüt - stopaj - komisyon - diğer

    notlar           = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    # İlişkiler
    yatirim          = db.relationship('Yatirim', backref='satis_islemleri')
    user             = db.relationship('User', backref='satis_islemleri')

    def __repr__(self):
        return f'<SatisIslemi {self.yatirim_id} {self.satis_tarihi} x{self.satilan_miktar}>'

    def to_dict(self):
        return {
            'id': self.id,
            'yatirim_id': self.yatirim_id,
            'satis_tarihi': self.satis_tarihi.strftime('%Y-%m-%d'),
            'satis_fiyati': float(self.satis_fiyati),
            'satilan_miktar': float(self.satilan_miktar),
            'alis_fiyati_baz': float(self.alis_fiyati_baz),
            'komisyon': float(self.komisyon or 0),
            'diger_masraf': float(self.diger_masraf or 0),
            'stopaj_orani': float(self.stopaj_orani) if self.stopaj_orani else None,
            'stopaj_tutari': float(self.stopaj_tutari or 0),
            'brut_kar': float(self.brut_kar) if self.brut_kar else None,
            'net_kar': float(self.net_kar) if self.net_kar else None,
            'notlar': self.notlar,
        }
```

### M1b. Yatirim Modeline durum ve alis_komisyon Alanları Ekle

`models.py` içindeki `Yatirim` modeline ekle:

```python
durum           = db.Column(db.String(20), default='aktif', index=True)
# 'aktif' | 'tamamen_satildi'
# Kısmi satışlarda 'aktif' kalır, miktar azalır
# Tam satışta 'tamamen_satildi' olur, kayıt silinmez

alis_komisyon   = db.Column(db.Numeric(precision=20, scale=6), default=0)
# Alışta ödenen komisyon — mevcut kayıtlar 0 kalır, ileriye dönük kullanım
```

`to_dict()` metoduna ekle:
```python
'durum': self.durum,
'alis_komisyon': float(self.alis_komisyon or 0),
```

### M1c. Migration

```bash
flask db migrate -m "satis_islemi_tablosu_ve_yatirim_durum_alani"
flask db upgrade
```

Migration sonrası mevcut tüm `Yatirim` kayıtlarının `durum` alanını `'aktif'` olarak güncelle:
```python
# Migration script içine veya init_database() içine ekle:
Yatirim.query.filter(Yatirim.durum == None).update({'durum': 'aktif'})
db.session.commit()
```

---

## GÖREV M2: Satış Servisi (app.py)

`app.py` içine route'lardan önce şu servis fonksiyonlarını ekle:

### M2a. FIFO Alış Fiyatı Hesaplama

```python
def fifo_alis_fiyati_bul(yatirim_id, satilan_miktar):
    """
    FIFO mantığıyla satılacak miktara karşılık gelen ağırlıklı ortalama alış fiyatını bulur.
    Aynı kod için birden fazla alış kaydı varsa en eskiden başlar.

    Returns:
        dict: {
            'alis_fiyati_baz': Decimal,  # Ağırlıklı ortalama alış fiyatı
            'kullanilan_kayitlar': list  # Hangi alış kayıtları kullanıldı
        }
        None: Yeterli bakiye yoksa
    """
    yatirim = Yatirim.query.get(yatirim_id)
    if not yatirim:
        return None

    # Aynı kod ve tipteki aktif alışları tarihe göre sırala (en eski önce = FIFO)
    alis_kayitlari = Yatirim.query.filter_by(
        user_id=yatirim.user_id,
        kod=yatirim.kod,
        tip=yatirim.tip,
        durum='aktif'
    ).order_by(Yatirim.alis_tarihi.asc()).all()

    toplam_bakiye = sum(k.miktar for k in alis_kayitlari)
    if toplam_bakiye < satilan_miktar:
        return None  # Yeterli bakiye yok

    kalan_satis = satilan_miktar
    toplam_maliyet = Decimal('0')
    kullanilan = []

    for kayit in alis_kayitlari:
        if kalan_satis <= 0:
            break
        kullanilan_miktar = min(kayit.miktar, kalan_satis)
        toplam_maliyet += kayit.alis_fiyati * kullanilan_miktar
        kullanilan.append({
            'id': kayit.id,
            'alis_tarihi': kayit.alis_tarihi,
            'alis_fiyati': float(kayit.alis_fiyati),
            'kullanilan_miktar': float(kullanilan_miktar)
        })
        kalan_satis -= kullanilan_miktar

    alis_fiyati_baz = toplam_maliyet / satilan_miktar

    return {
        'alis_fiyati_baz': alis_fiyati_baz,
        'kullanilan_kayitlar': kullanilan
    }
```

### M2b. Satış Hesaplama Servisi

```python
def satis_hesapla(yatirim, satilan_miktar, satis_fiyati, satis_tarihi,
                  komisyon=None, diger_masraf=None, stopaj_manuel=None):
    """
    Satış işleminin tüm mali sonuçlarını hesaplar. DB'ye yazmaz, sadece hesaplar.
    Kullanıcıya onay öncesi özet göstermek için kullanılır.

    Returns:
        dict: Tüm hesaplanmış değerler ve özet
    """
    if satilan_miktar <= 0 or satis_fiyati <= 0:
        return {'hata': 'Geçersiz miktar veya fiyat'}

    if satilan_miktar > yatirim.miktar:
        return {'hata': f'Yetersiz bakiye. Mevcut: {yatirim.miktar}'}

    komisyon    = Decimal(str(komisyon or 0))
    diger_masraf = Decimal(str(diger_masraf or 0))

    # FIFO alış fiyatını bul
    fifo = fifo_alis_fiyati_bul(yatirim.id, satilan_miktar)
    alis_fiyati_baz = fifo['alis_fiyati_baz'] if fifo else yatirim.alis_fiyati

    # Brüt kar hesabı
    satis_tutari = satis_fiyati * satilan_miktar
    alis_tutari  = alis_fiyati_baz * satilan_miktar
    brut_kar     = satis_tutari - alis_tutari

    # Stopaj hesabı — fonlar için stopaj modülünden, diğerleri için 0
    stopaj_orani  = Decimal('0')
    stopaj_tutari = Decimal('0')

    if stopaj_manuel is not None:
        # Kullanıcı manuel girdiyse onu kullan
        stopaj_tutari = Decimal(str(stopaj_manuel))
        stopaj_orani  = (stopaj_tutari / brut_kar * 100) if brut_kar > 0 else Decimal('0')
    elif yatirim.tip == 'fon' and yatirim.fon_grubu:
        oran = stopaj_orani_bul(yatirim.fon_grubu, yatirim.alis_tarihi, satis_tarihi)
        if oran and brut_kar > 0:
            stopaj_orani  = oran
            stopaj_tutari = brut_kar * oran / 100

    # Net kar
    toplam_masraf = komisyon + diger_masraf + stopaj_tutari
    net_kar = brut_kar - toplam_masraf

    # Satış sonrası kalan miktar
    kalan_miktar = yatirim.miktar - satilan_miktar

    return {
        'alis_fiyati_baz'  : alis_fiyati_baz,
        'satis_tutari'     : satis_tutari,
        'alis_tutari'      : alis_tutari,
        'brut_kar'         : brut_kar,
        'stopaj_orani'     : stopaj_orani,
        'stopaj_tutari'    : stopaj_tutari,
        'komisyon'         : komisyon,
        'diger_masraf'     : diger_masraf,
        'toplam_masraf'    : toplam_masraf,
        'net_kar'          : net_kar,
        'kalan_miktar'     : kalan_miktar,
        'tam_satis_mi'     : kalan_miktar == 0,
        'fifo_detay'       : fifo['kullanilan_kayitlar'] if fifo else [],
    }
```

### M2c. Satışı Kaydetme Servisi

```python
def satis_kaydet(yatirim, satilan_miktar, satis_fiyati, satis_tarihi,
                 komisyon=0, diger_masraf=0, diger_masraf_aciklama='',
                 stopaj_tutari=0, stopaj_orani=0, stopaj_manuel_mi=False,
                 notlar='', fifo_mi=True):
    """
    Satış işlemini DB'ye kaydeder ve yatırım bakiyesini günceller.
    Bu fonksiyon çağrılmadan önce satis_hesapla() ile kullanıcıya özet gösterilmeli.
    """
    try:
        hesap = satis_hesapla(
            yatirim, satilan_miktar, satis_fiyati, satis_tarihi,
            komisyon, diger_masraf,
            stopaj_manuel=stopaj_tutari if stopaj_manuel_mi else None
        )

        if 'hata' in hesap:
            return False, hesap['hata']

        # SatisIslemi kaydı oluştur
        satis = SatisIslemi(
            yatirim_id            = yatirim.id,
            user_id               = yatirim.user_id,
            satis_tarihi          = satis_tarihi,
            satis_fiyati          = satis_fiyati,
            satilan_miktar        = satilan_miktar,
            alis_fiyati_baz       = hesap['alis_fiyati_baz'],
            fifo_mi               = fifo_mi,
            komisyon              = komisyon,
            diger_masraf          = diger_masraf,
            diger_masraf_aciklama = diger_masraf_aciklama,
            stopaj_orani          = hesap['stopaj_orani'],
            stopaj_tutari         = hesap['stopaj_tutari'],
            stopaj_manuel_mi      = stopaj_manuel_mi,
            brut_kar              = hesap['brut_kar'],
            net_kar               = hesap['net_kar'],
            notlar                = notlar,
        )
        db.session.add(satis)

        # Yatırım bakiyesini güncelle
        yatirim.miktar = hesap['kalan_miktar']
        if hesap['tam_satis_mi']:
            yatirim.durum = 'tamamen_satildi'

        db.session.commit()
        return True, satis

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Satış kaydetme hatası: {e}", exc_info=True)
        return False, str(e)
```

---

## GÖREV M3: Route'lar

### M3a. Satış Önizleme API'si

```python
@app.route('/api/satis_onizle/<int:yatirim_id>', methods=['POST'])
@login_required
def satis_onizle(yatirim_id):
    """
    Satış formundan gelen verilerle hesaplama yapar, DB'ye yazmaz.
    Kullanıcıya onay öncesi özet göstermek için kullanılır.
    """
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    if yatirim.user_id != current_user.id:
        return jsonify({'error': 'Yetkisiz erişim'}), 403

    data = request.get_json()

    try:
        satilan_miktar = Decimal(str(data['satilan_miktar']))
        satis_fiyati   = Decimal(str(data['satis_fiyati']))
        satis_tarihi   = datetime.strptime(data['satis_tarihi'], '%Y-%m-%d')
        komisyon       = Decimal(str(data.get('komisyon', 0)))
        diger_masraf   = Decimal(str(data.get('diger_masraf', 0)))
        stopaj_manuel  = Decimal(str(data['stopaj_manuel'])) if data.get('stopaj_manuel_mi') else None

        hesap = satis_hesapla(
            yatirim, satilan_miktar, satis_fiyati, satis_tarihi,
            komisyon, diger_masraf, stopaj_manuel
        )

        if 'hata' in hesap:
            return jsonify({'success': False, 'error': hesap['hata']}), 400

        # Decimal'leri float'a çevir
        return jsonify({
            'success'         : True,
            'alis_fiyati_baz' : float(hesap['alis_fiyati_baz']),
            'satis_tutari'    : float(hesap['satis_tutari']),
            'alis_tutari'     : float(hesap['alis_tutari']),
            'brut_kar'        : float(hesap['brut_kar']),
            'stopaj_orani'    : float(hesap['stopaj_orani']),
            'stopaj_tutari'   : float(hesap['stopaj_tutari']),
            'komisyon'        : float(hesap['komisyon']),
            'diger_masraf'    : float(hesap['diger_masraf']),
            'toplam_masraf'   : float(hesap['toplam_masraf']),
            'net_kar'         : float(hesap['net_kar']),
            'kalan_miktar'    : float(hesap['kalan_miktar']),
            'tam_satis_mi'    : hesap['tam_satis_mi'],
            'fifo_detay'      : hesap['fifo_detay'],
            'mevcut_miktar'   : float(yatirim.miktar),
        })

    except (InvalidOperation, ValueError) as e:
        return jsonify({'success': False, 'error': f'Geçersiz değer: {str(e)}'}), 400


```

### M3b. Satışı Kaydet Route'u

```python
@app.route('/satis_yap/<int:yatirim_id>', methods=['POST'])
@login_required
def satis_yap(yatirim_id):
    """Satış işlemini onaylayıp kaydeder."""
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    if yatirim.user_id != current_user.id:
        flash('Bu yatırıma erişim yetkiniz yok!', 'danger')
        return redirect(url_for('yatirimlar'))

    try:
        satilan_miktar        = Decimal(request.form['satilan_miktar'].replace(',', '.'))
        satis_fiyati          = Decimal(request.form['satis_fiyati'].replace(',', '.'))
        satis_tarihi          = datetime.strptime(request.form['satis_tarihi'], '%Y-%m-%d')
        komisyon              = Decimal(request.form.get('komisyon', '0').replace(',', '.'))
        diger_masraf          = Decimal(request.form.get('diger_masraf', '0').replace(',', '.'))
        diger_masraf_aciklama = request.form.get('diger_masraf_aciklama', '')
        stopaj_tutari         = Decimal(request.form.get('stopaj_tutari', '0').replace(',', '.'))
        stopaj_manuel_mi      = request.form.get('stopaj_manuel_mi') == 'true'
        notlar                = request.form.get('notlar', '')

        basarili, sonuc = satis_kaydet(
            yatirim               = yatirim,
            satilan_miktar        = satilan_miktar,
            satis_fiyati          = satis_fiyati,
            satis_tarihi          = satis_tarihi,
            komisyon              = komisyon,
            diger_masraf          = diger_masraf,
            diger_masraf_aciklama = diger_masraf_aciklama,
            stopaj_tutari         = stopaj_tutari,
            stopaj_manuel_mi      = stopaj_manuel_mi,
            notlar                = notlar,
        )

        if basarili:
            if yatirim.durum == 'tamamen_satildi':
                flash(f'{yatirim.kod} tamamen satıldı. Net kâr: ₺{float(sonuc.net_kar):+,.2f}', 'success')
            else:
                flash(f'{yatirim.kod} kısmi satış tamamlandı. Kalan: {float(yatirim.miktar):,.4f}', 'success')
        else:
            flash(f'Satış hatası: {sonuc}', 'danger')

    except Exception as e:
        flash(f'Satış işlemi sırasında hata: {str(e)}', 'danger')

    return redirect(url_for('yatirimlar'))
```

### M3c. Satış Geçmişi Sayfası

```python
@app.route('/satislar')
@login_required
def satislar():
    """Tüm satış işlemlerinin geçmiş sayfası."""
    tip_filter      = request.args.get('tip', '')
    tarih_baslangic = request.args.get('tarih_baslangic', '')
    tarih_bitis     = request.args.get('tarih_bitis', '')

    query = db.session.query(SatisIslemi).join(Yatirim).filter(
        SatisIslemi.user_id == current_user.id
    )

    if tip_filter:
        query = query.filter(Yatirim.tip == tip_filter)
    if tarih_baslangic:
        query = query.filter(SatisIslemi.satis_tarihi >= datetime.strptime(tarih_baslangic, '%Y-%m-%d'))
    if tarih_bitis:
        query = query.filter(SatisIslemi.satis_tarihi <= datetime.strptime(tarih_bitis, '%Y-%m-%d'))

    satislar_listesi = query.order_by(SatisIslemi.satis_tarihi.desc()).all()

    # Özet istatistikler
    toplam_brut_kar   = sum(float(s.brut_kar or 0)    for s in satislar_listesi)
    toplam_net_kar    = sum(float(s.net_kar or 0)     for s in satislar_listesi)
    toplam_stopaj     = sum(float(s.stopaj_tutari or 0) for s in satislar_listesi)
    toplam_komisyon   = sum(float(s.komisyon or 0)    for s in satislar_listesi)
    toplam_masraf     = sum(float(s.diger_masraf or 0) for s in satislar_listesi)

    return render_template(
        'satislar.html',
        satislar        = satislar_listesi,
        toplam_brut_kar = toplam_brut_kar,
        toplam_net_kar  = toplam_net_kar,
        toplam_stopaj   = toplam_stopaj,
        toplam_komisyon = toplam_komisyon,
        toplam_masraf   = toplam_masraf,
        tip_filter      = tip_filter,
    )
```

---

## GÖREV M4: Satış Modal'ı (yatirimlar.html)

Her yatırım satırına "Sat" butonu ekle. Tek bir ortak modal kullanılacak, JS ile doldurulacak.

### Sat Butonu

Mevcut işlem butonlarının yanına ekle (sadece `durum='aktif'` olan yatırımlar için):

```html
{% if grup.tip in ['fon', 'altin', 'doviz'] %}
<button class="btn btn-outline-danger btn-sm"
        onclick="satisModalAc('{{ grup.kod }}', '{{ grup.tip }}')"
        title="Sat">
    <i class="fas fa-hand-holding-usd"></i>
</button>
{% endif %}
```

### Satış Modal'ı HTML

```html
<div class="modal fade" id="satisModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">
          <i class="fas fa-hand-holding-usd me-2"></i>
          Satış Yap — <span id="satisModalBaslik"></span>
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>

      <div class="modal-body">
        <!-- Adım 1: Form -->
        <div id="satisForm">
          <div class="row g-3">
            <div class="col-md-6">
              <label class="form-label">Mevcut Bakiye</label>
              <input type="text" class="form-control" id="mevcutMiktar" readonly>
            </div>
            <div class="col-md-6">
              <label class="form-label">Satılacak Miktar *</label>
              <input type="number" class="form-control" id="satisMiktar"
                     step="0.000001" min="0.000001">
              <div class="form-text">Tamamını sat:
                <a href="#" onclick="tamaminiSat()">Tümünü seç</a>
              </div>
            </div>
            <div class="col-md-6">
              <label class="form-label">Satış Tarihi *</label>
              <input type="date" class="form-control" id="satisTarihi">
            </div>
            <div class="col-md-6">
              <label class="form-label">Satış Fiyatı (₺) *</label>
              <input type="number" class="form-control" id="satisFiyati"
                     step="0.000001" min="0">
              <div class="form-text">
                <a href="#" onclick="guncelFiyatiKullan()">Güncel fiyatı kullan</a>
              </div>
            </div>

            <!-- Komisyon — fon ve hisse için göster -->
            <div class="col-md-6" id="komisyonAlani">
              <label class="form-label">Komisyon (₺)</label>
              <input type="number" class="form-control" id="satisKomisyon"
                     step="0.01" min="0" value="0">
            </div>

            <!-- Diğer Masraflar — tüm tipler için -->
            <div class="col-md-6">
              <label class="form-label">Diğer Masraflar (₺)</label>
              <input type="number" class="form-control" id="digerMasraf"
                     step="0.01" min="0" value="0">
            </div>
            <div class="col-12" id="digerMasrafAciklamaAlani" style="display:none;">
              <label class="form-label">Masraf Açıklaması</label>
              <input type="text" class="form-control" id="digerMasrafAciklama"
                     placeholder="Örn: Saklama ücreti, havale masrafı...">
            </div>

            <!-- Stopaj — sadece fon için, otomatik hesaplanır -->
            <div class="col-12" id="stopajAlani" style="display:none;">
              <div class="card border-warning">
                <div class="card-body py-2">
                  <div class="row align-items-center">
                    <div class="col-md-4">
                      <label class="form-label mb-0">Stopaj Oranı (%)</label>
                      <input type="number" class="form-control form-control-sm"
                             id="stopajOrani" readonly step="0.01">
                    </div>
                    <div class="col-md-4">
                      <label class="form-label mb-0">Stopaj Tutarı (₺)</label>
                      <input type="number" class="form-control form-control-sm"
                             id="stopajTutari" step="0.01" min="0">
                    </div>
                    <div class="col-md-4 d-flex align-items-end">
                      <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="stopajManuelMi">
                        <label class="form-check-label" for="stopajManuelMi">
                          <small>Manuel düzelt</small>
                        </label>
                      </div>
                    </div>
                  </div>
                  <small class="text-muted">
                    Otomatik hesaplandı. Gerçek tutardan farklıysa "Manuel düzelt" ile değiştir.
                  </small>
                </div>
              </div>
            </div>

            <div class="col-12">
              <label class="form-label">Notlar</label>
              <textarea class="form-control" id="satisNotlar" rows="2"></textarea>
            </div>
          </div>

          <div class="mt-3 text-end">
            <button type="button" class="btn btn-primary" onclick="satisOnizle()">
              <i class="fas fa-calculator me-2"></i>Hesapla ve Önizle
            </button>
          </div>
        </div>

        <!-- Adım 2: Özet (hesapla'ya basınca görünür) -->
        <div id="satisOzet" style="display:none;">
          <div class="alert alert-info">
            <h6 class="alert-heading">Satış Özeti</h6>
            <div class="row g-2">
              <div class="col-6"><small class="text-muted">Satış Tutarı</small>
                <div class="fw-bold" id="ozet_satis_tutari"></div></div>
              <div class="col-6"><small class="text-muted">Alış Maliyeti</small>
                <div class="fw-bold" id="ozet_alis_tutari"></div></div>
              <div class="col-6"><small class="text-muted">Brüt Kâr/Zarar</small>
                <div class="fw-bold" id="ozet_brut_kar"></div></div>
              <div class="col-6"><small class="text-muted">Stopaj</small>
                <div class="fw-bold text-warning" id="ozet_stopaj"></div></div>
              <div class="col-6"><small class="text-muted">Komisyon + Masraf</small>
                <div class="fw-bold text-warning" id="ozet_masraf"></div></div>
              <div class="col-6"><small class="text-muted">Kalan Bakiye</small>
                <div class="fw-bold" id="ozet_kalan"></div></div>
            </div>
            <hr>
            <div class="d-flex justify-content-between align-items-center">
              <span class="fs-6">NET KÂR / ZARAR</span>
              <span class="fs-4 fw-bold" id="ozet_net_kar"></span>
            </div>
          </div>

          <!-- FIFO detay — birden fazla alış kaydı kullanıldıysa -->
          <div id="fifoDetayAlani" style="display:none;">
            <small class="text-muted">FIFO — Kullanılan alış kayıtları:</small>
            <div id="fifoDetay" class="small"></div>
          </div>

          <div class="alert alert-warning mt-2 py-2">
            <small><i class="fas fa-exclamation-triangle me-1"></i>
            Bu hesaplama tahminidir. Stopaj aracı kurum tarafından kesilir.</small>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">İptal</button>
        <button type="button" class="btn btn-outline-primary" id="geriDonBtn"
                onclick="satisGeriDon()" style="display:none;">
          <i class="fas fa-arrow-left me-1"></i>Geri
        </button>
        <form id="satisOnayForm" method="POST" style="display:none;">
          <input type="hidden" name="satilan_miktar"        id="form_satilan_miktar">
          <input type="hidden" name="satis_fiyati"          id="form_satis_fiyati">
          <input type="hidden" name="satis_tarihi"          id="form_satis_tarihi">
          <input type="hidden" name="komisyon"              id="form_komisyon">
          <input type="hidden" name="diger_masraf"          id="form_diger_masraf">
          <input type="hidden" name="diger_masraf_aciklama" id="form_diger_masraf_aciklama">
          <input type="hidden" name="stopaj_tutari"         id="form_stopaj_tutari">
          <input type="hidden" name="stopaj_manuel_mi"      id="form_stopaj_manuel_mi">
          <input type="hidden" name="notlar"                id="form_notlar">
          <button type="submit" class="btn btn-danger">
            <i class="fas fa-check me-2"></i>Satışı Onayla
          </button>
        </form>
      </div>
    </div>
  </div>
</div>
```

### Satış Modal'ı JavaScript

```javascript
let aktifYatirimId = null;
let aktifYatirimTip = null;
let aktifGuncelFiyat = null;
let aktifMevcut = null;

function satisModalAc(kod, tip) {
    // Grubun ilk aktif kalemini bul
    fetch(`/api/yatirim_grup/${kod}`)
        .then(r => r.json())
        .then(data => {
            const ilkKalem = data.kalemler[0];
            aktifYatirimId   = ilkKalem.id;
            aktifYatirimTip  = tip;
            aktifGuncelFiyat = ilkKalem.guncel_fiyat;
            aktifMevcut      = data.kalemler.reduce((s, k) => s + k.miktar, 0);

            document.getElementById('satisModalBaslik').textContent = kod;
            document.getElementById('mevcutMiktar').value = aktifMevcut.toFixed(6);
            document.getElementById('satisTarihi').value  = new Date().toISOString().split('T')[0];

            // Tip bazlı alan görünürlüğü
            document.getElementById('komisyonAlani').style.display =
                ['fon', 'hisse'].includes(tip) ? '' : 'none';
            document.getElementById('stopajAlani').style.display =
                tip === 'fon' ? '' : 'none';

            // Formu sıfırla
            satisGeriDon();
            new bootstrap.Modal(document.getElementById('satisModal')).show();
        });
}

function guncelFiyatiKullan() {
    if (aktifGuncelFiyat)
        document.getElementById('satisFiyati').value = aktifGuncelFiyat.toFixed(6);
}

function tamaminiSat() {
    document.getElementById('satisMiktar').value = aktifMevcut.toFixed(6);
}

function satisOnizle() {
    const payload = {
        satilan_miktar  : document.getElementById('satisMiktar').value,
        satis_fiyati    : document.getElementById('satisFiyati').value,
        satis_tarihi    : document.getElementById('satisTarihi').value,
        komisyon        : document.getElementById('satisKomisyon')?.value || 0,
        diger_masraf    : document.getElementById('digerMasraf').value,
        stopaj_manuel_mi: document.getElementById('stopajManuelMi')?.checked || false,
        stopaj_manuel   : document.getElementById('stopajManuelMi')?.checked
                          ? document.getElementById('stopajTutari').value : null,
    };

    fetch(`/api/satis_onizle/${aktifYatirimId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) { alert(data.error); return; }

        const fmt = v => '₺' + parseFloat(v).toLocaleString('tr-TR', {minimumFractionDigits:2});
        const karRenk = v => parseFloat(v) >= 0 ? 'text-success' : 'text-danger';

        document.getElementById('ozet_satis_tutari').textContent = fmt(data.satis_tutari);
        document.getElementById('ozet_alis_tutari').textContent  = fmt(data.alis_tutari);

        const brutEl = document.getElementById('ozet_brut_kar');
        brutEl.textContent  = fmt(data.brut_kar);
        brutEl.className    = 'fw-bold ' + karRenk(data.brut_kar);

        document.getElementById('ozet_stopaj').textContent  =
            `₺${parseFloat(data.stopaj_tutari).toFixed(2)} (%${data.stopaj_orani})`;
        document.getElementById('ozet_masraf').textContent  =
            fmt(data.komisyon + data.diger_masraf);
        document.getElementById('ozet_kalan').textContent   =
            parseFloat(data.kalan_miktar).toFixed(6) + (data.tam_satis_mi ? ' (Tam Satış)' : '');

        const netEl = document.getElementById('ozet_net_kar');
        netEl.textContent = fmt(data.net_kar);
        netEl.className   = 'fs-4 fw-bold ' + karRenk(data.net_kar);

        // FIFO detay
        if (data.fifo_detay && data.fifo_detay.length > 1) {
            document.getElementById('fifoDetayAlani').style.display = '';
            document.getElementById('fifoDetay').innerHTML =
                data.fifo_detay.map(f =>
                    `<span class="me-3">${f.alis_tarihi.split('T')[0]}: 
                     ${f.kullanilan_miktar} adet × ₺${f.alis_fiyati}</span>`
                ).join('');
        }

        // Form hidden alanlarını doldur
        document.getElementById('form_satilan_miktar').value        = payload.satilan_miktar;
        document.getElementById('form_satis_fiyati').value          = payload.satis_fiyati;
        document.getElementById('form_satis_tarihi').value          = payload.satis_tarihi;
        document.getElementById('form_komisyon').value              = payload.komisyon;
        document.getElementById('form_diger_masraf').value          = payload.diger_masraf;
        document.getElementById('form_diger_masraf_aciklama').value =
            document.getElementById('digerMasrafAciklama')?.value || '';
        document.getElementById('form_stopaj_tutari').value         = data.stopaj_tutari;
        document.getElementById('form_stopaj_manuel_mi').value      = payload.stopaj_manuel_mi;
        document.getElementById('form_notlar').value                =
            document.getElementById('satisNotlar').value;

        document.getElementById('satisOnayForm').action = `/satis_yap/${aktifYatirimId}`;

        // Adım 2'ye geç
        document.getElementById('satisForm').style.display  = 'none';
        document.getElementById('satisOzet').style.display  = '';
        document.getElementById('satisOnayForm').style.display = '';
        document.getElementById('geriDonBtn').style.display = '';
    });
}

function satisGeriDon() {
    document.getElementById('satisForm').style.display   = '';
    document.getElementById('satisOzet').style.display   = 'none';
    document.getElementById('satisOnayForm').style.display = 'none';
    document.getElementById('geriDonBtn').style.display  = 'none';
}

// Diğer masraf girilince açıklama alanını göster
document.getElementById('digerMasraf')?.addEventListener('input', function() {
    document.getElementById('digerMasrafAciklamaAlani').style.display =
        parseFloat(this.value) > 0 ? '' : 'none';
});
```

---

## GÖREV M5: Satış Geçmişi Sayfası (satislar.html)

`templates/satislar.html` oluştur, `{% extends "base.html" %}` kullan.

**Sayfa yapısı:**

**Üst — Özet Kartlar (5 kart):**
- Toplam Satış Adedi
- Toplam Brüt Kâr
- Toplam Stopaj Kesintisi (kırmızı)
- Toplam Komisyon + Masraf (sarı)
- Toplam Net Kâr (büyük, yeşil/kırmızı)

**Filtre Alanı:**
- Tip filtresi (fon/hisse/altın/döviz)
- Tarih aralığı (başlangıç - bitiş)

**Satış Tablosu:**

| Sütun | Açıklama |
|---|---|
| Tarih | Satış tarihi |
| Kod / İsim | Yatırım kodu |
| Tip | fon/altın/döviz badge |
| Satılan Miktar | |
| Alış Fiyatı | FIFO bazlı |
| Satış Fiyatı | |
| Brüt Kâr | Yeşil/kırmızı |
| Stopaj | |
| Komisyon + Masraf | |
| Net Kâr | Büyük, belirgin |

---

## GÖREV M6: Navigasyona Ekle

`templates/base.html` navbar'a ekle (Stopaj linkinden sonra):

```html
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('satislar') }}">
        <i class="fas fa-history me-1"></i>Satış Geçmişi
    </a>
</li>
```

---

## GÖREV M7: Satış Geri Alma (İptal) Özelliği

Yanlışlıkla yapılan satışları geri almak için. Satış kaydı silinmez, `iptal_edildi=True` olarak işaretlenir ve yatırım bakiyesi eski haline döner.

### M7a. SatisIslemi Modeline iptal Alanları Ekle

`models.py` içindeki `SatisIslemi` modeline ekle:

```python
iptal_edildi     = db.Column(db.Boolean, default=False, index=True)
iptal_tarihi     = db.Column(db.DateTime, nullable=True)
iptal_notu       = db.Column(db.String(200), nullable=True)
```

### M7b. Satış Geri Alma Route'u

`app.py` içine ekle:

```python
@app.route('/satis_geri_al/<int:satis_id>', methods=['POST'])
@login_required
def satis_geri_al(satis_id):
    """
    Bir satış işlemini geri alır.
    Satış kaydı silinmez, iptal_edildi=True olarak işaretlenir.
    Yatırım bakiyesi ve durumu eski haline döner.
    """
    satis = SatisIslemi.query.get_or_404(satis_id)

    if satis.user_id != current_user.id:
        flash('Bu işleme erişim yetkiniz yok!', 'danger')
        return redirect(url_for('satislar'))

    if satis.iptal_edildi:
        flash('Bu satış zaten iptal edilmiş.', 'warning')
        return redirect(url_for('satislar'))

    try:
        yatirim = Yatirim.query.get(satis.yatirim_id)
        if not yatirim:
            flash('İlgili yatırım kaydı bulunamadı.', 'danger')
            return redirect(url_for('satislar'))

        iptal_notu = request.form.get('iptal_notu', '')

        # Satışı iptal et
        satis.iptal_edildi = True
        satis.iptal_tarihi = datetime.now()
        satis.iptal_notu   = iptal_notu

        # Yatırım bakiyesini geri yükle
        yatirim.miktar += satis.satilan_miktar

        # Eğer tamamen satılmış durumdaysa aktif'e döndür
        if yatirim.durum == 'tamamen_satildi':
            yatirim.durum = 'aktif'

        db.session.commit()

        flash(
            f'{yatirim.kod} için {satis.satis_tarihi.strftime("%d.%m.%Y")} '
            f'tarihli satış geri alındı. Bakiye güncellendi.',
            'success'
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Satış geri alma hatası: {e}", exc_info=True)
        flash(f'Geri alma işlemi başarısız: {str(e)}', 'danger')

    return redirect(url_for('satislar'))
```

### M7c. Satışlar Sayfasına Geri Al Butonu ve İptal Edilmiş Satışların Gösterimi

`satislar()` route'unda sorguya filtre ekle — iptal edilmiş satışlar varsayılan olarak gizlensin, toggle ile gösterilebilsin:

```python
goster_iptal = request.args.get('iptal', 'false') == 'true'

if not goster_iptal:
    query = query.filter(SatisIslemi.iptal_edildi == False)
```

`templates/satislar.html` tablosuna her satır için ekle:

```html
{% if not satis.iptal_edildi %}
  <!-- Geri Al butonu -->
  <button type="button" class="btn btn-outline-warning btn-sm"
          data-bs-toggle="modal"
          data-bs-target="#geriAlModal{{ satis.id }}"
          title="Satışı Geri Al">
      <i class="fas fa-undo"></i>
  </button>

  <!-- Geri Al Onay Modal'ı -->
  <div class="modal fade" id="geriAlModal{{ satis.id }}" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title text-warning">
            <i class="fas fa-undo me-2"></i>Satışı Geri Al
          </h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <form method="POST" action="{{ url_for('satis_geri_al', satis_id=satis.id) }}">
          <div class="modal-body">
            <p>
              <strong>{{ satis.yatirim.kod }}</strong> —
              {{ satis.satis_tarihi.strftime('%d.%m.%Y') }} tarihli
              {{ satis.satilan_miktar }} adet satış geri alınacak.
            </p>
            <p class="text-muted small">
              Yatırım bakiyenize <strong>{{ satis.satilan_miktar }}</strong> adet
              geri eklenecek. Satış kaydı silinmez, iptal olarak işaretlenir.
            </p>
            <div class="mb-3">
              <label class="form-label">İptal Notu (isteğe bağlı)</label>
              <input type="text" class="form-control" name="iptal_notu"
                     placeholder="Örn: Yanlış işlem, sistem hatası...">
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary"
                    data-bs-dismiss="modal">Vazgeç</button>
            <button type="submit" class="btn btn-warning">
              <i class="fas fa-undo me-2"></i>Geri Al
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>

{% else %}
  <!-- İptal edilmiş satış gösterimi -->
  <span class="badge bg-secondary">
    <i class="fas fa-ban me-1"></i>İptal
  </span>
  {% if satis.iptal_notu %}
    <small class="text-muted d-block">{{ satis.iptal_notu }}</small>
  {% endif %}
{% endif %}
```

Sayfanın üstüne iptal göster/gizle toggle ekle:

```html
<div class="form-check form-switch d-inline-block ms-3">
  <input class="form-check-input" type="checkbox" id="iptalGoster"
         onchange="window.location.href='?iptal=' + this.checked"
         {{ 'checked' if request.args.get('iptal') == 'true' }}>
  <label class="form-check-label" for="iptalGoster">
    <small>İptal edilenleri göster</small>
  </label>
</div>
```

### M7d. Özet Kartlarda İptal Edilenleri Hariç Tut

`satislar()` route'undaki özet hesaplamalarda iptal edilmiş satışları dahil etme:

```python
# Sadece aktif (iptal edilmemiş) satışlar üzerinden hesapla
aktif_satislar = [s for s in satislar_listesi if not s.iptal_edildi]

toplam_brut_kar = sum(float(s.brut_kar   or 0) for s in aktif_satislar)
toplam_net_kar  = sum(float(s.net_kar    or 0) for s in aktif_satislar)
toplam_stopaj   = sum(float(s.stopaj_tutari or 0) for s in aktif_satislar)
toplam_komisyon = sum(float(s.komisyon   or 0) for s in aktif_satislar)
toplam_masraf   = sum(float(s.diger_masraf or 0) for s in aktif_satislar)
```

---

## Test Senaryoları

```
1. Kısmi satış:
   → 100 adet ZBJ'den 40 adet sat
   → Kalan bakiye 60 olmalı, yatırım 'aktif' kalmalı
   → Satış geçmişinde 1 kayıt görünmeli

2. Tam satış:
   → Kalan 60 adedi sat
   → Yatırım portföyde görünmemeli (durum='tamamen_satildi')
   → /satislar sayfasında 2 kayıt görünmeli

3. FIFO testi:
   → Aynı fondan farklı tarihlerde 2 alış yap (farklı fiyat)
   → Kısmi satış yap
   → Özet'te FIFO detay alanı çıkmalı, en eski alış kaydı kullanılmalı

4. Stopaj testi (fon):
   → Grup B fon, 2024-01-15 alış tarihli
   → Satış önizlemesinde %0 stopaj görünmeli
   → Grup B fon, 2025-08-01 alış tarihli
   → Satış önizlemesinde %17.5 stopaj görünmeli

5. Stopaj manuel düzeltme:
   → "Manuel düzelt" checkbox'ı işaretle
   → Stopaj tutarını değiştir
   → Kayıtta stopaj_manuel_mi=True olmalı

6. Altın satışı:
   → Stopaj alanı görünmemeli
   → Komisyon alanı görünmemeli
   → Sadece "Diğer Masraflar" alanı olmalı

7. PDF raporu:
   → Satış geçmişi PDF'e eklenmeli (isteğe bağlı, sonraki faz)
```

---

## Bilinen Kısıtlamalar

1. **Alış komisyonu:** `alis_komisyon` alanı eklendi ama mevcut kayıtlar 0. Gerçek maliyet hesabında kullanılmıyor — ileriye dönük.
2. **FIFO çoklu alış:** Aynı koddan farklı tarihlerde alış varsa FIFO doğru çalışır. Ama `Yatirim.miktar` güncellenirken en eski kayıt önce tükenir — bu mantık `satis_kaydet()` içinde henüz tam implement edilmedi, M2c sonrası test ederek tamamlanmalı.
3. **Hisse satışı:** Şu an hisse için komisyon alanı var ama stopaj yok. İleride eklenebilir.
4. **BES fonları:** Emeklilik fonları için stopaj farklı — bu fonlar için uyarı gösterilmeli.

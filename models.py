from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from decimal import Decimal

# Initialize db here to avoid circular imports
db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    yatirimlar = db.relationship('Yatirim', backref='user', lazy=True, cascade='all, delete-orphan')
    fiyat_gecmisleri = db.relationship('FiyatGecmisi', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'

class Yatirim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tip = db.Column(db.String(20), nullable=False)  # 'fon', 'hisse', 'altin', 'doviz'
    kod = db.Column(db.String(30), nullable=False, index=True)  # Yatırım kodu (USDTRY, XU100, vb.)
    isim = db.Column(db.String(100))
    alis_tarihi = db.Column(db.DateTime, nullable=False)
    alis_fiyati = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    miktar = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    guncel_fiyat = db.Column(db.Numeric(precision=20, scale=6))
    guncel_alis_fiyat = db.Column(db.Numeric(precision=20, scale=6))  # Alış fiyatı (Altın/Döviz için)
    guncel_satis_fiyat = db.Column(db.Numeric(precision=20, scale=6))  # Satış fiyatı (Altın/Döviz için)
    son_guncelleme = db.Column(db.DateTime)
    notlar = db.Column(db.Text)
    kategori = db.Column(db.String(30))
    durum = db.Column(db.String(20), default='aktif', index=True)
    # 'aktif' | 'tamamen_satildi'
    # Kısmi satışlarda 'aktif' kalır, miktar azalır
    # Tam satışta 'tamamen_satildi' olur, kayıt silinmez
    alis_komisyon = db.Column(db.Numeric(precision=20, scale=6), default=0)
    # Alışta ödenen komisyon — mevcut kayıtlar 0 kalır, ileriye dönük kullanım

    # Fon bilgisi alanlari - sadece tip='fon' icin kullanilir
    fon_grubu = db.Column(db.String(1), nullable=True)  # 'A','B','C','D' - stopaj grubu
    fon_tur_kodu = db.Column(db.String(10), nullable=True)  # TEFAS FONTURKOD
    semsiye_fon_turu = db.Column(db.String(10), nullable=True)  # TEFAS FONTUR
    fon_unvan_tipi = db.Column(db.String(100), nullable=True)  # Tam unvan tipi aciklamasi
    kurucu_kodu = db.Column(db.String(20), nullable=True)  # Portfoy yoneticisi/kurucu kodu
    fon_grubu_otomatik = db.Column(db.Boolean, default=False)  # True=TEFAS'tan otomatik, False=manuel
    fon_bilgi_guncelleme = db.Column(db.DateTime, nullable=True)  # Son fon bilgisi guncelleme tarihi
  # Opsiyonel kategori alanı
    
    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    def __repr__(self):
        return f'<Yatirim {self.tip} {self.kod}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'tip': self.tip,
            'kod': self.kod,
            'isim': self.isim,
            'alis_tarihi': self.alis_tarihi.strftime('%Y-%m-%d'),
            'alis_fiyati': float(self.alis_fiyati),
            'miktar': float(self.miktar),
            'guncel_fiyat': float(self.guncel_fiyat) if self.guncel_fiyat else None,
            'son_guncelleme': self.son_guncelleme.strftime('%Y-%m-%d %H:%M') if self.son_guncelleme else None,
            'notlar': self.notlar,
            'kategori': self.kategori,
            'durum': self.durum,
            'alis_komisyon': float(self.alis_komisyon or 0),

            'fon_grubu': self.fon_grubu,
            'fon_tur_kodu': self.fon_tur_kodu,
            'semsiye_fon_turu': self.semsiye_fon_turu,
            'fon_unvan_tipi': self.fon_unvan_tipi,
            'kurucu_kodu': self.kurucu_kodu,
            'fon_grubu_otomatik': self.fon_grubu_otomatik,
            'alis_tutari': float(self.alis_fiyati * self.miktar),
            'guncel_tutar': float(self.guncel_fiyat * self.miktar) if self.guncel_fiyat else None,
            'kar_zarar_tl': float((self.guncel_fiyat - self.alis_fiyati) * self.miktar) if self.guncel_fiyat else None,
            'kar_zarar_yuzde': float((self.guncel_fiyat / self.alis_fiyati - 1) * 100) if self.guncel_fiyat else None
        }


class StopajOrani(db.Model):
    """
    Fon grubuna ve alış tarihine göre stopaj oranlarını tutar.
    Yeni mevzuat değişikliklerinde yalnızca bu tabloya satır eklenir.
    """
    id = db.Column(db.Integer, primary_key=True)
    fon_grubu = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', 'D'
    donem_baslangic = db.Column(db.Date, nullable=False)  # Bu tarih ve sonrasında alınanlar
    donem_bitis = db.Column(db.Date, nullable=True)  # None = hâlâ geçerli
    elde_tutma_gun = db.Column(db.Integer, nullable=True)  # None = süre şartı yok
    oran = db.Column(db.Numeric(5, 2), nullable=False)  # Yüzde olarak: 17.50, 10.00, 0.00
    aciklama = db.Column(db.String(200))  # İsteğe bağlı not

    def __repr__(self):
        return f'<StopajOrani Grup:{self.fon_grubu} {self.donem_baslangic} %{self.oran}>'


class SatisIslemi(db.Model):
    """
    Her satış işlemi bir kayıt olarak saklanır.
    Kısmi satışlarda aynı yatirim_id'ye birden fazla kayıt olabilir.
    Tam satışlarda Yatirim.durum='tamamen_satildi' olur ama kayıt silinmez.
    """
    id = db.Column(db.Integer, primary_key=True)
    yatirim_id = db.Column(db.Integer, db.ForeignKey('yatirim.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    satis_tarihi = db.Column(db.DateTime, nullable=False)
    satis_fiyati = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    satilan_miktar = db.Column(db.Numeric(precision=20, scale=6), nullable=False)

    # Maliyet — FIFO veya manuel seçimle belirlenen alış fiyatı
    alis_fiyati_baz = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    fifo_mi = db.Column(db.Boolean, default=True)

    # Masraflar
    komisyon = db.Column(db.Numeric(precision=20, scale=6), default=0)
    diger_masraf = db.Column(db.Numeric(precision=20, scale=6), default=0)
    diger_masraf_aciklama = db.Column(db.String(200))

    # Stopaj — otomatik hesaplanır, kullanıcı düzeltebilir
    stopaj_orani = db.Column(db.Numeric(5, 2))
    stopaj_tutari = db.Column(db.Numeric(precision=20, scale=6), default=0)
    stopaj_manuel_mi = db.Column(db.Boolean, default=False)

    # Hesaplanmış sonuçlar
    brut_kar = db.Column(db.Numeric(precision=20, scale=6))
    net_kar = db.Column(db.Numeric(precision=20, scale=6))

    notlar = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # İlişkiler
    yatirim = db.relationship('Yatirim', backref='satis_islemleri')
    user = db.relationship('User', backref='satis_islemleri')

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


class FiyatGecmisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    yatirim_id = db.Column(db.Integer, db.ForeignKey('yatirim.id'), nullable=False, index=True)
    tarih = db.Column(db.DateTime, nullable=False, index=True)
    fiyat = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    
    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for migration
    
    def __repr__(self):
        return f'<FiyatGecmisi {self.yatirim_id} {self.tarih}>'

class PaylasilanPortfoy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(200), nullable=False)
    aciklama = db.Column(db.Text)
    paylasin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    view_count = db.Column(db.Integer, default=0)
    
    # Relationships
    paylasin = db.relationship('User', foreign_keys=[paylasin_id], backref='paylasilan_portfoyler')
    
    def __repr__(self):
        return f'<PaylasilanPortfoy {self.baslik}>'

class PaylasilanYatirim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    portfoy_id = db.Column(db.Integer, db.ForeignKey('paylasilan_portfoy.id'), nullable=False)
    tip = db.Column(db.String(20), nullable=False)
    kod = db.Column(db.String(30), nullable=False)
    isim = db.Column(db.String(100))
    alis_tarihi = db.Column(db.DateTime, nullable=False)
    alis_fiyati = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    miktar = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    notlar = db.Column(db.Text)
    kategori = db.Column(db.String(30))
    
    # Relationships
    portfoy = db.relationship('PaylasilanPortfoy', backref='yatirimlar')
    
    def __repr__(self):
        return f'<PaylasilanYatirim {self.kod}>'

class PortfoyTakip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    takip_eden_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    portfoy_id = db.Column(db.Integer, db.ForeignKey('paylasilan_portfoy.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    takip_eden = db.relationship('User', backref='takip_edilen_portfoyler')
    portfoy = db.relationship('PaylasilanPortfoy', backref='takipci_listesi')
    
    def __repr__(self):
        return f'<PortfoyTakip {self.takip_eden_id}->{self.portfoy_id}>'

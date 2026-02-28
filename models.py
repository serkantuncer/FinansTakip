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

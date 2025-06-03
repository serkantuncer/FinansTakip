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
    kod = db.Column(db.String(30), nullable=False)  # Yatırım kodu (USDTRY, XU100, vb.)
    isim = db.Column(db.String(100))
    alis_tarihi = db.Column(db.DateTime, nullable=False)
    alis_fiyati = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    miktar = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    guncel_fiyat = db.Column(db.Numeric(precision=20, scale=6))
    son_guncelleme = db.Column(db.DateTime)
    notlar = db.Column(db.Text)
    kategori = db.Column(db.String(30))  # Opsiyonel kategori alanı
    
    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for migration
    
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
            'alis_tutari': float(self.alis_fiyati * self.miktar),
            'guncel_tutar': float(self.guncel_fiyat * self.miktar) if self.guncel_fiyat else None,
            'kar_zarar_tl': float((self.guncel_fiyat - self.alis_fiyati) * self.miktar) if self.guncel_fiyat else None,
            'kar_zarar_yuzde': float((self.guncel_fiyat / self.alis_fiyati - 1) * 100) if self.guncel_fiyat else None
        }

class FiyatGecmisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    yatirim_id = db.Column(db.Integer, db.ForeignKey('yatirim.id'), nullable=False)
    tarih = db.Column(db.DateTime, nullable=False)
    fiyat = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    
    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for migration
    
    def __repr__(self):
        return f'<FiyatGecmisi {self.yatirim_id} {self.tarih}>'

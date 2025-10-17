# app.py - Ana Flask uygulaması

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from decimal import Decimal, InvalidOperation
import plotly
import plotly.express as px
import plotly.graph_objects as go
from functools import wraps
import re
import sys
import os
import xml.etree.ElementTree as ET
import shutil


def resource_path(relative_path):
    """PyInstaller paketindeki dosyaların yolunu bulur."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_writable_db_path():
    """Yazılabilir veritabanı yolunu döndürür ve gerekirse kopyalar."""
    if getattr(sys, 'frozen', False):
        # PyInstaller ile paketlenmiş durumda
        # Kullanıcının ana dizininde uygulama klasörü oluştur
        home_dir = os.path.expanduser("~")
        app_data_dir = os.path.join(home_dir, ".yatirim_takip")
        
        # Klasör yoksa oluştur
        if not os.path.exists(app_data_dir):
            os.makedirs(app_data_dir)
            print(f"Uygulama veri klasörü oluşturuldu: {app_data_dir}")
        
        # Hedef veritabanı yolu
        target_db_path = os.path.join(app_data_dir, "finans_takip.db")
        
        # Eğer kullanıcı dizininde veritabanı yoksa, paket içindekini kopyala
        if not os.path.exists(target_db_path):
            bundled_db_path = resource_path(os.path.join("instance", "finans_takip.db"))
            if os.path.exists(bundled_db_path):
                try:
                    shutil.copy2(bundled_db_path, target_db_path)
                    print(f"Veritabanı kopyalandı: {bundled_db_path} -> {target_db_path}")
                except Exception as e:
                    print(f"Veritabanı kopyalama hatası: {e}")
            else:
                print(f"Paket içinde veritabanı bulunamadı: {bundled_db_path}")
                print("Yeni veritabanı oluşturulacak...")
        
        return target_db_path
    else:
        # Normal geliştirme ortamında
        instance_dir = "instance"
        if not os.path.exists(instance_dir):
            os.makedirs(instance_dir)
        
        db_path = os.path.join(instance_dir, "finans_takip.db")
        return os.path.abspath(db_path)


app = Flask(__name__)
app.config['SECRET_KEY'] = 'finanstakip2025'

# Veritabanı yolunu al
db_path = get_writable_db_path()
print("Veritabanı yolu:", db_path)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Veri modelleri
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
    kategori = db.Column(db.String(30))  # Opsiyonel kategori alanı (Örn: "Emeklilik", "Acil Durum", "Uzun Vadeli")
    
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


def init_database():
    """Veritabanını başlatır - tabloları oluşturur."""
    with app.app_context():
        try:
            db.create_all()
            print("Veritabanı tabloları kontrol edildi/oluşturuldu.")
        except Exception as e:
            print(f"Veritabanı başlatma hatası: {e}")


# Uygulama başladığında veritabanını kontrol et
try:
    init_database()
except Exception as e:
    print(f"Veritabanı initialization hatası: {e}")

class FiyatGecmisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    yatirim_id = db.Column(db.Integer, db.ForeignKey('yatirim.id'), nullable=False)
    tarih = db.Column(db.DateTime, nullable=False)
    fiyat = db.Column(db.Numeric(precision=20, scale=6), nullable=False)
    
    def __repr__(self):
        return f'<FiyatGecmisi {self.yatirim_id} {self.tarih}>'

# Veri çekme fonksiyonları
def tefas_fon_verisi_cek(fon_kodu):
    """TEFAŞ'tan fon verisi çeker - Güncellenmiş Versiyon"""
    fon_kodu_upper = fon_kodu.upper()
    url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu_upper}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    app.logger.info(f"TEFAŞ Verisi Çekiliyor: {fon_kodu_upper} - URL: {url}")
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            app.logger.warning(f"TEFAŞ sayfası ({fon_kodu_upper}) HTTP {response.status_code} hatası verdi.")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # FON ADI İÇİN OLASI SEÇİCİLER
        fon_adi = None
        
        # 1. İlk seçenek: Önceki seçici
        fon_adi_element = soup.find('span', {'id': 'MainContent_FormViewMainIndicators_LabelFund'})
        
        # 2. İkinci seçenek: Yeni header'dan
        if not fon_adi_element:
            fon_adi_element = soup.find('h2', class_='main-indicators-header')
            
        # 3. Başlığı al (son çare)
        if fon_adi_element:
            fon_adi = fon_adi_element.text.strip()
        else:
            fon_adi = soup.title.string if soup.title else f"{fon_kodu_upper} Fonu"
            # Eğer başlıkta "bulunamadı" benzeri bir ifade varsa, sayfa hata vermiş olabilir
            if "bulunamadı" in fon_adi.lower():
                app.logger.warning(f"TEFAŞ sayfasında {fon_kodu_upper} için kayıt bulunamadı görünüyor (başlıktan tespit).")
                return None
        
        # FİYAT İÇİN OLASI SEÇİCİLER
        # 1. Önceki seçici ile fiyat 
        fiyat_element = soup.find('span', {'id': 'MainContent_FormViewMainIndicators_LabelPrice'})
        
        # 2. Top-list ile fiyat bulma (önceki kodunuzdan)
        if not fiyat_element:
            price_list = soup.find('ul', class_='top-list')
            if price_list:
                first_item = price_list.find('li')
                if first_item:
                    fiyat_element = first_item.find('span')
        
        # 3. Ana göstergeler bölümünde fiyat arama
        if not fiyat_element:
            main_indicators = soup.find('div', class_='main-indicators')
            if main_indicators:
                items = main_indicators.find_all('li')
                for item in items:
                    if 'Fiyat' in item.text or 'TL' in item.text:
                        fiyat_element = item.find('span')
                        break
        
        # Eğer hala fiyat bulunamadıysa en son çare olarak genel sayfa içinde uygun metinleri ara
        if not fiyat_element:
            # Tüm span'ları kontrol et, "TL" içeren veya sayısal değer içeren span'ları bul
            spans = soup.find_all('span')
            for span in spans:
                text = span.text.strip()
                if ('TL' in text) or (',' in text and text.replace(',', '').replace('.', '').isdigit()):
                    fiyat_element = span
                    break
        
        if not fiyat_element:
            app.logger.warning(f"TEFAŞ sayfasında {fon_kodu_upper} için fiyat bulunamadı.")
            return None
            
        fiyat_text = fiyat_element.text.strip()
        app.logger.debug(f"TEFAŞ'tan okunan ham değerler: Ad='{fon_adi}', Fiyat='{fiyat_text}'")
        
        # Fiyatı Decimal'e çevir (TL veya diğer birim işaretlerini temizle)
        fiyat_text = fiyat_text.replace('TL', '').replace('₺', '').strip()
        
        try:
            # Önce binlik ayraçları kaldır, sonra virgülü noktaya çevir
            fiyat = Decimal(fiyat_text.replace('.', '').replace(',', '.'))
        except (InvalidOperation, ValueError):
            app.logger.error(f"TEFAŞ fiyatı ({fon_kodu_upper}) Decimal'e çevrilemedi: '{fiyat_text}'")
            return None
            
        veri = {
            'isim': fon_adi,
            'guncel_fiyat': fiyat,
            'tarih': datetime.now()
        }
        app.logger.info(f"TEFAŞ Verisi Başarıyla Çekildi: {fon_kodu_upper} - Veri: {veri}")
        return veri
        
    except requests.exceptions.Timeout:
        app.logger.error(f"TEFAŞ veri çekme zaman aşımına uğradı ({fon_kodu_upper}): {url}")
        return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"TEFAŞ veri çekme (Request) hatası ({fon_kodu_upper}): {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"TEFAŞ Hata Yanıt Kodu: {e.response.status_code}")
        return None
    except Exception as e:
        app.logger.error(f"TEFAŞ veri çekme (Genel) hatası ({fon_kodu_upper}): {str(e)}", exc_info=True)
        return None

def bist_hisse_verisi_cek(hisse_kodu):
    """İş Yatırım'dan hisse verisi çeker"""
    hisse_kodu_upper = hisse_kodu.upper()

    # Yeni API URL'si (JSON API kullanımı)
    api_url = f"https://www.isyatirim.com.tr/tr-tr/_layouts/Isyatirim.Website/Common/Data.aspx/OneEndeks?endeks={hisse_kodu_upper}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.isyatirim.com.tr/'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()

        data = response.json()
        app.logger.info(f"API'den dönen veri: {data}")  # Veriyi logla

        if isinstance(data, list) and len(data) > 0:
            hisse_bilgisi = data[0]

            if "last" in hisse_bilgisi and "symbol" in hisse_bilgisi:
                fiyat_text = hisse_bilgisi["last"]
                isim = hisse_bilgisi["symbol"]

                fiyat = Decimal(fiyat_text)

                return {
                    'isim': isim.strip(),
                    'guncel_fiyat': fiyat,
                    'tarih': datetime.now()
                }

        return None
    except Exception as e:
        app.logger.error(f"BIST veri çekme hatası: {str(e)}")
        return None

def altin_verisi_cek(altin_turu_kodu):
    """Altinkaynak servisine manuel SOAP isteği göndererek altın fiyatlarını çeker."""
    service_url = 'http://data.altinkaynak.com/DataService.asmx'
    altin_turu_kodu_upper = altin_turu_kodu.upper()
    app.logger.info(f"Altın Verisi Çekiliyor (Altinkaynak Manuel SOAP): {altin_turu_kodu_upper} - URL: {service_url}")

    username = 'AltinkaynakWebServis'
    password = 'AltinkaynakWebServis'

    # XML içindeki 'Aciklama' etiketine göre eşleştirme (YANITTAN ALINAN GERÇEK DEĞERLER!)
    altin_tipi_map = {
        'GA': 'Gram Altın',       # XML'deki Açıklama ile eşleşiyor
        'C': 'Çeyrek Altın',      # XML'deki Açıklama ile eşleşiyor
        'Y': 'Yarım Altın',       # XML'deki Açıklama ile eşleşiyor
        'T': 'Teklik Altın',      # XML'deki Açıklama 'Teklik Altın' (Cumhuriyet değil)
        # 'ONS': 'ONS',           # ONS için XML'de doğrudan eşleşme yok
    }
    altin_isim_aranan = altin_tipi_map.get(altin_turu_kodu_upper)
    if not altin_isim_aranan:
        app.logger.warning(f"Geçersiz veya eşleşmeyen altın türü kodu: {altin_turu_kodu_upper}")
        return None

    # SOAP 1.1 İstek XML'ini oluşturma (f-string ile)
    soap_request_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Header>
    <AuthHeader xmlns="http://data.altinkaynak.com/">
      <Username>{username}</Username>
      <Password>{password}</Password>
    </AuthHeader>
  </soap:Header>
  <soap:Body>
    <GetGold xmlns="http://data.altinkaynak.com/" />
  </soap:Body>
</soap:Envelope>"""

    # HTTP Header'larını ayarlama (SOAP 1.1 için)
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://data.altinkaynak.com/GetGold"',
        'Host': 'data.altinkaynak.com'
    }

    try:
        # POST isteğini gönderme
        response = requests.post(service_url, headers=headers, data=soap_request_xml.encode('utf-8'), timeout=20)
        response.raise_for_status() # HTTP 4xx/5xx hatalarını kontrol et

        # Yanıt XML'ini parse etme
        try:
            response_xml_root = ET.fromstring(response.content)
            namespaces = {
                'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                'ak': 'http://data.altinkaynak.com/'
            }
            get_gold_result_element = response_xml_root.find('.//soap:Body/ak:GetGoldResponse/ak:GetGoldResult', namespaces)

            if get_gold_result_element is None or get_gold_result_element.text is None:
                 get_gold_result_element = response_xml_root.find('.//{http://data.altinkaynak.com/}GetGoldResult')
                 if get_gold_result_element is None or get_gold_result_element.text is None:
                    app.logger.warning("Altinkaynak yanıt XML'inde GetGoldResult etiketi veya içeriği bulunamadı.")
                    app.logger.debug(f"Alınan yanıt içeriği (ilk 500kr): {response.text[:500]}")
                    if "Nesne başvurusu" in response.text:
                        app.logger.error("Altinkaynak servisi 'Nesne başvurusu' hatası döndürdü (yetkilendirme hatası olabilir)")
                    return None

            inner_xml_string = get_gold_result_element.text
            # TAM YANITI LOGLA (DEBUG İÇİN) - Eğer çok uzunsa sorun olabilir, gerekirse kısaltılabilir.
            app.logger.debug(f"Altinkaynak GetGoldResult İçerik Stringi (ilk 1000kr): {inner_xml_string[:1000]}...") # İlk 1000 karakter daha güvenli

            # --- Bu string'i de XML olarak parse et ---
            try:
                inner_root = ET.fromstring(inner_xml_string)
                app.logger.debug(f"Inner XML root tag adı: '{inner_root.tag}'") # Beklenen: Kurlar
                altin_bulundu = False

                # Inner XML içindeki altın kayıtlarını bul (Yapı: <Kur>...</Kur>)
                kur_elements = inner_root.findall('./Kur') # Doğrudan root altındaki Kur'ları ara
                app.logger.debug(f"Toplam {len(kur_elements)} adet <Kur> elementi bulundu.")

                for i, kur_element in enumerate(kur_elements):
                    aciklama_raw = kur_element.findtext('Aciklama')
                    satis_str = kur_element.findtext('Satis')
                    log_prefix = f"[Kur {i+1}/{len(kur_elements)}]"

                    if aciklama_raw and satis_str:
                        aciklama_clean = aciklama_raw.strip()
                        aranan_lower = altin_isim_aranan.lower()
                        bulunan_lower = aciklama_clean.lower()
                        eslesme_sonucu = (aranan_lower == bulunan_lower)

                        app.logger.debug(f"{log_prefix} Aciklama Raw: '{aciklama_raw}', Clean: '{aciklama_clean}', Satis: '{satis_str}'")
                        app.logger.debug(f"{log_prefix} KARŞILAŞTIRMA: Aranan (lower): '{aranan_lower}', Bulunan (lower): '{bulunan_lower}', SONUÇ (==): {eslesme_sonucu}")

                        if eslesme_sonucu: # Tam eşleşme kontrolü
                            try:
                                fiyat = Decimal(satis_str.replace(',', '.'))
                            except (InvalidOperation, TypeError) as e_decimal:
                                app.logger.error(f"{log_prefix} Altinkaynak Inner XML fiyatı ('{aciklama_clean}') çevirme hatası: '{satis_str}', Hata: {e_decimal}")
                                continue # Sonraki kayda geç

                            veri = {
                                'isim': aciklama_clean,
                                'guncel_fiyat': fiyat,
                                'tarih': datetime.now()
                            }
                            app.logger.info(f"Altinkaynak Altın Verisi (Manuel SOAP) Başarıyla Çekildi: {altin_turu_kodu_upper} ({aciklama_clean}) - Fiyat: {fiyat}")
                            altin_bulundu = True
                            return veri # Eşleşme bulundu, döngüden ve fonksiyondan çık
                    else:
                         app.logger.warning(f"{log_prefix} Aciklama veya Satis etiketi bulunamadı veya boş.")

                # Eğer döngü bittiyse ve altın bulunamadıysa
                if not altin_bulundu:
                    app.logger.warning(f"Döngü bitti. Altinkaynak Inner XML içinde aranan altın türü bulunamadı: '{altin_isim_aranan}' (Kod: {altin_turu_kodu_upper})")
                    return None
                
            except ET.ParseError as e:
                app.logger.error(f"Altın veri XML'i parse edilemedi: {str(e)}")
                app.logger.debug(f"Parse edilemeyen XML: {inner_xml_string[:200]}")
                return None
                
        except ET.ParseError as e:
            app.logger.error(f"SOAP yanıt XML'i parse edilemedi: {str(e)}")
            app.logger.debug(f"Parse edilemeyen yanıt: {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
         app.logger.error(f"Altinkaynak Manuel SOAP isteği zaman aşımına uğradı ({altin_turu_kodu_upper}).")
         return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Altinkaynak Manuel SOAP isteği hatası ({altin_turu_kodu_upper}): {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
             app.logger.error(f"Altinkaynak Hata Yanıt Kodu: {e.response.status_code}, Yanıt: {e.response.text[:200]}")
             if "Nesne başvurusu" in e.response.text:
                  app.logger.error("Altinkaynak sunucusu hala 'Nesne Başvurusu' hatası veriyor (HTTP Hata Kodu üzerinden).")
        return None
    except Exception as e:
        app.logger.error(f"Altinkaynak Altın verisi çekme (Manuel SOAP Genel) hatası ({altin_turu_kodu_upper}): {str(e)}", exc_info=True)
        return None

def doviz_verisi_cek(doviz_kodu):
    """TCMB API'sinden döviz verisi çeker"""
    doviz_kodu_upper = doviz_kodu.upper()
    
    # TCMB XML servisi
    url = "https://www.tcmb.gov.tr/kurlar/today.xml"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            app.logger.warning(f"TCMB döviz verisi HTTP {response.status_code} hatası verdi.")
            return None
        
        # XML'i parse et
        root = ET.fromstring(response.content)
        
        # Döviz kodlarını kontrol et
        for currency in root.findall('.//Currency'):
            curr_code = currency.get('CurrencyCode')
            if curr_code == doviz_kodu_upper:
                # Döviz ismi
                isim = currency.find('CurrencyName').text
                
                # Alış fiyatı (ForexBuying) al
                fiyat_element = currency.find('ForexBuying')
                if fiyat_element is not None and fiyat_element.text:
                    try:
                        # Nokta ile ayrılmış ondalıklı sayıyı Decimal'e çevir
                        fiyat = Decimal(fiyat_element.text)
                        
                        return {
                            'isim': isim,
                            'guncel_fiyat': fiyat,
                            'tarih': datetime.now()
                        }
                    except (InvalidOperation, ValueError) as e:
                        app.logger.error(f"TCMB döviz fiyatı Decimal'e çevrilemedi: {str(e)} - Veri: {fiyat_element.text}")
                        return None
        
        app.logger.warning(f"TCMB verilerinde {doviz_kodu_upper} kodu bulunamadı.")
        return None
        
    except Exception as e:
        app.logger.error(f"TCMB döviz verisi çekme hatası: {str(e)}")
        return None

def yatirim_verisi_guncelle(yatirim):
    """Yatırım verisini türüne göre günceller"""
    if yatirim.tip == 'fon':
        veri = tefas_fon_verisi_cek(yatirim.kod)
    elif yatirim.tip == 'hisse':
        veri = bist_hisse_verisi_cek(yatirim.kod)
    elif yatirim.tip == 'altin':
        veri = altin_verisi_cek(yatirim.kod)
    elif yatirim.tip == 'doviz':
        veri = doviz_verisi_cek(yatirim.kod)
    else:
        app.logger.error(f"Bilinmeyen yatırım tipi: {yatirim.tip}")
        return False
    
    if veri:
        # Güncel fiyatı kaydet
        yatirim.guncel_fiyat = veri['guncel_fiyat']
        yatirim.son_guncelleme = veri['tarih']
        
        # İsim boşsa veya en az 3 karakter kısaysa, gelen ismi kaydet
        if not yatirim.isim or (len(yatirim.isim) < 3 and len(veri['isim']) >= 3):
            yatirim.isim = veri['isim']
        
        # Fiyat geçmişine ekle (en son fiyat değişmişse)
        son_kayit = FiyatGecmisi.query.filter_by(yatirim_id=yatirim.id).order_by(FiyatGecmisi.tarih.desc()).first()
        
        if not son_kayit or son_kayit.fiyat != veri['guncel_fiyat']:
            yeni_kayit = FiyatGecmisi(
                yatirim_id=yatirim.id,
                tarih=veri['tarih'],
                fiyat=veri['guncel_fiyat']
            )
            db.session.add(yeni_kayit)
        
        db.session.commit()
        return True
    else:
        app.logger.warning(f"Yatırım verisi çekilemedi: {yatirim.tip} {yatirim.kod}")
        return False

# Yeni arama fonksiyonları
def fon_ara(terim):
    """Fon arama API'si"""
    terim = terim.upper()
    
    # 1. TEFAS'tan fon verileri çekilir (isimleriyle birlikte)
    # Bu örnek için sadece yaygın fonları içeren bir listeyi döndürüyoruz
    # Gerçek uygulamada buraya TEFAS'tan veri çekme API'si eklenebilir
    
    yaygın_fonlar = [
        {"kod": "TLI", "isim": "Ak Portföy Para Piyasası Fonu", "tur": "fon"},
        {"kod": "TI2", "isim": "İş Portföy Para Piyasası Fonu", "tur": "fon"},
        {"kod": "AFA", "isim": "Ak Portföy Amerika Yabancı Hisse Senedi Fonu", "tur": "fon"},
        {"kod": "TTE", "isim": "İş Portföy BIST Teknoloji Ağırlıklı Sınırlamalı Endeks Hisse Senedi Fonu", "tur": "fon"},
        {"kod": "IYF", "isim": "İş Portföy Yıldızlar Serbest Fon", "tur": "fon"},
        {"kod": "TYA", "isim": "HSBC Portföy Para Piyasası Fonu", "tur": "fon"},
        {"kod": "HVS", "isim": "HSBC Portföy Hisse Senedi Fonu", "tur": "fon"},
        {"kod": "YFT", "isim": "Yapı Kredi Portföy BİST 30 Endeksi Hisse Senedi Fonu", "tur": "fon"},
        {"kod": "TZA", "isim": "Ziraat Portföy Para Piyasası Fonu", "tur": "fon"},
        {"kod": "ZBJ", "isim": "Ziraat Portföy Para Piyasası Fonu", "tur": "fon"},
        {"kod": "ZPE", "isim": "Ziraat Portföy BIST 30 Endeksi Hisse Senedi Fonu", "tur": "fon"},
        {"kod": "GMR", "isim": "Garanti Portföy Birinci Para Piyasası Fonu", "tur": "fon"},
        {"kod": "GUD", "isim": "Garanti Portföy Değişken Fon", "tur": "fon"},
        {"kod": "DZE", "isim": "Deniz Portföy BIST 100 Endeksi Hisse Senedi Fonu", "tur": "fon"},
        {"kod": "OMF", "isim": "Osmanlı Portföy Para Piyasası Fonu", "tur": "fon"},
        {"kod": "VEF", "isim": "Vakıf Emeklilik Para Piyasası Fonu", "tur": "fon"}
    ]
    
    sonuclar = []
    
    # Koddaki eşleşme (tam eşleşmeyi en önde göster)
    for fon in yaygın_fonlar:
        if fon["kod"] == terim:
            sonuclar.append(fon)
            break
    
    # Koddaki eşleşme (kısmi)
    for fon in yaygın_fonlar:
        if terim in fon["kod"] and fon not in sonuclar:
            sonuclar.append(fon)
    
    # İsimdeki eşleşme
    for fon in yaygın_fonlar:
        if terim in fon["isim"].upper() and fon not in sonuclar:
            sonuclar.append(fon)
    
    return sonuclar

def hisse_ara(terim):
    """Hisse senedi arama API'si"""
    terim = terim.upper()
    
    # Yaygın hisse senetleri listesi
    yaygın_hisseler = [
        {"kod": "THYAO", "isim": "Türk Hava Yolları", "tur": "hisse"},
        {"kod": "GARAN", "isim": "Garanti Bankası", "tur": "hisse"},
        {"kod": "ASELS", "isim": "Aselsan", "tur": "hisse"},
        {"kod": "SISE", "isim": "Şişe Cam", "tur": "hisse"},
        {"kod": "AKBNK", "isim": "Akbank", "tur": "hisse"},
        {"kod": "PGSUS", "isim": "Pegasus", "tur": "hisse"},
        {"kod": "KRDMD", "isim": "Kardemir", "tur": "hisse"},
        {"kod": "KOZAL", "isim": "Koza Altın", "tur": "hisse"},
        {"kod": "TUPRS", "isim": "Tüpraş", "tur": "hisse"},
        {"kod": "EREGL", "isim": "Ereğli Demir Çelik", "tur": "hisse"},
        {"kod": "BIMAS", "isim": "BİM Mağazalar", "tur": "hisse"},
        {"kod": "YKBNK", "isim": "Yapı Kredi Bankası", "tur": "hisse"},
        {"kod": "TCELL", "isim": "Turkcell", "tur": "hisse"},
        {"kod": "TOASO", "isim": "Tofaş Oto", "tur": "hisse"},
        {"kod": "VESTL", "isim": "Vestel", "tur": "hisse"}
    ]
    
    sonuclar = []
    
    # Koddaki eşleşme (tam eşleşmeyi en önde göster)
    for hisse in yaygın_hisseler:
        if hisse["kod"] == terim:
            sonuclar.append(hisse)
            break
    
    # Koddaki eşleşme (kısmi)
    for hisse in yaygın_hisseler:
        if terim in hisse["kod"] and hisse not in sonuclar:
            sonuclar.append(hisse)
    
    # İsimdeki eşleşme
    for hisse in yaygın_hisseler:
        if terim in hisse["isim"].upper() and hisse not in sonuclar:
            sonuclar.append(hisse)
    
    return sonuclar

def yatirim_kodu_dogrula():
    """Yatırım kodunu doğrular ve varsa güncel bilgilerini getirir"""
    veri = request.get_json()
    
    if not veri or 'tip' not in veri or 'kod' not in veri:
        return jsonify({
            'basarili': False,
            'hata': 'Eksik parametreler'
        })
    
    tip = veri['tip']
    kod = veri['kod'].upper().strip()
    
    if tip == 'fon':
        sonuc = tefas_fon_verisi_cek(kod)
    elif tip == 'hisse':
        sonuc = bist_hisse_verisi_cek(kod)
    elif tip == 'altin':
        sonuc = altin_verisi_cek(kod)
    elif tip == 'doviz':
        sonuc = doviz_verisi_cek(kod)
    else:
        return jsonify({
            'basarili': False,
            'hata': 'Geçersiz yatırım tipi'
        })
    
    if sonuc:
        return jsonify({
            'basarili': True,
            'veri': {
                'kod': kod,
                'isim': sonuc['isim'],
                'guncel_fiyat': float(sonuc['guncel_fiyat']),
                'tarih': sonuc['tarih'].strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    else:
        return jsonify({
            'basarili': False,
            'hata': 'Yatırım kodu bulunamadı veya veri çekilemedi'
        })

def kategori_yatirimlar(tip):
    """Belirli bir kategorideki yatırımları getirir"""
    yatirimlar = Yatirim.query.filter_by(tip=tip).all()
    return jsonify([yatirim.to_dict() for yatirim in yatirimlar])

# Route'lar

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')

@app.route('/yatirimlar')
def yatirimlar_sayfasi():
    """Yatırım yönetimi sayfası"""
    return render_template('yatirimlar.html')

# API Route'ları
@app.route('/api/yatirimlar', methods=['GET'])
def get_yatirimlar():
    """Tüm yatırımları listeler"""
    yatirimlar = Yatirim.query.all()
    return jsonify([yatirim.to_dict() for yatirim in yatirimlar])

@app.route('/api/yatirimlar/<string:tip>', methods=['GET'])
def get_kategori_yatirimlar(tip):
    """Belirli bir kategorideki yatırımları getirir"""
    yatirimlar = Yatirim.query.filter_by(tip=tip).all()
    return jsonify([yatirim.to_dict() for yatirim in yatirimlar])

@app.route('/api/yatirim/<int:yatirim_id>', methods=['GET'])
def get_yatirim(yatirim_id):
    """Belirli bir yatırımın detayını getirir"""
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    return jsonify(yatirim.to_dict())

@app.route('/api/yatirim', methods=['POST'])
def create_yatirim():
    """Yeni bir yatırım ekler"""
    veri = request.json
    
    try:
        # Decimal dönüşümleri - hataları ele alarak
        try:
            # Locale ayarlarını dikkate alarak (virgül veya nokta) dönüşüm yap
            alis_fiyati_str = str(veri['alis_fiyati']).replace(',', '.')
            miktar_str = str(veri['miktar']).replace(',', '.')
            
            alis_fiyati = Decimal(alis_fiyati_str)
            miktar = Decimal(miktar_str)
        except Exception as e:
            app.logger.error(f"Decimal dönüşüm hatası: {str(e)}")
            return jsonify({
                'basarili': False,
                'hata': f"Fiyat veya miktar sayısal formatta değil. Lütfen rakamlardan oluşan bir değer girin. Hata: {str(e)}"
            }), 400
        
        # Yeni yatırım oluştur
        yatirim = Yatirim(
            tip=veri['tip'],
            kod=veri['kod'].upper(),
            isim=veri.get('isim'),
            alis_tarihi=datetime.strptime(veri['alis_tarihi'], '%Y-%m-%d'),
            alis_fiyati=alis_fiyati,
            miktar=miktar,
            kategori=veri.get('kategori'),
            notlar=veri.get('notlar')
        )
        
        db.session.add(yatirim)
        db.session.commit()
        
        # Güncel fiyat bilgisini hemen çek
        yatirim_verisi_guncelle(yatirim)
        
        return jsonify({
            'basarili': True,
            'mesaj': 'Yatırım başarıyla eklendi',
            'yatirim': yatirim.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Yatırım ekleme hatası: {str(e)}")
        return jsonify({
            'basarili': False,
            'hata': str(e)
        }), 400

@app.route('/api/yatirim/<int:yatirim_id>', methods=['PUT'])
def update_yatirim(yatirim_id):
    """Bir yatırımı günceller"""
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    veri = request.json
    
    try:
        # Decimal dönüşümleri - hataları ele alarak
        try:
            # Locale ayarlarını dikkate alarak (virgül veya nokta) dönüşüm yap
            alis_fiyati_str = str(veri['alis_fiyati']).replace(',', '.')
            miktar_str = str(veri['miktar']).replace(',', '.')
            
            alis_fiyati = Decimal(alis_fiyati_str)
            miktar = Decimal(miktar_str)
        except Exception as e:
            app.logger.error(f"Decimal dönüşüm hatası: {str(e)}")
            return jsonify({
                'basarili': False,
                'hata': f"Fiyat veya miktar sayısal formatta değil. Lütfen rakamlardan oluşan bir değer girin. Hata: {str(e)}"
            }), 400
        
        yatirim.tip = veri['tip']
        yatirim.kod = veri['kod'].upper()
        yatirim.isim = veri.get('isim')
        yatirim.alis_tarihi = datetime.strptime(veri['alis_tarihi'], '%Y-%m-%d')
        yatirim.alis_fiyati = alis_fiyati
        yatirim.miktar = miktar
        yatirim.kategori = veri.get('kategori')
        yatirim.notlar = veri.get('notlar')
        
        db.session.commit()
        
        # Güncel fiyat bilgisini hemen çek
        yatirim_verisi_guncelle(yatirim)
        
        return jsonify({
            'basarili': True,
            'mesaj': 'Yatırım başarıyla güncellendi',
            'yatirim': yatirim.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Yatırım güncelleme hatası: {str(e)}")
        return jsonify({
            'basarili': False,
            'hata': str(e)
        }), 400

@app.route('/api/yatirim/<int:yatirim_id>', methods=['DELETE'])
def delete_yatirim(yatirim_id):
    """Bir yatırımı siler"""
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    
    try:
        # Önce yatırıma ait fiyat geçmişi kayıtlarını sil
        FiyatGecmisi.query.filter_by(yatirim_id=yatirim_id).delete()
        
        # Sonra yatırımı sil
        db.session.delete(yatirim)
        db.session.commit()
        
        return jsonify({
            'basarili': True,
            'mesaj': 'Yatırım başarıyla silindi'
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Yatırım silme hatası: {str(e)}")
        return jsonify({
            'basarili': False,
            'hata': str(e)
        }), 400

@app.route('/api/yatirimlar/guncelle', methods=['POST'])
def guncelle_tum_yatirimlar():
    """Tüm yatırımların güncel verilerini çeker"""
    try:
        yatirimlar = Yatirim.query.all()
        basarili_count = 0
        
        for yatirim in yatirimlar:
            if yatirim_verisi_guncelle(yatirim):
                basarili_count += 1
        
        return jsonify({
            'basarili': True,
            'mesaj': f'{len(yatirimlar)} yatırımdan {basarili_count} tanesi güncellendi',
            'toplam': len(yatirimlar),
            'guncellenen': basarili_count
        })
    except Exception as e:
        app.logger.error(f"Toplu güncelleme hatası: {str(e)}")
        return jsonify({
            'basarili': False,
            'hata': str(e)
        }), 500

@app.route('/api/yatirim/<int:yatirim_id>/guncelle', methods=['POST'])
def guncelle_yatirim(yatirim_id):
    """Belirli bir yatırımın güncel verisini çeker"""
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    
    try:
        if yatirim_verisi_guncelle(yatirim):
            return jsonify({
                'basarili': True,
                'mesaj': 'Yatırım başarıyla güncellendi',
                'yatirim': yatirim.to_dict()
            })
        else:
            return jsonify({
                'basarili': False,
                'hata': 'Veri güncellenemedi'
            }), 500
    except Exception as e:
        app.logger.error(f"Yatırım güncelleme hatası: {str(e)}")
        return jsonify({
            'basarili': False,
            'hata': str(e)
        }), 500

@app.route('/api/yatirim/<int:yatirim_id>/fiyat-gecmisi', methods=['GET'])
def get_fiyat_gecmisi(yatirim_id):
    """Belirli bir yatırımın fiyat geçmişini getirir"""
    # Son 30 güne ait verileri getir
    baslangic_tarihi = datetime.now() - timedelta(days=30)
    
    gecmis = FiyatGecmisi.query.filter(
        FiyatGecmisi.yatirim_id == yatirim_id,
        FiyatGecmisi.tarih >= baslangic_tarihi
    ).order_by(FiyatGecmisi.tarih).all()
    
    return jsonify([{
        'tarih': kayit.tarih.strftime('%Y-%m-%d'),
        'fiyat': float(kayit.fiyat)
    } for kayit in gecmis])

@app.route('/api/ozet', methods=['GET'])
def get_ozet():
    """Yatırımların özetini getirir"""
    yatirimlar = Yatirim.query.all()
    
    # 30 gün önceki tarihi hesapla
    otuz_gun_once = datetime.now() - timedelta(days=30)
    
    # Toplam değerler
    toplam_maliyet = Decimal('0')
    toplam_deger = Decimal('0')
    
    # Varlık tipine göre toplamlar
    tip_ozetleri = {
        'fon': {'guncel_deger': 0, 'maliyet': 0, 'kar_zarar_tl': 0, 'kar_zarar_yuzde': 0},
        'hisse': {'guncel_deger': 0, 'maliyet': 0, 'kar_zarar_tl': 0, 'kar_zarar_yuzde': 0},
        'altin': {'guncel_deger': 0, 'maliyet': 0, 'kar_zarar_tl': 0, 'kar_zarar_yuzde': 0},
        'doviz': {'guncel_deger': 0, 'maliyet': 0, 'kar_zarar_tl': 0, 'kar_zarar_yuzde': 0}
    }
    
    # 30 gün önceki değer
    otuz_gun_once_deger = Decimal('0')
    
    for yatirim in yatirimlar:
        # Alış maliyeti
        alis_tutari = yatirim.alis_fiyati * yatirim.miktar
        toplam_maliyet += alis_tutari
        
        # Güncel değer
        if yatirim.guncel_fiyat:
            guncel_tutar = yatirim.guncel_fiyat * yatirim.miktar
            toplam_deger += guncel_tutar
            
            # Varlık tipine göre topla
            if yatirim.tip in tip_ozetleri:
                tip_ozetleri[yatirim.tip]['maliyet'] += float(alis_tutari)
                tip_ozetleri[yatirim.tip]['guncel_deger'] += float(guncel_tutar)
                tip_ozetleri[yatirim.tip]['kar_zarar_tl'] += float(guncel_tutar - alis_tutari)
            
            # 30 gün önceki fiyatı bul
            eski_fiyat_kayit = FiyatGecmisi.query.filter(
                FiyatGecmisi.yatirim_id == yatirim.id,
                FiyatGecmisi.tarih <= otuz_gun_once
            ).order_by(FiyatGecmisi.tarih.desc()).first()
            
            if eski_fiyat_kayit:
                eski_tutar = eski_fiyat_kayit.fiyat * yatirim.miktar
                otuz_gun_once_deger += eski_tutar
    
    # Varlık tipi yüzdeleri hesapla
    for tip, ozet in tip_ozetleri.items():
        if ozet['maliyet'] > 0:
            ozet['kar_zarar_yuzde'] = (ozet['guncel_deger'] / ozet['maliyet'] - 1) * 100
    
    # Kâr/zarar hesapla
    toplam_kar_zarar = toplam_deger - toplam_maliyet
    toplam_kar_zarar_yuzde = (toplam_deger / toplam_maliyet - 1) * 100 if toplam_maliyet > 0 else 0
    
    # 30 günlük performans hesapla
    otuz_gun_degisim_tl = toplam_deger - otuz_gun_once_deger
    otuz_gun_degisim_yuzde = (toplam_deger / otuz_gun_once_deger - 1) * 100 if otuz_gun_once_deger > 0 else 0
    
    return jsonify({
        'toplam_deger': float(toplam_deger),
        'toplam_maliyet': float(toplam_maliyet),
        'toplam_kar_zarar': float(toplam_kar_zarar),
        'toplam_kar_zarar_yuzde': float(toplam_kar_zarar_yuzde),
        'otuz_gun': {
            'degisim_tl': float(otuz_gun_degisim_tl),
            'degisim_yuzde': float(otuz_gun_degisim_yuzde)
        },
        'tip_ozetleri': tip_ozetleri
    })

@app.route('/api/grafik/dagilim', methods=['GET'])
def api_grafik_dagilim():
    """Varlık dağılımı için grafik verisi"""
    yatirimlar = Yatirim.query.all()
    
    # Tipe göre toplam
    tip_toplamlar = {'fon': 0, 'hisse': 0, 'altin': 0, 'doviz': 0}
    
    for yatirim in yatirimlar:
        if yatirim.guncel_fiyat:
            guncel_tutar = float(yatirim.guncel_fiyat * yatirim.miktar)
            tip_toplamlar[yatirim.tip] += guncel_tutar
    
    # Grafik verisi oluştur
    labels = []
    values = []
    
    for tip, toplam in tip_toplamlar.items():
        if toplam > 0:
            labels.append(tip)
            values.append(toplam)
    
    return jsonify({
        'labels': labels,
        'values': values
    })

@app.route('/api/grafik/performans', methods=['GET'])
def api_grafik_performans():
    """Yatırım performansı için grafik verisi"""
    yatirimlar = Yatirim.query.all()
    performans_verileri = []
    
    for yatirim in yatirimlar:
        if yatirim.guncel_fiyat:
            kar_zarar_yuzde = float((yatirim.guncel_fiyat / yatirim.alis_fiyati - 1) * 100)
            kar_zarar_tl = float((yatirim.guncel_fiyat - yatirim.alis_fiyati) * yatirim.miktar)
            
            performans_verileri.append({
                'kod': yatirim.kod,
                'isim': yatirim.isim or yatirim.kod,
                'tip': yatirim.tip,
                'yuzde': kar_zarar_yuzde,
                'tl': kar_zarar_tl
            })
    
    return jsonify({
        'yatirimlar': performans_verileri
    })

@app.route('/api/arama/fon/<string:terim>', methods=['GET'])
def api_fon_ara(terim):
    """Fon arama API endpoint'i"""
    sonuclar = fon_ara(terim)
    return jsonify(sonuclar)

@app.route('/api/arama/hisse/<string:terim>', methods=['GET'])
def api_hisse_ara(terim):
    """Hisse senedi arama API endpoint'i"""
    sonuclar = hisse_ara(terim)
    return jsonify(sonuclar)

@app.route('/api/yatirim/dogrula', methods=['POST'])
def api_yatirim_dogrula():
    """Yatırım kodu doğrulama API endpoint'i"""
    return yatirim_kodu_dogrula()

# Veritabanı oluştur
with app.app_context():
    db.create_all()

#main.py içinden çalıştırdık
#if __name__ == '__main__':
#    app.run(debug=True, host='0.0.0.0', port=5001)
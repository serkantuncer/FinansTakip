# app.py - Ana Flask uygulaması
import os
import sys
import shutil
import logging
import time
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import requests
import certifi
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import pandas as pd
import json
from decimal import Decimal, InvalidOperation
import plotly
import plotly.express as px
import plotly.graph_objects as go
from functools import wraps
import re
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

# .env dosyasını yükle
load_dotenv()


def http_session_olustur():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


http_session = http_session_olustur()

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
        home_dir = os.path.expanduser("~")
        app_data_dir = os.path.join(home_dir, ".financial_portal")
        
        if not os.path.exists(app_data_dir):
            os.makedirs(app_data_dir)
            logging.info(f"Uygulama veri klasörü oluşturuldu: {app_data_dir}")
        
        target_db_path = os.path.join(app_data_dir, "finans_takip.db")
        
        if not os.path.exists(target_db_path):
            bundled_db_path = resource_path(os.path.join("instance", "finans_takip.db"))
            if os.path.exists(bundled_db_path):
                try:
                    shutil.copy2(bundled_db_path, target_db_path)
                    logging.info(f"Veritabanı kopyalandı: {bundled_db_path} -> {target_db_path}")
                except Exception as e:
                    logging.error(f"Veritabanı kopyalama hatası: {e}")
            else:
                logging.warning(f"Paket içinde veritabanı bulunamadı: {bundled_db_path}")
                logging.info("Yeni veritabanı oluşturulacak...")
        
        return target_db_path
    else:
        # Normal geliştirme ortamında
        instance_dir = "instance"
        if not os.path.exists(instance_dir):
            os.makedirs(instance_dir)
        
        db_path = os.path.join(instance_dir, "finans_takip.db")
        return os.path.abspath(db_path)

app = Flask(__name__)
flask_env = os.environ.get("FLASK_ENV", "").lower()
secret = os.environ.get("SESSION_SECRET")
if not secret:
    if flask_env == "production":
        raise ValueError("SESSION_SECRET ortam degiskeni tanimlanmamis!")
    secret = "dev-insecure-session-secret-change-me"
    logging.warning("SESSION_SECRET yok; development fallback secret kullaniliyor.")
app.secret_key = secret
app.config['SESSION_COOKIE_SECURE'] = flask_env == "production"
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Database configuration - use SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{get_writable_db_path()}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# CSRF koruması
csrf = CSRFProtect(app)

# Import and initialize database from models
from models import db, User, Yatirim, FiyatGecmisi
from werkzeug.security import generate_password_hash

db.init_app(app)
migrate = Migrate(app, db)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Bu sayfaya erişmek için giriş yapmanız gerekiyor.'
login_manager.login_message_category = 'info'

# Import and register auth blueprint
from auth import auth_bp
app.register_blueprint(auth_bp)

@login_manager.user_loader
def load_user(user_id):
    try:
        app.logger.debug(f"Loading user with ID: {user_id}")
        user = User.query.get(int(user_id))
        app.logger.debug(f"User loaded: {user.username if user else None}")
        return user
    except Exception as e:
        app.logger.error(f"User loading error: {e}")
        return None

def init_database():
    """Veritabanını başlatır - tabloları oluşturur."""
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Veritabanı tabloları kontrol edildi/oluşturuldu.")
            
            # Check if we need to migrate existing data
            migrate_existing_data()
            
        except Exception as e:
            app.logger.error(f"Veritabanı başlatma hatası: {e}")

def migrate_existing_data():
    """Mevcut verileri user_id olmadan oluşturulmuş tablolardan yeni yapıya taşır."""
    try:
        # Check if there are any Yatirim records without user_id
        orphaned_investments = Yatirim.query.filter_by(user_id=None).all()
        
        if orphaned_investments:
            app.logger.warning(f"Kullanıcısız {len(orphaned_investments)} yatırım kaydı bulundu. Varsayılan kullanıcıya atanıyor...")
            
            # Create a default user if none exists
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
            
            # Assign orphaned investments to default user
            for investment in orphaned_investments:
                investment.user_id = default_user.id
            
            db.session.commit()
            app.logger.info(f"{len(orphaned_investments)} yatırım kaydı admin kullanıcısına atandı.")
            
    except Exception as e:
        app.logger.error(f"Veri taşıma hatası: {e}")

# Uygulama başladığında veritabanını kontrol et
try:
    init_database()
except Exception as e:
    app.logger.error(f"Veritabanı initialization hatası: {e}")

# Fiyat verisi için basit TTL cache
_fiyat_cache = {}  # {cache_key: (veri, timestamp)}
CACHE_TTL = 900  # 15 dakika
_bist_ssl_fallback_warned_symbols = set()
_cache_hit_logged_keys = set()
ALTIN_VERBOSE_DEBUG = os.environ.get("ALTIN_VERBOSE_DEBUG", "0") == "1"


def _log_cache_hit_once(kaynak, kod):
    key = f"{kaynak}:{kod}"
    if key not in _cache_hit_logged_keys:
        app.logger.debug(f"{kaynak} cache hit: {kod}")
        _cache_hit_logged_keys.add(key)


def _cache_key(varlik_tipi, kod):
    return f"{varlik_tipi}:{kod.upper()}"


def cache_den_al(varlik_tipi, kod):
    key = _cache_key(varlik_tipi, kod)
    kayit = _fiyat_cache.get(key)
    if not kayit:
        return None

    veri, ts = kayit
    if time.time() - ts < CACHE_TTL:
        return veri

    _fiyat_cache.pop(key, None)
    return None


def cache_kaydet(varlik_tipi, kod, veri):
    if not veri:
        return
    _fiyat_cache[_cache_key(varlik_tipi, kod)] = (veri, time.time())


# Veri çekme fonksiyonları
def tefas_fon_verisi_cek(fon_kodu):
    """TEFAŞ'tan fon verisi çeker - Güncellenmiş Versiyon"""
    fon_kodu_upper = fon_kodu.upper()
    cached_veri = cache_den_al('fon', fon_kodu_upper)
    if cached_veri:
        _log_cache_hit_once("TEFAS", fon_kodu_upper)
        return cached_veri

    url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu_upper}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    app.logger.info(f"TEFAŞ Verisi Çekiliyor: {fon_kodu_upper} - URL: {url}")
    
    try:
        response = http_session.get(url, headers=headers, timeout=15)
        
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
            if fon_adi and "bulunamadı" in fon_adi.lower():
                app.logger.warning(f"TEFAŞ sayfasında {fon_kodu_upper} için kayıt bulunamadı görünüyor (başlıktan tespit).")
                # Continue with default handling for now
                pass
        
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
        cache_kaydet('fon', fon_kodu_upper, veri)
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
        # Try alternative TEFAS search as fallback
        return tefas_alternatif_arama(fon_kodu_upper)

def tefas_alternatif_arama(fon_kodu):
    """TEFAŞ alternatif API kullanarak fon arama"""
    fon_kodu_upper = fon_kodu.upper()
    cached_veri = cache_den_al('fon', fon_kodu_upper)
    if cached_veri:
        _log_cache_hit_once("TEFAS", fon_kodu_upper)
        return cached_veri

    try:
        # TEFAS public API endpoint
        api_url = f"https://www.tefas.gov.tr/api/DB/BindHistoryInfo?fontip=YAT&sfontur=&kurucukod=&fonkod={fon_kodu_upper}&bastarih=&bittarih="
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.tefas.gov.tr/'
        }
        
        app.logger.info(f"TEFAŞ Alternatif API deneniyor: {fon_kodu_upper}")
        response = http_session.get(api_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                latest_data = data[0]  # En son veri
                veri = {
                    'isim': latest_data.get('FONUNVAN', f"{fon_kodu} Fonu"),
                    'guncel_fiyat': Decimal(str(latest_data.get('FIYAT', 0))),
                    'tarih': datetime.now()
                }
                cache_kaydet('fon', fon_kodu_upper, veri)
                return veri
        
        app.logger.warning(f"TEFAŞ alternatif API'den {fon_kodu} bulunamadı")
        return None
        
    except Exception as e:
        app.logger.error(f"TEFAŞ alternatif API hatası: {str(e)}")
        return None

def bist_hisse_verisi_cek(hisse_kodu):
    """İş Yatırım'dan hisse verisi çeker"""
    hisse_kodu_upper = hisse_kodu.upper()
    cached_veri = cache_den_al('hisse', hisse_kodu_upper)
    if cached_veri:
        _log_cache_hit_once("BIST", hisse_kodu_upper)
        return cached_veri

    api_url = f"https://www.isyatirim.com.tr/tr-tr/_layouts/Isyatirim.Website/Common/Data.aspx/OneEndeks?endeks={hisse_kodu_upper}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.isyatirim.com.tr/'
    }

    try:
        response = http_session.get(api_url, headers=headers, timeout=15, verify=certifi.where())
        response.raise_for_status()
    except requests.exceptions.SSLError as ssl_err:
        if os.environ.get("FLASK_ENV", "").lower() == "production":
            app.logger.error(f"BIST SSL doğrulama hatası (production): {ssl_err}")
            return None

        if hisse_kodu_upper not in _bist_ssl_fallback_warned_symbols:
            app.logger.warning(f"BIST SSL doğrulama hatası, development fallback kullanılacak: {ssl_err}")
            _bist_ssl_fallback_warned_symbols.add(hisse_kodu_upper)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            response = http_session.get(api_url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
        except Exception as e:
            app.logger.error(f"BIST veri çekme hatası (SSL fallback sonrası): {str(e)}")
            return None
    except Exception as e:
        app.logger.error(f"BIST veri çekme hatası: {str(e)}")
        return None

    try:
        data = response.json()
        app.logger.debug(f"BIST API veri boyutu: {len(data) if isinstance(data, list) else 0}")

        if isinstance(data, list) and len(data) > 0:
            hisse_bilgisi = data[0]

            if "last" in hisse_bilgisi and "symbol" in hisse_bilgisi:
                isim = hisse_bilgisi["symbol"]

                try:
                    fiyat = Decimal(str(hisse_bilgisi["last"]).replace(',', '.'))
                except (InvalidOperation, ValueError, KeyError) as e:
                    app.logger.error(f"BIST fiyat parse hatası ({hisse_kodu_upper}): {e}")
                    return None

                veri = {
                    'isim': isim.strip(),
                    'guncel_fiyat': fiyat,
                    'tarih': datetime.now()
                }
                cache_kaydet('hisse', hisse_kodu_upper, veri)
                return veri

        return None
    except Exception as e:
        app.logger.error(f"BIST veri çekme hatası: {str(e)}")
        return None

def altin_verisi_cek(altin_turu_kodu):
    """Altinkaynak servisine manuel SOAP isteği göndererek altın fiyatlarını çeker."""
    service_url = 'http://data.altinkaynak.com/DataService.asmx'
    altin_turu_kodu_upper = altin_turu_kodu.upper()
    cached_veri = cache_den_al('altin', altin_turu_kodu_upper)
    if cached_veri:
        _log_cache_hit_once("Altin", altin_turu_kodu_upper)
        return cached_veri

    app.logger.info(f"Altın Verisi Çekiliyor (Altinkaynak Manuel SOAP): {altin_turu_kodu_upper} - URL: {service_url}")

    alt_username = os.environ.get('ALTINKAYNAK_USERNAME')
    alt_password = os.environ.get('ALTINKAYNAK_PASSWORD')

    if not alt_username or not alt_password:
        app.logger.error('ALTINKAYNAK_USERNAME veya ALTINKAYNAK_PASSWORD tanımlanmamış.')
        return None

    # XML içindeki 'Aciklama' etiketine göre eşleştirme (YANITTAN ALINAN GERÇEK DEĞERLER!)
    altin_tipi_map = {
        'GA': 'Gram Altın',       # XML'deki Açıklama ile eşleşiyor
        'C': 'Çeyrek Altın',      # XML'deki Açıklama ile eşleşiyor
        'Y': 'Yarım Altın',       # XML'deki Açıklama ile eşleşiyor
        'T': 'Teklik Altın',      # XML'deki Açıklama 'Teklik Altın' (Cumhuriyet değil)
        # 'ONS': 'ONS',           # ONS için XML'de doğrudan eşleşme yok
    }

    if altin_turu_kodu_upper not in altin_tipi_map:
        app.logger.error(f"Desteklenmeyen altın türü: {altin_turu_kodu_upper}")
        return None

    # SOAP 1.1 İstek XML'ini oluşturma (f-string ile)
    soap_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Header>
    <AuthHeader xmlns="http://data.altinkaynak.com/">
      <Username>{alt_username}</Username>
      <Password>{alt_password}</Password>
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
        response = http_session.post(service_url, headers=headers, data=soap_xml.encode('utf-8'), timeout=20)
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
            if ALTIN_VERBOSE_DEBUG:
                app.logger.debug(f"Altinkaynak GetGoldResult İçerik Stringi (ilk 1000kr): {inner_xml_string[:1000]}...")

            # --- Bu string'i de XML olarak parse et ---
            try:
                inner_root = ET.fromstring(inner_xml_string)
                if ALTIN_VERBOSE_DEBUG:
                    app.logger.debug(f"Inner XML root tag adı: '{inner_root.tag}'")
                altin_bulundu = False

                # Inner XML içindeki altın kayıtlarını bul (Yapı: <Kur>...</Kur>)
                kur_elements = inner_root.findall('./Kur') # Doğrudan root altındaki Kur'ları ara
                if ALTIN_VERBOSE_DEBUG:
                    app.logger.debug(f"Toplam {len(kur_elements)} adet <Kur> elementi bulundu.")

                for i, kur_element in enumerate(kur_elements):
                    aciklama_raw = kur_element.findtext('Aciklama')
                    satis_str = kur_element.findtext('Satis')
                    log_prefix = f"[Kur {i+1}/{len(kur_elements)}]"

                    if aciklama_raw and satis_str:
                        aciklama_clean = aciklama_raw.strip()
                        target_aciklama = altin_tipi_map[altin_turu_kodu_upper]
                        aranan_lower = target_aciklama.lower()
                        bulunan_lower = aciklama_clean.lower()
                        eslesme_sonucu = (aranan_lower == bulunan_lower)

                        if ALTIN_VERBOSE_DEBUG:
                            app.logger.debug(f"{log_prefix} Aciklama Raw: '{aciklama_raw}', Clean: '{aciklama_clean}', Satis: '{satis_str}'")
                            app.logger.debug(f"{log_prefix} KARŞILAŞTIRMA: Aranan (lower): '{aranan_lower}', Bulunan (lower): '{bulunan_lower}', SONUÇ (==): {eslesme_sonucu}")

                        if eslesme_sonucu: # Tam eşleşme kontrolü
                            try:
                                fiyat = Decimal(satis_str.replace(',', '.'))
                            except (InvalidOperation, TypeError) as e_decimal:
                                app.logger.error(f"{log_prefix} Altinkaynak Inner XML fiyatı ('{aciklama_clean}') çevirme hatası: '{satis_str}', Hata: {e_decimal}")
                                continue # Sonraki kayda geç

                            # Also get buying price if available
                            alis_str = kur_element.findtext('Alis')
                            alis_fiyat = None
                            if alis_str:
                                try:
                                    alis_fiyat = Decimal(alis_str.replace(',', '.'))
                                except (InvalidOperation, TypeError):
                                    pass

                            veri = {
                                'isim': aciklama_clean,
                                'guncel_fiyat': fiyat,  # Selling price
                                'alis_fiyat': alis_fiyat,  # Buying price
                                'satis_fiyat': fiyat,   # Selling price (explicit)
                                'tarih': datetime.now()
                            }
                            cache_kaydet('altin', altin_turu_kodu_upper, veri)
                            app.logger.info(f"Altinkaynak Altın Verisi (Manuel SOAP) Başarıyla Çekildi: {altin_turu_kodu_upper} ({aciklama_clean}) - Fiyat: {fiyat}")
                            altin_bulundu = True
                            return veri # Eşleşme bulundu, döngüden ve fonksiyondan çık
                    else:
                         app.logger.warning(f"{log_prefix} Aciklama veya Satis etiketi bulunamadı veya boş.")

                # Eğer döngü bittiyse ve altın bulunamadıysa
                if not altin_bulundu:
                    app.logger.warning(f"Döngü bitti. Altinkaynak Inner XML içinde aranan altın türü bulunamadı: '{target_aciklama}' (Kod: {altin_turu_kodu_upper})")
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
    """TCMB'den döviz verisi çeker"""
    doviz_kodu_upper = doviz_kodu.upper()
    cached_veri = cache_den_al('doviz', doviz_kodu_upper)
    if cached_veri:
        _log_cache_hit_once("Doviz", doviz_kodu_upper)
        return cached_veri

    app.logger.info(f"Döviz Verisi Çekiliyor: {doviz_kodu_upper}")
    
    try:
        # Try current date first, then try previous business days
        for days_back in range(10):  # Try up to 10 days back
            target_date = datetime.now() - timedelta(days=days_back)
            
            # Skip weekends for business days
            if target_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                continue
            
            # TCMB URL format: ddmmyyyy.xml
            date_str = target_date.strftime('%d%m%Y')
            month_year = target_date.strftime('%Y%m')
            url = f"https://www.tcmb.gov.tr/kurlar/{month_year}/{date_str}.xml"
            
            app.logger.debug(f"TCMB URL deneniyor: {url}")
            
            try:
                response = http_session.get(url, timeout=15)
                if response.status_code == 200:
                    app.logger.info(f"TCMB verisi başarıyla alındı: {url}")
                    break
                else:
                    app.logger.warning(f"TCMB URL başarısız ({response.status_code}): {url}")
                    continue
            except requests.exceptions.RequestException as e:
                app.logger.warning(f"TCMB URL isteği hatası: {url} - {str(e)}")
                continue
        else:
            # If no successful response after all attempts
            app.logger.error(f"TCMB'den {doviz_kodu_upper} için son 10 gün içinde veri alınamadı")
            return None
        
        # Parse XML response
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            app.logger.error(f"TCMB XML parse hatası: {str(e)}")
            return None
        
        # Find currency in XML
        for currency in root.findall('Currency'):
            currency_code = currency.get('Kod') or currency.get('CurrencyCode')
            if currency_code == doviz_kodu_upper:
                app.logger.info(f"TCMB'de {doviz_kodu_upper} kodu bulundu")
                
                # Get currency name
                currency_name_elem = currency.find('Isim') or currency.find('CurrencyName')
                currency_name = currency_name_elem.text if currency_name_elem is not None else f"{doviz_kodu_upper}/TRY"
                
                # Get prices - try different element names
                buying_elem = currency.find('BanknoteBuying') or currency.find('ForexBuying')
                selling_elem = currency.find('BanknoteSelling') or currency.find('ForexSelling')
                
                alis_fiyat = None
                satis_fiyat = None
                
                # Parse buying price
                if buying_elem is not None and buying_elem.text:
                    try:
                        alis_fiyat = Decimal(buying_elem.text.replace(',', '.'))
                        app.logger.debug(f"Alış fiyatı bulundu: {buying_elem.text}")
                    except (InvalidOperation, ValueError) as e:
                        app.logger.warning(f"Alış fiyatı parse hatası: {buying_elem.text} - {str(e)}")
                
                # Parse selling price
                if selling_elem is not None and selling_elem.text:
                    try:
                        satis_fiyat = Decimal(selling_elem.text.replace(',', '.'))
                        app.logger.debug(f"Satış fiyatı bulundu: {selling_elem.text}")
                    except (InvalidOperation, ValueError) as e:
                        app.logger.warning(f"Satış fiyatı parse hatası: {selling_elem.text} - {str(e)}")
                
                # Use selling price as main price, fallback to buying price
                guncel_fiyat = satis_fiyat if satis_fiyat else alis_fiyat
                
                if guncel_fiyat:
                    veri = {
                        'isim': currency_name,
                        'guncel_fiyat': guncel_fiyat,
                        'alis_fiyat': alis_fiyat,
                        'satis_fiyat': satis_fiyat,
                        'tarih': datetime.now()
                    }
                    cache_kaydet('doviz', doviz_kodu_upper, veri)
                    app.logger.info(f"TCMB Döviz Verisi Başarıyla Çekildi: {doviz_kodu_upper} - Veri: {veri}")
                    return veri
                else:
                    app.logger.error(f"TCMB'den {doviz_kodu_upper} için fiyat bilgisi parse edilemedi")
                    return None
        
        app.logger.warning(f"TCMB XML'inde döviz kodu bulunamadı: {doviz_kodu_upper}")
        
        # Log available currencies for debugging
        available_currencies = []
        for currency in root.findall('Currency'):
            kod = currency.get('Kod') or currency.get('CurrencyCode')
            if kod:
                available_currencies.append(kod)
        
        app.logger.debug(f"TCMB'de mevcut döviz kodları: {available_currencies}")
        return None
        
    except Exception as e:
        app.logger.error(f"Döviz veri çekme genel hatası ({doviz_kodu_upper}): {str(e)}", exc_info=True)
        return None

def fiyat_guncelle(yatirim_id):
    """Tek bir yatırımın fiyatını günceller"""
    yatirim = Yatirim.query.get(yatirim_id)
    if not yatirim:
        return False, "Yatırım bulunamadı"
    
    # Check if user owns this investment
    if yatirim.user_id != current_user.id:
        return False, "Bu yatırıma erişim yetkiniz yok"
    
    veri = None
    
    if yatirim.tip == 'fon':
        veri = tefas_fon_verisi_cek(yatirim.kod)
    elif yatirim.tip == 'hisse':
        veri = bist_hisse_verisi_cek(yatirim.kod)
    elif yatirim.tip == 'altin':
        veri = altin_verisi_cek(yatirim.kod)
    elif yatirim.tip == 'doviz':
        veri = doviz_verisi_cek(yatirim.kod)
    
    if veri:
        yatirim.guncel_fiyat = veri['guncel_fiyat']
        yatirim.son_guncelleme = veri['tarih']
        
        # Altın ve Döviz için alış ve satış fiyatlarını da kaydet
        if yatirim.tip in ['altin', 'doviz']:
            if veri.get('alis_fiyat'):
                yatirim.guncel_alis_fiyat = veri['alis_fiyat']
            if veri.get('satis_fiyat'):
                yatirim.guncel_satis_fiyat = veri['satis_fiyat']
        
        if not yatirim.isim and veri.get('isim'):
            yatirim.isim = veri['isim']
        
        # Fiyat geçmişine kaydet
        fiyat_gecmisi = FiyatGecmisi(
            yatirim_id=yatirim.id,
            tarih=veri['tarih'],
            fiyat=veri['guncel_fiyat'],
            user_id=current_user.id
        )
        db.session.add(fiyat_gecmisi)
        
        db.session.commit()
        return True, "Fiyat güncellendi"
    else:
        return False, "Fiyat verisi alınamadı"


def fiyat_verisi_cek_by_tip_kod(tip, kod):
    """DB yazmadan, tip+kod bazında sadece fiyat verisini çeker."""
    try:
        if tip == 'fon':
            veri = tefas_fon_verisi_cek(kod)
        elif tip == 'hisse':
            veri = bist_hisse_verisi_cek(kod)
        elif tip == 'altin':
            veri = altin_verisi_cek(kod)
        elif tip == 'doviz':
            veri = doviz_verisi_cek(kod)
        else:
            return False, None

        return (veri is not None), veri
    except Exception as e:
        app.logger.error(f"fiyat_verisi_cek_by_tip_kod hatası ({tip}:{kod}): {e}", exc_info=True)
        return False, None


def hesapla_portfoy_ozeti(yatirimlar):
    """Verilen yatırım listesi için portföy özet istatistiklerini hesaplar."""
    toplam_yatirim = Decimal('0')
    guncel_deger = Decimal('0')
    kategori_dagilim = {}
    tip_ozet = {}

    altin_doviz_alis = {
        'guncel_deger': Decimal('0'),
        'kar_zarar': Decimal('0'),
        'kar_zarar_yuzde': 0
    }
    altin_doviz_satis = {
        'guncel_deger': Decimal('0'),
        'kar_zarar': Decimal('0'),
        'kar_zarar_yuzde': 0
    }
    altin_doviz_yatirim = Decimal('0')

    for y in yatirimlar:
        maliyet = y.alis_fiyati * y.miktar
        toplam_yatirim += maliyet

        if y.guncel_fiyat and y.guncel_fiyat > 0:
            guncel_deger += y.guncel_fiyat * y.miktar
        else:
            guncel_deger += maliyet

        kategori = y.kategori or 'Diğer'
        if kategori not in kategori_dagilim:
            kategori_dagilim[kategori] = Decimal('0')
        if y.guncel_fiyat and y.guncel_fiyat > 0:
            kategori_dagilim[kategori] += y.guncel_fiyat * y.miktar
        else:
            kategori_dagilim[kategori] += maliyet

        tip = y.tip
        if tip not in tip_ozet:
            tip_ozet[tip] = {
                'tip': tip,
                'maliyet': Decimal('0'),
                'guncel_deger': Decimal('0'),
                'kar_zarar': Decimal('0'),
                'kar_zarar_yuzde': 0,
                'agirlik': 0
            }
        tip_ozet[tip]['maliyet'] += maliyet
        if y.guncel_fiyat and y.guncel_fiyat > 0:
            tip_ozet[tip]['guncel_deger'] += y.guncel_fiyat * y.miktar
        else:
            tip_ozet[tip]['guncel_deger'] += maliyet

        if y.tip in ['altin', 'doviz']:
            altin_doviz_yatirim += maliyet

            if y.guncel_alis_fiyat and y.guncel_alis_fiyat > 0:
                altin_doviz_alis['guncel_deger'] += y.guncel_alis_fiyat * y.miktar
            elif y.guncel_fiyat and y.guncel_fiyat > 0:
                altin_doviz_alis['guncel_deger'] += y.guncel_fiyat * y.miktar
            else:
                altin_doviz_alis['guncel_deger'] += maliyet

            if y.guncel_satis_fiyat and y.guncel_satis_fiyat > 0:
                altin_doviz_satis['guncel_deger'] += y.guncel_satis_fiyat * y.miktar
            elif y.guncel_fiyat and y.guncel_fiyat > 0:
                altin_doviz_satis['guncel_deger'] += y.guncel_fiyat * y.miktar
            else:
                altin_doviz_satis['guncel_deger'] += maliyet

    toplam_yatirim_float = float(toplam_yatirim)
    guncel_deger_float = float(guncel_deger)
    kar_zarar = guncel_deger_float - toplam_yatirim_float
    kar_zarar_yuzde = (kar_zarar / toplam_yatirim_float * 100) if toplam_yatirim_float > 0 else 0

    if altin_doviz_yatirim > 0:
        altin_doviz_yatirim_float = float(altin_doviz_yatirim)
        altin_doviz_alis['guncel_deger'] = float(altin_doviz_alis['guncel_deger'])
        altin_doviz_alis['kar_zarar'] = altin_doviz_alis['guncel_deger'] - altin_doviz_yatirim_float
        altin_doviz_alis['kar_zarar_yuzde'] = (altin_doviz_alis['kar_zarar'] / altin_doviz_yatirim_float * 100)
        altin_doviz_satis['guncel_deger'] = float(altin_doviz_satis['guncel_deger'])
        altin_doviz_satis['kar_zarar'] = altin_doviz_satis['guncel_deger'] - altin_doviz_yatirim_float
        altin_doviz_satis['kar_zarar_yuzde'] = (altin_doviz_satis['kar_zarar'] / altin_doviz_yatirim_float * 100)
    else:
        altin_doviz_yatirim_float = 0.0
        altin_doviz_alis['guncel_deger'] = 0.0
        altin_doviz_satis['guncel_deger'] = 0.0

    kategori_dagilim = {k: float(v) for k, v in kategori_dagilim.items()}

    for tip_data in tip_ozet.values():
        tip_data['maliyet'] = float(tip_data['maliyet'])
        tip_data['guncel_deger'] = float(tip_data['guncel_deger'])
        tip_data['kar_zarar'] = tip_data['guncel_deger'] - tip_data['maliyet']
        tip_data['kar_zarar_yuzde'] = (tip_data['kar_zarar'] / tip_data['maliyet'] * 100) if tip_data['maliyet'] > 0 else 0
        tip_data['agirlik'] = (tip_data['guncel_deger'] / guncel_deger_float * 100) if guncel_deger_float > 0 else 0

    return {
        'toplam_yatirim': toplam_yatirim_float,
        'guncel_deger': guncel_deger_float,
        'kar_zarar': kar_zarar,
        'kar_zarar_yuzde': kar_zarar_yuzde,
        'kategori_dagilim': kategori_dagilim,
        'tip_ozet': tip_ozet,
        'altin_doviz_yatirim': altin_doviz_yatirim_float,
        'altin_doviz_alis': altin_doviz_alis,
        'altin_doviz_satis': altin_doviz_satis
    }


# Ana sayfa route'u - Düzeltilmiş versiyon
def grupla_yatirimlar(yatirimlar, sadece_guncel_fiyatli=False):
    """Yatirim listesini kod+tip bazinda gruplar ve ozet metrikleri hesaplar."""
    yatirim_gruplari_liste = {}
    yatirim_by_id = {y.id: y for y in yatirimlar}

    for y in yatirimlar:
        if sadece_guncel_fiyatli and not (y.guncel_fiyat and y.guncel_fiyat > 0):
            continue

        key = f"{y.kod}_{y.tip}"
        if key not in yatirim_gruplari_liste:
            yatirim_gruplari_liste[key] = {
                'kod': y.kod,
                'isim': y.isim,
                'tip': y.tip,
                'toplam_maliyet': Decimal('0'),
                'toplam_guncel_deger': Decimal('0'),
                'toplam_kar_zarar': Decimal('0'),
                'ortalama_getiri': 0,
                'kalemler': [],
                'kategori': y.kategori
            }

        maliyet = y.alis_fiyati * y.miktar
        if y.guncel_fiyat and y.guncel_fiyat > 0:
            guncel_deger_item = y.guncel_fiyat * y.miktar
            kar_zarar_item = guncel_deger_item - maliyet
            getiri = (y.guncel_fiyat / y.alis_fiyati - 1) * 100
        else:
            guncel_deger_item = maliyet
            kar_zarar_item = Decimal('0')
            getiri = Decimal('0')

        yatirim_gruplari_liste[key]['toplam_maliyet'] += maliyet
        yatirim_gruplari_liste[key]['toplam_guncel_deger'] += guncel_deger_item
        yatirim_gruplari_liste[key]['kalemler'].append({
            'id': y.id,
            'alis_tarihi': y.alis_tarihi,
            'alis_fiyati': float(y.alis_fiyati),
            'miktar': float(y.miktar),
            'guncel_fiyat': float(y.guncel_fiyat) if y.guncel_fiyat else None,
            'maliyet': float(maliyet),
            'guncel_deger': float(guncel_deger_item),
            'kar_zarar': float(kar_zarar_item),
            'getiri': float(getiri),
            'kategori': y.kategori,
            'notlar': y.notlar,
            'son_guncelleme': y.son_guncelleme
        })

    for grup in yatirim_gruplari_liste.values():
        grup['toplam_maliyet'] = float(grup['toplam_maliyet'])
        grup['toplam_guncel_deger'] = float(grup['toplam_guncel_deger'])
        grup['toplam_kar_zarar'] = grup['toplam_guncel_deger'] - grup['toplam_maliyet']
        grup['ortalama_getiri'] = (grup['toplam_guncel_deger'] / grup['toplam_maliyet'] - 1) * 100 if grup['toplam_maliyet'] > 0 else 0
        grup['kalem_sayisi'] = len(grup['kalemler'])
        grup['kalemler'].sort(key=lambda x: x['alis_tarihi'], reverse=True)

        if grup['tip'] in ['altin', 'doviz']:
            grup['guncel_deger_alis'] = 0
            grup['guncel_deger_satis'] = 0
            grup['kar_zarar_alis'] = 0
            grup['kar_zarar_satis'] = 0
            grup['getiri_alis'] = 0
            grup['getiri_satis'] = 0

            for kalem in grup['kalemler']:
                y_obj = yatirim_by_id.get(kalem['id'])
                if not y_obj:
                    continue

                maliyet = kalem['maliyet']

                if y_obj.guncel_alis_fiyat and y_obj.guncel_alis_fiyat > 0:
                    grup['guncel_deger_alis'] += float(y_obj.guncel_alis_fiyat) * kalem['miktar']
                elif kalem['guncel_fiyat']:
                    grup['guncel_deger_alis'] += kalem['guncel_deger']
                else:
                    grup['guncel_deger_alis'] += maliyet

                if y_obj.guncel_satis_fiyat and y_obj.guncel_satis_fiyat > 0:
                    grup['guncel_deger_satis'] += float(y_obj.guncel_satis_fiyat) * kalem['miktar']
                elif kalem['guncel_fiyat']:
                    grup['guncel_deger_satis'] += kalem['guncel_deger']
                else:
                    grup['guncel_deger_satis'] += maliyet

            grup['kar_zarar_alis'] = grup['guncel_deger_alis'] - grup['toplam_maliyet']
            grup['kar_zarar_satis'] = grup['guncel_deger_satis'] - grup['toplam_maliyet']
            grup['getiri_alis'] = (grup['guncel_deger_alis'] / grup['toplam_maliyet'] - 1) * 100 if grup['toplam_maliyet'] > 0 else 0
            grup['getiri_satis'] = (grup['guncel_deger_satis'] / grup['toplam_maliyet'] - 1) * 100 if grup['toplam_maliyet'] > 0 else 0

    return list(yatirim_gruplari_liste.values())


class YatirimPerformans:
    def __init__(self, kod, isim, tip, kar_zarar, getiri, kalemler):
        self.kod = kod
        self.isim = isim
        self.tip = tip
        self.kar_zarar = kar_zarar
        self.getiri = getiri
        self.kalemler = kalemler
        self.kalem_sayisi = len(kalemler)


def portfoy_gecmis_grafigi(user_id, gun_sayisi=30):
    """Kullanicinin son N gunluk portfoy deger gecmisini gercek fiyat verisiyle hesaplar."""
    baslangic = datetime.now() - timedelta(days=gun_sayisi - 1)
    yatirimlar = Yatirim.query.filter_by(user_id=user_id).all()
    if not yatirimlar:
        return []

    son_fiyatlar = {}
    for yatirim in yatirimlar:
        onceki_kayit = (
            FiyatGecmisi.query
            .filter(
                FiyatGecmisi.yatirim_id == yatirim.id,
                FiyatGecmisi.tarih < baslangic
            )
            .order_by(FiyatGecmisi.tarih.desc())
            .first()
        )
        if onceki_kayit and onceki_kayit.fiyat:
            son_fiyatlar[yatirim.id] = onceki_kayit.fiyat
        elif yatirim.guncel_fiyat:
            son_fiyatlar[yatirim.id] = yatirim.guncel_fiyat
        else:
            son_fiyatlar[yatirim.id] = yatirim.alis_fiyati

    yatirim_idleri = [y.id for y in yatirimlar]
    gecmis_kayitlar = (
        FiyatGecmisi.query
        .filter(
            FiyatGecmisi.yatirim_id.in_(yatirim_idleri),
            FiyatGecmisi.tarih >= baslangic
        )
        .order_by(FiyatGecmisi.tarih.asc())
        .all()
    )

    gunluk_kayitlar = defaultdict(list)
    for kayit in gecmis_kayitlar:
        gunluk_kayitlar[kayit.tarih.date()].append(kayit)

    sonuc = []
    for i in range(gun_sayisi):
        gun = (baslangic + timedelta(days=i)).date()

        for kayit in gunluk_kayitlar.get(gun, []):
            son_fiyatlar[kayit.yatirim_id] = kayit.fiyat

        gunluk_toplam = Decimal('0')
        for yatirim in yatirimlar:
            fiyat = son_fiyatlar.get(yatirim.id) or yatirim.guncel_fiyat or yatirim.alis_fiyati
            gunluk_toplam += Decimal(fiyat) * Decimal(yatirim.miktar)

        sonuc.append((gun.strftime('%Y-%m-%d'), float(gunluk_toplam)))

    return sonuc


@app.route('/')
@login_required
def index():
    # Kullanıcının yatırımlarını getir
    yatirimlar = Yatirim.query.filter_by(user_id=current_user.id).order_by(Yatirim.alis_tarihi.desc()).all()

    # Performans grafik dönem seçimi
    period_map = {
        '30': ('30 Gün', 30),
        '60': ('60 Gün', 60),
        '180': ('6 Ay', 180),
        '365': ('1 Yıl', 365),
    }
    selected_period_key = request.args.get('perf_period', '30')
    if selected_period_key not in period_map:
        selected_period_key = '30'
    selected_period_label, selected_period_days = period_map[selected_period_key]
    
    ozet = hesapla_portfoy_ozeti(yatirimlar)
    toplam_yatirim_float = ozet['toplam_yatirim']
    guncel_deger_float = ozet['guncel_deger']
    kar_zarar = ozet['kar_zarar']
    kar_zarar_yuzde = ozet['kar_zarar_yuzde']
    kategori_dagilim = ozet['kategori_dagilim']
    tip_ozet = ozet['tip_ozet']
    altin_doviz_yatirim_float = ozet['altin_doviz_yatirim']
    altin_doviz_alis = ozet['altin_doviz_alis']
    altin_doviz_satis = ozet['altin_doviz_satis']
        
    # Performans sıralaması - Gruplu hesaplama
    yatirim_gruplari = grupla_yatirimlar(yatirimlar, sadece_guncel_fiyatli=True)

    
    # Grup performanslarını hesapla
    performans_siralamasi = []
    for grup in yatirim_gruplari:
        toplam_kar_zarar = grup['toplam_kar_zarar']
        ortalama_getiri = grup['ortalama_getiri']

        performans_siralamasi.append((0, YatirimPerformans(
            grup['kod'], grup['isim'], grup['tip'], 
            toplam_kar_zarar, ortalama_getiri, grup['kalemler']
        )))
    
    # En iyi 10 performansa göre sırala
    performans_siralamasi.sort(key=lambda x: x[1].getiri, reverse=True)
    performans_siralamasi = performans_siralamasi[:10]
    
    # Kategoriler listesi (filtreleme için)
    kategoriler = list(set([y.kategori for y in yatirimlar if y.kategori]))
    
    # Grafik verileri
    grafik_html = None
    if kategori_dagilim:
        try:
            fig = px.pie(
                values=list(kategori_dagilim.values()),
                names=list(kategori_dagilim.keys()),
                title='Kategoriye Göre Dağılım'
            )
            fig.update_layout(
                font=dict(color='white'),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400
            )
            grafik_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
        except Exception as e:
            app.logger.error(f"Grafik oluşturma hatası: {e}")
    
    # Seçili dönem için performans grafiği
    performans_grafik_html = None
    if yatirimlar:
        try:
            gecmis_veri = portfoy_gecmis_grafigi(current_user.id, gun_sayisi=selected_period_days)
            if gecmis_veri:
                dates = [item[0] for item in gecmis_veri]
                values = [item[1] for item in gecmis_veri]

                fig_perf = go.Figure()
                fig_perf.add_trace(go.Scatter(
                    x=dates,
                    y=values,
                    mode='lines',
                    name='Portföy Değeri',
                    line=dict(color='#17a2b8', width=3)
                ))

                fig_perf.update_layout(
                    title=f'{selected_period_label} Portföy Performansı',
                    xaxis_title='Tarih',
                    yaxis_title='Değer (₺)',
                    font=dict(color='white'),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=400
                )

                performans_grafik_html = fig_perf.to_html(full_html=False, include_plotlyjs='cdn')
        except Exception as e:
            app.logger.error(f"Performans grafiği oluşturma hatası: {e}")
    
    # Tüm Yatırımlar için gruplu veri hazırla
    yatirim_gruplari_liste = grupla_yatirimlar(yatirimlar)

    return render_template('index.html', 
                         yatirimlar=yatirimlar,
                         yatirim_gruplari=yatirim_gruplari_liste,
                         toplam_yatirim=toplam_yatirim_float,
                         guncel_deger=guncel_deger_float,
                         kar_zarar=kar_zarar,
                         kar_zarar_yuzde=kar_zarar_yuzde,
                         tip_ozet=list(tip_ozet.values()),
                         performans_siralamasi=performans_siralamasi,
                         kategoriler=kategoriler,
                         grafik_html=grafik_html,
                         performans_grafik_html=performans_grafik_html,
                         performans_period_key=selected_period_key,
                         performans_period_label=selected_period_label,
                         altin_doviz_yatirim=altin_doviz_yatirim_float,
                         altin_doviz_alis=altin_doviz_alis,
                         altin_doviz_satis=altin_doviz_satis)


@app.route('/yatirimlar')
@login_required
def yatirimlar():
    search = request.args.get('search', '')
    tip_filter = request.args.get('tip', '')
    kategori_filter = request.args.get('kategori', '')
    
    query = Yatirim.query.filter_by(user_id=current_user.id)
    
    if search:
        query = query.filter(
            (Yatirim.kod.contains(search)) |
            (Yatirim.isim.contains(search)) |
            (Yatirim.notlar.contains(search))
        )
    
    if tip_filter:
        query = query.filter(Yatirim.tip == tip_filter)
    
    if kategori_filter:
        query = query.filter(Yatirim.kategori == kategori_filter)
    
    yatirimlar = query.order_by(Yatirim.alis_tarihi.desc()).all()
    
    # Kategoriler listesi
    kategoriler = db.session.query(Yatirim.kategori).filter(
        Yatirim.user_id == current_user.id,
        Yatirim.kategori.isnot(None)
    ).distinct().all()
    kategoriler = [k[0] for k in kategoriler]
    
    yatirim_gruplari_liste = grupla_yatirimlar(yatirimlar)

    return render_template('yatirimlar.html', 
                         yatirimlar=yatirimlar,
                         yatirim_gruplari=yatirim_gruplari_liste,
                         search=search,
                         tip_filter=tip_filter,
                         kategori_filter=kategori_filter,
                         kategoriler=kategoriler)

@app.route('/yatirim_ekle', methods=['GET', 'POST'])
@login_required
def yatirim_ekle():
    if request.method == 'POST':
        try:
            tip = request.form['tip']
            kod = request.form['kod'].upper()
            alis_tarihi = datetime.strptime(request.form['alis_tarihi'], '%Y-%m-%d')
            alis_fiyati = Decimal(request.form['alis_fiyati'].replace(',', '.'))
            miktar = Decimal(request.form['miktar'].replace(',', '.'))
            notlar = request.form.get('notlar', '')
            kategori = request.form.get('kategori', '')
            
            # Duplicate check removed - allow multiple entries of same investment code
            
            yatirim = Yatirim(
                tip=tip,
                kod=kod,
                alis_tarihi=alis_tarihi,
                alis_fiyati=alis_fiyati,
                miktar=miktar,
                notlar=notlar,
                kategori=kategori,
                user_id=current_user.id
            )
            
            db.session.add(yatirim)
            db.session.commit()
            
            # İlk fiyat güncelleme ve isim doğrulama
            fiyat_guncelle(yatirim.id)
            
            # Yatırım ismini API'den gelen verilerle doğrula
            try:
                if tip == 'fon':
                    api_veri = tefas_fon_verisi_cek(kod)
                    if api_veri and 'isim' in api_veri:
                        api_isim = api_veri['isim']
                        if yatirim.isim and yatirim.isim != api_isim:
                            # İsim farklıysa güncelle ve kullanıcıyı bilgilendir
                            yatirim.isim = api_isim
                            db.session.commit()
                            flash(f'{kod} kodlu fon eklendi. İsim güncellendi: {api_isim}', 'info')
                        elif not yatirim.isim:
                            # İsim yoksa API'den al
                            yatirim.isim = api_isim
                            db.session.commit()
                elif tip == 'hisse':
                    api_veri = bist_hisse_verisi_cek(kod)
                    if api_veri and 'isim' in api_veri:
                        api_isim = api_veri['isim']
                        if yatirim.isim and yatirim.isim != api_isim:
                            yatirim.isim = api_isim
                            db.session.commit()
                            flash(f'{kod} kodlu hisse eklendi. İsim güncellendi: {api_isim}', 'info')
                        elif not yatirim.isim:
                            yatirim.isim = api_isim
                            db.session.commit()
            except Exception as e:
                app.logger.warning(f"İsim doğrulama hatası: {e}")
            
            flash(f'{kod} kodlu {tip} başarıyla eklendi!', 'success')
            return redirect(url_for('yatirimlar'))
            
        except Exception as e:
            flash(f'Yatırım eklenirken hata oluştu: {str(e)}', 'danger')
            return redirect(url_for('yatirimlar'))
    
    return redirect(url_for('yatirimlar'))

@app.route('/yatirim_sil/<int:yatirim_id>', methods=['POST'])
@login_required
def yatirim_sil(yatirim_id):
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    
    # Check if user owns this investment
    if yatirim.user_id != current_user.id:
        flash('Bu yatırıma erişim yetkiniz yok!', 'danger')
        return redirect(url_for('yatirimlar'))
    
    # İlgili fiyat geçmişini de sil
    FiyatGecmisi.query.filter_by(yatirim_id=yatirim_id).delete()
    
    db.session.delete(yatirim)
    db.session.commit()
    
    flash(f'{yatirim.kod} kodlu yatırım silindi!', 'success')
    return redirect(url_for('yatirimlar'))

@app.route('/fiyat_guncelle/<int:yatirim_id>', methods=['POST'])
@login_required
def fiyat_guncelle_route(yatirim_id):
    basarili, mesaj = fiyat_guncelle(yatirim_id)
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if basarili:
            # Get updated investment data
            yatirim = Yatirim.query.get(yatirim_id)
            if yatirim and yatirim.user_id == current_user.id:
                # Calculate updated values
                maliyet = float(yatirim.alis_fiyati * yatirim.miktar)
                if yatirim.guncel_fiyat:
                    guncel_deger = float(yatirim.guncel_fiyat * yatirim.miktar)
                    kar_zarar = guncel_deger - maliyet
                    getiri = (float(yatirim.guncel_fiyat) / float(yatirim.alis_fiyati) - 1) * 100
                else:
                    guncel_deger = maliyet
                    kar_zarar = 0
                    getiri = 0
                
                return jsonify({
                    'success': True,
                    'message': mesaj,
                    'data': {
                        'id': yatirim.id,
                        'guncel_fiyat': float(yatirim.guncel_fiyat) if yatirim.guncel_fiyat else None,
                        'guncel_deger': guncel_deger,
                        'kar_zarar': kar_zarar,
                        'getiri': getiri,
                        'son_guncelleme': yatirim.son_guncelleme.strftime('%d.%m.%Y %H:%M') if yatirim.son_guncelleme else None
                    }
                })
            else:
                return jsonify({'success': False, 'message': 'Yatırım bulunamadı'}), 404
        else:
            return jsonify({'success': False, 'message': mesaj}), 400
    else:
        # Regular form submission - redirect as before
        if basarili:
            flash(mesaj, 'success')
        else:
            flash(mesaj, 'danger')
        
        return redirect(url_for('yatirimlar'))

@app.route('/toplu_fiyat_guncelle', methods=['POST'])
@login_required
def toplu_fiyat_guncelle():
    yatirimlar = Yatirim.query.filter_by(user_id=current_user.id).all()

    altin_creds_var = bool(os.environ.get('ALTINKAYNAK_USERNAME') and os.environ.get('ALTINKAYNAK_PASSWORD'))

    basarili_count = 0
    hata_count = 0
    atlanan_altin_count = 0

    # Aynı varlığı (kod+tip) sadece bir kez çekmek için grupla
    gruplar = {}
    for yatirim in yatirimlar:
        key = f"{yatirim.tip}:{yatirim.kod.upper()}"
        if key not in gruplar:
            gruplar[key] = {
                'tip': yatirim.tip,
                'kod': yatirim.kod.upper(),
                'yatirimlar': []
            }
        gruplar[key]['yatirimlar'].append(yatirim)

    # Altın credentials yoksa altın gruplarını baştan atla
    cekilecek_gruplar = []
    for grup in gruplar.values():
        if grup['tip'] == 'altin' and not altin_creds_var:
            atlanan_altin_count += len(grup['yatirimlar'])
            continue
        cekilecek_gruplar.append(grup)

    # Dış API çağrılarını paralel yap
    cekim_sonuclari = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_key = {
            executor.submit(fiyat_verisi_cek_by_tip_kod, grup['tip'], grup['kod']): f"{grup['tip']}:{grup['kod']}"
            for grup in cekilecek_gruplar
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                cekim_sonuclari[key] = future.result()
            except Exception as e:
                app.logger.error(f"Paralel fiyat çekme hatası ({key}): {e}", exc_info=True)
                cekim_sonuclari[key] = (False, None)

    # DB yazımları tek thread'de (SQLAlchemy session güvenliği)
    for key, grup in gruplar.items():
        if grup['tip'] == 'altin' and not altin_creds_var:
            continue

        basarili, veri = cekim_sonuclari.get(key, (False, None))
        if not basarili or not veri:
            hata_count += len(grup['yatirimlar'])
            continue

        for yatirim in grup['yatirimlar']:
            yatirim.guncel_fiyat = veri['guncel_fiyat']
            yatirim.son_guncelleme = veri['tarih']

            if yatirim.tip in ['altin', 'doviz']:
                if veri.get('alis_fiyat'):
                    yatirim.guncel_alis_fiyat = veri['alis_fiyat']
                if veri.get('satis_fiyat'):
                    yatirim.guncel_satis_fiyat = veri['satis_fiyat']

            if not yatirim.isim and veri.get('isim'):
                yatirim.isim = veri['isim']

            fiyat_gecmisi = FiyatGecmisi(
                yatirim_id=yatirim.id,
                tarih=veri['tarih'],
                fiyat=veri['guncel_fiyat'],
                user_id=current_user.id
            )
            db.session.add(fiyat_gecmisi)
            basarili_count += 1

    db.session.commit()

    if basarili_count > 0:
        flash(f'{basarili_count} yatırımın fiyatı güncellendi!', 'success')

    if atlanan_altin_count > 0:
        flash(
            f'{atlanan_altin_count} altın yatırımı atlandı (ALTINKAYNAK_USERNAME/ALTINKAYNAK_PASSWORD eksik).',
            'info'
        )

    if hata_count > 0:
        flash(f'{hata_count} yatırımın fiyatı güncellenemedi!', 'warning')

    return redirect(url_for('yatirimlar'))

@app.route('/yatirim_duzenle/<int:yatirim_id>', methods=['POST'])
@login_required
def yatirim_duzenle(yatirim_id):
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    
    # Check if user owns this investment
    if yatirim.user_id != current_user.id:
        flash('Bu yatırıma erişim yetkiniz yok!', 'danger')
        return redirect(url_for('yatirimlar'))
    
    try:
        yatirim.alis_fiyati = Decimal(request.form['alis_fiyati'].replace(',', '.'))
        yatirim.miktar = Decimal(request.form['miktar'].replace(',', '.'))
        yatirim.notlar = request.form.get('notlar', '')
        yatirim.kategori = request.form.get('kategori', '')
        
        db.session.commit()
        flash('Yatırım bilgileri güncellendi!', 'success')
        
    except Exception as e:
        flash(f'Güncelleme hatası: {str(e)}', 'danger')
    
    return redirect(url_for('yatirimlar'))

@app.route('/api/yatirim/<int:yatirim_id>')
@login_required
def api_yatirim(yatirim_id):
    yatirim = Yatirim.query.get_or_404(yatirim_id)
    
    # Check if user owns this investment
    if yatirim.user_id != current_user.id:
        return jsonify({'error': 'Bu yatırıma erişim yetkiniz yok'}), 403
    
    return jsonify(yatirim.to_dict())

@app.route('/api/yatirim_dogrula', methods=['POST'])
@login_required
def api_yatirim_dogrula():
    data = request.get_json()
    tip = data.get('tip')
    kod = data.get('kod')
    
    if not tip or not kod:
        return jsonify({'success': False, 'error': 'Tip ve kod gerekli'})
    
    try:
        if tip == 'fon':
            result = tefas_fon_verisi_cek(kod)
        elif tip == 'hisse':
            result = bist_hisse_verisi_cek(kod)
        elif tip == 'altin':
            result = altin_verisi_cek(kod)
        elif tip == 'doviz':
            result = doviz_verisi_cek(kod)
        else:
            return jsonify({'success': False, 'error': 'Geçersiz yatırım tipi'})
        
        if result:
            return jsonify({
                'success': True,
                'isim': result.get('isim', 'Bilinmeyen'),
                'guncel_fiyat': float(result.get('guncel_fiyat', 0))
            })
        else:
            return jsonify({'success': False, 'error': 'Veri çekilemedi'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/yatirim_grup/<kod>')
@login_required
def api_yatirim_grup(kod):
    """Get investment group details by code"""
    yatirimlar = Yatirim.query.filter_by(
        user_id=current_user.id,
        kod=kod.upper()
    ).order_by(Yatirim.alis_tarihi.desc()).all()
    
    if not yatirimlar:
        return jsonify({'error': 'Yatırım grubu bulunamadı'}), 404
    
    kalemler = []
    for yatirim in yatirimlar:
        kalemler.append({
            'id': yatirim.id,
            'alis_tarihi': yatirim.alis_tarihi.isoformat(),
            'alis_fiyati': float(yatirim.alis_fiyati),
            'miktar': float(yatirim.miktar),
            'guncel_fiyat': float(yatirim.guncel_fiyat) if yatirim.guncel_fiyat else None,
            'kategori': yatirim.kategori,
            'notlar': yatirim.notlar
        })
    
    return jsonify({
        'kod': kod.upper(),
        'kalemler': kalemler
    })

# Portfolio Sharing Routes
@app.route('/portfolio/share')
@login_required
def share_portfolio():
    """Portföy paylaşım sayfası"""
    from models import PaylasilanPortfoy
    
    user_portfolios = PaylasilanPortfoy.query.filter_by(paylasin_id=current_user.id).all()
    yatirimlar = Yatirim.query.filter_by(user_id=current_user.id).all()
    return render_template('share_portfolio.html', portfolios=user_portfolios, yatirimlar=yatirimlar)

@app.route('/portfolio/create_share', methods=['POST'])
@login_required
def create_shared_portfolio():
    """Yeni paylaşılan portföy oluştur"""
    from models import PaylasilanPortfoy, PaylasilanYatirim
    
    try:
        baslik = request.form.get('baslik')
        aciklama = request.form.get('aciklama', '')
        is_public = request.form.get('is_public') == 'on'
        selected_investments = request.form.getlist('selected_investments')
        
        if not baslik:
            flash('Portföy başlığı gerekli', 'error')
            return redirect(url_for('share_portfolio'))
        
        # Yeni paylaşılan portföy oluştur
        portfoy = PaylasilanPortfoy(
            baslik=baslik,
            aciklama=aciklama,
            paylasin_id=current_user.id,
            is_public=is_public
        )
        db.session.add(portfoy)
        db.session.flush()  # ID'yi al
        
        # Seçilen yatırımları ekle
        for yatirim_id in selected_investments:
            yatirim = Yatirim.query.filter_by(id=yatirim_id, user_id=current_user.id).first()
            if yatirim:
                paylasilan = PaylasilanYatirim(
                    portfoy_id=portfoy.id,
                    tip=yatirim.tip,
                    kod=yatirim.kod,
                    isim=yatirim.isim,
                    alis_tarihi=yatirim.alis_tarihi,
                    alis_fiyati=yatirim.alis_fiyati,
                    miktar=yatirim.miktar,
                    notlar=yatirim.notlar,
                    kategori=yatirim.kategori
                )
                db.session.add(paylasilan)
        
        db.session.commit()
        flash('Portföy başarıyla paylaşıldı!', 'success')
        return redirect(url_for('share_portfolio'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Portföy paylaşım hatası: {str(e)}", exc_info=True)
        flash('Portföy paylaşımında hata oluştu', 'error')
        return redirect(url_for('share_portfolio'))

@app.route('/community')
def community_portfolios():
    """Topluluk portföyleri sayfası"""
    from models import PaylasilanPortfoy, User
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    portfolios = PaylasilanPortfoy.query.filter_by(is_public=True)\
        .order_by(PaylasilanPortfoy.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('community.html', portfolios=portfolios)

@app.route('/portfolio/view/<int:portfolio_id>')
def view_shared_portfolio(portfolio_id):
    """Paylaşılan portföyü görüntüle"""
    from models import PaylasilanPortfoy, PaylasilanYatirim
    
    portfoy = PaylasilanPortfoy.query.get_or_404(portfolio_id)
    
    if not portfoy.is_public and (not current_user.is_authenticated or portfoy.paylasin_id != current_user.id):
        flash('Bu portföy özel olarak paylaşılmış', 'error')
        return redirect(url_for('community_portfolios'))
    
    # Görüntülenme sayısını artır
    portfoy.view_count += 1
    db.session.commit()
    
    yatirimlar = PaylasilanYatirim.query.filter_by(portfoy_id=portfolio_id).all()
    
    return render_template('view_shared_portfolio.html', portfoy=portfoy, yatirimlar=yatirimlar)

@app.route('/portfolio/follow/<int:portfolio_id>')
@login_required
def follow_portfolio(portfolio_id):
    """Portföyü takip et"""
    from models import PaylasilanPortfoy, PortfoyTakip
    
    portfoy = PaylasilanPortfoy.query.get_or_404(portfolio_id)
    
    # Zaten takip ediliyor mu kontrol et
    existing_follow = PortfoyTakip.query.filter_by(
        takip_eden_id=current_user.id,
        portfoy_id=portfolio_id
    ).first()
    
    if existing_follow:
        flash('Bu portföyü zaten takip ediyorsunuz', 'info')
    else:
        takip = PortfoyTakip(
            takip_eden_id=current_user.id,
            portfoy_id=portfolio_id
        )
        db.session.add(takip)
        db.session.commit()
        flash(f'{portfoy.baslik} portföyünü takip etmeye başladınız', 'success')
    
    return redirect(url_for('view_shared_portfolio', portfolio_id=portfolio_id))

@app.route('/my-follows')
@login_required
def my_follows():
    """Takip edilen portföyler"""
    from models import PortfoyTakip, PaylasilanPortfoy
    
    takip_edilenler = db.session.query(PaylasilanPortfoy, PortfoyTakip)\
        .join(PortfoyTakip, PaylasilanPortfoy.id == PortfoyTakip.portfoy_id)\
        .filter(PortfoyTakip.takip_eden_id == current_user.id)\
        .order_by(PortfoyTakip.created_at.desc()).all()
    
    return render_template('my_follows.html', takip_edilenler=takip_edilenler)

@app.route('/export_portfolio_pdf')
@login_required
def export_portfolio_pdf():
    """Portföy özetini PDF olarak indir - Runtime import ile"""
    try:
        # Runtime'da WeasyPrint'i import et
        try:
            import weasyprint
            from flask import make_response
            import html
        except ImportError as e:
            app.logger.error(f"WeasyPrint import hatası: {e}")
            flash('PDF oluşturma özelliği kullanılamıyor. WeasyPrint kurulmamış olabilir.', 'error')
            return redirect(url_for('yatirimlar'))
        
        # Kullanıcının yatırımlarını getir
        yatirimlar = Yatirim.query.filter_by(user_id=current_user.id).all()
        
        ozet = hesapla_portfoy_ozeti(yatirimlar)
        toplam_yatirim_float = ozet['toplam_yatirim']
        guncel_deger_float = ozet['guncel_deger']
        kar_zarar = ozet['kar_zarar']
        kar_zarar_yuzde = ozet['kar_zarar_yuzde']
        kategori_dagilim = ozet['kategori_dagilim']
        altin_doviz_yatirim_float = ozet['altin_doviz_yatirim']
        altin_doviz_alis = ozet['altin_doviz_alis']
        altin_doviz_satis = ozet['altin_doviz_satis']
        
        # HTML içeriği oluştur
        html_content = f"""
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <title>Portföy Raporu</title>
            <style>
                @page {{
                    size: A4;
                    margin: 2cm;
                }}
                body {{
                    font-family: "DejaVu Sans", Arial, sans-serif;
                    font-size: 12px;
                    line-height: 1.4;
                    color: #333;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #007bff;
                    padding-bottom: 15px;
                }}
                .header h1 {{
                    color: #007bff;
                    margin-bottom: 5px;
                    font-size: 24px;
                }}
                .header p {{
                    color: #666;
                    margin: 5px 0;
                }}
                .summary {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 30px;
                    border-left: 4px solid #007bff;
                }}
                .summary h3 {{
                    color: #007bff;
                    margin-top: 0;
                }}
                .summary-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                }}
                .summary-item {{
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid #dee2e6;
                }}
                .summary-item:last-child {{
                    border-bottom: none;
                    font-weight: bold;
                    color: #007bff;
                }}
                .category-section {{
                    margin-bottom: 20px;
                }}
                .category-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr 1fr;
                    gap: 10px;
                    margin-bottom: 20px;
                }}
                .category-item {{
                    background-color: #f8f9fa;
                    padding: 10px;
                    border-radius: 4px;
                    text-align: center;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                    font-size: 10px;
                }}
                th, td {{
                    border: 1px solid #dee2e6;
                    padding: 6px;
                    text-align: left;
                }}
                th {{
                    background-color: #007bff;
                    color: white;
                    font-weight: bold;
                    text-align: center;
                    font-size: 9px;
                }}
                tr:nth-child(even) {{
                    background-color: #f8f9fa;
                }}
                tr:last-child {{
                    background-color: #e3f2fd;
                    font-weight: bold;
                }}
                .text-center {{ text-align: center; }}
                .text-right {{ text-align: right; }}
                .text-success {{ color: #28a745; }}
                .text-danger {{ color: #dc3545; }}
                .tip-badge {{
                    display: inline-block;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 8px;
                    font-weight: bold;
                    text-transform: uppercase;
                }}
                .tip-fon {{ background-color: #007bff; color: white; }}
                .tip-hisse {{ background-color: #28a745; color: white; }}
                .tip-altin {{ background-color: #ffc107; color: #212529; }}
                .tip-doviz {{ background-color: #17a2b8; color: white; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{html.escape(current_user.username)} - Yatırım Portföyü Raporu</h1>
                <p>Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
            </div>
            
            <div class="summary">
                <h3>Portföy Özeti</h3>
                <div class="summary-grid">
                    <div>
                        <div class="summary-item">
                            <span>Toplam Yatırım:</span>
                            <span>₺{toplam_yatirim_float:,.2f}</span>
                        </div>
                        <div class="summary-item">
                            <span>Güncel Değer:</span>
                            <span>₺{guncel_deger_float:,.2f}</span>
                        </div>
                    </div>
                    <div>
                        <div class="summary-item">
                            <span>Kar/Zarar:</span>
                            <span class="{'text-success' if kar_zarar >= 0 else 'text-danger'}">
                                ₺{kar_zarar:+,.2f}
                            </span>
                        </div>
                        <div class="summary-item">
                            <span>Getiri Oranı:</span>
                            <span class="{'text-success' if kar_zarar_yuzde >= 0 else 'text-danger'}">
                                %{kar_zarar_yuzde:+.2f}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        """
        
        # Altın ve Döviz için alış/satış fiyatları bölümü ekle
        if altin_doviz_yatirim_float > 0:
            html_content += f"""
            <div class="summary" style="border-left: 4px solid #ffc107;">
                <h3 style="color: #ffc107;">Altın & Döviz - Alış/Satış Fiyatları Karşılaştırması</h3>
                <div class="summary-grid">
                    <div>
                        <div class="summary-item">
                            <span>Toplam Yatırım:</span>
                            <span>₺{altin_doviz_yatirim_float:,.2f}</span>
                        </div>
                    </div>
                    <div style="grid-column: span 2;">
                        <table style="margin-top: 0; font-size: 11px;">
                            <thead>
                                <tr>
                                    <th>Hesaplama Türü</th>
                                    <th>Güncel Değer</th>
                                    <th>Kar/Zarar</th>
                                    <th>Getiri %</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td><strong>Alış Fiyatından</strong></td>
                                    <td class="text-right">₺{altin_doviz_alis['guncel_deger']:,.2f}</td>
                                    <td class="text-right {'text-success' if altin_doviz_alis['kar_zarar'] >= 0 else 'text-danger'}">
                                        ₺{altin_doviz_alis['kar_zarar']:+,.2f}
                                    </td>
                                    <td class="text-right {'text-success' if altin_doviz_alis['kar_zarar_yuzde'] >= 0 else 'text-danger'}">
                                        %{altin_doviz_alis['kar_zarar_yuzde']:+.2f}
                                    </td>
                                </tr>
                                <tr>
                                    <td><strong>Satış Fiyatından</strong></td>
                                    <td class="text-right">₺{altin_doviz_satis['guncel_deger']:,.2f}</td>
                                    <td class="text-right {'text-success' if altin_doviz_satis['kar_zarar'] >= 0 else 'text-danger'}">
                                        ₺{altin_doviz_satis['kar_zarar']:+,.2f}
                                    </td>
                                    <td class="text-right {'text-success' if altin_doviz_satis['kar_zarar_yuzde'] >= 0 else 'text-danger'}">
                                        %{altin_doviz_satis['kar_zarar_yuzde']:+.2f}
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                <p style="margin-top: 10px; font-size: 9px; color: #666; font-style: italic;">
                    Not: Altın ve Döviz yatırımlarınız için alış ve satış fiyatlarından hesaplanan değerler yukarıda ayrı ayrı gösterilmektedir.
                </p>
            </div>
            """
        
        # Kategori dağılımı ekle
        if kategori_dagilim:
            html_content += """
            <div class="category-section">
                <h3 style="color: #007bff;">Kategoriye Göre Dağılım</h3>
                <div class="category-grid">
            """
            for kategori, deger in kategori_dagilim.items():
                yuzde = (deger / guncel_deger_float * 100) if guncel_deger_float > 0 else 0
                html_content += f"""
                    <div class="category-item">
                        <strong>{html.escape(kategori)}</strong><br>
                        ₺{deger:,.2f}<br>
                        <small>%{yuzde:.1f}</small>
                    </div>
                """
            html_content += "</div></div>"
        
        # Yatırımlar tablosu
        if yatirimlar:
            html_content += """
            <table>
                <thead>
                    <tr>
                        <th>Tip</th>
                        <th>Kod</th>
                        <th>İsim</th>
                        <th>Alış Tarihi</th>
                        <th>Alış Fiyatı</th>
                        <th>Miktar</th>
                        <th>Güncel Fiyat</th>
                        <th>Toplam Değer</th>
                        <th>Kar/Zarar</th>
                        <th>Getiri %</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for yatirim in yatirimlar:
                alis_tutari = float(yatirim.alis_fiyati * yatirim.miktar)
                
                if yatirim.guncel_fiyat and yatirim.guncel_fiyat > 0:
                    guncel_tutar = float(yatirim.guncel_fiyat * yatirim.miktar)
                    kar_zarar_item = guncel_tutar - alis_tutari
                    getiri_yuzde = (kar_zarar_item / alis_tutari * 100) if alis_tutari > 0 else 0
                    kar_zarar_class = 'text-success' if kar_zarar_item >= 0 else 'text-danger'
                    getiri_class = 'text-success' if getiri_yuzde >= 0 else 'text-danger'
                    guncel_fiyat_str = f"₺{yatirim.guncel_fiyat:,.3f}"
                    guncel_tutar_str = f"₺{guncel_tutar:,.2f}"
                    kar_zarar_str = f"₺{kar_zarar_item:+,.2f}"
                    getiri_str = f"%{getiri_yuzde:+.2f}"
                else:
                    kar_zarar_class = ''
                    getiri_class = ''
                    guncel_fiyat_str = "-"
                    guncel_tutar_str = f"₺{alis_tutari:,.2f}"
                    kar_zarar_str = "-"
                    getiri_str = "-"
                
                html_content += f"""
                    <tr>
                        <td class="text-center">
                            <span class="tip-badge tip-{yatirim.tip}">{yatirim.tip.upper()}</span>
                        </td>
                        <td class="text-center"><strong>{html.escape(yatirim.kod)}</strong></td>
                        <td>{html.escape(yatirim.isim or '-')}</td>
                        <td class="text-center">{yatirim.alis_tarihi.strftime('%d.%m.%Y')}</td>
                        <td class="text-right">₺{yatirim.alis_fiyati:,.3f}</td>
                        <td class="text-right">{yatirim.miktar:,.2f}</td>
                        <td class="text-right">{guncel_fiyat_str}</td>
                        <td class="text-right">{guncel_tutar_str}</td>
                        <td class="text-right {kar_zarar_class}">{kar_zarar_str}</td>
                        <td class="text-right {getiri_class}">{getiri_str}</td>
                    </tr>
                """
            
            html_content += f"""
                    <tr>
                        <td colspan="4" class="text-center"><strong>TOPLAM</strong></td>
                        <td class="text-right"><strong>₺{toplam_yatirim_float:,.2f}</strong></td>
                        <td class="text-right">-</td>
                        <td class="text-right">-</td>
                        <td class="text-right"><strong>₺{guncel_deger_float:,.2f}</strong></td>
                        <td class="text-right {'text-success' if kar_zarar >= 0 else 'text-danger'}">
                            <strong>₺{kar_zarar:+,.2f}</strong>
                        </td>
                        <td class="text-right {'text-success' if kar_zarar_yuzde >= 0 else 'text-danger'}">
                            <strong>%{kar_zarar_yuzde:+.2f}</strong>
                        </td>
                    </tr>
                </tbody>
            </table>
            """
        else:
            html_content += """
            <div style="text-align: center; padding: 50px; color: #666;">
                <h3>Henüz yatırım kaydı bulunmamaktadır.</h3>
                <p>İlk yatırımınızı ekleyerek başlayın!</p>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        # PDF oluştur
        try:
            pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
            
            # Response oluştur
            response = make_response(pdf_bytes)
            filename = f"portfoy_raporu_{current_user.username}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as pdf_error:
            app.logger.error(f"PDF oluşturma hatası: {pdf_error}", exc_info=True)
            flash('PDF oluşturulurken bir hata oluştu. Lütfen tekrar deneyin.', 'error')
            return redirect(url_for('yatirimlar'))
        
    except Exception as e:
        app.logger.error(f"PDF export genel hatası: {str(e)}", exc_info=True)
        flash('PDF oluşturulurken bir hata oluştu. Lütfen tekrar deneyin.', 'error')
        return redirect(url_for('yatirimlar'))

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)

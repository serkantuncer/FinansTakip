# app.py - Ana Flask uygulaması
import os
import sys
import shutil
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
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
import xml.etree.ElementTree as ET

# Set up logging
logging.basicConfig(level=logging.DEBUG)

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
        app_data_dir = os.path.join(home_dir, ".yatirim_takip")
        
        if not os.path.exists(app_data_dir):
            os.makedirs(app_data_dir)
            print(f"Uygulama veri klasörü oluşturuldu: {app_data_dir}")
        
        target_db_path = os.path.join(app_data_dir, "finans_takip.db")
        
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
app.secret_key = os.environ.get("SESSION_SECRET", "finanstakip2025_default_secret_key")

# Database configuration - use PostgreSQL from environment
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "connect_args": {
        "sslmode": "prefer",
        "connect_timeout": 10
    }
}

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
    return User.query.get(int(user_id))

def init_database():
    """Veritabanını başlatır - tabloları oluşturur."""
    with app.app_context():
        try:
            db.create_all()
            print("Veritabanı tabloları kontrol edildi/oluşturuldu.")
            
            # Check if we need to migrate existing data
            migrate_existing_data()
            
        except Exception as e:
            print(f"Veritabanı başlatma hatası: {e}")

def migrate_existing_data():
    """Mevcut verileri user_id olmadan oluşturulmuş tablolardan yeni yapıya taşır."""
    try:
        # Check if there are any Yatirim records without user_id
        orphaned_investments = Yatirim.query.filter_by(user_id=None).all()
        
        if orphaned_investments:
            print(f"Kullanıcısız {len(orphaned_investments)} yatırım kaydı bulundu. Varsayılan kullanıcıya atanıyor...")
            
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
                print("Varsayılan admin kullanıcısı oluşturuldu (admin/admin123)")
            
            # Assign orphaned investments to default user
            for investment in orphaned_investments:
                investment.user_id = default_user.id
            
            db.session.commit()
            print(f"{len(orphaned_investments)} yatırım kaydı admin kullanıcısına atandı.")
            
    except Exception as e:
        print(f"Veri taşıma hatası: {e}")

# Uygulama başladığında veritabanını kontrol et
try:
    init_database()
except Exception as e:
    print(f"Veritabanı initialization hatası: {e}")

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
    api_url = f"https://www.isyatirim.com.tr/tr-tr/_layouts/Isyatirim.Website/Common/Data.aspx/OneEndeks?endeks={hisse_kodu_upper}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.isyatirim.com.tr/'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()

        data = response.json()
        app.logger.info(f"API'den dönen veri: {data}")

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

    altin_tipi_map = {
        'GA': 'Gram Altın',
        'C': 'Çeyrek Altın',
        'Y': 'Yarım Altın',
        'T': 'Tam Altın'
    }

    if altin_turu_kodu_upper not in altin_tipi_map:
        app.logger.error(f"Desteklenmeyen altın türü: {altin_turu_kodu_upper}")
        return None

    soap_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <GetLive xmlns="http://tempuri.org/">
          <user>{username}</user>
          <pass>{password}</pass>
        </GetLive>
      </soap:Body>
    </soap:Envelope>"""

    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/GetLive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.post(service_url, data=soap_xml, headers=headers, timeout=30)
        app.logger.debug(f"SOAP Response Status: {response.status_code}")

        if response.status_code != 200:
            app.logger.error(f"SOAP servis HTTP {response.status_code} hatası verdi.")
            return None

        xml_content = response.text
        root = ET.fromstring(xml_content)

        ns = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns': 'http://tempuri.org/'
        }

        get_live_result = root.find('.//ns:GetLiveResult', ns)
        
        if get_live_result is None:
            app.logger.error("GetLiveResult elementi bulunamadı.")
            return None

        xml_data = get_live_result.text
        data_root = ET.fromstring(xml_data)

        target_aciklama = altin_tipi_map[altin_turu_kodu_upper]

        for item in data_root.findall('item'):
            aciklama_elem = item.find('Aciklama')
            if aciklama_elem is not None and aciklama_elem.text == target_aciklama:
                satis_elem = item.find('Satis')
                if satis_elem is not None:
                    try:
                        fiyat = Decimal(satis_elem.text.replace(',', '.'))
                        
                        return {
                            'isim': target_aciklama,
                            'guncel_fiyat': fiyat,
                            'tarih': datetime.now()
                        }
                    except (InvalidOperation, ValueError) as e:
                        app.logger.error(f"Altın fiyatı Decimal'e çevrilemedi: {satis_elem.text}, hata: {e}")
                        return None

        app.logger.warning(f"Altın türü bulunamadı: {target_aciklama}")
        return None

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Altın veri çekme Request hatası: {str(e)}")
        return None
    except ET.ParseError as e:
        app.logger.error(f"XML parsing hatası: {str(e)}")
        return None
    except Exception as e:
        app.logger.error(f"Altın veri çekme genel hatası: {str(e)}", exc_info=True)
        return None

def doviz_verisi_cek(doviz_kodu):
    """TCMB'den döviz verisi çeker"""
    doviz_kodu_upper = doviz_kodu.upper()
    
    try:
        today = datetime.now()
        url = f"https://www.tcmb.gov.tr/kurlar/{today.strftime('%Y%m')}/{today.strftime('%d%m%Y')}.xml"
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        for currency in root.findall('Currency'):
            if currency.get('Kod') == doviz_kodu_upper:
                selling_elem = currency.find('BanknoteSelling')
                if selling_elem is not None and selling_elem.text:
                    try:
                        fiyat = Decimal(selling_elem.text.replace(',', '.'))
                        
                        return {
                            'isim': f"{doviz_kodu_upper}/TRY",
                            'guncel_fiyat': fiyat,
                            'tarih': datetime.now()
                        }
                    except (InvalidOperation, ValueError):
                        app.logger.error(f"Döviz fiyatı çevrilemedi: {selling_elem.text}")
                        return None
        
        app.logger.warning(f"Döviz kodu bulunamadı: {doviz_kodu_upper}")
        return None
        
    except Exception as e:
        app.logger.error(f"Döviz veri çekme hatası: {str(e)}")
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

# Ana sayfa route'u
@app.route('/')
@login_required
def index():
    # Kullanıcının yatırımlarını getir
    yatirimlar = Yatirim.query.filter_by(user_id=current_user.id).order_by(Yatirim.alis_tarihi.desc()).all()
    
    # Özet istatistikler
    toplam_yatirim = sum([float(y.alis_fiyati * y.miktar) for y in yatirimlar])
    
    guncel_deger = 0
    for y in yatirimlar:
        if y.guncel_fiyat:
            guncel_deger += float(y.guncel_fiyat * y.miktar)
        else:
            guncel_deger += float(y.alis_fiyati * y.miktar)
    
    kar_zarar = guncel_deger - toplam_yatirim
    kar_zarar_yuzde = (kar_zarar / toplam_yatirim * 100) if toplam_yatirim > 0 else 0
    
    # Kategoriye göre dağılım
    kategori_dagilim = {}
    for y in yatirimlar:
        kategori = y.kategori or 'Diğer'
        if kategori not in kategori_dagilim:
            kategori_dagilim[kategori] = 0
        
        if y.guncel_fiyat:
            kategori_dagilim[kategori] += float(y.guncel_fiyat * y.miktar)
        else:
            kategori_dagilim[kategori] += float(y.alis_fiyati * y.miktar)
    
    # Grafik verileri
    if kategori_dagilim:
        fig = px.pie(
            values=list(kategori_dagilim.values()),
            names=list(kategori_dagilim.keys()),
            title='Kategoriye Göre Dağılım'
        )
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        graphJSON = None
    
    return render_template('index.html', 
                         yatirimlar=yatirimlar[:5],  # Son 5 yatırım
                         toplam_yatirim=toplam_yatirim,
                         guncel_deger=guncel_deger,
                         kar_zarar=kar_zarar,
                         kar_zarar_yuzde=kar_zarar_yuzde,
                         kategori_dagilim=kategori_dagilim,
                         graphJSON=graphJSON)

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
    
    return render_template('yatirimlar.html', 
                         yatirimlar=yatirimlar,
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
            
            # Aynı koddan var mı kontrol et
            mevcut_yatirim = Yatirim.query.filter_by(
                user_id=current_user.id,
                tip=tip,
                kod=kod
            ).first()
            
            if mevcut_yatirim:
                flash(f'{kod} kodlu {tip} zaten portföyünüzde mevcut!', 'warning')
                return redirect(url_for('yatirimlar'))
            
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
            
            # İlk fiyat güncelleme
            fiyat_guncelle(yatirim.id)
            
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
    
    if basarili:
        flash(mesaj, 'success')
    else:
        flash(mesaj, 'danger')
    
    return redirect(url_for('yatirimlar'))

@app.route('/toplu_fiyat_guncelle', methods=['POST'])
@login_required
def toplu_fiyat_guncelle():
    yatirimlar = Yatirim.query.filter_by(user_id=current_user.id).all()
    
    basarili_count = 0
    hata_count = 0
    
    for yatirim in yatirimlar:
        basarili, _ = fiyat_guncelle(yatirim.id)
        if basarili:
            basarili_count += 1
        else:
            hata_count += 1
    
    if basarili_count > 0:
        flash(f'{basarili_count} yatırımın fiyatı güncellendi!', 'success')
    
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

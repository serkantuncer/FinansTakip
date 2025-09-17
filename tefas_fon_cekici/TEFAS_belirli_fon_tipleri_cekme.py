from tefas import Crawler
import pandas as pd
import json
from datetime import datetime, timedelta
import re
import os

class TefasFundClassifier:
    def __init__(self):
        self.crawler = Crawler()
        
        # Fon tipi tanımlama kuralları
        self.classification_rules = {
            'Para Piyasası': [
                r'PARA\s*PİYASA[SI]*',
                r'MONEY\s*MARKET',
                r'LİKİDİTE',
                r'LIQUIDITY'
            ],
            'Hisse Senedi Yoğun': [
                r'HİSSE\s*SENEDİ\s*YOĞUN',
                r'EQUITY\s*INTENSIVE',
                r'HİSSE.*YOĞUN'
            ],
            'Hisse Senedi': [
                r'HİSSE\s*SENEDİ',
                r'EQUITY',
                r'HİSSE\s*SEN',
                r'STOCKS?'
            ],
            'Borçlanma Araçları': [
                r'BORÇLANMA\s*ARAÇLAR[IİĞ]*',
                r'DEBT\s*INSTRUMENT',
                r'TAHVİL',
                r'BOND',
                r'BONO'
            ],
            'Karma': [
                r'KARMA',
                r'MİXED',
                r'BALANCED',
                r'DENGELİ'
            ],
            'Altın': [
                r'ALTIN',
                r'GOLD',
                r'PRECIOUS\s*METAL',
                r'DEĞERLİ\s*MADEN'
            ],
            'Endeks': [
                r'ENDEKS',
                r'INDEX',
                r'İNDEKS'
            ],
            'Sektör': [
                r'SEKTÖR',
                r'SECTOR',
                r'ENERJİ',
                r'ENERGY',
                r'TEKNOLOJİ',
                r'TECHNOLOGY',
                r'BANKA',
                r'BANK'
            ],
            'Gayrimenkul': [
                r'GAYRİMENKUL',
                r'REAL\s*ESTATE',
                r'GYO'
            ],
            'Emtia': [
                r'EMTİA',
                r'COMMODITY',
                r'METAL'
            ]
        }
    
    def classify_fund(self, fund_title):
        """Fon ismini analiz ederek tipini belirler"""
        title_upper = fund_title.upper()
        
        for fund_type, patterns in self.classification_rules.items():
            for pattern in patterns:
                if re.search(pattern, title_upper):
                    return fund_type
        
        return 'Diğer'
    
    def fetch_all_funds(self, date=None):
        """Tüm fonları çeker"""
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        try:
            print(f"TEFAS'tan {date} tarihli veriler çekiliyor...")
            data = self.crawler.fetch(start=date, columns=["code", "title"])
            print(f"Toplam {len(data) if data is not None else 0} fon verisi çekildi.")
            return data
        except Exception as e:
            print(f"Veri çekme hatası: {e}")
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                print(f"Bugünün ({today}) verileri deneniyor...")
                data = self.crawler.fetch(start=today, columns=["code", "title"])
                print(f"Toplam {len(data) if data is not None else 0} fon verisi çekildi.")
                return data
            except Exception as e2:
                print(f"Bugünün verisi de alınamadı: {e2}")
                return []
    
    def get_funds_by_types(self, target_types):
        """
        Belirli fon tiplerini çeker
        target_types: list - istenen fon tipleri listesi
        """
        funds_data = self.fetch_all_funds()
        
        if funds_data is None or len(funds_data) == 0:
            return {}
        
        classified_funds = {}
        
        # DataFrame'i dictionary listesine çevir
        if hasattr(funds_data, 'to_dict'):
            funds_data = funds_data.to_dict('records')
        
        for fund in funds_data:
            code = fund.get('code', '')
            title = fund.get('title', '')
            
            if not code or not title:
                continue
            
            fund_type = self.classify_fund(title)
            
            # Sadece istenen tipleri al
            if fund_type in target_types:
                if fund_type not in classified_funds:
                    classified_funds[fund_type] = []
                
                classified_funds[fund_type].append({
                    'kod': code,
                    'isim': title
                })
        
        return classified_funds
    
    def get_specific_fund_type(self, fund_type):
        """Tek bir fon tipini çeker"""
        return self.get_funds_by_types([fund_type])
    
    def create_export_folder(self):
        """Export klasörü oluştur"""
        folder_name = "tefas_fonlar_export"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            print(f"'{folder_name}' klasörü oluşturuldu.")
        return folder_name
    
    def save_to_json(self, funds_data, filename):
        """JSON formatında kaydet"""
        folder_name = self.create_export_folder()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename}_{timestamp}.json"
        filepath = os.path.join(folder_name, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(funds_data, f, ensure_ascii=False, indent=2)
        
        print(f"JSON dosyası: {filepath}")
        return filepath
    
    def save_to_excel(self, funds_data, filename):
        """Excel formatında kaydet"""
        folder_name = self.create_export_folder()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename}_{timestamp}.xlsx"
        filepath = os.path.join(folder_name, filename)
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                for fund_type, fund_list in funds_data.items():
                    if fund_list:
                        df = pd.DataFrame(fund_list)
                        sheet_name = fund_type.replace('/', '_').replace('\\', '_')[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            print(f"Excel dosyası: {filepath}")
            return filepath
        except Exception as e:
            print(f"Excel kaydetme hatası: {e}")
            return None
    
    def save_to_js_format(self, funds_data, filename):
        """JavaScript formatında kaydet"""
        folder_name = self.create_export_folder()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename}_{timestamp}.txt"
        filepath = os.path.join(folder_name, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("// TEFAS Fonları - JavaScript Formatı\n")
            f.write(f"// Oluşturma Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for fund_type, fund_list in funds_data.items():
                if fund_list:
                    safe_name = fund_type.replace(' ', '_').replace('ç', 'c').replace('ğ', 'g').replace('ı', 'i').replace('ö', 'o').replace('ş', 's').replace('ü', 'u').lower()
                    f.write(f"// {fund_type} Fonları ({len(fund_list)} adet)\n")
                    f.write(f"const {safe_name}_fonlari = [\n")
                    
                    for fund in fund_list:
                        f.write(f"  {{ kod: '{fund['kod']}', isim: '{fund['isim']}' }},\n")
                    
                    f.write("];\n\n")
        
        print(f"JavaScript dosyası: {filepath}")
        return filepath
    
    def print_funds_summary(self, funds_data):
        """Fon özetini yazdır"""
        total_funds = sum(len(fund_list) for fund_list in funds_data.values())
        print(f"\n=== FON ÖZETİ ===")
        print(f"Toplam Fon Sayısı: {total_funds}")
        print("-" * 30)
        
        for fund_type, fund_list in funds_data.items():
            print(f"{fund_type}: {len(fund_list)} adet")
    
    def show_sample_funds(self, funds_data, sample_count=5):
        """Örnek fonları göster"""
        print(f"\n=== ÖRNEK FONLAR ===")
        for fund_type, fund_list in funds_data.items():
            print(f"\n{fund_type} Fonları (İlk {min(sample_count, len(fund_list))} adet):")
            print("-" * 50)
            
            for fund in fund_list[:sample_count]:
                print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }}")
            
            if len(fund_list) > sample_count:
                print(f"... ve {len(fund_list) - sample_count} tane daha")

# KULLANIM ÖRNEKLERİ

def sadece_para_piyasasi():
    """Sadece Para Piyasası fonlarını çek"""
    print("="*60)
    print("SADECE PARA PİYASASI FONLARI")
    print("="*60)
    
    classifier = TefasFundClassifier()
    
    # Para Piyasası fonlarını çek
    funds_data = classifier.get_specific_fund_type('Para Piyasası')
    
    # Özet göster
    classifier.print_funds_summary(funds_data)
    
    # Örnek fonları göster
    classifier.show_sample_funds(funds_data, 10)
    
    # Dosyalara kaydet
    print(f"\nDosyalara kaydediliyor...")
    json_file = classifier.save_to_json(funds_data, "para_piyasasi_fonlari")
    excel_file = classifier.save_to_excel(funds_data, "para_piyasasi_fonlari")
    js_file = classifier.save_to_js_format(funds_data, "para_piyasasi_fonlari")
    
    return funds_data

def para_piyasasi_ve_hisse_senedi_yogun():
    """Para Piyasası ve Hisse Senedi Yoğun fonlarını çek"""
    print("="*60)
    print("PARA PİYASASI VE HİSSE SENEDİ YOĞUN FONLARI")
    print("="*60)
    
    classifier = TefasFundClassifier()
    
    # İstenen fon tiplerini belirle
    istenen_tipler = ['Para Piyasası', 'Hisse Senedi Yoğun']
    
    # Fonları çek
    funds_data = classifier.get_funds_by_types(istenen_tipler)
    
    # Özet göster
    classifier.print_funds_summary(funds_data)
    
    # Örnek fonları göster
    classifier.show_sample_funds(funds_data, 7)
    
    # Dosyalara kaydet
    print(f"\nDosyalara kaydediliyor...")
    json_file = classifier.save_to_json(funds_data, "para_piyasasi_ve_hisse_yogun")
    excel_file = classifier.save_to_excel(funds_data, "para_piyasasi_ve_hisse_yogun")
    js_file = classifier.save_to_js_format(funds_data, "para_piyasasi_ve_hisse_yogun")
    
    return funds_data

def ozel_fon_kombinasyonu():
    """Özel fon kombinasyonu - istediğiniz tipleri seçin"""
    print("="*60)
    print("ÖZEL FON KOMBİNASYONU")
    print("="*60)
    
    classifier = TefasFundClassifier()
    
    # İstediğiniz fon tiplerini buraya yazın
    istenen_tipler = [
        'Para Piyasası',
        'Hisse Senedi Yoğun', 
        'Altın',
        'Borçlanma Araçları'
    ]
    
    print(f"Çekilecek fon tipleri: {', '.join(istenen_tipler)}")
    
    # Fonları çek
    funds_data = classifier.get_funds_by_types(istenen_tipler)
    
    # Özet göster
    classifier.print_funds_summary(funds_data)
    
    # Örnek fonları göster
    classifier.show_sample_funds(funds_data, 3)
    
    # Dosyalara kaydet
    print(f"\nDosyalara kaydediliyor...")
    json_file = classifier.save_to_json(funds_data, "ozel_fon_kombinasyonu")
    excel_file = classifier.save_to_excel(funds_data, "ozel_fon_kombinasyonu")
    js_file = classifier.save_to_js_format(funds_data, "ozel_fon_kombinasyonu")
    
    return funds_data

def hizli_kullanim_para_piyasasi():
    """En hızlı kullanım - sadece Para Piyasası listesi"""
    classifier = TefasFundClassifier()
    funds_data = classifier.get_specific_fund_type('Para Piyasası')
    
    if 'Para Piyasası' in funds_data:
        para_piyasasi_listesi = funds_data['Para Piyasası']
        print(f"Para Piyasası Fonları ({len(para_piyasasi_listesi)} adet):")
        print("-" * 50)
        
        for fund in para_piyasasi_listesi:
            print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }},")
        
        return para_piyasasi_listesi
    else:
        print("Para Piyasası fonu bulunamadı!")
        return []

def interaktif_secim():
    """Kullanıcının seçim yapabileceği interaktif mod"""
    print("="*60)
    print("İNTERAKTİF FON SEÇİMİ")
    print("="*60)
    
    # Mevcut fon tipleri
    fon_tipleri = [
        'Para Piyasası',
        'Hisse Senedi Yoğun',
        'Hisse Senedi',
        'Borçlanma Araçları',
        'Karma',
        'Altın',
        'Endeks',
        'Sektör',
        'Gayrimenkul',
        'Emtia'
    ]
    
    print("Mevcut fon tipleri:")
    for i, tip in enumerate(fon_tipleri, 1):
        print(f"{i}. {tip}")
    
    # Kullanıcıdan seçim al
    try:
        secimler = input("\nHangi fon tiplerini istiyorsunuz? (Virgülle ayırarak sayı girin, örn: 1,2,6): ")
        secilen_indeksler = [int(x.strip()) - 1 for x in secimler.split(',')]
        
        istenen_tipler = []
        for indeks in secilen_indeksler:
            if 0 <= indeks < len(fon_tipleri):
                istenen_tipler.append(fon_tipleri[indeks])
        
        if not istenen_tipler:
            print("Geçerli seçim yapılmadı!")
            return
        
        print(f"\nSeçilen fon tipleri: {', '.join(istenen_tipler)}")
        
        # Fonları çek
        classifier = TefasFundClassifier()
        funds_data = classifier.get_funds_by_types(istenen_tipler)
        
        # Özet göster
        classifier.print_funds_summary(funds_data)
        
        # Örnek fonları göster
        classifier.show_sample_funds(funds_data, 5)
        
        # Dosyalara kaydet
        dosya_adi = "_".join([tip.replace(' ', '_').lower() for tip in istenen_tipler])
        json_file = classifier.save_to_json(funds_data, f"secili_fonlar_{dosya_adi}")
        excel_file = classifier.save_to_excel(funds_data, f"secili_fonlar_{dosya_adi}")
        js_file = classifier.save_to_js_format(funds_data, f"secili_fonlar_{dosya_adi}")
        
        return funds_data
        
    except Exception as e:
        print(f"Hata: {e}")
        print("Lütfen geçerli sayılar girin!")

# ANA ÇALIŞTIRMA BÖLÜMÜ
if __name__ == "__main__":
    print("TEFAS Belirli Fon Tipleri Çekici")
    print("="*60)
    
    # Hangi işlemi yapmak istediğinizi seçin:
    
    # 1. Sadece Para Piyasası
    print("\n1. SADECE PARA PİYASASI FONLARI:")
    #sadece_para_piyasasi()
    
    # 2. Para Piyasası + Hisse Senedi Yoğun
    print("\n" + "="*60)
    print("2. PARA PİYASASI + HİSSE SENEDİ YOĞUN:")
    #para_piyasasi_ve_hisse_senedi_yogun()
    
    # 3. Özel kombinasyon
    print("\n" + "="*60)
    print("3. ÖZEL KOMBİNASYON:")
    #ozel_fon_kombinasyonu()
    
    # 4. Hızlı kullanım (yorum satırını kaldırın)
    # print("\n" + "="*60)
    # print("4. HIZLI KULLANIM:")
    # hizli_kullanim_para_piyasasi()
    
    # 5. İnteraktif seçim (yorum satırını kaldırın)
    # print("\n" + "="*60)
    # print("5. İNTERAKTİF SEÇİM:")
    interaktif_secim()
    
    #classifier = TefasFundClassifier()
    #istenen_tipler = ['Para Piyasası', 'Hisse Senedi Yoğun', 'Altın']
    #funds_data = classifier.get_funds_by_types(istenen_tipler)
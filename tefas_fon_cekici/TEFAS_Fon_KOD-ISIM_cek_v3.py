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
        """
        Fon ismini analiz ederek tipini belirler
        """
        title_upper = fund_title.upper()
        
        # Önce daha spesifik kategorileri kontrol et
        for fund_type, patterns in self.classification_rules.items():
            for pattern in patterns:
                if re.search(pattern, title_upper):
                    return fund_type
        
        return 'Diğer'
    
    def fetch_all_funds(self, date=None):
        """
        Tüm fonları çeker ve sınıflandırır
        """
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        try:
            print(f"TEFAS'tan {date} tarihli veriler çekiliyor...")
            
            # Tüm fonları çek
            data = self.crawler.fetch(
                start=date,
                columns=["code", "title"]
            )
            
            print(f"Toplam {len(data) if data is not None else 0} fon verisi çekildi.")
            return data
            
        except Exception as e:
            print(f"Veri çekme hatası: {e}")
            print("Alternatif olarak bugünün verilerini deneyiniz...")
            
            # Eğer dün verisi yoksa bugünü dene
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                print(f"Bugünün ({today}) verileri deneniyor...")
                
                data = self.crawler.fetch(
                    start=today,
                    columns=["code", "title"]
                )
                
                print(f"Toplam {len(data) if data is not None else 0} fon verisi çekildi.")
                return data
                
            except Exception as e2:
                print(f"Bugünün verisi de alınamadı: {e2}")
                return []
    
    def get_funds_by_type(self, target_type=None):
        """
        Fonları tipine göre gruplandırır
        """
        funds_data = self.fetch_all_funds()
        
        # DataFrame kontrolü düzeltildi
        if funds_data is None or len(funds_data) == 0:
            return {}
        
        classified_funds = {}
        
        # Eğer pandas DataFrame ise dictionary listesine çevir
        if hasattr(funds_data, 'to_dict'):
            funds_data = funds_data.to_dict('records')
        
        for fund in funds_data:
            code = fund.get('code', '')
            title = fund.get('title', '')
            
            if not code or not title:
                continue
            
            fund_type = self.classify_fund(title)
            
            if fund_type not in classified_funds:
                classified_funds[fund_type] = []
            
            classified_funds[fund_type].append({
                'kod': code,
                'isim': title
            })
        
        # Eğer spesifik bir tip isteniyorsa sadece onu döndür
        if target_type and target_type in classified_funds:
            return {target_type: classified_funds[target_type]}
        
        return classified_funds
    
    def get_funds_as_dict_list(self, fund_type):
        """
        Belirli bir fon tipinin fonlarını liste olarak döndürür
        """
        funds_by_type = self.get_funds_by_type(fund_type)
        return funds_by_type.get(fund_type, [])
    
    def get_money_market_funds(self):
        """
        Sadece Para Piyasası fonlarını döndür
        """
        return self.get_funds_as_dict_list('Para Piyasası')
    
    def create_export_folder(self):
        """
        Export klasörü oluştur
        """
        folder_name = "tefas_fon_cekici/tefas_fonlar_export"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            print(f"'{folder_name}' klasörü oluşturuldu.")
        return folder_name
    
    def export_to_json(self, filename='tefas_funds.json', fund_type=None):
        """
        Sınıflandırılmış fonları JSON formatında kaydet
        """
        if fund_type:
            funds = self.get_funds_by_type(fund_type)
        else:
            funds = self.get_funds_by_type()
        
        # Export klasörü oluştur
        folder_name = self.create_export_folder()
        
        # Dosya adına tarih ekle
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = filename.replace('.json', '')
        filename = f"{base_name}_{timestamp}.json"
        filepath = os.path.join(folder_name, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(funds, f, ensure_ascii=False, indent=2)
        
        print(f"Fon listesi {filepath} dosyasına kaydedildi.")
        return filepath
    
    def export_to_js_format(self, filename='tefas_funds_js.txt', fund_type=None):
        """
        Fonları JavaScript obje formatında kaydet
        Örnek: { kod: 'ZBJ', isim: 'ZİRAAT PORTFÖY BAŞAK PARA PİYASASI (TL) FONU' },
        """
        if fund_type:
            funds = self.get_funds_by_type(fund_type)
        else:
            funds = self.get_funds_by_type()
        
        # Export klasörü oluştur
        folder_name = self.create_export_folder()
        
        # Dosya adına tarih ekle
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = filename.replace('.txt', '').replace('.js', '')
        filename = f"{base_name}_{timestamp}.txt"
        filepath = os.path.join(folder_name, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("// TEFAS Fonları - JavaScript Objesi Formatı\n")
            f.write(f"// Oluşturma Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for fund_type_name, fund_list in funds.items():
                if fund_list:
                    f.write(f"// {fund_type_name} Fonları ({len(fund_list)} adet)\n")
                    f.write(f"const {fund_type_name.replace(' ', '_').replace('ç', 'c').replace('ğ', 'g').replace('ı', 'i').replace('ö', 'o').replace('ş', 's').replace('ü', 'u').lower()}_fonlari = [\n")
                    
                    for fund in fund_list:
                        f.write(f"  {{ kod: '{fund['kod']}', isim: '{fund['isim']}' }},\n")
                    
                    f.write("];\n\n")
        
        print(f"JavaScript formatında fon listesi {filepath} dosyasına kaydedildi.")
        return filepath
    
    def export_to_excel(self, filename='tefas_funds.xlsx', fund_type=None):
        """
        Sınıflandırılmış fonları Excel formatında kaydet
        Her fon tipi ayrı sheet'te olacak
        """
        if fund_type:
            funds = self.get_funds_by_type(fund_type)
        else:
            funds = self.get_funds_by_type()
        
        if not funds:
            print("Excel'e aktarılacak veri bulunamadı!")
            return None
        
        # Export klasörü oluştur
        folder_name = self.create_export_folder()
        
        # Dosya adına tarih ekle
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = filename.replace('.xlsx', '')
        filename = f"{base_name}_{timestamp}.xlsx"
        filepath = os.path.join(folder_name, filename)
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Her fon tipi için ayrı sheet oluştur
                for fund_type_name, fund_list in funds.items():
                    if fund_list:  # Boş olmayan listeler için
                        df = pd.DataFrame(fund_list)
                        
                        # Sheet adını Excel için uygun hale getir
                        sheet_name = fund_type_name.replace('/', '_').replace('\\', '_')[:31]
                        
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Özet sheet oluştur
                summary_data = []
                for fund_type_name, fund_list in funds.items():
                    summary_data.append({
                        'Fon Tipi': fund_type_name,
                        'Fon Sayısı': len(fund_list)
                    })
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Özet', index=False)
            
            print(f"Excel dosyası {filepath} olarak kaydedildi.")
            return filepath
            
        except Exception as e:
            print(f"Excel kaydetme hatası: {e}")
            return None
    
    def export_specific_type_to_files(self, fund_type, base_name=None):
        """
        Belirli bir fon tipini hem JSON hem Excel hem de JS formatında kaydet
        """
        if not base_name:
            safe_type_name = fund_type.replace(' ', '_').replace('/', '_').lower()
            base_name = f"tefas_{safe_type_name}"
        
        # JSON olarak kaydet
        json_file = self.export_to_json(f"{base_name}.json", fund_type)
        
        # Excel olarak kaydet
        excel_file = self.export_to_excel(f"{base_name}.xlsx", fund_type)
        
        # JavaScript formatında kaydet
        js_file = self.export_to_js_format(f"{base_name}_js.txt", fund_type)
        
        return json_file, excel_file, js_file
    
    def export_all_formats(self, fund_type=None):
        """
        Tüm formatları (JSON, Excel, JS) dışa aktar
        """
        print("Tüm formatlarda dosyalar oluşturuluyor...")
        
        # JSON formatı
        json_file = self.export_to_json('tefas_funds_complete.json', fund_type)
        
        # Excel formatı
        excel_file = self.export_to_excel('tefas_funds_complete.xlsx', fund_type)
        
        # JavaScript formatı
        js_file = self.export_to_js_format('tefas_funds_js_format.txt', fund_type)
        
        print("\n=== OLUŞTURULAN DOSYALAR ===")
        print(f"JSON: {json_file}")
        print(f"Excel: {excel_file}")
        print(f"JavaScript: {js_file}")
        
        return json_file, excel_file, js_file
    
    def print_summary(self):
        """
        Fon dağılımının özetini yazdır
        """
        try:
            funds = self.get_funds_by_type()
            
            if not funds:
                print("Hiç fon verisi bulunamadı!")
                return
            
            print("=== TEFAS FON DAĞILIMI ===")
            total_funds = sum(len(fund_list) for fund_list in funds.values())
            print(f"Toplam Fon Sayısı: {total_funds}")
            print("-" * 40)
            
            for fund_type, fund_list in sorted(funds.items(), key=lambda x: len(x[1]), reverse=True):
                print(f"{fund_type:<20}: {len(fund_list):>3} adet")
                
        except Exception as e:
            print(f"Özet yazdırılırken hata: {e}")
            return
    
    def get_available_fund_types(self):
        """
        Mevcut fon tiplerini listele
        """
        funds = self.get_funds_by_type()
        return list(funds.keys())
    
    def interactive_fund_selection(self):
        """
        Kullanıcının fon tipini seçmesine olanak sağlar
        """
        available_types = self.get_available_fund_types()
        
        if not available_types:
            print("Hiç fon tipi bulunamadı!")
            return None
        
        print("\n=== MEVCUT FON TİPLERİ ===")
        for i, fund_type in enumerate(available_types, 1):
            funds_count = len(self.get_funds_as_dict_list(fund_type))
            print(f"{i}. {fund_type} ({funds_count} adet)")
        
        print(f"{len(available_types) + 1}. Tümü")
        
        try:
            choice = int(input(f"\nSeçiminizi yapın (1-{len(available_types) + 1}): "))
            
            if 1 <= choice <= len(available_types):
                return available_types[choice - 1]
            elif choice == len(available_types) + 1:
                return "Tümü"
            else:
                print("Geçersiz seçim!")
                return None
                
        except ValueError:
            print("Lütfen geçerli bir sayı girin!")
            return None

# Yardımcı fonksiyonlar
def get_specific_fund_type_data(fund_type):
    """
    Belirli bir fon tipinin verilerini al ve dosyalara kaydet
    """
    classifier = TefasFundClassifier()
    json_file, excel_file, js_file = classifier.export_specific_type_to_files(fund_type)
    
    # Fonları da döndür
    funds = classifier.get_funds_as_dict_list(fund_type)
    print(f"{fund_type} fonları:")
    print(f"Toplam {len(funds)} adet fon bulundu.")
    
    # İlk 5 tanesini göster
    for fund in funds[:5]:
        print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }}")
    
    if len(funds) > 5:
        print(f"... ve {len(funds) - 5} tane daha")
    
    print(f"\nDosyalar:")
    print(f"- JSON: {json_file}")
    print(f"- Excel: {excel_file}")
    print(f"- JavaScript: {js_file}")
    
    return json_file, excel_file, js_file

def get_multiple_fund_types_data(fund_types_list):
    """
    Birden fazla fon tipinin verilerini al
    """
    classifier = TefasFundClassifier()
    results = {}
    
    for fund_type in fund_types_list:
        funds = classifier.get_funds_as_dict_list(fund_type)
        results[fund_type] = funds
        print(f"{fund_type}: {len(funds)} adet")
    
    return results

# Kullanım örneği
def main():
    classifier = TefasFundClassifier()
    
    print("TEFAS fonları analiz ediliyor...")
    
    # Özet bilgi yazdır
    classifier.print_summary()
    
    # Para Piyasası fonlarını al
    print("\n=== PARA PİYASASI FONLARI ===")
    para_piyasasi = classifier.get_money_market_funds()
    
    for fund in para_piyasasi[:10]:  # İlk 10 tanesini göster
        print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }}")
    
    if len(para_piyasasi) > 10:
        print(f"... ve {len(para_piyasasi) - 10} tane daha")
    
    # Tüm fonları JSON ve Excel olarak kaydet
    print("\n=== DOSYALARA KAYDETME ===")
    json_file, excel_file, js_file = classifier.export_all_formats()
    
    # Hisse Senedi fonlarını al - HATA DÜZELTİLDİ
    print("\n=== HİSSE SENEDİ FONLARI (İlk 5) ===")
    hisse_senedi = classifier.get_funds_as_dict_list('Hisse Senedi')
    for fund in hisse_senedi[:5]:
        print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }}")

# Özelleştirilmiş kullanım örnekleri - DÜZELTME YAPILDI
def ozel_kullanim_ornekleri():
    """
    Farklı kullanım senaryoları
    """
    print("\n" + "="*60)
    print("ÖZEL KULLANIM ÖRNEKLERİ")
    print("="*60)
    
    # 1. Sadece Para Piyasası fonları - HATA DÜZELTİLDİ
    print("\n1. SADECE PARA PİYASASI FONLARI:")
    print("-" * 40)
    json_file, excel_file, js_file = get_specific_fund_type_data('Para Piyasası')  # 3 değişken
    
    # 2. Birden fazla fon tipi
    print("\n2. BİRDEN FAZLA FON TİPİ:")
    print("-" * 40)
    istenen_tipler = ['Para Piyasası', 'Hisse Senedi', 'Altın']
    sonuclar = get_multiple_fund_types_data(istenen_tipler)
    
    for tip, fonlar in sonuclar.items():
        print(f"\n{tip} - İlk 3 fon:")
        for fund in fonlar[:3]:
            print(f"  {{ kod: '{fund['kod']}', isim: '{fund['isim']}' }}")

def interaktif_kullanim():
    """
    Kullanıcının seçim yapabileceği interaktif mod
    """
    print("\n" + "="*60)
    print("İNTERAKTİF KULLANIM")
    print("="*60)
    
    classifier = TefasFundClassifier()
    
    # Kullanıcıdan fon tipi seçmesini iste
    selected_type = classifier.interactive_fund_selection()
    
    if selected_type:
        if selected_type == "Tümü":
            print("\nTüm fonlar için dosyalar oluşturuluyor...")
            json_file, excel_file, js_file = classifier.export_all_formats()
        else:
            print(f"\n'{selected_type}' fonları için dosyalar oluşturuluyor...")
            json_file, excel_file, js_file = get_specific_fund_type_data(selected_type)

# Basit kullanım örneği (hızlı başlangıç için)
def basit_kullanim():
    """
    Tek bir fon tipini hızlı şekilde almak için
    """
    print("\n" + "="*60)
    print("BASİT/HIZLI KULLANIM")
    print("="*60)
    
    classifier = TefasFundClassifier()
    
    # Para Piyasası fonlarını al
    para_piyasasi_funds = classifier.get_money_market_funds()
    
    print("Para Piyasası Fonları:")
    print("-" * 40)
    # İstediğiniz formatta yazdır
    for fund in para_piyasasi_funds:
        print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }},")
    
    # Para Piyasası fonlarını dosyalara kaydet
    print(f"\nPara Piyasası fonları dosyalara kaydediliyor...")
    json_file, excel_file, js_file = classifier.export_specific_type_to_files('Para Piyasası')
    
    print(f"\nOluşturulan dosyalar:")
    print(f"- JSON: {json_file}")
    print(f"- Excel: {excel_file}")
    print(f"- JavaScript: {js_file}")

if __name__ == "__main__":
    # Hangi modu çalıştırmak istediğinizi seçin:
    
    # 1. Ana detaylı analiz
    main()
    
    # 2. Özel kullanım örnekleri
    ozel_kullanim_ornekleri()
    
    # 3. İnteraktif kullanım (yorum satırını kaldırın)
    # interaktif_kullanim()
    
    # 4. Basit/hızlı kullanım
    basit_kullanim()
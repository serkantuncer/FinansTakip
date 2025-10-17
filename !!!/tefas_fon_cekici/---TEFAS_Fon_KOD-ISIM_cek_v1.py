from tefas import Crawler
import pandas as pd
import json
from datetime import datetime, timedelta
import re

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
    
    def get_money_market_funds(self):
        """
        Sadece Para Piyasası fonlarını döndür
        """
        all_funds = self.get_funds_by_type('Para Piyasası')
        return all_funds.get('Para Piyasası', [])
    
    def export_to_json(self, filename='tefas_funds.json'):
        """
        Sınıflandırılmış fonları JSON formatında kaydet
        """
        funds = self.get_funds_by_type()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(funds, f, ensure_ascii=False, indent=2)
        
        print(f"Fon listesi {filename} dosyasına kaydedildi.")
        return filename
    
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
    
    def get_funds_as_dict_list(self, fund_type=None):
        """
        Fonları istenen formatta liste olarak döndür
        Örnek: [{'kod': 'TLI', 'isim': 'TÜRK LİRASI PARA PİYASASI FONU'}]
        """
        if fund_type:
            funds = self.get_funds_by_type(fund_type)
            return funds.get(fund_type, [])
        else:
            all_funds = self.get_funds_by_type()
            result = []
            for fund_list in all_funds.values():
                result.extend(fund_list)
            return result

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
    
    # JSON olarak kaydet
    classifier.export_to_json()
    
    # Hisse Senedi fonlarını al
    print("\n=== HİSSE SENEDİ FONLARI (İlk 5) ===")
    hisse_senedi = classifier.get_funds_as_dict_list('Hisse Senedi')
    for fund in hisse_senedi[:5]:
        print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }}")

# Basit kullanım örneği
def basit_kullanim():
    """
    Tek bir fon tipini hızlı şekilde almak için
    """
    classifier = TefasFundClassifier()
    
    # Para Piyasası fonlarını al
    para_piyasasi_funds = classifier.get_money_market_funds()
    
    print("Para Piyasası Fonları:")
    print("-" * 40)
    # İstediğiniz formatta yazdır
    for fund in para_piyasasi_funds:
        print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }},")
        
def ozel_kullanim():
    classifier = TefasFundClassifier()
    
    # Sadece istediğiniz fon tiplerini al
    print("=== SADECE PARA PİYASASI FONLARI ===")
    para_piyasasi = classifier.get_funds_as_dict_list('Para Piyasası')
    for fund in para_piyasasi:
        print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }},")
    
    print("\n=== SADECE HİSSE SENEDİ FONLARI ===")
    hisse_senedi = classifier.get_funds_as_dict_list('Hisse Senedi')
    for fund in hisse_senedi:
        print(f"{{ kod: '{fund['kod']}', isim: '{fund['isim']}' }},")


if __name__ == "__main__":
    # Ana fonksiyonu çalıştır (detaylı analiz)
    main()
    
    print("\n" + "="*60)
    print("BASİT KULLANIM ÖRNEĞİ:")
    print("="*60)
    
    # Basit kullanım örneği
    basit_kullanim()
    #ozel_kullanim()
    
import unittest
from datetime import datetime
from decimal import Decimal

from app import app, stopaj_orani_bul, stopaj_hesapla


class DummyYatirim:
    def __init__(self, fon_grubu, alis_tarihi, alis_fiyati, miktar, guncel_fiyat):
        self.tip = "fon"
        self.fon_grubu = fon_grubu
        self.alis_tarihi = alis_tarihi
        self.alis_fiyati = Decimal(str(alis_fiyati))
        self.miktar = Decimal(str(miktar))
        self.guncel_fiyat = Decimal(str(guncel_fiyat))


class StopajKurallariTest(unittest.TestCase):
    def test_grup_a_2025_oncesi_sifir(self):
        with app.app_context():
            oran = stopaj_orani_bul(
                "A",
                datetime(2025, 7, 8),
                datetime(2025, 7, 20),
            )
        self.assertEqual(oran, Decimal("0"))

    def test_grup_a_2025_sonrasi_1_yildan_az_175(self):
        with app.app_context():
            oran = stopaj_orani_bul(
                "A",
                datetime(2025, 7, 9),
                datetime(2026, 7, 8),
            )
        self.assertEqual(oran, Decimal("17.5"))

    def test_grup_a_2025_sonrasi_1_yil_ve_uzeri_sifir(self):
        with app.app_context():
            oran = stopaj_orani_bul(
                "A",
                datetime(2025, 7, 9),
                datetime(2026, 7, 9),
            )
        self.assertEqual(oran, Decimal("0"))

    def test_grup_b_donem_gecisleri(self):
        with app.app_context():
            oran_2020 = stopaj_orani_bul("B", datetime(2020, 12, 22), datetime(2021, 1, 5))
            oran_2021 = stopaj_orani_bul("B", datetime(2021, 1, 10), datetime(2021, 2, 1))
            oran_2025 = stopaj_orani_bul("B", datetime(2025, 7, 9), datetime(2025, 8, 1))

        self.assertEqual(oran_2020, Decimal("10"))
        self.assertEqual(oran_2021, Decimal("0"))
        self.assertEqual(oran_2025, Decimal("17.5"))

    def test_stopaj_hesapla_kar_varsa_uygulanir(self):
        yatirim = DummyYatirim(
            fon_grubu="B",
            alis_tarihi=datetime(2025, 7, 10),
            alis_fiyati="100",
            miktar="1",
            guncel_fiyat="120",
        )
        with app.app_context():
            sonuc = stopaj_hesapla(yatirim, satis_tarihi=datetime(2025, 8, 10))

        self.assertEqual(sonuc["stopaj_orani"], Decimal("17.5"))
        self.assertEqual(sonuc["brut_kar"], Decimal("20"))
        self.assertEqual(sonuc["stopaj_tutari"], Decimal("3.5"))
        self.assertEqual(sonuc["net_kar"], Decimal("16.5"))

    def test_stopaj_hesapla_zarar_varsa_stopaj_sifir(self):
        yatirim = DummyYatirim(
            fon_grubu="B",
            alis_tarihi=datetime(2025, 7, 10),
            alis_fiyati="100",
            miktar="1",
            guncel_fiyat="80",
        )
        with app.app_context():
            sonuc = stopaj_hesapla(yatirim, satis_tarihi=datetime(2025, 8, 10))

        self.assertEqual(sonuc["stopaj_orani"], Decimal("17.5"))
        self.assertEqual(sonuc["brut_kar"], Decimal("-20"))
        self.assertEqual(sonuc["stopaj_tutari"], Decimal("0"))
        self.assertEqual(sonuc["net_kar"], Decimal("-20"))


if __name__ == "__main__":
    unittest.main()

import unittest
import uuid
import re
from datetime import datetime
from decimal import Decimal

from app import app, db
from models import StopajOrani, User, Yatirim


class StopajApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["WTF_CSRF_CHECK_DEFAULT"] = False

    def setUp(self):
        self.client = app.test_client()
        self._create_user_and_fon()

    def tearDown(self):
        with app.app_context():
            StopajOrani.query.filter(StopajOrani.aciklama.like("test-api-%")).delete()
            Yatirim.query.filter_by(user_id=self.user_id).delete()
            User.query.filter_by(id=self.user_id).delete()
            db.session.commit()

    def _create_user_and_fon(self):
        uid = uuid.uuid4().hex[:10]
        with app.app_context():
            user = User(
                username=f"test_user_{uid}",
                email=f"test_{uid}@example.com",
                password_hash="dummy_hash"
            )
            db.session.add(user)
            db.session.commit()

            fon = Yatirim(
                tip="fon",
                kod=f"TST{uid[:3].upper()}",
                isim="Test Fon",
                alis_tarihi=datetime(2025, 7, 10),
                alis_fiyati=Decimal("100"),
                miktar=Decimal("10"),
                guncel_fiyat=Decimal("120"),
                fon_grubu="B",
                user_id=user.id
            )
            db.session.add(fon)
            db.session.commit()

            self.user_id = user.id
            self.yatirim_id = fon.id

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.user_id)
            sess["_fresh"] = True

    def _csrf_headers(self):
        resp = self.client.get("/stopaj_oranlari")
        html = resp.get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        if not match:
            return {}
        return {"X-CSRFToken": match.group(1)}

    def test_stopaj_simulasyon_requires_auth(self):
        resp = self.client.post(
            f"/api/stopaj_simulasyon/{self.yatirim_id}",
            json={"satis_fiyati": "130", "satis_tarihi": "2026-01-01"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_stopaj_simulasyon_success(self):
        self._login()
        headers = self._csrf_headers()
        resp = self.client.post(
            f"/api/stopaj_simulasyon/{self.yatirim_id}",
            json={"satis_fiyati": "130", "satis_tarihi": "2026-01-01"},
            headers=headers
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("net_kar", data)
        self.assertEqual(data["fon_grubu"], "B")

    def test_stopaj_simulasyon_invalid_price(self):
        self._login()
        headers = self._csrf_headers()
        resp = self.client.post(
            f"/api/stopaj_simulasyon/{self.yatirim_id}",
            json={"satis_fiyati": "abc", "satis_tarihi": "2026-01-01"},
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_stopaj_orani_ekle_invalid_group(self):
        self._login()
        headers = self._csrf_headers()
        resp = self.client.post(
            "/api/stopaj_orani_ekle",
            json={
                "fon_grubu": "X",
                "donem_baslangic": "2026-01-01",
                "oran": "10",
                "aciklama": "test-api-invalid"
            },
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_stopaj_orani_ekle_overlap_rejected(self):
        self._login()
        headers = self._csrf_headers()
        resp = self.client.post(
            "/api/stopaj_orani_ekle",
            json={
                "fon_grubu": "B",
                "donem_baslangic": "2026-01-01",
                "donem_bitis": "",
                "elde_tutma_gun": None,
                "oran": "17.5",
                "aciklama": "test-api-overlap"
            },
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_stopaj_orani_ekle_non_overlap_success(self):
        self._login()
        headers = self._csrf_headers()
        resp = self.client.post(
            "/api/stopaj_orani_ekle",
            json={
                "fon_grubu": "B",
                "donem_baslangic": "1990-01-01",
                "donem_bitis": "1999-12-31",
                "elde_tutma_gun": None,
                "oran": "10",
                "aciklama": "test-api-non-overlap"
            },
            headers=headers
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("id", data)


if __name__ == "__main__":
    unittest.main()

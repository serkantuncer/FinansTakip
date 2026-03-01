# Finans Takip Sistemi

## Fon Stopaj Hesabı (Özet)

- Stopaj hesaplaması yalnızca **fon** yatırımları için uygulanır.
- Stopaj, yalnızca **pozitif kar** üzerinde hesaplanır.
- Zarar durumunda stopaj `0` kabul edilir.
- Uygulanan oran:
  - Fon grubu (`A/B/C/D`)
  - Alış tarihi (dönem aralığı)
  - Elde tutma süresi (gün)
  bilgilerine göre belirlenir.

Formül:

`brüt_kar = (satış_fiyatı * miktar) - (alış_fiyatı * miktar)`

`stopaj_tutarı = brüt_kar > 0 ise (brüt_kar * stopaj_oranı / 100), değilse 0`

`net_kar = brüt_kar - stopaj_tutarı`

## API Kısa Kullanım

Not:
- Tüm çağrılar oturum açıkken yapılmalıdır.
- CSRF koruması aktif olduğundan `csrf_token` gönderilmelidir.

### 1) Stopaj Simülasyonu

`POST /api/stopaj_simulasyon/<yatirim_id>`

Örnek form-data:

- `satis_tarihi=2026-03-01`
- `satis_fiyati=12.45`
- `csrf_token=<token>`

Örnek başarılı yanıt (JSON):

```json
{
  "success": true,
  "sonuc": {
    "brut_kar": 1520.35,
    "stopaj_orani": 17.5,
    "stopaj_tutari": 266.06,
    "net_kar": 1254.29,
    "elde_tutma_gun": 214
  }
}
```

### 2) Yeni Stopaj Dönemi Ekleme

`POST /api/stopaj_orani_ekle`

Örnek form-data:

- `fon_grubu=B`
- `donem_baslangic=2026-01-01`
- `donem_bitis=`
- `elde_tutma_gun=`
- `oran=17.5`
- `aciklama=TL Standart - Güncel`
- `csrf_token=<token>`

Örnek başarılı yanıt (JSON):

```json
{
  "success": true,
  "message": "Stopaj oranı dönemi eklendi."
}
```

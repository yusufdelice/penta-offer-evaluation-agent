# Penta Teknoloji — Mock Veri Dosyaları ve Mock Servis Yaklaşımı

> **Referans:** Case Study Şartnamesi (Bölüm 2) — *“Mock veri dosyaları veya mock servis yaklaşımının açıklaması”* teslimat çıktısı olarak hazırlanmıştır.

---

## 1. Mimari Yaklaşım ve Konumlandırma

Kurumsal teknoloji dağıtıcısı mimarisinde teklifler CRM ve ERP sistemleriyle çapraz doğrulanır. Bu prototipte SAP ve Salesforce gibi kurumsal sistemler simüle edilirken, kod içerisine statik Python sözlükleri gömmek (`mock_db = {...}`) yerine; bağımsız, temiz ve gerçekçi **harici JSON veri dosyaları** (`data/`) ve bu dosyaları dış dünyadan soyutlayan **Servis / Adaptör Deseni (Service & Adapter Pattern)** kullanılmıştır.

---

## 2. Mock Veri Dosyalarının Yapısı (`data/`)

### A. `data/offers.json` (Mock CRM Teklif Veritabanı)
Sistemde kayıtlı ve geçerli teklifleri temsil eder:
```json
[
  {
    "offer_id": "OFF-10023",
    "customer": {
      "name": "ABC Teknoloji",
      "segment": "strategic_partner"
    },
    "product_id": "PRD-445",
    "quantity": 8,
    "requested_discount": 12,
    "offer_total": 125000
  },
  {
    "offer_id": "OFF-20001",
    "customer": {
      "name": "Yeni Müşteri A.Ş.",
      "segment": "standard"
    },
    "product_id": "PRD-101",
    "quantity": 2,
    "requested_discount": 5,
    "offer_total": 2280
  }
]
```

### B. `data/stock.json` (Mock ERP Depo ve Stok Envanteri)
Ürünlerin güncel depo fiziki stok adetlerini tutar:
```json
{
  "PRD-445": { "stock_quantity": 50 },
  "PRD-101": { "stock_quantity": 250 },
  "PRD-999": { "stock_quantity": 5 }
}
```

### C. `data/prices.json` (Mock ERP Maliyet ve Taban Liste Fiyatları)
Ürünlerin liste satış fiyatı (`base_price`) ve satın alma maliyetini (`cost_price`) tutar:
```json
{
  "PRD-445": { "base_price": 17755.68, "cost_price": 14200.0 },
  "PRD-101": { "base_price": 1200.0, "cost_price": 800.0 },
  "PRD-999": { "base_price": 5000.0, "cost_price": 4500.0 }
}
```

---

## 3. Mock Servis Deseni (Service & Adapter Pattern)

Veri dosyaları doğrudan karar motorunun içine gömülmez; bağımsız istemci servisleri üzerinden soyutlanır:

### 1. `CRMClient` (`app/services/crm_client.py`)
- `data/offers.json` dosyasını diskten okuyup `offer_id` anahtarıyla bellekte indeksler.
- `get_offer(offer_id)` metodu ile teklifin varlığını ve müşteri segmentini döner. Kayıt yoksa `None` döner.
- `customer` nesnesi üzerinden müşteri unvanı ve segment doğrulamasını sağlar.

### 2. `ERPClient` (`app/services/erp_client.py`)
- `data/stock.json` ve `data/prices.json` dosyalarını dinamik okur.
- `get_product_data(product_id, requested_discount)` metodu ile bayinin talep ettiği indirimi taban fiyata uygulayarak **net kar marjını** matematiksel olarak hesaplar:
  ```text
  İndirimli Fiyat = Taban Liste Fiyatı * (1 - (Talep Edilen İndirim / 100))
  Net Kar Marjı (%) = ((İndirimli Fiyat - Satın Alma Maliyeti) / İndirimli Fiyat) * 100
  ```
- Ürün ERP'de yoksa `{"exists": False}` döner.

---

## 4. Entegrasyon Güvenliği ve Hata Yönetimi

- Eğer veri dosyalarından biri fiziksel olarak silinirse veya erişilemezse, istemciler kontrollü bir `FileNotFoundError` fırlatır.
- API katmanı (`app/api/routes.py`) bu hatayı yakalayarak istemciye genel bir `500` hatası yerine, entegrasyon kopukluğunu net belirten `HTTP 502 Bad Gateway` ("Kurumsal sistem entegrasyon veri dosyası bulunamadı") yanıtı döner.
- Bu durum denetim günlüğüne (`logs/audit.log`) ilgili `request_id` ile `OFFER_ERROR` etiketiyle işlenir.

---

## 5. Canlı Kurumsal Sistemlere Geçiş (Enterprise Transition)

Prototipte uygulanan servis deseni sayesinde sistem canlıya alınırken:
- `DecisionEngine` ve API katmanında hiçbir kod değişikliği gerekmez.
- `CRMClient` içerisindeki JSON dosya okuma mantığı Salesforce REST / Dynamics OData API istemcisiyle değiştirilir.
- `ERPClient` içerisindeki JSON dosya okuma mantığı SAP RFC / BAPI veya REST servisleriyle değiştirilir.
- Yüksek çağrı hacminde ERP yükünü azaltmak amacıyla istemcilerin önüne 5-10 dakikalık bir Redis önbellekleme (caching) katmanı konumlandırılabilir.

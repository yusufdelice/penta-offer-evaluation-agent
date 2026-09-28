# Penta Teknoloji — Örnek cURL İstekleri ve Yanıtlar

> **Referans:** Case Study Şartnamesi (Bölüm 2) — *“Örnek cURL veya Postman istekleri ile örnek yanıtlar”* teslimat çıktısı olarak hazırlanmıştır.

Bu dokümanda, sistemin tüm karar yollarını (`APPROVE`, `REJECT`, `NEED_APPROVAL`) ve Pydantic girdi doğrulama hatalarını test eden uçtan uca örnekler listelenmiştir. Her senaryo için hem **Mock Modu (`LLM_MODE=mock`)** hem de **Canlı Groq Modu (`LLM_MODE=groq`)** yanıtları sunulmuştur.

---

## 1. Test Senaryoları Özeti

| # | Senaryo | Test Edilen Durum | Beklenen Karar | Gerekçe Kodları |
|---|---|---|---|---|
| **1** | **Düşük Marj & Yüksek Tutar** | 125.000 TL (>100k) & %12 indirim sonrası net marj %9.09 (<%10) | `NEED_APPROVAL` | `LOW_MARGIN`, `HIGH_VALUE_OFFER` |
| **2** | **Normal Teklif** | 2 adet stok (250 adet mevcut), %5 indirim sonrası net marj %29.82 (>%15) | `APPROVE` | `ALL_CRITERIA_MET` |
| **3** | **Kritik Stok Yetersizliği** | 25 adet talep, depoda 5 adet mevcut (Karşılama oranı %20 < %70) | `REJECT` | `INSUFFICIENT_STOCK`, `LOW_MARGIN`, `HIGH_VALUE_OFFER` |
| **4** | **Geçersiz İstek (Validasyon)** | Negatif ürün adedi (`quantity: -5`) | `HTTP 422` | `greater_than` doğrulama hatası |

---

## 2. Swagger UI ile İnteraktif Test Adımları

Uygulamayı başlattıktan sonra (`uvicorn app.main:app --reload --port 8000`):
1. Tarayıcınızda `http://localhost:8000/docs` adresini açın.
2. **`POST /evaluate-offer`** paneline tıklayıp **Try it out** butonuna basın.
3. Aşağıdaki örnek JSON gövdelerinden birini yapıştırıp mavi **Execute** butonuna tıklayın.

---

## 3. Senaryolar ve cURL Örnekleri

### Senaryo 1: Düşük Marj ve Yüksek Tutar (Yönetici Onayı - NEED_APPROVAL)

```bash
curl -X POST "http://localhost:8000/evaluate-offer" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": "OFF-10023",
    "customer": {"name": "ABC Teknoloji", "email": "buyer@example.com"},
    "product_id": "PRD-445",
    "quantity": 8,
    "requested_discount": 12,
    "offer_total": 125000,
    "customer_segment": "strategic_partner"
  }'
```

**A) Mock Modu Yanıtı (`LLM_MODE=mock` — Araç Çağırma Destekli):**
```json
{
  "request_id": "37753a44-a788-4faa-9045-f84cd730dba9",
  "offer_id": "OFF-10023",
  "decision": "NEED_APPROVAL",
  "reason_codes": [
    "LOW_MARGIN",
    "HIGH_VALUE_OFFER"
  ],
  "ai_summary": "OFF-10023 numaralı teklif için CRM sistemi üzerinden 'strategic_partner' segmenti doğrulandı. ERP sisteminde mevcut stok 50 adet, hesaplanan net marj %9.09 seviyesindedir. Belirlenen iş kuralı gerekçeleri (LOW_MARGIN, HIGH_VALUE_OFFER) doğrultusunda yönetici onayı gerekmektedir.",
  "approval_required": true,
  "approval_message_draft": "OFF-10023 teklifi A** T******** için LOW_MARGIN, HIGH_VALUE_OFFER gerekçeleriyle onayınıza sunulmuştur.",
  "pii_masked": true
}
```

**B) Canlı LLM Yanıtı (`LLM_MODE=groq` — Qwen / LLaMA Üzerinden Üretim):**
```json
{
  "request_id": "0fba2488-ed3f-4106-8a26-2644b1a584c9",
  "offer_id": "OFF-10023",
  "decision": "NEED_APPROVAL",
  "reason_codes": [
    "LOW_MARGIN",
    "HIGH_VALUE_OFFER"
  ],
  "ai_summary": "Stratejik partner A** T********'a ait 125.000 TL tutarındaki teklif, %12 indirimle net marjı %9,09'a düşürdüğü ve yüksek tutarlı olması nedeniyle onaya sevk edildi. Stok durumu (50 adet) uygun görünüyor.",
  "approval_required": true,
  "approval_message_draft": "Sayın Yöneticim, OFF-10023 numaralı teklif (müşteri: A** T********, segment: stratejik partner) %12 indirim talebiyle net marjı %9,09'a çekmekte olup 125.000 TL tutarıyla yüksek limit eşiğini aşmaktadır. Stok yeterlidir (50 adet). Stratejik ilişki gözetilerek onayınızı rica ederim.",
  "pii_masked": true
}
```

---

### Senaryo 2: Normal Teklif (Tüm Kriterler Uygun — APPROVE)

```bash
curl -X POST "http://localhost:8000/evaluate-offer" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": "OFF-20001",
    "customer": {"name": "Yeni Müşteri A.Ş."},
    "product_id": "PRD-101",
    "quantity": 2,
    "requested_discount": 5,
    "offer_total": 2280,
    "customer_segment": "standard"
  }'
```

**A) Mock Modu Yanıtı (`LLM_MODE=mock`):**
```json
{
  "request_id": "7769e3f8-7395-46c3-b1ee-bd93b8ef5d90",
  "offer_id": "OFF-20001",
  "decision": "APPROVE",
  "reason_codes": [
    "ALL_CRITERIA_MET"
  ],
  "ai_summary": "OFF-20001 numaralı teklif için CRM sistemi üzerinden 'standard' segmenti doğrulandı. ERP sisteminde mevcut stok 250 adet, hesaplanan net marj %29.82 seviyesindedir. Stok, kar marjı ve veri bütünlüğü kriterleri sağlandığı için teklif onaylanmıştır.",
  "approval_required": false,
  "approval_message_draft": null,
  "pii_masked": true
}
```

**B) Canlı LLM Yanıtı (`LLM_MODE=groq`):**
```json
{
  "request_id": "0e9ebaca-1594-4478-b3b5-2e03d24ecf9c",
  "offer_id": "OFF-20001",
  "decision": "APPROVE",
  "reason_codes": [
    "ALL_CRITERIA_MET"
  ],
  "ai_summary": "Teklif, standart segmentteki Y*** M****** A*** müşterisine ait olup toplam 2.280 tutarındadır. ERP'de 250 adet stok mevcut olup %5 indirim sonrası net kar marjı %29,82 ile sağlıklı seviyededir; tüm kriterler sağlandığından karar APPROVE olarak onaylanmıştır.",
  "approval_required": false,
  "approval_message_draft": null,
  "pii_masked": true
}
```

---

### Senaryo 3: Kritik Stok Yetersizliği (Doğrudan Ret — REJECT)

```bash
curl -X POST "http://localhost:8000/evaluate-offer" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": "OFF-10023",
    "customer": {"name": "ABC Teknoloji"},
    "product_id": "PRD-999",
    "quantity": 25,
    "requested_discount": 5,
    "offer_total": 118750,
    "customer_segment": "strategic_partner"
  }'
```

**A) Mock Modu Yanıtı (`LLM_MODE=mock`):**
```json
{
  "request_id": "f7ef9940-bd5f-4ad8-a9f9-5d0e4eb36eb7",
  "offer_id": "OFF-10023",
  "decision": "REJECT",
  "reason_codes": [
    "INSUFFICIENT_STOCK",
    "LOW_MARGIN",
    "HIGH_VALUE_OFFER"
  ],
  "ai_summary": "OFF-10023 numaralı teklif için CRM sistemi üzerinden 'strategic_partner' segmenti doğrulandı. ERP sisteminde mevcut stok 5 adet, hesaplanan net marj %5.26 seviyesindedir. Belirlenen gerekçeler (INSUFFICIENT_STOCK, LOW_MARGIN, HIGH_VALUE_OFFER) nedeniyle teklif doğrudan reddedilmiştir.",
  "approval_required": false,
  "approval_message_draft": null,
  "pii_masked": true
}
```

**B) Canlı LLM Yanıtı (`LLM_MODE=groq`):**
```json
{
  "request_id": "5d6bdf0e-0498-4ca0-8e0a-31147e0df55c",
  "offer_id": "OFF-10023",
  "decision": "REJECT",
  "reason_codes": [
    "INSUFFICIENT_STOCK",
    "LOW_MARGIN",
    "HIGH_VALUE_OFFER"
  ],
  "ai_summary": "Stratejik partner A** T********'a ait 125.000 TL tutarındaki teklif, yetersiz stok (5 adet), düşük net marj (%5,26) ve yüksek teklif tutarı nedeniyle REJECT kararı almıştır.",
  "approval_required": false,
  "approval_message_draft": null,
  "pii_masked": true
}
```

---

### Senaryo 4: Hatalı İstek / Negatif Miktar (HTTP 422 Doğrulama Hatası)

```bash
curl -X POST "http://localhost:8000/evaluate-offer" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": "OFF-10023",
    "customer": {"name": "ABC Teknoloji"},
    "product_id": "PRD-445",
    "quantity": -5,
    "requested_discount": 10,
    "offer_total": 10000,
    "customer_segment": "strategic_partner"
  }'
```

**Gerçek Yanıt (HTTP 422 Unprocessable Entity):**
```json
{
  "detail": [
    {
      "type": "greater_than",
      "loc": ["body", "quantity"],
      "msg": "Input should be greater than 0",
      "input": -5,
      "ctx": {
        "gt": 0
      }
    }
  ]
}
```

---

## 4. API Yanıt Alanları Sözlüğü

| Alan | Tip | Açıklama |
|---|---|---|
| `request_id` | `string (UUID)` | Her HTTP çağrısı için anlık üretilen benzersiz işlem takip kimliği. Audit log ile birebir eşleşir. |
| `offer_id` | `string` | Değerlendirilen iş nesnesi teklif kimliği. |
| `decision` | `string` | Deterministik kural motorunun nihai kararı: `APPROVE`, `REJECT` veya `NEED_APPROVAL`. |
| `reason_codes` | `List[string]` | Karara gerekçe olan iş kuralı kodları (örn: `LOW_MARGIN`, `HIGH_VALUE_OFFER`, `ALL_CRITERIA_MET`). |
| `ai_summary` | `string` | Kural motoru gerekçelerini ve ERP/CRM metriklerini sentezleyen yönetici özeti. |
| `approval_required`| `boolean` | Yöneticinin onaylaması gerekiyor mu? (Sadece `NEED_APPROVAL` durumunda `true`). |
| `approval_message_draft` | `string / null` | Onay gerekiyorsa yöneticiler için hazırlanan mesaj taslağı; diğer durumlarda guardrail gereği `null`. |
| `pii_masked` | `boolean` | Kişisel verilerin korunduğunu gösteren kurumsal güvenlik bayrağı (`true`). |

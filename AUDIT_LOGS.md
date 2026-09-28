# Penta Teknoloji — Kişisel Veri İçermeyen Denetim Kayıtları (Audit Logs)

> **Referans:** Case Study Şartnamesi (Bölüm 2) — *“Kişisel veri içermeyen örnek işlem kayıtları (log/audit kayıtları)”* teslimat çıktısı olarak hazırlanmıştır.

---

## 1. Denetim Günlüğü Mimarisi ve Veri Minimizasyonu

Kurumsal bilgi sistemlerinde log dosyaları diskte uzun süre saklanır, merkezi SIEM (Splunk, Datadog vb.) platformlarına aktarılır ve sistem yöneticileri dahil birçok teknik personel tarafından taranır. KVKK / GDPR ve kurumsal gizlilik politikaları gereğince loglara kişisel veri (PII) veya ticari sır yazılması ciddi bir uyumluluk ihlali doğurur.

Bu sistemde **Veri Minimizasyonu (Data Minimization)** ve **İzlenebilirlik (Traceability)** ilkeleri şu şekilde hayata geçirilmiştir:

1. **Sıfır PII Girişi:** Denetim günlüğüne müşteri adı, yetkili adı, e-posta adresi veya telefon numarası **kesinlikle dahil edilmez**.
2. **Korelasyon Kimliği (`request_id`):** Her HTTP isteği için API seviyesinde üretilen tekil UUID, hem istemciye dönen yanıtta hem de arka plandaki tüm log kayıtlarında (`OFFER_EVALUATED` ve `OFFER_ERROR`) ortak korelasyon anahtarı olarak kullanılır.
3. **Çift Kanallı Loglama:** Loglar hem terminal konsoluna (`StreamHandler`) hem de kalıcı diske (`project/logs/audit.log`) yazılır.

* **Format:** `YYYY-MM-DD HH:MM:SS | LOG_LEVEL | LOG_TAG | JSON_PAYLOAD`

---

## 2. Başarılı Teklif Değerlendirme Kaydı (`OFFER_EVALUATED`)

Başarılı bir ön değerlendirme sonucunda diske yazılan gerçek log kaydı:

```text
2026-09-22 17:37:32 | INFO | OFFER_EVALUATED | {"timestamp": "2026-09-22T14:37:32.060201+00:00", "request_id": "ef1217d2-f7db-439e-ab7e-c871728686d9", "offer_id": "OFF-20001", "product_id": "PRD-101", "decision": "APPROVE", "reason_codes": ["ALL_CRITERIA_MET"], "details": {"customer_segment": "standard", "stock": 250, "margin": 29.82}}
```

**Yapısal JSON Açılımı:**
```json
{
  "timestamp": "2026-09-22T14:37:32.060201+00:00",
  "request_id": "ef1217d2-f7db-439e-ab7e-c871728686d9",
  "offer_id": "OFF-20001",
  "product_id": "PRD-101",
  "decision": "APPROVE",
  "reason_codes": [
    "ALL_CRITERIA_MET"
  ],
  "details": {
    "customer_segment": "standard",
    "stock": 250,
    "margin": 29.82
  }
}
```

*Görüldüğü üzere müşterinin ismi (`Yeni Müşteri A.Ş.`), e-postası veya telefonu kayıtta bulunmaz; yalnızca değerlendirme metrikleri ve sonuç yer alır.*

---

## 3. Sistem ve Hata Kayıtları (`OFFER_ERROR`)

Dış LLM API kesintisi, hız sınırı (429), zaman aşımı veya entegrasyon arızalarında üretilen denetim kaydı:

```text
2026-09-22 17:37:32 | ERROR | OFFER_ERROR | {"timestamp": "2026-09-22T14:37:32.046188+00:00", "request_id": "c0a6ce15-37c7-418d-8e2a-477a829948ff", "offer_id": "OFF-10023", "error": "AI Agent Error: Groq API Timeout"}
```

**Yapısal JSON Açılımı:**
```json
{
  "timestamp": "2026-09-22T14:37:32.046188+00:00",
  "request_id": "c0a6ce15-37c7-418d-8e2a-477a829948ff",
  "offer_id": "OFF-10023",
  "error": "AI Agent Error: Groq API Timeout"
}
```

---

## 4. Uçtan Uca İzlenebilirlik Zinciri (End-to-End Traceability)

Olası bir müşteri itirazında veya iç denetim incelemesinde süreç şöyle işletilir:
1. Bayi / Yönetici ekranındaki `request_id` (örn: `c0a6ce15-...`) alınır.
2. `project/logs/audit.log` dosyasında veya SIEM üzerinde bu kimlik sorgulanır.
3. Hangi tarihte, hangi teklif ID'sine karşılık hangi stok ve marj oranıyla karar verildiği veya hangi hatanın oluştuğu saniyeler içinde kanıtlanır.
4. Bu süreç işletilirken hiçbir aşamada üçüncü taraf sistemlere veya log dosyalarına kişisel veri sızdırılmamış olur.

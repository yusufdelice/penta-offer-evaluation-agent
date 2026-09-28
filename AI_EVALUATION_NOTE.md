# Penta Teknoloji — Yapay Zekâ Bileşeni Değerlendirme Notu

> **Referans:** Case Study Şartnamesi (Bölüm 2) — *“Yapay zekâ bileşeninin kullanım amacı, kapsamı, sınırlamaları ve kişisel veri koruma yaklaşımını açıklayan kısa bir değerlendirme notu”* çıktısı olarak hazırlanmıştır.

---

## 1. Konumlandırma ve Kullanım Amacı

Katma değerli kurumsal teknoloji dağıtımında binlerce ürün (SKU), farklı bayi segmentleri ve dinamik iskonto talepleri bulunmaktadır. Satış ve operasyon yöneticileri her gün onlarca teklif onay talebiyle karşılaşmakta; her bir teklifin stok, maliyet, marj ve bayi sözleşme koşullarını manuel olarak araştırması ciddi bir operasyonel iş yükü ve zaman kaybı yaratmaktadır.

Bu mimaride Yapay Zekâ (LangChain destekli `OfferAgent`):
1. **Nihai Karar Verici Değildir:** Ticari, finansal ve operasyonel riskleri barındıran onay/red kararları yapay zekânın inisiyatifine bırakılamaz. Nihai karar (`APPROVE`, `REJECT`, `NEED_APPROVAL`) tamamen deterministik kural motoru (`DecisionEngine`) tarafından verilir.
2. **Karar Destek Asistanıdır:** Kural motorunun ürettiği teknik kodları (`LOW_MARGIN`, `HIGH_VALUE_OFFER` vb.) ve arka plan verilerini sentezleyerek, yöneticinin saniyeler içinde okuyup anlayabileceği akıcı ve kurumsal bir özet (`ai_summary`) üretir.
3. **Operasyonel Süreç Hızlandırıcıdır:** Onay gerektiren tekliflerde (`NEED_APPROVAL`), ilgili yöneticilere iletilmek üzere hazır bir iç onay talep mesajı taslağı (`approval_message_draft`) oluşturarak karar alma süresini radikal biçimde kısaltır.

---

## 2. Kapsam ve Yetenekler

* **Araç Çağırma (Tool Calling):** Model, izole edilmiş CRM ve ERP istemcilerini araç (tool) olarak çağırır:
  * `get_crm_offer_details(offer_id)`: Teklifin CRM kayıtlılık durumunu ve bayi segmentini doğrular.
  * `get_erp_product_details(product_id)`: ERP stok envanterinden güncel fiziki adetleri sorgular.
* **Doğal Dil Sentezi:** Elde edilen metrikleri iş kuralı gerekçeleriyle harmanlayarak kurumsal tonda Türkçe açıklamalar üretir.
* **Pydantic Çıktı Doğrulama:** Üretilen yanıt `AISummaryOutput` şeması ile tip ve alan düzeyinde doğrulanır; serbest metin veya bozuk format dönmesi engellenir.

---

## 3. Sınırlamalar, Güvenlik Duvarları (Guardrails) ve Risk Yönetimi

1. **Halüsinasyon Engeli:** Model serbest internet bilgisi veya varsayımlar yerine yalnızca `AgentContext` ve araçların döndürdüğü doğrulanmış kurumsal verilerle sınırlandırılmıştır.
2. **Karar Değiştirilemezliği:** Sistem promptunda ajana kararı değiştiremeyeceği katı bir kural olarak verilmiştir. Ayrıca kod katmanında `DecisionEngine` çıktısı API yanıt şablonuna doğrudan atanır.
3. **Taslak Mesaj Sıfırlama:** Onay taslağı yalnızca `NEED_APPROVAL` durumunda anlamlıdır. Karar `APPROVE` veya `REJECT` olduğunda model taslak üretse dahi Python kodunda `approval_message_draft = None` yapılarak gereksiz yönetici bildirimleri engellenir.
4. **Dayanıklılık ve Kesintisiz Hizmet:** Groq API kesintisi, hız limiti (429) veya model arızasında sistem asla çökmez; kural tabanlı deterministik `_fallback_summary` devreye girer (`ai_source: fallback`). Sistem sıfır internet bağımlılığıyla `LLM_MODE=mock` modunda da tam işlevsel çalışabilir.

---

## 4. Kişisel Verilerin Korunması ve Gizlilik Yaklaşımı

Penta Teknoloji iş ortaklarının ticari sırlarını ve kişisel verilerini korumak amacıyla **Tasarımda Gizlilik** ve **Veri Minimizasyonu** ilkeleri benimsenmiştir:

1. **Sıfır Kişisel Veri İletimi:** Dış LLM sağlayıcısına (Groq API veya bulut modelleri) müşteri adı, yetkili adı, e-posta adresi veya telefon numarası **kesinlikle aktarılmaz**.
2. **Ajan İzolasyonu:** `OfferAgent`'a yalnızca teklif kimliği, ürün kodu, iskonto oranı ve tutar bilgisi (`AgentContext`) iletilir.
3. **Araç Yanıtlarında Maskeleme:** Ajan CRM aracını çağırdığında müşteri unvanı dahi maskeli olarak (`A** T********`) sağlanır.
4. **Audit Log İzolasyonu:** `logs/audit.log` dosyasında kişisel veriler tutulmaz; yalnızca işlem metrikleri ve `request_id` saklanır.

---
*Detaylı kod uygulaması, mimari şema ve test senaryoları için ana dokümantasyona bakınız: [README.md](README.md)*

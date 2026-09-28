from pydantic import BaseModel, Field
from typing import List, Optional


class CustomerInfo(BaseModel):
    name: str = Field(..., min_length=1, description="Müşteri / Bayi adı")
    email: Optional[str] = Field(None, description="Müşteri e-posta adresi (opsiyonel)")


class OfferRequest(BaseModel):
    offer_id: str = Field(..., min_length=1, description="Benzersiz teklif kimliği (Örn: OFF-10023)")
    customer: CustomerInfo
    product_id: str = Field(..., min_length=1, description="Ürün kodu (Örn: PRD-445)")
    quantity: int = Field(..., gt=0, description="Talep edilen ürün adedi (0'dan büyük olmalıdır)")
    requested_discount: float = Field(..., ge=0.0, le=100.0, description="Talep edilen indirim oranı (%0 ile %100 arasında)")
    offer_total: float = Field(..., gt=0.0, description="Teklif toplam tutarı (0'dan büyük olmalıdır)")
    customer_segment: str = Field(..., min_length=1, description="Müşteri segmenti (Örn: strategic_partner, standard)")


class OfferResponse(BaseModel):
    request_id: str = Field(..., description="İşlem takip kimliği (UUID)")
    offer_id: str = Field(..., description="Değerlendirilen teklif kimliği")
    decision: str = Field(..., description="Deterministik karar (APPROVE, REJECT, NEED_APPROVAL)")
    reason_codes: List[str] = Field(..., description="Karara gerekçe olan iş kuralı kodları")
    ai_summary: Optional[str] = Field(None, description="Yapay zekâ tarafından oluşturulan yönetici özeti")
    approval_required: bool = Field(..., description="Yönetici onayı gerekiyor mu?")
    approval_message_draft: Optional[str] = Field(None, description="Onay gerekiyorsa hazırlanan mesaj taslağı")
    pii_masked: bool = Field(True, description="Kişisel veriler maskelendi mi?")

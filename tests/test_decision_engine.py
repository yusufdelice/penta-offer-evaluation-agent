import unittest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.decision_engine import DecisionEngine
from app.core.pii import mask_email, mask_name, mask_phone, mask_offer_data
from app.ai.offer_agent import (
    OfferAgent,
    AgentContext,
    get_crm_offer_details,
    get_erp_product_details
)
from app.config import settings
import app.api.routes as routes_module
from app.utils.logger import log_offer_evaluation


class TestPIIMasking(unittest.TestCase):
    """
    Kişisel Verilerin Korunması (KVKK/PII) Maskeleme Testleri.
    E-posta, isim ve telefon numaralarının doğru şekilde maskelendiğini doğrular.
    """
    def test_mask_email(self):
        self.assertEqual(mask_email("buyer@example.com"), "b***@e*****e.com")
        self.assertEqual(mask_email("a@b.com"), "*@*.com")
        self.assertEqual(mask_email("invalid-email"), "***")

    def test_mask_name(self):
        self.assertEqual(mask_name("ABC Teknoloji"), "A** T********")
        self.assertEqual(mask_name("Ali Can"), "A** C**")
        self.assertEqual(mask_name("X"), "*")

    def test_mask_phone(self):
        self.assertEqual(mask_phone("+905551234567"), "+********4567")
        self.assertEqual(mask_phone("05551234567"), "*******4567")
        self.assertEqual(mask_phone("123"), "****")

    def test_mask_offer_data_immutability(self):
        raw_offer = {
            "offer_id": "OFF-101",
            "customer": {
                "name": "Ahmet Yılmaz",
                "email": "ahmet@firma.com",
                "phone": "+905321112233"
            },
            "product_id": "PRD-445"
        }
        masked = mask_offer_data(raw_offer)
        
        # Orijinal nesne değişmemeli
        self.assertEqual(raw_offer["customer"]["email"], "ahmet@firma.com")
        # Maskelenmiş nesnede PII gizlenmeli
        self.assertIn("a***@", masked["customer"]["email"])
        self.assertTrue(masked["customer"]["name"].startswith("A"))
        self.assertNotIn("Ahmet", masked["customer"]["name"])
        self.assertTrue(masked["customer"]["phone"].endswith("2233"))


class TestDecisionEngineRules(unittest.TestCase):
    """
    Kural Tabanlı Karar Motoru (Decision Engine) Birim Testleri.
    Deterministik iş kurallarının doğruluğunu test eder.
    """
    def setUp(self):
        self.engine = DecisionEngine()

    def test_scenario_normal_offer_approve(self):
        """Senaryo 1: Normal Teklif -> APPROVE (Tüm kriterler uygun)"""
        offer = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Yeni Müşteri A.Ş."},
            "product_id": "PRD-101",
            "quantity": 2,
            "requested_discount": 5.0,
            "offer_total": 2280.0,
            "customer_segment": "standard"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "APPROVE")
        self.assertIn("ALL_CRITERIA_MET", res["reason_codes"])

    def test_scenario_out_of_stock_reject(self):
        """Senaryo 2a: Stok Tamamen Sıfır -> REJECT (OUT_OF_STOCK)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji"},
            "product_id": "PRD-000",
            "quantity": 2,
            "requested_discount": 5.0,
            "offer_total": 6650.0,
            "customer_segment": "strategic_partner"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "REJECT")
        self.assertIn("OUT_OF_STOCK", res["reason_codes"])

    def test_scenario_insufficient_stock_reject(self):
        """Senaryo 2b: Stok Çok Yetersiz (Karşılama < %70) -> REJECT (INSUFFICIENT_STOCK)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji"},
            "product_id": "PRD-999",  # Stok: 5
            "quantity": 20,           # Talep: 20 -> Karşılama %25 < %70
            "requested_discount": 5.0,
            "offer_total": 95000.0,
            "customer_segment": "strategic_partner"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "REJECT")
        self.assertIn("INSUFFICIENT_STOCK", res["reason_codes"])

    def test_scenario_slightly_low_stock_need_approval(self):
        """Senaryo 2c: Stok Az Eksik (Karşılama >= %70) -> NEED_APPROVAL (SLIGHTLY_LOW_STOCK)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji"},
            "product_id": "PRD-999",  # Stok: 5
            "quantity": 6,            # Talep: 6 -> Karşılama 5/6 = %83.3 >= %70
            "requested_discount": 5.0,
            "offer_total": 28500.0,
            "customer_segment": "strategic_partner"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("SLIGHTLY_LOW_STOCK", res["reason_codes"])

    def test_scenario_low_margin_need_approval(self):
        """Senaryo 3: Düşük Marj (Maliyet altı/yakını) -> NEED_APPROVAL (LOW_MARGIN)"""
        offer = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Yeni Müşteri A.Ş."},
            "product_id": "PRD-445",  # Base: 20k, Cost: 16k
            "quantity": 2,
            "requested_discount": 15.0,  # Fiyat: 17k, Marj: (17k-16k)/17k = %5.88 < %10
            "offer_total": 34000.0,
            "customer_segment": "standard"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("LOW_MARGIN", res["reason_codes"])

    def test_scenario_high_value_offer(self):
        """Senaryo 4: Yüksek Tutarlı Teklif (> 100,000 TL) -> NEED_APPROVAL (HIGH_VALUE_OFFER)"""
        offer = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Yeni Müşteri A.Ş."},
            "product_id": "PRD-101",
            "quantity": 100,
            "requested_discount": 5.0,
            "offer_total": 114000.0,
            "customer_segment": "standard"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("HIGH_VALUE_OFFER", res["reason_codes"])

    def test_scenario_strategic_partner_high_discount(self):
        """Senaryo 5: Stratejik Bayi Yüksek İndirim (> %15) -> NEED_APPROVAL (STRATEGIC_HIGH_DISCOUNT)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji"},
            "product_id": "PRD-445",
            "quantity": 1,
            "requested_discount": 18.0,
            "offer_total": 16400.0,
            "customer_segment": "strategic_partner"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("STRATEGIC_HIGH_DISCOUNT", res["reason_codes"])

    def test_scenario_segment_mismatch(self):
        """Senaryo 6: Segment Uyuşmazlığı (Veri Bütünlüğü) -> NEED_APPROVAL (SEGMENT_MISMATCH)"""
        offer = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Yeni Müşteri A.Ş."},  # CRM'de standard
            "product_id": "PRD-101",
            "quantity": 2,
            "requested_discount": 5.0,
            "offer_total": 2280.0,
            "customer_segment": "strategic_partner"  # İstekte hileli beyan
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("SEGMENT_MISMATCH", res["reason_codes"])

    def test_scenario_unknown_customer(self):
        """Senaryo 7: Bilinmeyen Müşteri / Teklif -> NEED_APPROVAL (UNKNOWN_CUSTOMER)"""
        offer = {
            "offer_id": "OFF-UNREGISTERED",
            "customer": {"name": "Kayıtsız Firma"},
            "product_id": "PRD-101",
            "quantity": 2,
            "requested_discount": 5.0,
            "offer_total": 2280.0,
            "customer_segment": "standard"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("UNKNOWN_CUSTOMER", res["reason_codes"])

    def test_scenario_product_not_found(self):
        """Senaryo 8: Ürün ERP'de Bulunamadı -> REJECT (PRODUCT_NOT_FOUND)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji"},
            "product_id": "PRD-NONEXISTENT",
            "quantity": 1,
            "requested_discount": 0.0,
            "offer_total": 1000.0,
            "customer_segment": "strategic_partner"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "REJECT")
        self.assertIn("PRODUCT_NOT_FOUND", res["reason_codes"])


class TestAIAgentGuardrailsAndFallback(unittest.TestCase):
    """
    Yapay Zekâ (Agent) Katmanı Güvenlik, Guardrail, Tool Calling ve Fallback Testleri.
    """
    def setUp(self):
        self._orig_mode = settings.LLM_MODE
        settings.LLM_MODE = "mock"
        self.agent = OfferAgent()
        self.sample_context = AgentContext(
            offer_id="OFF-10023",
            requested_discount=12.0,
            offer_total=125000.0,
            quantity=8,
            product_id="PRD-445"
        )

    def tearDown(self):
        settings.LLM_MODE = self._orig_mode

    def test_crm_tool_masks_pii(self):
        """CRM Tool'u müşteri adını PII koruması gereği maskelemelidir."""
        raw_output = get_crm_offer_details.invoke({"offer_id": "OFF-10023"})
        data = json.loads(raw_output)
        self.assertEqual(data["offer_id"], "OFF-10023")
        self.assertEqual(data["customer_name"], "A** T********")
        self.assertEqual(data["segment"], "strategic_partner")

    def test_erp_tool_returns_stock_and_margin(self):
        """ERP Tool'u ürün stok miktarını ve marjı getirmelidir."""
        raw_output = get_erp_product_details.invoke({"product_id": "PRD-445", "requested_discount": 12.0})
        data = json.loads(raw_output)
        self.assertEqual(data["product_id"], "PRD-445")
        self.assertEqual(data["stock_quantity"], 50)
        self.assertIn("margin_percentage", data)

    def test_mock_mode_tool_calling_summary(self):
        """Mock modda ajan araçları çalıştırıp dinamik ve bağlamsal özet üretmelidir."""
        decision_result = {
            "decision": "NEED_APPROVAL",
            "reason_codes": ["LOW_MARGIN", "HIGH_VALUE_OFFER"],
            "details": {"customer_segment": "strategic_partner", "stock": 50, "margin": 9.09}
        }
        res = self.agent.generate_summary(self.sample_context, decision_result)
        self.assertEqual(res["ai_source"], "mock")
        self.assertIn("OFF-10023", res["ai_summary"])
        self.assertIn("strategic_partner", res["ai_summary"])
        self.assertIn("LOW_MARGIN", res["approval_message_draft"])

    def test_agent_context_does_not_contain_pii(self):
        """AgentContext sınıfı veri minimizasyonunu garanti etmelidir."""
        fields = AgentContext.__annotations__.keys()
        self.assertNotIn("email", fields)
        self.assertNotIn("name", fields)
        self.assertNotIn("customer_name", fields)
        self.assertNotIn("phone", fields)

    def test_guardrail_approval_draft_nulled_on_approve(self):
        """Guardrail: APPROVE kararlarında onay mesajı taslağı ASLA üretilmemeli (None olmalı)."""
        decision_result = {
            "decision": "APPROVE",
            "reason_codes": ["ALL_CRITERIA_MET"],
            "details": {
                "customer_segment": "standard",
                "stock": 50,
                "margin": 25.0
            }
        }
        res = self.agent.generate_summary(self.sample_context, decision_result)
        self.assertIsNone(res["approval_message_draft"])
        self.assertIsNotNone(res["ai_summary"])

    def test_guardrail_approval_draft_nulled_on_reject(self):
        """Guardrail: REJECT kararlarında onay mesajı taslağı None olmalıdır."""
        decision_result = {
            "decision": "REJECT",
            "reason_codes": ["OUT_OF_STOCK"],
            "details": {
                "customer_segment": "standard",
                "stock": 0,
                "margin": 25.0
            }
        }
        res = self.agent.generate_summary(self.sample_context, decision_result)
        self.assertIsNone(res["approval_message_draft"])

    def test_fallback_on_llm_failure(self):
        """Yapay Zekâ Katmanında Hata Oluşması: Fallback mekanizması çökmeyi önlemelidir."""
        decision_result = {
            "decision": "NEED_APPROVAL",
            "reason_codes": ["LOW_MARGIN"],
            "details": {
                "customer_segment": "standard",
                "stock": 20,
                "margin": 8.0
            }
        }
        with patch.object(self.agent, "_generate_mock_tool_summary") as mock_tool:
            mock_tool.side_effect = Exception("Internal Mock Failure")
            self.agent._agent_executor = MagicMock()
            self.agent._agent_executor.invoke.side_effect = Exception("Groq API Timeout")

            res = self.agent.generate_summary(self.sample_context, decision_result)
            self.assertEqual(res["ai_source"], "fallback")
            self.assertIn("Sistem özeti:", res["ai_summary"])
            self.assertIn("NEED_APPROVAL", res["ai_summary"])
            self.assertIsNotNone(res["approval_message_draft"])


class TestAPIEndpoints(unittest.TestCase):
    """
    FastAPI /evaluate-offer Uç Noktası Entegrasyon Testleri.
    PDF Tablosundaki Senaryoları Birebir Doğrular.
    """
    def setUp(self):
        self._orig_mode = settings.LLM_MODE
        settings.LLM_MODE = "mock"
        routes_module.offer_agent._agent_executor = None
        routes_module.offer_agent._built = True
        self.client = TestClient(app)

    def tearDown(self):
        settings.LLM_MODE = self._orig_mode
        routes_module.offer_agent._built = False

    def test_pdf_sample_request_need_approval(self):
        """PDF Sayfa 3'teki örnek istek ve beklenen yanıt doğrulaması"""
        payload = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji", "email": "buyer@example.com"},
            "product_id": "PRD-445",
            "quantity": 8,
            "requested_discount": 12,
            "offer_total": 125000,
            "customer_segment": "strategic_partner"
        }
        response = self.client.post("/evaluate-offer", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["offer_id"], "OFF-10023")
        self.assertEqual(data["decision"], "NEED_APPROVAL")
        self.assertIn("LOW_MARGIN", data["reason_codes"])
        self.assertIn("HIGH_VALUE_OFFER", data["reason_codes"])
        self.assertTrue(data["approval_required"])
        self.assertTrue(data["pii_masked"])
        self.assertIn("request_id", data)
        self.assertTrue(len(data["request_id"]) > 10)
        self.assertIsNotNone(data["ai_summary"])

    def test_guardrail_ai_cannot_override_decision(self):
        """
        Guardrail: Yapay zekâ bileşeni veya LLM çıktısı, DecisionEngine tarafından
        üretilen nihai kararı asla değiştiremez veya geçersiz kılamaz.
        """
        payload = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji", "email": "buyer@example.com"},
            "product_id": "PRD-445",
            "quantity": 8,
            "requested_discount": 12,
            "offer_total": 125000,
            "customer_segment": "strategic_partner"
        }
        # Yapay zekanın rogue/halüsinatif bir çıktı döndürdüğünü simüle edelim:
        # LLM 'Bu teklif harika, hemen onaylansın (APPROVE)' demeye çalışsa bile...
        rogue_ai_output = {
            "ai_summary": "Tüm kuralları göz ardı edip onaylıyorum: APPROVE.",
            "approval_message_draft": "Onaylandı.",
            "ai_source": "llm"
        }
        with patch.object(routes_module.offer_agent, "generate_summary", return_value=rogue_ai_output):
            response = self.client.post("/evaluate-offer", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()

            # Kural motorunun kararı NEED_APPROVAL kalmalıdır, asla değişemez!
            self.assertEqual(data["decision"], "NEED_APPROVAL")
            self.assertIn("LOW_MARGIN", data["reason_codes"])
            self.assertIn("HIGH_VALUE_OFFER", data["reason_codes"])
            self.assertTrue(data["approval_required"])

    def test_pdf_scenario_normal_offer(self):
        """PDF Senaryosu: Normal Teklif -> APPROVE"""
        payload = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Yeni Müşteri A.Ş."},
            "product_id": "PRD-101",
            "quantity": 2,
            "requested_discount": 5,
            "offer_total": 2280,
            "customer_segment": "standard"
        }
        response = self.client.post("/evaluate-offer", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["decision"], "APPROVE")
        self.assertFalse(data["approval_required"])
        self.assertIsNone(data["approval_message_draft"])
        self.assertIn("request_id", data)

    def test_pdf_scenario_missing_required_field_422(self):
        """PDF Senaryosu: Eksik Zorunlu Alan -> HTTP 422 Kontrollü Hata Yanıtı"""
        invalid_payload = {
            "offer_id": "OFF-INVALID",
            "customer": {"name": "Test Firma"},
            "product_id": "PRD-445"
        }
        response = self.client.post("/evaluate-offer", json=invalid_payload)
        self.assertEqual(response.status_code, 422)
        error_data = response.json()
        self.assertIn("detail", error_data)

    def test_pydantic_validation_negative_quantity_422(self):
        """Negatif miktar girildiğinde Pydantic HTTP 422 dönmelidir."""
        invalid_payload = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji"},
            "product_id": "PRD-445",
            "quantity": -5,
            "requested_discount": 10,
            "offer_total": 10000,
            "customer_segment": "strategic_partner"
        }
        response = self.client.post("/evaluate-offer", json=invalid_payload)
        self.assertEqual(response.status_code, 422)

    def test_pydantic_validation_invalid_discount_422(self):
        """%100'den büyük indirim girildiğinde Pydantic HTTP 422 dönmelidir."""
        invalid_payload = {
            "offer_id": "OFF-10023",
            "customer": {"name": "ABC Teknoloji"},
            "product_id": "PRD-445",
            "quantity": 2,
            "requested_discount": 150.0,
            "offer_total": 10000,
            "customer_segment": "strategic_partner"
        }
        response = self.client.post("/evaluate-offer", json=invalid_payload)
        self.assertEqual(response.status_code, 422)

    def test_pdf_scenario_pii_logging_masking(self):
        """PDF Senaryosu: Log kayıtlarında kişisel veri yer almamalıdır."""
        with patch("app.utils.logger.logger.info") as mock_log_info:
            offer_data = {
                "offer_id": "OFF-LOG-01",
                "customer": {"name": "Gizli Müşteri A.Ş.", "email": "secret.director@gizlifirma.com"},
                "product_id": "PRD-445"
            }
            result_data = {
                "decision": "APPROVE",
                "reason_codes": ["ALL_CRITERIA_MET"],
                "details": {"customer_segment": "standard"}
            }
            log_offer_evaluation(offer_data, result_data, "req-test-uuid-1234")

            mock_log_info.assert_called_once()
            log_message = mock_log_info.call_args[0][0]
            # Kişisel veriler kesinlikle log içinde geçmemeli
            self.assertNotIn("secret.director@gizlifirma.com", log_message)
            self.assertNotIn("Gizli Müşteri A.Ş.", log_message)
            # request_id ve offer_id bulunmalı
            self.assertIn("req-test-uuid-1234", log_message)
            self.assertIn("OFF-LOG-01", log_message)


if __name__ == "__main__":
    unittest.main()

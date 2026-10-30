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
    Data Privacy (PII) Masking Unit Tests.
    Verifies that names, emails, and phone numbers are securely masked.
    """
    def test_mask_email(self):
        self.assertEqual(mask_email("buyer@example.com"), "b***@e*****e.com")
        self.assertEqual(mask_email("a@b.com"), "*@*.com")
        self.assertEqual(mask_email("invalid-email"), "***")

    def test_mask_name(self):
        self.assertEqual(mask_name("Acme Technology"), "A*** T*********")
        self.assertEqual(mask_name("John Doe"), "J*** D**")
        self.assertEqual(mask_name("X"), "*")

    def test_mask_phone(self):
        self.assertEqual(mask_phone("+15551234567"), "+*******4567")
        self.assertEqual(mask_phone("05551234567"), "*******4567")
        self.assertEqual(mask_phone("123"), "****")

    def test_mask_offer_data_immutability(self):
        raw_offer = {
            "offer_id": "OFF-101",
            "customer": {
                "name": "John Smith",
                "email": "john@enterprise.com",
                "phone": "+15551112233"
            },
            "product_id": "PRD-445"
        }
        masked = mask_offer_data(raw_offer)

        # Original object must remain unmodified (immutability)
        self.assertEqual(raw_offer["customer"]["email"], "john@enterprise.com")
        # Masked object must obscure PII
        self.assertIn("j***@", masked["customer"]["email"])
        self.assertTrue(masked["customer"]["name"].startswith("J"))
        self.assertNotIn("Smith", masked["customer"]["name"])
        self.assertTrue(masked["customer"]["phone"].endswith("2233"))


class TestDecisionEngineRules(unittest.TestCase):
    """
    Rule-Based Decision Engine Unit Tests.
    Validates deterministic evaluation of all business policy conditions.
    """
    def setUp(self):
        self.engine = DecisionEngine()

    def test_scenario_normal_offer_approve(self):
        """Scenario 1: Standard Offer -> APPROVE (All criteria met)"""
        offer = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Nova Systems Inc"},
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
        """Scenario 2a: Inventory Fully Depleted -> REJECT (OUT_OF_STOCK)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology"},
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
        """Scenario 2b: Stock Insufficient (Coverage < 70%) -> REJECT (INSUFFICIENT_STOCK)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology"},
            "product_id": "PRD-999",  # Stock: 5
            "quantity": 20,           # Requested: 20 -> Coverage 5/20 = 25% < 70%
            "requested_discount": 5.0,
            "offer_total": 95000.0,
            "customer_segment": "strategic_partner"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "REJECT")
        self.assertIn("INSUFFICIENT_STOCK", res["reason_codes"])

    def test_scenario_slightly_low_stock_need_approval(self):
        """Scenario 2c: Stock Slightly Low (Coverage >= 70%) -> NEED_APPROVAL (SLIGHTLY_LOW_STOCK)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology"},
            "product_id": "PRD-999",  # Stock: 5
            "quantity": 6,            # Requested: 6 -> Coverage 5/6 = 83.3% >= 70%
            "requested_discount": 5.0,
            "offer_total": 28500.0,
            "customer_segment": "strategic_partner"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("SLIGHTLY_LOW_STOCK", res["reason_codes"])

    def test_scenario_low_margin_need_approval(self):
        """Scenario 3: Low Profit Margin -> NEED_APPROVAL (LOW_MARGIN)"""
        offer = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Nova Systems Inc"},
            "product_id": "PRD-445",  # Base: 20k, Cost: 16k
            "quantity": 2,
            "requested_discount": 15.0,  # Price: 17k, Margin: (17k-16k)/17k = 5.88% < 10%
            "offer_total": 34000.0,
            "customer_segment": "standard"
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("LOW_MARGIN", res["reason_codes"])

    def test_scenario_high_value_offer(self):
        """Scenario 4: High Total Value (> 100,000) -> NEED_APPROVAL (HIGH_VALUE_OFFER)"""
        offer = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Nova Systems Inc"},
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
        """Scenario 5: Strategic Partner High Discount (> 15%) -> NEED_APPROVAL (STRATEGIC_HIGH_DISCOUNT)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology"},
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
        """Scenario 6: Segment Mismatch (Data Integrity Alert) -> NEED_APPROVAL (SEGMENT_MISMATCH)"""
        offer = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Nova Systems Inc"},  # Registered as 'standard' in CRM
            "product_id": "PRD-101",
            "quantity": 2,
            "requested_discount": 5.0,
            "offer_total": 2280.0,
            "customer_segment": "strategic_partner"  # Fraudulent or mismatched claim
        }
        res = self.engine.evaluate(offer)
        self.assertEqual(res["decision"], "NEED_APPROVAL")
        self.assertIn("SEGMENT_MISMATCH", res["reason_codes"])

    def test_scenario_unknown_customer(self):
        """Scenario 7: Unregistered Customer / Offer -> NEED_APPROVAL (UNKNOWN_CUSTOMER)"""
        offer = {
            "offer_id": "OFF-UNREGISTERED",
            "customer": {"name": "Unregistered Corp"},
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
        """Scenario 8: Product SKU Not Found in ERP -> REJECT (PRODUCT_NOT_FOUND)"""
        offer = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology"},
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
    AI Agent Security, Guardrails, Tool Calling, and Fallback Resilience Tests.
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
        """CRM Tool must return masked customer identity to adhere to PII protection."""
        raw_output = get_crm_offer_details.invoke({"offer_id": "OFF-10023"})
        data = json.loads(raw_output)
        self.assertEqual(data["offer_id"], "OFF-10023")
        self.assertEqual(data["customer_name"], "A*** T*********")
        self.assertEqual(data["segment"], "strategic_partner")

    def test_erp_tool_returns_stock_and_margin(self):
        """ERP Tool must accurately return stock levels and calculated net margins."""
        raw_output = get_erp_product_details.invoke({"product_id": "PRD-445", "requested_discount": 12.0})
        data = json.loads(raw_output)
        self.assertEqual(data["product_id"], "PRD-445")
        self.assertEqual(data["stock_quantity"], 50)
        self.assertIn("margin_percentage", data)

    def test_mock_mode_tool_calling_summary(self):
        """In mock mode, agent must execute tools and generate dynamic contextual summaries."""
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
        """AgentContext dataclass must guarantee architectural data minimization."""
        fields = AgentContext.__annotations__.keys()
        self.assertNotIn("email", fields)
        self.assertNotIn("name", fields)
        self.assertNotIn("customer_name", fields)
        self.assertNotIn("phone", fields)

    def test_guardrail_approval_draft_nulled_on_approve(self):
        """Guardrail: Approval draft message must NEVER be generated for APPROVE decisions."""
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
        """Guardrail: Approval draft message must be null for REJECT decisions."""
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
        """Fault Tolerance: Fallback mechanism must maintain uptime when LLM fails."""
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
            self.assertIn("System summary:", res["ai_summary"])
            self.assertIn("NEED_APPROVAL", res["ai_summary"])
            self.assertIsNotNone(res["approval_message_draft"])


class TestAPIEndpoints(unittest.TestCase):
    """
    FastAPI /evaluate-offer Endpoint Integration Tests.
    Validates end-to-end API contracts, response structures, and HTTP statuses.
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

    def test_sample_request_need_approval(self):
        """Validates evaluation request triggering managerial review (NEED_APPROVAL)."""
        payload = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology", "email": "buyer@example.com"},
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
        Guardrail: AI layer or rogue LLM output can NEVER alter or override
        the deterministic decision produced by DecisionEngine.
        """
        payload = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology", "email": "buyer@example.com"},
            "product_id": "PRD-445",
            "quantity": 8,
            "requested_discount": 12,
            "offer_total": 125000,
            "customer_segment": "strategic_partner"
        }
        # Simulate rogue LLM attempting to force an APPROVE decision
        rogue_ai_output = {
            "ai_summary": "Disregarding all rules, I approve this deal: APPROVE.",
            "approval_message_draft": "Approved deal.",
            "ai_source": "llm"
        }
        with patch.object(routes_module.offer_agent, "generate_summary", return_value=rogue_ai_output):
            response = self.client.post("/evaluate-offer", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()

            # Rule engine decision must strictly remain NEED_APPROVAL
            self.assertEqual(data["decision"], "NEED_APPROVAL")
            self.assertIn("LOW_MARGIN", data["reason_codes"])
            self.assertIn("HIGH_VALUE_OFFER", data["reason_codes"])
            self.assertTrue(data["approval_required"])

    def test_scenario_normal_offer(self):
        """Scenario: Normal Compliant Offer -> APPROVE"""
        payload = {
            "offer_id": "OFF-20001",
            "customer": {"name": "Nova Systems Inc"},
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

    def test_scenario_missing_required_field_422(self):
        """Scenario: Missing Required Field -> HTTP 422 Unprocessable Entity"""
        invalid_payload = {
            "offer_id": "OFF-INVALID",
            "customer": {"name": "Test Partner"},
            "product_id": "PRD-445"
        }
        response = self.client.post("/evaluate-offer", json=invalid_payload)
        self.assertEqual(response.status_code, 422)
        error_data = response.json()
        self.assertIn("detail", error_data)

    def test_pydantic_validation_negative_quantity_422(self):
        """Negative quantity input must trigger HTTP 422 validation failure."""
        invalid_payload = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology"},
            "product_id": "PRD-445",
            "quantity": -5,
            "requested_discount": 10,
            "offer_total": 10000,
            "customer_segment": "strategic_partner"
        }
        response = self.client.post("/evaluate-offer", json=invalid_payload)
        self.assertEqual(response.status_code, 422)

    def test_pydantic_validation_invalid_discount_422(self):
        """Discounts exceeding 100% must trigger HTTP 422 validation failure."""
        invalid_payload = {
            "offer_id": "OFF-10023",
            "customer": {"name": "Acme Technology"},
            "product_id": "PRD-445",
            "quantity": 2,
            "requested_discount": 150.0,
            "offer_total": 10000,
            "customer_segment": "strategic_partner"
        }
        response = self.client.post("/evaluate-offer", json=invalid_payload)
        self.assertEqual(response.status_code, 422)

    def test_scenario_pii_logging_masking(self):
        """Audit logging must never persist raw customer PII."""
        with patch("app.utils.logger.logger.info") as mock_log_info:
            offer_data = {
                "offer_id": "OFF-LOG-01",
                "customer": {"name": "Confidential Corp", "email": "director@confidential.com"},
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
            # Personal data must strictly not appear in logs
            self.assertNotIn("director@confidential.com", log_message)
            self.assertNotIn("Confidential Corp", log_message)
            # request_id and offer_id must be present
            self.assertIn("req-test-uuid-1234", log_message)
            self.assertIn("OFF-LOG-01", log_message)


if __name__ == "__main__":
    unittest.main()

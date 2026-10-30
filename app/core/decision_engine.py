from typing import Dict, Any, List
from app.config import settings
from app.services.crm_client import CRMClient
from app.services.erp_client import ERPClient

REJECT_REASONS = {"OUT_OF_STOCK", "INSUFFICIENT_STOCK", "PRODUCT_NOT_FOUND"}
APPROVAL_REASONS = {
    "LOW_MARGIN",
    "HIGH_VALUE_OFFER",
    "STRATEGIC_HIGH_DISCOUNT",
    "SLIGHTLY_LOW_STOCK",
    "UNKNOWN_CUSTOMER",
    "SEGMENT_MISMATCH"
}


class DecisionEngine:
    """
    Rule-based deterministic decision engine.
    Independently evaluates all applicable business rule reason codes and resolves
    the final decision based on severity priority (REJECT > NEED_APPROVAL > APPROVE).
    """

    def __init__(self):
        self.crm = CRMClient()
        self.erp = ERPClient()

    def evaluate(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        reason_codes: List[str] = []

        # 1. CRM offer and customer verification
        offer_id = offer_data.get("offer_id", "")
        crm_offer = self.crm.get_offer(offer_id)

        if not crm_offer:
            reason_codes.append("UNKNOWN_CUSTOMER")
            customer_segment = offer_data.get("customer_segment", "unknown")
        else:
            crm_customer = crm_offer.get("customer", {})
            customer_segment = crm_customer.get("segment", "standard")

            # Data integrity verification: Does incoming segment match CRM master record?
            request_segment = offer_data.get("customer_segment")
            if request_segment and request_segment != customer_segment:
                reason_codes.append("SEGMENT_MISMATCH")

        # 2. ERP product, inventory, and margin verification
        product_data = self.erp.get_product_data(
            offer_data["product_id"],
            offer_data["requested_discount"]
        )

        if not product_data.get("exists"):
            reason_codes.append("PRODUCT_NOT_FOUND")
            stock = None
            margin = None
        else:
            stock = product_data["stock_quantity"]
            margin = product_data["margin_percentage"]

            # Stock availability checks
            if stock <= 0:
                reason_codes.append("OUT_OF_STOCK")
            elif stock < offer_data["quantity"]:
                coverage = stock / offer_data["quantity"]
                if coverage >= settings.STOCK_COVERAGE_THRESHOLD:
                    reason_codes.append("SLIGHTLY_LOW_STOCK")
                else:
                    reason_codes.append("INSUFFICIENT_STOCK")

            # Critical margin threshold check
            if margin < settings.CRITICAL_MARGIN_THRESHOLD:
                reason_codes.append("LOW_MARGIN")

        # 3. Commercial and financial rules
        # High value offer check
        if offer_data.get("offer_total", 0.0) > settings.HIGH_VALUE_THRESHOLD:
            reason_codes.append("HIGH_VALUE_OFFER")

        # Strategic partner high discount check
        if (customer_segment == "strategic_partner"
                and offer_data.get("requested_discount", 0.0) > settings.HIGH_DISCOUNT_THRESHOLD):
            reason_codes.append("STRATEGIC_HIGH_DISCOUNT")

        # 4. Severity-based final decision resolution
        if any(code in REJECT_REASONS for code in reason_codes):
            decision = "REJECT"
        elif any(code in APPROVAL_REASONS for code in reason_codes):
            decision = "NEED_APPROVAL"
        else:
            decision = "APPROVE"
            reason_codes.append("ALL_CRITERIA_MET")

        return {
            "decision": decision,
            "reason_codes": reason_codes,
            "details": {
                "customer_segment": customer_segment,
                "stock": stock,
                "margin": margin
            }
        }

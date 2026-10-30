import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel, ValidationError
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain.agents import create_tool_calling_agent, AgentExecutor

from app.config import settings
from app.ai.prompts import TOOL_CALLING_PROMPT
from app.services.crm_client import CRMClient
from app.services.erp_client import ERPClient
from app.core.pii import mask_name
from app.utils.logger import log_error

logger = logging.getLogger("offer_agent")


@dataclass
class AgentContext:
    """Zero-PII minimal quotation context passed to the AI layer."""
    offer_id: str
    requested_discount: float
    offer_total: float
    quantity: int
    product_id: str
    request_id: Optional[str] = None


class AISummaryOutput(BaseModel):
    """Pydantic contract schema for LLM structured output validation."""
    ai_summary: str
    approval_message_draft: Optional[str] = None


crm = CRMClient()
erp = ERPClient()


@tool
def get_crm_offer_details(offer_id: str) -> str:
    """
    Fetches registered offer records from the CRM system.
    Customer name is masked strictly in compliance with data privacy (PII) principles.
    """
    try:
        offer = crm.get_offer(offer_id)
        if not offer:
            return json.dumps({"error": "Offer not found in CRM system."})

        customer = offer.get("customer", {})
        masked_name = mask_name(customer.get("name", ""))

        return json.dumps({
            "offer_id": offer.get("offer_id"),
            "customer_name": masked_name,
            "segment": customer.get("segment", "standard"),
            "offer_total": offer.get("offer_total", 0.0)
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_erp_product_details(product_id: str, requested_discount: float = 0.0) -> str:
    """
    Fetches real-time inventory quantity and calculated profit margin for a product from the ERP system.
    """
    try:
        data = erp.get_product_data(product_id, requested_discount)
        if not data.get("exists"):
            return json.dumps({"error": "Product not found in ERP system."})
        return json.dumps({
            "product_id": product_id,
            "stock_quantity": data["stock_quantity"],
            "margin_percentage": data["margin_percentage"]
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


tools = [get_crm_offer_details, get_erp_product_details]


class OfferAgent:
    """
    AI Decision Support Agent.
    - Mock mode: Directly executes CRM and ERP tool functions to produce dynamic, contextual summaries locally.
    - Groq mode: Executes autonomous tool calling chain via LangChain create_tool_calling_agent.
    """

    def __init__(self, llm=None):
        self._injected_llm = llm
        self._agent_executor = None
        self._built = False

    def _build(self):
        """Initializes agent components on first call (lazy initialization)."""
        if self._injected_llm:
            agent = create_tool_calling_agent(self._injected_llm, tools, TOOL_CALLING_PROMPT)
            self._agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)
        elif settings.LLM_MODE == "groq" and settings.GROQ_API_KEY:
            llm = ChatGroq(
                api_key=settings.GROQ_API_KEY,
                model_name=settings.LLM_MODEL,
                temperature=0.0,
                timeout=10,
                max_retries=1
            )
            agent = create_tool_calling_agent(llm, tools, TOOL_CALLING_PROMPT)
            self._agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

        self._built = True

    def generate_summary(
        self,
        context: AgentContext,
        decision_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates an executive summary and conditional approval draft based on deterministic engine results.
        """
        if not self._built:
            self._build()

        decision = decision_result["decision"]
        reason_codes_str = ", ".join(decision_result["reason_codes"])

        # 1. Default (Mock) Mode: Directly invoke tools to generate rich contextual summary
        if not self._agent_executor:
            return self._generate_mock_tool_summary(context, decision_result)

        # 2. Live LLM (Groq) Mode
        try:
            response = self._agent_executor.invoke({
                "offer_id": context.offer_id,
                "product_id": context.product_id,
                "requested_discount": context.requested_discount,
                "decision": decision,
                "reason_codes": reason_codes_str,
            })
            output_str = response["output"].strip()
            if output_str.startswith("```json"):
                output_str = output_str[7:]
            if output_str.startswith("```"):
                output_str = output_str[3:]
            if output_str.endswith("```"):
                output_str = output_str[:-3]
            raw_output = json.loads(output_str.strip())

            validated = AISummaryOutput(**raw_output)
            result = validated.model_dump()

            # Guardrail: Never generate approval drafts for APPROVE or REJECT decisions
            if decision != "NEED_APPROVAL":
                result["approval_message_draft"] = None
            elif not result.get("approval_message_draft"):
                result["approval_message_draft"] = (
                    f"Offer {context.offer_id} submitted for managerial approval due to: {reason_codes_str}."
                )

            result["ai_source"] = "llm"
            return result

        except (ValidationError, json.JSONDecodeError) as e:
            log_error(context.offer_id, f"AI Output Validation Error: {str(e)}", context.request_id)
            return self._fallback_summary(decision_result)

        except Exception as e:
            log_error(context.offer_id, f"AI Agent Error: {str(e)}", context.request_id)
            return self._fallback_summary(decision_result)

    def _generate_mock_tool_summary(
        self,
        context: AgentContext,
        decision_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mock mode summary generator that executes CRM and ERP tools directly,
        synthesizing realistic summaries from live data without internet dependencies.
        """
        decision = decision_result["decision"]
        reason_codes_str = ", ".join(decision_result["reason_codes"])
        customer_segment = decision_result["details"]["customer_segment"]

        # Tool 1: Execute CRM Tool
        try:
            crm_raw = get_crm_offer_details.invoke({"offer_id": context.offer_id})
            crm_data = json.loads(crm_raw)
        except Exception:
            crm_data = {}

        # Tool 2: Execute ERP Tool
        try:
            erp_raw = get_erp_product_details.invoke({
                "product_id": context.product_id,
                "requested_discount": context.requested_discount
            })
            erp_data = json.loads(erp_raw)
        except Exception:
            erp_data = {}

        stock_val = erp_data.get("stock_quantity", decision_result["details"].get("stock"))
        margin_val = erp_data.get("margin_percentage", decision_result["details"].get("margin"))
        segment_val = crm_data.get("segment", customer_segment)
        customer_display = crm_data.get("customer_name", "Partner")

        summary_parts = [
            f"For offer {context.offer_id}, partner segment '{segment_val}' was verified via CRM."
        ]

        if stock_val is not None and margin_val is not None:
            summary_parts.append(
                f"ERP records indicate available stock of {stock_val} units with a projected net margin of {margin_val}%."
            )

        if decision == "NEED_APPROVAL":
            summary_parts.append(
                f"Managerial approval is required due to triggered policy rules ({reason_codes_str})."
            )
            approval_draft = (
                f"Offer {context.offer_id} for {customer_display} submitted for manager review "
                f"due to: {reason_codes_str}."
            )
        elif decision == "REJECT":
            summary_parts.append(
                f"Offer was rejected based on policy criteria ({reason_codes_str})."
            )
            approval_draft = None
        else:
            summary_parts.append(
                "Offer approved: Stock availability, profit margin, and data integrity criteria are fully satisfied."
            )
            approval_draft = None

        return {
            "ai_summary": " ".join(summary_parts),
            "approval_message_draft": approval_draft,
            "ai_source": "mock"
        }

    def _fallback_summary(self, decision_result: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic fallback mechanism triggered when LLM services encounter errors or timeouts."""
        decision = decision_result["decision"]
        reason_codes = ", ".join(decision_result["reason_codes"])

        result = {
            "ai_summary": f"System summary: Decision evaluated as {decision}. Reason codes: {reason_codes}.",
            "approval_message_draft": None,
            "ai_source": "fallback"
        }

        if decision == "NEED_APPROVAL":
            result["approval_message_draft"] = (
                f"Automated Notification: Offer routed for managerial approval according to business policy ({reason_codes}). "
                "Please review."
            )

        return result

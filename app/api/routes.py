import uuid
from fastapi import APIRouter, HTTPException
from app.api.schemas import OfferRequest, OfferResponse
from app.core.decision_engine import DecisionEngine
from app.ai.offer_agent import OfferAgent, AgentContext
from app.utils.logger import log_offer_evaluation, log_error

router = APIRouter()

decision_engine = DecisionEngine()
offer_agent = OfferAgent()


@router.post("/evaluate-offer", response_model=OfferResponse)
def evaluate_offer(request: OfferRequest):
    """
    Offer pre-evaluation endpoint.
    A unique request_id is generated for every call to ensure end-to-end traceability.
    """
    request_id = str(uuid.uuid4())

    try:
        offer_data = request.model_dump()

        # 1. Deterministic evaluation via rule engine
        decision_result = decision_engine.evaluate(offer_data)

        # 2. Audit log entry (Zero PII, trace-indexed with request_id)
        log_offer_evaluation(offer_data, decision_result, request_id)

        # 3. AI decision synthesis (PII-free context)
        agent_context = AgentContext(
            offer_id=offer_data["offer_id"],
            requested_discount=offer_data["requested_discount"],
            offer_total=offer_data["offer_total"],
            quantity=offer_data["quantity"],
            product_id=offer_data["product_id"],
            request_id=request_id
        )
        ai_result = offer_agent.generate_summary(agent_context, decision_result)

        return OfferResponse(
            request_id=request_id,
            offer_id=request.offer_id,
            decision=decision_result["decision"],
            reason_codes=decision_result["reason_codes"],
            ai_summary=ai_result.get("ai_summary", "Summary could not be generated."),
            approval_required=(decision_result["decision"] == "NEED_APPROVAL"),
            approval_message_draft=ai_result.get("approval_message_draft"),
            pii_masked=True
        )

    except FileNotFoundError as fnf_err:
        log_error(request.offer_id, f"Integration Error: {str(fnf_err)}", request_id)
        raise HTTPException(
            status_code=502,
            detail="Enterprise system integration data file not found."
        )

    except Exception as e:
        log_error(request.offer_id, f"{type(e).__name__}: {str(e)}", request_id)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during offer evaluation."
        )

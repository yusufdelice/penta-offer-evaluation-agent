# Sample cURL Requests & API Responses

> **Architecture Reference:** Technical Specification — *“Production cURL & Postman request samples with corresponding Mock and Live LLM response payloads.”*

This document provides complete end-to-end examples covering every decision path (`APPROVE`, `REJECT`, `NEED_APPROVAL`) and Pydantic input validation error handling. Each scenario details outputs under both **Local Mock Mode (`LLM_MODE=mock`)** and **Live Groq LLM Mode (`LLM_MODE=groq`)**.

---

## 1. Test Scenarios Overview

| # | Scenario | Condition Under Test | Resolved Decision | Business Reason Codes |
|---|---|---|---|---|
| **1** | **Low Margin & High Value** | $125,000 (>100k) & net margin 9.09% (<10%) after 12% discount | `NEED_APPROVAL` | `LOW_MARGIN`, `HIGH_VALUE_OFFER` |
| **2** | **Standard Deal (Compliant)** | 2 units ordered (250 in stock), net margin 29.82% (>10%) | `APPROVE` | `ALL_CRITERIA_MET` |
| **3** | **Critical Stock Deficit** | 20 units requested, 5 units in warehouse (coverage 25% < 70%) | `REJECT` | `INSUFFICIENT_STOCK` |
| **4** | **Invalid Payload (Validation)** | Negative quantity entered (`quantity: -5`) | `HTTP 422` | `greater_than` validation constraint |

---

## 2. Interactive Testing via Swagger UI

With the application running locally (`uvicorn app.main:app --reload --port 8000`):
1. Navigate to `http://localhost:8000/docs` in your browser.
2. Expand the **`POST /evaluate-offer`** endpoint and click **Try it out**.
3. Paste any of the sample JSON payloads below and click **Execute**.

---

## 3. End-to-End Scenarios & cURL Samples

### Scenario 1: Low Margin & High Deal Value (Manager Review — NEED_APPROVAL)

```bash
curl -X POST "http://localhost:8000/evaluate-offer" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": "OFF-10023",
    "customer": {"name": "Acme Technology", "email": "buyer@example.com"},
    "product_id": "PRD-445",
    "quantity": 8,
    "requested_discount": 12,
    "offer_total": 125000,
    "customer_segment": "strategic_partner"
  }'
```

**A) Mock Mode Response (`LLM_MODE=mock` — Direct Tool Invocation):**
```json
{
  "request_id": "37753a44-a788-4faa-9045-f84cd730dba9",
  "offer_id": "OFF-10023",
  "decision": "NEED_APPROVAL",
  "reason_codes": [
    "LOW_MARGIN",
    "HIGH_VALUE_OFFER"
  ],
  "ai_summary": "For offer OFF-10023, partner segment 'strategic_partner' was verified via CRM. ERP records indicate available stock of 50 units with a projected net margin of 9.09%. Managerial approval is required due to triggered policy rules (LOW_MARGIN, HIGH_VALUE_OFFER).",
  "approval_required": true,
  "approval_message_draft": "Offer OFF-10023 for A*** T********* submitted for manager review due to: LOW_MARGIN, HIGH_VALUE_OFFER.",
  "pii_masked": true
}
```

**B) Live LLM Mode Response (`LLM_MODE=groq` — LLaMA-3.3-70B / Qwen):**
```json
{
  "request_id": "0fba2488-ed3f-4106-8a26-2644b1a584c9",
  "offer_id": "OFF-10023",
  "decision": "NEED_APPROVAL",
  "reason_codes": [
    "LOW_MARGIN",
    "HIGH_VALUE_OFFER"
  ],
  "ai_summary": "Offer OFF-10023 for strategic partner A*** T********* has been routed for managerial approval due to high total value ($125,000) and a reduced net margin of 9.09% following a 12% discount. Warehouse inventory (50 units) is sufficient.",
  "approval_required": true,
  "approval_message_draft": "Manager Review Requested: Quotation OFF-10023 for strategic partner A*** T********* requests a 12% discount reducing net profit margin to 9.09%, while exceeding the high-value deal threshold at $125,000. Inventory is fully available (50 units). Approval requested.",
  "pii_masked": true
}
```

---

### Scenario 2: Standard Compliant Quotation (All Criteria Met — APPROVE)

```bash
curl -X POST "http://localhost:8000/evaluate-offer" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": "OFF-20001",
    "customer": {"name": "Nova Systems Inc", "email": "procurement@novasystems.com"},
    "product_id": "PRD-101",
    "quantity": 2,
    "requested_discount": 5,
    "offer_total": 2280,
    "customer_segment": "standard"
  }'
```

**Response (HTTP 200 OK):**
```json
{
  "request_id": "ef1217d2-f7db-439e-ab7e-c871728686d9",
  "offer_id": "OFF-20001",
  "decision": "APPROVE",
  "reason_codes": [
    "ALL_CRITERIA_MET"
  ],
  "ai_summary": "For offer OFF-20001, partner segment 'standard' was verified via CRM. ERP records indicate available stock of 250 units with a projected net margin of 29.82%. Offer approved: Stock availability, profit margin, and data integrity criteria are fully satisfied.",
  "approval_required": false,
  "approval_message_draft": null,
  "pii_masked": true
}
```
*Notice: `approval_message_draft` is strictly set to `null` by the logic guardrail.*

---

### Scenario 3: Critical Stock Deficit (Insufficient Warehouse Stock — REJECT)

```bash
curl -X POST "http://localhost:8000/evaluate-offer" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": "OFF-10023",
    "customer": {"name": "Acme Technology"},
    "product_id": "PRD-999",
    "quantity": 20,
    "requested_discount": 5,
    "offer_total": 95000,
    "customer_segment": "strategic_partner"
  }'
```

**Response (HTTP 200 OK):**
```json
{
  "request_id": "8716f185-122e-4b26-86b4-223d611ef829",
  "offer_id": "OFF-10023",
  "decision": "REJECT",
  "reason_codes": [
    "INSUFFICIENT_STOCK"
  ],
  "ai_summary": "For offer OFF-10023, partner segment 'strategic_partner' was verified via CRM. ERP records indicate available stock of 5 units with a projected net margin of 5.26%. Offer was rejected based on policy criteria (INSUFFICIENT_STOCK).",
  "approval_required": false,
  "approval_message_draft": null,
  "pii_masked": true
}
```

---

### Scenario 4: Input Validation Failure (HTTP 422 Unprocessable Entity)

Demonstrating strict boundary filtering via Pydantic (`quantity: -5`):

```bash
curl -X POST "http://localhost:8000/evaluate-offer" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": "OFF-10023",
    "customer": {"name": "Acme Technology"},
    "product_id": "PRD-445",
    "quantity": -5,
    "requested_discount": 10,
    "offer_total": 10000,
    "customer_segment": "strategic_partner"
  }'
```

**Response (HTTP 422 Unprocessable Entity):**
```json
{
  "detail": [
    {
      "type": "greater_than",
      "loc": [
        "body",
        "quantity"
      ],
      "msg": "Input should be greater than 0",
      "input": -5,
      "ctx": {
        "gt": 0
      }
    }
  ]
}
```

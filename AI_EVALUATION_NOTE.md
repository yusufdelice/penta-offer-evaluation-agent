# AI Agent Component Architecture & Evaluation Report

> **Architecture Reference:** Technical Specification — *“Evaluation note covering the objective, scope, limitations, guardrail defenses, and data privacy principles of the artificial intelligence component.”*

---

## 1. Positioning and Objective

In enterprise B2B value-added technology distribution, distributors manage tens of thousands of active SKUs, tiered partner agreements, and dynamic discounting requests. Sales operations managers frequently encounter high volumes of quote approval requests. Manually checking stock availability, cost baselines, net margins, and tier compliance across separate ERP and CRM interfaces creates severe operational bottlenecks and delays deal velocity.

In this architecture, the AI component (LangChain-powered `OfferAgent`):
1. **Is NOT a Decision-Maker:** High-stakes commercial and financial decisions cannot be delegated to an opaque LLM. The final decision (`APPROVE`, `REJECT`, `NEED_APPROVAL`) is produced exclusively by a deterministic, rule-based `DecisionEngine`.
2. **Serves as a Decision-Support Copilot:** It analyzes the rule engine's raw technical codes (e.g., `LOW_MARGIN`, `HIGH_VALUE_OFFER`), correlates ERP/CRM state via tool calling, and generates a fluent, contextual executive summary (`ai_summary`) that sales managers can digest in seconds.
3. **Accelerates Deal Velocity:** For quotations requiring human intervention (`NEED_APPROVAL`), the agent drafts a ready-to-send managerial approval request message (`approval_message_draft`), drastically reducing human turn-around time.

---

## 2. Scope & Technical Capabilities

* **Tool / Function Calling:** The agent interacts with external backend boundaries through isolated, read-only tools:
  * `get_crm_offer_details(offer_id)`: Verifies deal registration and retrieves the partner's customer tier.
  * `get_erp_product_details(product_id, requested_discount)`: Queries physical inventory levels and computes real-time net margins against cost baselines.
* **Natural Language Deal Synthesis:** Translates discrete business rule codes into high-level business narratives.
* **Pydantic Contract Validation:** All model outputs are strictly validated against the `AISummaryOutput` schema, preventing unformatted, hallucinatory, or corrupted JSON responses.

---

## 3. Limitations, Guardrail Defenses & Risk Mitigation

1. **Hallucination Containment:** The model is strictly constrained to the sanitized `AgentContext` and live tool outputs. It cannot browse the public web or extrapolate outside provided enterprise boundaries.
2. **Architectural Decision Isolation (Single Source of Truth):** The prompt forbids the LLM from attempting to alter or dispute the engine's decision. More importantly, at the code level, the `decision` field in the API response is bound directly to `decision_engine.evaluate()`—it is structurally impossible for the LLM output to overwrite the verdict.
3. **Logic Guardrail (Approval Draft Scrubbing):** Managerial approval drafts are only relevant when human intervention is needed. If the model hallucinates an approval draft for an `APPROVE` or `REJECT` decision, backend application logic automatically resets `approval_message_draft = None`.
4. **Resilience & High Availability (Graceful Fallback):** External LLM outages, token rate limits (HTTP 429), or network timeouts never crash the service. The system instantly switches to a rule-based deterministic summary (`_fallback_summary` with `ai_source: fallback`). The entire application can also operate fully offline with zero internet dependencies using `LLM_MODE=mock`.

---

## 4. Privacy-by-Design & Data Protection

To protect partner commercial secrets and comply with global privacy regulations (GDPR/CCPA):

1. **Zero-PII Transmission:** Customer personal identities, buyer names, direct emails, and phone numbers are **never sent** to external LLM providers (Groq/cloud models).
2. **Context Isolation:** `OfferAgent` receives only an isolated, sanitized `AgentContext` containing anonymous quote, SKU, discount, and amount figures.
3. **Masking at the Tool Boundary:** When the agent calls the CRM tool, company and contact names are scrubbed using `pii.mask_name` (e.g., `Acme Technology` -> `A*** T*********`).
4. **Audit Log Isolation:** Audit log entries retain only transactional metrics and correlation UUIDs, completely excluding customer personal information.

---
*For complete code implementation, architectural diagrams, and automated test specifications, see the main documentation: [README.md](README.md)*

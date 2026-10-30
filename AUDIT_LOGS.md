# Privacy-Preserving Enterprise Audit Logging (Zero-PII)

> **Architecture Reference:** Technical Specification — *“Production audit logging architecture with strict Zero-PII compliance and end-to-end transaction traceability.”*

---

## 1. Audit Logging Architecture & Data Minimization

In enterprise environments, system log files are persisted across disk storage, aggregated into centralized SIEM platforms (e.g., Datadog, Splunk, Elastic, AWS CloudWatch), and monitored by operations personnel. Under GDPR, CCPA, and enterprise privacy standards, leaking Personally Identifiable Information (PII) or commercial deal secrets into log streams constitutes a critical compliance violation.

This platform enforces **Data Minimization** and **Full Traceability** through the following principles:

1. **Zero-PII Ingestion:** Customer personal details, contact names, email addresses, and phone numbers are **never written** to audit logs.
2. **Correlation ID (`request_id`):** Every inbound HTTP request receives a cryptographically unique UUID at the API gateway layer. This identifier serves as the single correlation key across client responses, decision events (`OFFER_EVALUATED`), and error occurrences (`OFFER_ERROR`).
3. **Dual-Channel Dispatch:** Logs are synchronously streamed to `stdout` (`StreamHandler`) for containerized orchestration (Docker/Kubernetes) and appended to a persistent audit trail (`project/logs/audit.log`).

* **Record Format:** `YYYY-MM-DD HH:MM:SS | LOG_LEVEL | LOG_TAG | JSON_PAYLOAD`

---

## 2. Successful Quotation Evaluation Entry (`OFFER_EVALUATED`)

Real-world audit log record emitted upon successful rule evaluation:

```text
2026-09-22 17:37:32 | INFO | OFFER_EVALUATED | {"timestamp": "2026-09-22T14:37:32.060201+00:00", "request_id": "ef1217d2-f7db-439e-ab7e-c871728686d9", "offer_id": "OFF-20001", "product_id": "PRD-101", "decision": "APPROVE", "reason_codes": ["ALL_CRITERIA_MET"], "details": {"customer_segment": "standard", "stock": 250, "margin": 29.82}}
```

**Parsed Structural JSON:**
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

*Note: Raw customer names (e.g., "Nova Systems Inc"), buyer emails, and direct phone lines are excluded. Only non-PII technical metrics, segment tags, and decision codes are retained.*

---

## 3. System & Fault Logging (`OFFER_ERROR`)

Emitted during external LLM outages, rate limits (HTTP 429), gateway timeouts, or integration disconnections:

```text
2026-09-22 17:37:32 | ERROR | OFFER_ERROR | {"timestamp": "2026-09-22T14:37:32.046188+00:00", "request_id": "c0a6ce15-37c7-418d-8e2a-477a829948ff", "offer_id": "OFF-10023", "error": "AI Agent Error: Groq API Timeout"}
```

**Parsed Structural JSON:**
```json
{
  "timestamp": "2026-09-22T14:37:32.046188+00:00",
  "request_id": "c0a6ce15-37c7-418d-8e2a-477a829948ff",
  "offer_id": "OFF-10023",
  "error": "AI Agent Error: Groq API Timeout"
}
```

---

## 4. End-to-End Operational Traceability

In the event of a customer dispute or an internal audit inspection:
1. The operations team retrieves the `request_id` (e.g., `c0a6ce15-...`) from the partner quote record or portal interface.
2. The SIEM or `logs/audit.log` file is queried for this specific correlation key.
3. The exact timestamp, evaluated SKU, inventory level, margin percentage, triggered policy rules, and resolved decision can be proven within seconds.
4. Total compliance is guaranteed: no confidential personal contact details are stored in or exposed via the logging pipeline.

# Mock Data Sets & Mock Service Architecture

> **Architecture Reference:** Technical Specification — *“Specification of mock data structures and service adapter patterns simulating enterprise systems.”*

---

## 1. Architectural Strategy & Context

In enterprise value-added technology distribution architectures, quotation offers are evaluated against real-time data from Enterprise Resource Planning (ERP) and Customer Relationship Management (CRM) backends. 

Rather than embedding static dictionary lookups (`mock_db = {...}`) directly into business logic, this prototype strictly implements the **Service & Adapter Pattern** decoupling clean, schema-driven **external JSON datasets** (`data/`) from domain evaluation rules. This mirrors enterprise multi-tier decoupling and ensures seamless production migration to systems like SAP and Salesforce without altering business logic.

---

## 2. Mock Dataset Schemas (`data/`)

### A. `data/offers.json` (CRM Master Offer Database)
Represents verified registered deal registrations and partner segment profiles:
```json
[
  {
    "offer_id": "OFF-10023",
    "customer": {
      "name": "Acme Technology",
      "segment": "strategic_partner"
    },
    "product_id": "PRD-445",
    "quantity": 8,
    "requested_discount": 12,
    "offer_total": 125000
  },
  {
    "offer_id": "OFF-20001",
    "customer": {
      "name": "Nova Systems Inc",
      "segment": "standard"
    },
    "product_id": "PRD-101",
    "quantity": 2,
    "requested_discount": 5,
    "offer_total": 2280
  }
]
```

### B. `data/stock.json` (ERP Warehouse Inventory)
Tracks real-time physical inventory quantities across SKU lines:
```json
{
  "PRD-445": { "stock_quantity": 50 },
  "PRD-101": { "stock_quantity": 250 },
  "PRD-999": { "stock_quantity": 5 }
}
```

### C. `data/prices.json` (ERP Pricing & Cost Catalog)
Contains standard base catalog prices (`base_price`) and procurement cost bases (`cost_price`):
```json
{
  "PRD-445": { "base_price": 17755.68, "cost_price": 14200.0 },
  "PRD-101": { "base_price": 1200.0, "cost_price": 800.0 },
  "PRD-999": { "base_price": 5000.0, "cost_price": 4500.0 }
}
```

---

## 3. Service & Adapter Pattern

Data sources are accessed exclusively through specialized client adapters:

### 1. `CRMClient` (`app/services/crm_client.py`)
- Reads `data/offers.json` from disk and indexes records in memory keyed by `offer_id`.
- The `get_offer(offer_id)` method verifies offer existence and resolves partner customer tiering (`segment`). Returns `None` if the offer ID is unregistered.
- Provides customer account identity for subsequent privacy-scrubbed processing.

### 2. `ERPClient` (`app/services/erp_client.py`)
- Reads inventory (`data/stock.json`) and pricing (`data/prices.json`) dynamically.
- The `get_product_data(product_id, requested_discount)` method applies requested partner discounts to base prices and computes the **net profit margin** deterministically:
  ```text
  Discounted Unit Price = Base Price * (1 - (Requested Discount / 100))
  Net Profit Margin (%) = ((Discounted Unit Price - Procurement Cost) / Discounted Unit Price) * 100
  ```
- Returns `{"exists": False}` if the requested product SKU is missing from the catalog.

---

## 4. Integration Fault Tolerance & Error Handling

- **Resilience to Storage Faults:** If any mock data file is deleted or inaccessible, the client raises a controlled `FileNotFoundError`.
- **Proper Gateway Error Status:** The API orchestration layer (`app/api/routes.py`) catches this exception and returns an informative `HTTP 502 Bad Gateway` ("Enterprise system integration data file not found") rather than an ambiguous `HTTP 500`.
- **Traceability:** Integration failures are automatically logged to `logs/audit.log` under the `OFFER_ERROR` event tag correlated with the incoming `request_id`.

---

## 5. Enterprise Production Transition Roadmap

Thanks to the adapter design, migrating from prototype to live enterprise infrastructure requires zero modification to core decision logic:
- The `DecisionEngine` and FastAPI endpoints remain completely untouched.
- `CRMClient` JSON loading is replaced with an enterprise REST/OData client connecting to Salesforce, Microsoft Dynamics 365, or HubSpot.
- `ERPClient` file lookups are substituted with SAP RFC/BAPI connectors, Oracle NetSuite REST services, or enterprise message brokers (Kafka/RabbitMQ).
- An in-memory distributed cache (e.g., Redis) with a 5-10 minute TTL can be placed in front of ERP endpoints to shield legacy systems during high quote volumes.

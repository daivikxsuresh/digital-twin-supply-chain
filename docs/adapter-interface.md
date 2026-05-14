# Adding a New ERP or TMS Integration

6-step protocol. Nothing outside these steps needs to change.

---

## Step 1 — Create the adapter file

For an ERP:
```
backend/app/adapters/erp/<system_name>_erp.py
```
For a TMS:
```
backend/app/adapters/tms/<system_name>_tms.py
```

---

## Step 2 — Subclass the correct base

```python
from app.adapters.base import BaseERPAdapter  # or BaseTMSAdapter

class SAPERPAdapter(BaseERPAdapter):
    source_system = "SAP_ERP"  # unique identifier for this system
```

---

## Step 3 — Implement all abstract methods

Every method must yield or return **canonical models only** — never raw API responses.

### ERP methods
| Method | Returns | Notes |
|--------|---------|-------|
| `fetch_orders()` | `AsyncIterator[CanonicalOrder]` | Yield newest first |
| `fetch_inventory_snapshots()` | `AsyncIterator[CanonicalInventorySnapshot]` | Current stock levels |
| `fetch_suppliers()` | `AsyncIterator[CanonicalSupplier]` | Active suppliers only |
| `fetch_facilities()` | `AsyncIterator[CanonicalFacility]` | Factories, DCs, stores |
| `push_recommendation()` | `WritebackResult` | Must be idempotent on `recommendation_id` |

### TMS methods
| Method | Returns | Notes |
|--------|---------|-------|
| `fetch_shipments()` | `AsyncIterator[CanonicalShipment]` | Active + recent |
| `fetch_shipment_location()` | `dict` | Keys: latitude, longitude, timestamp, status_description |
| `push_shipment_instruction()` | `WritebackResult` | Idempotent on shipment_id + instruction hash |

---

## Step 4 — Map your system's fields to canonical fields

Use `csv_erp.py` as the reference implementation — it documents every field mapping in its module docstring.

Key rules:
- `external_id` = your system's primary key for this record (used for dedup on upsert)
- `source_system` = must match `source_system` class attribute
- All timestamps must be `datetime` objects (timezone-aware preferred)
- Enum fields (status, shipping_mode, etc.) must use the canonical enum values

---

## Step 5 — Register in ADAPTER_REGISTRY

```python
# backend/app/adapters/__init__.py
from app.adapters.erp.sap_erp import SAPERPAdapter

ADAPTER_REGISTRY = {
    "CSV_ERP": CSVERPAdapter,
    "CSV_TMS": CSVTMSAdapter,
    "SAP_ERP": SAPERPAdapter,   # ← add this line
}
```

---

## Step 6 — Add a test

Create `backend/tests/unit/test_<system>_adapter.py` following the pattern in `test_csv_erp_adapter.py`.

Minimum test coverage:
- `fetch_orders()` yields at least one `CanonicalOrder` with all required fields
- `push_recommendation()` returns `WritebackResult(success=True)` and is idempotent

---

## That's it

The ingest pipeline (Kafka), twin engine, KPI engine, API, and frontend are all data-agnostic. They consume canonical models and never know which system produced them.

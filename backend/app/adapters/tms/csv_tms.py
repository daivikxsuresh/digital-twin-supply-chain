"""
CSV TMS Adapter
===============
Reads shipment data from the same DataCo CSV used by CSVERPAdapter.
In a real deployment this would call a TMS API (Oracle TMS, Blue Yonder, etc.).

DataCo column mapping for shipments
-------------------------------------
  "Order Id"                   → CanonicalShipment.order_id
  "Shipping Mode"              → CanonicalShipment.shipping_mode
  "Delivery Status"            → CanonicalShipment.status
  "Days for shipping (real)"   → CanonicalShipment.actual_transit_days
  "Days for shipment (schedu)" → CanonicalShipment.promised_transit_days
  "Late_delivery_risk"         → CanonicalShipment.late_delivery_risk
  "shipping date (DateOrders)" → CanonicalShipment.departed_at
  "order date (DateOrders)"    → used to compute promised_delivery_at
  "Order City/State/Country"   → destination fields
"""

import csv
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path

from app.adapters.base import BaseTMSAdapter
from app.adapters.canonical_models import (
    CanonicalRecommendation,
    CanonicalShipment,
    ShipmentStatus,
    ShippingMode,
    WritebackResult,
)

DEFAULT_CSV_PATH = Path(__file__).parents[6] / "data" / "demo" / "dataco.csv"

_SHIPPING_MODE_MAP = {
    "Standard Class": ShippingMode.STANDARD,
    "Second Class": ShippingMode.SECOND_CLASS,
    "First Class": ShippingMode.FIRST_CLASS,
    "Same Day": ShippingMode.SAME_DAY,
}

_DELIVERY_STATUS_MAP = {
    "Shipping on time": ShipmentStatus.IN_TRANSIT,
    "Advance shipping": ShipmentStatus.DELIVERED,
    "Late delivery": ShipmentStatus.EXCEPTION,
    "Shipping canceled": ShipmentStatus.CANCELLED,
}


def _parse_dt(value: str) -> datetime | None:
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value.strip()))
    except (ValueError, AttributeError):
        return default


class CSVTMSAdapter(BaseTMSAdapter):
    source_system = "CSV_TMS"

    def __init__(self, csv_path: Path | str | None = None) -> None:
        self.csv_path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH

    def _read_rows(self) -> list[dict]:
        if not self.csv_path.exists():
            return []
        with open(self.csv_path, encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))

    async def fetch_shipments(self) -> AsyncIterator[CanonicalShipment]:
        rows = self._read_rows()
        seen: set[str] = set()
        for i, row in enumerate(rows):
            order_id = row.get("Order Id", "").strip()
            if not order_id:
                continue
            # One shipment per order row (DataCo has one delivery per order)
            external_id = f"SHIP_{order_id}_{i}"
            if external_id in seen:
                continue
            seen.add(external_id)

            mode_raw = row.get("Shipping Mode", "Standard Class").strip()
            status_raw = row.get("Delivery Status", "Shipping on time").strip()
            departed_at = _parse_dt(row.get("shipping date (DateOrders)", ""))
            promised_days = _safe_int(row.get("Days for shipment (scheduled)", "0"))
            actual_days = _safe_int(row.get("Days for shipping (real)", "0"))
            order_date = _parse_dt(row.get("order date (DateOrders)", ""))
            promised_delivery = (
                (order_date + timedelta(days=promised_days)) if order_date and promised_days else None
            )
            actual_delivery = (
                (departed_at + timedelta(days=actual_days)) if departed_at and actual_days else None
            )
            late_risk_raw = row.get("Late_delivery_risk", "0").strip()
            yield CanonicalShipment(
                external_id=external_id,
                source_system=self.source_system,
                order_id=order_id,
                shipping_mode=_SHIPPING_MODE_MAP.get(mode_raw, ShippingMode.STANDARD),
                status=_DELIVERY_STATUS_MAP.get(status_raw, ShipmentStatus.IN_TRANSIT),
                destination_city=row.get("Order City", "").strip() or None,
                destination_state=row.get("Order State", "").strip() or None,
                destination_country=row.get("Order Country", "").strip() or None,
                departed_at=departed_at,
                promised_delivery_at=promised_delivery,
                actual_delivery_at=actual_delivery,
                promised_transit_days=promised_days or None,
                actual_transit_days=actual_days or None,
                late_delivery_risk=late_risk_raw == "1",
            )

    async def fetch_shipment_location(self, shipment_external_id: str) -> dict:
        # CSV has no live GPS — return a static placeholder suitable for demo
        return {
            "latitude": None,
            "longitude": None,
            "timestamp": datetime.utcnow().isoformat(),
            "status_description": "Location tracking not available in CSV mode",
        }

    async def push_shipment_instruction(
        self, shipment_external_id: str, instruction: dict
    ) -> WritebackResult:
        import json
        from pathlib import Path as _Path

        outbox = self.csv_path.parent / "outbox"
        outbox.mkdir(exist_ok=True)
        out_file = outbox / f"tms_{shipment_external_id}.json"
        out_file.write_text(json.dumps({"shipment_id": shipment_external_id, **instruction}, indent=2))
        return WritebackResult(
            recommendation_id=shipment_external_id,
            success=True,
            external_reference=str(out_file),
        )

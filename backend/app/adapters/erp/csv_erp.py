"""
CSV ERP Adapter — Reference Implementation
==========================================
Reads supply chain data from CSV files and yields canonical models.
This is the adapter that powers the demo (DataCo Smart Supply Chain dataset).

DataCo Dataset column mapping
------------------------------
The DataCo Smart Supply Chain dataset (Kaggle) has these relevant columns:

ORDERS
  "Order Id"                  → CanonicalOrder.external_id
  "Customer Id"               → CanonicalOrder.customer_id
  "Customer Fname"+"Lname"    → CanonicalOrder.customer_name
  "Customer Segment"          → CanonicalOrder.customer_segment
  "Order Status"              → CanonicalOrder.status
      DataCo values: COMPLETE, PENDING, PENDING_PAYMENT, PROCESSING,
                     CLOSED, ON_HOLD, SUSPECTED_FRAUD, CANCELED
  "Market"                    → CanonicalOrder.market
  "Order Region"              → CanonicalOrder.region
  "Order City"                → CanonicalOrder.destination_city
  "Order State"               → CanonicalOrder.destination_state
  "Order Country"             → CanonicalOrder.destination_country
  "order date (DateOrders)"   → CanonicalOrder.ordered_at
  "Order Item Total"          → CanonicalOrder.total_amount
  "Order Profit Per Order"    → CanonicalOrder.profit

ORDER ITEMS (one row per item in DataCo)
  "Order Item Cardprod Id"    → CanonicalOrderItem.product_id
  "Product Name"              → CanonicalOrderItem.product_name
  "Category Name"             → CanonicalOrderItem.category
  "Order Item Quantity"       → CanonicalOrderItem.quantity
  "Order Item Product Price"  → CanonicalOrderItem.unit_price
  "Order Item Discount"       → CanonicalOrderItem.discount
  "Order Item Total"          → CanonicalOrderItem.total

SHIPMENTS
  "Order Id"                  → CanonicalShipment.order_id (+ row index as suffix)
  "Shipping Mode"             → CanonicalShipment.shipping_mode
      DataCo values: Standard Class → STANDARD
                     Second Class   → SECOND_CLASS
                     First Class    → FIRST_CLASS
                     Same Day       → SAME_DAY
  "Delivery Status"           → CanonicalShipment.status
      DataCo values: Shipping on time  → IN_TRANSIT
                     Advance shipping  → DELIVERED
                     Late delivery     → EXCEPTION
                     Shipping canceled → CANCELLED
  "Days for shipping (real)"  → CanonicalShipment.actual_transit_days
  "Days for shipment (schedu)"→ CanonicalShipment.promised_transit_days
  "Late_delivery_risk"        → CanonicalShipment.late_delivery_risk
  "shipping date (DateOrders)"→ CanonicalShipment.departed_at
  "Order City/State/Country"  → CanonicalShipment.destination_*

SUPPLIERS (derived from Department Name)
  "Department Id"             → CanonicalSupplier.external_id
  "Department Name"           → CanonicalSupplier.name
  "Category Name"             → CanonicalSupplier.category

FACILITIES (derived from unique Order City/Region combos)
  Constructed as DIST_<region>_<city> distribution centers

INVENTORY (inferred from order quantities per product per region)
  Snapshot generated at adapter read time from aggregated order data
"""

import csv
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path

from app.adapters.base import BaseERPAdapter
from app.adapters.canonical_models import (
    CanonicalFacility,
    CanonicalInventorySnapshot,
    CanonicalOrder,
    CanonicalOrderItem,
    CanonicalRecommendation,
    CanonicalShipment,
    CanonicalSupplier,
    FacilityType,
    OrderStatus,
    ShipmentStatus,
    ShippingMode,
    WritebackResult,
)

# Default path — override by passing csv_path to __init__
DEFAULT_CSV_PATH = Path(__file__).parents[6] / "data" / "demo" / "dataco.csv"

_ORDER_STATUS_MAP = {
    "COMPLETE": OrderStatus.DELIVERED,
    "CLOSED": OrderStatus.DELIVERED,
    "PENDING": OrderStatus.PENDING,
    "PENDING_PAYMENT": OrderStatus.PENDING,
    "PAYMENT_REVIEW": OrderStatus.PENDING,
    "PROCESSING": OrderStatus.PROCESSING,
    "ON_HOLD": OrderStatus.ON_HOLD,
    "SUSPECTED_FRAUD": OrderStatus.ON_HOLD,
    "CANCELED": OrderStatus.CANCELLED,
}

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


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return default


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value.strip()))
    except (ValueError, AttributeError):
        return default


class CSVERPAdapter(BaseERPAdapter):
    """
    ERP adapter backed by a CSV file.
    Powers the demo with DataCo data; swap for SAPERPAdapter on a real client.
    """

    source_system = "CSV_ERP"

    def __init__(self, csv_path: Path | str | None = None) -> None:
        self.csv_path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH

    def _read_rows(self) -> list[dict]:
        if not self.csv_path.exists():
            return []
        with open(self.csv_path, encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))

    async def fetch_orders(self) -> AsyncIterator[CanonicalOrder]:
        rows = self._read_rows()
        # Group rows by Order Id (DataCo has one row per item)
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row.get("Order Id", "").strip()].append(row)

        for order_id, order_rows in grouped.items():
            if not order_id:
                continue
            first = order_rows[0]
            items = [
                CanonicalOrderItem(
                    product_id=r.get("Order Item Cardprod Id", "").strip() or "UNKNOWN",
                    product_name=r.get("Product Name", "").strip() or "Unknown Product",
                    category=r.get("Category Name", "").strip() or None,
                    quantity=_safe_int(r.get("Order Item Quantity", "1")),
                    unit_price=_safe_float(r.get("Order Item Product Price", "0")),
                    discount=_safe_float(r.get("Order Item Discount", "0")),
                    total=_safe_float(r.get("Order Item Total", "0")),
                )
                for r in order_rows
            ]
            status_raw = first.get("Order Status", "PENDING").strip().upper()
            ordered_at = _parse_dt(first.get("order date (DateOrders)", "")) or datetime.utcnow()
            yield CanonicalOrder(
                external_id=order_id,
                source_system=self.source_system,
                customer_id=first.get("Customer Id", "").strip() or "UNKNOWN",
                customer_name=(
                    f"{first.get('Customer Fname','').strip()} "
                    f"{first.get('Customer Lname','').strip()}".strip() or None
                ),
                customer_segment=first.get("Customer Segment", "").strip() or None,
                items=items,
                status=_ORDER_STATUS_MAP.get(status_raw, OrderStatus.PENDING),
                market=first.get("Market", "").strip() or None,
                region=first.get("Order Region", "").strip() or None,
                destination_city=first.get("Order City", "").strip() or None,
                destination_state=first.get("Order State", "").strip() or None,
                destination_country=first.get("Order Country", "").strip() or None,
                ordered_at=ordered_at,
                total_amount=_safe_float(first.get("Sales", "0")),
                profit=_safe_float(first.get("Order Profit Per Order", "0")),
            )

    async def fetch_inventory_snapshots(self) -> AsyncIterator[CanonicalInventorySnapshot]:
        rows = self._read_rows()
        # Aggregate quantity by (region, product_id) as a proxy for DC inventory
        stock: dict[tuple[str, str], dict] = {}
        for row in rows:
            region = row.get("Order Region", "UNKNOWN").strip()
            product_id = row.get("Order Item Cardprod Id", "").strip()
            if not product_id:
                continue
            key = (region, product_id)
            if key not in stock:
                stock[key] = {
                    "facility_id": f"DC_{region.upper().replace(' ', '_')}",
                    "product_id": product_id,
                    "product_name": row.get("Product Name", "").strip(),
                    "quantity": 0,
                    "unit_cost": _safe_float(row.get("Order Item Product Price", "0")),
                }
            stock[key]["quantity"] += _safe_int(row.get("Order Item Quantity", "0"))

        now = datetime.utcnow()
        for (region, product_id), data in stock.items():
            yield CanonicalInventorySnapshot(
                external_id=f"{data['facility_id']}_{product_id}",
                source_system=self.source_system,
                facility_id=data["facility_id"],
                product_id=product_id,
                product_name=data["product_name"] or None,
                quantity_on_hand=float(data["quantity"]),
                unit_cost=data["unit_cost"] or None,
                safety_stock_level=float(max(10, data["quantity"] * 0.1)),
                snapshotted_at=now,
            )

    async def fetch_suppliers(self) -> AsyncIterator[CanonicalSupplier]:
        rows = self._read_rows()
        seen: set[str] = set()
        for row in rows:
            dept_id = row.get("Department Id", "").strip()
            if not dept_id or dept_id in seen:
                continue
            seen.add(dept_id)
            yield CanonicalSupplier(
                external_id=dept_id,
                source_system=self.source_system,
                name=row.get("Department Name", f"Supplier {dept_id}").strip(),
                category=row.get("Category Name", "").strip() or None,
            )

    async def fetch_facilities(self) -> AsyncIterator[CanonicalFacility]:
        rows = self._read_rows()
        seen: set[str] = set()
        for row in rows:
            region = row.get("Order Region", "").strip()
            if not region or region in seen:
                continue
            seen.add(region)
            yield CanonicalFacility(
                external_id=f"DC_{region.upper().replace(' ', '_')}",
                source_system=self.source_system,
                name=f"{region} Distribution Center",
                facility_type=FacilityType.DISTRIBUTION_CENTER,
                region=region,
                country=row.get("Order Country", "").strip() or None,
            )

    async def push_recommendation(
        self, recommendation: CanonicalRecommendation
    ) -> WritebackResult:
        outbox = self.csv_path.parent / "outbox"
        outbox.mkdir(exist_ok=True)
        out_file = outbox / f"rec_{recommendation.recommendation_id}.json"
        import json
        out_file.write_text(json.dumps(recommendation.model_dump(), indent=2, default=str))
        return WritebackResult(
            recommendation_id=recommendation.recommendation_id,
            success=True,
            external_reference=str(out_file),
        )

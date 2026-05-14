"""
Parametrized test suite for the CSV ERP adapter.
All adapter implementations must pass an equivalent test.
Run: pytest -k adapter
"""

import csv
import io
from pathlib import Path

import pytest

from app.adapters.erp.csv_erp import CSVERPAdapter
from app.adapters.canonical_models import (
    CanonicalFacility,
    CanonicalInventorySnapshot,
    CanonicalOrder,
    CanonicalSupplier,
    CanonicalRecommendation,
    RecommendationType,
)

# Minimal DataCo-format CSV for tests (2 rows = 1 order with 2 items)
SAMPLE_CSV = """\
Type,Days for shipping (real),Days for shipment (scheduled),Delivery Status,Late_delivery_risk,Category Id,Category Name,Customer City,Customer Country,Customer Email,Customer Fname,Customer Id,Customer Lname,Customer Segment,Customer State,Customer Street,Customer Zipcode,Department Id,Department Name,Latitude,Longitude,Market,Order City,Order Country,Order Customer Id,order date (DateOrders),Order Id,Order Item Cardprod Id,Order Item Discount,Order Item Id,Order Item Product Price,Order Item Profit Ratio,Order Item Quantity,Order Item Total,Order Profit Per Order,Order Region,Order State,Order Status,Order Zipcode,Product Card Id,Product Category Id,Product Description,Product Image,Product Name,Product Price,Product Status,shipping date (DateOrders),Shipping Mode,Sales
DEBIT,3,4,Shipping on time,1,73,Electronics,Caguas,EE. UU.,test@example.com,Mary,1234,Smith,Consumer,PR,123 Main St,725,2,Electronics Dept,18.23,-66.03,USCA,San Juan,Puerto Rico,1234,1/31/2018 22:56,10001,1360,0.09,1,89.99,0.15,2,163.78,24.57,US East,PR,COMPLETE,725,1360,73,None,http://example.com/img,Wireless Headphones Pro,89.99,1,2/3/2018 22:56,Standard Class,163.78
DEBIT,3,4,Shipping on time,1,73,Electronics,Caguas,EE. UU.,test@example.com,Mary,1234,Smith,Consumer,PR,123 Main St,725,2,Electronics Dept,18.23,-66.03,USCA,San Juan,Puerto Rico,1234,1/31/2018 22:56,10001,1361,0.05,2,59.99,0.12,1,56.99,6.84,US East,PR,COMPLETE,725,1361,73,None,http://example.com/img,Bluetooth Speaker Compact,59.99,1,2/3/2018 22:56,Standard Class,56.99
"""


@pytest.fixture
def csv_adapter(tmp_path: Path) -> CSVERPAdapter:
    csv_file = tmp_path / "dataco.csv"
    csv_file.write_text(SAMPLE_CSV, encoding="utf-8")
    return CSVERPAdapter(csv_path=csv_file)


@pytest.mark.asyncio
async def test_fetch_orders_yields_canonical_order(csv_adapter: CSVERPAdapter) -> None:
    orders = [o async for o in await csv_adapter.fetch_orders()]
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, CanonicalOrder)
    assert order.external_id == "10001"
    assert order.source_system == "CSV_ERP"
    assert order.customer_id == "1234"
    assert len(order.items) == 2


@pytest.mark.asyncio
async def test_fetch_orders_items_have_required_fields(csv_adapter: CSVERPAdapter) -> None:
    orders = [o async for o in await csv_adapter.fetch_orders()]
    for item in orders[0].items:
        assert item.product_id
        assert item.quantity > 0
        assert item.unit_price >= 0


@pytest.mark.asyncio
async def test_fetch_suppliers_yields_canonical_supplier(csv_adapter: CSVERPAdapter) -> None:
    suppliers = [s async for s in await csv_adapter.fetch_suppliers()]
    assert len(suppliers) >= 1
    supplier = suppliers[0]
    assert isinstance(supplier, CanonicalSupplier)
    assert supplier.external_id
    assert supplier.name
    assert supplier.source_system == "CSV_ERP"


@pytest.mark.asyncio
async def test_fetch_facilities_yields_canonical_facility(csv_adapter: CSVERPAdapter) -> None:
    facilities = [f async for f in await csv_adapter.fetch_facilities()]
    assert len(facilities) >= 1
    facility = facilities[0]
    assert isinstance(facility, CanonicalFacility)
    assert facility.external_id
    assert facility.facility_type


@pytest.mark.asyncio
async def test_fetch_inventory_snapshots_yields_snapshots(csv_adapter: CSVERPAdapter) -> None:
    snapshots = [s async for s in await csv_adapter.fetch_inventory_snapshots()]
    assert len(snapshots) >= 1
    snap = snapshots[0]
    assert isinstance(snap, CanonicalInventorySnapshot)
    assert snap.quantity_on_hand >= 0
    assert snap.facility_id
    assert snap.product_id


@pytest.mark.asyncio
async def test_push_recommendation_returns_success(
    csv_adapter: CSVERPAdapter, tmp_path: Path
) -> None:
    rec = CanonicalRecommendation(
        recommendation_type=RecommendationType.REORDER,
        target_facility_id="DC_USCA",
        rationale="Stock below safety level",
        requires_approval=True,
        twin_confidence=0.92,
        suggested_action={"product_id": "PROD_001", "reorder_qty": 100},
    )
    result = await csv_adapter.push_recommendation(rec)
    assert result.success is True
    assert result.recommendation_id == rec.recommendation_id


@pytest.mark.asyncio
async def test_push_recommendation_is_idempotent(
    csv_adapter: CSVERPAdapter,
) -> None:
    rec = CanonicalRecommendation(
        recommendation_type=RecommendationType.EXPEDITE,
        target_order_id="ORD_0001",
        rationale="Critical delivery at risk",
        requires_approval=False,
        twin_confidence=0.87,
    )
    result1 = await csv_adapter.push_recommendation(rec)
    result2 = await csv_adapter.push_recommendation(rec)
    assert result1.success is True
    assert result2.success is True
    # Same recommendation_id → same output file (idempotent)
    assert result1.external_reference == result2.external_reference

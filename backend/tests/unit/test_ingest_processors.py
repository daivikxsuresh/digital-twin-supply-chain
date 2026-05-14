"""
Unit tests for ingest processors — validates canonical event parsing
and deduplication logic without hitting Kafka or the database.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingest.processors.inventory_processor import InventoryProcessor
from app.ingest.processors.order_processor import OrderProcessor
from app.ingest.processors.shipment_processor import ShipmentProcessor

NOW = datetime.now(timezone.utc).isoformat()


def _make_order_event(external_id: str = "TEST_ORD_001") -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "order.updated",
        "source_system": "CSV_ERP",
        "occurred_at": NOW,
        "payload": {
            "external_id": external_id,
            "source_system": "CSV_ERP",
            "customer_id": "CUST_001",
            "customer_name": "Test Customer",
            "items": [
                {
                    "product_id": "PROD_001",
                    "product_name": "Widget",
                    "quantity": 5,
                    "unit_price": 10.0,
                    "discount": 0.0,
                    "total": 50.0,
                }
            ],
            "status": "PROCESSING",
            "ordered_at": NOW,
            "total_amount": 50.0,
            "profit": 10.0,
        },
    }


def _make_shipment_event(external_id: str = "TEST_SHIP_001") -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "shipment.updated",
        "source_system": "CSV_TMS",
        "occurred_at": NOW,
        "payload": {
            "external_id": external_id,
            "source_system": "CSV_TMS",
            "order_id": "TEST_ORD_001",
            "shipping_mode": "STANDARD",
            "status": "IN_TRANSIT",
            "late_delivery_risk": False,
            "current_latitude": 40.7128,
            "current_longitude": -74.0060,
        },
    }


def _make_inventory_event(external_id: str = "DC_USCA_PROD_001") -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "inventory.snapshot",
        "source_system": "CSV_ERP",
        "occurred_at": NOW,
        "payload": {
            "external_id": external_id,
            "source_system": "CSV_ERP",
            "facility_id": "DC_USCA",
            "product_id": "PROD_001",
            "product_name": "Widget",
            "quantity_on_hand": 250.0,
            "quantity_reserved": 10.0,
            "snapshotted_at": NOW,
        },
    }


def _make_inventory_event_simulator_format() -> dict:
    """Simulator uses sku_id / snapshot_timestamp — processor must normalize these."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "inventory.snapshot",
        "source_system": "CSV_ERP",
        "occurred_at": NOW,
        "payload": {
            "external_id": "DC_USE_PROD_002",
            "source_system": "CSV_ERP",
            "facility_id": "DC_USE",
            "sku_id": "PROD_002",              # simulator field
            "quantity_on_hand": 100.0,
            "quantity_reserved": 5.0,
            "snapshot_timestamp": NOW,          # simulator field
        },
    }


@pytest.mark.asyncio
async def test_order_processor_parses_valid_event() -> None:
    processor = OrderProcessor.__new__(OrderProcessor)
    mock_msg = MagicMock()
    event = _make_order_event()

    with patch("app.ingest.processors.order_processor.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = mock_session

        await processor.process(event, mock_msg)
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_order_processor_rejects_invalid_payload() -> None:
    processor = OrderProcessor.__new__(OrderProcessor)
    mock_msg = MagicMock()
    bad_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "order.updated",
        "source_system": "CSV_ERP",
        "occurred_at": NOW,
        "payload": {"bad_field": "no external_id or customer_id"},
    }
    with pytest.raises(ValueError, match="Invalid CanonicalOrder payload"):
        await processor.process(bad_event, mock_msg)


@pytest.mark.asyncio
async def test_shipment_processor_parses_valid_event() -> None:
    processor = ShipmentProcessor.__new__(ShipmentProcessor)
    mock_msg = MagicMock()
    event = _make_shipment_event()

    with patch("app.ingest.processors.shipment_processor.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = mock_session

        await processor.process(event, mock_msg)
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_inventory_processor_parses_valid_event() -> None:
    processor = InventoryProcessor.__new__(InventoryProcessor)
    mock_msg = MagicMock()
    event = _make_inventory_event()

    with patch("app.ingest.processors.inventory_processor.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = mock_session

        await processor.process(event, mock_msg)
        mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_inventory_processor_normalizes_simulator_fields() -> None:
    """Simulator sends sku_id / snapshot_timestamp — processor must handle both."""
    processor = InventoryProcessor.__new__(InventoryProcessor)
    mock_msg = MagicMock()
    event = _make_inventory_event_simulator_format()

    with patch("app.ingest.processors.inventory_processor.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = mock_session

        await processor.process(event, mock_msg)
        mock_session.execute.assert_called_once()

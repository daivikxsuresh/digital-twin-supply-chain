"""
Inventory processor — consumes supply.inventory.
- Inserts a new InventorySnapshot row (append-only hypertable — never updates)
- Dedup: ON CONFLICT on (org_id, source_system, external_id, snapshotted_at) DO NOTHING
- Phase 3 hook: triggers KPI recompute when stock crosses alert thresholds
"""

import uuid
from datetime import datetime, timezone

import structlog
from confluent_kafka import Message
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.adapters.canonical_models import CanonicalInventorySnapshot
from app.db.session import AsyncSessionLocal
from app.ingest import topics as T
from app.ingest.consumer import BaseConsumer
from app.models.inventory import InventorySnapshot

logger = structlog.get_logger(__name__)

DEMO_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class InventoryProcessor(BaseConsumer):
    def __init__(self) -> None:
        super().__init__(topics=[T.INVENTORY])

    async def process(self, event: dict, raw_message: Message) -> None:
        payload = event.get("payload", {})

        # Normalize simulator payload → canonical shape
        # simulator uses "sku_id"; canonical uses "product_id"
        if "sku_id" in payload and "product_id" not in payload:
            payload["product_id"] = payload.pop("sku_id")
        if "snapshot_timestamp" in payload and "snapshotted_at" not in payload:
            payload["snapshotted_at"] = payload.pop("snapshot_timestamp")
        if "snapshotted_at" not in payload:
            payload["snapshotted_at"] = event.get("occurred_at", datetime.now(timezone.utc).isoformat())

        try:
            snapshot = CanonicalInventorySnapshot.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid CanonicalInventorySnapshot payload: {exc}") from exc

        async with AsyncSessionLocal() as session:
            stmt = (
                pg_insert(InventorySnapshot)
                .values(
                    org_id=DEMO_ORG_ID,
                    source_system=snapshot.source_system,
                    external_id=snapshot.external_id,
                    facility_id=snapshot.facility_id,
                    product_id=snapshot.product_id,
                    product_name=snapshot.product_name,
                    quantity_on_hand=snapshot.quantity_on_hand,
                    quantity_reserved=snapshot.quantity_reserved,
                    unit_cost=snapshot.unit_cost,
                    safety_stock_level=snapshot.safety_stock_level,
                    snapshotted_at=snapshot.snapshotted_at,
                )
                .on_conflict_do_nothing(constraint="uq_inventory_snapshot_dedup")
            )
            await session.execute(stmt)
            await session.commit()

        logger.info(
            "inventory.snapshot_inserted",
            facility_id=snapshot.facility_id,
            product_id=snapshot.product_id,
            quantity_on_hand=snapshot.quantity_on_hand,
        )

        # Phase 3 hook: trigger KPI recompute if below safety stock
        # if snapshot.safety_stock_level and snapshot.quantity_on_hand < snapshot.safety_stock_level:
        #     await kpi_engine.trigger_recompute(org_id=DEMO_ORG_ID, facility_id=snapshot.facility_id)

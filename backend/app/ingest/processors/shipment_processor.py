"""
Shipment processor — consumes supply.shipments.
- Upserts shipment record (dedup on org_id + source_system + external_id)
- Appends a ShipmentLocationEvent row to the hypertable if lat/lng present
"""

import uuid
from datetime import datetime, timezone

import structlog
from confluent_kafka import Message
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.adapters.canonical_models import CanonicalShipment
from app.db.session import AsyncSessionLocal
from app.ingest import topics as T
from app.ingest.consumer import BaseConsumer
from app.models.inventory import ShipmentLocationEvent
from app.models.shipment import Shipment

logger = structlog.get_logger(__name__)

DEMO_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class ShipmentProcessor(BaseConsumer):
    def __init__(self) -> None:
        super().__init__(topics=[T.SHIPMENTS])

    async def process(self, event: dict, raw_message: Message) -> None:
        payload = event.get("payload", {})
        try:
            shipment = CanonicalShipment.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid CanonicalShipment payload: {exc}") from exc

        async with AsyncSessionLocal() as session:
            # Upsert shipment row
            stmt = (
                pg_insert(Shipment)
                .values(
                    org_id=DEMO_ORG_ID,
                    source_system=shipment.source_system,
                    external_id=shipment.external_id,
                    order_id=shipment.order_id,
                    carrier=shipment.carrier,
                    shipping_mode=shipment.shipping_mode,
                    status=shipment.status,
                    origin_facility_id=shipment.origin_facility_id,
                    destination_city=shipment.destination_city,
                    destination_state=shipment.destination_state,
                    destination_country=shipment.destination_country,
                    departed_at=shipment.departed_at,
                    promised_delivery_at=shipment.promised_delivery_at,
                    actual_delivery_at=shipment.actual_delivery_at,
                    promised_transit_days=shipment.promised_transit_days,
                    actual_transit_days=shipment.actual_transit_days,
                    late_delivery_risk=shipment.late_delivery_risk,
                )
                .on_conflict_do_update(
                    constraint="uq_shipments_dedup",
                    set_={
                        "status": shipment.status,
                        "actual_delivery_at": shipment.actual_delivery_at,
                        "actual_transit_days": shipment.actual_transit_days,
                        "late_delivery_risk": shipment.late_delivery_risk,
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(stmt)

            # Append location event if coordinates present
            lat = payload.get("current_latitude")
            lng = payload.get("current_longitude")
            if lat is not None and lng is not None:
                session.add(
                    ShipmentLocationEvent(
                        org_id=DEMO_ORG_ID,
                        shipment_id=shipment.external_id,
                        latitude=float(lat),
                        longitude=float(lng),
                        status_description=str(shipment.status),
                        recorded_at=datetime.now(timezone.utc),
                    )
                )

            await session.commit()

        logger.info(
            "shipment.upserted",
            external_id=shipment.external_id,
            status=shipment.status,
            order_id=shipment.order_id,
        )

        # Phase 2 hook: update shipment state machine in twin engine
        # await twin_engine.handle_event(event)

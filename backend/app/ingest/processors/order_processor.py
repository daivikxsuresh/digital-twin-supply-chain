"""
Order processor — consumes supply.orders, upserts to orders table.
Deduplication: INSERT ... ON CONFLICT (org_id, source_system, external_id) DO UPDATE.
Triggers twin graph update signal after any status change.
"""

import uuid
from datetime import datetime, timezone

import structlog
from confluent_kafka import Message
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.adapters.canonical_models import CanonicalOrder
from app.db.session import AsyncSessionLocal
from app.ingest import topics as T
from app.ingest.consumer import BaseConsumer
from app.models.order import Order

logger = structlog.get_logger(__name__)

# Demo org — replaced by JWT-derived org_id in Phase 4
DEMO_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class OrderProcessor(BaseConsumer):
    def __init__(self) -> None:
        super().__init__(topics=[T.ORDERS])

    async def process(self, event: dict, raw_message: Message) -> None:
        payload = event.get("payload", {})
        try:
            order = CanonicalOrder.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid CanonicalOrder payload: {exc}") from exc

        async with AsyncSessionLocal() as session:
            stmt = (
                pg_insert(Order)
                .values(
                    org_id=DEMO_ORG_ID,
                    source_system=order.source_system,
                    external_id=order.external_id,
                    customer_id=order.customer_id,
                    customer_name=order.customer_name,
                    customer_segment=order.customer_segment,
                    status=order.status,
                    market=order.market,
                    region=order.region,
                    destination_city=order.destination_city,
                    destination_state=order.destination_state,
                    destination_country=order.destination_country,
                    items=[item.model_dump() for item in order.items],
                    total_amount=order.total_amount,
                    profit=order.profit,
                    ordered_at=order.ordered_at,
                    requested_delivery_at=order.requested_delivery_at,
                )
                .on_conflict_do_update(
                    constraint="uq_orders_dedup",
                    set_={
                        "status": order.status,
                        "total_amount": order.total_amount,
                        "profit": order.profit,
                        "items": [item.model_dump() for item in order.items],
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()

        logger.info(
            "order.upserted",
            external_id=order.external_id,
            status=order.status,
            source_system=order.source_system,
        )

        # Phase 2 hook: signal twin engine to update graph node for this order
        # await twin_engine.handle_event(event)  # wired up in Phase 2

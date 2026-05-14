import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class InventorySnapshot(BaseModel):
    """
    Append-only table — never updated, only inserted.
    Stored as a TimescaleDB hypertable (see migration 001) partitioned by snapshotted_at.
    Query via time_bucket() for trends; latest snapshot = MAX(snapshotted_at) per facility+product.
    """

    __tablename__ = "inventory_snapshots"

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)

    facility_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    product_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    quantity_on_hand: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_reserved: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_stock_level: Mapped[float | None] = mapped_column(Float, nullable=True)

    snapshotted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id", "source_system", "external_id", "snapshotted_at",
            name="uq_inventory_snapshot_dedup"
        ),
    )


class ShipmentLocationEvent(BaseModel):
    """
    Append-only GPS ping table — TimescaleDB hypertable partitioned by recorded_at.
    Powers the live map in the React frontend via WebSocket push.
    """

    __tablename__ = "shipment_location_events"

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    shipment_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

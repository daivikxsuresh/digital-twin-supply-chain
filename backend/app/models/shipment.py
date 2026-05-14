import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Shipment(BaseModel):
    __tablename__ = "shipments"

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)

    order_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    carrier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shipping_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="STANDARD")
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    origin_facility_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    destination_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination_state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(128), nullable=True)

    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promised_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    promised_transit_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_transit_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    late_delivery_risk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "source_system", "external_id", name="uq_shipments_dedup"),
    )

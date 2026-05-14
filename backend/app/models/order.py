import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Order(BaseModel):
    __tablename__ = "orders"

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)

    customer_id: Mapped[str] = mapped_column(String(256), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    customer_segment: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    market: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination_state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(128), nullable=True)

    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    requested_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "source_system", "external_id", name="uq_orders_dedup"),
    )

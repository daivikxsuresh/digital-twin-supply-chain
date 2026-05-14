import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Union

from pydantic import BaseModel, ConfigDict, Field


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"


class ShipmentStatus(str, Enum):
    PENDING = "PENDING"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    EXCEPTION = "EXCEPTION"
    CANCELLED = "CANCELLED"


class ShippingMode(str, Enum):
    STANDARD = "STANDARD"
    SECOND_CLASS = "SECOND_CLASS"
    FIRST_CLASS = "FIRST_CLASS"
    SAME_DAY = "SAME_DAY"


class FacilityType(str, Enum):
    SUPPLIER = "SUPPLIER"
    FACTORY = "FACTORY"
    DISTRIBUTION_CENTER = "DISTRIBUTION_CENTER"
    STORE = "STORE"
    PORT = "PORT"


class RecommendationType(str, Enum):
    REORDER = "REORDER"
    REROUTE = "REROUTE"
    EXPEDITE = "EXPEDITE"
    CANCEL = "CANCEL"
    TRANSFER = "TRANSFER"


class _CanonicalBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)


class CanonicalSupplier(_CanonicalBase):
    external_id: str
    source_system: str
    name: str
    contact_email: str | None = None
    country: str | None = None
    city: str | None = None
    category: str | None = None
    active: bool = True


class CanonicalFacility(_CanonicalBase):
    external_id: str
    source_system: str
    name: str
    facility_type: FacilityType
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    region: str | None = None


class CanonicalOrderItem(_CanonicalBase):
    product_id: str
    product_name: str
    category: str | None = None
    quantity: int
    unit_price: float
    discount: float = 0.0
    total: float


class CanonicalOrder(_CanonicalBase):
    external_id: str
    source_system: str
    customer_id: str
    customer_name: str | None = None
    customer_segment: str | None = None
    items: list[CanonicalOrderItem]
    status: OrderStatus
    market: str | None = None
    region: str | None = None
    destination_city: str | None = None
    destination_state: str | None = None
    destination_country: str | None = None
    ordered_at: datetime
    requested_delivery_at: datetime | None = None
    total_amount: float
    profit: float = 0.0


class CanonicalShipment(_CanonicalBase):
    external_id: str
    source_system: str
    order_id: str
    carrier: str | None = None
    shipping_mode: ShippingMode = ShippingMode.STANDARD
    status: ShipmentStatus
    origin_facility_id: str | None = None
    destination_city: str | None = None
    destination_state: str | None = None
    destination_country: str | None = None
    departed_at: datetime | None = None
    promised_delivery_at: datetime | None = None
    actual_delivery_at: datetime | None = None
    promised_transit_days: int | None = None
    actual_transit_days: int | None = None
    late_delivery_risk: bool = False


class CanonicalInventorySnapshot(_CanonicalBase):
    external_id: str
    source_system: str
    facility_id: str
    product_id: str
    product_name: str | None = None
    quantity_on_hand: float
    quantity_reserved: float = 0.0
    unit_cost: float | None = None
    safety_stock_level: float | None = None
    snapshotted_at: datetime


# ── Event envelope ──────────────────────────────────────────────────────────

EventPayload = Annotated[
    Union[
        CanonicalOrder,
        CanonicalShipment,
        CanonicalInventorySnapshot,
        CanonicalSupplier,
        CanonicalFacility,
    ],
    Field(discriminator=None),
]


class CanonicalEvent(_CanonicalBase):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str  # e.g. "order.created", "shipment.updated", "inventory.snapshot"
    source_system: str
    occurred_at: datetime
    payload: EventPayload


# ── Writeback ────────────────────────────────────────────────────────────────

class CanonicalRecommendation(_CanonicalBase):
    recommendation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recommendation_type: RecommendationType
    target_order_id: str | None = None
    target_shipment_id: str | None = None
    target_facility_id: str | None = None
    rationale: str
    requires_approval: bool = True
    twin_confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    suggested_action: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WritebackResult(_CanonicalBase):
    recommendation_id: str
    success: bool
    external_reference: str | None = None
    error_message: str | None = None
    executed_at: datetime = Field(default_factory=datetime.utcnow)

"""001_initial_schema

Revision ID: 001
Revises:
Create Date: 2026-05-14

Creates all supply chain tables + TimescaleDB hypertables for time-series data.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable extensions ────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── suppliers ────────────────────────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("contact_email", sa.String(256), nullable=True),
        sa.Column("country", sa.String(128), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_suppliers_org_id", "suppliers", ["org_id"])
    op.create_unique_constraint("uq_suppliers_dedup", "suppliers",
                                ["org_id", "source_system", "external_id"])

    # ── facilities ───────────────────────────────────────────────────────────
    op.create_table(
        "facilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("facility_type", sa.String(64), nullable=False),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("state", sa.String(128), nullable=True),
        sa.Column("country", sa.String(128), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("region", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_facilities_org_id", "facilities", ["org_id"])
    op.create_unique_constraint("uq_facilities_dedup", "facilities",
                                ["org_id", "source_system", "external_id"])

    # ── orders ───────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("customer_id", sa.String(256), nullable=False),
        sa.Column("customer_name", sa.String(256), nullable=True),
        sa.Column("customer_segment", sa.String(128), nullable=True),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("market", sa.String(128), nullable=True),
        sa.Column("region", sa.String(128), nullable=True),
        sa.Column("destination_city", sa.String(128), nullable=True),
        sa.Column("destination_state", sa.String(128), nullable=True),
        sa.Column("destination_country", sa.String(128), nullable=True),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("profit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_orders_org_id", "orders", ["org_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_ordered_at", "orders", ["ordered_at"])
    op.create_unique_constraint("uq_orders_dedup", "orders",
                                ["org_id", "source_system", "external_id"])

    # ── shipments ────────────────────────────────────────────────────────────
    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("order_id", sa.String(256), nullable=False),
        sa.Column("carrier", sa.String(128), nullable=True),
        sa.Column("shipping_mode", sa.String(64), nullable=False, server_default="STANDARD"),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("origin_facility_id", sa.String(256), nullable=True),
        sa.Column("destination_city", sa.String(128), nullable=True),
        sa.Column("destination_state", sa.String(128), nullable=True),
        sa.Column("destination_country", sa.String(128), nullable=True),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promised_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promised_transit_days", sa.Integer(), nullable=True),
        sa.Column("actual_transit_days", sa.Integer(), nullable=True),
        sa.Column("late_delivery_risk", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_shipments_org_id", "shipments", ["org_id"])
    op.create_index("ix_shipments_order_id", "shipments", ["order_id"])
    op.create_index("ix_shipments_status", "shipments", ["status"])
    op.create_index("ix_shipments_actual_delivery_at", "shipments", ["actual_delivery_at"])
    op.create_unique_constraint("uq_shipments_dedup", "shipments",
                                ["org_id", "source_system", "external_id"])

    # ── inventory_snapshots (TimescaleDB hypertable) ─────────────────────────
    op.create_table(
        "inventory_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("facility_id", sa.String(256), nullable=False),
        sa.Column("product_id", sa.String(256), nullable=False),
        sa.Column("product_name", sa.String(256), nullable=True),
        sa.Column("quantity_on_hand", sa.Float(), nullable=False),
        sa.Column("quantity_reserved", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Float(), nullable=True),
        sa.Column("safety_stock_level", sa.Float(), nullable=True),
        sa.Column("snapshotted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_inventory_snapshots_org_id", "inventory_snapshots", ["org_id"])
    op.create_index("ix_inventory_snapshots_facility_id", "inventory_snapshots", ["facility_id"])
    op.create_index("ix_inventory_snapshots_product_id", "inventory_snapshots", ["product_id"])
    op.create_index("ix_inventory_snapshots_snapshotted_at", "inventory_snapshots", ["snapshotted_at"])
    op.create_unique_constraint(
        "uq_inventory_snapshot_dedup", "inventory_snapshots",
        ["org_id", "source_system", "external_id", "snapshotted_at"]
    )
    op.execute(
        "SELECT create_hypertable('inventory_snapshots', 'snapshotted_at', "
        "if_not_exists => TRUE)"
    )

    # ── shipment_location_events (TimescaleDB hypertable) ────────────────────
    op.create_table(
        "shipment_location_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_id", sa.String(256), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("status_description", sa.String(256), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_shipment_location_events_org_id", "shipment_location_events", ["org_id"])
    op.create_index("ix_shipment_location_events_shipment_id", "shipment_location_events", ["shipment_id"])
    op.create_index("ix_shipment_location_events_recorded_at", "shipment_location_events", ["recorded_at"])
    op.execute(
        "SELECT create_hypertable('shipment_location_events', 'recorded_at', "
        "if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("shipment_location_events")
    op.drop_table("inventory_snapshots")
    op.drop_table("shipments")
    op.drop_table("orders")
    op.drop_table("facilities")
    op.drop_table("suppliers")

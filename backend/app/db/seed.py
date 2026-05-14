"""
seed_dev_data()
===============
Populates the database with realistic demo data for local development and demos.
3 suppliers · 2 factories · 3 DCs · 5 stores · 20 orders · 15 shipments
One user per RBAC role (added in Phase 4 when auth tables exist).

Run with:
    docker exec dt_backend python -m app.db.seed
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from random import choice, randint, uniform

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.facility import Facility
from app.models.inventory import InventorySnapshot
from app.models.order import Order
from app.models.shipment import Shipment
from app.models.supplier import Supplier

DEMO_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SOURCE = "CSV_ERP"
NOW = datetime.utcnow()


# ── Reference data ───────────────────────────────────────────────────────────

SUPPLIERS = [
    {"external_id": "SUP_001", "name": "Apex Electronics", "category": "Electronics",
     "country": "China", "city": "Shenzhen"},
    {"external_id": "SUP_002", "name": "ProTex Fabrics", "category": "Apparel",
     "country": "Vietnam", "city": "Ho Chi Minh City"},
    {"external_id": "SUP_003", "name": "OceanPack Logistics", "category": "Packaging",
     "country": "USA", "city": "Los Angeles"},
]

FACILITIES = [
    {"external_id": "FAC_001", "name": "Shenzhen Factory A", "facility_type": "FACTORY",
     "city": "Shenzhen", "country": "China", "region": "Asia Pacific",
     "latitude": 22.5431, "longitude": 114.0579},
    {"external_id": "FAC_002", "name": "Los Angeles Factory B", "facility_type": "FACTORY",
     "city": "Los Angeles", "country": "USA", "region": "USCA",
     "latitude": 34.0522, "longitude": -118.2437},
    {"external_id": "DC_USCA", "name": "West Coast DC", "facility_type": "DISTRIBUTION_CENTER",
     "city": "Los Angeles", "state": "CA", "country": "USA", "region": "USCA",
     "latitude": 33.9425, "longitude": -118.4081},
    {"external_id": "DC_USE", "name": "East Coast DC", "facility_type": "DISTRIBUTION_CENTER",
     "city": "Newark", "state": "NJ", "country": "USA", "region": "US East",
     "latitude": 40.7357, "longitude": -74.1724},
    {"external_id": "DC_EU", "name": "Europe DC", "facility_type": "DISTRIBUTION_CENTER",
     "city": "Rotterdam", "country": "Netherlands", "region": "Europe",
     "latitude": 51.9244, "longitude": 4.4777},
    {"external_id": "STORE_NY", "name": "New York Store", "facility_type": "STORE",
     "city": "New York", "state": "NY", "country": "USA", "region": "US East",
     "latitude": 40.7128, "longitude": -74.0060},
    {"external_id": "STORE_LA", "name": "Los Angeles Store", "facility_type": "STORE",
     "city": "Los Angeles", "state": "CA", "country": "USA", "region": "USCA",
     "latitude": 34.0195, "longitude": -118.4912},
    {"external_id": "STORE_CHI", "name": "Chicago Store", "facility_type": "STORE",
     "city": "Chicago", "state": "IL", "country": "USA", "region": "US Central",
     "latitude": 41.8781, "longitude": -87.6298},
    {"external_id": "STORE_LON", "name": "London Store", "facility_type": "STORE",
     "city": "London", "country": "UK", "region": "Europe",
     "latitude": 51.5074, "longitude": -0.1278},
    {"external_id": "STORE_TKY", "name": "Tokyo Store", "facility_type": "STORE",
     "city": "Tokyo", "country": "Japan", "region": "Asia Pacific",
     "latitude": 35.6762, "longitude": 139.6503},
]

PRODUCTS = [
    {"id": "PROD_001", "name": "Wireless Headphones Pro", "category": "Electronics", "price": 89.99},
    {"id": "PROD_002", "name": "Smart Watch Series X", "category": "Electronics", "price": 199.99},
    {"id": "PROD_003", "name": "Running Shorts Elite", "category": "Apparel", "price": 34.99},
    {"id": "PROD_004", "name": "Yoga Mat Premium", "category": "Fitness", "price": 49.99},
    {"id": "PROD_005", "name": "Bluetooth Speaker Compact", "category": "Electronics", "price": 59.99},
]

CUSTOMERS = [
    {"id": "CUST_001", "name": "Riverside Corp", "segment": "Corporate"},
    {"id": "CUST_002", "name": "Jane Hoffman", "segment": "Consumer"},
    {"id": "CUST_003", "name": "Metro Retail Group", "segment": "Wholesale"},
    {"id": "CUST_004", "name": "SportZone Inc", "segment": "Corporate"},
    {"id": "CUST_005", "name": "Alex Navarro", "segment": "Consumer"},
]

MARKETS = ["USCA", "US East", "US Central", "Europe", "Asia Pacific"]
REGIONS = ["West", "East", "Central", "Europe", "APAC"]
ORDER_STATUSES = ["DELIVERED", "DELIVERED", "DELIVERED", "PROCESSING", "PENDING",
                  "ON_HOLD", "CANCELLED"]
SHIP_STATUSES = ["DELIVERED", "DELIVERED", "IN_TRANSIT", "IN_TRANSIT", "EXCEPTION", "CANCELLED"]
SHIP_MODES = ["STANDARD", "SECOND_CLASS", "FIRST_CLASS", "SAME_DAY"]


def _order_items(n: int = 2) -> list[dict]:
    products = [choice(PRODUCTS) for _ in range(n)]
    items = []
    for p in products:
        qty = randint(1, 10)
        discount = choice([0.0, 0.05, 0.10])
        total = round(qty * p["price"] * (1 - discount), 2)
        items.append({
            "product_id": p["id"],
            "product_name": p["name"],
            "category": p["category"],
            "quantity": qty,
            "unit_price": p["price"],
            "discount": discount,
            "total": total,
        })
    return items


async def seed_dev_data() -> None:
    async with AsyncSessionLocal() as session:
        print("Seeding suppliers...")
        for s in SUPPLIERS:
            session.add(Supplier(
                org_id=DEMO_ORG_ID,
                source_system=SOURCE,
                external_id=s["external_id"],
                name=s["name"],
                category=s.get("category"),
                country=s.get("country"),
                city=s.get("city"),
                active=True,
            ))

        print("Seeding facilities...")
        for f in FACILITIES:
            session.add(Facility(
                org_id=DEMO_ORG_ID,
                source_system=SOURCE,
                external_id=f["external_id"],
                name=f["name"],
                facility_type=f["facility_type"],
                city=f.get("city"),
                state=f.get("state"),
                country=f.get("country"),
                region=f.get("region"),
                latitude=f.get("latitude"),
                longitude=f.get("longitude"),
            ))

        print("Seeding orders and shipments...")
        dc_ids = ["DC_USCA", "DC_USE", "DC_EU"]
        for i in range(1, 21):
            customer = choice(CUSTOMERS)
            market = choice(MARKETS)
            ordered_at = NOW - timedelta(days=randint(5, 60))
            items = _order_items(randint(1, 3))
            total = round(sum(item["total"] for item in items), 2)
            status = choice(ORDER_STATUSES)
            order = Order(
                org_id=DEMO_ORG_ID,
                source_system=SOURCE,
                external_id=f"ORD_{i:04d}",
                customer_id=customer["id"],
                customer_name=customer["name"],
                customer_segment=customer["segment"],
                status=status,
                market=market,
                region=choice(REGIONS),
                destination_city=choice(["New York", "Los Angeles", "Chicago", "London", "Tokyo"]),
                destination_country=choice(["USA", "USA", "USA", "UK", "Japan"]),
                items=items,
                total_amount=total,
                profit=round(total * uniform(0.05, 0.25), 2),
                ordered_at=ordered_at,
            )
            session.add(order)

            if i <= 15:
                ship_status = choice(SHIP_STATUSES)
                departed = ordered_at + timedelta(days=randint(1, 3))
                promised_days = randint(3, 10)
                actual_days = promised_days + randint(-1, 5)
                session.add(Shipment(
                    org_id=DEMO_ORG_ID,
                    source_system="CSV_TMS",
                    external_id=f"SHIP_{i:04d}",
                    order_id=f"ORD_{i:04d}",
                    shipping_mode=choice(SHIP_MODES),
                    status=ship_status,
                    origin_facility_id=choice(dc_ids),
                    destination_city=order.destination_city,
                    destination_country=order.destination_country,
                    departed_at=departed,
                    promised_delivery_at=departed + timedelta(days=promised_days),
                    actual_delivery_at=(
                        departed + timedelta(days=actual_days)
                        if ship_status == "DELIVERED" else None
                    ),
                    promised_transit_days=promised_days,
                    actual_transit_days=actual_days if ship_status == "DELIVERED" else None,
                    late_delivery_risk=actual_days > promised_days,
                ))

        print("Seeding inventory snapshots...")
        dc_facility_ids = ["DC_USCA", "DC_USE", "DC_EU"]
        for facility_id in dc_facility_ids:
            for product in PRODUCTS:
                qty = float(randint(50, 500))
                session.add(InventorySnapshot(
                    org_id=DEMO_ORG_ID,
                    source_system=SOURCE,
                    external_id=f"{facility_id}_{product['id']}",
                    facility_id=facility_id,
                    product_id=product["id"],
                    product_name=product["name"],
                    quantity_on_hand=qty,
                    quantity_reserved=float(randint(0, int(qty * 0.2))),
                    unit_cost=round(product["price"] * 0.6, 2),
                    safety_stock_level=round(qty * 0.15, 2),
                    snapshotted_at=NOW,
                ))

        await session.commit()
        print("Seed complete.")
        print(f"  Suppliers:            {len(SUPPLIERS)}")
        print(f"  Facilities:           {len(FACILITIES)}")
        print(f"  Orders:               20")
        print(f"  Shipments:            15")
        print(f"  Inventory snapshots:  {len(dc_facility_ids) * len(PRODUCTS)}")


if __name__ == "__main__":
    asyncio.run(seed_dev_data())

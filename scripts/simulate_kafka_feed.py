"""
Simulates a live ERP/TMS feed by publishing CanonicalEvents to Kafka.
Events are shaped to pass processor Pydantic validation.

Usage:
    python scripts/simulate_kafka_feed.py
    python scripts/simulate_kafka_feed.py --rate 2   # 2 events/sec per topic
    python scripts/simulate_kafka_feed.py --topic supply.orders --count 50
"""

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from confluent_kafka import Producer

BOOTSTRAP_SERVERS = "localhost:9092"

SUPPLIERS = ["SUP_001", "SUP_002", "SUP_003"]
FACILITY_IDS = ["DC_USCA", "DC_USE", "DC_EU", "FAC_001", "FAC_002",
                "STORE_NY", "STORE_LA", "STORE_CHI", "STORE_LON", "STORE_TKY"]
DC_IDS = ["DC_USCA", "DC_USE", "DC_EU"]
PRODUCTS = [
    {"id": "PROD_001", "name": "Wireless Headphones Pro", "category": "Electronics", "price": 89.99},
    {"id": "PROD_002", "name": "Smart Watch Series X", "category": "Electronics", "price": 199.99},
    {"id": "PROD_003", "name": "Running Shorts Elite", "category": "Apparel", "price": 34.99},
    {"id": "PROD_004", "name": "Yoga Mat Premium", "category": "Fitness", "price": 49.99},
    {"id": "PROD_005", "name": "Bluetooth Speaker Compact", "category": "Electronics", "price": 59.99},
]
CARRIERS = ["FedEx", "UPS", "DHL", "USPS", "XPO"]
CUSTOMERS = [
    {"id": "CUST_001", "name": "Riverside Corp", "segment": "Corporate"},
    {"id": "CUST_002", "name": "Jane Hoffman", "segment": "Consumer"},
    {"id": "CUST_003", "name": "Metro Retail Group", "segment": "Wholesale"},
]
MARKETS = ["USCA", "US East", "Europe", "Asia Pacific"]
ORDER_STATUSES = ["PENDING", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]
SHIPMENT_STATUSES = ["PENDING", "PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION"]
SHIP_MODES = ["STANDARD", "SECOND_CLASS", "FIRST_CLASS", "SAME_DAY"]
DESTINATIONS = [
    {"city": "New York", "state": "NY", "country": "USA"},
    {"city": "Los Angeles", "state": "CA", "country": "USA"},
    {"city": "Chicago", "state": "IL", "country": "USA"},
    {"city": "London", "state": None, "country": "UK"},
    {"city": "Tokyo", "state": None, "country": "Japan"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt(days_offset: int = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days_offset + random.randint(-1, 1))
    return dt.isoformat()


def _envelope(event_type: str, source_system: str, payload: dict) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "source_system": source_system,
        "occurred_at": _now(),
        "payload": payload,
    }


def make_order_event() -> tuple[str, str, dict]:
    customer = random.choice(CUSTOMERS)
    dest = random.choice(DESTINATIONS)
    products = random.sample(PRODUCTS, k=random.randint(1, 3))
    items = []
    total = 0.0
    for p in products:
        qty = random.randint(1, 10)
        discount = random.choice([0.0, 0.05, 0.10])
        item_total = round(qty * p["price"] * (1 - discount), 2)
        total += item_total
        items.append({
            "product_id": p["id"],
            "product_name": p["name"],
            "category": p["category"],
            "quantity": qty,
            "unit_price": p["price"],
            "discount": discount,
            "total": item_total,
        })
    external_id = f"SIM_{random.randint(10000, 99999)}"
    payload = {
        "external_id": external_id,
        "source_system": "CSV_ERP",
        "customer_id": customer["id"],
        "customer_name": customer["name"],
        "customer_segment": customer["segment"],
        "items": items,
        "status": random.choice(ORDER_STATUSES),
        "market": random.choice(MARKETS),
        "region": random.choice(["West", "East", "Central", "Europe", "APAC"]),
        "destination_city": dest["city"],
        "destination_state": dest["state"],
        "destination_country": dest["country"],
        "ordered_at": _dt(-random.randint(1, 30)),
        "total_amount": round(total, 2),
        "profit": round(total * random.uniform(0.05, 0.25), 2),
    }
    key = f"CSV_ERP:{external_id}"
    return "supply.orders", key, _envelope("order.updated", "CSV_ERP", payload)


def make_shipment_event() -> tuple[str, str, dict]:
    external_id = f"SHIP_SIM_{random.randint(10000, 99999)}"
    dest = random.choice(DESTINATIONS)
    status = random.choice(SHIPMENT_STATUSES)
    departed = _dt(-random.randint(1, 5))
    promised_days = random.randint(3, 10)
    actual_days = promised_days + random.randint(-1, 5)
    payload = {
        "external_id": external_id,
        "source_system": "CSV_TMS",
        "order_id": f"SIM_{random.randint(10000, 99999)}",
        "carrier": random.choice(CARRIERS),
        "shipping_mode": random.choice(SHIP_MODES),
        "status": status,
        "origin_facility_id": random.choice(DC_IDS),
        "destination_city": dest["city"],
        "destination_state": dest["state"],
        "destination_country": dest["country"],
        "departed_at": departed,
        "promised_transit_days": promised_days,
        "actual_transit_days": actual_days if status == "DELIVERED" else None,
        "actual_delivery_at": _dt(0) if status == "DELIVERED" else None,
        "late_delivery_risk": actual_days > promised_days,
        # Extra fields picked up by shipment processor for location hypertable
        "current_latitude": round(random.uniform(25.0, 48.0), 6),
        "current_longitude": round(random.uniform(-122.0, -71.0), 6),
    }
    key = f"CSV_TMS:{external_id}"
    return "supply.shipments", key, _envelope("shipment.updated", "CSV_TMS", payload)


def make_inventory_event() -> tuple[str, str, dict]:
    facility = random.choice(DC_IDS)
    product = random.choice(PRODUCTS)
    external_id = f"{facility}_{product['id']}"
    qty = round(random.uniform(0, 1000), 2)
    payload = {
        "external_id": external_id,
        "source_system": "CSV_ERP",
        "facility_id": facility,
        "product_id": product["id"],
        "product_name": product["name"],
        "quantity_on_hand": qty,
        "quantity_reserved": round(random.uniform(0, qty * 0.2), 2),
        "unit_cost": round(product["price"] * 0.6, 2),
        "safety_stock_level": round(qty * 0.15, 2),
        "snapshotted_at": _now(),
    }
    key = f"CSV_ERP:{external_id}"
    return "supply.inventory", key, _envelope("inventory.snapshot", "CSV_ERP", payload)


GENERATORS = {
    "supply.orders": make_order_event,
    "supply.shipments": make_shipment_event,
    "supply.inventory": make_inventory_event,
}


def delivery_report(err, msg):
    if err:
        print(f"  [FAIL] {msg.topic()}: {err}")


def main(rate: float, topic_filter: str | None, count: int | None):
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})
    interval = 1.0 / rate
    generators = (
        {topic_filter: GENERATORS[topic_filter]}
        if topic_filter and topic_filter in GENERATORS
        else GENERATORS
    )
    published = 0
    print(f"Publishing {rate} event/sec per topic → {BOOTSTRAP_SERVERS}")
    print("Ctrl+C to stop.\n")

    try:
        while True:
            for topic, gen in generators.items():
                actual_topic, key, event = gen()
                producer.produce(
                    topic=actual_topic,
                    key=key.encode(),
                    value=json.dumps(event, default=str).encode(),
                    callback=delivery_report,
                )
                print(f"  → {actual_topic}: {event['event_type']} [{event['payload']['external_id']}]")
                published += 1
                if count and published >= count:
                    raise KeyboardInterrupt
            producer.poll(0)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\nFlushing... ({published} events published)")
        producer.flush()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=1.0, help="Events/sec per topic")
    parser.add_argument("--topic", type=str, default=None, help="Publish to one topic only")
    parser.add_argument("--count", type=int, default=None, help="Stop after N total events")
    args = parser.parse_args()
    main(args.rate, args.topic, args.count)

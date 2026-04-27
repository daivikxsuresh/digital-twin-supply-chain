"""
Simulates a live ERP/TMS feed by publishing mock CanonicalEvents to Kafka.
Run while the stack is up to populate the twin with realistic data.

Usage:
    python scripts/simulate_kafka_feed.py
    python scripts/simulate_kafka_feed.py --rate 2  # 2 events/sec per topic
"""

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from confluent_kafka import Producer

BOOTSTRAP_SERVERS = "localhost:9092"

SUPPLIERS = ["SUP-001", "SUP-002", "SUP-003"]
FACILITIES = ["FAC-001", "FAC-002", "DC-001", "DC-002", "DC-003", "STR-001", "STR-002", "STR-003", "STR-004", "STR-005"]
SKUS = ["SKU-ALPHA", "SKU-BETA", "SKU-GAMMA", "SKU-DELTA", "SKU-EPSILON"]
CARRIERS = ["FedEx", "UPS", "DHL", "USPS", "XPO"]
ORDER_STATUSES = ["confirmed", "in_transit", "delivered"]
SHIPMENT_STATUSES = ["picked_up", "in_transit", "out_for_delivery", "delivered"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rand_date(days_offset: int = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days_offset + random.randint(-2, 2))
    return dt.isoformat()


def make_order_event() -> dict:
    origin = random.choice(SUPPLIERS)
    dest = random.choice([f for f in FACILITIES if f.startswith("DC") or f.startswith("FAC")])
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "order.updated",
        "source_system": "CSV_ERP",
        "occurred_at": now_iso(),
        "payload": {
            "external_id": f"PO-{random.randint(10000, 99999)}",
            "source_system": "CSV_ERP",
            "order_type": "purchase",
            "status": random.choice(ORDER_STATUSES),
            "origin_facility_id": origin,
            "destination_facility_id": dest,
            "sku_id": random.choice(SKUS),
            "quantity": round(random.uniform(50, 500), 2),
            "unit_of_measure": "units",
            "requested_delivery_date": rand_date(7),
            "confirmed_delivery_date": rand_date(6),
            "actual_delivery_date": rand_date(5) if random.random() > 0.4 else None,
            "unit_cost": round(random.uniform(10, 200), 2),
            "currency": "USD",
        },
    }


def make_shipment_event() -> dict:
    origin = random.choice([f for f in FACILITIES if f.startswith("DC") or f.startswith("FAC")])
    dest = random.choice([f for f in FACILITIES if f.startswith("STR")])
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "shipment.updated",
        "source_system": "CSV_TMS",
        "occurred_at": now_iso(),
        "payload": {
            "external_id": f"SHIP-{random.randint(10000, 99999)}",
            "source_system": "CSV_TMS",
            "order_id": f"PO-{random.randint(10000, 99999)}",
            "carrier": random.choice(CARRIERS),
            "tracking_number": f"TRK{random.randint(100000000, 999999999)}",
            "status": random.choice(SHIPMENT_STATUSES),
            "origin_facility_id": origin,
            "destination_facility_id": dest,
            "scheduled_pickup": rand_date(-3),
            "actual_pickup": rand_date(-2),
            "scheduled_delivery": rand_date(2),
            "actual_delivery": rand_date(1) if random.random() > 0.5 else None,
            "current_latitude": round(random.uniform(25.0, 48.0), 6),
            "current_longitude": round(random.uniform(-122.0, -71.0), 6),
            "cost": round(random.uniform(50, 800), 2),
            "currency": "USD",
        },
    }


def make_inventory_event() -> dict:
    facility = random.choice(FACILITIES)
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "inventory.snapshot",
        "source_system": "CSV_ERP",
        "occurred_at": now_iso(),
        "payload": {
            "external_id": f"INV-{facility}-{random.choice(SKUS)}",
            "source_system": "CSV_ERP",
            "facility_id": facility,
            "sku_id": random.choice(SKUS),
            "quantity_on_hand": round(random.uniform(0, 1000), 2),
            "quantity_reserved": round(random.uniform(0, 200), 2),
            "quantity_in_transit": round(random.uniform(0, 300), 2),
            "unit_cost": round(random.uniform(10, 200), 2),
            "snapshot_timestamp": now_iso(),
        },
    }


TOPIC_GENERATORS = {
    "supply.orders": make_order_event,
    "supply.shipments": make_shipment_event,
    "supply.inventory": make_inventory_event,
}


def delivery_report(err, msg):
    if err:
        print(f"  [ERROR] Failed to deliver to {msg.topic()}: {err}")


def main(rate: float):
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})
    interval = 1.0 / rate
    print(f"Publishing {rate} event/sec per topic to {BOOTSTRAP_SERVERS}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            for topic, generator in TOPIC_GENERATORS.items():
                event = generator()
                producer.produce(
                    topic=topic,
                    key=event["payload"]["external_id"],
                    value=json.dumps(event),
                    callback=delivery_report,
                )
                print(f"  → {topic}: {event['event_type']} [{event['payload']['external_id']}]")
            producer.poll(0)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nFlushing remaining messages...")
        producer.flush()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=1.0, help="Events per second per topic")
    args = parser.parse_args()
    main(args.rate)

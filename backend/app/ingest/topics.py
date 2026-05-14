"""All Kafka topic name constants. Single source of truth — never hardcode topic strings anywhere else."""

ORDERS = "supply.orders"
SHIPMENTS = "supply.shipments"
INVENTORY = "supply.inventory"
FACILITIES = "supply.facilities"
SUPPLIERS = "supply.suppliers"
DLQ = "supply.events.dlq"

ALL_TOPICS = [ORDERS, SHIPMENTS, INVENTORY, FACILITIES, SUPPLIERS, DLQ]

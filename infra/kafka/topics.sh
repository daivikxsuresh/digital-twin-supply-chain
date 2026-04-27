#!/bin/bash
# Creates all Kafka topics for the Digital Twin platform.
# Run after Kafka is healthy: docker exec dt_kafka bash /topics.sh

BROKER="localhost:9092"

topics=(
  "supply.orders"
  "supply.shipments"
  "supply.inventory"
  "supply.facilities"
  "supply.suppliers"
  "supply.events.dlq"
)

for topic in "${topics[@]}"; do
  kafka-topics --create \
    --bootstrap-server $BROKER \
    --replication-factor 1 \
    --partitions 3 \
    --topic "$topic" \
    --if-not-exists
  echo "Created topic: $topic"
done

echo "All topics created."

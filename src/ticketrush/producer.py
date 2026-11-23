from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from uuid import uuid4

from confluent_kafka import Producer


def publish_mock_purchase() -> None:
    bootstrap_servers = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9092",
    )

    producer = Producer(
        {
            "bootstrap.servers": bootstrap_servers,
            "acks": "all",
            "enable.idempotence": True,
        }
    )

    reservation_id = str(uuid4())

    event = {
        "event_id": str(uuid4()),
        "event_type": "ticket.purchased",
        "reservation_id": reservation_id,
        "customer_id": "customer-001",
        "seat_id": 42,
        "occurred_at": datetime.now(UTC).isoformat(),
    }

    delivery_errors: list[str] = []
    delivered = False

    def delivery_report(
        error: object,
        message: object,
    ) -> None:
        nonlocal delivered

        if error is not None:
            delivery_errors.append(str(error))
        else:
            delivered = True
            print(f"Delivery confirmed: {message}")

    producer.produce(
        topic="ticket-purchases",
        key=reservation_id.encode("utf-8"),
        value=json.dumps(event).encode("utf-8"),
        callback=delivery_report,
    )

    remaining = producer.flush(timeout=15)

    if remaining != 0 or delivery_errors or not delivered:
        raise RuntimeError(
            f"Kafka delivery not confirmed: {delivery_errors}"
        )

    print("Purchase event published successfully")


if __name__ == "__main__":
    publish_mock_purchase()
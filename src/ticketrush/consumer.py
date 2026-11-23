from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence

from confluent_kafka import Consumer, KafkaException, Message


def process_purchase(message: Message) -> None:
    raw_value = message.value()

    if raw_value is None:
        raise ValueError("Purchase event has no value")

    event = json.loads(raw_value.decode("utf-8"))

    print(
        f"Processing purchase: "
        f"event_id={event['event_id']} "
        f"seat_id={event['seat_id']} "
        f"customer_id={event['customer_id']}",
        flush=True,
    )

    print(
        "Simulated notification processed",
        flush=True,
    )


def consume(
    *,
    group_id: str,
    crash_before_commit: bool = False,
) -> None:
    bootstrap_servers = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9092",
    )

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )

    consumer.subscribe(["ticket-purchases"])

    print(
        f"Consumer started: group={group_id}",
        flush=True,
    )

    try:
        while True:
            message = consumer.poll(timeout=1.0)

            if message is None:
                continue

            if message.error():
                raise KafkaException(message.error())

            process_purchase(message)

            if crash_before_commit:
                print(
                    "SIMULATED CRASH BEFORE OFFSET COMMIT",
                    flush=True,
                )
                os._exit(1)

            # Commit the next offset after processing.
            consumer.commit(
                message=message,
                asynchronous=False,
            )

            print(
                f"Committed: partition={message.partition()} "
                f"offset={message.offset() + 1}",
                flush=True,
            )

    except KeyboardInterrupt:
        print("Consumer stopped", flush=True)

    finally:
        consumer.close()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--group",
        default="ticketrush-notifications",
    )

    parser.add_argument(
        "--crash-before-commit",
        action="store_true",
    )

    args = parser.parse_args(argv)

    consume(
        group_id=args.group,
        crash_before_commit=args.crash_before_commit,
    )


if __name__ == "__main__":
    main()
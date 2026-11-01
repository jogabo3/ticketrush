from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest

from ticketrush.reservation import (
    ReservationService,
    ReservationStatus,
)


@pytest.fixture
def database_url() -> str:
    value = os.getenv("TICKETRUSH_DATABASE_URL")

    if not value:
        pytest.skip("TICKETRUSH_DATABASE_URL is not configured")

    return value


@pytest.fixture
def available_seat(database_url: str) -> int:
    """Create isolated inventory for each test."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO concerts (
                    artist_name,
                    venue_name,
                    starts_at,
                    sale_starts_at
                )
                VALUES (
                    %s,
                    'Test Arena',
                    NOW() + INTERVAL '30 days',
                    NOW() - INTERVAL '1 hour'
                )
                RETURNING concert_id
                """,
                (f"Test Artist {uuid4()}",),
            )

            concert_row = cursor.fetchone()
            assert concert_row is not None

            cursor.execute(
                """
                INSERT INTO seats (
                    concert_id,
                    section,
                    row_label,
                    seat_number
                )
                VALUES (%s, 'TEST', 'A', 1)
                RETURNING seat_id
                """,
                (concert_row[0],),
            )

            seat_row = cursor.fetchone()
            assert seat_row is not None

            return int(seat_row[0])


def test_one_customer_can_reserve_seat(
    database_url: str,
    available_seat: int,
) -> None:
    service = ReservationService(database_url)

    result = service.reserve_seat(
        seat_id=available_seat,
        customer_id="customer-001",
    )

    assert result.status == ReservationStatus.RESERVED


def test_second_customer_cannot_reserve_same_seat(
    database_url: str,
    available_seat: int,
) -> None:
    service = ReservationService(database_url)

    first = service.reserve_seat(
        seat_id=available_seat,
        customer_id="customer-001",
    )

    second = service.reserve_seat(
        seat_id=available_seat,
        customer_id="customer-002",
    )

    assert first.status == ReservationStatus.RESERVED
    assert second.status == ReservationStatus.SEAT_UNAVAILABLE


def test_100_concurrent_customers_one_winner(
    database_url: str,
    available_seat: int,
) -> None:
    service = ReservationService(database_url)

    def attempt(customer_number: int) -> ReservationStatus:
        result = service.reserve_seat(
            seat_id=available_seat,
            customer_id=f"customer-{customer_number:03d}",
        )
        return result.status

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(attempt, range(100)))

    assert results.count(ReservationStatus.RESERVED) == 1
    assert (
        results.count(ReservationStatus.SEAT_UNAVAILABLE)
        == 99
    )

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, held_by
                FROM seats
                WHERE seat_id = %s
                """,
                (available_seat,),
            )

            row = cursor.fetchone()

    assert row is not None
    assert row[0] == "HELD"
    assert row[1] is not None
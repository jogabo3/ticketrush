from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest

from ticketrush.lifecycle import (
    HoldStatus,
    ReservationLifecycleService,
)


@pytest.fixture
def database_url() -> str:
    value = os.getenv("TICKETRUSH_DATABASE_URL")
    if not value:
        pytest.skip("TICKETRUSH_DATABASE_URL is not configured")
    return value


@pytest.fixture
def seat_id(database_url: str) -> int:
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
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
                    'Lifecycle Test Arena',
                    NOW() + INTERVAL '30 days',
                    NOW() - INTERVAL '1 hour'
                )
                RETURNING concert_id
                """,
            (f"Lifecycle Test {uuid4()}",),
        )
        concert = cursor.fetchone()
        assert concert is not None

        cursor.execute(
            """
                INSERT INTO seats (
                    concert_id, section, row_label, seat_number
                )
                VALUES (%s, 'TEST', 'A', 1)
                RETURNING seat_id
                """,
            (concert[0],),
        )
        seat = cursor.fetchone()
        assert seat is not None
        return int(seat[0])


def test_hold_creates_reservation(
    database_url: str,
    seat_id: int,
) -> None:
    service = ReservationLifecycleService(database_url)

    result = service.create_hold(
        seat_id=seat_id,
        customer_id="customer-A",
    )

    assert result.status == HoldStatus.HELD
    assert result.reservation_id is not None
    assert result.expires_at is not None


def test_second_customer_cannot_hold_seat(
    database_url: str,
    seat_id: int,
) -> None:
    service = ReservationLifecycleService(database_url)

    first = service.create_hold(
        seat_id=seat_id,
        customer_id="customer-A",
    )

    second = service.create_hold(
        seat_id=seat_id,
        customer_id="customer-B",
    )

    assert first.status == HoldStatus.HELD
    assert second.status == HoldStatus.UNAVAILABLE


def test_expired_hold_releases_seat(
    database_url: str,
    seat_id: int,
) -> None:
    service = ReservationLifecycleService(database_url)

    result = service.create_hold(
        seat_id=seat_id,
        customer_id="customer-A",
        duration=timedelta(milliseconds=100),
    )
    assert result.reservation_id is not None

    # Advance expiration deterministically in the test DB.
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                UPDATE reservations
                SET expires_at = clock_timestamp() - INTERVAL '1 second'
                WHERE reservation_id = %s
                """,
            (result.reservation_id,),
        )

    assert service.expire_hold(result.reservation_id) is True

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT status, current_reservation_id
                FROM seats
                WHERE seat_id = %s
                """,
            (seat_id,),
        )
        row = cursor.fetchone()

    assert row == ("AVAILABLE", None)


def test_old_expiration_cannot_release_new_hold(
    database_url: str,
    seat_id: int,
) -> None:
    service = ReservationLifecycleService(database_url)

    first = service.create_hold(
        seat_id=seat_id,
        customer_id="customer-A",
    )
    assert first.reservation_id is not None

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                UPDATE reservations
                SET expires_at = clock_timestamp() - INTERVAL '1 second'
                WHERE reservation_id = %s
                """,
            (first.reservation_id,),
        )

    assert service.expire_hold(first.reservation_id) is True

    second = service.create_hold(
        seat_id=seat_id,
        customer_id="customer-B",
    )
    assert second.reservation_id is not None

    # Stale worker retries expiration for Customer A.
    assert service.expire_hold(first.reservation_id) is False

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT status, current_reservation_id
                FROM seats
                WHERE seat_id = %s
                """,
            (seat_id,),
        )
        row = cursor.fetchone()

    assert row == ("HELD", second.reservation_id)
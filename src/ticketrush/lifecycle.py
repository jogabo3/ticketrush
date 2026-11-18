from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID, uuid4

import psycopg


class HoldStatus(StrEnum):
    HELD = "held"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class HoldResult:
    status: HoldStatus
    reservation_id: UUID | None
    seat_id: int
    expires_at: datetime | None


class ReservationLifecycleService:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def create_hold(
        self,
        *,
        seat_id: int,
        customer_id: str,
        duration: timedelta = timedelta(minutes=5),
    ) -> HoldResult:
        if duration <= timedelta(0):
            raise ValueError("Hold duration must be positive")

        reservation_id = uuid4()

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status
                    FROM seats
                    WHERE seat_id = %s
                    FOR UPDATE
                    """,
                    (seat_id,),
                )

                row = cursor.fetchone()

                if row is None or row[0] != "AVAILABLE":
                    return HoldResult(
                        status=HoldStatus.UNAVAILABLE,
                        reservation_id=None,
                        seat_id=seat_id,
                        expires_at=None,
                    )

                # Use database time for expiration decisions.
                cursor.execute("SELECT clock_timestamp()")
                time_row = cursor.fetchone()
                assert time_row is not None

                created_at = time_row[0]
                expires_at = created_at + duration

                cursor.execute(
                    """
                    INSERT INTO reservations (
                        reservation_id,
                        seat_id,
                        customer_id,
                        status,
                        created_at,
                        expires_at
                    )
                    VALUES (%s, %s, %s, 'HELD', %s, %s)
                    """,
                    (
                        reservation_id,
                        seat_id,
                        customer_id,
                        created_at,
                        expires_at,
                    ),
                )

                cursor.execute(
                    """
                    UPDATE seats
                    SET
                        status = 'HELD',
                        held_by = %s,
                        held_at = %s,
                        current_reservation_id = %s
                    WHERE seat_id = %s
                    """,
                    (
                        customer_id,
                        created_at,
                        reservation_id,
                        seat_id,
                    ),
                )

        return HoldResult(
            status=HoldStatus.HELD,
            reservation_id=reservation_id,
            seat_id=seat_id,
            expires_at=expires_at,
        )

    def expire_hold(self, reservation_id: UUID) -> bool:
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT seat_id
                    FROM reservations
                    WHERE reservation_id = %s
                    """,
                    (reservation_id,),
                )

                row = cursor.fetchone()
                if row is None:
                    return False

                seat_id = int(row[0])

                # Always lock the seat first, matching create_hold.
                cursor.execute(
                    """
                    SELECT seat_id
                    FROM seats
                    WHERE seat_id = %s
                    FOR UPDATE
                    """,
                    (seat_id,),
                )

                cursor.execute(
                    """
                    UPDATE reservations
                    SET status = 'EXPIRED'
                    WHERE reservation_id = %s
                      AND status = 'HELD'
                      AND expires_at <= clock_timestamp()
                    RETURNING reservation_id
                    """,
                    (reservation_id,),
                )

                if cursor.fetchone() is None:
                    return False

                cursor.execute(
                    """
                    UPDATE seats
                    SET
                        status = 'AVAILABLE',
                        held_by = NULL,
                        held_at = NULL,
                        current_reservation_id = NULL
                    WHERE seat_id = %s
                      AND status = 'HELD'
                      AND current_reservation_id = %s
                    """,
                    (seat_id, reservation_id),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "Reservation and seat ownership are inconsistent"
                    )

        return True
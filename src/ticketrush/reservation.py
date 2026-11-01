from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import psycopg


class ReservationStatus(StrEnum):
    RESERVED = "reserved"
    SEAT_UNAVAILABLE = "seat_unavailable"
    SEAT_NOT_FOUND = "seat_not_found"


@dataclass(frozen=True)
class ReservationResult:
    status: ReservationStatus
    seat_id: int
    customer_id: str


class ReservationService:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def reserve_seat(
        self,
        *,
        seat_id: int,
        customer_id: str,
    ) -> ReservationResult:
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE seats
                    SET
                        status = 'HELD',
                        held_by = %s,
                        held_at = NOW()
                    WHERE seat_id = %s
                      AND status = 'AVAILABLE'
                    RETURNING seat_id
                    """,
                    (customer_id, seat_id),
                )

                row = cursor.fetchone()

                if row is not None:
                    return ReservationResult(
                        status=ReservationStatus.RESERVED,
                        seat_id=seat_id,
                        customer_id=customer_id,
                    )

                cursor.execute(
                    """
                    SELECT 1
                    FROM seats
                    WHERE seat_id = %s
                    """,
                    (seat_id,),
                )

                exists = cursor.fetchone() is not None

                return ReservationResult(
                    status=(
                        ReservationStatus.SEAT_UNAVAILABLE
                        if exists
                        else ReservationStatus.SEAT_NOT_FOUND
                    ),
                    seat_id=seat_id,
                    customer_id=customer_id,
                )
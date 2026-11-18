CREATE TABLE IF NOT EXISTS reservations (
    reservation_id UUID PRIMARY KEY,
    seat_id BIGINT NOT NULL REFERENCES seats(seat_id),
    customer_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'HELD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT valid_reservation_status
        CHECK (status IN ('HELD', 'EXPIRED', 'SOLD')),

    CONSTRAINT valid_reservation_expiration
        CHECK (expires_at > created_at)
);

ALTER TABLE seats
    ADD COLUMN IF NOT EXISTS current_reservation_id UUID
    REFERENCES reservations(reservation_id);

CREATE UNIQUE INDEX IF NOT EXISTS
    one_active_reservation_per_seat
ON reservations(seat_id)
WHERE status = 'HELD';

CREATE INDEX IF NOT EXISTS
    idx_reservations_expiration
ON reservations(expires_at)
WHERE status = 'HELD';
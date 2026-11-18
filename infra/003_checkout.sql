CREATE TABLE IF NOT EXISTS purchases (
    purchase_id UUID PRIMARY KEY,
    reservation_id UUID NOT NULL UNIQUE
        REFERENCES reservations(reservation_id),
    seat_id BIGINT NOT NULL UNIQUE
        REFERENCES seats(seat_id),
    customer_id TEXT NOT NULL,
    purchased_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
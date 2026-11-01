CREATE TABLE IF NOT EXISTS concerts (
    concert_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    artist_name TEXT NOT NULL,
    venue_name TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    sale_starts_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS seats (
    seat_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    concert_id BIGINT NOT NULL
        REFERENCES concerts(concert_id),
    section TEXT NOT NULL,
    row_label TEXT NOT NULL,
    seat_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'AVAILABLE',
    held_by TEXT,
    held_at TIMESTAMPTZ,

    CONSTRAINT unique_concert_seat
        UNIQUE (
            concert_id,
            section,
            row_label,
            seat_number
        ),

    CONSTRAINT valid_seat_status
        CHECK (
            status IN ('AVAILABLE', 'HELD', 'SOLD')
        ),

    CONSTRAINT valid_hold_fields
        CHECK (
            (
                status = 'HELD'
                AND held_by IS NOT NULL
                AND held_at IS NOT NULL
            )
            OR (
                status IN ('AVAILABLE', 'SOLD')
                AND held_by IS NULL
                AND held_at IS NULL
            )
        )
);

INSERT INTO concerts (
    artist_name,
    venue_name,
    starts_at,
    sale_starts_at
)
VALUES (
    'The Midnight Circuit',
    'Capital Arena',
    '2026-12-12 20:00:00+00',
    '2026-11-01 10:00:00+00'
);

INSERT INTO seats (
    concert_id,
    section,
    row_label,
    seat_number
)
SELECT
    1,
    'FLOOR',
    'A',
    seat_number
FROM generate_series(1, 100) AS seat_number;

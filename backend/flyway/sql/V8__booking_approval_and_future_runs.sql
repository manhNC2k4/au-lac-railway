-- =========================================================================
-- V7 - Human-in-the-loop booking requests + rolling demo runs.
--
-- The previous demo seed contains one fixed run in June 2026.  This migration
-- keeps that historical scenario intact and adds runs dated from migration day
-- onward so the passenger search can exercise a realistic booking flow.
-- =========================================================================

CREATE TABLE booking_request (
    request_id VARCHAR(50) PRIMARY KEY,
    service_run_id VARCHAR(50) NOT NULL REFERENCES service_run(service_run_id),
    origin_station_id VARCHAR(20) NOT NULL REFERENCES station(station_id),
    dest_station_id VARCHAR(20) NOT NULL REFERENCES station(station_id),
    seat_class VARCHAR(20) NOT NULL,
    quantity INT NOT NULL DEFAULT 1 CHECK (quantity BETWEEN 1 AND 4),
    priority_passenger BOOLEAN NOT NULL DEFAULT FALSE,
    passenger_name VARCHAR(120),
    status VARCHAR(24) NOT NULL DEFAULT 'SUBMITTED',
    selected_candidate_id VARCHAR(50),
    hold_id VARCHAR(50) REFERENCES seat_hold(hold_id),
    booking_id VARCHAR(50) REFERENCES booking(booking_id),
    reject_code VARCHAR(50),
    reject_reason TEXT,
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    ready_for_review_at TIMESTAMP WITH TIME ZONE,
    approved_at TIMESTAMP WITH TIME ZONE,
    decided_by VARCHAR(100),
    selected_at TIMESTAMP WITH TIME ZONE,
    confirmed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '15 minutes'),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_booking_request_status CHECK (status IN (
        'SUBMITTED', 'AI_PROCESSING', 'PENDING_ADMIN', 'APPROVED',
        'REJECTED', 'EXPIRED', 'SELECTED', 'CONFIRMED'
    ))
);

CREATE TABLE booking_candidate (
    candidate_id VARCHAR(50) PRIMARY KEY,
    request_id VARCHAR(50) NOT NULL REFERENCES booking_request(request_id) ON DELETE CASCADE,
    offer_id VARCHAR(50) NOT NULL UNIQUE REFERENCES offer(offer_id),
    decision_record_id VARCHAR(50) REFERENCES decision_record(decision_id),
    rank INT NOT NULL CHECK (rank > 0),
    ai_recommended BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(24) NOT NULL DEFAULT 'AI_SUGGESTED',
    seat_plan JSONB NOT NULL,
    pricing JSONB NOT NULL,
    explanation TEXT,
    approved_price_vnd BIGINT,
    admin_note TEXT,
    approved_by VARCHAR(100),
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_booking_candidate_status CHECK (status IN (
        'AI_SUGGESTED', 'APPROVED', 'REJECTED', 'PRICE_OVERRIDDEN', 'SELECTED'
    )),
    UNIQUE (request_id, rank)
);

CREATE INDEX ix_booking_request_queue
    ON booking_request (status, submitted_at);
CREATE INDEX ix_booking_request_run
    ON booking_request (service_run_id, status);
CREATE INDEX ix_booking_candidate_request
    ON booking_candidate (request_id, status, rank);

-- Ensure the route topology exists. The old fixed seed had stations and a train,
-- but a fresh database did not have train_stop rows for passenger run matching.
INSERT INTO train_stop
    (train_id, station_id, stop_sequence, arrival_time, departure_time, dwell_seconds)
VALUES
    ('SE1', 'HNO', 1, NULL,       TIME '20:55', 0),
    ('SE1', 'NBI', 2, TIME '22:55', TIME '23:00', 300),
    ('SE1', 'THO', 3, TIME '00:05', TIME '00:12', 420),
    ('SE1', 'VIN', 4, TIME '02:20', TIME '02:27', 420),
    ('SE1', 'DHO', 5, TIME '06:15', TIME '06:22', 420),
    ('SE1', 'HUE', 6, TIME '09:40', TIME '09:47', 420),
    ('SE1', 'DNA', 7, TIME '12:05', TIME '12:12', 420),
    ('SE1', 'SGO', 8, TIME '05:45', NULL,          0)
ON CONFLICT (train_id, stop_sequence) DO UPDATE SET
    station_id = EXCLUDED.station_id,
    arrival_time = EXCLUDED.arrival_time,
    departure_time = EXCLUDED.departure_time,
    dwell_seconds = EXCLUDED.dwell_seconds;

-- Six sellable departures: today, the next three days, then day +5 and +7.
INSERT INTO service_run
    (service_run_id, train_id, service_date, direction, status, matrix_version)
SELECT
    'SE1_' || to_char(CURRENT_DATE + day_offset, 'YYYY-MM-DD') || '_LE',
    'SE1', CURRENT_DATE + day_offset, 'LE', 'ACTIVE', 1
FROM unnest(ARRAY[0, 1, 2, 3, 5, 7]) AS day_offset
ON CONFLICT (service_run_id) DO UPDATE SET status = 'ACTIVE';

-- 40 seats x 7 segments. Occupancy differs by departure day, while every run
-- keeps enough continuous inventory to generate three options for up to 4 pax.
INSERT INTO seat_segment_state
    (service_run_id, seat_id, segment_id, status, version)
SELECT
    sr.service_run_id,
    'C01-S' || lpad(seat_no::text, 3, '0'),
    segment_id,
    CASE
        WHEN seat_no <= 8 + (sr.service_date - CURRENT_DATE)
            THEN 'SOLD'
        WHEN seat_no BETWEEN 9 + (sr.service_date - CURRENT_DATE)
                         AND 14 + (sr.service_date - CURRENT_DATE)
             AND segment_id BETWEEN 2 AND 5
            THEN 'SOLD'
        ELSE 'FREE'
    END,
    1
FROM service_run sr
CROSS JOIN generate_series(1, 40) AS seat_no
CROSS JOIN generate_series(1, 7) AS segment_id
WHERE sr.service_run_id LIKE 'SE1_%_LE'
  AND sr.service_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
ON CONFLICT (service_run_id, seat_id, segment_id) DO NOTHING;

-- Fare products for every north-to-south O-D pair. The formula is deterministic
-- demo data: 45,000 VND boarding component + 650 VND/km, rounded to 1,000 VND.
INSERT INTO fare_product
    (service_run_id, origin_station_id, dest_station_id, seat_class, base_fare_vnd, version)
SELECT
    sr.service_run_id,
    origin.station_id,
    destination.station_id,
    'NGOI_MEM_DH',
    (round((45000 + (destination.ly_trinh_km - origin.ly_trinh_km) * 650) / 1000.0) * 1000)::BIGINT,
    1
FROM service_run sr
CROSS JOIN station origin
CROSS JOIN station destination
WHERE sr.service_run_id LIKE 'SE1_%_LE'
  AND sr.service_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
  AND origin.ly_trinh_km < destination.ly_trinh_km
ON CONFLICT (service_run_id, origin_station_id, dest_station_id, seat_class, version)
DO NOTHING;

-- Segment-level demand for allocation/bid-price cache. Higher near-term demand
-- makes the AI pricing and admin guardrail visible in the demo.
INSERT INTO demand_forecast
    (service_run_id, origin_station_id, dest_station_id, seat_class,
     forecast_demand, confidence_score, forecast_version)
SELECT
    sr.service_run_id,
    NULL,
    NULL,
    'NGOI_MEM_DH',
    GREATEST(8, 24 - (sr.service_date - CURRENT_DATE) - segment_id),
    0.82,
    1
FROM service_run sr
CROSS JOIN generate_series(1, 7) AS segment_id
WHERE sr.service_run_id LIKE 'SE1_%_LE'
  AND sr.service_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
  AND NOT EXISTS (
      SELECT 1 FROM demand_forecast existing
      WHERE existing.service_run_id = sr.service_run_id
        AND existing.seat_class = 'NGOI_MEM_DH'
        AND existing.forecast_version = 1
  );

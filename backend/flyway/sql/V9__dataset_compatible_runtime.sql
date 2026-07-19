-- =========================================================================
-- V8 - Runtime master/inventory contract aligned with v2-as-v1 input data.
-- Source files:
--   data/stations.csv
--   data/trains.csv (SE1 modal consist)
--   data/seat_inventory.csv (RUN:SE1:2026-06-30 reference profile)
--
-- Future runs are synthetic scenarios. Their structure is source-accurate and
-- their initial aggregate occupancy replays the last available SE1 snapshot.
-- =========================================================================

ALTER TABLE station ALTER COLUMN ly_trinh_km TYPE DECIMAL(8,1);
ALTER TABLE station
    ADD COLUMN station_type VARCHAR(30),
    ADD COLUMN dwell_minutes INT,
    ADD COLUMN province_2025 VARCHAR(100),
    ADD COLUMN effective_from DATE;

ALTER TABLE train
    ADD COLUMN direction VARCHAR(10),
    ADD COLUMN origin_station_id VARCHAR(20) REFERENCES station(station_id),
    ADD COLUMN dest_station_id VARCHAR(20) REFERENCES station(station_id),
    ADD COLUMN departure_time TIME,
    ADD COLUMN revenue_coefficient DECIMAL(5,3);

CREATE TABLE train_seat_class (
    train_id VARCHAR(20) NOT NULL REFERENCES train(train_id) ON DELETE CASCADE,
    seat_class VARCHAR(20) NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    source VARCHAR(100) NOT NULL,
    PRIMARY KEY (train_id, seat_class)
);

ALTER TABLE service_run
    ADD COLUMN model_run_id VARCHAR(80),
    ADD COLUMN data_source VARCHAR(30) NOT NULL DEFAULT 'LEGACY_DEMO',
    ADD COLUMN reference_run_id VARCHAR(80);

ALTER TABLE seat_segment_state
    ADD COLUMN seat_class VARCHAR(20),
    ADD COLUMN seat_index INT;
UPDATE seat_segment_state
   SET seat_class='NGOI_MEM_DH',
       seat_index=substring(seat_id from 'S([0-9]+)$')::INT - 1
 WHERE seat_class IS NULL;
ALTER TABLE seat_segment_state
    ALTER COLUMN seat_class SET NOT NULL,
    ALTER COLUMN seat_index SET NOT NULL;
ALTER TABLE seat_segment_state
    ADD CONSTRAINT ck_seat_index_nonnegative CHECK (seat_index >= 0),
    ADD CONSTRAINT uq_seat_index_segment
        UNIQUE (service_run_id, seat_class, seat_index, segment_id);
CREATE INDEX ix_seat_state_run_class
    ON seat_segment_state (service_run_id, seat_class, segment_id, status);

ALTER TABLE demand_forecast
    ADD COLUMN data_source VARCHAR(30) NOT NULL DEFAULT 'LEGACY_SEED',
    ADD COLUMN feature_snapshot JSONB;

-- Exact station master rows from data/stations.csv.
INSERT INTO station
    (station_id, station_name, ly_trinh_km, station_type, dwell_minutes,
     province_2025, effective_from)
VALUES
    ('HNO','Hà Nội',0.0,'dau_moi',20,'Hà Nội','2025-07-01'),
    ('PLY','Phủ Lý',56.0,'doc_duong',3,'Ninh Bình','2025-07-01'),
    ('NDI','Nam Định',87.0,'khu_doan',5,'Ninh Bình','2025-07-01'),
    ('NBI','Ninh Bình',115.0,'khu_doan',5,'Ninh Bình','2025-07-01'),
    ('BSO','Bỉm Sơn',138.0,'doc_duong',3,'Thanh Hóa','2025-07-01'),
    ('THO','Thanh Hóa',175.0,'khu_doan',7,'Thanh Hóa','2025-07-01'),
    ('VIN','Vinh',319.0,'khu_doan',10,'Nghệ An','2025-07-01'),
    ('YTR','Yên Trung',348.0,'doc_duong',3,'Hà Tĩnh','2025-07-01'),
    ('HPO','Hương Phố',410.0,'doc_duong',3,'Hà Tĩnh','2025-07-01'),
    ('DLE','Đồng Lê',460.0,'doc_duong',3,'Quảng Trị','2025-07-01'),
    ('DHO','Đồng Hới',522.0,'khu_doan',7,'Quảng Trị','2025-07-01'),
    ('DHA','Đông Hà',622.0,'khu_doan',5,'Quảng Trị','2025-07-01'),
    ('HUE','Huế',688.0,'khu_doan',10,'Huế','2025-07-01'),
    ('DNA','Đà Nẵng',791.4,'dau_moi',15,'Đà Nẵng','2025-07-01'),
    ('TKY','Tam Kỳ',865.0,'doc_duong',3,'Đà Nẵng','2025-07-01'),
    ('QNG','Quảng Ngãi',927.5,'khu_doan',7,'Quảng Ngãi','2025-07-01'),
    ('DTR','Diêu Trì',1095.0,'khu_doan',10,'Gia Lai','2025-07-01'),
    ('THA','Tuy Hòa',1198.0,'khu_doan',5,'Đắk Lắk','2025-07-01'),
    ('GIA','Giã',1258.0,'doc_duong',3,'Khánh Hòa','2025-07-01'),
    ('NTR','Nha Trang',1314.5,'dau_moi',12,'Khánh Hòa','2025-07-01'),
    ('TCH','Tháp Chàm',1408.0,'khu_doan',5,'Khánh Hòa','2025-07-01'),
    ('BTH','Bình Thuận',1551.0,'khu_doan',5,'Lâm Đồng','2025-07-01'),
    ('BHO','Biên Hòa',1697.0,'khu_doan',5,'Đồng Nai','2025-07-01'),
    ('DAN','Dĩ An',1707.0,'doc_duong',3,'TP. Hồ Chí Minh','2025-07-01'),
    ('SGO','Sài Gòn',1726.0,'dau_moi',20,'TP. Hồ Chí Minh','2025-07-01')
ON CONFLICT (station_id) DO UPDATE SET
    station_name=EXCLUDED.station_name,
    ly_trinh_km=EXCLUDED.ly_trinh_km,
    station_type=EXCLUDED.station_type,
    dwell_minutes=EXCLUDED.dwell_minutes,
    province_2025=EXCLUDED.province_2025,
    effective_from=EXCLUDED.effective_from;

-- Exact SE1 modal consist from data/trains.csv.
UPDATE train
   SET train_name='SE1', capacity=448, direction='LE',
       origin_station_id='HNO', dest_station_id='SGO',
       departure_time=TIME '21:45', revenue_coefficient=1.1
 WHERE train_id='SE1';

INSERT INTO train_seat_class (train_id, seat_class, capacity, source) VALUES
    ('SE1','NGOI_MEM_DH',168,'data/trains.csv'),
    ('SE1','NAM_K6',84,'data/trains.csv'),
    ('SE1','NAM_K4',196,'data/trains.csv')
ON CONFLICT (train_id, seat_class) DO UPDATE SET
    capacity=EXCLUDED.capacity, source=EXCLUDED.source;

-- SE1 uses all 25 stations in increasing kilometrage. Only departure time at
-- HNO exists in the compatibility input; unknown arrival/departure times stay NULL.
DELETE FROM train_stop WHERE train_id='SE1';
INSERT INTO train_stop
    (train_id, station_id, stop_sequence, arrival_time, departure_time, dwell_seconds)
SELECT 'SE1', station_id, row_number() OVER (ORDER BY ly_trinh_km), NULL,
       CASE WHEN station_id='HNO' THEN TIME '21:45' ELSE NULL END,
       dwell_minutes * 60
  FROM station
 ORDER BY ly_trinh_km;

CREATE TABLE inventory_reference_profile (
    reference_run_id VARCHAR(80) NOT NULL,
    seat_class VARCHAR(20) NOT NULL,
    segment_id INT NOT NULL,
    capacity INT NOT NULL,
    sold INT NOT NULL,
    PRIMARY KEY (reference_run_id, seat_class, segment_id)
);

-- Exact aggregate departure snapshot from data/seat_inventory.csv.
INSERT INTO inventory_reference_profile
    (reference_run_id, seat_class, segment_id, capacity, sold)
VALUES
    ('RUN:SE1:2026-06-30','NAM_K4',1,196,27),('RUN:SE1:2026-06-30','NAM_K6',1,84,16),('RUN:SE1:2026-06-30','NGOI_MEM_DH',1,168,41),
    ('RUN:SE1:2026-06-30','NAM_K4',2,196,44),('RUN:SE1:2026-06-30','NAM_K6',2,84,36),('RUN:SE1:2026-06-30','NGOI_MEM_DH',2,168,78),
    ('RUN:SE1:2026-06-30','NAM_K4',3,196,64),('RUN:SE1:2026-06-30','NAM_K6',3,84,62),('RUN:SE1:2026-06-30','NGOI_MEM_DH',3,168,97),
    ('RUN:SE1:2026-06-30','NAM_K4',4,196,71),('RUN:SE1:2026-06-30','NAM_K6',4,84,71),('RUN:SE1:2026-06-30','NGOI_MEM_DH',4,168,116),
    ('RUN:SE1:2026-06-30','NAM_K4',5,196,85),('RUN:SE1:2026-06-30','NAM_K6',5,84,81),('RUN:SE1:2026-06-30','NGOI_MEM_DH',5,168,124),
    ('RUN:SE1:2026-06-30','NAM_K4',6,196,94),('RUN:SE1:2026-06-30','NAM_K6',6,84,78),('RUN:SE1:2026-06-30','NGOI_MEM_DH',6,168,141),
    ('RUN:SE1:2026-06-30','NAM_K4',7,196,89),('RUN:SE1:2026-06-30','NAM_K6',7,84,80),('RUN:SE1:2026-06-30','NGOI_MEM_DH',7,168,143),
    ('RUN:SE1:2026-06-30','NAM_K4',8,196,92),('RUN:SE1:2026-06-30','NAM_K6',8,84,82),('RUN:SE1:2026-06-30','NGOI_MEM_DH',8,168,151),
    ('RUN:SE1:2026-06-30','NAM_K4',9,196,93),('RUN:SE1:2026-06-30','NAM_K6',9,84,82),('RUN:SE1:2026-06-30','NGOI_MEM_DH',9,168,151),
    ('RUN:SE1:2026-06-30','NAM_K4',10,196,92),('RUN:SE1:2026-06-30','NAM_K6',10,84,82),('RUN:SE1:2026-06-30','NGOI_MEM_DH',10,168,156),
    ('RUN:SE1:2026-06-30','NAM_K4',11,196,86),('RUN:SE1:2026-06-30','NAM_K6',11,84,84),('RUN:SE1:2026-06-30','NGOI_MEM_DH',11,168,143),
    ('RUN:SE1:2026-06-30','NAM_K4',12,196,80),('RUN:SE1:2026-06-30','NAM_K6',12,84,79),('RUN:SE1:2026-06-30','NGOI_MEM_DH',12,168,134),
    ('RUN:SE1:2026-06-30','NAM_K4',13,196,74),('RUN:SE1:2026-06-30','NAM_K6',13,84,74),('RUN:SE1:2026-06-30','NGOI_MEM_DH',13,168,122),
    ('RUN:SE1:2026-06-30','NAM_K4',14,196,68),('RUN:SE1:2026-06-30','NAM_K6',14,84,68),('RUN:SE1:2026-06-30','NGOI_MEM_DH',14,168,106),
    ('RUN:SE1:2026-06-30','NAM_K4',15,196,60),('RUN:SE1:2026-06-30','NAM_K6',15,84,61),('RUN:SE1:2026-06-30','NGOI_MEM_DH',15,168,99),
    ('RUN:SE1:2026-06-30','NAM_K4',16,196,54),('RUN:SE1:2026-06-30','NAM_K6',16,84,53),('RUN:SE1:2026-06-30','NGOI_MEM_DH',16,168,88),
    ('RUN:SE1:2026-06-30','NAM_K4',17,196,43),('RUN:SE1:2026-06-30','NAM_K6',17,84,49),('RUN:SE1:2026-06-30','NGOI_MEM_DH',17,168,78),
    ('RUN:SE1:2026-06-30','NAM_K4',18,196,39),('RUN:SE1:2026-06-30','NAM_K6',18,84,46),('RUN:SE1:2026-06-30','NGOI_MEM_DH',18,168,68),
    ('RUN:SE1:2026-06-30','NAM_K4',19,196,29),('RUN:SE1:2026-06-30','NAM_K6',19,84,43),('RUN:SE1:2026-06-30','NGOI_MEM_DH',19,168,57),
    ('RUN:SE1:2026-06-30','NAM_K4',20,196,24),('RUN:SE1:2026-06-30','NAM_K6',20,84,36),('RUN:SE1:2026-06-30','NGOI_MEM_DH',20,168,46),
    ('RUN:SE1:2026-06-30','NAM_K4',21,196,19),('RUN:SE1:2026-06-30','NAM_K6',21,84,29),('RUN:SE1:2026-06-30','NGOI_MEM_DH',21,168,36),
    ('RUN:SE1:2026-06-30','NAM_K4',22,196,17),('RUN:SE1:2026-06-30','NAM_K6',22,84,18),('RUN:SE1:2026-06-30','NGOI_MEM_DH',22,168,29),
    ('RUN:SE1:2026-06-30','NAM_K4',23,196,9),('RUN:SE1:2026-06-30','NAM_K6',23,84,13),('RUN:SE1:2026-06-30','NGOI_MEM_DH',23,168,18),
    ('RUN:SE1:2026-06-30','NAM_K4',24,196,4),('RUN:SE1:2026-06-30','NAM_K6',24,84,7),('RUN:SE1:2026-06-30','NGOI_MEM_DH',24,168,10);

-- Remove only unreferenced rolling runs created by V7's incompatible 40x7 seed.
DELETE FROM demand_forecast df USING service_run sr
 WHERE df.service_run_id=sr.service_run_id
   AND sr.service_run_id LIKE 'SE1_%_LE'
   AND sr.service_date >= DATE '2026-07-01';
DELETE FROM fare_product fp USING service_run sr
 WHERE fp.service_run_id=sr.service_run_id
   AND sr.service_run_id LIKE 'SE1_%_LE'
   AND sr.service_date >= DATE '2026-07-01';
DELETE FROM seat_segment_state sss USING service_run sr
 WHERE sss.service_run_id=sr.service_run_id
   AND sr.service_run_id LIKE 'SE1_%_LE'
   AND sr.service_date >= DATE '2026-07-01';
DELETE FROM service_run sr
 WHERE sr.service_run_id LIKE 'SE1_%_LE'
   AND sr.service_date >= DATE '2026-07-01'
   AND NOT EXISTS (SELECT 1 FROM booking_request br WHERE br.service_run_id=sr.service_run_id);

-- Local business date, independent of the Postgres container's UTC timezone.
INSERT INTO service_run
    (service_run_id, train_id, service_date, direction, status, matrix_version,
     model_run_id, data_source, reference_run_id)
SELECT
    'RUN:SE1:' || to_char(local_date + day_offset, 'YYYY-MM-DD'),
    'SE1', local_date + day_offset, 'LE', 'ACTIVE', 1,
    'RUN:SE1:' || to_char(local_date + day_offset, 'YYYY-MM-DD'),
    'MODEL_SIMULATION', 'RUN:SE1:2026-06-30'
FROM (SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::DATE AS local_date) d
CROSS JOIN unnest(ARRAY[0,1,2,3,5,7]) AS day_offset
ON CONFLICT (service_run_id) DO UPDATE SET
    status='ACTIVE', model_run_id=EXCLUDED.model_run_id,
    data_source=EXCLUDED.data_source, reference_run_id=EXCLUDED.reference_run_id;

-- Reconstruct deterministic seat-index matrices from the source aggregate profile.
INSERT INTO seat_segment_state
    (service_run_id, seat_id, segment_id, status, version, seat_class, seat_index)
SELECT
    sr.service_run_id,
    profile.seat_class || ':' || lpad(seat_idx::TEXT, 4, '0'),
    profile.segment_id,
    CASE WHEN seat_idx < profile.sold THEN 'SOLD' ELSE 'FREE' END,
    1,
    profile.seat_class,
    seat_idx
FROM service_run sr
JOIN inventory_reference_profile profile
  ON profile.reference_run_id=sr.reference_run_id
CROSS JOIN LATERAL generate_series(0, profile.capacity - 1) AS seat_idx
WHERE sr.data_source='MODEL_SIMULATION'
ON CONFLICT (service_run_id, seat_id, segment_id) DO NOTHING;

-- F0 comes from the same artifact formula as app.bt5_pricing.Pricer.f0.
INSERT INTO fare_product
    (service_run_id, origin_station_id, dest_station_id, seat_class, base_fare_vnd, version)
SELECT
    sr.service_run_id, origin.station_id, destination.station_id, cls.seat_class,
    round(1.1 * cls.class_factor * 1598.947872282371
          * power((destination.ly_trinh_km-origin.ly_trinh_km)::NUMERIC, 0.87))::BIGINT,
    1
FROM service_run sr
CROSS JOIN station origin
CROSS JOIN station destination
CROSS JOIN (VALUES
    ('NGOI_MEM_DH',1.000::NUMERIC),
    ('NAM_K6',1.215::NUMERIC),
    ('NAM_K4',1.462::NUMERIC)
) AS cls(seat_class,class_factor)
WHERE sr.data_source='MODEL_SIMULATION'
  AND origin.ly_trinh_km < destination.ly_trinh_km
ON CONFLICT (service_run_id, origin_station_id, dest_station_id, seat_class, version)
DO NOTHING;

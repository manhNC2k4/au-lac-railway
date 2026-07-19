-- =========================================================================
-- V9 - Derived physical layout for passenger seat-map UI.
--
-- The compatibility dataset explicitly drops physical seat identity and berth
-- tier. These rows therefore DO NOT change model seat_index or source facts.
-- They are a replaceable presentation mapping, marked DERIVED_UI_LAYOUT_V1.
-- =========================================================================

CREATE TABLE train_coach_layout (
    train_id VARCHAR(20) NOT NULL REFERENCES train(train_id) ON DELETE CASCADE,
    coach_number INT NOT NULL CHECK (coach_number > 0),
    coach_label VARCHAR(50) NOT NULL,
    seat_class VARCHAR(20) NOT NULL,
    layout_type VARCHAR(30) NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    display_order INT NOT NULL,
    data_source VARCHAR(40) NOT NULL,
    PRIMARY KEY (train_id, coach_number),
    UNIQUE (train_id, display_order)
);

CREATE TABLE train_seat_layout (
    train_id VARCHAR(20) NOT NULL,
    seat_class VARCHAR(20) NOT NULL,
    seat_index INT NOT NULL CHECK (seat_index >= 0),
    coach_number INT NOT NULL,
    seat_number INT NOT NULL CHECK (seat_number > 0),
    row_number INT NOT NULL CHECK (row_number > 0),
    column_code VARCHAR(10) NOT NULL,
    position_code VARCHAR(30) NOT NULL,
    compartment_number INT,
    berth_level VARCHAR(20),
    is_accessible BOOLEAN NOT NULL DEFAULT FALSE,
    data_source VARCHAR(40) NOT NULL,
    PRIMARY KEY (train_id, seat_class, seat_index),
    UNIQUE (train_id, coach_number, seat_number),
    FOREIGN KEY (train_id, coach_number)
        REFERENCES train_coach_layout(train_id, coach_number) ON DELETE CASCADE
);

INSERT INTO train_coach_layout
    (train_id, coach_number, coach_label, seat_class, layout_type,
     capacity, display_order, data_source)
VALUES
    ('SE1',1,'Toa 1','NGOI_MEM_DH','SEATED_2X2',56,1,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',2,'Toa 2','NGOI_MEM_DH','SEATED_2X2',56,2,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',3,'Toa 3','NGOI_MEM_DH','SEATED_2X2',56,3,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',4,'Toa 4','NAM_K6','SLEEPER_6',42,4,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',5,'Toa 5','NAM_K6','SLEEPER_6',42,5,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',6,'Toa 6','NAM_K4','SLEEPER_4',28,6,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',7,'Toa 7','NAM_K4','SLEEPER_4',28,7,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',8,'Toa 8','NAM_K4','SLEEPER_4',28,8,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',9,'Toa 9','NAM_K4','SLEEPER_4',28,9,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',10,'Toa 10','NAM_K4','SLEEPER_4',28,10,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',11,'Toa 11','NAM_K4','SLEEPER_4',28,11,'DERIVED_UI_LAYOUT_V1'),
    ('SE1',12,'Toa 12','NAM_K4','SLEEPER_4',28,12,'DERIVED_UI_LAYOUT_V1');

-- 168 seats: three 56-seat coaches, 14 rows, 2+2 across the aisle.
INSERT INTO train_seat_layout
    (train_id, seat_class, seat_index, coach_number, seat_number, row_number,
     column_code, position_code, is_accessible, data_source)
SELECT
    'SE1', 'NGOI_MEM_DH', seat_index,
    1 + seat_index / 56,
    1 + seat_index % 56,
    1 + (seat_index % 56) / 4,
    (ARRAY['A','B','C','D'])[1 + seat_index % 4],
    (ARRAY['WINDOW_LEFT','AISLE_LEFT','AISLE_RIGHT','WINDOW_RIGHT'])[1 + seat_index % 4],
    seat_index % 56 IN (0, 1, 2, 3),
    'DERIVED_UI_LAYOUT_V1'
FROM generate_series(0, 167) AS seat_index;

-- 84 berths: two 42-berth coaches, seven six-berth compartments.
INSERT INTO train_seat_layout
    (train_id, seat_class, seat_index, coach_number, seat_number, row_number,
     column_code, position_code, compartment_number, berth_level,
     is_accessible, data_source)
SELECT
    'SE1', 'NAM_K6', seat_index,
    4 + seat_index / 42,
    1 + seat_index % 42,
    1 + (seat_index % 42) / 6,
    CASE WHEN seat_index % 2 = 0 THEN 'L' ELSE 'R' END,
    CASE WHEN seat_index % 2 = 0 THEN 'LEFT' ELSE 'RIGHT' END,
    1 + (seat_index % 42) / 6,
    (ARRAY['LOWER','LOWER','MIDDLE','MIDDLE','UPPER','UPPER'])[1 + seat_index % 6],
    seat_index % 42 IN (0, 1),
    'DERIVED_UI_LAYOUT_V1'
FROM generate_series(0, 83) AS seat_index;

-- 196 berths: seven 28-berth coaches, seven four-berth compartments.
INSERT INTO train_seat_layout
    (train_id, seat_class, seat_index, coach_number, seat_number, row_number,
     column_code, position_code, compartment_number, berth_level,
     is_accessible, data_source)
SELECT
    'SE1', 'NAM_K4', seat_index,
    6 + seat_index / 28,
    1 + seat_index % 28,
    1 + (seat_index % 28) / 4,
    CASE WHEN seat_index % 2 = 0 THEN 'L' ELSE 'R' END,
    CASE WHEN seat_index % 2 = 0 THEN 'LEFT' ELSE 'RIGHT' END,
    1 + (seat_index % 28) / 4,
    (ARRAY['LOWER','LOWER','UPPER','UPPER'])[1 + seat_index % 4],
    seat_index % 28 IN (0, 1),
    'DERIVED_UI_LAYOUT_V1'
FROM generate_series(0, 195) AS seat_index;

CREATE INDEX ix_train_seat_layout_coach
    ON train_seat_layout (train_id, coach_number, seat_number);

-- =========================================================================
-- ÂU LẠC RAILWAY - DATABASE SCHEMA V1 (FULL SDD + CÁC KHUYẾN NGHỊ MỞ RỘNG)
-- =========================================================================

-- ---------------------------------------------------------
-- 1. HỆ THỐNG XÁC THỰC & PHÂN QUYỀN (AUTH)
-- ---------------------------------------------------------
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL, -- admin, revenue_manager, user
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE refresh_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- 2. DỮ LIỆU DANH MỤC (MASTER DATA & TARIFF)
-- ---------------------------------------------------------
CREATE TABLE station (
    station_id VARCHAR(20) PRIMARY KEY, -- vd: HNO, SGO
    station_name VARCHAR(100) NOT NULL,
    ly_trinh_km INT NOT NULL
);

CREATE TABLE train (
    train_id VARCHAR(20) PRIMARY KEY,
    train_name VARCHAR(100) NOT NULL,
    capacity INT NOT NULL
);

CREATE TABLE train_stop (
    id SERIAL PRIMARY KEY,
    train_id VARCHAR(20) REFERENCES train(train_id),
    station_id VARCHAR(20) REFERENCES station(station_id),
    stop_sequence INT NOT NULL,
    arrival_time TIME,             -- Đã bổ sung theo SDD Update
    departure_time TIME,
    dwell_seconds INT,
    UNIQUE (train_id, stop_sequence)
);

CREATE TABLE pricing_policy (
    policy_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    min_floor_vnd BIGINT NOT NULL,
    max_ceiling_vnd BIGINT NOT NULL,
    max_delta_percent DECIMAL(5,2),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE promotion (
    promo_id VARCHAR(50) PRIMARY KEY, -- Đã bổ sung theo SDD Update
    code VARCHAR(20) UNIQUE NOT NULL,
    discount_percent DECIMAL(5,2),
    discount_amount_vnd BIGINT,
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- ---------------------------------------------------------
-- 3. DỮ LIỆU CỐT LÕI VẬN HÀNH (CORE TRANSACTION)
-- ---------------------------------------------------------
CREATE TABLE service_run (
    service_run_id VARCHAR(50) PRIMARY KEY,
    train_id VARCHAR(20) REFERENCES train(train_id),
    service_date DATE NOT NULL,
    direction VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE'
);

CREATE TABLE seat_segment_state (
    id SERIAL PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    seat_id VARCHAR(20) NOT NULL,
    segment_id INT NOT NULL,
    status VARCHAR(20) NOT NULL, -- FREE, HELD, SOLD
    hold_id VARCHAR(50),
    hold_expires_at TIMESTAMP WITH TIME ZONE,
    version INT DEFAULT 1,
    UNIQUE (service_run_id, seat_id, segment_id)
);

CREATE TABLE fare_product (
    id SERIAL PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    origin_station_id VARCHAR(20) REFERENCES station(station_id),
    dest_station_id VARCHAR(20) REFERENCES station(station_id),
    seat_class VARCHAR(20) NOT NULL,
    base_fare_vnd BIGINT NOT NULL,
    version INT DEFAULT 1
);

CREATE TABLE offer (
    offer_id VARCHAR(50) PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    matrix_version INT,
    decision VARCHAR(20) NOT NULL,
    seat_plan JSONB,
    final_price_vnd BIGINT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE seat_hold (
    hold_id VARCHAR(50) PRIMARY KEY,
    offer_id VARCHAR(50) REFERENCES offer(offer_id),
    status VARCHAR(20) NOT NULL,
    idempotency_key VARCHAR(100) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE booking (
    booking_id VARCHAR(50) PRIMARY KEY,
    hold_id VARCHAR(50) REFERENCES seat_hold(hold_id),
    user_id UUID REFERENCES users(user_id),
    group_id UUID,                             -- Đã bổ sung (Group Seating)
    booking_channel VARCHAR(20) DEFAULT 'WEB', -- Đã bổ sung (WEB, APP, OTA)
    promo_id VARCHAR(50) REFERENCES promotion(promo_id),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE allocation_snapshot (
    id SERIAL PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    matrix_version INT NOT NULL,
    forecast_version INT NOT NULL,
    formula_version INT NOT NULL,
    leg_metrics JSONB NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- 4. BẢNG HỖ TRỢ AI, DATA WAREHOUSE & BACKGROUND WORKERS
-- ---------------------------------------------------------
CREATE TABLE demand_forecast (
    id SERIAL PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    origin_station_id VARCHAR(20) REFERENCES station(station_id),
    dest_station_id VARCHAR(20) REFERENCES station(station_id),
    seat_class VARCHAR(20) NOT NULL,
    forecast_demand INT NOT NULL,
    confidence_score DECIMAL(5,2),
    forecast_version INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bid_price (
    id SERIAL PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    segment_id INT NOT NULL,
    seat_class VARCHAR(20) NOT NULL,
    bid_price_vnd BIGINT NOT NULL,
    remaining_capacity INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE external_factor (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    station_id VARCHAR(20) REFERENCES station(station_id),
    weather_condition VARCHAR(50),
    local_events VARCHAR(255),
    competitor_price_vnd BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE forecast_observation (
    id SERIAL PRIMARY KEY,
    result_status VARCHAR(20),
    rejection_reason VARCHAR(100),
    quantity INT,
    days_to_departure INT,
    source VARCHAR(50),
    dedup_key VARCHAR(100) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE decision_record (
    decision_id VARCHAR(50) PRIMARY KEY,
    input_hash VARCHAR(255),
    versions JSONB,
    result VARCHAR(20) NOT NULL,
    base_fare_vnd BIGINT,
    ai_suggested_price_vnd BIGINT,
    final_price_vnd BIGINT,
    bid_price_total_vnd BIGINT,
    bid_price_breakdown JSONB,
    violations JSONB,
    audit_timeline JSONB,
    explanation_code VARCHAR(100),
    actor VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    old_value JSONB,
    new_value JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE waiting_list (
    waitlist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    origin_station_id VARCHAR(20) REFERENCES station(station_id),
    dest_station_id VARCHAR(20) REFERENCES station(station_id),
    seat_class VARCHAR(20) NOT NULL,
    priority_score INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE
);

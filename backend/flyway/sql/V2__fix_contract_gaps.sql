-- =========================================================================
-- V2 — Vá 3 lỗ hổng của V1 phát hiện khi review plan/API contract (17/07/2026)
-- 1) matrix_version toàn cục cho CAS  2) pricing_policy theo tỷ lệ F0
-- 3) CHECK/UNIQUE còn thiếu + version cho bid_price
-- =========================================================================

-- 1. matrix_version toàn cục: seat_segment_state.version là version TỪNG Ô;
--    POST /holds so `expected_matrix_version` với cột này và tăng nó
--    trong CÙNG transaction với UPDATE các cell.
ALTER TABLE service_run
    ADD COLUMN matrix_version INT NOT NULL DEFAULT 1;

-- 2. Sàn/trần là TỶ LỆ trên F0 của từng O-D (YAML §3: san=0.55, tran=1.60),
--    không phải số tuyệt đối chung cho mọi cự ly. Kèm policy_version để
--    offer.policy_version trace được về đúng bản policy.
ALTER TABLE pricing_policy
    ADD COLUMN floor_ratio   DECIMAL(4,2) NOT NULL DEFAULT 0.55,
    ADD COLUMN ceiling_ratio DECIMAL(4,2) NOT NULL DEFAULT 1.60,
    ADD COLUMN policy_version INT NOT NULL DEFAULT 1;
-- Xóa sàn/trần tuyệt đối để không tồn tại 2 nguồn chân lý
ALTER TABLE pricing_policy
    DROP COLUMN min_floor_vnd,
    DROP COLUMN max_ceiling_vnd;

-- 3a. Enum bằng CHECK — DB constraint rẻ hơn app code
ALTER TABLE seat_segment_state
    ADD CONSTRAINT ck_sss_status CHECK (status IN ('FREE', 'HELD', 'SOLD'));
ALTER TABLE seat_hold
    ADD CONSTRAINT ck_hold_status CHECK (status IN ('ACTIVE', 'CONFIRMED', 'EXPIRED', 'CANCELLED'));
ALTER TABLE offer
    ADD CONSTRAINT ck_offer_decision CHECK (decision IN ('ACCEPT', 'REJECT'));

-- 3b. Chống dữ liệu trùng: giá/forecast một phiên bản chỉ có một dòng
ALTER TABLE fare_product
    ADD CONSTRAINT uq_fare_product
    UNIQUE (service_run_id, origin_station_id, dest_station_id, seat_class, version);
ALTER TABLE demand_forecast
    ADD CONSTRAINT uq_demand_forecast
    UNIQUE (service_run_id, origin_station_id, dest_station_id, seat_class, forecast_version);

-- 3c. bid_price phải trace được về snapshot đã sinh ra nó (Final Review G14)
ALTER TABLE bid_price
    ADD COLUMN forecast_version INT,
    ADD COLUMN matrix_version   INT;

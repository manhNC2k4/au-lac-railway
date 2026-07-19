-- =========================================================================
-- Đề xuất giá vé theo chặng (price suggestion) — nhân viên duyệt/từ chối.
-- AI đề xuất mức giá điều chỉnh cho từng đoạn; điều độ viên (revenue_manager/
-- admin) ACCEPT -> áp vào fare_product của đoạn đó, hoặc REJECT. Trạng thái +
-- vết duyệt lưu ở đây; giá đề xuất được TÍNH LẠI lúc GET/decide (không tin client).
-- =========================================================================
CREATE TABLE price_suggestion (
    id SERIAL PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    segment_id INT NOT NULL,
    seat_class VARCHAR(20) NOT NULL,
    base_vnd BIGINT NOT NULL,
    suggested_vnd BIGINT NOT NULL,
    expected_gain_vnd BIGINT NOT NULL,   -- (suggested - base) * cầu dự báo còn lại
    multiplier DECIMAL(6,3) NOT NULL,
    explanation TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING / APPROVED / REJECTED
    decided_by VARCHAR(50),
    decided_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (service_run_id, segment_id, seat_class)
);

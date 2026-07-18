-- =========================================================================
-- V6 — Seed trực tiếp 3 kịch bản pain-point (thay cho golden-gap demo cũ):
--   Case 1: HNO->NBI (đoạn 1) — chặng ngắn bị "chặn" bởi áp lực HNO->VIN chặng dài;
--           model phải tính chi phí cơ hội (bid price DLP) rồi mới quyết định bán/giữ.
--   Case 2: NBI->VIN (đoạn 2+3) — chỉ còn đúng 1 ghế trống NBI->THO và 1 ghế
--           trống KHÁC THO->VIN => không ghế nào xuyên suốt => buộc đề xuất
--           ghép 2 vé đổi ghế tại THO (dwell 7' >= 5', hợp lệ), cần khách đồng ý.
--   Case 3: cùng route/đoạn 1 (HNO->NBI) ở các thời điểm khác nhau — vẫn còn
--           nhiều ghế trống (S026, S028..S040) để demo giá ĐỘNG (gia_cuoi_vnd)
--           tăng dần khi đặt live trên web, đối chiếu với giá PHẲNG gia_goc_vnd.
--
-- Ga/tuyến dùng lại đúng mạng 8 ga - 7 đoạn đã khóa cứng ở backend/src/forecast/network.py
-- (không có ga "Phủ Lý" trong mô hình gốc — dùng NBI/Ninh Bình làm chặng ngắn gần
-- Hà Nội thay thế, cùng vị trí vai trò trong câu chuyện pain-point).
--
-- Ghi trực tiếp vào Postgres để lên sẵn ngay sau `docker compose up`, không cần
-- gọi POST /demo/scenarios/{id}/reset trước. Idempotent theo service_run_id này
-- (DELETE rồi INSERT lại) — không đụng service_run_id khác nếu có.
-- =========================================================================

-- 0. Danh mục ga + tàu (ON CONFLICT DO UPDATE — vô hại nếu đã tồn tại từ reset_scenario).
INSERT INTO station (station_id, station_name, ly_trinh_km) VALUES
    ('HNO', 'Hà Nội', 0),
    ('NBI', 'Ninh Bình', 115),
    ('THO', 'Thanh Hóa', 175),
    ('VIN', 'Vinh', 319),
    ('DHO', 'Đồng Hới', 522),
    ('HUE', 'Huế', 688),
    ('DNA', 'Đà Nẵng', 791),
    ('SGO', 'Sài Gòn', 1726)
ON CONFLICT (station_id) DO UPDATE SET station_name = EXCLUDED.station_name, ly_trinh_km = EXCLUDED.ly_trinh_km;

INSERT INTO train (train_id, train_name, capacity) VALUES ('SE1', 'SE1', 40)
ON CONFLICT (train_id) DO NOTHING;

INSERT INTO service_run (service_run_id, train_id, service_date, direction, status, matrix_version)
VALUES ('SE1_2026-06-15_LE', 'SE1', DATE '2026-06-15', 'LE', 'ACTIVE', 1)
ON CONFLICT (service_run_id) DO UPDATE SET status = 'ACTIVE', matrix_version = 1;

-- 1. Dọn sạch dữ liệu vận hành cũ của đúng service_run_id này (thứ tự theo FK, giống reset_scenario()).
DELETE FROM booking WHERE hold_id IN (
    SELECT hold_id FROM seat_hold WHERE offer_id IN (
        SELECT offer_id FROM offer WHERE service_run_id = 'SE1_2026-06-15_LE'));
DELETE FROM seat_hold WHERE offer_id IN (SELECT offer_id FROM offer WHERE service_run_id = 'SE1_2026-06-15_LE');
DELETE FROM offer WHERE service_run_id = 'SE1_2026-06-15_LE';
DELETE FROM seat_segment_state WHERE service_run_id = 'SE1_2026-06-15_LE';
DELETE FROM waiting_list WHERE service_run_id = 'SE1_2026-06-15_LE';
DELETE FROM quota_version WHERE service_run_id = 'SE1_2026-06-15_LE';
DELETE FROM proposal_log WHERE service_run_id = 'SE1_2026-06-15_LE';
DELETE FROM fare_product WHERE service_run_id = 'SE1_2026-06-15_LE';
DELETE FROM demand_forecast WHERE service_run_id = 'SE1_2026-06-15_LE';

-- 2. Ma trận ghế: 40 ghế x 7 đoạn — pattern dựng đúng 3 case (xem seat_no ranges).
INSERT INTO seat_segment_state (service_run_id, seat_id, segment_id, status, version)
SELECT
    'SE1_2026-06-15_LE',
    'C01-S' || lpad(seat_no::text, 3, '0'),
    seg,
    CASE
        -- Seats 1-10: SOLD HNO->VIN (đoạn 1-3) — áp lực chặng dài "giữ chỗ" qua đoạn 1 (Case 1).
        WHEN seat_no BETWEEN 1 AND 10  THEN CASE WHEN seg BETWEEN 1 AND 3 THEN 'SOLD' ELSE 'FREE' END
        -- Seats 11-25: SOLD trọn tuyến HNO->SGO — cùng góp phần khan hiếm đoạn 1-3.
        WHEN seat_no BETWEEN 11 AND 25 THEN 'SOLD'
        -- Seat 26: CHỈ trống NBI->THO (đoạn 2) — "1 chỗ trống" đầu tiên của Case 2.
        WHEN seat_no = 26              THEN CASE WHEN seg <= 2 THEN 'FREE' ELSE 'SOLD' END
        -- Seat 27: CHỈ trống THO->VIN..SGO (đoạn 3-7) — "1 ghế khác trống" của Case 2.
        WHEN seat_no = 27              THEN CASE WHEN seg <= 2 THEN 'SOLD' ELSE 'FREE' END
        -- Seats 28-40: CHỈ trống HNO->NBI (đoạn 1) — kho để bán/demo giá động Case 1 & 3.
        ELSE                                 CASE WHEN seg = 1 THEN 'FREE' ELSE 'SOLD' END
    END,
    1
FROM generate_series(1, 40) AS seat_no
CROSS JOIN generate_series(1, 7) AS seg;

-- 3. Fare product (F0) cho đúng các O-D dùng trong 3 case (số liệu khớp backend/seed/fare_products.json).
INSERT INTO fare_product (service_run_id, origin_station_id, dest_station_id, seat_class, base_fare_vnd, version) VALUES
    ('SE1_2026-06-15_LE', 'HNO', 'NBI', 'NGOI_MEM_DH', 109000, 1),  -- Case 1 & 3
    ('SE1_2026-06-15_LE', 'HNO', 'VIN', 'NGOI_MEM_DH', 265000, 1),  -- tham chiếu chặng dài (narrative)
    ('SE1_2026-06-15_LE', 'NBI', 'THO', 'NGOI_MEM_DH',  62000, 1),  -- Case 2 (leg 1)
    ('SE1_2026-06-15_LE', 'THO', 'VIN', 'NGOI_MEM_DH', 133000, 1),  -- Case 2 (leg 2)
    ('SE1_2026-06-15_LE', 'NBI', 'VIN', 'NGOI_MEM_DH', 180000, 1);  -- Case 2 (yêu cầu thật của khách)

-- 4. Forecast theo đoạn (7 dòng, ĐÚNG THỨ TỰ segment_id 1..7 — allocation cache map theo row order).
INSERT INTO demand_forecast (service_run_id, seat_class, forecast_demand, confidence_score, forecast_version) VALUES
    ('SE1_2026-06-15_LE', 'NGOI_MEM_DH', 18, 0.74, 1),  -- đoạn 1: cầu(18) > cung còn lại(14) -> bid price > 0 (Case 1)
    ('SE1_2026-06-15_LE', 'NGOI_MEM_DH',  4, 0.74, 1),  -- đoạn 2: chỉ còn 1 chỗ (Case 2)
    ('SE1_2026-06-15_LE', 'NGOI_MEM_DH',  4, 0.74, 1),  -- đoạn 3: chỉ còn 1 chỗ (Case 2)
    ('SE1_2026-06-15_LE', 'NGOI_MEM_DH',  4, 0.74, 1),  -- đoạn 4: dư chỗ, không dùng trong 3 case
    ('SE1_2026-06-15_LE', 'NGOI_MEM_DH',  4, 0.74, 1),  -- đoạn 5
    ('SE1_2026-06-15_LE', 'NGOI_MEM_DH',  4, 0.74, 1),  -- đoạn 6
    ('SE1_2026-06-15_LE', 'NGOI_MEM_DH',  4, 0.74, 1);  -- đoạn 7

-- 5. Pricing policy — chỉ chèn nếu CHƯA có policy nào active (bảng này dùng chung
--    toàn hệ thống, không scope theo service_run_id — xem routes_offers.py).
INSERT INTO pricing_policy (name, max_delta_percent, is_active, floor_ratio, ceiling_ratio, policy_version)
SELECT 'SE1_2026-06-15_LE_policy', 5.00, TRUE, 0.55, 1.60, 1
WHERE NOT EXISTS (SELECT 1 FROM pricing_policy WHERE is_active = TRUE);

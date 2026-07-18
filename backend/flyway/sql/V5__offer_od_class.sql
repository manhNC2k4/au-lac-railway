-- =========================================================================
-- V5 — P7.6: `offer` chưa lưu O-D/seat_class riêng (chỉ có trong `seat_plan` JSONB
-- dạng seat_id+segment, không phải origin/dest station). Manual override cần tra
-- ĐÚNG fare_product (origin, dest, seat_class) để tính lại dải guardrail — không
-- thể suy ngược O-D thật từ segment_from/segment_to khi ghép nhiều ghế (P5).
-- =========================================================================
ALTER TABLE offer
    ADD COLUMN origin_station_id VARCHAR(20),
    ADD COLUMN dest_station_id VARCHAR(20),
    ADD COLUMN seat_class VARCHAR(20);

-- =========================================================================
-- V4 — P7.3 (C5 hàng chờ thông minh): waiting_list thiếu cột cho vòng đời
-- khớp/hold tạm + loại trừ hành khách ưu tiên khỏi ghép nhiều ghế (bất biến
-- chung toàn hệ thống, xem merging/resolver.py::best_multiseat).
-- =========================================================================
ALTER TABLE waiting_list
    ADD COLUMN priority_passenger BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN quantity INT NOT NULL DEFAULT 1,
    ADD COLUMN matched_hold_id VARCHAR(50);

ALTER TABLE waiting_list
    ADD CONSTRAINT ck_waiting_list_status CHECK (status IN ('PENDING', 'MATCHED', 'EXPIRED', 'CANCELLED'));

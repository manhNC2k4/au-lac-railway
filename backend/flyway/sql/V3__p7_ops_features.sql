-- =========================================================================
-- V3 — P7 (MODEL_BASE_INTEGRATION_PLAN §P7): tính năng vận hành
-- 1) proposal_log: persist mọi ProposalLog (_log) từ quote/realloc/merge/group/waitlist
-- 2) quota_version: version hoá đề xuất hạn mức (P7.2) để duyệt/rollback
-- =========================================================================

CREATE TABLE proposal_log (
    id SERIAL PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    loai VARCHAR(20) NOT NULL,     -- FORECAST | ALLOCATION | MERGE | PRICE | RELEASE | GROUP | WAITLIST | OVERRIDE
    input JSONB,
    output JSONB,
    explain TEXT,
    model_version VARCHAR(20),
    actor VARCHAR(50) NOT NULL DEFAULT 'system',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quota đề xuất (P7.2, app.reallocation) theo (service_run_id, version) — mỗi bản là
-- toàn bộ QuotaRow[] mới nhất tại thời điểm đề xuất; duyệt = ACTIVE, rollback = tái
-- kích hoạt bản cũ (đặt lại ACTIVE, bản đang ACTIVE hiện tại lùi về ROLLED_BACK).
CREATE TABLE quota_version (
    id SERIAL PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    version INT NOT NULL,
    quota JSONB NOT NULL,          -- QuotaRow[] (khu_gian_id, loai_hanh_trinh, seat_class, quota, booking_limit, bid_price)
    proposal JSONB,                -- diff vs bản trước: [{khu_gian_id, loai_hanh_trinh, seat_class, action, limit_cu, limit_moi}]
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    decided_by VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT ck_quota_status CHECK (status IN ('PENDING', 'ACTIVE', 'REJECTED', 'ROLLED_BACK')),
    UNIQUE (service_run_id, version)
);

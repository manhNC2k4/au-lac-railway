# -*- coding: utf-8 -*-
"""Pydantic request models — khớp openapi.yaml components.schemas."""
from pydantic import BaseModel, Field


class ResetRequest(BaseModel):
    reset_clock: bool = True
    apply_golden_gap: bool = True


class OfferRequest(BaseModel):
    service_run_id: str
    origin_station_id: str
    dest_station_id: str
    seat_class: str
    quantity: int = Field(ge=1)
    priority_passenger: bool = False  # cao tuổi/khuyết tật/trẻ đi một mình -> không bao giờ đổi ghế (P5)


class BookingRequestCreate(OfferRequest):
    """Yeu cau tim ghe/gia can revenue manager duyet truoc khi hien cho khach."""
    quantity: int = Field(ge=1, le=4, default=1)
    passenger_name: str | None = Field(default=None, max_length=120)


class CandidateApproval(BaseModel):
    candidate_id: str
    override_price_vnd: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=500)


class BookingApprovalRequest(BaseModel):
    decided_by: str = Field(default="revenue_manager", min_length=2, max_length=100)
    approved_candidates: list[CandidateApproval] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=1000)


class BookingRejectRequest(BaseModel):
    decided_by: str = Field(default="revenue_manager", min_length=2, max_length=100)
    reason: str = Field(min_length=3, max_length=1000)


class BookingSeatSelectionRequest(BaseModel):
    candidate_id: str
    seat_ids: list[str] = Field(min_length=1, max_length=4)


class HoldRequest(BaseModel):
    offer_id: str
    expected_matrix_version: int
    passenger_name: str | None = None
    consent: bool = False  # bắt buộc =True khi offer.requires_customer_consent (ghép nhiều ghế, P5)


class OverrideRequest(BaseModel):
    """P7.6 — ghi đè giá thủ công TRONG sàn-trần. Vai trò kiểm qua header `X-Actor-Role`."""
    new_price_vnd: int = Field(gt=0)
    reason: str
    decided_by: str = "revenue_manager"


class AllocationDecisionRequest(BaseModel):
    """P7.2 — approve/reject/rollback một bản quota_version. Vai trò kiểm qua header
    `X-Actor-Role` (xem `api/deps.py::require_approver_role`), `decided_by` chỉ là tên
    hiển thị trong audit log."""
    decided_by: str = "revenue_manager"


class WaitlistAddRequest(BaseModel):
    """P7.3 (C5 hàng chờ) — khách chủ động vào hàng chờ sau khi /offers trả
    NO_SAME_SEAT_OPTION (không tự động thêm — cần khách đồng ý chờ)."""
    service_run_id: str
    origin_station_id: str
    dest_station_id: str
    seat_class: str
    quantity: int = Field(ge=1, default=1)
    u: float = Field(ge=0, default=14.0)  # nguồn: 4 (app.config.U_FORECAST — mốc dự báo 14 ngày)
    priority_passenger: bool = False
    csxh_doi_tuong: str = "KHONG"


class GroupQuoteRequest(BaseModel):
    """P7.4 (C4 xếp nhóm) — đề xuất ghế cho nhóm/gia đình, thuần đề xuất (không giữ ghế)."""
    service_run_id: str
    origin_station_id: str
    dest_station_id: str
    seat_class: str
    n_khach: int = Field(ge=2)  # =1 thì dùng /offers bình thường, không cần xếp nhóm

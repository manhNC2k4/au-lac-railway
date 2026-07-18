# -*- coding: utf-8 -*-
"""Lỗi domain — map 1-1 sang error_code trong docs/API_Contract.md §1."""


class DomainError(Exception):
    error_code = "UNKNOWN"
    http_status = 500

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NoSameSeatOption(DomainError):
    error_code = "NO_SAME_SEAT_OPTION"
    http_status = 422


class SoldOutTrue(DomainError):
    error_code = "SOLD_OUT_TRUE"
    http_status = 422


class AllocationRejected(DomainError):
    error_code = "ALLOCATION_REJECTED"
    http_status = 422


class StaleSnapshot(DomainError):
    error_code = "STALE_SNAPSHOT"
    http_status = 409


class SeatConflict(DomainError):
    error_code = "SEAT_CONFLICT"
    http_status = 409


class OfferExpired(DomainError):
    error_code = "OFFER_EXPIRED"
    http_status = 410


class HoldExpired(DomainError):
    error_code = "HOLD_EXPIRED"
    http_status = 410


class PolicyUnavailable(DomainError):
    error_code = "POLICY_UNAVAILABLE"
    http_status = 503


class ConsentRequired(DomainError):
    """Ghép nhiều ghế (P5) — khách phải xác nhận đồng ý đổi chỗ trước khi /holds."""
    error_code = "CONSENT_REQUIRED"
    http_status = 422


class GuardrailViolation(DomainError):
    """P7.6 — manual override yêu cầu giá ngoài dải [floor_ratio, ceiling_ratio]·F0.
    Bất biến "không bao giờ tự định giá ngoài dải đã duyệt" áp dụng CẢ cho override
    thủ công, không chỉ engine tự động."""
    error_code = "GUARDRAIL_VIOLATION"
    http_status = 422


class Forbidden(DomainError):
    """P7.2/P7.6 — role không đủ quyền duyệt/ghi đè (kiểm qua header `X-Actor-Role`).

    ponytail: đây LÀ header check thô, KHÔNG phải RBAC thật (không JWT/session, không
    xác thực danh tính) — chỉ đủ để demo quy trình "cần role revenue_manager/admin mới
    được duyệt". RBAC thật (đăng nhập, token, gắn với bảng `users` có sẵn) là việc lớn
    hơn, ngoài phạm vi P7."""
    error_code = "FORBIDDEN"
    http_status = 403

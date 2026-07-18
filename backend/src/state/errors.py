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

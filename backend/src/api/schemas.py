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


class HoldRequest(BaseModel):
    offer_id: str
    expected_matrix_version: int
    passenger_name: str | None = None
    consent: bool = False  # bắt buộc =True khi offer.requires_customer_consent (ghép nhiều ghế, P5)

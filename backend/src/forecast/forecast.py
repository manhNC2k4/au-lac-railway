# -*- coding: utf-8 -*-
"""Forecast per-segment — schema `seed/forecast.json` (khóa cùng BE1, DEV2 §H0-H2).

Schema (freeze BE2, versioned, đọc bởi `POST /demo/forecasts/refresh`):
    {
      "forecast_version": int,
      "service_run_id": str,
      "che_do_gia": "AI" | "LUAT",
      "days_to_departure": float,
      "segments": [
        {"segment_id": int, "forecast_remaining": float, "confidence": float}, ...
      ]
    }

P4 (MODEL_BASE_INTEGRATION_PLAN §P4): cơ chế update = `app.bt1_forecast.DemandModel.update`
(unconstrain pickup `sold/F(u)`, blend `BLEND_W` với một "tổng kỳ vọng" — F(u) là booking
curve THẬT từ `models/artifacts/bt1_booking_curves.json`, không còn `pickup_fraction`/
`DEFAULT_TARGET_LOAD_FACTOR` hand-tuned cũ). "Tổng kỳ vọng" dùng SEED forecast đã hiệu chuẩn
P1 (`backend/seed/forecast.json`) làm anchor — KHÔNG gọi thẳng `DemandModel.total()` (model
HGB train trên 22 ga/448 chỗ, khác grain golden 8 ga/40 chỗ) — trung thực đúng plan §P4.2:
DemandModel cấp CƠ CHẾ update/divergence, số tuyệt đối golden vẫn neo vào seed hiệu chuẩn.
"""
import json
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:          # `app/` package sống ở repo root, ngoài backend/
    sys.path.insert(0, str(REPO_ROOT))

from app.config import BAND_EDGES, BAND_LABELS  # noqa: E402 — sau khi chỉnh sys.path

from .network import LEG_DISTANCE_KM

_logger = logging.getLogger(__name__)

SEED_FORECAST_PATH = BACKEND_ROOT / "seed" / "forecast.json"
CURVES_PATH = REPO_ROOT / "models" / "artifacts" / "bt1_booking_curves.json"

BLEND_W = 0.5  # app.bt1_forecast.DemandModel.BLEND_W — cùng hệ số, một nguồn


def _load_curves(path: Path = CURVES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_seed_totals(path: Path = SEED_FORECAST_PATH) -> dict[int, float]:
    """Anchor "tổng kỳ vọng" per-segment = sold-tại-seed-time + forecast_remaining hiệu
    chuẩn P1 tại thời điểm seed — cố định, không đổi giữa các lần refresh."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for seg in doc["segments"]:
        sold_at_seed = 40 - seg["remaining_capacity"]  # nguồn: seed 40 ghế NGOI_MEM_DH (golden spec)
        out[seg["segment_id"]] = sold_at_seed + seg["forecast_remaining_demand"]
    return out


_CURVES = _load_curves()
_SEED_TOTALS = _load_seed_totals()


def _band(d_km: float) -> str:
    for i in range(len(BAND_LABELS)):
        if d_km <= BAND_EDGES[i + 1]:
            return BAND_LABELS[i]
    return BAND_LABELS[-1]


def _F(band: str, is_tet: bool, u: float) -> float:
    """Booking curve F(u) thật (app.bt1_forecast.DemandModel._F, cùng artifact)."""
    curves = _CURVES["curves"]
    F = curves.get(f"{band}|{int(is_tet)}") or curves.get(f"trung|{int(is_tet)}")
    ui = min(max(int(round(u)), 0), len(F) - 1)
    return max(F[ui], 1e-4)


def compute_forecast(sold_by_segment: dict[int, int], capacity_by_segment: dict[int, int],
                      days_to_departure: float, forecast_version: int, service_run_id: str,
                      che_do_gia: str = "AI", tet_window: bool = False) -> dict:
    segments = []
    for seg_id in sorted(capacity_by_segment):
        sold = sold_by_segment.get(seg_id, 0)
        band = _band(LEG_DISTANCE_KM.get(seg_id, 0.0))
        F = _F(band, tet_window, days_to_departure)
        tot_seed = _SEED_TOTALS.get(seg_id, capacity_by_segment[seg_id])
        tot_pickup = sold / F
        total = (1 - BLEND_W) * tot_seed + BLEND_W * tot_pickup
        remaining = max(total - sold, 0.0)
        confidence = round(0.5 + 0.5 * F, 2)
        segments.append({"segment_id": seg_id, "forecast_remaining": round(remaining, 1),
                         "confidence": confidence})
    return {
        "forecast_version": forecast_version,
        "service_run_id": service_run_id,
        "che_do_gia": che_do_gia,
        "days_to_departure": days_to_departure,
        "segments": segments,
    }


def refresh_forecast(prev_forecast: dict, sold_by_segment: dict[int, int],
                     capacity_by_segment: dict[int, int], days_to_departure: float,
                     **kw) -> dict:
    """Logic của `POST /demo/forecasts/refresh` (route: BE1 trong src/api/) — DEV2 §Bạn sở hữu.
    Tính lại forecast từ trạng thái hiện tại, BUMP `forecast_version` (+1) so với bản trước.
    Giữ nguyên `service_run_id`/`che_do_gia` của bản trước nếu bên gọi không override —
    bất biến trung tâm (Master §7.1): một offer dùng cùng bộ version, refresh chỉ tạo bản MỚI.

    Ghi divergence log per-segment (P4 — tín hiệu bán chậm/nhanh hơn kỳ vọng, `app.bt1_forecast
    .DemandModel.divergence` cùng công thức, anchor = seed thay vì HGB — xem module docstring)."""
    kw.setdefault("service_run_id", prev_forecast["service_run_id"])
    kw.setdefault("che_do_gia", prev_forecast.get("che_do_gia", "AI"))
    new = compute_forecast(sold_by_segment, capacity_by_segment, days_to_departure,
                           forecast_version=prev_forecast["forecast_version"] + 1, **kw)
    for seg_id, sold in sold_by_segment.items():
        tot_seed = _SEED_TOTALS.get(seg_id)
        if tot_seed is None:
            continue
        band = _band(LEG_DISTANCE_KM.get(seg_id, 0.0))
        F = _F(band, kw.get("tet_window", False), days_to_departure)
        expected = tot_seed * F
        divergence = (sold - expected) / max(expected, 1e-6)
        _logger.info("forecast divergence seg=%s u=%.0f expected=%.1f actual=%s divergence=%+.0f%%",
                    seg_id, days_to_departure, expected, sold, divergence * 100)
    return new

# -*- coding: utf-8 -*-
"""Backtest engine — baseline B0 vs Âu Lạc trên cùng event stream (DEV2 §H6-H10).

`_default_fare_fn`/`fixed_fare` là fallback khi không truyền `fare_fn` (test allocation
thuần, cô lập biến ALLOCATION). Evidence runner thật dùng `make_priced_fare_fns()` (P6):
baseline B0 bán giá niêm yết F0, Âu Lạc bán giá `PricingEngine` v2 elasticity thật (P3).

Baseline B0 = "FCFS, không tái sử dụng gap": một ghế đã có BẤT KỲ booking nào coi
như bị loại khỏi kho ghế còn "trinh nguyên" (virgin) — baseline chỉ bán được ghế
virgin. Đây là mô hình hoá tối giản cho hệ thống vé truyền thống không hỗ trợ bán
lại đoạn trống giữa hai vé trên cùng một ghế — đúng cơ chế mà golden scenario
(§1 Master Plan) muốn chứng minh Âu Lạc vượt qua.
Âu Lạc = tìm ghế trống liên tục thật (SegmentSeatMatrix.first_fit), có gate
guardrail: chỉ nhận nếu giá đề xuất >= tổng bid-price các leg (bid = công thức
scarcity đóng offline, xem `make_priced_fare_fns` docstring).
"""
import hashlib
import json
import statistics
from dataclasses import dataclass, field

import numpy as np

from src.forecast import bid_price, forecast, network
from src.backtest.seat_matrix import SegmentSeatMatrix

# --- golden pre-state (§1 Master Plan) — cố định, dùng riêng cho test golden request,
# KHÔNG dùng làm state khởi đầu của backtest 5-seed (xem run_seed: bắt đầu trống) ---
GOLDEN_SEAT_IDX = 16  # C01-S017 (S001=idx0 .. S040=idx39)
FULL_BOOKED_SEATS = 39  # toàn bộ 39 ghế còn lại đã bán trọn — đúng "quota" khiến baseline hết ghế trinh nguyên


def fixed_fare(distance_km: float) -> int:
    return bid_price.round_to_1k(bid_price.REFERENCE_YIELD_PER_KM_VND * distance_km)


class BaselineQuota:
    """'Ghế trinh nguyên' — không tái sử dụng gap. Xem docstring module."""

    def __init__(self, n_seats: int = network.N_SEATS):
        self.n_seats = n_seats
        self.touched = np.zeros(n_seats, dtype=bool)

    def request(self, segment_from: int, segment_to: int, quantity: int = 1) -> bool:
        free_idx = np.flatnonzero(~self.touched)
        if free_idx.size < quantity:
            return False
        self.touched[free_idx[:quantity]] = True
        return True

    def remaining_capacity(self, segment_id: int) -> int:
        return int((~self.touched).sum())


def build_golden_state() -> tuple[BaselineQuota, SegmentSeatMatrix]:
    """39 ghế khác: FULL_BOOKED_SEATS đã bán trọn HNO-SGO, phần còn lại "trinh nguyên".
    Ghế C01-S017: bán 1..2 (HNO-THO) + 5..7 (DHO-SGO), TRỐNG 3..4 — golden gap."""
    baseline = BaselineQuota()
    aulac = SegmentSeatMatrix(network.N_SEATS, network.N_SEGMENTS)
    full_booked = [i for i in range(network.N_SEATS) if i != GOLDEN_SEAT_IDX][:FULL_BOOKED_SEATS]
    for idx in full_booked:
        aulac._m[idx, :] = 1  # DA_BAN trọn hành trình HNO-SGO
        baseline.touched[idx] = True
    aulac._m[GOLDEN_SEAT_IDX, 0:2] = 1   # segments 1..2 (HNO-THO)
    aulac._m[GOLDEN_SEAT_IDX, 4:7] = 1   # segments 5..7 (DHO-SGO) — 3..4 (0-based cols 2:4) TRỐNG
    baseline.touched[GOLDEN_SEAT_IDX] = True
    return baseline, aulac


@dataclass
class RequestResult:
    request_id: str
    accepted: bool
    revenue_vnd: int = 0
    distance_km: float = 0.0


def _forecast_snapshot(matrix: SegmentSeatMatrix, days_to_departure: float) -> dict[int, float]:
    sold = {s: network.N_SEATS - matrix.remaining_capacity(s) for s in network.all_segment_ids()}
    capacity = {s: network.N_SEATS for s in network.all_segment_ids()}
    fc = forecast.compute_forecast(sold, capacity, days_to_departure, forecast_version=1,
                                    service_run_id=network.SERVICE_RUN_ID)
    return {seg["segment_id"]: seg["forecast_remaining"] for seg in fc["segments"]}


def _default_fare_fn(e: dict, bid_total: int = 0, lf_max: float = 1.0) -> int:
    return fixed_fare(e["distance_km"])


def make_priced_fare_fns(seed_dir=None):
    """P6 (MODEL_BASE_INTEGRATION_PLAN §P6): baseline B0 bán GIÁ NIÊM YẾT (F0 fare
    product); Âu Lạc bán giá `PricingEngine` v2 (P3) — elasticity optimizer thật
    (`app.elasticity.Elasticity`, cùng artifact/hệ số dùng ở `/offers` sống), gate
    bằng bid_total = công thức scarcity đóng (`forecast/bid_price.py` — xấp xỉ offline
    replay riêng, KHÔNG phải DLP dual `app.bt3_allocation`: LP solve mỗi request ×
    ~2000 event/backtest không khả thi trong NFR + DLP cache của P2 gắn với Postgres
    snapshot theo version, không có state khớp cho backtest in-memory; xem CLAUDE.md
    "bid_price.py ... still backs the offline backtest replay only"). Interface
    accept/reject + revenue giữ nguyên.
    """
    from src.pricing.context import PricingContext
    from src.pricing.engine import PricingEngine        # import trước — tự chỉnh sys.path cho `app.*`
    from app.elasticity import Elasticity

    sd = seed_dir or (Path(__file__).resolve().parents[2] / "seed")
    products = json.loads((sd / "fare_products.json").read_text(encoding="utf-8"))["products"]
    f0 = {(p["origin_station_id"], p["dest_station_id"]): int(p["gia_goc_vnd"]) for p in products}
    policy = json.loads((sd / "pricing_policy.json").read_text(encoding="utf-8"))
    engine_ = PricingEngine({"floor_ratio": policy["floor_ratio"],
                             "ceiling_ratio": policy["ceiling_ratio"],
                             "max_delta_ratio": policy["max_delta_ratio"], "csxh": []},
                            elasticity=Elasticity.load())

    def baseline_fare(e: dict, bid_total: int = 0, lf_max: float = 1.0) -> int:
        return f0[(e["origin"], e["dest"])]

    def aulac_fare(e: dict, bid_total: int = 0, lf_max: float = 1.0) -> int:
        ctx = PricingContext(che_do_gia="AI", lead_time_days=int(e["days_to_departure"]),
                             distance_km=e["distance_km"], peak_summer=True,
                             load_factor_max=lf_max, load_factor_route=lf_max)
        return engine_.price(f0[(e["origin"], e["dest"])], ctx, bid_total_vnd=bid_total).gia_cuoi_vnd

    return baseline_fare, aulac_fare


def replay_baseline(events: list[dict], state: BaselineQuota, fare_fn=None) -> list[RequestResult]:
    fare_fn = fare_fn or _default_fare_fn
    results = []
    for e in events:
        fare = fare_fn(e)
        ok = state.request(e["segment_from"], e["segment_to"], e["quantity"])
        results.append(RequestResult(e["request_id"], ok, fare if ok else 0, e["distance_km"]))
    return results


def replay_aulac(events: list[dict], state: SegmentSeatMatrix, fare_fn=None) -> list[RequestResult]:
    fare_fn = fare_fn or _default_fare_fn
    results = []
    for e in events:
        remaining = {s: state.remaining_capacity(s) for s in network.all_segment_ids()}
        fc = _forecast_snapshot(state, e["days_to_departure"])
        segs = list(range(e["segment_from"], e["segment_to"] + 1))
        bid_total = sum(bid_price.bid_price_segment(fc[s], remaining[s], network.LEG_DISTANCE_KM[s])
                        for s in segs)
        lf_max = max((1.0 - remaining[s] / network.N_SEATS for s in segs), default=0.0)
        fare = fare_fn(e, bid_total, lf_max)
        if fare < bid_total:
            results.append(RequestResult(e["request_id"], False, 0, e["distance_km"]))
            continue
        seat_idx = state.first_fit(e["segment_from"], e["segment_to"])
        ok = seat_idx is not None
        results.append(RequestResult(e["request_id"], ok, fare if ok else 0, e["distance_km"]))
    return results


def metrics(events: list[dict], baseline_results: list[RequestResult], aulac_results: list[RequestResult],
            baseline_state: BaselineQuota, aulac_state: SegmentSeatMatrix) -> dict:
    n = len(events)
    false_sold_out = sum(1 for b, a in zip(baseline_results, aulac_results) if not b.accepted and a.accepted)
    aulac_occ = {s: network.N_SEATS - aulac_state.remaining_capacity(s) for s in network.all_segment_ids()}
    empty_seat_km = sum((network.N_SEATS - aulac_occ[s]) * network.LEG_DISTANCE_KM[s]
                        for s in network.all_segment_ids())
    passenger_km = sum(aulac_occ[s] * network.LEG_DISTANCE_KM[s] for s in network.all_segment_ids())
    return {
        "false_sold_out_rate": false_sold_out / max(n, 1),
        "empty_seat_km": empty_seat_km,
        "passenger_km": passenger_km,
        "baseline": {
            "revenue_vnd": sum(r.revenue_vnd for r in baseline_results),
            "acceptance_rate": sum(r.accepted for r in baseline_results) / max(n, 1),
        },
        "aulac": {
            "revenue_vnd": sum(r.revenue_vnd for r in aulac_results),
            "acceptance_rate": sum(r.accepted for r in aulac_results) / max(n, 1),
        },
    }


def run_seed(events: list[dict], baseline_fare_fn=None, aulac_fare_fn=None) -> dict:
    """Common random numbers: cùng event stream cho cả 2 policy (§DEV2 H6-H10).
    State bắt đầu TRỐNG (không golden pre-seed) — sự khác biệt baseline/Âu Lạc emerge
    tự nhiên qua ~400 request/seed vì baseline không tái sử dụng gap (xem BaselineQuota).
    Test riêng cho golden request cố định dùng build_golden_state() (test_backtest.py).
    fare_fn mặc định = fixed_fare (cô lập biến allocation); bản priced dùng
    make_priced_fare_fns() — xem T5 plan tích hợp."""
    baseline_state = BaselineQuota()
    aulac_state = SegmentSeatMatrix(network.N_SEATS, network.N_SEGMENTS)
    baseline_results = replay_baseline(events, baseline_state, baseline_fare_fn)
    aulac_results = replay_aulac(events, aulac_state, aulac_fare_fn)
    return metrics(events, baseline_results, aulac_results, baseline_state, aulac_state)


def run_backtest(events_by_seed: dict[int, list[dict]],
                 baseline_fare_fn=None, aulac_fare_fn=None) -> dict:
    per_seed = {}
    failed_seeds = []
    for seed, events in events_by_seed.items():
        try:
            per_seed[seed] = run_seed(events, baseline_fare_fn, aulac_fare_fn)
        except Exception as exc:  # noqa: BLE001 — báo seed fail, KHÔNG giấu (DEV2 §H14-H18)
            failed_seeds.append({"seed": seed, "error": str(exc)})
    revenues_baseline = [m["baseline"]["revenue_vnd"] for m in per_seed.values()]
    revenues_aulac = [m["aulac"]["revenue_vnd"] for m in per_seed.values()]
    report = {
        "seeds_run": sorted(per_seed.keys()),
        "failed_seeds": failed_seeds,
        "raw": per_seed,
        "baseline_metrics": _summary(revenues_baseline),
        "aulac_metrics": _summary(revenues_aulac),
    }
    report["checksum"] = report_checksum(report)
    return report


def _summary(values: list[float]) -> dict:
    if not values:
        return {"revenue_median": 0, "revenue_min": 0, "revenue_max": 0}
    return {
        "revenue_median": statistics.median(values),
        "revenue_min": min(values),
        "revenue_max": max(values),
    }


def report_checksum(report: dict) -> str:
    body = {k: v for k, v in report.items() if k != "checksum"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --- Evidence runner (DEV2 §H14-H18): chạy backtest trên event stream ĐÃ COMMIT
# (seed/backtest/*.jsonl, do BE1 duyệt) và xuất report median+min/max+raw+checksum ---
from pathlib import Path  # noqa: E402 — gom import phụ trợ của runner ở cuối cho gọn

SEED_BACKTEST_DIR = Path(__file__).resolve().parents[2] / "seed" / "backtest"


def load_events(seed: int, seed_dir: Path | None = None) -> list[dict]:
    path = (seed_dir or SEED_BACKTEST_DIR) / f"events-seed-{seed}.jsonl"
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_all_events(seeds: list[int] | None = None, seed_dir: Path | None = None) -> dict[int, list[dict]]:
    from src.backtest.events import SEEDS  # tránh vòng import ở top-level
    return {s: load_events(s, seed_dir) for s in (seeds or SEEDS)}


if __name__ == "__main__":
    # Evidence runner với GIÁ THẬT (T5): baseline = giá niêm yết, Âu Lạc = PricingEngine.
    baseline_fn, aulac_fn = make_priced_fare_fns()
    report = run_backtest(load_all_events(), baseline_fn, aulac_fn)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

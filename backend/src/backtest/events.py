# -*- coding: utf-8 -*-
"""Sinh event stream backtest — NHPP theo booking curve YAML §6, deterministic theo seed.

DEV2 §H0-H2: "sinh seed/backtest/events-seed-{20260717..20260721}.jsonl bằng NHPP
từ YAML (booking curve theo cự ly), deterministic theo seed, kèm checksum."

Phương pháp: conditional sampling (đếm ~ Poisson(Λ) rồi rút thời điểm i.i.d. từ mật
độ chuẩn hóa) — tương đương chính xác thinning Lewis-Shedler, không chia bin. Cùng
cách tiếp cận với `generated_data/generate_data.py::sample_arrivals` (đã kiểm chứng
trong dataset generator), viết lại gọn cho 8 ga / 1 chuyến thay vì toàn mạng lưới.

Quy mô cầu ở đây là DEMO — hiệu chỉnh bằng DEMAND_SCALE để tổng số request/seed nằm
trong khoảng vài trăm cho một chuyến 40 ghế (đủ tạo khan hiếm nhưng chạy backtest
<10s). Không phải hiệu chuẩn SMM đầy đủ như generator gốc.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from src.forecast import network

REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/src/backtest -> backend/src -> backend -> repo root
BACKEND_ROOT = Path(__file__).resolve().parents[2]  # backend/src/backtest -> backend/src -> backend
YAML_PATH = (REPO_ROOT / "generated_data" / "Synthetic_DATA_guide"
             / "04_THAM_SO_CAU_HINH_MO_PHONG.yaml")
# nguồn: backend/scripts/calibrate_backtest_lambda.py (offline, cần generated_data/data/,
# tính từ search_log thang=2026-06 SE1 08..22/06 cho đúng 8 ga golden, scale 40/448) —
# thay TARGET_TOTAL_REQUESTS=400 bịa cũ. Sinh lại: python backend/scripts/calibrate_backtest_lambda.py
LAMBDA_CACHE_PATH = REPO_ROOT / "backend" / "scripts" / "backtest_lambda_cache.json"
SEEDS = [20260717, 20260718, 20260719, 20260720, 20260721]  # nguồn: spec — 5 seed đã commit (DoD "backtest ≥5 seeds")
HORIZON_DAYS = 65.0  # nguồn: generated_data/data/calendar_events.csv ngay=2026-06-15, H_horizon (đợt HE_2026)


def _load_curves() -> list[dict]:
    raw = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    return raw["duong_cong_dat_cho"]["bang"][:3]  # DAI_THUONG, TRUNG, NGAN (bỏ TET — golden run không phải Tết)


def _curve_for_distance(curves: list[dict], d_km: float) -> dict:
    if d_km >= 900:  # nguồn: 2 (YAML band DAI_THUONG, khớp app.config.BAND_EDGES)
        return curves[0]
    if d_km >= 300:  # nguồn: 2 (YAML band TRUNG, khớp app.config.BAND_EDGES)
        return curves[1]
    return curves[2]


def _od_pairs() -> list[tuple[str, str]]:
    ids = [s["id"] for s in network.STATIONS]
    return [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]


def _sample_days_to_departure(rng: np.random.Generator, n: int, w0: float, comps: list[tuple],
                               horizon: float) -> np.ndarray:
    """z ~ w0*delta0 + sum w_m Beta(a,b); days_to_departure = z*horizon (z=0 sát ngày chạy,
    z=1 lúc mở bán — đảo ngược quy ước u=(1-z)H của generator gốc cho rõ nghĩa 'ngày trước khởi hành')."""
    if n == 0:
        return np.empty(0)
    ws = np.array([w0] + [c[0] for c in comps])
    ws = ws / ws.sum()
    pick = rng.choice(len(ws), size=n, p=ws)
    z = np.zeros(n)
    for k, (w, a, b) in enumerate(comps, start=1):
        m = pick == k
        z[m] = rng.beta(a, b, int(m.sum()))
    return z * horizon


def _load_real_lambda() -> dict[tuple[str, str], float]:
    """λ thật per O-D (tổng số request kỳ vọng suốt đợt bán, cho 1 chuyến), từ search_log
    thật đã scale 40/448 — xem docstring LAMBDA_CACHE_PATH ở trên."""
    raw = json.loads(LAMBDA_CACHE_PATH.read_text(encoding="utf-8"))["lambda_per_day_scaled"]
    out = {}
    for key, v in raw.items():
        o, d = key.split("|")
        out[(o, d)] = v
    return out


def generate_events(seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    curves = _load_curves()
    pairs = _od_pairs()
    real_lambda = _load_real_lambda()

    events = []
    for (o, d) in pairs:
        dist = network.od_distance_km(o, d)
        curve = _curve_for_distance(curves, dist)
        lam = real_lambda.get((o, d), 0.0)
        n = int(rng.poisson(lam))
        comps = [(c["w"], c["a"], c["b"]) for c in curve["thanh_phan"]]
        days = _sample_days_to_departure(rng, n, curve["w0"], comps, HORIZON_DAYS)
        seg_from, seg_to = network.seg_range(o, d)
        for u in days:
            events.append({
                "seed": seed,
                "origin": o,
                "dest": d,
                "segment_from": seg_from,
                "segment_to": seg_to,
                "seat_class": network.SEAT_CLASS,
                "quantity": 1,
                "distance_km": round(dist, 1),
                "days_to_departure": round(float(u), 3),
            })
    events.sort(key=lambda e: (-e["days_to_departure"], e["origin"], e["dest"]))
    for i, e in enumerate(events, start=1):
        e["request_id"] = f"req_{seed}_{i:05d}"
    return events


def checksum(events: list[dict]) -> str:
    canon = json.dumps(events, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def write_all(out_dir: Path | None = None) -> dict[int, str]:
    out_dir = out_dir or (BACKEND_ROOT / "seed" / "backtest")
    out_dir.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for seed in SEEDS:
        events = generate_events(seed)
        path = out_dir / f"events-seed-{seed}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        checksums[seed] = checksum(events)
    (out_dir / "checksums.json").write_text(
        json.dumps({"generated_by": "BE2/src/backtest/events.py", "checksums": checksums}, indent=2),
        encoding="utf-8")
    return checksums


if __name__ == "__main__":
    for seed, cs in write_all().items():
        print(f"seed {seed}: {cs}")

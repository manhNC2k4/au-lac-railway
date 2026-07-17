# -*- coding: utf-8 -*-
"""Seed/dataset pipeline DoD tests — không cần DB."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
BACKEND_DIR = Path(__file__).resolve().parent.parent


def sha256_of(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_seed_package_matches_expected_checksums():
    scenario = json.loads((SEED_DIR / "scenario.json").read_text(encoding="utf-8"))
    bookings = [json.loads(line) for line in
                (SEED_DIR / "initial_bookings.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    fare_products = json.loads((SEED_DIR / "fare_products.json").read_text(encoding="utf-8"))["products"]
    pricing_policy = json.loads((SEED_DIR / "pricing_policy.json").read_text(encoding="utf-8"))
    forecast = json.loads((SEED_DIR / "forecast.json").read_text(encoding="utf-8"))
    expected = json.loads((SEED_DIR / "expected_checksums.json").read_text(encoding="utf-8"))

    assert sha256_of(scenario) == expected["scenario_checksum"]
    assert sha256_of(bookings) == expected["initial_bookings_checksum"]
    assert sha256_of(fare_products) == expected["fare_products_checksum"]
    assert sha256_of(pricing_policy) == expected["pricing_policy_checksum"]
    assert sha256_of(forecast) == expected["forecast_checksum"]


def test_golden_gap_present():
    bookings = [json.loads(line) for line in
                (SEED_DIR / "initial_bookings.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    golden = [b for b in bookings if b["seat_id"] == "C01-S017"]
    covered_segments = {s for b in golden for s in b["segments"]}
    assert 3 not in covered_segments and 4 not in covered_segments
    assert covered_segments == {1, 2, 5, 6, 7}


def test_no_ground_truth_import():
    """CI gate (Master §2.1): grep -r "_ground_truth" src/ phải rỗng."""
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys, pathlib; "
         "hits = [str(p) for p in pathlib.Path('src').rglob('*.py') "
         "if '_ground_truth' in p.read_text(encoding='utf-8')]; "
         "sys.exit(1) if hits else sys.exit(0)"],
        cwd=str(BACKEND_DIR),
    )
    assert result.returncode == 0, "src/ chứa tham chiếu _ground_truth — cấm tuyệt đối (Master §2.1)"

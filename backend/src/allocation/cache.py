# -*- coding: utf-8 -*-
"""P2 Bước4 — cache bid price DLP thật (`app.bt3_allocation.analyze_run`, live-import
qua shim `integration/ssm_from_postgres.py`). Refresh CHỈ lúc reset/forecast-refresh,
KHÔNG mỗi request /offers — giữ p95 thấp (NFR gốc <1s), LP không giải trong request path.

LP fail (`_solve_dlp` lỗi/exception) => KHÔNG cache => route đọc cache rỗng => 503
POLICY_UNAVAILABLE, KHÔNG fallback công thức scarcity cũ (đã xoá, xem forecast/bid_price.py).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:      # `app/` package sống ở repo root, ngoài backend/
    sys.path.insert(0, str(REPO_ROOT))

_CACHE: dict[tuple[str, int, int], dict] = {}


def _chuyen_id(service_run_id: str) -> str:
    """'SE1_2026-06-15_LE' -> 'SE1_2026-06-15' (khớp app.bt3_allocation.rsplit('_',1))."""
    return service_run_id.rsplit("_", 1)[0]


def refresh(service_run_id: str) -> dict | None:
    """Giải DLP cho `service_run_id` ở version hiện tại + lưu cache. Trả kết quả hoặc
    None nếu LP fail."""
    from app.bt3_allocation import analyze_run
    from integration.ssm_from_postgres import build_forecast_df, build_shim

    from ..adapters import model_adapter
    from ..api.deps import SEED_DIR, get_pricer, get_state_manager
    from ..forecast import network
    from ..state.db import get_connection

    scenario = json.loads((SEED_DIR / "scenario.json").read_text(encoding="utf-8"))
    ssm = get_state_manager()
    seatmap = ssm.get_seatmap(service_run_id)
    matrix_version = seatmap["matrix_version"]
    matrix, _seat_ids = model_adapter.seatmap_to_matrix(seatmap, network.N_SEGMENTS)

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT forecast_demand, forecast_version FROM demand_forecast
               WHERE service_run_id=%s AND seat_class=%s
                 AND forecast_version=(SELECT COALESCE(MAX(forecast_version),1)
                                       FROM demand_forecast WHERE service_run_id=%s)
               ORDER BY id""",
            (service_run_id, "NGOI_MEM_DH", service_run_id),
        )
        rows = cur.fetchall()
    conn.commit()
    forecast_version = rows[0][1] if rows else 1

    # Seed chỉ có forecast MỨC ĐOẠN (7 hàng theo thứ tự segment, không phải O-D pair
    # thật) — xấp xỉ mỗi đoạn liền kề thành 1 cặp O-D cho DLP; các cặp O-D nhiều đoạn
    # khác không có tín hiệu riêng, DLP coi cầu=0 cho chúng (bảo thủ, không bịa cầu).
    segs = scenario["segments"]
    fc_rows = [{"origin": s["from"], "dest": s["to"], "seat_class": "NGOI_MEM_DH",
                "remaining_demand": float(rows[i][0])}
               for i, s in enumerate(segs) if i < len(rows)]
    forecast_df = build_forecast_df(fc_rows)

    shim = build_shim(scenario, matrix)
    try:
        result = analyze_run(shim, get_pricer(), shim.chuyen_id, forecast_df)
    except Exception:
        return None

    _CACHE.clear()  # 1 scenario duy nhất trong demo — tránh cache phình vô hạn
    _CACHE[(service_run_id, matrix_version, forecast_version)] = result
    return result


def get(service_run_id: str, matrix_version: int, forecast_version: int) -> dict | None:
    return _CACHE.get((service_run_id, matrix_version, forecast_version))

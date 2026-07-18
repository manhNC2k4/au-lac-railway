# -*- coding: utf-8 -*-
"""P7.4 (C4 xếp nhóm) — bọc `app.group_seating.plan_group` (CP-SAT, fallback greedy)
trên snapshot Postgres thật, tái dùng shim `integration/ssm_from_postgres.py` đã có sẵn
cho P2 (cùng shim, không viết thêm bản chuyển đổi ma trận thứ hai). Thuần đề xuất —
không giữ ghế (giữ ghế thật vẫn qua `/offers`→`/holds` như bình thường, seat_plan lấy
seat_id từ `assignments`)."""
import json

from ..adapters import model_adapter
from ..api.deps import SEED_DIR
from ..forecast import network


def quote_group(ssm, service_run_id: str, origin: str, dest: str, seat_class: str,
                n_khach: int) -> dict:
    from app.group_seating import plan_group

    from integration.ssm_from_postgres import build_shim

    scenario = json.loads((SEED_DIR / "scenario.json").read_text(encoding="utf-8"))
    seatmap = ssm.get_seatmap(service_run_id)
    matrix, seat_ids = model_adapter.seatmap_to_matrix(seatmap, network.N_SEGMENTS)
    shim = build_shim(scenario, matrix)

    result = plan_group(shim, shim.chuyen_id, seat_class, origin, dest, n_khach)
    plan = result["plan"]
    if plan["kha_thi"]:
        for a in plan["assignments"]:
            a["seat_id"] = seat_ids[a["seat_idx"]]
    return result

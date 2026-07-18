# -*- coding: utf-8 -*-
"""P7.2 (C2 tái phân bổ + phê duyệt + rollback) — re-solve DLP thật (tái dùng
`allocation/cache.py` P2, không giải LP lần hai), diff hạn mức (`booking_limit`)
đoạn×loại-hành-trình×lớp-ghế cũ/mới -> đề xuất MO_THEM/SIET_LAI, version hoá vào
`quota_version` để điều độ viên duyệt/rollback.

Khác `app.reallocation.propose_reallocation` (band ngan/trung/dài từ ML per-O-D) ở
CHỖ GRAIN: golden scenario chỉ có forecast per-SEGMENT (không phải per-O-D thật, xem
`forecast/forecast.py` — cùng lý do P4 không gọi thẳng HGB model). Diff hạn mức ở đây
vẫn đúng Ý TƯỞNG của `app.reallocation` (so booking_limit cũ/mới cùng key), chỉ khác
nguồn `rows_by_band`/`sold_by_band` không áp dụng được cho grain golden.

ponytail: chưa enforce `booking_limit` trong `/offers` (route hiện chỉ so giá vs bid
DLP) — đây là workflow đề xuất/duyệt/rollback, KHÔNG tự động chặn request nào. Enforce
thật là việc kế tiếp, cố tình để riêng vì đổi hành vi route sống cần regression test
golden path kỹ hơn phạm vi lần này.
"""
import json

from ..audit import log as audit_log
from ..state.errors import PolicyUnavailable


def _latest_active_quota(conn, service_run_id: str) -> tuple[int | None, list | None]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT version, quota FROM quota_version WHERE service_run_id=%s AND status='ACTIVE'
               ORDER BY version DESC LIMIT 1""",
            (service_run_id,),
        )
        row = cur.fetchone()
    conn.commit()
    return (row[0], row[1]) if row else (None, None)


def _next_version(conn, service_run_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(version),0) FROM quota_version WHERE service_run_id=%s",
                    (service_run_id,))
        v = cur.fetchone()[0]
    conn.commit()
    return v + 1


def _diff_quota(old_quota: list[dict] | None, new_quota: list[dict]) -> list[dict]:
    old_map = {(q["khu_gian_id"], q["loai_hanh_trinh"], q["seat_class"]): q["booking_limit"]
              for q in (old_quota or [])}
    proposals = []
    for q in new_quota:
        key = (q["khu_gian_id"], q["loai_hanh_trinh"], q["seat_class"])
        old = old_map.get(key)
        if old is not None and old != q["booking_limit"]:
            action = "MO_THEM" if q["booking_limit"] > old else "SIET_LAI"
            proposals.append({"khu_gian_id": q["khu_gian_id"], "loai_hanh_trinh": q["loai_hanh_trinh"],
                              "seat_class": q["seat_class"], "action": action,
                              "limit_cu": old, "limit_moi": q["booking_limit"]})
    return proposals


def propose(conn, service_run_id: str) -> dict:
    """Re-solve DLP (P2 cache) + diff vs bản ACTIVE hiện tại -> tạo bản PENDING mới."""
    from ..allocation import cache as allocation_cache

    result = allocation_cache.refresh(service_run_id)
    if result is None:
        raise PolicyUnavailable("DLP không giải được — chưa thể đề xuất hạn mức mới", {})
    new_quota = result["quota"]
    _, old_quota = _latest_active_quota(conn, service_run_id)
    proposal = _diff_quota(old_quota, new_quota)
    version = _next_version(conn, service_run_id)

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO quota_version (service_run_id, version, quota, proposal, status)
               VALUES (%s,%s,%s,%s,'PENDING')""",
            (service_run_id, version, json.dumps(new_quota), json.dumps(proposal)),
        )
    conn.commit()
    audit_log.persist(conn, {
        "loai": "ALLOCATION", "input": {"service_run_id": service_run_id},
        "output": {"version": version, "n_proposals": len(proposal)},
        "explain": f"{len(proposal)} thay đổi hạn mức đề xuất (version {version}, PENDING duyệt)",
        "model_version": "1.0",
    }, service_run_id)
    return {"version": version, "status": "PENDING", "proposal": proposal, "quota": new_quota}


def get_version(conn, service_run_id: str, version: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT version, quota, proposal, status, decided_by, created_at, decided_at
               FROM quota_version WHERE service_run_id=%s AND version=%s""",
            (service_run_id, version),
        )
        row = cur.fetchone()
    conn.commit()
    if not row:
        return None
    return {"version": row[0], "quota": row[1], "proposal": row[2], "status": row[3],
           "decided_by": row[4], "created_at": row[5].isoformat(),
           "decided_at": row[6].isoformat() if row[6] else None}


def _activate(conn, service_run_id: str, version: int, decided_by: str) -> bool:
    """Đặt `version` ACTIVE, lùi bản ACTIVE cũ (nếu có) về ROLLED_BACK — dùng chung
    cho cả approve() (từ PENDING) và rollback() (từ bất kỳ bản cũ nào)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE quota_version SET status='ROLLED_BACK' WHERE service_run_id=%s AND status='ACTIVE'",
            (service_run_id,),
        )
        cur.execute(
            """UPDATE quota_version SET status='ACTIVE', decided_by=%s, decided_at=NOW()
               WHERE service_run_id=%s AND version=%s RETURNING version""",
            (decided_by, service_run_id, version),
        )
        row = cur.fetchone()
    conn.commit()
    return row is not None


def approve(conn, service_run_id: str, version: int, decided_by: str) -> dict | None:
    v = get_version(conn, service_run_id, version)
    if v is None or v["status"] != "PENDING":
        return None
    _activate(conn, service_run_id, version, decided_by)
    audit_log.persist(conn, {
        "loai": "ALLOCATION", "input": {"version": version},
        "output": {"status": "ACTIVE"}, "explain": f"duyệt hạn mức version {version} bởi {decided_by}",
        "model_version": "1.0",
    }, service_run_id)
    return get_version(conn, service_run_id, version)


def reject(conn, service_run_id: str, version: int, decided_by: str) -> dict | None:
    v = get_version(conn, service_run_id, version)
    if v is None or v["status"] != "PENDING":
        return None
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE quota_version SET status='REJECTED', decided_by=%s, decided_at=NOW() WHERE service_run_id=%s AND version=%s",
            (decided_by, service_run_id, version),
        )
    conn.commit()
    audit_log.persist(conn, {
        "loai": "ALLOCATION", "input": {"version": version},
        "output": {"status": "REJECTED"}, "explain": f"từ chối hạn mức version {version} bởi {decided_by}",
        "model_version": "1.0",
    }, service_run_id)
    return get_version(conn, service_run_id, version)


def rollback(conn, service_run_id: str, version: int, decided_by: str) -> dict | None:
    """Tái kích hoạt một bản cũ (đã ACTIVE trước đây hoặc PENDING) — bản đang ACTIVE
    hiện tại lùi về ROLLED_BACK. Không giới hạn trạng thái nguồn (rollback là hành vi
    khẩn cấp: điều độ viên cần quay lại bản BẤT KỲ đã biết là đúng)."""
    if get_version(conn, service_run_id, version) is None:
        return None
    _activate(conn, service_run_id, version, decided_by)
    audit_log.persist(conn, {
        "loai": "ALLOCATION", "input": {"version": version},
        "output": {"status": "ACTIVE"}, "explain": f"rollback về hạn mức version {version} bởi {decided_by}",
        "model_version": "1.0",
    }, service_run_id)
    return get_version(conn, service_run_id, version)

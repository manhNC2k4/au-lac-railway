# -*- coding: utf-8 -*-
"""P7.1 — persist mọi ProposalLog (`_log`) mà các module `app/` trả về (quote/
merge/reallocation/group/waitlist). Trước P7, các `_log` này bị bỏ (không route
nào ghi vào DB) — bảng `audit_log`/`proposal_log` tồn tại trong schema nhưng
rỗng. Đây là điểm ghi DUY NHẤT, mọi caller đi qua đây để không lệch schema.
"""
import json

from psycopg import Connection


def persist(conn: Connection, log: dict, service_run_id: str, actor: str = "system") -> None:
    """`log` = `ProposalLog.to_dict()` (loai/input/output/explain/model_version/timestamp)."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO proposal_log (service_run_id, loai, input, output, explain, model_version, actor)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (service_run_id, log["loai"], _json(log.get("input")), _json(log.get("output")),
             log.get("explain"), log.get("model_version"), actor),
        )
    conn.commit()


def _json(d):
    return json.dumps(d, ensure_ascii=False) if d is not None else None

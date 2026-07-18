# -*- coding: utf-8 -*-
"""P7.1 — proposal_log phải ghi được và đọc lại đúng nội dung ProposalLog."""
from src.audit import log as audit_log

SERVICE_RUN_ID = "SE1_2026-06-15_LE"


def test_persist_writes_proposal_log_row(conn, reset_state):
    entry = {"loai": "WAITLIST", "input": {"n_pending": 2}, "output": {"n_matched": 1},
             "explain": "khớp 1 yêu cầu hàng chờ, còn 1 chưa khớp", "model_version": "1.0"}
    audit_log.persist(conn, entry, SERVICE_RUN_ID, actor="tester")

    with conn.cursor() as cur:
        cur.execute(
            """SELECT loai, input, output, explain, model_version, actor FROM proposal_log
               WHERE service_run_id=%s ORDER BY id DESC LIMIT 1""",
            (SERVICE_RUN_ID,),
        )
        row = cur.fetchone()
    conn.commit()
    assert row[0] == "WAITLIST"
    assert row[1] == {"n_pending": 2}
    assert row[2] == {"n_matched": 1}
    assert row[3] == entry["explain"]
    assert row[4] == "1.0"
    assert row[5] == "tester"

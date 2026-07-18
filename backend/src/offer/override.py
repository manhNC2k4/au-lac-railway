# -*- coding: utf-8 -*-
"""P7.6 — ghi đè giá thủ công TRONG sàn-trần đã duyệt (điều độ viên can thiệp khi
engine chưa xử lý được tình huống đặc biệt). Bất biến giữ nguyên: không bao giờ tự
định giá ngoài dải [floor_ratio, ceiling_ratio]·F0 (`GuardrailViolation` nếu vi phạm).
Chỉ override được offer CHƯA có hold (giá đã khoá lúc hold là bất khả xâm phạm — xem
`pricing/engine.py::held price` — override sau khi hold coi như sửa giá đã khoá, cấm)."""
from ..audit import log as audit_log
from ..state.errors import GuardrailViolation, OfferExpired, PolicyUnavailable, SeatConflict


def override_price(conn, offer_id: str, new_price_vnd: int, reason: str, decided_by: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT service_run_id, final_price_vnd, expires_at,
                      origin_station_id, dest_station_id, seat_class
               FROM offer WHERE offer_id=%s""",
            (offer_id,),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise OfferExpired("Offer không tồn tại", {"offer_id": offer_id})
    service_run_id, old_price, expires_at, origin, dest, seat_class = row

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM seat_hold WHERE offer_id=%s AND status IN ('ACTIVE','CONFIRMED') LIMIT 1",
            (offer_id,),
        )
        held = cur.fetchone() is not None
    conn.commit()
    if held:
        raise SeatConflict(
            "Offer đã có hold — giá đã khoá bất khả xâm phạm, không override được",
            {"offer_id": offer_id})

    with conn.cursor() as cur:
        cur.execute(
            """SELECT floor_ratio, ceiling_ratio FROM pricing_policy
               WHERE is_active=TRUE ORDER BY policy_id DESC LIMIT 1""",
        )
        prow = cur.fetchone()
        cur.execute(
            """SELECT base_fare_vnd FROM fare_product
               WHERE service_run_id=%s AND origin_station_id=%s AND dest_station_id=%s AND seat_class=%s
               ORDER BY version DESC LIMIT 1""",
            (service_run_id, origin, dest, seat_class),
        )
        frow = cur.fetchone()
    conn.commit()
    if prow is None or frow is None:
        raise PolicyUnavailable(
            "Chưa có pricing policy / fare_product để tính guardrail override", {"offer_id": offer_id})
    floor_ratio, ceiling_ratio = float(prow[0]), float(prow[1])
    base_fare = int(frow[0])
    lo, hi = floor_ratio * base_fare, ceiling_ratio * base_fare
    if not (lo <= new_price_vnd <= hi):
        raise GuardrailViolation(
            f"Giá override {new_price_vnd:,}đ ngoài dải guardrail [{lo:,.0f};{hi:,.0f}]đ",
            {"offer_id": offer_id, "floor": lo, "ceiling": hi, "requested": new_price_vnd})

    with conn.cursor() as cur:
        cur.execute("UPDATE offer SET final_price_vnd=%s WHERE offer_id=%s", (new_price_vnd, offer_id))
    conn.commit()

    audit_log.persist(conn, {
        "loai": "OVERRIDE", "input": {"offer_id": offer_id, "reason": reason},
        "output": {"old_price_vnd": old_price, "new_price_vnd": new_price_vnd},
        "explain": f"override {offer_id}: {old_price:,}đ -> {new_price_vnd:,}đ, lý do: {reason}",
        "model_version": "1.0",
    }, service_run_id, actor=decided_by)
    return {"offer_id": offer_id, "old_price_vnd": old_price, "new_price_vnd": new_price_vnd,
           "expires_at": expires_at.isoformat()}

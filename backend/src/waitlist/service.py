# -*- coding: utf-8 -*-
"""P7.3 (C5 hàng chờ thông minh, YC7) — Postgres-backed trên bảng `waiting_list` đã
có sẵn trong schema V1. Điểm ưu tiên tái dùng ĐÚNG công thức `app.waitlist.WaitlistManager`
(một nguồn tính điểm — không viết lại công thức lần hai): tất định, không dùng dữ
liệu cá nhân để phân biệt giá, chỉ (giá trị vé chuẩn hoá, độ gấp 1/(1+u), khan hiếm
đoạn qua bid, cờ CSXH).

Khớp/giữ chỗ tạm: gọi lại ĐÚNG pipeline `/offers` -> `/holds` (không viết pipeline
giá/CAS thứ hai) — khớp được thì khách có `hold_id` thật để thanh toán trong TTL bình
thường (10 phút), y hệt luồng đặt vé trực tiếp.

ponytail: không có worker nền trong demo này — `match()` được gọi tường minh qua
`POST /waitlist/match` (ops trigger sau khi có hold hết hạn/hủy vé), không tự động
chạy sau mỗi `expire_due_holds` để không đụng ranh giới "SeatStateManager là single
writer duy nhất". Nâng cấp: cron/scheduler gọi endpoint này định kỳ khi cần thật.
"""
import uuid

from ..audit import log as audit_log
from ..state.errors import DomainError

# cột `priority_score` (schema V1) là INT — scale để giữ 4 chữ số thập phân của score
# gốc (round(...,4) trong app.waitlist) mà không phải đổi kiểu cột.
SCORE_SCALE = 10000  # ponytail: hệ số scale lưu trữ, không phải số đo/hiệu chuẩn
# giới hạn số waitlist xử lý mỗi lần gọi /waitlist/match — nâng khi hàng chờ thật lớn hơn.
DEFAULT_MAX_MATCHES = 50  # ponytail: giới hạn demo scale, không phải số đo/hiệu chuẩn


def _score(pricer, service_run_id: str, origin: str, dest: str, seat_class: str,
          u: float, csxh_doi_tuong: str, bid_price_route: int) -> float:
    from app.contracts import BookingRequest, PassengerProfile
    from app.waitlist import WaitlistManager

    profile = PassengerProfile(doi_tuong_csxh=csxh_doi_tuong if csxh_doi_tuong != "KHONG" else "KHONG")
    req = BookingRequest(chuyen_id=f"{service_run_id}_dummy", ga_di=origin, ga_den=dest,
                        loai_cho=seat_class, ngay_chay="", u=u, profile=profile)
    entry = WaitlistManager(pricer).add(req, bid_price_route)
    return entry.priority_score


def add(conn, pricer, service_run_id: str, origin: str, dest: str, seat_class: str,
       u: float, quantity: int = 1, priority_passenger: bool = False,
       csxh_doi_tuong: str = "KHONG", bid_price_route: int = 0) -> dict:
    score = _score(pricer, service_run_id, origin, dest, seat_class, u, csxh_doi_tuong, bid_price_route)
    waitlist_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO waiting_list (waitlist_id, service_run_id, origin_station_id,
                   dest_station_id, seat_class, priority_score, priority_passenger, quantity, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'PENDING')""",
            (waitlist_id, service_run_id, origin, dest, seat_class,
             round(score * SCORE_SCALE), priority_passenger, quantity),
        )
    conn.commit()
    audit_log.persist(conn, {"loai": "WAITLIST", "input": {"origin": origin, "dest": dest, "u": u},
                             "output": {"waitlist_id": waitlist_id, "priority_score": score},
                             "explain": f"vào hàng chờ {origin}->{dest}, score={score:.4f}",
                             "model_version": "1.0"}, service_run_id)
    return {"waitlist_id": waitlist_id, "priority_score": score, "status": "PENDING"}


def pending(conn, service_run_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT waitlist_id, origin_station_id, dest_station_id, seat_class,
                      priority_score, priority_passenger, quantity, created_at
               FROM waiting_list WHERE service_run_id=%s AND status='PENDING'
               ORDER BY priority_score DESC, created_at ASC""",
            (service_run_id,),
        )
        rows = cur.fetchall()
    conn.commit()
    return [{"waitlist_id": r[0], "origin_station_id": r[1], "dest_station_id": r[2],
            "seat_class": r[3], "priority_score": r[4] / SCORE_SCALE, "priority_passenger": r[5],
            "quantity": r[6], "created_at": r[7].isoformat()} for r in rows]


def match(conn, service_run_id: str, max_matches: int = DEFAULT_MAX_MATCHES) -> dict:
    """Duyệt hàng chờ PENDING theo score giảm dần; khớp được thì tạo Offer+Hold THẬT
    (tái dùng nguyên pipeline /offers -> /holds, KHÔNG viết lại giá/CAS) và đánh dấu
    MATCHED. Chưa khớp được thì giữ nguyên PENDING (không phải lỗi)."""
    from ..api.routes_holds import create_hold
    from ..api.routes_offers import create_offer
    from ..api.schemas import HoldRequest, OfferRequest

    matched, still = [], 0
    for e in pending(conn, service_run_id)[:max_matches * 4]:
        if len(matched) >= max_matches:
            break
        try:
            offer_out = create_offer(OfferRequest(
                service_run_id=service_run_id, origin_station_id=e["origin_station_id"],
                dest_station_id=e["dest_station_id"], seat_class=e["seat_class"],
                quantity=e["quantity"], priority_passenger=e["priority_passenger"],
            ))["data"]
        except DomainError:
            still += 1
            continue  # chưa có ghế/giá không đạt — vẫn PENDING, thử lại lần match sau

        hold_out = create_hold(
            HoldRequest(offer_id=offer_out["offer_id"], expected_matrix_version=offer_out["matrix_version"],
                       consent=offer_out["requires_customer_consent"]),
            idempotency_key=f"waitlist-{e['waitlist_id']}",
        )["data"]

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE waiting_list SET status='MATCHED', matched_hold_id=%s WHERE waitlist_id=%s",
                (hold_out["hold_id"], e["waitlist_id"]),
            )
        conn.commit()
        matched.append({"waitlist_id": e["waitlist_id"], "hold_id": hold_out["hold_id"],
                        "expires_at": hold_out["expires_at"]})

    audit_log.persist(conn, {"loai": "WAITLIST", "input": {"service_run_id": service_run_id},
                             "output": {"n_matched": len(matched), "n_still_pending": still},
                             "explain": f"khớp {len(matched)} yêu cầu hàng chờ, còn {still} chưa khớp",
                             "model_version": "1.0"}, service_run_id)
    return {"matched": matched, "still_pending": still}

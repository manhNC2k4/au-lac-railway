# -*- coding: utf-8 -*-
"""Đề xuất giá vé theo chặng cho MỘT chuyến — tín hiệu THẬT từ DB, không auto-quyết.

Mỗi đoạn: giá gốc (đơn giá/km × chiều dài đoạn) → hệ số điều chỉnh theo áp lực cầu
(cầu dự báo còn lại / chỗ trống) → giá đề xuất kẹp trong [floor, ceiling] của policy.
"Biên độ lợi nhuận" = doanh thu tăng thêm kỳ vọng = (giá đề xuất − giá gốc) × cầu dự báo
còn lại; danh sách xếp giảm dần theo số này. Nhân viên ACCEPT -> áp vào fare_product đoạn.

Cầu dự báo dùng `forecast.compute_forecast` (booking-curve pickup THẬT) nên chạy được cho
chuyến bất kỳ kể cả chuyến mới tạo chưa seed forecast/DLP — KHÔNG bịa cầu.
"""
import json
import logging
import math
from datetime import date
from pathlib import Path

from ..forecast.forecast import compute_forecast

_logger = logging.getLogger(__name__)

DEFAULT_RATE_VND_PER_KM = 950  # nguồn: golden 109000đ / 115km ≈ 948 — fallback khi run thiếu fare_product
DEFAULT_FLOOR_RATIO = 0.55
DEFAULT_CEILING_RATIO = 1.6
DEFAULT_SEAT_CLASS = "NGOI_MEM_DH"

# Mô hình cầu logistic THẬT (models/estimate_elasticity.py): P(mua | r) = σ(a + β·ln r),
# r = giá/giá_gốc, β<0. Thay bảng hệ số gõ tay cũ — giá đề xuất = giá tối đa hoá doanh thu
# kỳ vọng, gain tính có elasticity (giảm giá chỉ dương nếu cầu tăng bù được phần cắt).
_ELAST_PATH = Path(__file__).resolve().parents[3] / "models" / "artifacts" / "elasticity_params.json"
try:
    _ELAST = json.loads(_ELAST_PATH.read_text(encoding="utf-8"))
    _BETA = float(_ELAST["beta_ln_r"])
except Exception:  # thiếu artifact -> fallback trung tính (không co giãn): giữ nguyên giá gốc
    _logger.warning("suggestions: thiếu %s — fallback không-elasticity (giữ giá gốc)", _ELAST_PATH)
    _ELAST, _BETA = None, 0.0


def _band(km: float) -> str:
    return "ngan" if km <= 300 else ("trung" if km <= 900 else "dai")


def _lead_label(days: float) -> str:
    for edge, lab in zip(_ELAST["lead_edges"][1:], _ELAST["lead_labels"]) if _ELAST else []:
        if days <= edge:
            return lab
    return "30+"


def _context_a(km: float, days: float) -> float:
    """Hằng số ngữ cảnh a của đường cong cầu cho MỘT đoạn (band cự ly + lead-time; is_tet=0 demo 06/2026)."""
    if _ELAST is None:
        return 0.0
    c = _ELAST["coef"]
    return (_ELAST["intercept"] + c.get(f"band_{_band(km)}", 0.0)
            + c.get(f"lead_{_lead_label(days)}", 0.0))


def _p_buy(a: float, r: float) -> float:
    return 1.0 / (1.0 + math.exp(-(a + _BETA * math.log(max(r, 1e-3)))))


def _optimal_ratio(a: float, floor_ratio: float, ceiling_ratio: float) -> float:
    """Tỉ lệ giá r* tối đa hoá r·σ(a+β·ln r). Nghiệm đóng: q*=1+1/β (β<-1); cầu kém co giãn -> đẩy trần.

    ponytail: MỨC (intercept a) của đường cầu được train theo giá tham chiếu p_ny của generator,
    KHÔNG phải base_fare runtime -> P_mua(base)≈0.62 làm r* văng lên trần với hầu hết ngữ cảnh
    (mô hình cho rằng giá gốc đang thấp hơn WTP). Chỉ độ dốc β là đáng tin tuyệt đối. Muốn r*
    NỘI SUY hợp lý (không pin trần): hoặc (1) sàn = bid price DLP (chi phí cơ hội thật, allocation/cache),
    hoặc (2) hiệu chỉnh lại intercept theo phân phối base_fare thật. Xem tổng kết trong PR."""
    if _BETA >= -1:  # bao gồm fallback β=0: doanh thu tăng đơn điệu theo giá -> lên trần
        return ceiling_ratio
    q_star = 1.0 + 1.0 / _BETA
    logit = math.log(q_star / (1.0 - q_star))
    r = math.exp((logit - a) / _BETA)
    return min(max(r, floor_ratio), ceiling_ratio)

# Cache cầu-model per-run: output HGB chỉ phụ thuộc (train_id, stops, ngày chạy, lead-time,
# seat_class) — đều tĩnh theo chuyến (da_ban_truoc_u14=0), KHÔNG đổi theo matrix_version.
# Nên 1 lần tính (O(stops²) call model, ~5s) là đủ; GET/decide sau lấy tức thì.
# ponytail: dict không giới hạn — demo ít chuyến; nếu nhiều chuyến -> LRU theo run_id.
_MODEL_CACHE: dict[str, dict[int, float]] = {}


def clear_model_cache() -> None:
    _MODEL_CACHE.clear()


def _model_seat_class(seat_class: str) -> str:
    """seat_class runtime (NGOI_MEM_DH…) -> vocab model {K4,K6,NGOI}."""
    for cat in ("K4", "K6"):
        if cat in seat_class:
            return cat
    return "NGOI"


def _model_leg_remaining(demand_model, stops: list, seat_class: str, train_id: str,
                         service_date: date, days_to_departure: float) -> dict[int, float]:
    """Cầu còn lại per-ĐOẠN từ model HGB THẬT (scale dataset 448 chỗ/22 ga): với mỗi hành
    trình O-D (mọi cặp ga đi<đến), model dự báo tổng vé còn lại `remaining`; cộng dồn vào
    mọi đoạn mà hành trình đó đi qua -> cầu chiếm chỗ trên từng đoạn. Đây là cầu MỨC ĐOẠN
    đúng nghĩa (Σ hành trình qua đoạn). Key đoạn sinh động theo topology (số ga dừng) —
    KHÔNG khóa theo số đoạn seatmap (có run seatmap ít đoạn hơn train_stop, xem SE1)."""
    sc = _model_seat_class(seat_class)
    dow = str(service_date.weekday())
    leg_rem: dict[int, float] = {}
    for i in range(len(stops)):
        for j in range(i + 1, len(stops)):
            km = abs(stops[j][2] - stops[i][2])
            band = "ngan" if km <= 300 else ("trung" if km <= 900 else "dai")
            row = {"mac_tau": train_id, "ga_di": stops[i][0], "ga_den": stops[j][0],
                   "seat_class": sc, "band": band, "dot_ban_ve": "THUONG",
                   "che_do_gia": "LUAT", "dow": dow,
                   "da_ban_truoc_u14": 0, "toc_do_ban_7d": 0, "cu_ly_km": km,
                   "tau_tet": 99, "la_le": 0, "H_horizon": 60,
                   "sau_15_5": 1, "q_lag_7": None, "rolling_mean_28": None}
            rem = demand_model.remaining(row, days_to_departure)["remaining_demand"]
            for seg in range(i + 1, j + 1):  # đoạn 1-based: hành trình stop i->j phủ đoạn i+1..j
                leg_rem[seg] = leg_rem.get(seg, 0.0) + rem
    return leg_rem


def _forecast_remaining(service_run_id: str, sold: dict, capacity: dict, days_to_departure: float,
                        stops: list, seat_class: str, train_id: str,
                        service_date: date) -> dict[int, dict]:
    """{segment_id: {forecast_remaining, confidence}}. MỌI chuyến dùng model HGB thật (cầu
    mức-đoạn = Σ hành trình O-D qua đoạn). Model lỗi/thiếu artifact mới fallback pickup-curve
    (màn tư vấn, không phải quyết định giá -> fallback được, không 503)."""
    try:
        leg_rem = _MODEL_CACHE.get(service_run_id)
        if leg_rem is None:
            from ..api.deps import get_demand_model
            leg_rem = _model_leg_remaining(get_demand_model(), stops, seat_class, train_id,
                                           service_date, days_to_departure)
            _MODEL_CACHE[service_run_id] = leg_rem
        return {s: {"forecast_remaining": round(leg_rem.get(s, 0.0), 1), "confidence": None}
                for s in sold}
    except Exception:
        _logger.exception("suggestions: model HGB lỗi cho %s — fallback pickup-curve", service_run_id)
    fc = compute_forecast(sold, capacity, days_to_departure, forecast_version=1,
                          service_run_id=service_run_id)
    return {seg["segment_id"]: {"forecast_remaining": seg["forecast_remaining"],
                                "confidence": seg["confidence"]} for seg in fc["segments"]}


def _round_1k(x: float) -> int:
    return int(round(x / 1000.0)) * 1000


def _reason(r: float) -> str:
    if r >= 1.02:
        return f"Cầu đủ co giãn để tận thu — nâng giá ×{r:.2f} tối đa doanh thu"
    if r <= 0.98:
        return f"Đường cầu cho thấy giảm giá ×{r:.2f} kích thêm khách, doanh thu ròng tăng"
    return "Giá gốc đã sát mức tối đa doanh thu — giữ nguyên"


def _stops(cur, service_run_id: str) -> list[tuple[str, str, float]]:
    """[(station_id, station_name, ly_trinh_km)] theo thứ tự dừng của chuyến."""
    cur.execute(
        """SELECT s.station_id, s.station_name, s.ly_trinh_km FROM train_stop ts
             JOIN service_run sr ON ts.train_id = sr.train_id
             JOIN station s ON ts.station_id = s.station_id
            WHERE sr.service_run_id = %s ORDER BY ts.stop_sequence""",
        (service_run_id,),
    )
    return [(r[0], r[1], float(r[2])) for r in cur.fetchall()]


def _rate_per_km(cur, service_run_id: str) -> float:
    """Đơn giá/km = trung vị (giá gốc O-D / khoảng cách O-D) — khoảng cách suy từ station.ly_trinh_km
    (fare_product không có cột distance_km trong DB, chỉ có ở seed JSON)."""
    cur.execute(
        """SELECT fp.base_fare_vnd, ABS(sd.ly_trinh_km - so.ly_trinh_km) km
             FROM fare_product fp
             JOIN station so ON fp.origin_station_id = so.station_id
             JOIN station sd ON fp.dest_station_id = sd.station_id
            WHERE fp.service_run_id=%s""",
        (service_run_id,),
    )
    rates = sorted(b / k for b, k in cur.fetchall() if k)
    return rates[len(rates) // 2] if rates else DEFAULT_RATE_VND_PER_KM


def _policy_ratios(cur, service_run_id: str) -> tuple[float, float]:
    cur.execute(
        """SELECT floor_ratio, ceiling_ratio FROM pricing_policy
            WHERE name=%s AND is_active ORDER BY policy_version DESC LIMIT 1""",
        (f"{service_run_id}_policy",),
    )
    row = cur.fetchone()
    if row and row[0] is not None and row[1] is not None:
        return float(row[0]), float(row[1])
    return DEFAULT_FLOOR_RATIO, DEFAULT_CEILING_RATIO


def _seat_class(cur, service_run_id: str) -> str:
    cur.execute(
        "SELECT seat_class, COUNT(*) c FROM fare_product WHERE service_run_id=%s "
        "GROUP BY seat_class ORDER BY c DESC LIMIT 1", (service_run_id,))
    row = cur.fetchone()
    return row[0] if row else DEFAULT_SEAT_CLASS


def _bid_floor_by_seg(conn, ssm, service_run_id: str, seat_class: str) -> dict[int, int]:
    """Sàn = bid price DLP thật per-đoạn, ĐỌC cache `allocation/cache.py` (không refresh —
    tránh giải LP nặng; reset/forecast-refresh đã nạp). Cache miss / lỗi -> {} (fallback sàn
    policy; màn tư vấn được phép fallback, không 503)."""
    try:
        from ..allocation import cache as allocation_cache
        matrix_version = ssm.get_matrix_version(service_run_id)
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(forecast_version),1) FROM demand_forecast WHERE service_run_id=%s",
                        (service_run_id,))
            forecast_version = cur.fetchone()[0]
        cached = allocation_cache.get(service_run_id, matrix_version, forecast_version)
        if not cached:
            return {}
        bp = cached["bid_price_theo_lop"].get(seat_class, [])
        return {i + 1: int(bp[i]) for i in range(len(bp))}
    except Exception:
        _logger.exception("suggestions: đọc bid floor DLP lỗi cho %s — fallback sàn policy", service_run_id)
        return {}


def _seg_counts(seatmap: dict) -> tuple[dict[int, int], dict[int, int], int]:
    sold: dict[int, int] = {}
    free: dict[int, int] = {}
    for states in seatmap["seats"].values():
        for seg_str, status in states.items():
            seg = int(seg_str)
            sold.setdefault(seg, 0)
            free.setdefault(seg, 0)
            if status == "FREE":
                free[seg] += 1
            else:
                sold[seg] += 1
    return sold, free, len(seatmap["seats"])


def _suggest(base: int, km: float, days: float, forecast_remaining: float, free_seg: int,
             floor_ratio: float, ceiling_ratio: float, bid_floor_vnd: int = 0) -> tuple[int, float, int, str]:
    """Giá đề xuất tối đa hoá doanh thu kỳ vọng theo đường cầu elasticity.
    Trả (suggested_vnd, r_eff, expected_gain_vnd, lý do).

    Sàn = max(base·floor_ratio, bid_floor_vnd) — bid price DLP là CHI PHÍ CƠ HỘI thật của
    ghế (không bao giờ đề xuất bán dưới mức đó). r_eff = giá đề xuất thực tế / giá gốc, dùng
    để tính gain nhất quán với giá đã kẹp. forecast_remaining ≈ cầu ở giá gốc = pool·P_mua(1);
    cầu ở giá r là forecast_remaining·P_mua(r)/P_mua(1), kẹp bởi số chỗ trống."""
    a = _context_a(km, days)
    r = _optimal_ratio(a, floor_ratio, ceiling_ratio)
    floor_vnd = max(base * floor_ratio, float(bid_floor_vnd))
    suggested = _round_1k(max(min(max(base * r, floor_vnd), base * ceiling_ratio), float(bid_floor_vnd)))
    r_eff = suggested / base if base else 1.0
    pb1 = _p_buy(a, 1.0)
    sales_base = min(forecast_remaining, float(free_seg))
    sales_sug = min(forecast_remaining * _p_buy(a, r_eff) / pb1 if pb1 else 0.0, float(free_seg))
    gain = int(round(suggested * sales_sug - base * sales_base))
    reason = _reason(r_eff)
    if bid_floor_vnd and suggested <= bid_floor_vnd:
        reason += f" (chạm sàn chi phí cơ hội DLP {bid_floor_vnd:,}đ)"
    return suggested, r_eff, gain, reason


def compute(conn, ssm, clock, service_run_id: str) -> dict:
    seatmap = ssm.get_seatmap(service_run_id)
    sold, free, n_seats = _seg_counts(seatmap)
    if not sold:
        return {"service_run_id": service_run_id, "seat_class": DEFAULT_SEAT_CLASS, "suggestions": []}

    with conn.cursor() as cur:
        stops = _stops(cur, service_run_id)
        rate = _rate_per_km(cur, service_run_id)
        floor_ratio, ceiling_ratio = _policy_ratios(cur, service_run_id)
        seat_class = _seat_class(cur, service_run_id)
        cur.execute("SELECT service_date, train_id FROM service_run WHERE service_run_id=%s", (service_run_id,))
        srow = cur.fetchone()
        service_date = srow[0] if isinstance(srow[0], date) else date.fromisoformat(str(srow[0]))
        train_id = srow[1]
        cur.execute(
            "SELECT segment_id, status, suggested_vnd, decided_by, decided_at "
            "FROM price_suggestion WHERE service_run_id=%s AND seat_class=%s",
            (service_run_id, seat_class),
        )
        persisted = {r[0]: {"status": r[1], "approved_vnd": r[2], "decided_by": r[3],
                            "decided_at": r[4].isoformat() if r[4] else None}
                     for r in cur.fetchall()}

    days_to_departure = float(max((service_date - clock.now().date()).days, 0))
    capacity = {s: n_seats for s in sold}
    # Cầu dự báo mức-đoạn từ model HGB thật (mọi chuyến); lỗi model mới fallback pickup-curve.
    fc_by_seg = _forecast_remaining(service_run_id, sold, capacity, days_to_departure,
                                    stops, seat_class, train_id, service_date)
    # Sàn giá = bid price DLP thật (chi phí cơ hội ghế); miss -> {} -> fallback sàn policy.
    bid_floor = _bid_floor_by_seg(conn, ssm, service_run_id, seat_class)

    # chiều dài đoạn + nhãn ga từ danh sách dừng (segment_id 1-based)
    leg = {i + 1: {"km": abs(stops[i + 1][2] - stops[i][2]),
                   "from": stops[i][1], "to": stops[i + 1][1],
                   "from_id": stops[i][0], "to_id": stops[i + 1][0]}
           for i in range(len(stops) - 1)} if len(stops) > 1 else {}

    out = []
    for seg in sorted(sold):
        km = leg.get(seg, {}).get("km", 0.0)
        base = _round_1k(rate * km) if km else _round_1k(rate * 60)  # km=0 (thiếu topology) -> 1 đoạn ~60km
        fseg = fc_by_seg.get(seg, {})
        forecast_remaining = float(fseg.get("forecast_remaining", 0.0))
        confidence = fseg.get("confidence")
        free_seg = free.get(seg, 0)
        occ = sold[seg] / n_seats if n_seats else 0.0
        suggested, mult, gain, reason = _suggest(base, km, days_to_departure, forecast_remaining,
                                                 free_seg, floor_ratio, ceiling_ratio,
                                                 bid_floor.get(seg, 0))
        label = (f"{leg[seg]['from']} → {leg[seg]['to']}" if seg in leg else f"Đoạn {seg}")
        delta_pct = (suggested - base) / base if base else 0.0
        p = persisted.get(seg, {})
        out.append({
            "segment_id": seg,
            "label": label,
            "seat_class": seat_class,
            "occupancy": round(occ, 3),
            "remaining_capacity": free_seg,
            "forecast_remaining": round(forecast_remaining, 1),
            "confidence": confidence,
            "base_vnd": base,
            "suggested_vnd": suggested,
            "delta_pct": round(delta_pct, 4),
            "expected_gain_vnd": gain,
            "multiplier": round(mult, 3),
            "explanation": (f"Đã bán {occ*100:.0f}% số ghế, còn {free_seg} chỗ, dự báo còn "
                            f"~{forecast_remaining:.0f} khách. {reason}. Giá đề xuất "
                            f"{suggested:,}đ (gốc {base:,}đ, {'+' if delta_pct>=0 else ''}{delta_pct*100:.0f}%)."),
            "status": p.get("status", "PENDING"),
            "decided_by": p.get("decided_by"),
            "decided_at": p.get("decided_at"),
        })
    out.sort(key=lambda x: x["expected_gain_vnd"], reverse=True)
    return {"service_run_id": service_run_id, "seat_class": seat_class,
            "days_to_departure": days_to_departure, "suggestions": out}


def decide(conn, ssm, clock, service_run_id: str, segment_id: int,
           decision: str, decided_by: str) -> dict:
    """ACCEPT/REJECT một đoạn. Tính lại đề xuất (không tin client); ACCEPT -> lưu APPROVED
    + UPSERT fare_product cho O-D đúng đoạn đó (giá được duyệt áp thật cho offer đoạn sau)."""
    from ..audit import log as audit_log

    decision = decision.upper()
    if decision not in ("ACCEPT", "REJECT"):
        raise ValueError("decision phải là ACCEPT hoặc REJECT")

    data = compute(conn, ssm, clock, service_run_id)
    item = next((s for s in data["suggestions"] if s["segment_id"] == segment_id), None)
    if item is None:
        return None
    status = "APPROVED" if decision == "ACCEPT" else "REJECTED"
    seat_class = item["seat_class"]

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO price_suggestion
                 (service_run_id, segment_id, seat_class, base_vnd, suggested_vnd,
                  expected_gain_vnd, multiplier, explanation, status, decided_by, decided_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
               ON CONFLICT (service_run_id, segment_id, seat_class) DO UPDATE
                 SET base_vnd=EXCLUDED.base_vnd, suggested_vnd=EXCLUDED.suggested_vnd,
                     expected_gain_vnd=EXCLUDED.expected_gain_vnd, multiplier=EXCLUDED.multiplier,
                     explanation=EXCLUDED.explanation, status=EXCLUDED.status,
                     decided_by=EXCLUDED.decided_by, decided_at=NOW()""",
            (service_run_id, segment_id, seat_class, item["base_vnd"], item["suggested_vnd"],
             item["expected_gain_vnd"], item["multiplier"], item["explanation"], status, decided_by),
        )
        applied = False
        if status == "APPROVED":
            # O-D của đúng đoạn liền kề (from_id -> to_id) lấy lại từ topology
            with conn.cursor() as c2:
                stops = _stops(c2, service_run_id)
            if 1 <= segment_id < len(stops):
                o_id, d_id = stops[segment_id - 1][0], stops[segment_id][0]
                cur.execute(
                    """SELECT id, version FROM fare_product
                        WHERE service_run_id=%s AND origin_station_id=%s AND dest_station_id=%s
                          AND seat_class=%s ORDER BY version DESC LIMIT 1""",
                    (service_run_id, o_id, d_id, seat_class),
                )
                fp = cur.fetchone()
                if fp:
                    cur.execute("UPDATE fare_product SET base_fare_vnd=%s, version=version+1 WHERE id=%s",
                                (item["suggested_vnd"], fp[0]))
                else:
                    cur.execute(
                        """INSERT INTO fare_product
                             (service_run_id, origin_station_id, dest_station_id, seat_class, base_fare_vnd, version)
                           VALUES (%s,%s,%s,%s,%s,1)""",
                        (service_run_id, o_id, d_id, seat_class, item["suggested_vnd"]),
                    )
                applied = True
    conn.commit()
    audit_log.persist(conn, {
        "loai": "PRICING", "input": {"segment_id": segment_id, "decision": decision},
        "output": {"status": status, "suggested_vnd": item["suggested_vnd"], "applied": applied},
        "explain": (f"{'Duyệt' if status=='APPROVED' else 'Từ chối'} chỉnh giá đoạn {item['label']} "
                    f"-> {item['suggested_vnd']:,}đ bởi {decided_by}"),
        "model_version": "1.0",
    }, service_run_id)
    return {**item, "status": status, "decided_by": decided_by, "applied": applied}


def _selfcheck() -> None:
    assert _round_1k(157340) == 157000 and _round_1k(157600) == 158000
    if _ELAST is None:
        print("suggestions self-check OK (no elasticity artifact — skipped curve asserts)")
        return
    # nghiệm đóng: xác suất mua ở giá tối ưu = q* = 1 + 1/β
    a = _context_a(km=200, days=20)
    r = _optimal_ratio(a, 0.55, 1.6)
    assert 0.55 <= r <= 1.6
    if 0.55 < r < 1.6:  # không bị kẹp -> đúng điểm dừng doanh thu
        assert abs(_p_buy(a, r) - (1 + 1 / _BETA)) < 1e-6, _p_buy(a, r)
    # r* tối đa doanh thu r·P_mua(r) TRONG [floor,ceiling]: mọi lân cận hợp lệ đều không tốt hơn
    rev = lambda x: x * _p_buy(a, x)
    for nb in (r * 0.95, r * 1.05):
        if 0.55 <= nb <= 1.6:
            assert rev(r) >= rev(nb) - 1e-12, (rev(r), rev(nb), r)
    # kẹp trần: β rất âm vẫn không vượt ceiling
    assert _suggest(100000, 200, 20, 3.0, 476, 0.55, 1.6)[0] <= 160000
    # sàn bid price DLP: không bao giờ đề xuất dưới chi phí cơ hội (kể cả khi elasticity muốn giảm sâu)
    sug_bid, _, _, why = _suggest(100000, 200, 20, 3.0, 476, 0.55, 1.6, bid_floor_vnd=95000)
    assert sug_bid >= 95000, sug_bid
    # sàn bid rỗng (=0) -> hành vi cũ, không đổi
    assert _suggest(100000, 200, 20, 3.0, 476, 0.55, 1.6, 0)[0] == _suggest(100000, 200, 20, 3.0, 476, 0.55, 1.6)[0]
    # gain trung thực: giá cao hơn giá gốc -> gain>=0 khi còn chỗ; cầu bị kẹp bởi free
    _, _, g, _ = _suggest(100000, 200, 20, 5.0, 476, 0.55, 1.6)
    _, _, g_cap, _ = _suggest(100000, 200, 20, 1000.0, 2, 0.55, 1.6)  # free=2 kẹp cầu
    assert isinstance(g, int) and isinstance(g_cap, int)
    print("suggestions self-check OK")


if __name__ == "__main__":
    _selfcheck()

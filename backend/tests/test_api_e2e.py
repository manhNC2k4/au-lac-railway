# -*- coding: utf-8 -*-
"""BỘ TEST API END-TO-END — gọi qua HTTP thật (FastAPI TestClient), phủ 11/11 endpoint
+ mọi mã lỗi trong openapi.yaml. Mỗi test = một tình huống, payload ĐIỀN CỤ THỂ ngay
trong code (xem comment "ĐIỀN:" ở mỗi request) để làm tài liệu sống cho ai gọi API tay.

CÁCH CHẠY
---------
    cd backend
    docker compose up -d db flyway          # cần Postgres + schema (Flyway V1/V2) sẵn
    pip install -r requirements.txt         # fastapi, httpx, pytest... đã có sẵn
    pytest tests/test_api_e2e.py -v

TestClient chạy app trong tiến trình (không cần `uvicorn` riêng) nhưng đi qua đúng
routing + exception handler + Postgres thật — tương đương gọi HTTP thật, không phải
gọi hàm nội bộ. Mỗi test tự `POST /reset` (fixture `scenario`) nên chạy độc lập,
thứ tự nào cũng được.

BẢN ĐỒ PHỦ (endpoint / mã lỗi → test)
-------------------------------------
  POST /demo/scenarios/{id}/reset ......... test_reset_deterministic
  GET  /demo/seatmap ...................... test_seatmap_golden_gap
  GET  /demo/overview .................... test_overview_shape
  GET  /demo/analytics .................. test_analytics_shape
  POST /demo/forecasts/refresh .......... test_forecast_refresh_bumps_version
  POST /offers (201 ACCEPT, gap) ........ test_offer_golden_gap_accept
  POST /offers (201 ACCEPT, ghế thường) . test_offer_plain_seat_accept
  POST /offers (422 NO_SAME_SEAT) ....... test_offer_no_same_seat_option
  POST /offers (422 O-D sai thứ tự) ..... test_offer_reversed_od
  POST /offers (422 ga lạ) .............. test_offer_unknown_station
  POST /holds (201 ACTIVE) .............. test_hold_happy_path
  POST /holds (idempotent) .............. test_hold_idempotent
  POST /holds (409 STALE_SNAPSHOT) ...... test_hold_stale_snapshot
  POST /holds (410 OFFER_EXPIRED) ....... test_hold_offer_expired
  POST /bookings/{id}/confirm (200) ..... test_confirm_happy_path
  POST /bookings/{id}/confirm (idempo) .. test_confirm_idempotent
  POST /bookings/{id}/confirm (410) ..... test_confirm_hold_expired / test_confirm_unknown_hold
  GET  /decisions/{id} (200 / 404) ...... test_decision_detail / test_decision_not_found
  POST /backtests + GET (202/200) ....... test_backtest_run_and_report
  GET  /backtests/{id} (404) ............ test_backtest_report_not_found

GHI CHÚ về 2 mã lỗi KHÔNG dựng được qua API công khai với seed hiện tại (cố ý, không phải thiếu sót):
  • SEAT_CONFLICT: mọi thao tác chiếm ghế đều bump matrix_version toàn cục, nên lần
    hold thứ hai luôn dính STALE_SNAPSHOT (khoá lạc quan) TRƯỚC khi tới bước kiểm ghế.
    SEAT_CONFLICT là lớp phòng thủ sâu ở tầng manager — đã có test riêng ở
    tests/test_state_cas.py. Xem test_hold_stale_snapshot (chứng minh khoá version chặn trước).
  • POLICY_UNAVAILABLE / ALLOCATION_REJECTED: với seed vàng (lead=0 → chạm trần 1.6×F0,
    bid các leg thấp) mọi ghế tìm được đều có giá ≥ Σbid ⇒ luôn ACCEPT; và policy luôn
    được nạp lúc reset. Hai nhánh này có test đơn vị ở tầng engine (test_offer.py/test_pricing.py).
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import app
from src.state.clock import Clock, FixedClock

from tests.conftest import insert_test_offer

BASE = "/api/v1"
SCENARIO_ID = "golden_scenario_1"
SERVICE_RUN_ID = "SE1_2026-06-15_LE"
SEAT_CLASS = "NGOI_MEM_DH"
# Đồng hồ demo = scenario.json.demo_clock. Ngày chạy TRÙNG ngày phục vụ ⇒ lead_time=0
# ⇒ luật giờ chót R_GIO_CHOT (+70%) bắn, vượt trần ⇒ guardrail clamp về TRAN (1.6×F0).
DEMO_CLOCK = datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc)

# `with` bắt buộc — kích hoạt lifespan (load_models: Pricer/DemandModel), thiếu nó
# get_pricer()/allocation_cache.refresh() luôn 503 giả (fail-closed nhưng sai lý do).
_client_cm = TestClient(app)
client = _client_cm.__enter__()


def _key() -> str:
    """Idempotency-Key mới cho mỗi thao tác ghi (client tự sinh, openapi yêu cầu uuid)."""
    return str(uuid.uuid4())


@pytest.fixture
def scenario():
    """Cài đồng hồ demo cố định + reset kịch bản vàng qua API TRƯỚC mỗi test.
    Trả (clock, reset_data) — test cần chứng minh hết hạn thì tự `.advance(giây)`."""
    fixed = FixedClock(DEMO_CLOCK)
    deps.set_clock(fixed)
    r = client.post(f"{BASE}/demo/scenarios/{SCENARIO_ID}/reset",
                    json={"reset_clock": True, "apply_golden_gap": True})  # ĐIỀN: cờ reset (tuỳ chọn)
    assert r.status_code == 200, r.text
    yield fixed, r.json()["data"]
    deps.set_clock(Clock())  # trả lại đồng hồ thật, không rò trạng thái sang test khác


def _create_offer(origin: str, dest: str, quantity: int = 1, priority_passenger: bool = False):
    """POST /offers — ĐIỀN 5 trường bắt buộc theo OfferRequest."""
    return client.post(f"{BASE}/offers", json={
        "service_run_id": SERVICE_RUN_ID,   # ĐIỀN: chuyến tàu
        "origin_station_id": origin,        # ĐIỀN: ga đi (mã 3 ký tự, vd THO)
        "dest_station_id": dest,            # ĐIỀN: ga đến (vd DHO)
        "seat_class": SEAT_CLASS,           # ĐIỀN: hạng ghế
        "quantity": quantity,               # ĐIỀN: số vé (>=1)
        "priority_passenger": priority_passenger,  # ĐIỀN: cao tuổi/khuyết tật -> không bao giờ ghép ghế (P5)
    })


# ---------------------------------------------------------------------------
# 1. DEMO / read-only
# ---------------------------------------------------------------------------
def test_reset_deterministic(scenario):
    _clock, data = scenario
    assert data["service_run_id"] == SERVICE_RUN_ID
    assert data["matrix_version"] == 1
    assert data["forecast_version"] == 1
    assert data["policy_version"] == 1
    first_checksum = data["checksum"]

    # Reset lần 2 cùng seed ⇒ CÙNG checksum (demo tất định — bấm lại bao nhiêu lần cũng như nhau)
    r2 = client.post(f"{BASE}/demo/scenarios/{SCENARIO_ID}/reset", json={})
    assert r2.status_code == 200
    assert r2.json()["data"]["checksum"] == first_checksum


def test_seatmap_golden_gap(scenario):
    r = client.get(f"{BASE}/demo/seatmap", params={"service_run_id": SERVICE_RUN_ID})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["matrix_version"] == 1
    seats = {s["seat_id"]: s["states"] for s in data["seats"]}
    assert len(seats) == 40                              # đủ 40 ghế NGOI_MEM_DH
    gap = seats["C01-S017"]                              # GHẾ VÀNG: bán đầu+cuối, trống giữa
    assert gap["1"] == "SOLD" and gap["2"] == "SOLD"     # HNO→THO đã bán
    assert gap["3"] == "FREE" and gap["4"] == "FREE"     # THO→DHO TRỐNG ← chính là golden gap
    assert gap["5"] == "SOLD" and gap["7"] == "SOLD"     # DHO→SGO đã bán
    classes = {s["seat_id"]: s["seat_class"] for s in data["seats"]}
    assert classes["C01-S017"] == SEAT_CLASS             # id golden ko khớp <lớp>-<4 số> ⇒ fallback


def test_seat_class_of_derives_mock_loader_prefix():
    """seat_id kiểu <agg_class>-<4 số> (backend/scripts/load_mock_from_dataset.py::seat_id_of)
    phải trả đúng agg_class; id golden (C01-S017) phải fallback về SEAT_CLASS scenario."""
    from src.api.routes_demo import SEAT_CLASS as _SC, _seat_class_of

    assert _seat_class_of("NAM_K6-0012") == "NAM_K6"
    assert _seat_class_of("NGOI_MEM_DH-0004") == "NGOI_MEM_DH"
    assert _seat_class_of("C01-S017") == _SC


def test_overview_shape(scenario):
    r = client.get(f"{BASE}/demo/overview", params={"service_run_id": SERVICE_RUN_ID})
    assert r.status_code == 200
    d = r.json()["data"]
    for field in ("overall_occupancy", "total_revenue_vnd", "passenger_km",
                  "false_sold_out_rate", "bottlenecks", "underused", "recent_decisions"):
        assert field in d
    assert d["total_revenue_vnd"] == 0        # chưa confirm vé nào ⇒ doanh thu 0
    assert 0.0 <= d["overall_occupancy"] <= 1.0


def test_analytics_shape(scenario):
    r = client.get(f"{BASE}/demo/analytics", params={"service_run_id": SERVICE_RUN_ID})
    assert r.status_code == 200
    d = r.json()["data"]
    assert len(d["forecasts"]) == 7           # 7 đoạn
    assert len(d["segment_loads"]) == 7
    assert len(d["allocations"]) == 7
    assert all(a["bid_price_vnd"] >= 0 for a in d["allocations"])


def test_forecast_refresh_bumps_version(scenario):
    r = client.post(f"{BASE}/demo/forecasts/refresh",
                    json={"service_run_id": SERVICE_RUN_ID})   # ĐIỀN: chuyến cần refresh
    assert r.status_code == 200
    assert r.json()["data"]["forecast_version"] == 2   # bản MỚI, không sửa bản cũ


# ---------------------------------------------------------------------------
# 2. OFFERS — pipeline lõi (resolver → pricing → so bid)
# ---------------------------------------------------------------------------
def test_offer_golden_gap_accept(scenario):
    """KỊCH BẢN HERO: THO→DHO — hệ thống truyền thống báo hết chỗ, Âu Lạc bán trên ghế vàng."""
    r = _create_offer("THO", "DHO")     # ĐIỀN: đúng cặp ga của golden gap
    assert r.status_code == 201, r.text
    d = r.json()["data"]

    # Chọn đúng ghế vàng (best-fit: khít nhất, 0 ô thừa) và nhận diện là tái dùng khoảng trống
    assert d["decision"] == "ACCEPT"
    plan = d["seat_plan"][0]
    assert plan["seat_id"] == "C01-S017"
    assert plan["segment_from"] == 3 and plan["segment_to"] == 4
    assert plan["reused_gap"] is True

    # Giá: F0=285.000đ; mùa hè thật (+7.5%, bt5_pricing_params.json) → elasticity optimizer
    # (r≈1.08, tối đa P(mua)·(p−c) với c=Σbid=0) ⇒ 307.000đ (P3 — không còn R_GIO_CHOT bịa
    # ×1.7 để ép vượt trần; DoD "guardrail clamp thật" nay là unit test
    # test_guardrail_order_floor_ceiling_delta_round_freeze, chạy trực tiếp apply_guardrail).
    p = d["pricing"]
    assert p["gia_goc_vnd"] == 285000
    assert p["gia_niem_yet_vnd"] == 307000
    assert p["gia_cuoi_vnd"] == 307000        # không có CSXH (API chưa nhận trường hành khách)
    assert p["clamped"] is False              # trong biên [san,tran], không chạm guardrail
    assert p["che_do_gia"] == "AI"

    # Bid = dual LP thật (app.bt3_allocation): seg 3-4 có cầu (3.6/16.2) < sức chứa còn
    # lại (19/28) ⇒ KHÔNG nghẽn ⇒ dual=0 hợp lý (khác công thức scarcity cũ luôn >0).
    # ACCEPT ở đây đến từ trần giá (456.000đ) bù đủ Σbid=0, không phải từ bid dương.
    assert d["bid"]["total_vnd"] >= 0
    assert d["matrix_version"] == 1 and d["forecast_version"] == 1 and d["policy_version"] == 1
    assert d["decision_record_id"].startswith("dr_")


def test_offer_plain_seat_accept(scenario):
    """Ghế bình thường (không phải gap) vẫn phục vụ được — HNO→NBI (đoạn 1)."""
    r = _create_offer("HNO", "NBI")     # ĐIỀN: chặng ngắn đầu tuyến
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["decision"] == "ACCEPT"
    assert d["seat_plan"][0]["seat_id"].startswith("C01-S")
    assert d["pricing"]["gia_goc_vnd"] == 109000    # F0 HNO→NBI


def test_offer_no_same_seat_option(scenario):
    """THO→HUE (đoạn 3-4-5): KHÔNG ghế nào trống liên tục cả 3 đoạn. P5 cho hành khách
    thường ghép nhiều ghế nên bình thường sẽ ACCEPT (xem test_offer_multiseat_when_same_seat_empty)
    — dùng priority_passenger=True (không bao giờ đổi ghế) để vẫn dựng được 422 qua API công khai."""
    r = _create_offer("THO", "HUE", priority_passenger=True)
    assert r.status_code == 422
    assert r.json()["error_code"] == "NO_SAME_SEAT_OPTION"


def test_offer_multiseat_when_same_seat_empty(scenario):
    """P5 · THO→HUE không có same-seat nhưng ghép nhiều ghế tìm được phương án ⇒ 201,
    requires_customer_consent=True, so_lan_doi_cho khớp số leg-1."""
    r = _create_offer("THO", "HUE")
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["requires_customer_consent"] is True
    assert d["so_lan_doi_cho"] >= 1
    assert len(d["seat_plan"]) == d["so_lan_doi_cho"] + 1
    assert all(leg["requires_seat_change"] for leg in d["seat_plan"])


def test_offer_reversed_od(scenario):
    """Ga đến đứng TRƯỚC ga đi theo lý trình ⇒ 422 (đầu vào vô lý, chặn sớm)."""
    r = _create_offer("DHO", "THO")     # ĐIỀN: cố tình đảo ngược
    assert r.status_code == 422
    assert r.json()["error_code"] == "NO_SAME_SEAT_OPTION"


def test_offer_unknown_station(scenario):
    r = _create_offer("XXX", "SGO")     # ĐIỀN: mã ga không tồn tại trên tuyến
    assert r.status_code == 422
    assert r.json()["error_code"] == "NO_SAME_SEAT_OPTION"


# ---------------------------------------------------------------------------
# 3. HOLDS — giữ ghế nguyên tử (CAS)
# ---------------------------------------------------------------------------
def _offer_then_hold(origin="THO", dest="DHO", expected_version=1, key=None):
    offer = _create_offer(origin, dest).json()["data"]
    key = key or _key()
    resp = client.post(f"{BASE}/holds",
                       headers={"Idempotency-Key": key},   # ĐIỀN header: khoá chống gửi trùng
                       json={
                           "offer_id": offer["offer_id"],          # ĐIỀN: id offer vừa tạo
                           "expected_matrix_version": expected_version,  # ĐIỀN: version đọc từ offer
                           "passenger_name": "Nguyễn Văn A",       # ĐIỀN: tên khách (tuỳ chọn)
                       })
    return offer, key, resp


def test_hold_happy_path(scenario):
    _offer, _key_, resp = _offer_then_hold(expected_version=1)
    assert resp.status_code == 201, resp.text
    d = resp.json()["data"]
    assert d["status"] == "ACTIVE"
    assert d["new_matrix_version"] == 2        # giữ ghế xong ⇒ version toàn cục +1
    assert d["hold_id"].startswith("hold_")


def test_hold_idempotent(scenario):
    """Gửi lại đúng Idempotency-Key (vd client mất mạng rồi thử lại) ⇒ trả HOLD CŨ, không giữ 2 lần."""
    offer, key, resp1 = _offer_then_hold(expected_version=1)
    assert resp1.status_code == 201
    resp2 = client.post(f"{BASE}/holds", headers={"Idempotency-Key": key},
                        json={"offer_id": offer["offer_id"], "expected_matrix_version": 1})
    assert resp2.status_code == 201
    assert resp2.json()["data"]["hold_id"] == resp1.json()["data"]["hold_id"]


def test_hold_stale_snapshot(scenario):
    """expected_matrix_version SAI (client cầm bản chụp cũ) ⇒ 409 STALE_SNAPSHOT.
    Đây cũng là lý do SEAT_CONFLICT không tới được qua API: khoá version chặn trước."""
    offer = _create_offer("THO", "DHO").json()["data"]
    resp = client.post(f"{BASE}/holds", headers={"Idempotency-Key": _key()},
                       json={"offer_id": offer["offer_id"],
                             "expected_matrix_version": 999})   # ĐIỀN: version lệch thực tế
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "STALE_SNAPSHOT"


def test_hold_multiseat_requires_consent(scenario, conn):
    """P5 · offer với seat_plan >=2 leg (ghép nhiều ghế) -> /holds thiếu consent=True
    trả 422 CONSENT_REQUIRED; gửi lại kèm consent=True thì giữ được cả 2 ghế cùng lúc."""
    clock, _ = scenario
    seat_plan = json.dumps([
        {"seat_id": "C01-S001", "segment_from": 3, "segment_to": 3,
         "reused_gap": False, "requires_seat_change": True},
        {"seat_id": "C01-S002", "segment_from": 4, "segment_to": 4,
         "reused_gap": False, "requires_seat_change": True},
    ])
    offer_id = "offer_e2e_multiseat"
    insert_test_offer(conn, offer_id, SERVICE_RUN_ID, clock.now() + timedelta(minutes=5),
                      seat_plan=seat_plan)

    resp = client.post(f"{BASE}/holds", headers={"Idempotency-Key": _key()},
                       json={"offer_id": offer_id, "expected_matrix_version": 1})
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "CONSENT_REQUIRED"

    resp2 = client.post(f"{BASE}/holds", headers={"Idempotency-Key": _key()},
                        json={"offer_id": offer_id, "expected_matrix_version": 1, "consent": True})
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["data"]["status"] == "ACTIVE"


def test_hold_offer_expired(scenario):
    """Offer sống 15 phút. Tua đồng hồ qua mốc đó rồi mới giữ ⇒ 410 OFFER_EXPIRED."""
    clock, _ = scenario
    offer = _create_offer("THO", "DHO").json()["data"]
    clock.advance(901)   # +15 phút 1 giây — quá hạn offer (OFFER_TTL_SECONDS=900)
    resp = client.post(f"{BASE}/holds", headers={"Idempotency-Key": _key()},
                       json={"offer_id": offer["offer_id"], "expected_matrix_version": 1})
    assert resp.status_code == 410
    assert resp.json()["error_code"] == "OFFER_EXPIRED"


# ---------------------------------------------------------------------------
# 4. CONFIRM — chốt HELD→SOLD (không tính lại giá)
# ---------------------------------------------------------------------------
def test_confirm_happy_path(scenario):
    _offer, _key_, hold_resp = _offer_then_hold(expected_version=1)
    hold_id = hold_resp.json()["data"]["hold_id"]
    resp = client.post(f"{BASE}/bookings/{hold_id}/confirm",
                       headers={"Idempotency-Key": _key()})   # ĐIỀN header (không cần body)
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["status"] == "CONFIRMED"
    assert d["booking_id"].startswith("bk_")
    assert d["final_price_vnd"] == 307000       # ĐÚNG giá đã chốt lúc offer (P3 elasticity), không đổi

    # Xác minh phụ: ghế vàng giờ đã SOLD ở đoạn 3-4
    seatmap = client.get(f"{BASE}/demo/seatmap", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]
    gap = {s["seat_id"]: s["states"] for s in seatmap["seats"]}["C01-S017"]
    assert gap["3"] == "SOLD" and gap["4"] == "SOLD"


def test_confirm_idempotent(scenario):
    _offer, _key_, hold_resp = _offer_then_hold(expected_version=1)
    hold_id = hold_resp.json()["data"]["hold_id"]
    r1 = client.post(f"{BASE}/bookings/{hold_id}/confirm", headers={"Idempotency-Key": _key()})
    r2 = client.post(f"{BASE}/bookings/{hold_id}/confirm", headers={"Idempotency-Key": _key()})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["data"]["booking_id"] == r2.json()["data"]["booking_id"]   # không tạo vé thứ 2


def test_confirm_hold_expired(scenario):
    """Giữ ghế 10 phút không thanh toán ⇒ tự hết hạn ⇒ confirm trả 410 HOLD_EXPIRED."""
    clock, _ = scenario
    _offer, _key_, hold_resp = _offer_then_hold(expected_version=1)
    hold_id = hold_resp.json()["data"]["hold_id"]
    clock.advance(601)   # +10 phút 1 giây — quá hạn hold (HOLD_TTL_SECONDS=600)
    resp = client.post(f"{BASE}/bookings/{hold_id}/confirm", headers={"Idempotency-Key": _key()})
    assert resp.status_code == 410
    assert resp.json()["error_code"] == "HOLD_EXPIRED"


def test_confirm_unknown_hold(scenario):
    resp = client.post(f"{BASE}/bookings/hold_khong_ton_tai/confirm",
                       headers={"Idempotency-Key": _key()})   # ĐIỀN: hold_id bịa
    assert resp.status_code == 410
    assert resp.json()["error_code"] == "HOLD_EXPIRED"


# ---------------------------------------------------------------------------
# 5. DECISIONS — nhật ký/giải trình
# ---------------------------------------------------------------------------
def test_decision_detail(scenario):
    offer = _create_offer("THO", "DHO").json()["data"]
    dr_id = offer["decision_record_id"]
    resp = client.get(f"{BASE}/decisions/{dr_id}")
    assert resp.status_code == 200
    d = resp.json()["data"]
    assert d["decision_id"] == dr_id
    assert d["action"] == "ACCEPT"
    assert d["base_fare"] == 285000
    assert d["final_price"] == 307000  # P3: mùa hè thật + elasticity optimizer (không còn R_GIO_CHOT bịa)
    assert d["bid_price_total"] >= 0   # DLP thật: seg 3-4 không nghẽn ⇒ dual=0 hợp lý
    assert isinstance(d["violations"], list)   # [] — không chạm guardrail (clamp có unit test riêng)


def test_decision_not_found(scenario):
    resp = client.get(f"{BASE}/decisions/dr_khong_ton_tai")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# 6. BACKTESTS — bằng chứng định lượng baseline vs Âu Lạc
# ---------------------------------------------------------------------------
def test_backtest_run_and_report(scenario):
    start = client.post(f"{BASE}/backtests", json={
        "event_stream_id": "stream_demo_1",     # ĐIỀN: nhãn luồng sự kiện (metadata)
        "seeds": ["20260717", "20260718", "20260719", "20260720", "20260721"],  # ĐIỀN: 5 seed đã commit
    })
    assert start.status_code == 202
    report_id = start.json()["data"]["report_id"]
    assert report_id.startswith("bt_")

    got = client.get(f"{BASE}/backtests/{report_id}")
    assert got.status_code == 200
    d = got.json()["data"]
    assert d["status"] == "COMPLETED"
    assert sorted(d["seeds_run"]) == [20260717, 20260718, 20260719, 20260720, 20260721]
    assert d["failed_seeds"] == []
    # Luận điểm cốt lõi: cùng chuỗi yêu cầu, Âu Lạc thu > baseline (tái dùng gap + giá linh hoạt)
    assert d["ai_metrics"]["revenue_median"] > d["baseline_metrics"]["revenue_median"]
    assert len(d["checksum"]) == 64   # sha256 hex — báo cáo không sửa được mà không lộ


def test_backtest_report_not_found(scenario):
    resp = client.get(f"{BASE}/backtests/bt_khong_ton_tai")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "RESOURCE_NOT_FOUND"

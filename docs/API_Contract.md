# Hợp đồng Giao tiếp API (API Contract) - Âu Lạc Railway (MVP 30h)

Tài liệu này đặc tả chi tiết các endpoints giao tiếp giữa Frontend (FE) và Backend (BE). Mọi request đều tuân theo chuẩn RESTful.

> ⚠️ **Nguồn chân lý cuối cùng là `backend/openapi.yaml`.** File này đã đối chiếu lại với code thật (`backend/src/api/`) ngày 18/07/2026, cập nhật thêm mục 6/7/8 + §3.4 sau khi P7 (tính năng vận hành: phân bổ/duyệt/rollback, hàng chờ, xếp nhóm, ghi đè giá) merge — mọi ví dụ JSON dưới đây là **output thật** chạy qua `TestClient`, không phải minh họa tay. Nếu có mâu thuẫn, `openapi.yaml` thắng.

## 1. Thông tin chung
- **Base URL:** `/api/v1`
- **Content-Type mặc định:** `application/json`
- **Quy ước dữ liệu (khóa cứng, mọi module tuân theo):**
  - **Segment/leg đánh số 1-based:** `L1..L7` (L1 = HNO→NBI, …, L7 = DNA→SGO). `segment_id ∈ {1..7}`. `seat_plan` dùng `[segment_from, segment_to]` **bao gồm cả hai đầu** (golden gap THO→DHO = L3..L4).
  - **Định dạng seat_id:** `C{toa 2 chữ số}-S{ghế 3 chữ số}`, ví dụ `C01-S001` … `C01-S040`. Golden seat = `C01-S017`.
  - Tiền: **số nguyên VND (int64)**, làm tròn 1.000 đ. Timestamp: ISO-8601 UTC, theo **demo clock** của scenario (ngày chạy 2026-06-15), không phải giờ thật.
  - Mọi thao tác ghi (`POST /holds`, `POST /bookings/.../confirm`) yêu cầu header `Idempotency-Key`.
- **Xử lý Lỗi Chuẩn (Error Response Format):**
  ```json
  {
    "error_code": "STRING_CODE",
    "message": "Chi tiết lỗi bằng tiếng Việt",
    "details": {} // (Optional) Thông tin debug thêm
  }
  ```
  - `404 Not Found`: Không tìm thấy resource (`GET /backtests/{id}`, `GET /decisions/{id}` không tồn tại) — trả `error_code: "RESOURCE_NOT_FOUND"`.
  - `409 Conflict`: Xung đột trạng thái (stale version, mất ghế).
  - `410 Gone`: Resource đã hết hạn (Offer/Hold expired).
  - `422 Unprocessable Entity`: Dữ liệu đúng định dạng nhưng vi phạm logic nghiệp vụ.
  - `503 Service Unavailable`: Policy/model bắt buộc không sẵn sàng. **Không bao giờ im lặng dùng giá/bid mặc định** (fail-closed).
- **Bộ reason code chuẩn (`error_code`) — khớp `src/state/errors.py`:**

  | Code | HTTP | Ý nghĩa |
  |---|---|---|
  | `NO_SAME_SEAT_OPTION` | 422 | Không tìm được ghế liên tục (same-seat) **và** không ghép được nhiều ghế cho hành trình |
  | `SOLD_OUT_TRUE` | 422 | Hết chỗ thật (mọi ghế đều bận) |
  | `ALLOCATION_REJECTED` | 422 | Giá offer < Σ bid-price các leg (từ chối theo quota) |
  | `CONSENT_REQUIRED` | 422 | **(P5, mới)** `seat_plan` có ≥2 leg (ghép nhiều ghế) nhưng `POST /holds` không kèm `consent: true` |
  | `STALE_SNAPSHOT` | 409 | `expected_matrix_version` không khớp |
  | `SEAT_CONFLICT` | 409 | Ghế vừa bị người khác giữ/mua |
  | `OFFER_EXPIRED` | 410 | Offer quá `expires_at` |
  | `HOLD_EXPIRED` | 410 | Hold quá hạn thanh toán, ghế đã tự release |
  | `POLICY_UNAVAILABLE` | 503 | Pricing policy / forecast / DLP bid-price chưa sẵn sàng — fail closed |
  | `RESOURCE_NOT_FOUND` | 404 | Không tìm thấy resource (`GET /backtests/{id}`, `GET /decisions/{id}`, `GET /allocation/{version}`) |
  | `FORBIDDEN` | 403 | **(P7.2/P7.6, mới)** Header `X-Actor-Role` không phải `revenue_manager`/`admin` cho thao tác duyệt/ghi đè |
  | `GUARDRAIL_VIOLATION` | 422 | **(P7.6, mới)** Giá override nằm ngoài dải `[floor_ratio, ceiling_ratio] × F0` |

---

## 2. API Quản trị Demo & Ops Dashboard (Dành cho Admin)

### 2.1. Khởi tạo Kịch bản Demo
**`POST /demo/scenarios/{scenario_id}/reset`**

Nạp dữ liệu giả định ban đầu, reset lại ma trận ghế và đồng hồ hệ thống. `scenario_id` trên path hiện **không được dùng để chọn kịch bản** (luôn nạp golden scenario `SE1_2026-06-15_LE` từ `backend/seed/`) — chỉ giữ chỗ cho path REST, giá trị nào cũng được chấp nhận.

- **Request Body** (tùy chọn, có default):
  ```json
  { "reset_clock": true, "apply_golden_gap": true }
  ```
- **Response (200 OK)** — output thật:
  ```json
  {
    "data": {
      "service_run_id": "SE1_2026-06-15_LE",
      "matrix_version": 1,
      "forecast_version": 1,
      "policy_version": 1,
      "checksum": "9a3524bcc8f32d7933637602921909ff093d9cbe179d561288a8edb9e00c3447"
    },
    "message": "Scenario reset successfully"
  }
  ```
- **Ràng buộc:** không partial load — scenario lỗi thì từ chối toàn bộ (rollback), state đang chạy giữ nguyên. Cùng seed ⇒ cùng checksum (reset deterministic). Reset cũng tự làm mới cache bid-price DLP (`allocation/cache.py`) cho version mới.

### 2.2. Làm mới Dự báo
**`POST /demo/forecasts/refresh`**

Tính lại dự báo còn lại theo cơ chế `DemandModel.update` (unconstrain từ số đã bán thật + blend với seed) — KHÔNG dùng model HGB dự báo trực tiếp golden 40 ghế (model train ở grain 22 ga/448 chỗ, chỉ cấp *cơ chế* cập nhật/divergence).

- **Request Body:**
  ```json
  { "service_run_id": "SE1_2026-06-15_LE" }
  ```
- **Response (200 OK):**
  ```json
  { "message": "Forecast updated", "data": { "forecast_version": 2 } }
  ```
- Refresh cũng làm mới cache bid-price DLP theo `forecast_version` mới — `POST /offers` gọi ngay sau refresh sẽ dùng bid mới.

### 2.3. Dashboard Tổng quan
**`GET /demo/overview`**

- **Query Parameters:** `service_run_id` (string, required)
- **Response (200 OK)** — output thật (sau 1 golden booking):
  ```json
  {
    "data": {
      "overall_occupancy": 0.4,
      "total_revenue_vnd": 307000,
      "empty_seat_km": 38607.0,
      "passenger_km": 30433.0,
      "false_sold_out_rate": 0.0,
      "bottlenecks": [
        { "segment_id": 3, "occupancy": 0.55 },
        { "segment_id": 5, "occupancy": 0.475 },
        { "segment_id": 6, "occupancy": 0.475 }
      ],
      "underused": [
        { "segment_id": 1, "occupancy": 0.25 },
        { "segment_id": 2, "occupancy": 0.25 },
        { "segment_id": 4, "occupancy": 0.325 }
      ],
      "recent_decisions": [
        { "decision_id": "dr_edfab201f59b", "result": "ACCEPT", "final_price_vnd": 307000,
          "explanation_code": "ACCEPT_BID_COVERED", "created_at": "2026-06-15T09:00:00+00:00" }
      ]
    }
  }
  ```
  ⚠️ Khác bản draft cũ: key trong `recent_decisions` là **`result`** (không phải `action`), và không có field `name` trong `bottlenecks`/`underused` (chỉ `segment_id` + `occupancy`) — FE tự tra tên ga từ `segment_id` qua `GET /demo/seatmap` hoặc bảng tĩnh 8 ga.

### 2.4. Ma trận Ghế × Đoạn (Heatmap)
**`GET /demo/seatmap`**

- **Query Parameters:** `service_run_id` (string, required)
- **Response (200 OK):**
  ```json
  {
    "data": {
      "matrix_version": 2,
      "seats": [
        { "seat_id": "C01-S017", "seat_class": "NGOI_MEM_DH",
          "states": { "1": "SOLD", "2": "SOLD", "3": "SOLD", "4": "SOLD", "5": "SOLD", "6": "SOLD", "7": "SOLD" } }
      ]
    }
  }
  ```
  ⚠️ Khác bản draft cũ: **không có field `reused_gap_segments`** trong mỗi ghế — `reused_gap` chỉ xuất hiện trong `seat_plan` của response `POST /offers` (nhãn tại thời điểm resolve, không phải thuộc tính tĩnh của ghế). FE tự tô màu "khoảng trống vàng" bằng cách so `states` với dải request gần nhất nếu cần.

### 2.5. Phân tích Dự báo và Phân bổ
**`GET /demo/analytics`**

- **Query Parameters:** `service_run_id` (string, required)
- **Response (200 OK):**
  ```json
  {
    "data": {
      "forecast_version": 1,
      "forecasts": [
        { "segment_id": 1, "forecast_remaining": 5.0, "confidence": 0.74 }
      ],
      "segment_loads": [
        { "segment_id": 1, "occupancy": 0.25, "remaining_capacity": 30 }
      ],
      "allocations": [
        { "segment_id": 1, "bid_price_vnd": 0 }
      ]
    }
  }
  ```
  ⚠️ Khác bản draft cũ: không có `origin`/`dest`/`demand_predicted`/`protection_level` — `forecasts[]` là **theo đoạn** (per-segment, không phải per-O-D), và `allocations[].bid_price_vnd` đọc từ cache DLP thật (`allocation/cache.py`); **trả `0` nếu chưa `reset`/`forecasts/refresh` cho version hiện tại** (cache miss → hiển thị 0, KHÔNG bịa công thức fallback — endpoint này chỉ đọc, không phải quyết định giá).

### 2.6. Chi tiết Quyết định AI (Audit/Explain)
**`GET /decisions/{decision_id}`**

- **Response (200 OK)** — output thật:
  ```json
  {
    "data": {
      "decision_id": "dr_edfab201f59b",
      "input_hash": "0b0134afd658ad7f",
      "versions": { "matrix_version": 1, "forecast_version": 1, "policy_version": 1 },
      "action": "ACCEPT",
      "base_fare": 285000,
      "ai_suggested_price": 307000,
      "final_price": 307000,
      "bid_price_total": 0,
      "bid_price_breakdown": { "3": 0, "4": 0 },
      "violations": [],
      "audit_timeline": {
        "explanation": "F0=285000đ → MUA_VU:HE(×1.075), ELASTIC:r=1.08(×1.0788) → niêm yết 307000đ → cuối 307000đ vs Σbid 0đ ⇒ ACCEPT",
        "rules_fired": [
          { "rule_id": "MUA_VU:HE", "he_so": 1.075, "thu_tu": 1 },
          { "rule_id": "ELASTIC:r=1.08", "he_so": 1.0788, "thu_tu": 2 }
        ]
      },
      "explanation_code": "ACCEPT_BID_COVERED",
      "actor": "system",
      "created_at": "2026-06-15T09:00:00+00:00"
    }
  }
  ```
  ⚠️ Khác bản draft cũ: `audit_timeline` là **object** `{explanation, rules_fired}` (không phải mảng `{step,time,note}[]`); có thêm `input_hash`/`versions`/`actor`/`created_at`. `404` trả `error_code: "RESOURCE_NOT_FOUND"` nếu `decision_id` không tồn tại.
- **Ghi chú "rule_id" (P3):** `rules/pricing_rules.yaml` với các luật gõ tay (`R_HE2026_XA_NGAY`, `R_GIO_CHOT`...) **đã bị xóa**. Rule động giờ là 2 nguồn thật: `MUA_VU:HE`/`MUA_VU:TET` (hệ số mùa vụ đọc từ `models/artifacts/bt5_pricing_params.json`, không gõ tay) và `ELASTIC:r=<tỷ lệ>` (optimizer tối đa hoá `P(mua|r)·(p−c)` từ `app.elasticity`, `c` = Σ bid DLP). FE hiển thị `rule_id` gì cũng được — chuỗi tự mô tả, không cần bảng tra tên luật tĩnh nữa.

---

## 3. Luồng Đặt vé Hành khách (Booking Pipeline)

### 3.1. Tìm kiếm và Đề xuất vé (Tạo Offer)
**`POST /offers`**

Quét ma trận, tìm ghế trống xuyên suốt (same-seat gap); nếu không có, **thử ghép nhiều ghế** (P5, xem §3.1.1); so khớp Bid-price (DLP thật) và trả về báo giá.

- **Request Body:**
  ```json
  {
    "service_run_id": "SE1_2026-06-15_LE",
    "origin_station_id": "THO",
    "dest_station_id": "DHO",
    "seat_class": "NGOI_MEM_DH",
    "quantity": 1,
    "priority_passenger": false
  }
  ```
  - `priority_passenger` **(P5, mới, mặc định `false`)**: hành khách cao tuổi/khuyết tật/trẻ đi một mình. `true` ⇒ **không bao giờ** nhận phương án ghép nhiều ghế — chỉ same-seat hoặc 422 `NO_SAME_SEAT_OPTION`.
- **Response (201 Created)** — output thật (golden path THO→DHO, same-seat):
  ```json
  {
    "data": {
      "offer_id": "offer_6346c65d8bf2",
      "service_run_id": "SE1_2026-06-15_LE",
      "matrix_version": 1,
      "forecast_version": 1,
      "policy_version": 1,
      "decision": "ACCEPT",
      "seat_plan": [
        { "seat_id": "C01-S017", "segment_from": 3, "segment_to": 4, "reused_gap": true, "requires_seat_change": false }
      ],
      "requires_customer_consent": false,
      "change_station_ids": [],
      "so_lan_doi_cho": 0,
      "pricing": {
        "gia_goc_vnd": 285000,
        "gia_niem_yet_vnd": 307000,
        "gia_cuoi_vnd": 307000,
        "rules_fired": [
          { "rule_id": "MUA_VU:HE", "he_so": 1.075, "thu_tu": 1 },
          { "rule_id": "ELASTIC:r=1.08", "he_so": 1.0788, "thu_tu": 2 }
        ],
        "violations": [],
        "clamped": false,
        "csxh_doi_tuong": "KHONG",
        "che_do_gia": "AI"
      },
      "bid": { "total_vnd": 0, "by_segment": { "3": 0, "4": 0 } },
      "decision_record_id": "dr_edfab201f59b",
      "explanation": "F0=285000đ → MUA_VU:HE(×1.075), ELASTIC:r=1.08(×1.0788) → niêm yết 307000đ → cuối 307000đ vs Σbid 0đ ⇒ ACCEPT",
      "expires_at": "2026-06-15T09:05:00+00:00"
    }
  }
  ```
  ⚠️ **Số ví dụ đổi so với bản draft cũ** (400.000/480.000/450.000đ → nay 285.000/307.000/307.000đ): pricing cắm elasticity optimizer thật (P3) + xóa luật `pricing_rules.yaml` gõ tay (kể cả `R_GIO_CHOT` từng cố tình tạo case vượt trần) — golden path hè 2026 **không còn chạm trần** trên luồng chính (`clamped: false`). `bid.total_vnd = 0` cho golden gap là **đúng, không phải bug**: DLP thật (`app.bt3_allocation`) tính cầu đoạn 3-4 (~3.6/16.2 vé) thấp hơn nhiều sức chứa còn lại (19/28 ghế) ⇒ dual=0 (không nghẽn).

#### 3.1.1 Ghép nhiều ghế (P5) — khi same-seat rỗng

Ví dụ THO→HUE (không ghế nào trống liên tục cả đoạn 3-4-5):

```json
{
  "data": {
    "decision": "ACCEPT",
    "seat_plan": [
      { "seat_id": "C01-S001", "segment_from": 3, "segment_to": 4, "reused_gap": false, "requires_seat_change": true },
      { "seat_id": "C01-S003", "segment_from": 5, "segment_to": 5, "reused_gap": false, "requires_seat_change": true }
    ],
    "requires_customer_consent": true,
    "change_station_ids": ["DHO"],
    "so_lan_doi_cho": 1,
    "pricing": { "...": "giống mục 3.1, giá vẫn theo O-D THO→HUE, không cộng theo từng leg" }
  }
}
```

- `seat_plan` giờ **luôn là mảng ≥1 phần tử** — 1 phần tử = same-seat (như trước), ≥2 phần tử = ghép nhiều ghế.
- `requires_customer_consent: true` ⇒ FE **bắt buộc** hiển thị disclosure (số lần đổi chỗ `so_lan_doi_cho`, ga đổi `change_station_ids`) và chỉ gọi `POST /holds` với `consent: true` sau khi khách bấm đồng ý — không auto-accept.
- Điểm đổi chỗ chỉ đặt tại ga có thời gian dừng ≥5 phút (`DWELL_MINUTES` trong `forecast/network.py`, nguồn: YAML tham số mô phỏng §1 `mang_luoi.ga.dwell_phut`).
- `priority_passenger: true` ⇒ nhánh này **không bao giờ** được trả về (resolver tự lọc rỗng) — nếu same-seat cũng rỗng thì 422 `NO_SAME_SEAT_OPTION`.
- **Chưa có `web/`** để dựng disclosure UI thật — mục này là hợp đồng API cho FE dựng khi có frontend.

- **Lỗi phổ biến:**
  - `422 NO_SAME_SEAT_OPTION`: Không tìm được ghế liên tục **và** không ghép được nhiều ghế (hoặc `priority_passenger=true` mà same-seat rỗng).
  - `422 ALLOCATION_REJECTED`: Giá offer thấp hơn Σ bid-price.
    ```json
    { "error_code": "ALLOCATION_REJECTED",
      "message": "Giá vé không bù đủ chi phí cơ hội các đoạn chiếm dụng",
      "details": { "final_price_vnd": 380000, "bid_price_total_vnd": 420000, "decision_record_id": "dr_8900" } }
    ```
  - `503 POLICY_UNAVAILABLE`: pricing policy chưa approve, hoặc forecast/DLP bid-price cache chưa sẵn sàng cho version hiện tại (cần `reset`/`forecasts/refresh` trước).

### 3.2. Giữ chỗ Nguyên tử (Atomic Hold)
**`POST /holds`**

Khóa **toàn bộ leg** trong `seat_plan` của offer (1 leg = same-seat, ≥2 leg = ghép nhiều ghế) trong MỘT giao dịch — tất-cả-hoặc-không.

- **Headers:** `Idempotency-Key` (string, required)
- **Request Body:**
  ```json
  { "offer_id": "offer_9981", "expected_matrix_version": 1, "passenger_name": "Nguyễn Văn A", "consent": false }
  ```
  - `consent` **(P5, mới, mặc định `false`)**: bắt buộc `true` nếu offer có `requires_customer_consent: true` (≥2 leg), nếu không → `422 CONSENT_REQUIRED`. Same-seat (1 leg) không cần set field này.
- **Response (201 Created):**
  ```json
  { "data": { "hold_id": "hold_a7d2d70f2163", "status": "ACTIVE", "expires_at": "2026-06-15T09:10:00+00:00", "new_matrix_version": 2 } }
  ```
- **Lỗi phổ biến:**
  - `422 CONSENT_REQUIRED` **(P5, mới)**: `seat_plan` ≥2 leg mà thiếu `consent: true`.
  - `409 Conflict`: `expected_matrix_version` không khớp (`STALE_SNAPSHOT`) hoặc ghế vừa bị người khác mua (`SEAT_CONFLICT`) — với ghép nhiều ghế, **1 leg conflict ⇒ rollback toàn bộ**, không leg nào bị giữ một phần.
  - `410 Gone`: Offer đã hết thời gian tồn tại (`expires_at`, TTL 5 phút).

### 3.3. Xác nhận Thanh toán (Confirm)
**`POST /bookings/{hold_id}/confirm`**

- **Headers:** `Idempotency-Key` (string, required)
- **Request Body:** `{}` (không cần body)
- **Response (200 OK):**
  ```json
  { "data": { "booking_id": "bk_8da7f3ebc816", "status": "CONFIRMED", "final_price_vnd": 307000, "decision_record_id": null } }
  ```
  ⚠️ `decision_record_id` luôn `null` trong response confirm (schema V1 `offer` không có cột này, khóa từ đầu, không sửa migration) — FE tra decision qua `POST /offers`' `decision_record_id` đã nhận trước đó, hoặc `GET /demo/overview`'s `recent_decisions`.
- **Lỗi phổ biến:** `410 Gone` — Hold đã quá hạn thanh toán (10 phút), ghế đã tự release.

### 3.4. Ghi đè giá thủ công (P7.6, mới)
**`POST /offers/{offer_id}/override`**

Điều độ viên (`revenue_manager`/`admin`) ghi đè `final_price_vnd` của một offer **TRONG** dải guardrail đã duyệt `[floor_ratio, ceiling_ratio] × F0` — bất biến "không bao giờ tự định giá ngoài dải đã duyệt" áp dụng cho cả override thủ công, không chỉ engine tự động. Chỉ override được khi offer **chưa có hold** (giá đã khoá lúc hold là bất khả xâm phạm — xem §3.2).

- **Headers:** `X-Actor-Role: revenue_manager|admin` (required — kiểm qua header, **KHÔNG phải RBAC/JWT thật**, xem ghi chú `ponytail` trong `state/errors.py::Forbidden`)
- **Request Body:**
  ```json
  { "new_price_vnd": 109000, "reason": "Khách VIP - đại lý yêu cầu giữ giá gốc", "decided_by": "nguyen_van_dieu_do" }
  ```
- **Response (200 OK)** — output thật:
  ```json
  {
    "data": {
      "offer_id": "offer_34f261613c42",
      "old_price_vnd": 113000,
      "new_price_vnd": 109000,
      "expires_at": "2026-06-15T09:05:00+00:00"
    }
  }
  ```
- **Lỗi phổ biến:**
  - `403 FORBIDDEN`: thiếu header hoặc role không phải `revenue_manager`/`admin`.
  - `422 GUARDRAIL_VIOLATION`: giá đề nghị ngoài dải — output thật:
    ```json
    { "error_code": "GUARDRAIL_VIOLATION",
      "message": "Giá override 545.000đ ngoài dải guardrail [59.950;174.400]đ",
      "details": { "offer_id": "offer_34f261613c42", "floor": 59950, "ceiling": 174400, "requested": 545000 } }
    ```
  - `409 SEAT_CONFLICT`: offer đã có hold `ACTIVE`/`CONFIRMED` — `"Offer đã có hold — giá đã khoá bất khả xâm phạm, không override được"`.
  - `503 POLICY_UNAVAILABLE`: chưa có `pricing_policy`/`fare_product` để tính dải guardrail.
- Mọi lần override được ghi vào `proposal_log` (`loai=OVERRIDE`, kèm `reason`, giá cũ/mới, `decided_by` là `actor`) — truy vết qua audit, chưa có endpoint đọc riêng (dùng chung cơ chế `GET /decisions/{id}` không phủ override, xem §6 ghi chú).

---

## 4. API Khảo sát So sánh (Backtest)

### 4.1. Khởi chạy Backtest
**`POST /backtests`**

- **Request Body:** `{}` (rỗng — engine luôn chạy đúng 5 seed **đã commit** trong `backend/seed/backtest/*.jsonl`: `20260717..20260721`, không nhận `event_stream_id` tùy ý).
  - Tùy chọn: `{"seeds": [20260717, 20260718]}` để chỉ chạy một tập con seed đã commit.
- **Response (202 Accepted):**
  ```json
  { "message": "Backtest started", "data": { "report_id": "bt_0c057f42a271" } }
  ```

### 4.2. Xem Kết quả Backtest
**`GET /backtests/{report_id}`**

- **Response (200 OK)** — output thật (5 seed, 0 fail):
  ```json
  {
    "data": {
      "status": "COMPLETED",
      "seeds_run": [20260717, 20260718, 20260719, 20260720, 20260721],
      "failed_seeds": [],
      "baseline_metrics": { "revenue_median": 18848000, "revenue_min": 15739000, "revenue_max": 22427000 },
      "ai_metrics": { "revenue_median": 23438000, "revenue_min": 19910000, "revenue_max": 27670000 },
      "raw": {
        "20260717": {
          "false_sold_out_rate": 0.111, "empty_seat_km": 37778.4, "passenger_km": 31261.6,
          "baseline": { "revenue_vnd": 18848000, "acceptance_rate": 0.889 },
          "aulac": { "revenue_vnd": 24334000, "acceptance_rate": 1.0 }
        }
      },
      "checksum": "3f3234322f8a49fe975fbba97e256e2db4d6b0739b180a709926545968213f84"
    }
  }
  ```
  ⚠️ Khác bản draft cũ: field tên `ai_metrics` (không phải `data.ai_metrics` khác tên), chỉ có `{revenue_median, revenue_min, revenue_max}` ở tầng tổng hợp (không có `acceptance_rate` — số đó nằm trong `raw[seed].baseline/aulac.acceptance_rate` per-seed); có thêm `seeds_run`/`failed_seeds`/`raw`/`checksum`. **Không tìm thấy `report_id`** → `404` `RESOURCE_NOT_FOUND`.
  ⚠️ **Số pitch đổi so với bản demo ban đầu**: "+156%" (baseline 19,5tr vs Âu Lạc 50,0tr) là artifact của kịch bản mà baseline từ chối gần hết request — **không phải bằng chứng doanh thu chuẩn**. Số hiệu chỉnh từ dữ liệu thật cuối cùng (calibrate λ per O-D từ `search_log` thật + pricing elasticity thật + DLP gating): **baseline median 18.848.000đ vs Âu Lạc median 23.438.000đ = +24,4%**, cùng với evidence riêng từ model backtest trên dữ liệu thật cả năm (`models/artifacts/backtest_report.json`): Tết +2,3% DT, 89,0% tối ưu offline, ghế trống cục bộ −52%, MASE 0,515, 0 vi phạm.

---

## 5. Ghi chú kiến trúc cho FE (P5 — ghép nhiều ghế)

- `web/` **chưa được xây** trong repo này — mục 3.1.1 và 3.2 là hợp đồng API sẵn sàng cho FE khi bắt đầu dựng disclosure UI.
- Khi dựng UI ghép nhiều ghế: hiển thị RÕ trước khi khách bấm "đồng ý" — số lần đổi ghế (`so_lan_doi_cho`), ga đổi (`change_station_ids`), và toàn bộ `seat_plan` (từng leg seat_id + đoạn). Chỉ gọi `POST /holds` với `consent: true` SAU khi khách xác nhận — không tự động coi im lặng là đồng ý.
- Hành khách thuộc diện ưu tiên (cao tuổi/khuyết tật/trẻ đi một mình) **luôn** gửi `priority_passenger: true` trong `POST /offers` — không hiển thị lựa chọn ghép ghế cho nhóm này (bất biến cứng, không phải gợi ý UX).

---

## 6. API Phân bổ & Hạn mức (P7.2, mới — Dành cho Điều độ viên)

Đề xuất/duyệt/rollback hạn mức bán theo `(khu_gian, loại hành trình ngắn/trung/dài, lớp ghế)` — thuần workflow, **chưa enforce** `booking_limit` trong `/offers` (route hiện chỉ so giá vs bid DLP như trước, xem `allocation/reallocation.py` docstring).

### 6.1. Đề xuất hạn mức mới
**`POST /allocation/refresh?service_run_id=...`**

Re-solve DLP (tái dùng cache P2, không giải LP lần 2), diff `booking_limit` cũ/mới → tạo bản `PENDING` mới.

- **Response (201 Created)** — output thật (rút gọn, `quota` đủ 63 dòng = 7 đoạn × 3 loại hành trình × 3 lớp ghế):
  ```json
  {
    "data": {
      "version": 1,
      "status": "PENDING",
      "proposal": [],
      "quota": [
        { "khu_gian_id": 1, "loai_hanh_trinh": "ngan", "seat_class": "NGOI_MEM_DH", "quota": 5, "booking_limit": 5, "bid_price": 0 },
        { "khu_gian_id": 1, "loai_hanh_trinh": "trung", "seat_class": "NGOI_MEM_DH", "quota": 0, "booking_limit": 30, "bid_price": 0 },
        "... 61 dòng còn lại"
      ]
    }
  }
  ```
  `proposal` rỗng ở bản đầu tiên (chưa có bản ACTIVE để so); từ bản thứ 2 trở đi liệt kê từng `{khu_gian_id, loai_hanh_trinh, seat_class, action: MO_THEM|SIET_LAI, limit_cu, limit_moi}`.
- **Lỗi:** `503 POLICY_UNAVAILABLE` nếu DLP không giải được.

### 6.2. Xem một bản hạn mức
**`GET /allocation/{version}?service_run_id=...`** → `200` cùng shape §6.1, hoặc `404 RESOURCE_NOT_FOUND`.

### 6.3. Duyệt / Từ chối / Rollback
**`POST /allocation/{version}/approve|reject|rollback?service_run_id=...`**

- **Headers:** `X-Actor-Role: revenue_manager|admin` bắt buộc — thiếu/sai → `403 FORBIDDEN`:
  ```json
  { "error_code": "FORBIDDEN", "message": "Cần role revenue_manager/admin để thực hiện thao tác này (nhận: 'user')", "details": {} }
  ```
- **Request Body:** `{ "decided_by": "nguyen_van_dieu_do" }` (chỉ là tên hiển thị trong audit — role được kiểm qua header, không qua field này).
- **`approve`**: chỉ áp dụng cho bản `PENDING` → chuyển `ACTIVE`, bản `ACTIVE` cũ (nếu có) tự lùi về `ROLLED_BACK` (tại một thời điểm chỉ có đúng 1 bản `ACTIVE`).
- **`reject`**: chỉ áp dụng cho bản `PENDING` → chuyển `REJECTED`.
- **`rollback`**: áp dụng cho **bất kỳ** bản nào (kể cả đã `REJECTED`/`ROLLED_BACK` từ trước) → chuyển `ACTIVE`, dùng khi cần quay lại nhanh một bản cũ đã biết là đúng.
- Không tìm thấy version hoặc version không ở đúng trạng thái nguồn (vd `approve` một bản đã `ACTIVE`) → `404 RESOURCE_NOT_FOUND`.
- Mọi quyết định ghi vào `proposal_log` (`loai=ALLOCATION`) qua `audit/log.py::persist`.

---

## 7. API Hàng chờ thông minh (P7.3, mới)

Bảng `waiting_list` (đã có sẵn từ schema V1). Điểm ưu tiên tất định, tái dùng đúng công thức `app.waitlist.WaitlistManager` (không dùng dữ liệu cá nhân để phân biệt giá): `score = 0.4·(F0 chuẩn hoá) + 0.3·1/(1+u) + 0.2·(bid chuẩn hoá) + 0.1·(cờ CSXH)`.

### 7.1. Vào hàng chờ
**`POST /waitlist`** — khách **chủ động** vào chờ sau khi `/offers` trả `422 NO_SAME_SEAT_OPTION` (không tự động thêm).

- **Request Body:**
  ```json
  { "service_run_id": "SE1_2026-06-15_LE", "origin_station_id": "HNO", "dest_station_id": "NBI",
    "seat_class": "NGOI_MEM_DH", "u": 10 }
  ```
- **Response (201 Created)** — output thật:
  ```json
  { "data": { "waitlist_id": "a4c6191f-ff00-476a-aa62-bac6cd08ac87", "priority_score": 0.0537, "status": "PENDING" } }
  ```

### 7.2. Xem hàng chờ
**`GET /waitlist?service_run_id=...`** → danh sách `PENDING`, sắp theo `priority_score` giảm dần rồi `created_at` tăng dần:
```json
{ "data": { "pending": [
  { "waitlist_id": "a4c6191f-...", "origin_station_id": "HNO", "dest_station_id": "NBI",
    "seat_class": "NGOI_MEM_DH", "priority_score": 0.0537, "priority_passenger": false,
    "quantity": 1, "created_at": "2026-07-18T08:25:35.190144+00:00" } ] } }
```

### 7.3. Khớp hàng chờ
**`POST /waitlist/match?service_run_id=...`**

Duyệt các entry `PENDING` theo score giảm dần; khớp được thì gọi lại **nguyên** pipeline `/offers` → `/holds` (không viết pipeline giá/CAS thứ hai) — có ghế thì tạo **Hold thật** để khách thanh toán trong TTL bình thường (10 phút), entry chuyển `MATCHED`. Chưa khớp được thì giữ `PENDING`, không phải lỗi.

- **Response (200 OK)** — output thật:
  ```json
  { "data": { "matched": [
      { "waitlist_id": "a4c6191f-...", "hold_id": "hold_d06e23c037f7", "expires_at": "2026-06-15T09:10:00+00:00" } ],
    "still_pending": 0 } }
  ```
- ⚠️ **ponytail — không có worker nền trong demo này.** Endpoint là ops-trigger tường minh, gọi sau khi có hủy vé/hold hết hạn. Nâng cấp: cron/scheduler gọi định kỳ khi cần vận hành thật.

---

## 8. API Xếp nhóm (P7.4, mới)

**`POST /group/quote`** — đề xuất ghế cùng toa/khoang cho nhóm/gia đình (CP-SAT, fallback greedy nếu thiếu `ortools`). **Thuần đề xuất — không giữ ghế**; khách đồng ý thì gọi `/offers` + `/holds` bình thường cho từng ghế trong `assignments`.

- **Request Body:**
  ```json
  { "service_run_id": "SE1_2026-06-15_LE", "origin_station_id": "HNO", "dest_station_id": "NBI",
    "seat_class": "NGOI_MEM_DH", "n_khach": 8 }
  ```
- **Response (200 OK)** — output thật (`n_khach=8`, 40 ghế còn trống hết → gọn 1 toa):
  ```json
  {
    "data": {
      "kha_thi": true,
      "seat_class": "NGOI_MEM_DH",
      "assignments": [
        { "seat_idx": 7, "seg_from": 0, "seg_to": 1, "ga_di": "HNO", "ga_den": "NBI", "seat_id": "C01-S008" },
        { "seat_idx": 8, "seg_from": 0, "seg_to": 1, "ga_di": "HNO", "ga_den": "NBI", "seat_id": "C01-S009" },
        "... 6 ghế còn lại"
      ],
      "toa": [0],
      "diem_lien_ke": 0.857,
      "so_lan_tach": 2,
      "ghi_chu": "greedy: 8 khách / 1 toa / 3 khoang, liền kề 86%"
    }
  }
  ```
  ⚠️ Môi trường không cài `ortools` thì luôn chạy nhánh `greedy` (fallback tự động, không lỗi) — ví dụ trên đo bằng `greedy`. `solver` trong `ghi_chu` đổi thành `CP-SAT` nếu môi trường có cài.
- **Lỗi:** `422 NO_SAME_SEAT_OPTION` khi không đủ ghế trống suốt cho cả nhóm:
  ```json
  { "error_code": "NO_SAME_SEAT_OPTION", "message": "chỉ còn 19 ghế trống suốt, cần 100",
    "details": { "origin_station_id": "THO", "dest_station_id": "DHO", "n_khach": 100 } }
  ```

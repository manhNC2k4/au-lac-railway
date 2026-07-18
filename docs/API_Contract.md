# Hợp đồng Giao tiếp API (API Contract) - Âu Lạc Railway (MVP 30h)

Tài liệu này đặc tả chi tiết các endpoints giao tiếp giữa Frontend (FE) và Backend (BE) dành riêng cho phiên bản **MVP 30 giờ**. Mọi request đều tuân theo chuẩn RESTful.

> ⚠️ **Nguồn chân lý cuối cùng là `openapi.yaml` do BE1 freeze giờ 2.** File này là bản draft đã đối chiếu thống nhất với `plan/00_MASTER_PLAN.md §7` (17/07/2026). Nếu có mâu thuẫn, `openapi.yaml` thắng.

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
  - `400 Bad Request`: Thiếu tham số hoặc dữ liệu sai định dạng.
  - `404 Not Found`: Không tìm thấy resource (ga, chuyến, offer, hold).
  - `409 Conflict`: Xung đột trạng thái (stale version, mất ghế).
  - `410 Gone`: Resource đã hết hạn (Offer/Hold expired).
  - `422 Unprocessable Entity`: Dữ liệu đúng định dạng nhưng vi phạm logic nghiệp vụ.
  - `503 Service Unavailable`: Policy/dependency bắt buộc không sẵn sàng. **Không bao giờ im lặng dùng giá mặc định.**
- **Bộ reason code chuẩn (`error_code`) — khớp Master Plan §7:**

  | Code | HTTP | Ý nghĩa |
  |---|---|---|
  | `NO_SAME_SEAT_OPTION` | 422 | Không tìm được ghế liên tục cho hành trình |
  | `SOLD_OUT_TRUE` | 422 | Hết chỗ thật (mọi ghế đều bận) |
  | `ALLOCATION_REJECTED` | 422 | Giá offer < Σ bid-price các leg (từ chối theo quota) |
  | `STALE_SNAPSHOT` | 409 | `expected_matrix_version` không khớp |
  | `SEAT_CONFLICT` | 409 | Ghế vừa bị người khác giữ/mua |
  | `OFFER_EXPIRED` | 410 | Offer quá `expires_at` |
  | `HOLD_EXPIRED` | 410 | Hold quá hạn thanh toán, ghế đã tự release |
  | `POLICY_UNAVAILABLE` | 503 | Pricing policy thiếu/chưa approved — fail closed |

---

## 2. API Quản trị Demo & Ops Dashboard (Dành cho Admin)

### 2.1. Khởi tạo Kịch bản Demo
**`POST /demo/scenarios/{scenario_id}/reset`**

Nạp dữ liệu giả định ban đầu, reset lại ma trận ghế và đồng hồ hệ thống.

- **Path Variables:**
  - `scenario_id` (string, required): Mã kịch bản (VD: `golden_scenario_1`).
- **Request Body:**
  ```json
  {
    "reset_clock": true,
    "apply_golden_gap": true
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "data": {
      "service_run_id": "SE1_2026-06-15_LE",
      "matrix_version": 1,
      "forecast_version": 1,
      "policy_version": 1,
      "checksum": "abc123xyz"
    },
    "message": "Scenario reset successfully"
  }
  ```
- **Ràng buộc:** không partial load — scenario lỗi thì từ chối toàn bộ, state đang chạy giữ nguyên. Cùng seed ⇒ cùng checksum (reset deterministic).

### 2.2. Làm mới Dự báo
**`POST /demo/forecasts/refresh`**

Kích hoạt chạy lại dự báo cho một chuyến tàu (phục vụ Demo nóng). **Owner: logic `src/forecast/` = BE2; route `src/api/` = BE1.**

- **Request Body:**
  ```json
  {
    "service_run_id": "SE1_2026-06-15_LE"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "message": "Forecast updated",
    "data": { "forecast_version": 2 }
  }
  ```

### 2.3. Dashboard Tổng quan
**`GET /demo/overview`**

- **Query Parameters:**
  - `service_run_id` (string, required): Mã chuyến tàu.
- **Response (200 OK):**
  ```json
  {
    "data": {
      "overall_occupancy": 0.75,
      "total_revenue_vnd": 45000000,
      "empty_seat_km": 12000,
      "passenger_km": 85000,
      "false_sold_out_rate": 0.05,
      "bottlenecks": [
         { "segment_id": 3, "name": "THO-VIN", "occupancy": 0.95 }
      ],
      "underused": [
         { "segment_id": 6, "name": "HUE-DNA", "occupancy": 0.30 }
      ],
      "recent_decisions": [
         { "decision_id": "dr_8899", "action": "ACCEPT", "time": "2026-06-15T10:05:00Z" }
      ]
    }
  }
  ```

### 2.4. Ma trận Ghế × Đoạn (Heatmap)
**`GET /demo/seatmap`**

- **Query Parameters:**
  - `service_run_id` (string, required)
- **Response (200 OK):**
  ```json
  {
    "data": {
      "matrix_version": 5,
      "segments": [
        { "segment_id": 1, "name": "HNO-NBI" },
        { "segment_id": 2, "name": "NBI-THO" }
      ],
      "seats": [
        {
           "seat_id": "C01-S017",
           "seat_class": "NGOI_MEM_DH",
           "states": { "1": "SOLD", "2": "SOLD", "3": "FREE", "4": "FREE", "5": "SOLD", "6": "SOLD", "7": "SOLD" },
           "reused_gap_segments": [3, 4]
        }
      ]
    }
  }
  ```

### 2.5. Phân tích Dự báo và Phân bổ
**`GET /demo/analytics`**

- **Query Parameters:**
  - `service_run_id` (string, required)
- **Response (200 OK):**
  ```json
  {
    "data": {
      "forecasts": [
        { "origin": "HNO", "dest": "THO", "demand_predicted": 120, "confidence": 0.85 }
      ],
      "segment_loads": [
        { "segment_id": 1, "occupancy": 0.85, "remaining_capacity": 12 }
      ],
      "allocations": [
        { "segment_id": 1, "bid_price_vnd": 250000, "protection_level": "HIGH" }
      ]
    }
  }
  ```

### 2.6. Chi tiết Quyết định AI (Audit/Explain)
**`GET /decisions/{decision_id}`**

- **Path Variables:**
  - `decision_id` (string, required): Mã log quyết định.
- **Response (200 OK):**
  ```json
  {
    "data": {
      "decision_id": "dr_8899",
      "action": "ACCEPT",
      "base_fare": 400000,
      "ai_suggested_price": 480000,
      "final_price": 450000,
      "bid_price_total": 420000,
      "bid_price_breakdown": { "1": 200000, "2": 220000 },
      "violations": [
        "MAX_DELTA_EXCEEDED: Giá AI (480k) vượt trần tăng 10% (440k). Clamped về 440k + làm tròn 450k."
      ],
      "audit_timeline": [
        { "step": "Forecast", "time": "2026-06-15T10:04:00Z", "note": "Scarcity = 0.9" },
        { "step": "Guardrail", "time": "2026-06-15T10:04:01Z", "note": "Applied MAX_DELTA" }
      ]
    }
  }
  ```

---

## 3. Luồng Đặt vé Hành khách (Booking Pipeline)

### 3.1. Tìm kiếm và Đề xuất vé (Tạo Offer)
**`POST /offers`**

Quét ma trận, tìm ghế trống xuyên suốt (same-seat gap), so khớp Bid-price và trả về báo giá.

- **Request Body:**
  ```json
  {
    "service_run_id": "SE1_2026-06-15_LE",
    "origin_station_id": "THO",
    "dest_station_id": "DHO",
    "seat_class": "NGOI_MEM_DH",
    "quantity": 1
  }
  ```
- **Response (201 Created)** — đủ **4 versions** (bất biến trung tâm) + **price breakdown 3 mức** + **bid từng leg** để FE2 dựng S03 không phải gọi thêm request nào:
  ```json
  {
    "data": {
      "offer_id": "offer_9981",
      "service_run_id": "SE1_2026-06-15_LE",
      "matrix_version": 5,
      "forecast_version": 2,
      "policy_version": 1,
      "decision": "ACCEPT",
      "seat_plan": [
        { "seat_id": "C01-S017", "segment_from": 3, "segment_to": 4, "reused_gap": true, "requires_seat_change": false }
      ],
      "pricing": {
        "gia_goc_vnd": 400000,
        "gia_niem_yet_vnd": 480000,
        "gia_cuoi_vnd": 450000,
        "rules_fired": [ { "rule_id": "R_HE2026_XA_NGAY", "he_so": 0.92, "thu_tu": 1 } ],
        "clamped": true,
        "che_do_gia": "AI"
      },
      "bid": {
        "total_vnd": 420000,
        "by_segment": { "3": 200000, "4": 220000 }
      },
      "decision_record_id": "dr_8899",
      "expires_at": "2026-06-15T10:05:00Z"
    }
  }
  ```
- **Ràng buộc:** tạo offer **KHÔNG giữ ghế** (giữ ghế là việc của `POST /holds`). Offer immutable tới khi hết hạn — không tính lại giá cho offer còn hiệu lực.
- **Lỗi phổ biến:**
  - `422 NO_SAME_SEAT_OPTION`: Không tìm thấy ghế trống xuyên suốt.
  - `422 SOLD_OUT_TRUE`: Hết chỗ thật.
  - `422 ALLOCATION_REJECTED`: Giá offer thấp hơn Σ bid-price (từ chối theo quota). Ví dụ response lỗi:
    ```json
    {
      "error_code": "ALLOCATION_REJECTED",
      "message": "Giá vé không bù đủ chi phí cơ hội các đoạn chiếm dụng",
      "details": { "final_price_vnd": 380000, "bid_price_total_vnd": 420000, "decision_record_id": "dr_8900" }
    }
    ```
  - `503 POLICY_UNAVAILABLE`: Chưa có pricing policy được approve.

### 3.2. Giữ chỗ Nguyên tử (Atomic Hold)
**`POST /holds`**

Thực hiện khóa ghế trên ma trận. Bắt buộc trùng khớp version để tránh race condition.

- **Headers:**
  - `Idempotency-Key` (string, required): UUID sinh từ Frontend để tránh double click.
- **Request Body:**
  ```json
  {
    "offer_id": "offer_9981",
    "expected_matrix_version": 5,
    "passenger_name": "Nguyễn Văn A"
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "data": {
      "hold_id": "hold_112233",
      "status": "ACTIVE",
      "expires_at": "2026-06-15T10:15:00Z",
      "new_matrix_version": 6
    }
  }
  ```
- **Lỗi phổ biến:**
  - `409 Conflict`: `expected_matrix_version` không khớp (stale state) hoặc ghế vừa bị người khác mua.
  - `410 Gone`: Offer đã hết thời gian tồn tại (`expires_at`).

### 3.3. Xác nhận Thanh toán (Confirm)
**`POST /bookings/{hold_id}/confirm`**

Chuyển trạng thái vé từ HELD sang SOLD.

- **Headers:**
  - `Idempotency-Key` (string, required)
- **Path Variables:**
  - `hold_id` (string, required)
- **Request Body:** `{}` (Không cần body)
- **Response (200 OK):**
  ```json
  {
    "data": {
      "booking_id": "bk_556677",
      "status": "CONFIRMED",
      "final_price_vnd": 450000,
      "decision_record_id": "dr_8899"
    }
  }
  ```
- **Lỗi phổ biến:**
  - `410 Gone`: Hold đã quá hạn thanh toán (hết 10 phút). Hệ thống đã tự động release ghế.

---

## 4. API Khảo sát So sánh (Backtest)

### 4.1. Khởi chạy Backtest
**`POST /backtests`**

- **Request Body:**
  ```json
  {
    "event_stream_id": "stream_demo_1",
    "seeds": ["20260717", "20260718", "20260719", "20260720", "20260721"]
  }
  ```
- **Response (202 Accepted):**
  ```json
  {
    "message": "Backtest started",
    "data": { "report_id": "bt_12345" }
  }
  ```

### 4.2. Xem Kết quả Backtest
**`GET /backtests/{report_id}`**

- **Path Variables:**
  - `report_id` (string, required)
- **Response (200 OK):**
  ```json
  {
    "data": {
      "status": "COMPLETED",
      "baseline_metrics": { "revenue_median": 100000000, "acceptance_rate": 0.65 },
      "ai_metrics": { "revenue_median": 115000000, "acceptance_rate": 0.78 }
    }
  }
  ```

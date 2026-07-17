# Hợp đồng Giao tiếp API (API Contract) - Âu Lạc Railway (MVP 30h)

Tài liệu này đặc tả chi tiết các endpoints giao tiếp giữa Frontend (FE) và Backend (BE) dành riêng cho phiên bản **MVP 30 giờ**. Mọi request đều tuân theo chuẩn RESTful.

## 1. Thông tin chung
- **Base URL:** `/api/v1`
- **Content-Type mặc định:** `application/json`
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
      "checksum": "abc123xyz"
    },
    "message": "Scenario reset successfully"
  }
  ```

### 2.2. Làm mới Dự báo
**`POST /demo/forecasts/refresh`**

Kích hoạt worker chạy lại model dự báo cho một chuyến tàu (phục vụ Demo nóng).

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
         { "decision_id": "dr_8899", "action": "ACCEPT", "time": "2026-07-17T10:05:00Z" }
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
           "seat_id": "C01-S01",
           "seat_class": "NGOI_MEM_DH",
           "states": { "1": "SOLD", "2": "FREE", "3": "HELD" }
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
        { "step": "Forecast", "time": "2026-07-17T10:04:00Z", "note": "Scarcity = 0.9" },
        { "step": "Guardrail", "time": "2026-07-17T10:04:01Z", "note": "Applied MAX_DELTA" }
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
    "origin_station_id": "HNO",
    "dest_station_id": "VIN",
    "seat_class": "NGOI_MEM_DH",
    "quantity": 1
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "data": {
      "offer_id": "offer_9981",
      "matrix_version": 5,
      "decision": "ACCEPT",
      "seat_plan": [ 
        { "segment_from": 1, "segment_to": 3, "seat_id": "C01-S01" } 
      ],
      "final_price_vnd": 450000,
      "expires_at": "2026-07-17T10:05:00Z"
    }
  }
  ```
- **Lỗi phổ biến:**
  - `422 Unprocessable Entity`: Không tìm thấy chỗ trống xuyên suốt, hoặc giá AI thấp hơn Bid-price (REJECTED).

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
      "expires_at": "2026-07-17T10:15:00Z",
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
    "seeds": ["20260717", "20260718"]
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

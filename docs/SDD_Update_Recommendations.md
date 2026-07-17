# Khuyến nghị Cập nhật và Hoàn thiện Software Design Document (SDD) - Âu Lạc Railway

Tài liệu này tổng hợp các điểm cần bổ sung vào bản SDD hiện tại để đảm bảo đáp ứng 100% yêu cầu từ đề bài, đồng thời mô tả rõ luồng hoạt động thực tế của hệ thống giữa các tầng (Frontend, Backend, AI Models).

---

## PHẦN 1: CẬP NHẬT THIẾT KẾ CƠ SỞ DỮ LIỆU (DATABASE)

Để lưu trữ đầy đủ các luồng dữ liệu đầu vào và đáp ứng bảo mật (Auth), cần bổ sung và điều chỉnh các bảng sau:

### 1.1. Bổ sung bảng `users` và `refresh_tokens` (Auth & Phân quyền)
Hiện tại hệ thống thiếu cấu trúc lưu trữ để quản lý tài khoản, phân quyền và duy trì phiên đăng nhập bảo mật.
- **Tên bảng:** `users`
  - `user_id` (PK)
  - `username` / `email` (Unique)
  - `password_hash`
  - `role` (Enum: `admin`, `revenue_manager`, `user`)
  - `created_at`, `updated_at`
- **Tên bảng:** `refresh_tokens` (Quản lý phiên đăng nhập/Refresh Token)
  - `token_id` (PK)
  - `user_id` (FK)
  - `token_hash` (Unique, mã hóa của refresh token)
  - `expires_at`
  - `is_revoked` (Boolean)
  - `created_at`

### 1.2. Bổ sung bảng `waiting_list` (Quản lý danh sách chờ - Mục 5.8 PDF)
Đề bài yêu cầu hệ thống tự động tìm và khớp chỗ khi có khách hủy vé.
- **Tên bảng:** `waiting_list`
- **Các trường cần thiết:**
  - `waitlist_id` (PK)
  - `user_id` (FK - Tham chiếu người dùng đặt)
  - `profile_id` (FK - Tham chiếu hồ sơ khách đi)
  - `train_id`, `origin_station_id`, `dest_station_id`
  - `service_date`, `seat_class`
  - `flexibility_preferences` (JSON - Lưu trữ sẵn sàng đổi ghế, đổi ngày)
  - `status` (pending, matched, expired, cancelled)

### 1.3. Mở rộng dữ liệu Ngoại cảnh (External Data - Mục 8.5 PDF)
- **Hành động:** Đổi tên bảng `calendar_event` thành `external_factor`.
- **Cột bổ sung:**
  - `factor_type`: Enum (holiday, weather, traffic, competitor_pricing, local_event)
  - `factor_value`: Giá trị của yếu tố (VD: Mức độ mưa bão, giá vé xe khách).

### 1.4. Cập nhật bảng `booking` (Nhóm khách & Kênh bán)
- **Bổ sung cột `user_id`:** Tham chiếu người tạo booking.
- **Bổ sung cột `group_id` (UUID hoặc Int):** Nhóm các `booking_id` đi cùng nhau (gia đình) để ưu tiên xếp cùng toa/khoang.
- **Bổ sung cột `booking_channel`:** Nguồn đặt (Web, App, OTA).
- **Bổ sung cột `payment_time` và `refund_time`:** Phục vụ phân tích thời gian thanh toán.

### 1.5. Cập nhật bảng `train_stop` và `seat`
- **Bảng `train_stop`:** Thêm cột `arrival_time` để tính tổng thời gian đi (hiện mới có `departure_time`).
- **Bảng `seat_segment_state` (hoặc `seat`):** Thêm trạng thái `blocked` (bên cạnh `free`, `held`, `sold`) để xử lý các ghế bị hỏng/khóa nội bộ.

---

## PHẦN 2: CẬP NHẬT KIẾN TRÚC & THUẬT TOÁN

### 2.1. Thiết kế Service Quản lý Danh sách chờ (Smart Waiting List)
- **Thêm Class:** `WaitlistManagerService`.
- **Nhiệm vụ:** Lắng nghe event khi có vé bị hủy (`SOLD -> FREE`). Quét bảng `waiting_list` theo ưu tiên để tự động gọi `AllocationService` giữ chỗ và báo khách hàng thanh toán.

### 2.2. Bổ sung thuật toán Xếp chỗ cho Nhóm (Group Seating)
Trong `MergeEngine`, thuật toán hiện tại chỉ tối ưu cho ghế đơn (single seat).
- **Nâng cấp:** Thêm hàm `find_group_seats(booking_requests: List[BookingRequest])`.
- **Logic:** Tìm các ghế trống và tính toán hàm chi phí khoảng cách vật lý (cùng toa, ghế liền kề) để sinh ra phương án tối ưu cho cả nhóm khách (ưu tiên trẻ em không tách rời người lớn).

### 2.3. Cập nhật API Authentication & Authorization (Hỗ trợ Refresh Token)
- Cần bổ sung các endpoint: 
  - `/api/v1/auth/register`, `/api/v1/auth/login` (Sinh bộ đôi Access Token & Refresh Token).
  - `/api/v1/auth/refresh` (Sử dụng Refresh Token cũ để cấp Access Token mới).
  - `/api/v1/auth/logout` (Hủy bỏ / Revoke Refresh Token trong Database).
- Thiết lập middleware kiểm tra JWT Token và RBAC (Role-based access control) cho các API nhạy cảm (như ghi đè giá của admin/revenue_manager).

---

## PHẦN 3: LUỒNG HOẠT ĐỘNG THỰC TẾ (RUNTIME WORKFLOW)

Tiến trình xử lý từ khi tìm vé đến khi thanh toán thành công thể hiện sự tương tác chặt chẽ giữa 3 lớp: **Frontend (FE) - Backend (BE) - Model AI**.

### ⚙️ Các tiến trình chạy ngầm (Background Jobs)
Trước khi người dùng thao tác, hệ thống đã chuẩn bị dữ liệu:
* **Model Dự báo (ForecastingService):** Chạy ngầm định kỳ để cập nhật dự báo nhu cầu (O-D demand) dựa trên lịch sử mua, lượt tìm kiếm thất bại, và yếu tố ngoại cảnh.
* **Tối ưu Giá trị biên (Bid-Price Optimizer):** Từ dự báo nhu cầu, BE tính ra giá trị biên (`bid_price`) cho **từng đoạn nhỏ** của tuyến đường để thiết lập ngưỡng giá bán tối thiểu.

### 🚶‍♂️ Bước 1: Khách hàng Tìm kiếm vé (Search & Resolve Options)
1. **[FE]** Người dùng nhập: *Ga đi, Ga đến, Ngày, Hạng ghế*.
2. **[BE]** Nhận request, hệ thống quét **Ma trận trạng thái ghế (Seat State Matrix)** ở thời gian thực.
3. **[Model - Merging]** Thuật toán `MergeEngine` trả về các phương án tốt nhất: Ghế xuyên suốt, ghép đoạn không đổi chỗ, và ghép đoạn có đổi chỗ (với điều kiện nghiêm ngặt).
4. **[Model - Pricing]** `PricingEngine` lấy mức lấp đầy hiện tại của các đoạn để tính mức giá động.
5. **[BE - Guardrail]** Giá AI đề xuất chạy qua `GuardrailEngine` để kiểm tra trần/sàn và biên độ thay đổi, đảm bảo tuân thủ chính sách.
6. **[FE]** Hiển thị danh sách phương án, giá vé (kèm lý do) và nút chốt vé.

### 🛒 Bước 2: Khách hàng Giữ chỗ (Hold Seat)
1. **[FE]** Khách bấm "Đặt vé". FE gọi API `POST /booking/hold`.
2. **[BE - Allocation]** Hệ thống kiểm tra xem giá vé có lớn hơn tổng `bid_price` hiện tại của các đoạn chiếm dụng không. Nếu đủ, cho phép giữ chỗ.
3. **[BE - SeatMatrix]** BE dùng cơ chế Khóa lạc quan (Optimistic Locking) cập nhật Ma trận ghế từ **FREE ➔ HELD**. Một bộ đếm (TTL) được kích hoạt (VD: 10 phút).

### 💳 Bước 3: Thanh toán và Chốt vé (Confirm Booking)
1. **[FE]** Khách hàng thanh toán thành công, gọi API `POST /booking/confirm`.
2. **[BE]** Chuyển trạng thái ghế từ **HELD ➔ SOLD**.
3. **[BE - Guardrail]** Giá của booking này bị đóng băng (frozen).
4. **[BE - Audit]** Hành động mua vé được lưu vào `audit_log`.

### 🔄 Bước 4: Tự cập nhật Hệ thống (System Update & Learning)
Ngay khi vé chuyển sang **SOLD**, hệ thống phản ứng dây chuyền:
1. **[BE]** Khoảng trống ghế biến mất khỏi SeatMatrix.
2. **[BE - SegmentLoad]** Tỷ lệ lấp đầy (Occupancy Rate) tăng lên, cập nhật lên Ops Dashboard.
3. **[Model - Pricing]** Do lấp đầy tăng, các lượt tìm kiếm tiếp theo sẽ tự động có giá vé được AI đẩy lên cao hơn (Dynamic Pricing).
4. **[Model - Allocation]** `Bid-price` cũng tăng lên, hệ thống sẽ ưu tiên nhường ghế trống còn lại cho khách đi đường dài (giá trị cao).

*(Nếu thanh toán thất bại, hết TTL, vé sẽ tự động nhả từ HELD về FREE, cập nhật lại toàn bộ ma trận).*

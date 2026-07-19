# ĐẶC TẢ MÀN HÌNH DEMO — ÂU LẠC RAILWAY

> Bản tổng hợp cuối (2026-07-19). Nguồn: phân tích UX + pitch pipeline + API hiện có.
> Chủ sở hữu triển khai: DEV6 (A6, U1–U3), DEV7 (A1–A5, A7).

## 0. Ba solution phải được "nhìn thấy" trên màn hình

| # | Solution | Màn hình thể hiện chính | Màn hỗ trợ |
|---|---|---|---|
| S1 | **Suggest bán vé chặng ngắn** (AI đề xuất → nhân viên duyệt) | A6 (hàng chờ duyệt + A/B) | A1 (chuông), U2 (khách chờ duyệt), A7 (audit) |
| S2 | **Gợi ý ghép chặng cho khách** (cắt chặng / ghép khoảng trống) | U1 (đặt vé), A2 (ma trận ghế–chặng) | A6 (bằng chứng ghép), U3 (vé có lịch đổi ghế) |
| S3 | **Gợi ý điều chỉnh giá vé** (AI-suggest giá theo O-D, người duyệt) | A4 (phiên đề xuất giá) | A3 (nguyên nhân: dự báo + bid price), A5 (bằng chứng doanh thu), U1 (khối giá 3 dòng) |

Nguyên tắc định vị xuyên suốt (bắt buộc, đã chốt): **AI chỉ đề xuất — con người (nhân viên hoặc khách) là người quyết định cuối cùng.** Mọi copy trên UI dùng từ "đề xuất/gợi ý", không bao giờ "AI đã áp dụng/đã quyết".

## 1. Sơ đồ điều hướng & luồng dữ liệu

```
ADMIN                                          USER (khách)
┌──────────────────────────────────┐           ┌─────────────────────────┐
│ A1 Dashboard                     │           │ U1 Tìm & chọn vé        │
│  ├─ chuông ──────────► A6 Duyệt ◄┼── offer ──┤  (ghép chặng = S2)      │
│  ├─ KPI doanh thu ───► A5 Backtest           │        │ POST /holds    │
│  ├─ cảnh báo lệch ───► A3 Dự báo │           │        ▼                │
│  └─ ghế trống ───────► A2 Ma trận│  duyệt/từ chối      U2 Chờ duyệt    │
│                                  │ ────────────────►  (polling 3–5s)   │
│ A3 Dự báo ◄──► A4 AI-suggest giá │           │        │ confirm        │
│ (nguyên nhân)   (phiên đề xuất=S3)│          │        ▼                │
│ A4 / A6 ─── mỗi quyết định ────► A7 Audit    │ U3 Vé & xác nhận        │
│ A2 ◄─── ô SOLD mới sau khi U3 xong           └─────────────────────────┘
└──────────────────────────────────┘
```

Bất biến phiên bản: mọi màn admin hiển thị `service_run_id / matrix_version / forecast_version / policy_version` ở footer; một quyết định trong A6/A7 luôn tham chiếu đúng bộ 4 version này.

---

## 2. PHÍA ADMIN

### A1 — Dashboard tổng quan
- **Ai dùng:** quản lý doanh thu + nhân viên điều độ (màn mở đầu ca làm việc).
- **Dùng để làm gì:** trả lời trong 10 giây "chuyến hôm nay có ổn không, có gì cần tôi xử lý không"; là điểm vào của kịch bản demo (bấm chuông → A6).
- **Có gì:**
  1. **4 thẻ KPI:** (a) doanh thu hiện tại vs. kịch bản giá cứng, hiện `▲ +x%` — giá trị AI nằm ngay dòng đầu; (b) tỷ lệ lấp đầy trung bình theo chặng; (c) số ghế-chặng trống *cục bộ* có thể ghép (nối S2); (d) **số yêu cầu đang chờ duyệt** — badge đỏ, bấm vào nhảy A6 (nối S1).
  2. **Chuông thông báo** góc phải: đếm request chặng ngắn mới; mỗi item = 1 dòng "THO→DHO · ghế C01-S017 · còn 4:32" → click mở thẳng A6 bước 2.
  3. **Banner cảnh báo độ lệch dự báo** (vàng): hiện khi đường bán thực lệch F(u) quá ngưỡng, kèm nút "Xem dự báo" → A3. Cho thấy AI *biết khi nào nó sai*.
  4. **Sparkline doanh thu theo giờ** trong ngày demo (đồng hồ demo 2026-06-15, không phải giờ thật).
- **Nối với:** A6 (chuông/badge), A5 (thẻ KPI doanh thu), A3 (banner lệch), A2 (thẻ ghế trống).
- **API:** `GET /demo/overview`, `GET /demo/analytics`; danh sách chờ duyệt cần endpoint review-queue mới của DEV6.

### A2 — Ma trận ghế–chặng
- **Ai dùng:** nhân viên điều độ; đồng thời là màn "aha moment" khi trình bày cho hội đồng.
- **Dùng để làm gì:** làm bài toán ghế-trống-cục-bộ **nhìn thấy được** — nền tảng trực quan của S2; trước/sau demo cho thấy khoảng trống được lấp thật.
- **Có gì:**
  1. **Lưới 40 hàng (ghế) × 7 cột (chặng):** ô màu FREE (xanh) / HELD (vàng) / SOLD (xám đậm). Chú giải màu cố định góc trên.
  2. **Highlight khoảng trống ghép được:** dải FREE kẹp giữa 2 dải SOLD được viền nổi (vd. C01-S017 trống L3–L4) — "hàng tồn kho vô hình" mà giá cứng vứt đi.
  3. **Hover ô:** tooltip ghế + chặng + trạng thái; nếu SOLD: mã vé, O-D của khách → chứng minh từng ô là dữ liệu thật.
  4. **Bộ lọc:** chỉ hiện ghế có khoảng trống / theo toa (tư duy scale lên 448 ghế).
  5. **Footer:** `matrix_version` + đồng hồ demo — kể câu chuyện snapshot nhất quán.
- **Nối với:** A6 (mini-matrix trong màn A/B cắt từ đây); tự cập nhật sau khi U3 confirm (2 ô C01-S017 chuyển SOLD — cảnh chốt demo).
- **API:** `GET /demo/seatmap`.

### A3 — Dự báo nhu cầu & Phân bổ chỗ
- **Ai dùng:** quản lý doanh thu.
- **Dùng để làm gì:** màn **nguyên nhân** của S3 — trả lời "AI dựa vào đâu mà đề xuất giá như vậy". A4 là kết quả, A3 là gốc.
- **Có gì:**
  1. **Đường cong đặt chỗ F(u):** trục X = số ngày trước giờ chạy; 2 đường dự báo (nét đứt, kèm vùng tin cậy) vs. thực tế (nét liền). Hai đường bám nhau = mô hình đáng tin; tách nhau = đúng lúc banner A1 bật.
  2. **Heatmap nhu cầu theo cặp O-D** (8×8 nửa tam giác, 28 ô): ô đậm = cầu dự báo cao — cho thấy dự báo ở đúng grain (mác tàu × cặp ga × hạng ghế × ngày) như pitch.
  3. **Bar chart bid price theo 7 chặng:** cột cao = chặng khan hiếm; caption cố định: *"Bid price — nghiệm đối ngẫu LP (DLP), <10ms/chuyến"* (không bao giờ ghi EMSR-b). Đây là cây cầu số học giữa dự báo và giá.
  4. **Bảng hạn mức phân bổ theo chặng** + trạng thái phiên bản phân bổ (đề xuất / đã duyệt) + nút Duyệt/Từ chối/Rollback — human-in-the-loop cấp *chính sách*.
  5. Nút `Refresh dự báo` (POST /demo/forecasts/refresh) → sinh `forecast_version` mới, kích hoạt phiên đề xuất giá mới ở A4.
- **Nối với:** A4 (nút "Xem đề xuất giá từ dự báo này"), A1 (banner lệch trỏ về đây).
- **API:** `GET /demo/analytics`, `POST /demo/forecasts/refresh`, `POST /allocation/{version}/approve|reject|rollback`.

### A4 — AI-suggest giá vé (phiên đề xuất giá) — **màn lõi của S3**
- **Ai dùng:** quản lý doanh thu (người duy nhất có quyền duyệt giá).
- **Dùng để làm gì:** nơi AI đề xuất điều chỉnh giá và **con người sửa/duyệt từng dòng**; đồng thời là nơi trưng bày giải thích tường minh + hàng rào tuân thủ.
- **Mô hình dữ liệu của màn:** làm việc theo **"phiên đề xuất" (pricing session)**:
  - **Phiên #1 — khởi tạo chuyến:** chạy ngay khi chuyến mới phát sinh (demo: gắn vào nút Tạo chuyến / Reset kịch bản). Tàu trống → đề xuất chạy trên dự báo mùa vụ + độ co giãn, Δ khiêm tốn (đúng thiết kế: biên hẹp quanh giá gốc).
  - **Phiên #2, #3…:** tự sinh mỗi lần forecast refresh / đường F(u) lệch ngưỡng — giá trị thật của định giá động nằm ở đây.
  - Mỗi phiên là một bảng đề xuất chờ duyệt → tự thành lịch sử audit "chuyến này chỉnh giá mấy lần, ai duyệt".
- **Đơn vị định giá: cặp O-D + hạng ghế (28 dòng), KHÔNG phải từng ghế.** Cùng hạng cùng O-D = cùng giá (công bằng + đúng khung giá pháp lý). Hiệu ứng thị giác "mỗi ghế một màu giá" làm bằng cách tô sơ đồ ghế theo mức giá của O-D phổ biến, không tách giá từng ghế.
- **Có gì:**
  1. **Chọn phiên đề xuất** (dropdown: Phiên #1 khởi tạo · Phiên #2 sau refresh…) + trạng thái phiên: Chờ duyệt / Đã duyệt / Đã điều chỉnh.
  2. **Bảng 28 dòng O-D**, cột: cặp ga → giá phẳng (gốc) → giá AI đề xuất → **Δ (đồng & %)** → mã lý do (`R_HE2026_XA_NGAY`…) → trạng thái → hành động. **Sort mặc định theo |Δ| giảm dần** (không chỉ tăng — đề xuất *giảm giá* chặng ế để kích cầu đáng chú ý ngang tăng, và cho thấy AI không phải công cụ chỉ tăng giá). Toggle nhóm: Tăng / Giảm / Giữ nguyên.
  3. **Mở rộng 1 dòng → pipeline giải thích ngang:** `Giá gốc 450k → quét tối ưu ±x% (độ co giãn) → bid price chặng L3+L4 → chạm trần +y% (bước bị GẠCH đỏ) → 495k (làm tròn 1.000đ)`. Guardrail thắng AI được vẽ ra, không chỉ nói.
  4. **Khối "Hàng rào đang hiệu lực":** trần/sàn theo khung, giới hạn biến động mỗi lần, bảo vệ giá đã khóa cho hold đang sống, CSXH áp cuối theo `max` không cộng dồn.
  5. **Khối "AI KHÔNG được thấy":** tuổi/khuyết tật/trẻ em một mình, số lần tìm kiếm, thiết bị, IP, lịch sử mua — biến invariant `PricingContext ≠ SafetyContext` thành điểm cộng công khai về công bằng.
  6. **Hành động mỗi dòng:** `Duyệt` / `Điều chỉnh` (nhập giá tay + lý do bắt buộc, hệ thống vẫn clip theo trần/sàn) / `Bỏ qua`. Nút `Duyệt tất cả trong biên an toàn` cho các dòng Δ nhỏ.
- **Nối với:** A3 (nguồn tín hiệu), A7 (mỗi lượt duyệt ghi DecisionRecord), U1 (giá đã duyệt là "Giá áp dụng" khách nhìn thấy).
- **API:** pricing engine + forecast có sẵn; cần endpoint batch mới (loop `PricingEngine` qua 28 O-D theo forecast_version) — rẻ, chưa có trong contract. Override từng dòng nối `POST /offers/{id}/override` hoặc endpoint phiên mới của DEV7 (chốt với BE1).

### A5 — So sánh chiến lược cũ / mới (Backtest replay)
- **Ai dùng:** quản lý cấp cao / dùng khi pitch — màn **bằng chứng** cho cả S1+S2+S3 trên toàn bộ data test.
- **Dùng để làm gì:** chứng minh bằng replay lịch sử rằng AI tăng doanh thu và giảm ghế trống **mà không vi phạm** chính sách nào.
- **Có gì:**
  1. Nút `Chạy replay` + progress: chạy trên 5 event-seed đã commit; kết quả trình bày **median + khoảng dao động** (không một con số duy nhất — "chúng tôi không cherry-pick").
  2. **Biểu đồ 2 đường doanh thu tích lũy:** AI vs. giá cứng, *cùng chuỗi yêu cầu, cùng WTP* — so sánh công bằng trên cùng khách hàng, không phải so 2 tháng khác nhau.
  3. **Thẻ kết quả phụ:** % ghế-chặng trống giảm; số vé chặng ngắn bán thêm (S1); **số vi phạm trần/sàn/CSXH = 0** — đặt cạnh con số tăng doanh thu.
  4. **Ghi chú phương pháp (1 dòng):** "WTP của khách được giữ kín với AI trong suốt replay" — chặn trước câu phản biện "AI nhìn trộm đáp án".
- **Nối với:** A1 (thẻ KPI trỏ về đây), là màn chốt của kịch bản demo.
- **API:** `POST /backtests` → poll `GET /backtests/{id}`.

### A6 — Hàng chờ duyệt bán chặng ngắn (thông báo → A/B → quyết định) — **màn lõi của S1**
- **Ai dùng:** nhân viên điều độ / bán vé.
- **Dùng để làm gì:** cổng phê duyệt con người cho từng đề xuất bán vé chặng ngắn — hiện thân của "thử nghiệm có kiểm soát với phê duyệt thủ công" (pilot giai đoạn 3).
- **Trạng thái backend:** CHƯA CÓ — DEV6 đang xây (offer thêm `requires_staff_review` + `review_id`; gate `422 REVIEW_PENDING` tại `POST /holds`; polling 3–5s, không WebSocket; chấp nhận ceiling: TTL offer 5 phút không gia hạn khi chờ duyệt).
- **Có gì — flow 2 bước trong 1 khu vực:**
  - **Bước 1 — Hàng chờ (danh sách):** mỗi dòng: giờ yêu cầu · O-D (THO→DHO) · ghế ứng viên · giá đề xuất · **đồng hồ đếm ngược TTL offer** (quyết định có chi phí thời gian thật; duyệt chậm → khách phải lấy offer mới) · trạng thái (Mới / Đang xem / Đã xử lý).
  - **Bước 2 — Chi tiết A/B (2 cột đối xứng):**
    | | Cột A — Cách cũ (giá cứng) | Cột B — Đề xuất Âu Lạc |
    |---|---|---|
    | Kết cục | **TỪ CHỐI** — ghế trống L3–L4 chết, doanh thu 0đ | **BÁN** — ghép vào khoảng trống C01-S017, **+Zđ** |
    | Bằng chứng | — | Mini-matrix cắt từ A2, tô đúng 2 ô sẽ lấp |
    | Kinh tế | — | "Chi phí cơ hội (Σ bid price L3+L4) = Yđ < giá bán Zđ → bán có lợi" |
    | Ràng buộc đã kiểm | — | ✅ cùng ghế suốt hành trình · ✅ khách không thuộc nhóm ưu tiên bị đổi chỗ · ✅ giá trong trần/sàn · ✅ CSXH áp cuối |
    Nhân viên không cần hiểu LP dual — chỉ cần thấy *Z > Y và luật không vướng*.
  - **Bước 3 — Quyết định:** nút `Duyệt bán` / `Từ chối` (+ ô lý do bắt buộc khi từ chối). Sau bấm: toast xác nhận, dòng ghi vào A7 kèm tên nhân viên — mỗi quyết định có người ký.
- **Nối với:** A1 (chuông/badge vào đây), U2 (kết quả duyệt đẩy trạng thái khách qua polling), A2 (nguồn mini-matrix), A7 (ghi audit).

### A7 — Chi tiết quyết định / Nhật ký audit
- **Ai dùng:** quản lý, kiểm toán/thanh tra nội bộ; trong demo dùng để chốt câu chuyện tuân thủ.
- **Dùng để làm gì:** trả lời "6 tháng sau, chứng minh vé này được định giá và bán đúng luật thế nào" — gánh trọn lời hứa "giải thích tường minh, ghi nhận kèm mã lý do".
- **Có gì:**
  1. **Danh sách DecisionRecord** (lọc theo ngày/loại/người duyệt) → click vào chi tiết.
  2. **Timeline 1 quyết định:** yêu cầu → phương án ghép được chọn (và các phương án bị loại, kèm lý do loại) → giá từng bước (gốc → linh hoạt → guardrail → CSXH) → ai duyệt, lúc nào → hold → confirm.
  3. **Khối kỹ thuật:** `input_hash` + bộ 4 version (`service_run_id / matrix_version / forecast_version / policy_version`) — mọi thứ tái lập được từ đúng snapshot; bản ghi bất biến (append-only).
- **Nối với:** A4 và A6 đẩy bản ghi vào đây; mọi màn admin có link "Xem quyết định" trỏ về.
- **API:** `GET /decisions/{id}` — có sẵn, `web/app/decisions/` đã tồn tại; gần như miễn phí.

---

## 3. PHÍA USER (khách hàng)

Nguyên tắc ngược với admin: khách **không bao giờ thấy** bid price, elasticity, thuật ngữ AI, hay lý do kỹ thuật. Với khách, hệ thống chỉ là *"có vé hợp lý ở nơi cách cũ nói hết vé"*. Phức tạp thuộc về hệ thống, không thuộc về khách.

### U1 — Tìm & chọn vé (đặt vé) — **màn lõi của S2, mặt tiền của S3**
- **Ai dùng:** khách mua vé.
- **Dùng để làm gì:** khách tìm hành trình, nhận gợi ý ghép chặng như một ghế bình thường, thấy giá minh bạch 3 dòng, và (nếu cần) đồng thuận đổi chỗ.
- **Có gì:**
  1. **Ô tìm kiếm:** ga đi / ga đến / ngày (demo: THO→DHO, 15/06/2026).
  2. **Kết quả khi cách cũ hết vé — khoảnh khắc vàng:** thay vì "Hết chỗ", hiện: *"Còn 1 chỗ cho hành trình của bạn — bạn ngồi nguyên một ghế suốt chặng"*. Câu "nguyên một ghế" chặn trước nỗi sợ bị đổi chỗ.
  3. **Sơ đồ ghế:** chỉ ghế khả dụng *cho đúng O-D của khách* mới sáng; ghế ghép chặng có nhãn nhỏ nhưng chọn được y như ghế thường — khách không cần hiểu "ghép chặng".
  4. **Phương án nhiều ghế (đổi chỗ giữa hành trình) — chỉ khi không còn same-seat:** màn đồng thuận riêng: "Ghế 17 (Ga A→C), đổi sang ghế 21 (Ga C→E); thời gian dừng đủ để di chuyển" + nút đồng ý tường minh. **Tự động ẨN hoàn toàn** với người cao tuổi / khuyết tật / trẻ em đi một mình (invariant cứng của hệ thống — chính sách xã hội nằm trong UI, không nằm trong lời hứa).
  5. **Khối giá 3 dòng:** Giá gốc → Giá áp dụng (nhãn "giá linh hoạt theo nhu cầu") → Giảm chính sách xã hội (nếu chọn) = **Tổng, làm tròn 1.000đ**. Minh bạch cấu trúc mà không lộ cơ chế; CSXH đứng cuối đúng Điều 40.
  6. **Chọn diện CSXH (tự khai):** dropdown; áp **một mức giảm cao nhất**, ghi rõ "không cộng dồn theo quy định" — giảm khiếu nại.
  7. **Đồng hồ giữ giá:** "Giá này được giữ trong 5:00" — cam kết giá chốt ở đây không đổi ở bước sau.
- **Nối với:** U2 (nếu offer có `requires_staff_review` → sau bấm Đặt vé chuyển sang chờ duyệt) hoặc thẳng thanh toán → U3; phía admin: yêu cầu của khách xuất hiện ở chuông A1 + hàng chờ A6.
- **API:** `POST /offers` (báo giá, không giữ ghế) → `POST /holds` (Idempotency-Key, CAS all-or-nothing; `422 REVIEW_PENDING` nếu cần duyệt).

### U2 — Trạng thái chờ duyệt — **nửa kia của S1**
- **Ai dùng:** khách vừa đặt vé chặng ngắn cần nhân viên duyệt.
- **Dùng để làm gì:** biến "chờ" thành chờ-có-ngữ-cảnh, và là bằng chứng trực quan phía khách rằng có con người phê duyệt.
- **Có gì:**
  1. Trạng thái sống (polling 3–5s): *"Yêu cầu của bạn đang được nhân viên xác nhận"* + spinner + **đồng hồ TTL của offer**.
  2. **Được duyệt:** chuyển thẳng thanh toán với **đúng giá đã báo** (hold/confirm không bao giờ re-price) — chờ không bị đổi giá.
  3. **Bị từ chối / offer hết hạn (410):** thông báo tử tế + gợi ý lối ra (chuyến khác, hạng khác, tìm lại) — fail không dead-end; khớp ceiling TTL 5 phút không gia hạn.
- **Nối với:** nhận kết quả từ A6; timeout → quay về U1.
- **API:** polling trạng thái review (endpoint DEV6), `POST /bookings/{hold_id}/confirm` khi được duyệt.

### U3 — Xác nhận & vé
- **Ai dùng:** khách đã thanh toán.
- **Dùng để làm gì:** khép vòng — vé thật, và phía admin ma trận A2 đổi màu ngay.
- **Có gì:** vé điện tử: ghế, (các) chặng, giá cuối, mã vé, mã quyết định; nếu vé ghép có đổi chỗ: **in rõ lịch đổi ghế kèm ga đổi** (disclosure lần cuối). 
- **Nối với:** A2 (2 ô C01-S017 chuyển SOLD — cảnh chốt demo), A7 (mã quyết định tra được).
- **API:** `POST /bookings/{hold_id}/confirm` (idempotent).

---

## 4. Kịch bản demo khép kín (thứ tự trình chiếu)

1. **A2** — chỉ vào khoảng trống C01-S017 L3–L4: "đây là hàng tồn kho vô hình mà giá cứng vứt đi" (đặt vấn đề, S2).
2. **U1** — khách tìm THO→DHO: cách cũ từ chối, Âu Lạc mời mua nguyên-một-ghế, giá 3 dòng minh bạch (S2 + S3 phía khách).
3. **A1 → A6** — chuông reo, nhân viên mở A/B: 0đ vs +Zđ, ràng buộc ✅ hết, bấm **Duyệt** (S1 — AI đề xuất, người quyết).
4. **U2 → U3** — khách thấy được duyệt, thanh toán đúng giá đã báo, nhận vé.
5. **A2** — quay lại: 2 ô vừa chuyển SOLD — dữ liệu thật xuyên suốt.
6. **A4** — mở phiên đề xuất giá: bảng 28 O-D sort theo |Δ|, mở 1 dòng xem pipeline giải thích + guardrail gạch đỏ (S3 phía quản lý).
7. **A3** — (nếu bị hỏi "giá từ đâu ra") đường F(u) + bid price 7 chặng.
8. **A5** — chạy replay cả bộ data test: median tăng x%, ghế trống giảm, **0 vi phạm** (bằng chứng nhân rộng).
9. **A7** — (nếu bị hỏi tuân thủ/thanh tra) mở đúng quyết định vừa duyệt: timeline + input_hash + 4 version.

## 5. Trạng thái hiện thực (để chia việc, không đưa vào pitch)

| Màn | Nền tảng có sẵn | Việc phải làm |
|---|---|---|
| A1 | `GET /demo/overview`, `/analytics`; `web/app/admin/overview` | Thẻ chờ-duyệt cần review-queue của DEV6 |
| A2 | `GET /demo/seatmap`; `web/app/admin/seat-matrix`, `web/app/ops/seatmap` | Highlight khoảng trống ghép được |
| A3 | `GET /demo/analytics`, forecast refresh, allocation approve; `web/app/forecast` | Ghép các khối vào 1 màn |
| A4 | PricingEngine + forecast + override | **Endpoint batch phiên đề xuất (28 O-D) — mới**, chốt contract với BE1 |
| A5 | `POST/GET /backtests`; `web/app/admin/backtest` | Trình bày median+range, thẻ 0-vi-phạm |
| A6 | — | **Toàn bộ mới** (DEV6: review table + `requires_staff_review` + gate 422 tại /holds + polling) |
| A7 | `GET /decisions/{id}`; `web/app/decisions/` | Timeline hoá, gần như miễn phí |
| U1–U3 | offers/holds/confirm; `web/app/booking/*` | Trạng thái chờ duyệt (DEV6), copy ghép chặng, khối giá 3 dòng |

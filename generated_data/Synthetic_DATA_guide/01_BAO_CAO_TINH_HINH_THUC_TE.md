# BÁO CÁO TÌNH HÌNH THỰC TẾ ĐƯỜNG SẮT HÀNH KHÁCH VIỆT NAM
## Phục vụ bài toán: AI cắt chặng – ghép chặng – giá vé linh hoạt
**Kỳ báo cáo:** 07/2025 – 07/2026 (mốc chốt dữ liệu: 17/07/2026)
**Mục đích:** Xác lập nền sự thật (ground truth) để hiệu chuẩn (calibrate) bộ dữ liệu mô phỏng ở Tài liệu 02 và 03.

---

## 0. Tóm tắt điều hành (Executive summary)

1. **Ngành đường sắt đang tăng trưởng nhưng quy mô nhỏ**: ~7,1 triệu lượt khách/năm (2024), ~3,9 triệu lượt trong 6 tháng đầu 2026. Đây là con số quan trọng nhất cho việc định cỡ dataset: **quy mô bài toán là hàng triệu vé/năm, không phải hàng trăm triệu** → dataset mô phỏng đầy đủ 1–3 năm là hoàn toàn khả thi trên một máy trạm.
2. **VNR ĐÃ triển khai chính "lời giải" của bài toán này từ 01/5/2026**: tính năng **"Giá vé linh hoạt"** dùng AI tự động quét các **chặng ngắn còn trống** sau khi chuyến tàu đã bán một phần cho hành trình dài, và giảm giá **15%–35%**. Đây không còn là bài toán giả định — nhóm đang cạnh tranh với một hệ thống đã chạy thật. Hệ quả kỹ thuật: **dữ liệu lịch sử có một điểm gãy chính sách (policy regime shift) vào 01/5/2026** và mọi mô hình phải xử lý điều này.
3. **Cấu trúc giá hiện hành đã là "dynamic pricing dạng luật"** (rule-based): giảm theo lead time, theo cự ly, theo chiều tàu, theo tập thể, theo khứ hồi, theo đối tượng chính sách; **tăng 3–7% khi mua sát ngày**. Bộ luật này phải được tái tạo *nguyên vẹn* trong dataset, vì nó chính là "chính sách nền" (baseline policy) mà AI phải đánh bại và là nguồn biến thiên giá để nhận dạng độ co giãn.
4. **Rủi ro thiên tai là biến ngoại sinh bậc nhất**, không phải chi tiết trang trí: năm 2025 phải **dừng hơn 300 chuyến tàu**, chuyển tải gần **8.500 lượt khách**; riêng đợt bão số 13 + mưa lũ 6–22/11/2025 đã **dừng 44 đoàn tàu khách**, **hoàn 39.000 vé ≈ 24 tỷ đồng**, phong tỏa nhiều đoạn Km1123–Km1339.
5. **Khung pháp lý mới**: Luật Đường sắt số 95/2025/QH15 (hiệu lực 01/01/2026) và Nghị định 16/2026/NĐ-CP (14/01/2026) quy định miễn/giảm giá cho đối tượng chính sách xã hội → đây là **ràng buộc cứng (hard constraint)** của bài toán tối ưu, không phải mục tiêu mềm.

---

## 1. Kết quả sản xuất kinh doanh (số liệu chính thống)

### 1.1. Toàn Tổng công ty Đường sắt Việt Nam (VNR)

| Chỉ tiêu | 2024 | 2025 | 6T/2026 |
|---|---|---|---|
| Doanh thu hợp nhất | > 9.600 tỷ (+7,4%) | **> 10.700 tỷ (+10%)** | – |
| Lợi nhuận | 110 tỷ (+43,2%) | **139 tỷ (+5,3%)** | – |
| Doanh thu Công ty mẹ | – | 3.031 tỷ (+10,2%) | – |
| Hành khách vận chuyển | **> 7,1 triệu lượt (+15,5%)** | – | **~3,9 triệu lượt (+5,2%)** |
| Hàng hóa | 5,1 triệu tấn (+10,5%) | – | ~2,3 triệu tấn (85,9% CK) |
| Doanh thu vận tải | – | – | **2.921,2 tỷ (+8,4%)** |
| Thu nhập BQ | – | 14 triệu/người/tháng (+8%) | – |

*Nguồn: Hội nghị triển khai KHSXKD 2026 của VNR (28/12/2025) — Báo Nhân Dân; báo cáo VNR 6T/2026 — Báo Xây dựng 09/07/2026.*

### 1.2. Công ty CP Vận tải đường sắt (Traravico – đơn vị vận tải chủ lực), 6T/2026

- Doanh thu vận tải: **2.727,3 tỷ (+8,7%)**; trong đó **doanh thu vận tải hành khách 2.003 tỷ (+10,8%)**.
- **Tết Bính Ngọ: ~779.000 lượt khách (+9,5%), doanh thu ~556 tỷ (+12,4%)** — "mùa cao điểm tốt nhất nhiều năm gần đây".
- Tăng trưởng doanh thu theo tuyến: **Hà Nội – Lào Cai +27%**, **Hà Nội – Đà Nẵng (SE19/20) +12%**, **Hà Nội – Hải Phòng +12%**.
- Tàu **"Hành trình di sản" Huế – Đà Nẵng** (khai thác từ tháng 3/2026): **sản lượng +11%, doanh thu +41%**.
- **13 chuyến tàu charter**: 5.400 khách, > 16 tỷ đồng.

> **Các hằng số hiệu chuẩn rút ra (dùng bắt buộc ở Tài liệu 02):**
> - Doanh thu bình quân/lượt khách 6T/2026 ≈ 2.003 tỷ / 3,9 triệu ≈ **≈ 514.000 đ/lượt**
> - Doanh thu bình quân/lượt khách dịp Tết ≈ 556 tỷ / 779.000 ≈ **≈ 714.000 đ/lượt** (cao hơn ~39% mức bình quân năm — do cả *mix* cự ly dài lẫn *mức giá* cao hơn; mô hình phải tách được hai hiệu ứng này)
> - Doanh thu charter bình quân ≈ 16 tỷ / 5.400 ≈ **≈ 2,96 triệu đ/khách**

### 1.3. Cảnh báo phương pháp luận về số liệu vĩ mô

Số liệu Cục Thống kê cho biết "vận tải hành khách đường sắt năm 2025 tăng **106,5%**" (11 tháng) và Quý I/2025 tăng **165,1%** đạt **12 triệu lượt**. Con số này **KHÔNG mâu thuẫn** với con số ~7 triệu lượt/năm của VNR: mức tăng đột biến là do **Cục Thống kê bổ sung sản phẩm đường sắt đô thị (metro Hà Nội, metro số 1 TP.HCM) vào phạm vi thống kê**, tức là **thay đổi định nghĩa phạm vi (scope break)**, không phải tăng trưởng thực.

> ⚠️ **Đây là bài kiểm tra đầu tiên về tính chuẩn xác dữ liệu**: nếu nhóm lấy series "vận tải hành khách đường sắt" của Cục Thống kê làm chuỗi mục tiêu, mô hình sẽ học một cú nhảy giả (spurious level shift). **Chỉ dùng số liệu VNR/Traravico cho bài toán đường sắt quốc gia.** Trong dataset phải có cột `pham_vi_thong_ke` để đánh dấu các đứt gãy định nghĩa.

---

## 2. Mạng lưới, biểu đồ chạy tàu và sức chứa (cấu trúc bài toán)

### 2.1. Trục Thống Nhất

- Chiều dài Hà Nội – Sài Gòn: **1.726 km**. Toàn mạng ~3.143 km (7 tuyến chính), đi qua ~20–21 tỉnh/thành sau sáp nhập.
- Lý trình tham chiếu (đã kiểm chứng chéo, đơn vị: km tính từ ga Hà Nội):
  **Ga Đà Nẵng: Km 791+400**; cách Vinh 472 km ⇒ **Vinh ≈ Km 319**; cách Huế 103 km ⇒ **Huế ≈ Km 688**; cách Quảng Ngãi 136,5 km ⇒ **Quảng Ngãi ≈ Km 927,5**; cách Diêu Trì 304 km ⇒ **Diêu Trì ≈ Km 1.095**; cách Nha Trang 523,5 km ⇒ **Nha Trang ≈ Km 1.314,5**; cách Sài Gòn 935 km ⇒ **Sài Gòn = Km 1.726**.
  *(Các lý trình khác phải lấy từ Công lệnh tốc độ/Công lệnh tải trọng của VNR hoặc dsvn.vn — xem Tài liệu 03, §2.)*

### 2.2. Biểu đồ chạy tàu hiện hành (từ 15/5/2026 – kiểm chứng 07/2026)

**Trục Bắc – Nam: 5 đôi tàu Thống Nhất chạy hằng ngày** SE1/2, SE3/4, SE5/6, SE7/8, SE9/10.

| Tàu | Xuất phát ga Hà Nội | Tàu | Xuất phát ga Sài Gòn |
|---|---|---|---|
| SE1 | 21:45 | SE2 | 20:35 |
| SE3 | 19:20 | SE4 | 19:20 |
| SE5 | 08:00 | SE6 | 08:45 |
| SE7 | 06:00 | SE8 | 06:00 |
| SE9 | 13:00 | SE10 | 13:15 |

**Tàu khu đoạn / du lịch (2025–2026):**
- SE19/20 (Hà Nội – Đà Nẵng), SE17/SE18, SE27 (tăng cường HN–ĐN 09/3–13/4/2026)
- NA1/NA2 (Hà Nội – Vinh)
- SE21/22 (TP.HCM – Đà Nẵng), SE29/30 (TP.HCM – Quy Nhơn), SNT1/2 (TP.HCM – Nha Trang), SPT1/2 (TP.HCM – Phan Thiết)
- **HĐ1/2, HĐ3/4 "Kết nối di sản" / "Hành trình di sản" (Huế – Đà Nẵng)** – 2 đôi/ngày
- **SP3/4, SP7/8 (Hà Nội – Lào Cai)**
- **4 đôi "Hoa Phượng Đỏ" (Hà Nội – Hải Phòng): HP1/2, LP5/6, LP2/3, LP7/8** + tăng cường LP9, LP10, HD2 cuối tuần
- DL1/2…DL11/12 (Đà Lạt – Trại Mát), tàu 2 tầng **"Hà Nội 5 Cửa Ô"** (từ 19/8/2025)

**Ý nghĩa cho bài toán:** trục Thống Nhất là một **đồ thị đường thẳng (path graph)**, tàu khu đoạn chồng lấn lên trục chính (SE19/20 phủ HN→ĐN; SE21/22 phủ SG→ĐN; NA1/2 phủ HN→Vinh). Vì vậy **cạnh tranh nội bộ (internal competition) giữa các mác tàu trên cùng khu gian là có thật** và phải nằm trong mô hình lựa chọn (choice model), không được bỏ qua.

### 2.3. Thành phần đoàn tàu & sức chứa (tham chiếu)

- Đoàn SE điển hình: **11–14 toa xe khách**; toa ghế ngồi mềm điều hòa (~56–64 chỗ), toa giường nằm khoang 6 (**42 chỗ = 7 khoang × 6**), toa giường nằm khoang 4 (**28 chỗ = 7 khoang × 4**), một số toa có khoang VIP 2 giường.
- Dịp Tết Bính Ngọ 2026: **55 đoàn tàu/ngày, > 800 toa xe, cung ứng ~330.000 vé đi suốt**; riêng tuyến HN–TP.HCM chạy **906 chuyến, cung ứng ~384.000 vé đi suốt** trong đợt 3/2–8/3.
- Dịp 30/4–1/5/2026: **182 chuyến thường xuyên (~90.000 chỗ đi suốt) + 47 chuyến tăng cường (>22.000 chỗ)**.
- Dịp hè 2026 (15/5–16/8): **~1,5 triệu vé chặng suốt**.
- **Hệ số sử dụng chỗ đạt 79%** trong tuần 22–29/4/2026 (tăng 9% cùng kỳ, 12% so tháng trước) sau khi bật AI giá linh hoạt.

---

## 3. Chính sách giá thực tế (bộ luật phải tái tạo 1:1)

### 3.1. Giảm giá theo đối tượng chính sách xã hội — **ràng buộc pháp lý cứng**

Theo Nghị định 65/2018/NĐ-CP (Điều 24) và nay là **Điều 40 Nghị định 16/2026/NĐ-CP** hướng dẫn Luật Đường sắt 95/2025/QH15:

| Đối tượng | Mức giảm |
|---|---|
| Người hoạt động cách mạng trước 19/8/1945; Bà mẹ VN anh hùng | **90%** |
| Thương binh, người hưởng chính sách như thương binh, nạn nhân chất độc hóa học, người khuyết tật đặc biệt nặng/nặng | **30%** |
| Người cao tuổi (≥ 60 tuổi) | **≥ 15%** |
| Trẻ em 6 – <10 tuổi | 25% (chính sách doanh nghiệp) |
| Học sinh, sinh viên | 10% (20% trong một số đợt Tết) |
| Trẻ em < 6 tuổi đi cùng người lớn | **Miễn vé** (dùng chung chỗ; tối đa 2 trẻ/người lớn) |
| Đoàn viên công đoàn (vé cá nhân) | 5% |

**Quy tắc hợp thành:** hưởng **một mức giảm cao nhất, KHÔNG cộng dồn** → về mặt toán học là toán tử `max`, không phải tích các hệ số.

### 3.2. Giảm/tăng giá thương mại (dữ liệu 2025–2026)

**Tết Bính Ngọ 2026** (mở bán tập thể 15–19/9/2025; mở bán rộng rãi **8:00 ngày 20/9/2025**; cao điểm **3/2 – 8/3/2026**):
- Mua **xa ngày ≥10 ngày**, **cự ly > 900 km**: giảm **5%–15%**, chỉ áp dụng **tàu chiều Lẻ trước Tết (3/2–17/2)** và **chiều Chẵn sau Tết (21/2–8/3)** → tức **giảm giá cho chiều rỗng**.
- Giảm **3%** cho tàu xuất phát ga Sài Gòn ngày **15/2/2026 (28 tháng Chạp)**, cự ly ≥ 1.000 km.
- Vé tập thể ≥ 11 người: giảm **2%–12%**. Vé lượt về: giảm **5%**.
- Giá vé Tết 2026 **tăng 4–5%** so với Tết 2025.
- **Sau Tết, 23–27/2/2026**: giảm **40% giá vé giường nằm** tàu **SE chẵn** cho khách có **ga đi từ Đông Hà đến Phủ Lý** và **ga đến từ Mỹ Trạch đến Hà Nội**; giảm **20%** với tàu **TN chẵn** cùng điều kiện.
  → ⭐ **Đây chính là "cắt chặng có định giá" thủ công**: chính sách được định nghĩa trên **cặp (miền ga đi, miền ga đến)**, tức trên **ô của ma trận O–D**, không phải trên toàn chuyến. Dataset bắt buộc phải biểu diễn được luật dạng này.

**Hè 2026** (bán từ ~11/4/2026, tàu chạy 15/5–16/8):
- Giá vé **tăng 5–10%** so với hè 2025 do biến động giá nhiên liệu.
- Khứ hồi: giảm **10%** lượt về; riêng HN–Lào Cai (SP2/SP4/SP8): giảm **15%**.
- Tập thể ≥ 20 người, mua trước 10–19 ngày: giảm **3%–9%**.
- Cá nhân mua trước ≥ 20 ngày: giảm **5%–10%**, với **ngưỡng cự ly theo mác tàu**: SE1–SE12 (≥ 900 km), SE21/22 (≥ 600 km), SE29/30 (≥ 400 km), SNT1/2 (≥ 300 km). **Giới hạn 20 vé giảm giá cho mỗi loại chỗ trên mỗi đoàn tàu**; **không áp dụng** khoang 4 giường của SE3, SNT1/2, SPT1/2.
- **Mua sát ngày (≤ 2 ngày trước giờ tàu chạy): TĂNG 5%–7%** (giai đoạn sau hè: tăng 3%–5%).
- SE17 (HN→ĐN) các ngày T7/CN/T2/T3 từ 21/5–16/8: giảm thêm **5%**.
- **1/7 – 16/8/2026**: giảm **10%** giá vé tàu SE Bắc–Nam, SG–Nha Trang, HN–Vinh (do giá nhiên liệu giảm) — tương đương **110.000–280.000 đ/vé**.

**Sau hè (17/8 – 30/12/2026):** khứ hồi −10%; HN–Lào Cai −15%; tập thể ≥20 người −3%…−9%; chặng dài mua trước ≥10 ngày −5%…−15%; sát ngày ≤2 ngày **+3%…+5%**.

### 3.3. ⭐ "Giá vé linh hoạt" bằng AI — từ 01/5/2026

- Thí điểm **22–29/4/2026**: bán **9.376 vé**, doanh thu **2 tỷ đồng**, **giảm giá trực tiếp cho khách 523 triệu đồng** (≈ **20,7%** trên doanh thu gộp trước giảm ≈ 2,523 tỷ); **hệ số sử dụng chỗ 79%** (+9% cùng kỳ, +12% so tháng trước); **10,36%** hành khách được hưởng khuyến mãi.
- Chính thức từ **01/5/2026**, áp dụng **tất cả các mác tàu**.
- Cơ chế: *"Dựa trên tình hình thực tế của chuyến tàu khi đã bán được một phần cho hành trình dài, các chặng ngắn còn lại sẽ được hệ thống AI truy quét, tính toán và đưa ra mức giảm giá phù hợp theo từng thời điểm mua vé."*
- **Biên độ giảm: tối thiểu 15%, tối đa 35%.** Theo tuyến: HN–Hải Phòng, HN–Lào Cai **20–25%**; HN–ĐN, SG–Phan Thiết/Nha Trang/Quy Nhơn/ĐN **15–25%**; **Huế–ĐN đến 30%**; chặng ngắn Thống Nhất **đến 35%**.
- **Minh bạch**: vé ưu đãi hiển thị **màu xanh nhạt** kèm mức giảm; thông báo "Tàu này đang có khuyến mãi chỗ giá rẻ".

> **Kết luận quan trọng nhất của báo cáo:** VNR đã hiện thực hóa đúng cơ chế mà đề bài yêu cầu, nhưng ở dạng **giảm giá một chiều (chỉ giảm, không tăng)** và **chỉ trên chặng ngắn còn trống**. Khoảng trống mà nhóm có thể chiếm lĩnh: (i) **dự báo nhu cầu O–D** để quyết định *khi nào* mới nên nhả chặng ngắn (nhả sớm → mất khách dài giá cao; nhả muộn → ghế chạy rỗng); (ii) **ghép khoảng trống (gap merging)** — hiện chưa có bằng chứng công khai VNR làm; (iii) **quota cắt chặng động** thay vì luật cố định; (iv) **bid price** để lượng hóa chi phí cơ hội của một vé chặng ngắn đi qua khu gian nút cổ chai.

### 3.4. Đổi/trả vé

- Khấu trừ **30%** giá tiền in trên thẻ đi tàu. Vé cá nhân: trả trước giờ tàu chạy **≥ 24 giờ**; vé tập thể **≥ 48 giờ**.
- **Từ 00:00 ngày 15/5/2026: đổi/trả vé trực tuyến trên dsvn.vn**, xác thực bằng OTP, không cần ra ga.
  → **Tác động lên dataset**: rào cản trả vé giảm mạnh ⇒ **tỷ lệ trả vé tăng và trả muộn hơn** từ 15/5/2026 ⇒ **thêm một điểm gãy chế độ thứ hai** và làm gia tăng số "khoảng trống" (gaps) phát sinh trong giai đoạn cận ngày.

### 3.5. Kênh bán

dsvn.vn, vetau.com.vn, vetauonline.vn, giare.vetau.vn; nhà ga & đại lý; ví điện tử MoMo, VNPay, ZaloPay, ViettelPay; Smart Banking; app di động; tích hợp Zalo/Facebook/YouTube/Google Maps. **Vé tàu dự kiến tích hợp lên VNeID từ quý IV/2026.**
→ Kênh là biến giải thích thật (khách ga/đại lý có hành vi mua muộn hơn, ít nhạy giá hơn, tỷ lệ đối tượng chính sách cao hơn).

---

## 4. Thiên tai, thời tiết và gián đoạn khai thác (biến ngoại sinh bậc nhất)

### 4.1. Sự kiện đã xảy ra

| Thời gian | Sự kiện | Hệ quả định lượng |
|---|---|---|
| 2024 | Sạt lở hầm **Bãi Gió**, **Chí Thạnh** | Ách tắc tuyến HN–TP.HCM **> 20 ngày** qua 2 đợt |
| 2024 | Bão số 3 **Yagi**, bão số 6 **Trà Mi** | Thiệt hại hạ tầng |
| **6–22/11/2025** | **Bão số 13 (Kalmaegi)** + mưa lũ Nam Trung Bộ | **Dừng 44 đoàn tàu khách**; hoàn **25.200 vé ≈ 17,6 tỷ** (sau đó **39.000 vé ≈ 24 tỷ**); miễn phí 9.400 suất ăn chính + 6.100 suất phụ (~623 triệu); **34 đoàn tàu chuyên tuyến** ngừng (~9,5 tỷ) |
| 19/11/2025 | Mưa lũ khu vực **Nha Trang – Diêu Trì** | Dừng **4 mác tàu Thống Nhất** trong ngày |
| Từ 23/11/2025 | **Chuyển tải bằng đường bộ ga Tuy Hòa ↔ ga Giã** | Tàu từ Nam dừng ở **ga Giã**, từ Bắc dừng ở **ga Tuy Hòa** |
| 08/12/2025 | Bộ Xây dựng **công bố tình huống khẩn cấp** | Hư hỏng nghiêm trọng: **Km1123+600–Km1139+100**, **Km1204+200–Km1219+742**, **Km1337+900–Km1339+850**; riêng **Km1136+850–Km1136+925** (khu gian Vân Canh – Phước Lãnh) **trôi 75 m nền đường, sâu 9 m** |
| Cả năm 2025 | Tổng hợp | **Dừng > 300 chuyến tàu**, **chuyển tải gần 8.500 lượt khách** |

**Hằng số hiệu chuẩn:** hoàn vé bình quân đợt lũ 11/2025 ≈ 24 tỷ / 39.000 ≈ **≈ 615.000 đ/vé** (hoặc 17,6 tỷ / 25.200 ≈ **698.000 đ/vé**) → cao hơn giá vé bình quân năm (~514k) ⇒ **khách bị hủy chuyến thiên lệch về chặng dài, giá cao**. Đây là một **cơ chế chọn mẫu (selection)** phải mô phỏng đúng, không được hủy ngẫu nhiên đều.

### 4.2. Quy luật mùa thiên tai theo vùng (dùng cho λ của quá trình gián đoạn)

- **Bắc Bộ & Bắc Trung Bộ (Km 0 – Km 500):** bão/lũ tập trung **tháng 7 – 9**.
- **Trung Trung Bộ (Km 500 – Km 900, Huế – Đà Nẵng – Quảng Ngãi):** **tháng 9 – 12**, đỉnh tháng 10–11.
- **Nam Trung Bộ (Km 900 – Km 1.400, Diêu Trì – Tuy Hòa – Nha Trang):** **tháng 10 – 12**, đỉnh **tháng 11** (đúng như đợt 11/2025).
- **Nam Bộ (Km 1.400 – 1.726):** rủi ro thấp; ảnh hưởng chủ yếu là mưa lớn cục bộ.
- **Đèo Hải Vân (Km ~740–790)** và các hầm: điểm xung yếu cấu trúc (sạt lở đất đá, không cần bão).

### 4.3. Nắng nóng / mưa và nhu cầu

- Nắng nóng gay gắt Bắc/Trung Bộ tháng 5–7 → tăng nhu cầu đi biển (Sầm Sơn/Cửa Lò qua ga Thanh Hóa/Vinh; Nha Trang, Phan Thiết, Quy Nhơn, Đà Nẵng).
- Mưa dông → giảm nhẹ nhu cầu du lịch chặng ngắn cuối tuần, gần như **không ảnh hưởng** nhu cầu về quê/công vụ chặng dài.
→ Về mặt mô hình: **thời tiết tác động lên nhu cầu là hiệu ứng nhỏ và không đồng nhất theo mục đích chuyến đi**; tác động **lớn** của thời tiết là qua kênh **gián đoạn nguồn cung**. Đừng đảo ngược hai kênh này.

---

## 5. Lịch mùa vụ, lễ Tết, sự kiện (2025–2026)

### 5.1. Lịch nghỉ chính thức 2026

| Dịp | Ngày (dương lịch) | Số ngày |
|---|---|---|
| Tết Dương lịch | 01/01 – 04/01/2026 | 4 |
| **Tết Nguyên đán Bính Ngọ** (**mùng 1 = 17/02/2026**) | **14/02 – 22/02/2026** | **9** |
| Giỗ Tổ Hùng Vương (10/3 ÂL = CN 26/4, nghỉ bù T2 27/4) | 25/04 – 27/04/2026 | 3 |
| 30/4 – 1/5 (rơi vào T5, T6) | 30/04 – 03/05/2026 | 4 |
| Quốc khánh 2/9 | 01/09 – 02/09/2026 | 2 (một số nơi hoán đổi tới 5) |

Tổng ngày nghỉ lễ + cuối tuần + hoán đổi năm 2026: **26 ngày**.
Mốc Tết các năm để dựng biến `tau = ngày lệch so với mùng 1`: **Tết 2024 = 10/02**, **Tết 2025 = 29/01**, **Tết 2026 = 17/02**, **Tết 2027 = 06/02**.
→ **Bắt buộc dùng biến âm lịch tương đối, KHÔNG dùng "tháng dương lịch"**: Tết trượt gần 3 tuần giữa các năm, mô hình dùng month-of-year sẽ học sai hoàn toàn (xem Tài liệu 02, §4.3).

### 5.2. Đợt cao điểm vận tải (do VNR công bố)

- **Cao điểm Tết Bính Ngọ: 03/02 – 08/03/2026** (16 tháng Chạp Ất Tỵ → 20 tháng Giêng Bính Ngọ). Mở bán từ **20/9/2025** ⇒ **horizon đặt chỗ H ≈ 136–169 ngày**.
- Trong 9 ngày nghỉ Tết (14/2–22/2): chạy thêm **33 chuyến khu đoạn** (SG–Nha Trang, SG–Tam Kỳ, SG–Đà Nẵng, HN–Vinh, HN–Đà Nẵng, HN–Lào Cai).
- **Cao điểm hè: 15/05 – 16/08/2026**. **Sau hè: 17/08 – 30/12/2026**.
- Cao điểm 30/4–1/5 và 2/9.
- Hơn **140.000 vé tàu Tết Bính Ngọ** đã bán tính đến ~12/2025; **> 60.000 vé** sau 1 tháng mở bán; **> 44.000 vé** dịp cao điểm 30/4; Tết Dương lịch 2026 bổ sung **20.000 chỗ**.

### 5.3. Sự kiện & yếu tố hút khách (event covariates)

- **Đại hội Đảng toàn quốc lần thứ XIV: 19–23/01/2026**; **Bầu cử ĐBQH khóa XVI & HĐND các cấp nhiệm kỳ 2026–2031** (2026) → nhu cầu công vụ về Hà Nội.
- Du lịch: **6T/2026 đón 12,3 triệu lượt khách quốc tế (+14,9%)**, phục vụ **~81 triệu lượt khách nội địa**, tổng thu **~569 nghìn tỷ**; mục tiêu năm **25 triệu khách quốc tế**. Khách quốc tế đến bằng đường không chiếm 82,6%.
- Sự kiện thường niên có ảnh hưởng cục bộ mạnh (phải gắn với ga cụ thể): Lễ hội pháo hoa quốc tế Đà Nẵng (ga Đà Nẵng, T6–T7), Festival Huế (ga Huế), Lễ hội biển Nha Trang (ga Nha Trang), Lễ hội Đền Hùng (ga Việt Trì – ngoài trục Thống Nhất), mùa lúa chín Y Tý/Sa Pa (ga Lào Cai, T9–T10), mùa du lịch biển Sầm Sơn/Cửa Lò (ga Thanh Hóa/Vinh, T5–T8).
- **Mùa nhập học/khai giảng tháng 8–9** → luồng học sinh, sinh viên về Hà Nội & TP.HCM (VNR có chính sách giảm giá tân sinh viên đến 31/10 hằng năm).
- **Cạnh tranh phương thức**: đường bay HN–TP.HCM là một trong những đường bay nội địa bận rộn nhất thế giới; **5 dự án cao tốc Bắc–Nam qua miền Trung bắt đầu thu phí từ 15/7/2026** → thay đổi chi phí tương đối của đường bộ; **giá nhiên liệu biến động mạnh 2026** (VNR tăng giá hè 5–10% rồi giảm 10% từ 1/7 khi nhiên liệu hạ) → **giá vé đường sắt là biến nội sinh theo chi phí đầu vào**.

### 5.4. Các ga đông khách nhất (trọng số hấp dẫn A_i)

Nhóm 1 (đầu mối lớn): **Hà Nội, Sài Gòn**.
Nhóm 2 (trung tâm vùng/du lịch lớn): **Đà Nẵng (Km 791), Nha Trang (Km 1.314,5), Huế (Km 688), Vinh (Km 319)**.
Nhóm 3: **Thanh Hóa (Km ~175), Đồng Hới (Km ~522), Diêu Trì (Km 1.095), Quảng Ngãi (Km 927,5), Biên Hòa (Km ~1.697), Tháp Chàm, Bình Thuận (Mương Mán), Tam Kỳ, Đông Hà, Tuy Hòa, Dĩ An**.
Ngoài trục: **Hải Phòng, Lào Cai, Đà Lạt/Trại Mát, Quy Nhơn, Phan Thiết**.

### 5.5. Ràng buộc địa lý – hành chính (bẫy dữ liệu)

Từ **01/7/2025** Việt Nam vận hành **34 đơn vị hành chính cấp tỉnh** sau sáp nhập. Hệ quả trực tiếp: **ga Tuy Hòa nay thuộc Đắk Lắk** (Phú Yên cũ), **ga Giã thuộc Khánh Hòa**, đoạn tuyến hư hỏng 11/2025 được mô tả thuộc **"Gia Lai, Đắk Lắk, Khánh Hòa, Lâm Đồng"** thay vì Bình Định/Phú Yên/Ninh Thuận.
→ **Bảng `ga` phải là SCD Type-2 theo tỉnh** (`tinh_truoc_01072025`, `tinh_tu_01072025`, `hieu_luc_tu`, `hieu_luc_den`). Nếu join dữ liệu dân số/du lịch theo tỉnh mà không xử lý, mọi biến gravity sẽ sai từ 01/7/2025 trở đi.

---

## 6. Khung pháp lý & quản trị (ràng buộc cứng cho AI)

| Văn bản | Nội dung liên quan |
|---|---|
| **Luật Đường sắt số 95/2025/QH15** (QH thông qua 27/6/2025) | Hiệu lực **01/01/2026** (một số điều từ 01/7/2025) |
| **Nghị định 16/2026/NĐ-CP** (ban hành & hiệu lực **14/01/2026**) | Quy định chi tiết Luật Đường sắt; **Điều 40**: miễn/giảm giá vận tải hành khách cho đối tượng chính sách xã hội |
| **Quyết định 2072/QĐ-TTg** (17/9/2025) | Kế hoạch triển khai thi hành Luật Đường sắt |
| Nghị định 65/2018/NĐ-CP | Khung mức giảm 90%/30%/15% (nền của Điều 40 NĐ 16/2026) |
| Bộ luật Lao động 2019, Điều 112 | Cơ sở của lịch nghỉ lễ (biến calendar) |
| Định hướng 2026–2030 | VNR **chuyển đổi sang mô hình Tập đoàn**; mục tiêu tăng trưởng 2026 **≥ 2 con số**; Đề án tái cơ cấu trình Thủ tướng |

**Diễn giải sang ràng buộc tối ưu:**
1. `giá ≥ giá_sàn` và `giá ≤ giá_trần` đã duyệt → ràng buộc hộp (box constraint), vi phạm = loại.
2. Giảm giá chính sách xã hội áp trên **giá vé bán thực tế của loại chỗ, loại tàu mà đối tượng sử dụng** → nghĩa là **giảm chính sách được tính SAU giảm động**, không phải trước. Thứ tự toán tử này ảnh hưởng trực tiếp doanh thu; phải khai báo tường minh.
3. Không cộng dồn ưu đãi → `max`, không `∏`.
4. Không định giá theo dữ liệu cá nhân nhạy cảm, không tăng giá vì khách tìm kiếm lặp lại → **ràng buộc trên tập đặc trưng đầu vào (feature set), kiểm chứng được bằng kiểm toán schema**, không phải bằng lời hứa.
5. Giá đã giữ chỗ (đã xác nhận) không được thay đổi → **tính bất biến của giá theo thời gian sau khi hold**.

---

## 7. Danh mục 12 rủi ro & bẫy dữ liệu quan trọng nhất

| # | Bẫy | Hệ quả nếu bỏ qua | Cách chặn |
|---|---|---|---|
| 1 | Đứt gãy phạm vi thống kê (metro nhập vào ĐS) | Học cú nhảy giả +106% | Chỉ dùng số VNR; cột `pham_vi_thong_ke` |
| 2 | **Điểm gãy chính sách 01/5/2026** (AI giá linh hoạt) | Mô hình huấn luyện trên chế độ cũ → sai lệch phân phối | Cột `che_do_gia`; đánh giá riêng từng chế độ |
| 3 | Điểm gãy 15/5/2026 (trả vé online) | Tỷ lệ/thời điểm trả vé đổi | Cột `kenh_tra_ve`; hazard model theo chế độ |
| 4 | **Kiểm duyệt cầu (demand censoring)**: chỉ thấy vé bán, không thấy nhu cầu bị từ chối | Dự báo thấp hơn thực tế ở chặng "cháy vé" (chính là chặng cần tối ưu nhất) | **Bắt buộc log yêu cầu tìm kiếm**; unconstraining (EM) |
| 5 | **Nội sinh của giá**: giá thấp vì ế, không phải ế vì giá cao | Ước lượng độ co giãn ngược dấu | Log luật giá + thăm dò ngẫu nhiên ε; IV/DML |
| 6 | Dùng tháng dương lịch thay vì lệch ngày âm lịch | Tết trượt 3 tuần → nhiễu lớn | Biến `tau = D − mùng1(năm)` |
| 7 | Sáp nhập tỉnh 01/7/2025 | Join gravity sai | SCD-2 cho bảng ga |
| 8 | Dữ liệu O–D cực thưa (nhiều 0) | MAPE = ∞; RMSE vô nghĩa | MASE, Poisson deviance, pinball; mô hình đếm |
| 9 | **Không nhất quán phân cấp**: dự báo O–D không cộng bằng dự báo khu gian | Quyết định quota mâu thuẫn | Hòa giải MinT với ma trận tổng S = A |
| 10 | Rò rỉ thời gian (dùng hệ số chiếm chỗ cuối cùng làm feature) | Backtest đẹp, production sập | As-of join theo `thoi_diem_biet` |
| 11 | Hủy chuyến do thiên tai bị mô phỏng ngẫu nhiên đều | Mất cơ chế chọn mẫu (khách chặng dài bị hủy nhiều hơn) | Gián đoạn = phong tỏa **khu gian**, hủy theo phủ khu gian |
| 12 | Bỏ qua cạnh tranh nội bộ giữa mác tàu | Đánh giá pricing quá lạc quan | Nested logit trên tập lựa chọn thật |

---

## 8. Nguồn tham chiếu

1. Báo Nhân Dân, *"Năm 2025, ngành đường sắt đạt lợi nhuận 139 tỷ đồng"*, 28/12/2025 — https://nhandan.vn/nam-2025-nganh-duong-sat-dat-loi-nhuan-139-ty-dong-post933551.html
2. Báo Xây dựng, *"Gần 3,9 triệu lượt khách đi tàu trong 6 tháng đầu năm"*, 09/07/2026 — https://baoxaydung.vn/gan-39-trieu-luot-khach-di-tau-trong-6-thang-dau-nam-192260709122856484.htm
3. An ninh Thủ đô, *"Đường sắt áp dụng AI bán vé tàu, tự động truy quét tạo 'giá linh hoạt' trên chặng ngắn"*, 29/04/2026 — https://anninhthudo.vn/duong-sat-ap-dung-ai-ban-ve-tau-tu-dong-truy-quet-tao-gia-linh-hoat-tren-chang-ngan-post647666.antd
4. VNR (vr.com.vn), *"Chính thức áp dụng giảm giá vé linh hoạt trên hệ thống bán vé điện tử"* — https://vr.com.vn/cac-uu-dai-danh-cho-khach-hang/chinh-thuc-ap-dung-giam-gia-ve-linh-hoat-tren-he-thong-ban-ve-dien-tu.html
5. VNR (vr.com.vn), *"Từ ngày 15/5, có thể đổi vé, trả vé trực tuyến mà không cần ra ga"* — https://vr.com.vn/cam-nang-di-tau/tu-ngay-155-co-the-doi-ve-tra-ve-truc-tuyen-ma-khong-can-ra-ga.html
6. Công ty CP Vận tải đường sắt, *"Mở bán vé tàu Tết Nguyên đán Bính Ngọ 2026"*, 15/09/2025 — https://cophanvantaiduongsat.vn/2025/09/15/mo-ban-ve-tau-tet-nguyen-dan-binh-ngo-2026/
7. Báo Xây dựng, *"Đường sắt giảm giá vé tới 40% sau Tết Bính Ngọ 2026"*, 23/02/2026 — https://baoxaydung.vn/duong-sat-giam-gia-ve-toi-40-sau-tet-binh-ngo-2026-192260223162033246.htm
8. Báo Pháp Luật TP.HCM, *"Mở bán vé tàu hè 2026: Mua sớm giảm giá, mua sát ngày tăng 5%-7%"*, 11/04/2026 — https://plo.vn/mo-ban-ve-tau-he-2026-mua-som-giam-gia-mua-sat-ngay-tang-5-7-post903784.html
9. Báo Văn hóa, *"Điều chỉnh giá vé tàu hè 2026, triển khai AI săn vé rẻ đến 35%"*, 08/05/2026 — https://baovanhoa.vn/doi-song/dieu-chinh-gia-ve-tau-he-2026-trien-khai-ai-san-ve-re-den-35-225882.html
10. Báo Chính phủ, *"Tuyến đường sắt quốc gia hư hỏng nghiêm trọng sau bão lũ"*, 15/12/2025 — https://baochinhphu.vn/tuyen-duong-sat-quoc-gia-hu-hong-nghiem-trong-sau-bao-lu-102251215214553163.htm
11. CafeF/Bộ Xây dựng, *"Công bố tình huống khẩn cấp trên tuyến đường sắt Bắc - Nam"*, 08/12/2025 — https://cafef.vn/cong-bo-tinh-huong-khan-cap-tren-tuyen-duong-sat-bac-nam-188251208135100611.chn
12. Người Đưa Tin, *"Dự kiến thông tuyến đường sắt Bắc – Nam sau 8 ngày gián đoạn do mưa lũ miền Trung"*, 25/11/2025 — https://www.nguoiduatin.vn/du-kien-thong-tuyen-duong-sat-bac-nam-sau-8-ngay-gian-doan-do-mua-lu-mien-trung-204251125172945767.htm
13. Nhân Dân, *"Sáu tháng đầu 2026, khách quốc tế đến Việt Nam đạt 12,3 triệu lượt người"*, 07/2026 — https://nhandan.vn/sau-thang-dau-2026-khach-quoc-te-den-viet-nam-dat-123-trieu-luot-nguoi-post973401.html
14. LuatVietnam, *"Nghị định 16/2026/NĐ-CP quy định chi tiết Luật Đường sắt"* — https://luatvietnam.vn/giao-thong/nghi-dinh-16-2026-nd-cp-quy-dinh-chi-tiet-luat-duong-sat-co-hieu-luc-tu-14-01-2026-424207-d1.html
15. VNR, *"Quy định việc bán vé và giá vé áp dụng cho các đối tượng chính sách xã hội"* — https://vr.com.vn/cac-quy-dinh/quy-dinh-viec-ban-ve-va-gia-ve-ap-dung-cho-cac-doi-tuong-chinh-sach-xa-hoi.html
16. Báo Xây dựng, *"Vé tàu sau hè chính thức mở bán, nhiều ưu đãi cho hành khách"*, 04/07/2026 — https://baoxaydung.vn/ve-tau-sau-he-chinh-thuc-mo-ban-nhieu-uu-dai-cho-hanh-khach-192260704100130352.htm
17. Báo Pháp Luật TP.HCM, *"Chi tiết các đoàn tàu Bắc Nam chạy dịp Tết Dương lịch 2026"*, 26/12/2025 — https://plo.vn/chi-tiet-cac-doan-tau-bac-nam-chay-dip-tet-duong-lich-2026-post888533.html
18. Wikipedia tiếng Việt, *Ga Đà Nẵng* (lý trình Km 791+400 và cự ly tới các ga chính) — https://vi.wikipedia.org/wiki/Ga_%C4%90%C3%A0_N%E1%BA%B5ng
19. Báo Chính phủ, *"Vận tải khách đường sắt tăng trưởng rõ nét trong năm 2025"*, 21/12/2025 — https://baochinhphu.vn/van-tai-khach-duong-sat-tang-truong-ro-net-trong-nam-2025-102251221122029112.htm
20. Cổng dsvn.vn — *Chính sách giá vé, quy định đổi–trả vé năm 2026* — https://dsvn.vn/

> **Ghi chú về mức độ tin cậy:** Mục 1, 3, 4, 5.1, 5.2, 6 dựa trên nguồn chính thống (báo chí nhà nước, cổng VNR, văn bản QPPL) và có thể trích dẫn trực tiếp trong hồ sơ dự thi. Mục 2.3 (số chỗ/toa) và các mức giá vé cụ thể lấy từ đại lý/tổng hợp → **phải thay bằng dữ liệu cào từ dsvn.vn** trước khi hiệu chuẩn cuối cùng (xem Tài liệu 03, §2).

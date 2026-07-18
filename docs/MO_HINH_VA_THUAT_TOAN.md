# MÔ HÌNH & THUẬT TOÁN — Chi tiết kỹ thuật

Tài liệu đặc tả chi tiết TỪNG mô hình học máy và thuật toán tối ưu: phát biểu toán học,
đầu vào/ra, tham số, độ phức tạp, lý do chọn, và điểm cài đặt then chốt. Mã nguồn tương
ứng ghi trong ngoặc.

Ký hiệu chung: một chuyến tàu có `L` đoạn (khu gian) liên tiếp `e = 1..L`; ghế `s`; hành
trình O–D phủ dải đoạn liên tiếp `[i, j)`. Tiền là **int64 đồng**.

---

## 1. BT1 — Dự báo cầu (Demand Forecasting)  ·  `models/train_bt1_forecast.py`, `app/bt1_forecast.py`

### 1.1 Loại mô hình
**Gradient Boosting cây hồi quy, hàm mất mát Poisson** —
`sklearn.ensemble.HistGradientBoostingRegressor(loss="poisson")`.

Lý do chọn Poisson thay vì bình phương sai số (MSE):
- Nhãn là **số đếm không âm, thưa** (median 1–2 vé/grain). MSE giả định nhiễu Gauss đối
  xứng → dự báo âm/lệch cho đuôi. Poisson giả định `y ~ Poisson(μ)`, `Var = μ`, phù hợp
  dữ liệu đếm.
- Hàm mất mát tối thiểu hoá **Poisson deviance**:
  `D = 2·Σ [ y·ln(y/μ) − (y − μ) ]`, với `μ = exp(F(x))`, `F` = tổng các cây.

Vì sao "histogram" boosting: rời rạc hoá đặc trưng thành bin → train nhanh trên **2,4
triệu dòng grain**, hỗ trợ **categorical gốc** (không cần one-hot) và **NaN gốc** (lag
thiếu ở đầu chuỗi).

### 1.2 Grain & đặc trưng
- **Grain (đơn vị dự báo):** `(mac_tau, ga_di, ga_den, seat_class, ngay_chay)`.
- **Nhãn:** `q_final` = tổng vé HIEU_LUC của grain.
- **Đặc trưng hạng mục:** `mac_tau, ga_di, ga_den, seat_class, band, dot_ban_ve,
  che_do_gia, dow`.
- **Đặc trưng số:** `da_ban_truoc_u14` (pickup — tín hiệu mạnh nhất), `toc_do_ban_7d`,
  `cu_ly_km`, `tau_tet` (lịch âm tương đối), `la_le`, `H_horizon`, `sau_15_5`, `q_lag_7`,
  `rolling_mean_28`.

### 1.3 Chống rò rỉ (2 lớp)
1. **Không gian đặc trưng khoá tại u = 14 ngày:** chỉ dùng thông tin biết trước mốc dự
   báo (vé lead_time < 14 chưa tồn tại).
2. **Chia theo `ngay_chay` tại điểm gãy 01/5/2026** (train = LUAT, test = AI), KHÔNG chia
   theo `thoi_diem_mua` — vì vé Tết bán trước tới 169 ngày, chia theo lúc mua sẽ rò rỉ
   xuyên horizon. (Bản `feat` còn siết thêm: bỏ `q_lag_7` rò rỉ, dùng lag lịch ≥15 ngày +
   embargo 14 ngày + valid set riêng — chống rò rỉ chuẩn hơn; xem NOTE_DEV §4.)

### 1.4 Siêu tham số & kết quả
`learning_rate=0.06, max_iter=600, max_leaf_nodes=63, min_samples_leaf=40,
l2_regularization=1.0, early_stopping, validation_fraction=0.1, seed=20260717`.

Test (giai đoạn AI, 507.764 dòng): **MASE = 0.515** (baseline pickup 0.796; naïve lag-7 =
1) · **Poisson deviance = 0.393** · **bias = −5.6%**.

> MASE (Mean Absolute Scaled Error) = MAE mô hình / MAE của dự báo naïve mùa vụ (lag-7).
> MASE < 1 ⇒ thắng naïve; dùng MASE/deviance vì dữ liệu đếm thưa (MAPE vô nghĩa khi y=0).

### 1.5 Đường cong đặt chỗ F(u) & DemandModel  ·  `models/build_bt1_curves.py`
Ước lượng **hàm sống sót thực nghiệm**:
`F(u | band, tết) = P(lead_time ≥ u)` = tỉ lệ vé đã bán trước mốc u, tính theo (băng cự
ly × cửa sổ Tết). Ví dụ F(14): ngắn 0.40 / trung 0.74 / dài 0.92 (Tết cao hơn).

`DemandModel` dùng F(u) để:
- **Cầu còn lại:** `remaining(u) = total × (1 − F(u))`.
- **Cập nhật liên tục (không train lại):** unconstrain pickup `total_pickup = sold / F(u)`
  rồi blend `total = 0.5·total_model + 0.5·total_pickup`.
- **Tín hiệu lệch (drift):** `divergence = (sold − total·F(u)) / (total·F(u))` → cấp cho
  C2 (nhả ghế).

### 1.6 Độ phức tạp
Train: `O(n·d·log n)` (histogram). Suy luận 1 grain: `O(#cây · độ_sâu)` ≈ vài µs.

---

## 2. Mô hình CO GIÃN GIÁ (Elasticity)  ·  `models/estimate_elasticity.py`, `app/elasticity.py`

### 2.1 Nhận diện toán học
Trong DGP, quyết định mua là `WTP < giá_niêm_yết`. Cả WTP lẫn giá đều tỉ lệ với F0 theo
tier ⇒ **tier triệt tiêu**, xác suất mua chỉ phụ thuộc **tỉ lệ giá** `r = giá / F0`:

**Mô hình logistic:**
`logit P(mua | r, ctx) = β₀ + β_r·ln(r) + Σ β_band·1[band] + β_tết·1[tết] + Σ β_lead·1[lead_bin]`

### 2.2 Dữ liệu & ước lượng (chỉ quan sát được)
- **Số ca MUA + giá r:** từ `transactions` (`r = gia_niem_yet / gia_goc`).
- **Số ca KHÔNG mua:** `search_log.ket_qua = BO_VI_GIA`. Loại `TU_CHOI_HET_CHO` (từ chối
  do hết chỗ — không phải quyết định giá).
- **Ghép cell** `(chuyen_id, ga_di, ga_den, lead_bin)`: giá gần như cố định trong cell (giá
  tất định theo trạng thái) → gán r cho nhóm BO_VI_GIA cùng cell.
- **KHÔNG dùng `phan_khuc`** (mục đích chuyến = dữ liệu cá nhân) → giá công bằng.
- Fit logistic có trọng số (mỗi cell → 1 dòng "mua" w=n_mua + 1 dòng "bỏ" w=n_bo).

**Kết quả:** `β_r = −1.19` (âm ⇒ cầu giảm khi giá tăng). `P(mua)`: 0.606 (r=1.0) → 0.553
(r=1.2). Cầu **kém co giãn** trong dải quan sát.

### 2.3 Cảnh báo thiên lệch nội sinh (endogeneity)
Giá cao trùng lúc cầu/WTP cao (phụ thu Tết/nghẽn). Đặc trưng chỉ khử được một phần ⇒ β
lệch về 0 (cầu *trông* kém co giãn hơn thực). Hệ quả cài đặt: **cấm ngoại suy** — bộ tối
ưu chỉ chạy trong dải hẹp quanh F0 (xem §8.2).

### 2.4 Tối ưu doanh thu
Chọn `r*` tối đa **đóng góp kỳ vọng**:
`r* = argmax_r  P(mua | r) · (r·F0 − c)`,  với `c` = bid price hành trình (§4).
Cài bằng **quét lưới** 40 điểm trên `[floor_r, ceil_r]` (đơn biến, hàm không lồi nhẹ →
lưới an toàn & rẻ hơn tối ưu giải tích).

---

## 3. BT2 — Seat State Matrix  ·  `app/bt2_ssm.py`

### 3.1 Cấu trúc
Mỗi `(chuyến, lớp_chỗ)` là ma trận `int8` kích thước `(n_ghế, L)`, ô ∈ `{0 TRỐNG, 1
ĐÃ_BÁN, 2 ĐANG_GIỮ}`. Hành trình O–D chiếm cột `[i, j)` nửa mở.

### 3.2 Thuật toán then chốt
- **`assign` nguyên tử:** `if (m[s, i:j] != TRỐNG).any(): return False` — kiểm cả dải
  trước khi ghi; xung đột ⇒ không ghi gì. Chống race "hai khách một ghế".
- **`first_fit`:** `ok = (m[:, i:j] == TRỐNG).all(axis=1); idx = argmax(ok)` —
  vector hoá, `O(n_ghế · độ_dài_dải)`.
- **Dựng bằng replay:** phát lại giao dịch theo thứ tự mua (lead_time giảm) + first-fit →
  cùng thuật toán gán với generator ⇒ tải từng đoạn nhất quán.
- **Giữ chỗ có hạn / sổ giá khoá:** `hold_with_expiry`, `expire_holds` (nhả quá hạn → sinh
  gap), `lock_price` (honor held price).

---

## 4. BT3 — Phân bổ tồn kho (DLP) & Bid price  ·  `app/bt3_allocation.py`

### 4.1 Quy hoạch tuyến tính (giải riêng từng lớp chỗ)
```
max_y   Σ_k f_k · y_k
s.t.    A y ≤ c        (mỗi đoạn ≤ chỗ còn lại)
        0 ≤ y_k ≤ D_k  (≤ cầu dự báo mỗi O–D)
```
`y_k` = số vé mở bán cho O–D thứ k; `f_k` = giá; `A[e,k] = 1` nếu O–D k đi qua đoạn e;
`c_e` = chỗ còn lại đoạn e; `D_k` = cầu dự báo (từ BT1).

### 4.2 Vì sao KHÔNG cần MILP — tính nguyên
`A` là **ma trận liên thuộc đoạn–hành trình**, mỗi cột có các số 1 **liên tiếp** (hành
trình phủ đoạn liền kề) ⇒ `A` có tính **hoàn toàn đơn modular (TU)**. Với `A` TU và biên
`c, D` nguyên, **mọi đỉnh của đa diện khả thi đều nguyên** ⇒ nghiệm LP tối ưu tự nguyên.
Nhờ đó dùng LP (HiGHS) thay vì MILP → giải một chuyến **< 10 ms**.

### 4.3 Bid price = đối ngẫu
Bài đối ngẫu gán mỗi ràng buộc sức chứa đoạn e một biến `π_e ≥ 0` (giá bóng / shadow
price) = **doanh thu tăng thêm nếu có thêm 1 ghế trên đoạn e** = chi phí cơ hội bán 1 chỗ
ở đoạn đó. Cài: `π = −marginals` của `A_ub` từ `scipy.optimize.linprog(method="highs")`.
`π_e` cao ⇔ đoạn nghẽn. **Đây là tín hiệu khan hiếm theo đoạn** cấp cho định giá (§8).

### 4.4 Hạn mức lồng nhau (nested booking limit)
Quota chặng ngắn trên đoạn nghẽn = `chỗ_còn − Σ (bảo vệ cho hành trình dài/trung qua đoạn
đó)`. Bảo đảm không bán rẻ chặng ngắn làm mất chặng dài giá cao.

---

## 5. BT4 — Ghép chặng (Segment Merging)  ·  `app/bt4_merge.py`, `integration/resolver_multiseat.py`

### 5.1 Ghế đơn — lọc & xếp hạng
`free_full = (m[:, i:j] == TRỐNG).all(axis=1)` — các ghế trống suốt [i, j). Phân loại:
- **pristine:** trống toàn tuyến → phương án "xuyên suốt".
- **gap_khit:** trống trên [i, j) nhưng bận nơi khác; **độ khít** = số ô trống thừa hai
  biên = `(i − mép_bận_trái) + (mép_bận_phải − j)`; xếp **khít nhất trước** (giữ ghế trống
  dài cho hành trình dài).

### 5.2 Ghép nhiều ghế — phủ khoảng tối thiểu tham lam
Khi không còn ghế đơn, phủ [i, j) bằng ≥2 ghế:
```
pos = i
while pos < j:
    tại cột pos, chọn ghế FREE có "run trống" dài nhất tới end
    (không đặt điểm đổi tại ga dwell < 5 phút)
    thêm mảnh (ghế, pos, end);  pos = end
```
- **Đúng đắn:** mỗi bước lấy dải phủ xa nhất từ `pos` ⇒ số mảnh tối thiểu (đây là bài phủ
  khoảng cổ điển, tham lam tối ưu).
- **Độ phức tạp:** `O((j−i) · n_ghế)`; guard `≤ (j−i)` chặn vòng lặp.
- **transfers = số mảnh − 1**; ga đổi = biên giữa các mảnh.

### 5.3 Ràng buộc bắt buộc (không chỉ tối ưu)
- Ga đổi có **dwell ≥ 5 phút**; **cùng lớp chỗ**; **`requires_customer_consent=True`**
  (phải disclosure & khách đồng ý); **loại trừ** nhóm ưu tiên (cao tuổi/khuyết tật/trẻ đi
  một mình/cần hỗ trợ) → `resolve` trả rỗng cho họ.

---

## 6. C4 — Xếp nhóm (Group Seating, CP-SAT)  ·  `app/group_seating.py`

### 6.1 Mô hình ràng buộc (OR-Tools CP-SAT)
Biến: `x_s ∈ {0,1}` chọn ghế s; `uc_t` (dùng toa t); `uk_k` (dùng khoang k).
Ràng buộc: `Σ x_s = n`; `x_s ⇒ uc_{toa(s)}`, `x_s ⇒ uk_{khoang(s)}`; `span = max_s{s·x_s}
− min_s{s·x_s}`.

**Mục tiêu (trọng số từ vựng):**
`min  10000·Σ uc_t + 100·Σ uk_k + span`
→ ưu tiên **ít toa ≫ ít khoang ≫ dải ghế hẹp**.

### 6.2 Vì sao CP-SAT
Bài xếp nhóm "cùng khoang/liền kề" là tổ hợp (NP-khó tổng quát). CP-SAT cho **nghiệm tối
ưu chứng minh được** ở quy mô 1 toa (≤ ~56 ghế) trong mili-giây, **tất định** (1 luồng +
seed). Có **fallback tham lam** (ưu tiên 1 khoang đủ chỗ → 1 toa cửa sổ hẹp nhất → rải)
nếu thiếu OR-Tools.

---

## 7. C5 & C2 — Hàng chờ & Tái phân bổ  ·  `app/waitlist.py`, `app/reallocation.py`

### 7.1 Điểm ưu tiên hàng chờ (tất định, phi cá nhân)
`score = 0.4·min(F0/1.5tr,1) + 0.3·1/(1+u) + 0.2·min(bid/150k,1) + 0.1·1[CSXH]`
= (giá trị doanh thu) × (độ gấp theo lead-time) × (khan hiếm đoạn) × (quyền lợi xã hội).
Khớp khi có ghế nhả: duyệt score giảm dần → gọi BT4 tìm ghế.

### 7.2 Tái phân bổ động
Đầu vào: `divergence` (§1.5). Nếu `|lệch| ≥ 15%`: (1) `expire_holds` nhả giữ chỗ quá hạn;
(2) cập nhật cầu còn lại → **re-solve DLP** (§4); (3) so quota cũ/mới → đề xuất `MO_THEM`/
`SIET_LAI`. Thuần đề xuất, chờ duyệt.

---

## 8. BT5 — Định giá động  ·  `app/bt5_pricing.py`

### 8.1 Giá gốc F0
`F0 = ρ_t · ς_tier · κ₀ · d^θ` (θ = 0.87); `κ₀` hiệu chỉnh từ neo giá thật SE1 HN–SG →
khớp chính xác cột `gia_goc` dataset.

### 8.2 Bước động (elasticity, dải hẹp)
Chọn `r*` = argmax `P(mua|r)·(r·F0 − bid_route)` trên:
- trần động `ceil_r = 1 + 0.15·LF_max` (đoạn càng đầy càng cho tăng — phản ánh khan hiếm);
- sàn động `floor_r = 1 − 0.05·(1 − LF_max)` (đoạn ế cho giảm nhẹ).
Dải hẹp **cố ý** để không ngoại suy ra vùng β thiên lệch (§2.3).

### 8.3 Thứ tự toán tử (bất biến — không đảo)
```
F0 → (elasticity) → cap biến động ±5%/lần → clip sàn/trần [0.55, 1.6]·F0
   = GIÁ NIÊM YẾT → CSXH SAU CÙNG (max một mức, không cộng dồn) = GIÁ CUỐI
```
- **Giá đã khoá (held):** short-circuit, trả nguyên (chỉ áp CSXH).
- **Tất định:** giá chỉ phụ thuộc trạng thái tồn kho + lịch; KHÔNG dùng dữ liệu cá nhân /
  số lần tìm kiếm. Có test `test_price_invariant...`.
- Mỗi báo giá kèm `rule_ids` + câu giải thích (audit/XAI).

---

## 9. Kiểm chứng — phương pháp  ·  `eval/replay.py`, `eval/metrics.py`, `eval/backtest.py`

### 9.1 Replay 2 chính sách
Phát lại `search_log` theo thời gian, chạy song song **FCFS** (first-fit, giá tĩnh) và
**AI** (BT3+BT4+BT5+quota gating). Khách quyết định bằng **WTP thật** (`_ground_truth/
wtp.parquet` — chỉ để chấm, cấm làm feature). So thêm với **z_opt** (tối ưu offline hindsight).

### 9.2 Chỉ số & kết quả
MASE, hệ số sử dụng pax-km, số gap ghép, % đổi chỗ, unmet→sale, refund, độ công bằng giá,
p95 tính lại. Kết quả 4 tàu × 2 ngày: **Tết doanh thu +2.3% (đạt 89.0% z_opt vs FCFS
87.0%)**, ghế trống cục bộ **−52%**, p95 **~8 ms**, **0 vi phạm**.

---

## 10. Bảng tổng hợp lựa chọn kỹ thuật

| Bài toán | Kỹ thuật | Vì sao |
|---|---|---|
| Dự báo cầu | GBM Poisson | dữ liệu đếm thưa; nhanh; categorical/NaN gốc |
| Cầu còn lại | đường cong F(u) thực nghiệm | dự báo theo lead-time + cập nhật không train lại |
| Co giãn giá | Logistic P(mua\|r) | nhận diện được (tier triệt tiêu); giải thích được |
| Phân bổ | DLP (LP), ma trận TU | nghiệm nguyên miễn phí; <10ms; cho bid price |
| Ghép chặng | phủ khoảng tham lam | tối thiểu số ghế/đổi chỗ; O((j−i)·n) |
| Xếp nhóm | CP-SAT | tối ưu chứng minh được; tất định |
| Định giá | tối ưu doanh thu + guardrail | max E[đóng góp]; hành lang pháp lý cứng |
| Đánh giá | replay + WTP ground-truth | chấm điểm khách quan AI vs FCFS vs tối ưu |

*Chi tiết vận hành: `README_models.md`. Tích hợp backend: `BACKEND_GUIDE.md`, `NOTE_DEV.md`.*

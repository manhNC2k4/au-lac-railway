# BÁO CÁO KỸ THUẬT
## Hệ thống AI cắt chặng – ghép chặng – định giá động cho vận tải hành khách đường sắt

**Phiên bản:** v1 (lớp Model + Thuật toán) · **Nhánh:** `algomodel` · **Ngày:** 2026-07-18
**Phạm vi báo cáo:** mô tả chi tiết các MÔ HÌNH và THUẬT TOÁN đã triển khai, kết quả
kiểm chứng, cách chuyển sang một phiên bản dữ liệu khác, và lộ trình xây dựng Backend.

---

## Mục lục
1. Tổng quan kiến trúc
2. Mô hình (Models)
3. Thuật toán (Algorithms)
4. Bất biến & ràng buộc pháp lý/chính sách
5. Kiểm chứng & kết quả (backtest)
6. Hạn chế đã biết
7. Chuyển sang phiên bản dữ liệu khác
8. Lộ trình Backend
9. Phụ lục: artifact & tham số

---

## 1. Tổng quan kiến trúc

Hệ thống chia làm ba tầng, nối với nhau qua **một cấu trúc dữ liệu trung tâm — Seat
State Matrix (SSM)** và **một bảng hợp đồng dataclass** (`app/contracts.py`). Nguyên
tắc: output của bài toán trước = input của bài toán sau; tất cả đọc/ghi vào SSM.

```
Ngoại sinh (lịch, sự kiện, gián đoạn)
        │
        ▼
[BT1] Dự báo cầu ──────────────┐
   (O-D, ngày, tàu, lớp chỗ, u) │  forecast
        │                       ▼
        │             [BT3] Phân tích tải + phân bổ (DLP)
        │                 LF đoạn · quota · bid price
        │                       │
        ▼                       ▼
[BT2] SEAT STATE MATRIX  ◄──► [BT4] Ghép chặng ──► [C4] Xếp nhóm
   ma trận ghế × đoạn           phương án ghế        [C5] Hàng chờ
   {trống, đã_bán, giữ}         │                    [C2] Nhả & tái phân bổ
        │                       ▼
        └────────────► [BT5] Định giá động (elasticity + bid price)
                          giá qua guardrail + log giải thích
```

Toàn bộ hàm ở tầng thuật toán là **thuần đề xuất** (không tự áp giá / không gán ghế
vĩnh viễn trừ khi được gọi tường minh), mỗi output kèm `ProposalLog` + `explain` để
Backend lưu làm audit trail.

**Công nghệ:** Python 3.13 · NumPy/pandas · scikit-learn (HistGradientBoosting,
LogisticRegression) · SciPy HiGHS (LP) · OR-Tools CP-SAT (xếp nhóm) · PyArrow/Parquet
· FastAPI (demo).

---

## 2. Mô hình (Models)

### 2.1 BT1 — Dự báo cầu (Demand Forecasting)

**Bài toán.** Ước lượng số vé của mỗi grain `(tàu, ga_đi, ga_đến, lớp_chỗ, ngày_chạy)`.
Cầu là dữ liệu **đếm, thưa** ⇒ dùng MASE / Poisson deviance làm chỉ số, KHÔNG dùng MAPE.

**Mô hình.** `HistGradientBoostingRegressor(loss="poisson")` — gradient boosting cây
hồi quy với hàm mất mát Poisson.

| Siêu tham số | Giá trị |
|---|---|
| learning_rate | 0.06 |
| max_iter | 600 (early stopping, validation_fraction=0.1) |
| max_leaf_nodes | 63 |
| min_samples_leaf | 40 |
| l2_regularization | 1.0 |
| categorical_features | `from_dtype` (native categorical) |

**Đặc trưng (leakage-safe tại mốc u=14 ngày trước khởi hành):**
- *Hạng mục:* `mac_tau, ga_di, ga_den, seat_class, band(cự ly), dot_ban_ve, che_do_gia, dow`
- *Số:* `da_ban_truoc_u14` (pickup — số vé đã bán khi còn ≥14 ngày), `toc_do_ban_7d`,
  `cu_ly_km`, `tau_tet` (lịch âm tương đối — Tết trượt 21 ngày/năm), `la_le`,
  `H_horizon`, `sau_15_5`, `q_lag_7` (trễ 7 ngày), `rolling_mean_28`.

**Chống rò rỉ (2 lớp):**
1. Đặc trưng chỉ dùng thông tin biết tại u=14 (vé có lead_time <14 chưa tồn tại).
2. Chia tập theo `ngay_chay` tại điểm gãy chế độ **01/5/2026** (train = LUAT, test =
   AI) — KHÔNG chia theo thời điểm mua (vé Tết bán trước tới 169 ngày ⇒ chia theo
   lúc mua sẽ rò rỉ xuyên horizon).

**Kết quả (2.412.861 grain; test 507.764 dòng, giai đoạn AI):**

| Chỉ số | Model | Baseline pickup×mùa vụ |
|---|---|---|
| MASE (so naive lag-7) | **0.515** | 0.796 |
| Poisson deviance BQ | 0.393 | — |
| Bias tổng | −5.6% | — |

MASE < 1 ⇒ thắng naive; thắng cả heuristic pickup.

### 2.2 Đường cong đặt chỗ F(u) & DemandModel

Để dự báo theo **lead-time bất kỳ** và **cập nhật liên tục**, ta ước lượng đường cong
đặt chỗ empirical:

> **F(u | band, tết) = P(lead_time ≥ u)** = tỉ lệ vé đã bán trước mốc u ngày.

Ước lượng trên tập train (< 01/5) theo (băng cự ly × cửa sổ Tết). Ví dụ F(14):

| Băng | Thường | Tết |
|---|---|---|
| ngắn (<300km) | 0.397 | 0.617 |
| trung (300–900) | 0.739 | 0.868 |
| dài (≥900) | 0.921 | 0.983 |

(Chặng dài & Tết bán sớm hơn nhiều.)

Lớp `DemandModel` gói model + F(u):
- `remaining(row, u) = total × (1 − F(u))` — cầu còn lại từ u đến giờ chạy.
- `update(row, sold, u)`: unconstrain `total_pickup = sold / F(u)` rồi **blend** với
  model (trọng số 0.5) ⇒ cập nhật khi có vé mới, **không cần retrain** (near-real-time).
- `divergence(row, sold, u) = (sold − total·F(u)) / (total·F(u))` — tín hiệu lệch dự
  báo (âm = bán chậm hơn dự báo) cấp cho C2 để nhả ghế đang giữ.

### 2.3 Mô hình co giãn giá (Elasticity)

**Bài toán.** Ước lượng xác suất mua theo mức giá để tối ưu doanh thu.

**Nhận diện.** Trong DGP, quyết định là `WTP < giá_niêm_yết`; cả WTP lẫn giá đều tỉ lệ
với F0 theo tier ⇒ **tier triệt tiêu**, xác suất mua chỉ phụ thuộc `r = giá/F0`:

> **logit P(mua) = β₀ + β_r·ln(r) + β_band + β_tết + β_lead**

**Dữ liệu.** Chỉ từ `search_log` (quan sát được):
- Tử số & giá r: từ transactions (mỗi vé = 1 lần MUA, `r = gia_niem_yet / gia_goc`).
- Mẫu số: `ket_qua = BO_VI_GIA` (bỏ vì giá). Loại `TU_CHOI_HET_CHO` (hết chỗ, không
  phải quyết định giá).
- Ghép theo cell `(chuyến, ga_đi, ga_đến, lead_bin)` — giá gần cố định trong cell (giá
  tất định theo trạng thái) ⇒ gán r cho nhóm BO_VI_GIA cùng cell.
- **KHÔNG dùng `phan_khuc`** (mục đích chuyến = dữ liệu cá nhân) ⇒ giá công bằng.
- Loại các ngày backtest ⇒ không rò rỉ.

**Kết quả:** β_ln(r) = **−1.19** (cầu giảm khi giá tăng). P(mua) = 0.606 (r=1.0) →
0.553 (r=1.2) ⇒ cầu **kém co giãn** trong dải giá quan sát.

**⚠️ Thiên lệch nội sinh (endogeneity).** Trong dữ liệu, giá cao trùng lúc cầu/WTP cao
(phụ thu Tết, đoạn nghẽn). Đặc trưng `is_tet/band/lead` chỉ khử được một phần ⇒ đường
cầu ước lượng *trông kém co giãn hơn thực tế*. Hệ quả: **cấm ngoại suy ra vùng giá cao**
— bộ tối ưu chỉ chạy trong dải hẹp quanh F0 (xem §3.7). Đây là hạn chế cần cải thiện
bằng cách thêm biến trạng thái LF vào ước lượng (xem §6).

---

## 3. Thuật toán (Algorithms)

### 3.1 BT2 — Seat State Matrix (kho trung tâm)

Cấu trúc: mỗi (chuyến, lớp_chỗ) là ma trận `int8` kích thước `(n_ghế, n_đoạn)`, ô ∈
`{0 trống, 1 đã_bán, 2 đang_giữ}`. Hành trình ga i→j chiếm cột `[i, j)` (nửa mở).

- Dựng bằng **replay** giao dịch theo đúng thứ tự mua (lead_time giảm dần), first-fit —
  cùng thuật toán gán chỗ với generator ⇒ tải từng đoạn nhất quán.
- API hợp đồng: `get_state, load_factor, seg_range, assign` (nguyên tử — chồng lấn ⇒
  từ chối, không ghi một phần), `release, first_fit, apply_transaction`.
- Nâng cấp vận hành: `hold_with_expiry` (giữ chỗ có hạn), `expire_holds` (nhả quá hạn
  ⇒ sinh gap cho BT4), `confirm_hold`, `lock_price/locked_price` (sổ giá đã khoá).
- `save/load_snapshot` (`.npz` + `.meta.json`) để Backend nạp nhanh, khỏi replay.

### 3.2 BT3 — Phân tích tải + Phân bổ tồn kho (DLP / cắt chặng)

**Mô hình quy hoạch tuyến tính xác định (DLP), giải riêng từng lớp chỗ:**

> maximize  Σ_k f_k · y_k
> s.t.      A y ≤ c   (sức chứa còn lại mỗi đoạn)
>           0 ≤ y_k ≤ D_k   (cầu dự báo mỗi O-D)

trong đó `A` là ma trận liên thuộc đoạn–hành trình (hành trình phủ các đoạn **liên
tiếp**). Vì `A` **hoàn toàn đơn modular (totally unimodular)** nên nghiệm LP đã nguyên
— không cần MILP; HiGHS giải một chuyến < 10ms.

**Đầu ra:**
- `SegmentLoad[]`: LF từng khu gian + nhãn `nghẽn (LF≥0.85) / trống (LF≤0.35) / bình thường`.
- **Bid price** π_e = đối ngẫu (dual) của ràng buộc sức chứa đoạn e = chi phí cơ hội
  bán 1 chỗ trên đoạn e. Đây là "chi phí biên" cấp cho BT5.
- `QuotaRow[]`: quota theo `(khu_gian, loại_hành_trình{ngắn/trung/dài}, lớp_chỗ)` +
  **booking limit lồng nhau (nested)**: limit chặng ngắn trên đoạn nghẽn = chỗ còn −
  phần bảo vệ cho hành trình dài/trung đi qua đoạn đó.
- `z_opt` (giá trị mục tiêu) = trần doanh thu tham chiếu.

### 3.3 BT4 — Ghép chặng (Segment Merging)

Với mỗi yêu cầu `(chuyến, O, D, lớp_ghế, hồ_sơ_khách)`, sinh danh sách phương án XẾP
HẠNG (thuần đề xuất, không mutate kho):

1. **`xuyen_suot`** — 1 ghế pristine (trống toàn tuyến), không cần đổi.
2. **`gap_khit`** — 1 ghế trống đúng đoạn [O,D) nhưng đã bán chỗ khác; xếp theo **độ
   khít** (biên trống thừa nhỏ nhất trước) ⇒ lấp gap hiệu quả.
3. **`ghep_nhieu`** — ghép ≥2 ghế bằng **phủ khoảng tối thiểu tham lam** (min-interval
   cover: quét trái→phải, mỗi vị trí chọn ghế có dải trống dài nhất). CHỈ xuất hiện khi
   **bất khả kháng** (hết ghế đơn) và thoả:
   - ga đổi có `dwell ≥ 5 phút` (điểm đổi rơi vào ga dừng đủ lâu);
   - cùng lớp chỗ vật lý (`cung_hang_cho`);
   - `can_khach_chap_nhan = True` — Backend phải hiển thị disclosure (số lần đổi, ga
     đổi) và chờ khách chủ động đồng ý;
   - **LOẠI TRỪ** hồ sơ ưu tiên: cao tuổi / khuyết tật / trẻ đi một mình / cần hỗ trợ.

Hàm phụ `list_mergeable_gaps` liệt kê mọi khoảng trống ghép được (một output tối thiểu
của đề bài).

### 3.4 C2 — Nhả & tái phân bổ ghế động

Khi thực tế lệch dự báo (tín hiệu từ `DemandModel.divergence`):
1. `expire_holds(u)` — nhả mọi giữ chỗ quá hạn.
2. Đo divergence từng băng cự ly; `|lệch| ≥ 15%` ⇒ cảnh báo.
3. Cập nhật cầu còn lại (`DemandModel.update`) ⇒ **re-solve DLP** ⇒ so quota cũ/mới ⇒
   đề xuất `MO_THEM` / `SIET_LAI` từng (đoạn, băng, lớp). Thuần đề xuất — chờ duyệt.

### 3.5 C4 — Xếp nhóm (Group seating, CP-SAT)

Mô hình toa/khoang: `ghế // sức_chứa_toa = toa`; trong toa `// sức_chứa_khoang = khoang`.

**CP-SAT** (OR-Tools), biến: `x[s]∈{0,1}` chọn ghế, `uc[toa]`, `uk[khoang]`; ràng buộc
`Σx = n` + implication `x[s]⇒uc[toa(s)], uk[khoang(s)]`; span = ghế_max − ghế_min.

> minimize  10000·Σ uc + 100·Σ uk + span

(trọng số từ vựng: ưu tiên ít toa ≫ ít khoang ≫ dải ghế hẹp). Chạy tất định (1 worker,
seed cố định). Fallback greedy nếu thiếu OR-Tools. Ví dụ: 8 khách NGỒI → 1 toa, ghế
liền 100%.

### 3.6 C5 — Hàng chờ thông minh (Smart waitlist)

Điểm ưu tiên (tất định, không dùng dữ liệu cá nhân để phân biệt giá):

> score = 0.4·(F0/1.5tr) + 0.3·1/(1+u) + 0.2·(bid/150k) + 0.1·(cờ CSXH)

(giá trị doanh thu × độ gấp × khan hiếm đoạn × bảo đảm quyền lợi chính sách xã hội).
Tự khớp khi có ghế nhả (nối C2): duyệt theo score giảm dần, gọi BT4 tìm ghế.

### 3.7 BT5 — Định giá động (Dynamic Pricing)

**Hai chế độ** (`Pricer.load(use_elasticity=)`):

**(a) Elasticity (mặc định) — tối ưu doanh thu:**

> chọn giá p = r·F0 tối đa  **E[đóng góp] = P(mua | r) · (p − c)**

với `c = bid_price_route` (chi phí cơ hội). Tối ưu trên **dải hẹp quanh F0** (tránh
ngoại suy vào vùng thiên lệch nội sinh):
- trần động `ceil_r = 1.0 + 0.15·LF_max` (đoạn càng đầy càng cho tăng);
- sàn động `floor_r = 1.0 − 0.05·(1−LF_max)` (đoạn trống cho giảm nhẹ hút khách);
- Tết: nền giá ≥ (1 + δ_mùa_vụ).

Cơ chế này **phản ánh khan hiếm theo đoạn** (không phải cả tàu): nghẽn → giá cao (bảo
vệ chỗ cho khách giá trị cao); trống → giá gần F0 (hút khách, làm mượt cầu).

**(b) Heuristic (fallback):** F0 → phụ thu theo bid-price floor / LF surcharge.

**F0 (giá gốc):** `F0 = ρ_t · ς_tier · κ₀ · d^θ`, với θ=0.87, κ₀ hiệu chỉnh từ neo
[THẬT] SE1 HN–SG (khớp chính xác cột `gia_goc` của dataset).

**Thứ tự toán tử (bất biến pháp lý & chính sách):**
```
F0 → (elasticity | mùa vụ+động) → cap biến động ±5%/lần → clip sàn/trần [0.55,1.6]·F0
   = GIÁ NIÊM YẾT → giảm CSXH SAU CÙNG (max một mức, không cộng dồn) = GIÁ CUỐI
```
- **Giá đã khoá (held)** ⇒ trả nguyên, bỏ mọi điều chỉnh (honor confirmed price).
- Giá **tất định** theo trạng thái tồn kho + lịch; KHÔNG dùng dữ liệu cá nhân / số lần
  tìm kiếm ⇒ chống phân biệt đối xử.
- Tiền = **int64 đồng** (không float — để audit sàn/trần chính xác).

---

## 4. Bất biến & ràng buộc (có test tự động, 9/9 PASS)

| # | Bất biến | Test |
|---|---|---|
| 1 | Giá tất định — cùng trạng thái ⇒ cùng giá | `test_gia_tat_dinh` |
| 2 | Guardrail: giá niêm yết ∈ [0.55, 1.6]·F0 | `test_guardrail_san_tran` |
| 3 | CSXH áp SAU CÙNG, max không cộng dồn (được phép < sàn) | `test_csxh_ap_sau_cung` |
| 4 | Cap biến động ±5%/lần so giá trước | `test_volatility_cap` |
| 5 | Giá đã khoá bất khả xâm phạm | `test_held_price_bat_kha_xam_pham` |
| 6 | Nhóm ưu tiên không bao giờ nhận phương án ghép | `test_uu_tien_khong_ghep` |
| 7 | Ghép chặng có disclosure + dwell + cùng lớp chỗ | `test_ghep_co_disclosure_va_dwell` |
| 8 | SSM assign nguyên tử (không ghi một phần) | `test_ssm_assign_nguyen_tu` |
| 9 | Hold hết hạn sinh gap | `test_hold_expiry_sinh_gap` |

Ngoài ra: tiền int64; `_ground_truth/` cấm dùng runtime (chỉ eval); không tự áp giá
ngoài guardrail.

---

## 5. Kiểm chứng & kết quả (Backtest Phase 1)

**Phương pháp.** Replay `search_log` theo thứ tự thời gian, chạy song song 2 chính sách:
- **FCFS (baseline):** first-fit ghế đơn, không ghép, giá tĩnh ≈ F0×mùa vụ.
- **AI:** ghép chặng + phân bổ DLP + định giá elasticity + quota gating.

Khách quyết định bằng **WTP thật** từ `_ground_truth/wtp.parquet` (chỉ để chấm điểm).
So thêm với **tối ưu offline** (`offline_optimum.parquet`, z_opt = trần hindsight LP).

**Kết quả (4 tàu SE1/3/5/7 × 2 ngày đại diện):**

| Chỉ số | Tết 14/02 | Ngày thường 20/05 | Target đề bài |
|---|---|---|---|
| Doanh thu AI vs FCFS | **+2.3%** | −0.8% | +3–10% |
| Hiệu suất vs tối ưu offline | **89.0%** (FCFS 87.0%) | 63.6% (FCFS 64.1%) | — |
| Pax-km utilization | 0.807 (FCFS 0.838) | +1.1% | +3–8% |
| Ghế trống cục bộ | −2.7% | **−51.9%** | −20% |
| Số gap ghép thành công | 1.674 | 924 | — |
| % khách phải đổi chỗ | 2.15% | 1.09% | càng thấp càng tốt |
| Tốc độ tính lại p95 | ~8–23ms | ~8–19ms | < 200ms |
| Vi phạm giá/chính sách | 0 | 0 | 0 |

**Nhận định:** Elasticity thắng doanh thu **đúng chỗ cần nhất** (cao điểm Tết, nơi cầu
đông & kém co giãn → tăng giá có kiểm soát); gần trung tính khi thấp điểm nhưng đẩy mạnh
fill/volume. Ghế trống cục bộ giảm sâu nhờ ghép chặng. Tốc độ đạt yêu cầu near-real-time.

---

## 6. Hạn chế đã biết (trung thực khoa học)

1. **Doanh thu chưa vào biên +3–10% ổn định** — mới +2.3% ở peak. Nguyên nhân: FCFS đã
   là baseline mạnh (đạt 87–64% tối ưu offline) và cầu kém co giãn ⇒ dư địa tăng giá hẹp.
2. **Thiên lệch nội sinh của elasticity** (§2.3): cần thêm biến trạng thái LF vào ước
   lượng (hoặc dùng biến công cụ) để tách biến động giá do chính sách khỏi do cầu.
3. **Rủi ro overfit tham số** (markup/markdown, ngưỡng quota) trên 2 ngày backtest —
   cần validate trên nhiều ngày trước khi tin con số.
4. **Replay tái tạo ma trận bằng first-fit** — có thể khác ghế cụ thể ở nhóm vé ghép
   (0,06% vé) nhưng nhất quán về tải từng đoạn.
5. **Choice model rút gọn** (WTP-threshold + recapture xác suất) — chưa phải nested
   logit đầy đủ.

---

## 7. Chuyển sang một PHIÊN BẢN DỮ LIỆU KHÁC

Toàn bộ hệ được tham số hoá theo `generated_data/data/` (dataset) + YAML cấu hình. Có 2
tình huống:

### 7.1 Dữ liệu mới CÙNG lược đồ (schema giống — ví dụ seed khác, thêm tháng, thêm tàu)

Không phải sửa code. Chỉ **chạy lại pipeline artifact theo đúng thứ tự**:

```bash
python models/export_bt5_params.py          # κ₀, θ, ς, ρ_t, sàn/trần, tham số AI  (từ YAML+trains.csv)
python models/train_bt1_forecast.py         # model dự báo + contract
python models/build_bt1_curves.py           # đường cong F(u)
python models/estimate_elasticity.py        # đường cầu P(mua|r)
python models/make_backtest_forecast.py --cutoff <ngày> --dates <ngày backtest>
python eval/backtest.py --dates <...> --trains <...>
python tests/test_invariants.py             # xác nhận bất biến
```

- **Bất biến, không đổi:** contracts, các thuật toán (DLP, ghép chặng, CP-SAT,
  waitlist), thứ tự toán tử giá, bộ test.
- **Tự ước lượng lại theo dữ liệu:** trọng số model BT1, đường cong F(u), hệ số
  elasticity, κ₀ (từ neo giá), quota & bid price.
- **Xác định lại (từ YAML):** κ₀, θ, ς_tier, sàn/trần, tham số AI. Nếu YAML đổi neo giá
  ⇒ κ₀ tự đổi theo.
- **Tất định:** một seed + một YAML ⇒ một dataset ⇒ một bộ artifact (tái lập được).

**Công sức:** ~ vài giờ máy (chủ yếu là train BT1 + estimate elasticity đọc toàn bộ
transactions/search_log). Không cần lập trình.

### 7.2 Dữ liệu mới KHÁC lược đồ (đổi lớp chỗ / ga / cột / đơn vị)

Cần sửa **điểm cấu hình tập trung** (đã gom sẵn để dễ thay), không đụng lõi thuật toán:

| Thay đổi dữ liệu | File cần sửa |
|---|---|
| Lớp chỗ / tier mới | `app/config.py` → `SEAT_CLASSES`, `MACRO_CLASS`, `TIERS`, `CAR_SIZE`, `COMPARTMENT_SIZE` |
| Băng cự ly / ngưỡng LF | `app/config.py` → `BAND_EDGES`, `BOTTLENECK_LF`, `SLACK_LF` |
| Cột dataset đổi tên | các hàm `load()` trong `models/*.py`, `eval/replay.py`, `app/bt2_ssm.py` |
| Ga / lý trình khác | tự đọc từ `stations.csv` — không hard-code |
| Quy tắc giá (mùa vụ, AI) | `models/export_bt5_params.py` (đọc YAML) + `app/bt5_pricing.py` |
| Chính sách CSXH | tham số `muc_giam_csxh` truyền vào `quote()` (đã ngoài lõi) |

**Nguyên tắc:** contracts (`app/contracts.py`) là lớp cách ly — nếu giữ đúng schema
hợp đồng thì Backend và các module khác không phải đổi. Sau khi sửa config, chạy lại
pipeline §7.1 + test.

### 7.3 Cần hiệu chỉnh lại (thận trọng, tránh overfit)

Tham số chính sách (`DEFAULT_POLICY`: `elastic_markup_max`, `elastic_markdown_max`,
`lf_ref`, ngưỡng quota) nên **re-tune trên tập validate riêng, nhiều ngày**, rồi khoá
lại — không tinh chỉnh trực tiếp trên tập test/backtest.

---

## 8. Lộ trình BACKEND

Lớp Model + Thuật toán đã **đóng băng contract** (`app/contracts.py`). Backend KHÔNG
sửa lõi — chỉ gọi hàm, lưu log, bọc phê duyệt/rollback/UI. Chi tiết ở `BACKEND_GUIDE.md`.

### 8.1 Kiến trúc mục tiêu

```
e-ticketing ─► API Gateway (FastAPI) ─► Orchestrator
                    │                        │ gọi qua contracts
       auth/role ───┤                        ├─► BT1 forecast (model .joblib)
       audit DB ────┤                        ├─► BT2 SSM (state + snapshot)
       approval ────┤                        ├─► BT3/BT4/BT5 + C2/C4/C5
       rollback ────┤                        └─► ProposalLog ─► audit DB
       dashboard ───┘
```

### 8.2 Thành phần Backend cần xây

| Hạng mục | Nội dung | Yêu cầu đề bài |
|---|---|---|
| **API tích hợp** | REST nối e-ticketing; adaptor map schema vé ↔ `BookingRequest`/`TXN_SCHEMA` | ✔ |
| **Near-real-time** | mỗi giao dịch → `ssm.apply_transaction`; refresh `analyze_run` theo timer/N-vé; nạp snapshot `.npz` thay replay | chạy near-real-time |
| **Audit DB** | persist mọi `ProposalLog` (+ ai áp dụng, thời điểm) | nhật ký quyết định/phê duyệt |
| **Phân quyền & phê duyệt** | thay đổi quota/giá ngoài dải mặc định phải duyệt (điều độ viên) | role-based approval |
| **Rollback** | version hoá QuotaTable + policy; áp lại bản cũ | rollback |
| **Manual override** | ghi đè giá/quota TRONG guardrail, log lý do | manual override |
| **Drift monitor** | log `DemandModel.divergence` theo (chuyến, băng); cảnh báo khi lệch kéo dài | model-drift monitoring |
| **Dashboard/heatmap** | render `lf_theo_doan` + `fill_matrix_*.csv`; danh sách gap; cảnh báo bottleneck | bản đồ tải + cảnh báo |
| **A/B (Phase 3)** | policy dict theo nhóm thử nghiệm | A/B testing |

### 8.3 Ánh xạ 3 phase pilot của đề

- **Phase 1 — Backtest lịch sử:** ĐÃ XONG (`eval/backtest.py`) — có số liệu AI vs FCFS
  vs tối ưu offline.
- **Phase 2 — AI gợi ý, chưa áp:** bật shadow mode; mọi output là `ProposalLog` chờ
  duyệt; hoàn thiện audit + approval + drift + dashboard.
- **Phase 3 — Triển khai hạn chế + A/B:** near-real-time + adaptor e-ticketing +
  guardrail enforcement trong vòng lặp + khung A/B.

### 8.4 Bất biến Backend KHÔNG được phá
Giá tất định; thứ tự toán tử giá (CSXH cuối); held price bất khả xâm phạm; nhóm ưu tiên
không ghép; ghép phải có khách đồng ý; SSM nguyên tử; tiền int64; `_ground_truth/` cấm
runtime; **không bao giờ tự định giá ngoài dải đã duyệt**.

---

## 9. Phụ lục

### 9.1 Artifact xuất ra (`models/artifacts/`)

| File | Loại | Nội dung |
|---|---|---|
| `bt1_forecast_hgb.joblib` | model ML | HistGradientBoosting Poisson đã fit |
| `bt1_feature_spec.json` | schema | cột + vocab category + metrics |
| `bt1_booking_curves.json` | model | đường cong F(u) theo băng×Tết |
| `elasticity_params.json` | model ML | logistic P(mua\|r) |
| `bt5_pricing_params.json` | config | κ₀, θ, ς, ρ_t, sàn/trần, tham số AI |
| `bt2_snapshot_*.npz/.meta.json` | state | ma trận ghế đã build |
| `bt3_allocation_*.json` | dữ liệu | LF + quota + bid price |
| `backtest_report.json` | báo cáo | AI vs FCFS + tối ưu offline |
| `fill_matrix_*.csv` | heatmap | ma trận LF chuyến × đoạn |

### 9.2 Tham số chính (mặc định)

| Tham số | Giá trị | Nguồn |
|---|---|---|
| θ (số mũ cự ly giá) | 0.87 | YAML |
| Sàn / trần giá | 0.55 / 1.60 × F0 | YAML |
| Cap biến động/lần | ±5% | YAML |
| Elastic markup / markdown | +15% / −5% (× theo LF) | `config.py` |
| Ngưỡng nghẽn / trống | LF ≥ 0.85 / ≤ 0.35 | `config.py` |
| Dwell tối thiểu đổi chỗ | 5 phút | `config.py` |
| Mốc dự báo u | 14 ngày | `config.py` |
| Ngưỡng divergence tái phân bổ | 15% | `reallocation.py` |
| β_ln(r) elasticity | −1.19 | ước lượng |

### 9.3 Lệnh tái lập nhanh
```bash
pip install -r requirements.txt
python models/export_bt5_params.py && python models/train_bt1_forecast.py
python models/build_bt1_curves.py && python models/estimate_elasticity.py
python run_all.py                 # demo 5 bài toán
python eval/backtest.py --dates 2026-02-14,2026-05-20 --trains SE1,SE3,SE5,SE7
python tests/test_invariants.py   # 9/9 PASS
```

---
*Báo cáo này mô tả lớp Model + Thuật toán v1. Xem `README_models.md` (hướng dẫn chạy) và
`BACKEND_GUIDE.md` (tích hợp Backend) để biết chi tiết vận hành.*

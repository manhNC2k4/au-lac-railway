# NOTE_DEV — Khớp nối lớp Model+Thuật toán (`algomodel`) với backend `dev`

Mục đích: liệt kê **những gì đã chỉnh ở phía tôi cho khớp dev** và **những gì dev cần
đổi** (theo owner), để cả team làm trên `dev` không lệch. Tôi **KHÔNG sửa file trong
`backend/`** (tôn trọng file-ownership Master Plan §5.1) — mọi thứ dưới đây là artifact
tham chiếu trong `integration/` + `app/`, dev-owner tự cắm.

Nguyên tắc giữ nguyên: **dataset ≠ runtime** (backend chạy off `seed/`, không import
pandas). Lớp `app/` của tôi là **offline** (hiệu chỉnh seed + bằng chứng backtest),
đúng như `dev/CLAUDE.md` mô tả. Không đề xuất kéo pandas/sklearn vào runtime.

---

## 1. Bản đồ khớp (concept ↔ code)

| Khái niệm | `app/` (tôi, offline) | `backend/` (dev, runtime) | Khớp? |
|---|---|---|---|
| Ma trận ghế | `bt2_ssm.py` int8 {0,1,2} | `state/seat_state_manager.py` FREE/SOLD/HELD | ✅ cùng semantic |
| Segment/seat index | 0-based, span nửa mở `[a,b)` | **1-based, inclusive `[from,to]`, seat_id `C01-S017`** | ⚠️ khác quy ước (xem §3.1) |
| Thứ tự định giá | F0→động→cap→guardrail→CSXH cuối | **y hệt** (`pricing/engine.py`) | ✅ |
| Không dữ liệu cá nhân trong giá | có | `PricingContext`≠`SafetyContext` | ✅ |
| Tiền int64 + round 1k | có | `round_to_1k` | ✅ |
| Bid price | **DLP thật** (LP dual) | công thức scarcity đóng | ⚠️ khác phương pháp (§3.2) |
| Định giá động | **elasticity tối ưu DT** | luật YAML `he_so` | ⚠️ (§3.3) |
| Ghép chặng | same-seat + **ghép nhiều ghế** | **chỉ same-seat** | ⚠️ dev thiếu (§3.4) |
| Forecast | model Poisson + F(u) | pickup-curve/seed `×0.6` | ⚠️ (§3.5) |
| Enum CSXH | (đã sửa) khớp dev | `NGUOI_CAO_TUOI/NGUOI_KHUYET_TAT/TRE_EM/NGUOI_CO_CONG` | ✅ (§2) |

---

## 2. Đã chỉnh Ở PHÍA TÔI cho khớp dev (không cần dev làm gì)

- **`app/contracts.py`**: đổi enum CSXH sang đúng vocabulary dev (`NGUOI_CAO_TUOI/
  NGUOI_KHUYET_TAT/TRE_EM/NGUOI_CO_CONG`) + hằng `CSXH_DEV_MUC_GIAM` (0.15/0.25/0.10/
  0.30, khớp `seed/pricing_policy.json`) + `PassengerProfile.csxh_dev()`. (Trước đây tôi
  dùng tên của generator: `TRE_6_10/HSSV/THUONG_BINH_CDHH/ME_VNAH` — đã bỏ.)
- Xác nhận **thứ tự toán tử giá + guardrail + CSXH-max-last** của tôi trùng khít
  `pricing/engine.py` → không cần đổi gì hai bên.

---

## 3. Việc dev cần đổi (theo owner)

### 3.1 [KHUYẾN NGHỊ · mọi owner] Chốt quy ước index khi trao dữ liệu
Runtime dev là chuẩn (1-based, inclusive, `seat_id`). Artifact offline của tôi khi xuất
cho seed sẽ **theo chuẩn dev**. Không cần đổi code dev; chỉ cần mọi file tôi giao đã
1-based inclusive (đã đảm bảo trong `integration/`).

### 3.2 [TÙY CHỌN · owner BE2 forecast/bid] Nâng bid-price bằng DLP (không bắt buộc)
`forecast/bid_price.py` hiện là xấp xỉ scarcity đóng — **giữ cũng được cho MVP**. Nếu
muốn số bid sát tối ưu hơn, tôi cấp bảng bid-price tiền tính từ DLP (offline) vào seed.
Không đổi runtime, chỉ thay số. → Ưu tiên thấp.

### 3.3 [KHUYẾN NGHỊ · owner BE3 pricing] Calibrate luật giá từ elasticity
File `integration/pricing_rules_elastic.yaml` (đúng schema `rules/pricing_rules.yaml`)
thay 1 luật của dev:
- Bỏ `R_AI_LINH_HOAT` (giảm phẳng −15%): **cầu KÉM co giãn (β_ln r=−1.19)** nên giảm
  sâu là LỖ doanh thu (đã kiểm bằng backtest).
- Thêm bậc thang `R_ELASTIC_NGHEN` (+12% khi LF≥0.85) / `R_ELASTIC_DONG_VUA` (+6%,
  0.70–0.85) / `R_ELASTIC_XA_NHE` (−3% khi AI & LF≤0.40) — xấp xỉ trần động r≈1+0.15·LF.
- **Thay đổi = chỉ file YAML**, engine không đổi. → Ưu tiên trung bình (tăng doanh thu).

### 3.4 [BẮT BUỘC nếu demo cần "đổi chỗ" · owner BE3 merging] Thêm ghép nhiều ghế
Dev đang scope-out (Master §G09/P2) nên **golden chỉ minh hoạ 1 ghế qua 1 gap** — chưa
chứng minh được tính năng lõi *segment-merging with seat change* của đề bài. Tôi cấp
`integration/resolver_multiseat.py` viết **đúng convention `resolver.py`** (numpy, 1-based
inclusive, FREE/SOLD/HELD, tất định), thêm:
- `resolve_multiseat_options(...)` → `MergedSeatPlan` (nhiều leg + `change_station_ids` +
  `so_lan_doi_cho` + `requires_seat_change=True` + `requires_customer_consent=True`);
- cổng dwell ≥5' tại ga đổi; loại trừ `priority_passenger`.

**Dev cần bổ sung để dùng:**
1. `resolver.py`: gọi `resolve_multiseat_options` khi `resolve_same_seat_options` rỗng.
2. **Schema Offer** (`api/schemas.py`): thêm nhánh `seat_plan` nhiều leg + cờ
   `requires_customer_consent`, `change_station_ids`, `so_lan_doi_cho`.
3. **`POST /holds`**: CAS phải giữ **nhiều cell-set (mỗi leg 1 ghế)** trong 1 transaction
   (all-or-nothing) — mở rộng logic hiện tại (đang 1 ghế).
4. **UI**: hiện disclosure (số lần đổi + ga đổi), chỉ tiếp tục khi khách bấm đồng ý.
5. Golden: nếu muốn demo đổi chỗ, thêm 1 scenario phụ (giữ golden 1-ghế cho luồng chính).
→ Ưu tiên: **cao nếu ban giám khảo chấm tính năng ghép nhiều ghế**; nếu demo chỉ cần
gap-1-ghế thì để P2.

### 3.5 [KHUYẾN NGHỊ · owner BE2 seed] Forecast seed model-backed (sửa `×0.6` phẳng)
`build_seed.py::build_forecast` đang đặt `forecast_remaining_demand = remaining_cap×0.6`
cho MỌI đoạn → `pressure=0.6` đồng đều → **bid price như nhau, đoạn nghẽn không đắt hơn**
(mất đúng tín hiệu "khan hiếm theo đoạn"). Tôi cấp `integration/forecast_seed_ref.py`:
`forecast_remaining_demand[s] = max(intensity[s]·N − sold[s], 0)`, với `intensity[s] =
(đã_bán + tìm-kiếm-bị-từ-chối-HẾT_CHO)/sức_chứa` tính offline từ dataset (leg tương đương).
Demo cho thấy seg nghẽn pressure ~4.0 vs seg ế ~0.03 (thay vì 0.6 phẳng). Schema seed
**giữ nguyên**. → Ưu tiên trung bình (làm bid-price/định giá golden có chiều sâu hơn).

### 3.6 [BẮT BUỘC để có bằng chứng · owner BE2 backtest] Điền event stream backtest
`seed/backtest/events-seed-2026071x.jsonl` hiện là **placeholder rỗng**. Đây là chỗ chứng
minh forecast-accuracy + revenue bằng thống kê. Tôi có sẵn:
- kết quả backtest trên dữ liệu thật (AI vs FCFS): **Tết DT +2.3%, hiệu suất 89.0% vs
  FCFS 87.0%; ghế trống cục bộ −52%**, MASE 0.50, β elasticity −1.19.
→ Có thể xuất thành event stream/summary khớp format BE2. → Ưu tiên cao (DoD "backtest ≥5 seeds").

---

## 4. Chốt 1 nguồn forecast (đang có 3)

| Nguồn | MASE | Ghi chú |
|---|---|---|
| `feat` LightGBM | 0.50 | **chống rò rỉ tốt nhất** (lag an toàn ≥15 ngày + embargo + valid set) |
| `app/` sklearn (tôi) | 0.52 | downstream đầy đủ (F(u), DLP, elasticity, backtest) nhưng có lag-leak nhẹ |
| `dev` pickup-curve | — | chỉ để runtime, không phải ML |

**Đề xuất:** lấy **model `feat`** làm *nguồn chính thức* (chính xác ngang, rò rỉ chuẩn hơn),
**bọc bằng downstream của tôi** (F(u)/DLP/elasticity/backtest), `dev` giữ hình dạng
pickup-curve nhưng lấy *số* từ đó qua seed. → 1 model · 1 downstream · 1 seed runtime.

---

## 5. Tóm tắt ưu tiên cho team

| Việc | Owner | Ưu tiên | Đổi gì |
|---|---|---|---|
| Điền backtest event stream + bằng chứng | BE2 | 🔴 cao | seed/backtest/* |
| Ghép nhiều ghế (nếu chấm tính năng) | BE3 | 🔴 cao* | resolver + schema + holds CAS + UI |
| Forecast seed model-backed (bỏ ×0.6) | BE2 | 🟡 vừa | build_seed.build_forecast |
| Pricing rules elasticity | BE3 | 🟡 vừa | rules/pricing_rules.yaml |
| Bid-price DLP tiền tính | BE2 | 🟢 thấp | seed (số) |
| Chốt 1 forecast | cả team | 🔴 cao | quyết định |

\* cao nếu demo phải minh hoạ đổi chỗ; nếu chỉ gap-1-ghế thì hạ xuống P2.

---

## 6. Artifact tôi giao (trong `integration/`, đã test)

- `resolver_multiseat.py` — ghép nhiều ghế, đúng convention resolver dev.
- `pricing_rules_elastic.yaml` — luật giá calibrate từ elasticity, đúng schema rule dev.
- `forecast_seed_ref.py` — build_forecast model-backed, đúng schema seed forecast dev.
- (kèm) `app/` + `models/artifacts/` — model, elasticity, backtest report làm nguồn số.

Mọi thứ trên **không đụng `backend/`**; owner dev cắm theo §3/§5.

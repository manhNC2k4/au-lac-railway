# KẾ HOẠCH TỔNG — Âu Lạc Railway MVP (5 dev / 30 giờ)

**Đọc cùng:** `AuLac_Railway_Final_Plan_Review.md` (hợp đồng đã khóa — file này KHÔNG thay thế nó, chỉ nối nó với dataset thật).
**Phiên bản:** 1.0 · **Ngày:** 17/07/2026 · **Đội hình:** 3 backend + 2 frontend

---

## 0. Điều quan trọng nhất — trả lời câu hỏi "dataset connect thế nào?"

> **Dataset 12 tháng KHÔNG connect vào runtime của app. Không bao giờ.**

Đây là hiểu lầm tốn thời gian nhất có thể xảy ra, nên nói thẳng ở dòng đầu:

| | Dataset `generated_data/` | App MVP |
|---|---|---|
| Phạm vi | 12 tháng, ~24 ga, 14+ mác tàu, 7,6 triệu vé, ~4 GB | **1 chuyến** `SE1_2026-06-15_LE`, 8 ga, 40 ghế |
| Vai trò | Nguồn **hiệu chuẩn offline** + event stream cho backtest | Chạy demo end-to-end |
| Kết nối | **Một script trích xuất, chạy MỘT LẦN, offline** | Đọc `seed/` (~50 KB JSON, commit vào git) |

**Luồng đúng:**

```
generated_data/data/*.parquet  (4 GB, gitignored, KHÔNG có trên máy ai)
        │
        │  BE1 chạy 1 lần, offline, trước T0
        ▼
   seed/  (~50 KB JSON — COMMIT VÀO GIT)
        │
        ├── scenario.json, initial_bookings.jsonl, forecast.json,
        │   fare_products.json, pricing_policy.json,
        │   backtest/events-seed-*.jsonl, expected_checksums.json
        ▼
  PostgreSQL (BE1 nạp qua POST /demo/scenarios/{id}/reset)
        ▼
  API v1  ──►  Frontend
```

**Hệ quả cho từng người — đọc kỹ:**

- **Chỉ BE1 cần dataset 4 GB.** BE2, BE3, FE1, FE2 **không bao giờ** đọc Parquet, không cài DuckDB, không chờ dataset.
- Vì `seed/` được **commit vào git**, cả 5 người code song song từ giờ 0 mà không ai block ai.
- Không có dòng code app nào `import pandas` để phục vụ request. Parquet là công cụ phân tích offline, không phải database.

### 0.1 Tình trạng thực tế của repo (đã kiểm tra 17/07/2026)

Kiểm tra trước khi lập kế hoạch, để không ai mất 2 giờ phát hiện lại:

| Sự thật | Bằng chứng | Ảnh hưởng |
|---|---|---|
| **`generated_data/data/` KHÔNG tồn tại trên máy** | `.gitignore` loại trừ nó; `find` không thấy file parquet nào | README mô tả một run đã chạy ở **máy khác**. Dataset phải **sinh lại** hoặc **copy tay**. → BE1, giờ 0, ưu tiên #1 |
| **`_ground_truth/` cũng không tồn tại** | như trên | Backtest upper bound `z_opt` chưa có |
| **pandas / numpy / pyarrow chưa cài** | `ModuleNotFoundError` | Chưa có `requirements.txt`. → BE1 tạo, giờ 0 |
| **Không có venv, không có pyproject** | `find` không thấy | Onboarding thủ công |
| **Đã có code dùng được** | `demo/ssm/`, `demo/build_forecast_features.py`, `demo/eda_dataset_for_5_subproblems.py` | **Tái sử dụng, đừng viết lại** — xem §4 |

> ⚠️ **Rủi ro #1 của toàn dự án:** không ai biết `generate_data.py` chạy đủ 12 tháng mất bao lâu (ước lượng 30–90 phút, chưa đo). **Fallback đã khóa:** `seed/` **viết tay được** từ spec — 40 ghế × 7 khu gian là dữ liệu bé xíu. Golden path **không bao giờ** phụ thuộc vào việc generator chạy xong. Xem §3.2.

---

## 1. Golden scenario — con số cụ thể để mọi người dùng chung

`service_run_id = SE1_2026-06-15_LE`

**8 ga / 7 khu gian** (lý trình lấy từ `04_THAM_SO_CAU_HINH_MO_PHONG.yaml` §ga — số THẬT, không bịa):

| Leg | Từ | Đến | km đầu | km cuối | Chiều dài |
|---|---|---|---|---|---|
| L1 | HNO Hà Nội | NBI Ninh Bình | 0.0 | 115.0 | 115.0 |
| L2 | NBI | THO Thanh Hóa | 115.0 | 175.0 | 60.0 |
| L3 | THO | VIN Vinh | 175.0 | 319.0 | 144.0 |
| L4 | VIN | DHO Đồng Hới | 319.0 | 522.0 | 203.0 |
| L5 | DHO | HUE Huế | 522.0 | 688.0 | 166.0 |
| L6 | HUE | DNA Đà Nẵng | 688.0 | 791.4 | 103.4 |
| L7 | DNA | SGO Sài Gòn | 791.4 | 1726.0 | 934.6 |

> **Ghi chú trung thực:** SE1 thật dừng **22 ga**; ta gộp còn 8 ga cho demo. L7 dài 934,6 km là hệ quả của việc gộp (đã bỏ Nha Trang, Diêu Trì…). Lý trình từng ga là **thật**, nên giá vé theo `κ·d^θ` vẫn bảo vệ được trước giám khảo. Phải nói rõ điều này trong pitch, đừng để giám khảo tự phát hiện.

**Ghế:** 40 ghế `NGOI_MEM_DH`, `quantity=1`.
> SE1 thật có 448 chỗ (`trains.csv: cap_*`). 40 ghế là **thu nhỏ có chủ đích** để heatmap đọc được trên 1 màn hình. → Vì vậy `seed/` là **dựng từ spec**, không phải "trích 40 ghế đầu" từ dataset (xem §3.1).

**Golden gap:** ghế `C01-S017` — SOLD `HNO→THO` (L1–L2), **FREE `THO→DHO` (L3–L4)**, SOLD `DHO→SGO` (L5–L7).
**Golden request:** `THO→DHO` — baseline từ chối theo quota; Âu Lạc phục vụ **trên cùng một ghế, qua 2 leg**.

**Backtest seeds:** `20260717, 20260718, 20260719, 20260720, 20260721`.

### 1.1 Ba cái bẫy của ngày 2026-06-15

1. **`che_do_gia = AI`** — 15/06/2026 nằm **sau** điểm gãy 01/05/2026. Golden run chạy ở chế độ **AI**, không phải LUAT. Mọi fixture giá phải phản ánh điều đó.
2. **Sau 15/05/2026** → đổi/trả vé online đã bật + biểu đồ chạy tàu mới.
3. **Nằm trong cao điểm hè** (15/05 → 16/08/2026) → luật `R_HE2026_XA_NGAY` có hiệu lực (giảm 5–10% khi `lead_time ≥ 20` ngày, hạn mức **20 vé/loại chỗ/đoàn tàu**).

---

## 2. Bẫy kỹ thuật — đọc trước khi viết dòng code đầu tiên

Những cái này rẻ để vi phạm, đắt để phát hiện muộn.

### 2.1 ⛔ `bid_price` trong `_ground_truth/` là CHẤT ĐỘC

`_ground_truth/offline_optimum.parquet` có cột `bid_price`. **Cấm tuyệt đối** dùng nó ở runtime hoặc làm feature.
MVP **phải tự tính bid price lúc chạy**, theo công thức đã khóa (Plan §3.4):

```
pressure_s  = forecast_remaining_s / max(remaining_capacity_s, 1)
scarcity_s  = clip((pressure_s − p_low) / (p_high − p_low), 0, 1)
bid_s       = round_to_1k(reference_yield_per_km × distance_km_s × scarcity_s)
```

Gọi đúng tên: **"demo bid-price approximation"**. **Không** gọi là EMSR-b (`03` cấm claim này). CI gate: `grep -r "_ground_truth" src/ && exit 1`.
Owner: **BE2**.

### 2.2 Dataset không có HELD / offer / hold

`transactions` chỉ có vé **đã bán**. Không có trạng thái `DANG_GIU`, không có `offer`, không có vòng đời hold — vì generator không mô phỏng chúng.
⇒ Toàn bộ vòng đời **offer → hold → confirm là code MỚI của BE1**, không trích được từ dataset. `seed/initial_bookings.jsonl` chỉ dựng trạng thái **SOLD** ban đầu + đúng 2 hold cạnh tranh (fixture).

### 2.3 Vé ghép nhiều ghế — mất thông tin trong dataset

`transactions` chỉ lưu `cho_so` = **ghế đầu tiên** của vé ghép nhiều ghế (~0,06% vé). `demo/ssm/seat_state_matrix.py` đã ghi rõ và xử lý bằng replay first-fit.
⇒ Đây là **lý do nữa** để dựng `seed/` từ spec chứ không extract chính xác từng ghế. Bất biến giữ được là **tải từng đoạn**, không phải danh tính ghế.

### 2.4 Loại chỗ: dataset 6 tầng, MVP 1 lớp

Dataset: `NGOI_MEM_DH, NAM_K6_T1..T3, NAM_K4_T1..T2`. MVP: chỉ `NGOI_MEM_DH`.
Ánh xạ **đã có sẵn**: `MACRO_CLASS` trong `demo/ssm/ssm_contract.py`. Đừng viết lại.

### 2.5 CSXH áp SAU, dùng `max`, không nhân dồn

Điều 40 NĐ 16/2026: giảm CSXH áp lên **giá bán thực tế** (tức là **sau** giảm động), mỗi vé **≤ 1** ưu đãi, lấy mức **cao nhất** (`max`, **không** `∏`).
Sai thứ tự = **sai doanh thu VÀ sai quyền lợi hành khách**. Ràng buộc **cứng**, 0 vi phạm. Owner: **BE3**.

### 2.6 Giá là `int64` đồng

Không float. Float làm hỏng kiểm toán sàn/trần. `round_to_1k` ở mọi ngã ra.

### 2.7 `PricingContext` không được thấy `PassengerSafetyContext`

Pricing **không** được biết hành khách là người cao tuổi/khuyết tật/trẻ đi một mình. Cấm cả `so_lan_tim_kiem`, `user_id`, `thiet_bi`, `ip`, `lich_su_mua`.
Test bắt buộc (đưa thẳng lên slide): `test_price_invariant_to_search_count`, `test_price_locked_after_hold`, `test_pricing_features_exclude_sensitive`.

### 2.8 Dataset có 2 mô men LỆCH BIÊN — phải công bố, đừng giấu

`README_data.md` ghi rõ, người dùng **chấp nhận có chủ đích**:

| Mô men | Kết quả | Target | Sai số |
|---|---|---|---|
| M8b tỷ số giá Tết/năm | 1,201 | 1,39 | **−13,6%** ❌ |
| M9 hệ số lấp đầy 4/2026 | 0,655 | 0,79 | **−17,1%** ❌ |
| M8 giá BQ Tết | 610.037 đ | 714.000 đ | −14,6% ❌ |

**Không ảnh hưởng golden path** (demo chạy 15/06, không phải Tết). Nhưng **nếu giám khảo hỏi**, câu trả lời phải sẵn: *"M8b bị chặn cấu trúc — sức chứa Tết bind làm cầu chặng dài bị từ chối, mix bán không dịch đủ. Đã ghi trong README, có knob để chỉnh."* **Không sửa dataset trong 30h** — ngoài scope.
Owner câu trả lời: **FE2** (pitch).

---

## 3. Gói `seed/` — hợp đồng dữ liệu chung

### 3.1 Quyết định đã khóa: `seed/` DỰNG TỪ SPEC, không extract từ dataset

Lý do (chọn rung thang thấp nhất còn giữ được):

- 40 ghế ≠ 448 ghế, 8 ga ≠ 22 ga ⇒ mọi "extract" đều là **downsample**, không phải trích trung thực. Downsample sai còn tệ hơn dựng thẳng.
- Golden gap (`C01-S017` FREE đúng THO→DHO) **sẽ không tự nhiên xuất hiện** — phải **dựng có chủ đích** dù có dataset hay không.
- `seed/` = ~50 KB. Viết tay/sinh bằng script 150 dòng, chạy trong 1 giây.

**Dataset dùng để hiệu chuẩn `seed/` cho thật, không phải để copy:** phân bố lead time, tỷ lệ LF theo đoạn, giá vé BQ theo cự ly, tỷ lệ hủy. BE1 lấy các con số này từ `demo/eda_dataset_for_5_subproblems.py` (đã viết sẵn, chạy được), rồi cấp cho BE2 dùng khi thiết kế forecast/bid-price.

⇒ **`seed/` không block trên dataset.** Nếu generator chạy 3 tiếng, cả đội vẫn code bình thường.

### 3.2 Fallback đã khóa

| Nếu | Thì |
|---|---|
| Generator chưa xong lúc giờ 3 | BE1 commit `seed/` với tham số **prior** từ YAML (không cần dataset). Golden path chạy. Hiệu chuẩn lại sau, chỉ đổi **số**, không đổi **schema**. |
| Generator fail hẳn | Giữ nguyên `seed/` prior. Backtest event stream sinh bằng NHPP từ YAML. **Vẫn nộp được.** |
| pandas/pyarrow không cài được | Chỉ ảnh hưởng BE1 (extractor). App không cần chúng. |

### 3.3 Nội dung `seed/` (BE1 sở hữu, freeze giờ 3)

```
seed/
├─ scenario.json              # 8 ga, 7 leg, 40 ghế, service_run, clock, random seed
├─ initial_bookings.jsonl     # booking ban đầu theo timestamp — CHỨA golden gap C01-S017
├─ forecast.json              # forecast_remaining/leg, confidence, forecast_version
├─ fare_products.json         # giá O-D, int64 đồng, versioned
├─ pricing_policy.json        # sàn/trần, max delta, CSXH, policy_version
├─ backtest/events-seed-2026071{7,8,9}.jsonl, -2026072{0,1}.jsonl
└─ expected_checksums.json    # matrix checksum, event checksum, contract shape
```

---

## 4. Tái sử dụng — code đã có, ĐỪNG viết lại

| Đã có | Tái dùng cho | Ai |
|---|---|---|
| `demo/ssm/ssm_contract.py` | `MACRO_CLASS`, hằng `TRONG/DA_BAN/DANG_GIU`, `SeatStateMatrixAPI` Protocol — **hợp đồng SSM đã đóng băng** | BE1 |
| `demo/ssm/seat_state_matrix.py` | Mô hình in-memory ghế×đoạn + `first_fit` + `assign` nguyên tử. **Port sang Postgres**, giữ nguyên semantics | BE1 |
| `demo/build_forecast_features.py` | Feature pickup, `U_FORECAST=14`, split 01/05, MASE. Đã leakage-safe. Chạy trên dataset thô | BE1 (chạy) → cấp số cho BE2 |
| `demo/eda_dataset_for_5_subproblems.py` | Lấy số hiệu chuẩn cho `seed/` (LF/đoạn, gap/chuyến, booking curve) | BE1 |
| `generate_data.py` class `Pricer` (dòng 404) | **Logic giá đã đúng luật** — F0 → δ → clip sàn/trần → CSXH max sau cùng | BE3 |
| `generate_data.py` `solve_dlp_and_bid_price` (dòng 544) | Tham chiếu DLP cho bid-price approximation | BE2 |
| `04_THAM_SO_CAU_HINH_MO_PHONG.yaml` | **Nguồn số duy nhất**: `kappa0`, `theta`, `varsigma`, `rho_t`, `gia_neo`, `diem_gay_che_do` | BE1, BE3 |

> `generate_data.py` `Pricer` đã cài đúng thứ tự CSXH-áp-sau và clip sàn/trần. **BE3 đọc nó trước khi thiết kế PricingEngine.** Chép logic, không chép cấu trúc (nó viết cho batch, MVP cần per-request).

---

## 5. Phân công 5 workstream (3 BE + 2 FE)

| Dev | Vai trò | Sở hữu P0 | File plan |
|---|---|---|---|
| **BE1** | Database / Data Pipeline / Integration Lead | OpenAPI, PostgreSQL, `seed/` + extractor (dataset→hiệu chuẩn→`seed/`→DB, KHÔNG nạp thẳng dataset), `service_run`, SeatStateManager, atomic hold/confirm, expiry, merge owner | `DEV1_BE_STATE_INTEGRATION.md` |
| **BE2** | Forecast / Bid-Price / Backtest | forecast, bid-price approximation, baseline, backtest engine, metrics (đọc `seed/` do BE1 cấp, không đụng dataset thô) | `DEV2_BE_DATA_FORECAST_BACKTEST.md` |
| **BE3** | Decision (Merging + Pricing) | `continuous_same_seat`, `reused_gap`, safety filter, PricingEngine, guardrail, OfferService, DecisionRecord | `DEV3_BE_MERGING_PRICING.md` |
| **FE1** | UI nền tảng + Ops | Design system, typed client, S01 Ops, S02 Seat-Leg Matrix, S05 Decision Detail, S06 Compliance, a11y | `DEV4_FE_OPS_MATRIX.md` |
| **FE2** | UI luồng bán + Pitch | S03 Booking Lab, S04 Backtest Comparison, error states, video, AI log, pitch | `DEV5_FE_BOOKING_BACKTEST.md` |

> **Khác với Plan gốc:** Plan gốc chia D3 (Merging) và D4 (Pricing) riêng, 1 frontend. Yêu cầu là **3 BE + 2 FE** ⇒ gộp Merging+Pricing vào **BE3**, tách frontend thành **FE1 (nền tảng + ops) / FE2 (luồng bán + pitch)**. Ranh giới đọc/ghi giữ nguyên: BE3 phải giữ **PricingContext không thấy SafetyContext** dù cùng một người viết — đây là ràng buộc **kiểm chứng bằng test**, không phải bằng cách chia người.

### 5.1 File ownership — chống dẫm chân

| Đường dẫn | Owner duy nhất |
|---|---|
| `openapi.yaml`, `migrations/`, `src/state/`, `seed/`, `scripts/extract_seed.py` | BE1 |
| `src/forecast/`, `src/backtest/` | BE2 |
| `src/merging/`, `src/pricing/`, `src/offer/`, `rules/*.yaml` | BE3 |
| `web/src/api/`, `web/src/components/`, `web/src/pages/ops/`, `web/src/pages/decision/` | FE1 |
| `web/src/pages/booking/`, `web/src/pages/backtest/`, `pitch/` | FE2 |
| `progress.md` | **ai cũng append, không ai sửa dòng người khác** |

**Luật:** không bao giờ 2 dev sửa cùng 1 file shared trong cùng một block giờ. Đổi contract = proposal có impact list + BE1 duyệt.

### 5.2 Screens S01–S06

Plan gốc nói "S01-S06" nhưng không liệt kê. **Định nghĩa tại đây** (BE1 xác nhận giờ 2):

| ID | Tên | Owner | Nội dung |
|---|---|---|---|
| S01 | Ops Overview | FE1 | LF theo leg, alerts, versions, last_updated |
| S02 | Seat-Leg Matrix | FE1 | Heatmap ghế × leg, FREE/HELD/SOLD, highlight `reused_gap` |
| S03 | Booking Lab | FE2 | Nhập O-D → offer → hold → confirm. **Màn hình ăn tiền của demo** |
| S04 | Backtest Comparison | FE2 | Baseline vs Âu Lạc, 5 seed, median + range |
| S05 | Decision Detail | FE1 | Price breakdown, bid, rule đã bắn, violations, versions |
| S06 | Compliance Panel | FE1 | **"0 vi phạm"** sàn/trần + CSXH — `03` §13 khuyến nghị #9, đề bài chấm |

---

## 6. Timeline 30 giờ

| Giờ | Mục tiêu | Gate / stop-rule |
|---|---|---|
| 0–2 | **Contract freeze**: OpenAPI, enums, errors, `seed/` schema, metric definitions | Chưa freeze ⇒ **không tách nhánh core** |
| 2–6 | Tracer bullet bằng fixture | Giờ 6: fixture `offer→hold→confirm` chạy trong UI |
| 6–10 | Core algorithms + transaction path | Unit/integration tests xanh |
| 10–14 | Integration 1: thay fixture bằng service thật, **theo thứ tự** state → resolver → pricing → allocation → hold/confirm | Giờ 14: real golden path chạy |
| 14–18 | Backtest + UI + safety/governance | **Feature freeze giờ 18** |
| 18–23 | Stabilize: concurrency, p95, a11y, error states | Golden path chưa 3/3 ⇒ **không làm P1** |
| 23–26 | Pitch, evidence, video backup | Giờ 26 có video chạy được |
| 26–28 | Dress rehearsal, fix tối đa 1 blocker | Mọi thay đổi chạy lại smoke |
| 28–30 | Đóng gói + submit | **Cấm refactor, cấm upgrade dependency** |

### 6.1 Giờ 0 — 5 việc chạy song song ngay

| Dev | Việc đầu tiên |
|---|---|
| BE1 | `requirements.txt`, **chạy `generate_data.py` nền**, `openapi.yaml` + enum/error envelope + migration skeleton, `seed/` prior từ YAML |
| BE2 | Đọc draft schema `seed/forecast.json` cùng BE1; dựng khung forecast + công thức bid-price approximation |
| BE3 | Đọc `Pricer` trong `generate_data.py`; khóa `PricingBreakdown` / `SeatPlan` / `SafetyDecision` schema |
| FE1 | Khung route S01–S06 + typed mock client từ `seed/` |
| FE2 | Booking Lab wireframe chạy bằng fixture |

### 6.2 Checkpoint bắt buộc

| Mốc | Bằng chứng | Xác nhận |
|---|---|---|
| Giờ 2 | OpenAPI + `seed/` schema versioned; 0 câu hỏi P0 mở | BE1 + cả đội |
| Giờ 3 | `seed/` commit vào git (dù mới là prior) | BE1 |
| Giờ 6 | Fixture happy path chạy trong UI | BE1 + FE1 |
| Giờ 10 | Core transaction / resolver / pricing / metrics xanh | BE1–BE3 |
| Giờ 14 | Real golden path end-to-end | Cả đội |
| Giờ 18 | P0 feature complete; release candidate | BE1 |
| Giờ 23 | Smoke 3/3; p95 / error / a11y evidence | BE1 + FE1 |
| Giờ 26 | Video backup + pitch | FE2 |
| Giờ 30 | Submission checksum khớp | BE1 + FE2 |

---

## 7. Hợp đồng API v1 (BE1 khóa giờ 2)

| Method | Path | Điểm bắt buộc |
|---|---|---|
| POST | `/api/v1/demo/scenarios/{id}/reset` | Không partial load; trả checksum + versions |
| GET | `/api/v1/demo/state` | Matrix/load/alerts/last_updated; read-only |
| POST | `/api/v1/offers` | Seat plan + price + bid + expiry + versions. **Chưa giữ ghế** |
| POST | `/api/v1/holds` | `Idempotency-Key`; `expected_matrix_version`; **all-or-nothing** |
| POST | `/api/v1/bookings/{hold_id}/confirm` | **Không tính lại giá**; idempotent; 410 nếu expired |
| POST | `/api/v1/backtests` | Cùng event stream, seed set, metric definitions |
| GET | `/api/v1/backtests/{report_id}` | Median, range, raw seed, failed runs |
| GET | `/api/v1/decisions/{decision_id}` | Input versions, price/bid breakdown, violations |

**Enums:** `SeatState: FREE|HELD|SOLD` · `OfferDecision: ACCEPT|REJECT` · `HoldStatus: ACTIVE|CONFIRMED|EXPIRED|CANCELLED`
**Errors:** `NO_SAME_SEAT_OPTION, SOLD_OUT_TRUE, ALLOCATION_REJECTED, STALE_SNAPSHOT, SEAT_CONFLICT, OFFER_EXPIRED, HOLD_EXPIRED, POLICY_UNAVAILABLE`
**HTTP:** 409 stale/conflict · 410 hết hạn · 422 validation · 503 policy/dependency không sẵn sàng
Mọi thao tác ghi có `Idempotency-Key`. JSON UTF-8, timestamp ISO-8601 UTC.

### 7.1 Bất biến trung tâm

> Mọi bước của một offer dùng **cùng** `service_run_id`, `matrix_version`, `forecast_version`, `policy_version`.
> **Frontend không tự ghép** response của Allocation/Merging/Pricing thành quyết định kinh doanh. Backend trả quyết định đã hoàn chỉnh.

---

## 8. Pipeline quyết định (thứ tự bất di bất dịch)

```
1. Load snapshot nhất quán (service_run_id + matrix_version)
2. Ánh xạ O-D → dải leg [origin_seq, destination_seq)
3. Tìm continuous same-seat option        ← BE3
4. Tính base O-D fare                     ← BE3
5. Đề xuất giá từ scarcity                ← BE3
6. Áp hard guardrail (floor/ceiling/max delta/round-1k/freeze)  ← BE3
7. So final offered fare vs Σ bid-price các leg   ← BE2 cấp bid
8. Tạo immutable Offer (có expiry, đủ versions) — CHƯA giữ ghế  ← BE3
9. POST /holds: CAS toàn bộ cells trong MỘT transaction. 1 cell fail ⇒ rollback TẤT CẢ  ← BE1
10. Confirm idempotent HELD→SOLD, dùng NGUYÊN price/seat plan của hold  ← BE1
11. Ghi DecisionRecord (append-only) + trả state mới  ← BE3
```

---

## 9. Definition of Done (toàn đội)

Demo **chỉ** hoàn thành khi **tất cả**:

- [ ] Reset deterministic — cùng seed ⇒ cùng checksum
- [ ] Baseline **từ chối** golden request `THO→DHO`
- [ ] Âu Lạc tìm **đúng** same-seat gap trên `C01-S017`
- [ ] Offer hiển thị price / bid / versions / expiry
- [ ] Hold **nguyên tử** — 2 hold cạnh tranh: 1 thành công, 1 nhận 409, **0 partial hold**
- [ ] Guardrail **clamp thật** (có case vượt ceiling)
- [ ] Backtest **≥5 seed**, báo median + min/max + raw, failed seed không bị giấu
- [ ] Heatmap cập nhật sau confirm
- [ ] Decision truy vết được (versions + rule đã bắn + violations)
- [ ] Smoke test **3/3**, mỗi lần **< 90 giây**
- [ ] **0 vi phạm** sàn/trần + CSXH, hiển thị trên S06
- [ ] Video backup + AI collaboration log sẵn sàng
- [ ] `grep -r "_ground_truth" src/` **rỗng**

**NFR:** offer p95 **< 1s** · resolver **< 200ms** · scenario reset **< 3s**.

---

## 10. Rủi ro

| Rủi ro | Fallback đã khóa | Trigger |
|---|---|---|
| **Dataset không sinh được / quá chậm** | `seed/` prior từ YAML — golden path không phụ thuộc dataset | Giờ 3 chưa có dataset |
| Contract chưa freeze | **Dừng code core**, chốt canonical examples trước | Giờ 2 còn open P0 schema |
| Forecast trễ | Deterministic forecast fixture versioned | Không có output giờ 3 |
| Backtest chậm | Giảm event stream, **giữ đủ 5 seed + metric** | 1 run > 10s |
| PostgreSQL lỗi môi trường | Docker volume sạch + seed reset. **KHÔNG đổi sang SQLite giữa chừng** | Không recover trong 30' |
| UI chờ backend | Giữ fixture adapter, thay service từng module | API thật chưa sẵn giờ 10 |
| P1 chiếm thời gian | **Không làm P1**, giữ static evidence | Golden path chưa 3/3 giờ 18 |
| Live demo lỗi | Video backup + screenshots + checksum | Bất kỳ smoke fail sau giờ 23 |
| Giám khảo hỏi M8b/M9 lệch | Trả lời thẳng theo §2.8 | Chắc chắn hỏi |

---

## 11. ⭐ Quy trình bắt buộc — ghi tiến độ vào `progress.md`

**Mỗi dev, mỗi khi xong một mục P0, PHẢI append một dòng vào `plan/progress.md`.** Không phải cuối ngày — **ngay lúc xong**.

Lý do: 5 người / 30 giờ / không họp được. `progress.md` là **cách duy nhất** biết ai đang chờ ai. Không ghi = coi như chưa xong.

**Định dạng (append, KHÔNG sửa dòng người khác):**

```markdown
| Giờ | Dev | Mục | Trạng thái | Bằng chứng | Unblock ai |
|-----|-----|-----|-----------|-----------|-----------|
| H+03 | BE1 | seed/ prior commit | ✅ DONE | `git show a1b2c3` · 7 file trong seed/ | BE2, BE3, FE1, FE2 |
| H+05 | BE1 | atomic hold CAS | 🚧 WIP | test_two_competing_holds đang đỏ | — |
| H+06 | BE3 | continuous_same_seat | ✅ DONE | `pytest tests/test_merging.py -q` → 8 passed | FE1 (S02) |
| H+07 | BE1 | migration v2 | ⛔ BLOCKED | chờ seed/scenario.json schema | chờ chính mình xong seed/ |
```

**Luật:**
- `✅ DONE` phải có **bằng chứng chạy được**: lệnh test + output, hoặc commit sha. "Xong rồi" không phải bằng chứng.
- `⛔ BLOCKED` phải ghi **chờ ai, chờ cái gì**. Block > 30 phút ⇒ báo BE1 ngay, đừng ngồi chờ.
- Đổi contract ⇒ ghi dòng `⚠️ CONTRACT CHANGE` + impact list + tag các owner liên quan.
- Mỗi checkpoint (giờ 2/6/10/14/18/23/26/30) ⇒ **mọi dev** ghi 1 dòng trạng thái, kể cả khi không có gì mới.

---

## 12. Khởi động (mọi dev, giờ 0)

```bash
git clone <repo> && cd au-lac-railway
git checkout -b <be1|be2|be3|fe1|fe2>/<task>

# Backend
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt                     # BE1 tạo file này giờ 0
docker compose up -d postgres                       # BE1 tạo compose giờ 0

# Frontend
cd web && npm install && npm run dev
```

**Đọc theo thứ tự:** file này → file plan của bạn → `AuLac_Railway_Final_Plan_Review.md` §3 (hợp đồng).
`generated_data/Synthetic_DATA_guide/*.md` **chỉ đọc khi cần tra tham số** — 4 file đó là spec của *dataset*, không phải của *app*.

---

## Phụ lục — bản đồ cột dataset (chỉ BE1 cần)

`data/transactions/thang=YYYY-MM/part.parquet`:
```
ve_id, yeu_cau_id, chuyen_id, mac_tau, ngay_chay, ga_di, ga_den, cu_ly_km,
loai_cho, lead_time_ngay, gia_goc, gia_niem_yet, gia_cuoi, doi_tuong_csxh,
muc_giam_csxh, rule_ids, che_do_gia, so_lan_doi_cho, cho_so, trang_thai
```
`data/search_log/thang=YYYY-MM/part.parquet`:
```
yeu_cau_id, ngay_di, lead_time_ngay, ga_di, ga_den, chuyen_id, phan_khuc, ket_qua, ve_id
```
`ket_qua ∈ {MUA, BO_VI_GIA, TU_CHOI_HET_CHO, TU_CHOI_DOI_CHO, TU_CHOI_GIAN_DOAN, VAO_HANG_CHO}`

Khác: `stations.csv` · `trains.csv` (`cap_*` theo loại chỗ) · `seat_inventory.csv` (`chuyen_id, khu_gian_id, loai_cho, suc_chua, da_ban, he_so_su_dung`) · `calendar_events.csv` (`ngay, tau_tet, dow, la_le, ten_le, dot_ban_ve, H_horizon, che_do_gia`) · `run_summary.csv` (`chuyen_id, mac_tau, ngay_chay, so_ve, doanh_thu, so_gap, suc_chua, lf_bq`) · `refunds.parquet`

**`_ground_truth/`** (`demand_true`, `wtp`, `offline_optimum`) — **chấm điểm only**.

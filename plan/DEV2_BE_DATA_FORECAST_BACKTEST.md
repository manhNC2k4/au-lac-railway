# BE2 — Data / Forecast / Allocation / Backtest

**Đọc trước:** `00_MASTER_PLAN.md` (bắt buộc — §0, §2.1, §3, §4).
**Bạn là người DUY NHẤT chạm vào dataset 4 GB. 4 người còn lại phụ thuộc `seed/` của bạn.**

---

## Bạn sở hữu

| Đường dẫn | Nội dung |
|---|---|
| `seed/` | Gói dữ liệu chung — **cả đội đọc, chỉ bạn ghi** |
| `scripts/extract_seed.py` | Dataset → `seed/` (offline, chạy 1 lần) |
| `requirements.txt` | Bạn tạo, giờ 0 |
| `src/forecast/` | Forecast deterministic + bid-price approximation |
| `src/backtest/` | Backtest engine, baseline, metrics |

---

## ⚠️ Sự thật phũ phàng cần xử lý trong giờ đầu

**Dataset KHÔNG có trên máy.** `.gitignore` loại trừ `generated_data/data/` và `_ground_truth/`; không file parquet nào tồn tại. `README_data.md` mô tả một run đã chạy ở **máy khác**. `pandas`/`numpy`/`pyarrow` cũng chưa cài.

**Nhưng — đừng hoảng.** Master §3.1 đã khóa quyết định: **`seed/` dựng từ spec, KHÔNG extract từ dataset.** Lý do:

- 40 ghế ≠ 448 ghế thật, 8 ga ≠ 22 ga thật ⇒ mọi "extract" đều là downsample, không phải trích trung thực
- Golden gap (`C01-S017` FREE đúng `THO→DHO`) **không tự nhiên xuất hiện** trong dataset — phải dựng có chủ đích **dù có dataset hay không**
- `seed/` chỉ ~50 KB

⇒ **Dataset dùng để HIỆU CHUẨN `seed/` cho thật, không phải để copy.** Nếu generator chạy 3 tiếng, cả đội vẫn code bình thường. Đây là lý do bạn không phải là critical path.

---

## Nhiệm vụ theo giờ

### H0 · Ba việc, theo đúng thứ tự này

- [ ] **1. `requirements.txt`** (5 phút — 4 người đang chờ):
  ```
  fastapi, uvicorn, pydantic, sqlalchemy, psycopg[binary], alembic,
  numpy, pandas, pyarrow, pyyaml, lunardate, scipy, pytest, httpx
  ```
- [ ] **2. Chạy generator NỀN, ngay lập tức** — nó là thứ lâu nhất, khởi động trước rồi làm việc khác:
  ```bash
  cd generated_data && python generate_data.py --skip-lp > gen.log 2>&1 &
  ```
  `--skip-lp` bỏ LP offline optimum (bạn **không được dùng nó** ở runtime — Master §2.1 — nên nó chỉ để tham khảo).
  **Đo và ghi thời gian chạy vào `progress.md`** — chưa ai biết con số này.
- [ ] **3. `seed/` prior từ YAML** — **không chờ generator**. Đây là deliverable H3 của bạn.

### H0–H3 · `seed/` — deliverable quan trọng nhất của bạn

Freeze schema **giờ 2** cùng BE1, commit **giờ 3**.

```
seed/
├─ scenario.json              # 8 ga, 7 leg, 40 ghế, service_run, clock, seed
├─ initial_bookings.jsonl     # ⭐ CHỨA golden gap C01-S017
├─ forecast.json              # forecast_remaining/leg + confidence + forecast_version
├─ fare_products.json         # giá O-D int64 đồng, versioned
├─ pricing_policy.json        # sàn/trần, max delta, CSXH, policy_version   ← cùng BE3
├─ backtest/events-seed-2026071{7,8,9}.jsonl, -2026072{0,1}.jsonl
└─ expected_checksums.json
```

**Golden gap — dựng chính xác thế này:**

```jsonc
// initial_bookings.jsonl
{"seat_id":"C01-S017","from":"HNO","to":"THO","segments":[0,1],   "status":"SOLD"}
{"seat_id":"C01-S017","from":"DHO","to":"SGO","segments":[4,5,6], "status":"SOLD"}
// ⇒ segments [2,3] (THO→VIN→DHO) FREE  = GOLDEN GAP
// ⇒ golden request THO→DHO khớp đúng 2 leg này trên CÙNG một ghế
```

**Fixture bắt buộc** (Plan gốc §4.2 — thiếu cái nào là thiếu evidence):
- [ ] 2 hold cạnh tranh cùng seat/leg → chỉ 1 thành công
- [ ] Offer stale + hold expired với expected error/status
- [ ] Pricing proposal **vượt ceiling** để guardrail clamp thật
- [ ] Protected passenger: nhận same-seat option, **không** nhận option `requires_seat_change`
- [ ] Scenario invalid / booking interval chồng lấn → từ chối **toàn bộ**
- [ ] 5 event stream có checksum — baseline và Âu Lạc dùng **cùng** checksum

**Số hiệu chuẩn lấy từ đâu:** `demo/eda_dataset_for_5_subproblems.py` **đã viết sẵn và chạy được**. Nó in ra LF theo khu gian, gap/chuyến, booking curve theo băng cự ly, giá theo chế độ. Chạy nó khi generator xong, lấy số, cập nhật `seed/` — **chỉ đổi số, không đổi schema**.

> Nếu generator chưa xong lúc H3: commit `seed/` với tham số prior từ `04_THAM_SO_CAU_HINH_MO_PHONG.yaml` (`kappa0`, `theta`, `varsigma`, `rho_t`, `gia_neo`). Golden path chạy được ngay. **Đây là fallback đã khóa, không phải thất bại.**

### H2–H6 · Forecast + bid price

- [ ] Deterministic forecast từ `seed/forecast.json` — versioned (`forecast_version`)
- [ ] **Bid-price approximation** — công thức đã khóa, đừng sáng tạo:
  ```python
  pressure = forecast_remaining_s / max(remaining_capacity_s, 1)
  scarcity = clip((pressure - p_low) / (p_high - p_low), 0, 1)
  bid_s    = round_to_1k(reference_yield_per_km * distance_km_s * scarcity)
  ```
- [ ] Unit test: low-pressure fixture ⇒ bid **thấp hơn** bottleneck; **không NaN, không âm**; `round_to_1k` đúng

> ### ⛔ Bẫy chết người dành riêng cho bạn
>
> `_ground_truth/offline_optimum.parquet` **có sẵn cột `bid_price`**. Nó **CẤM** dùng ở runtime và cấm làm feature.
> `_ground_truth/` là **ĐÁP ÁN**, không phải input. Dùng nó = gian lận = CI đỏ (`grep -r "_ground_truth" src/ && exit 1`).
> Bid price ở MVP **phải tính lúc chạy** từ forecast. Nó có thể trùng `z_opt`? Không, và **không sao cả** — đó là điểm của bài.
>
> Gọi đúng tên: **"demo bid-price approximation"**. **KHÔNG** gọi là EMSR-b (doc `03` cấm claim này — giám khảo sẽ hỏi và bạn không chứng minh được).

### H6–H10 · Backtest engine

- [ ] Replay event stream + metric aggregation
- [ ] **B0 baseline** (FCFS + biểu giá cố định) — **phải TỪ CHỐI golden request `THO→DHO`**. Đây là điều làm demo có ý nghĩa. Nếu baseline cũng phục vụ được, không có gì để chứng minh.
- [ ] Âu Lạc strategy trên **cùng** event stream
- [ ] **Common random numbers** — cùng seed cho cả 2 chính sách. Giảm phương sai 5–10× **miễn phí** (doc `03` §13 #8). Đây là mẹo đánh giá tốt nhất trong mô phỏng và nó tốn 0 dòng code thêm.

**Metric (có đơn vị + mẫu số, không mập mờ):**

| Metric | Công thức | Mẫu số |
|---|---|---|
| False sold-out | # request bị từ chối nhưng **thật ra còn ghế liên tục** | # request |
| Empty seat-km | `Σ_e (C_e − x_e) × ℓ_e` | ghế-km cung ứng |
| Passenger-km | `Σ_e x_e × ℓ_e` | — |
| Revenue | `Σ gia_cuoi` | đồng (int64) |
| Acceptance rate | # ACCEPT / # request | — |

### H10–H14 · Integration

- [ ] BE1 thay adapter allocation/bid của bạn (thứ 4 trong hàng: state → resolver → pricing → **allocation** → hold/confirm)
- [ ] Bid price thật vào offer pipeline (Master §8 bước 7)

### H14–H18 · Evidence — feature freeze H18

- [ ] Backtest **5 seed** + raw-result trace
- [ ] Báo **median + min/max + raw**. **Failed seed KHÔNG được loại im lặng** — báo nó ra. Giấu 1 seed fail là mất uy tín cả bài.
- [ ] Cùng seed/input ⇒ **cùng report checksum**

---

## Test bắt buộc (DoD của bạn)

```python
def test_bid_low_pressure_below_bottleneck()
def test_bid_no_nan_no_negative()
def test_round_to_1k()
def test_baseline_rejects_golden_request()        # ⭐ demo vô nghĩa nếu test này fail
def test_same_event_checksum_both_strategies()
def test_same_seed_same_report_checksum()
def test_failed_seed_reported_not_dropped()
def test_no_ground_truth_import()                 # CI gate
def test_seed_package_matches_expected_checksums()
```

---

## Bẫy dành riêng cho bạn

1. **`_ground_truth/` là đáp án** — xem khung cảnh báo trên. Đây là cách nhanh nhất để mất tư cách.
2. **Đừng cố extract 40 ghế từ 448** — Master §3.1 đã khóa: dựng từ spec.
3. **Vé ghép nhiều ghế chỉ lưu ghế đầu** (~0,06%) — `demo/ssm/seat_state_matrix.py` đã ghi rõ. Bất biến giữ được là **tải từng đoạn**, không phải danh tính ghế.
4. **Chia dữ liệu theo `ngay_chay` + embargo 169 ngày, KHÔNG theo `thoi_diem_mua`, KHÔNG ngẫu nhiên.** Vé Tết bán trước 169 ngày ⇒ chia theo buy-time là rò rỉ qua booking horizon. Doc `03` gọi đây là **cái bẫy tinh vi nhất của toàn bộ spec** và nói 90% nhóm sẽ mắc. `demo/build_forecast_features.py` đã split đúng ở `2026-05-01` — tái dùng.
5. **Biến lịch là ÂM LỊCH tương đối** — dùng `tau_tet`, không dùng month-of-year. Tết trượt 21 ngày giữa 2025 (29/01) và 2026 (17/02) ⇒ "tháng 2" là sau-Tết năm này, trước-Tết năm kia. `q_lag_364` = cùng ngày **âm lịch**.
6. **MASE / pinball / CRPS — KHÔNG MAPE.** Dữ liệu O–D thưa và có nhiều 0; MAPE chia cho 0.
7. **`che_do_gia` là feature bắt buộc.** Train xuyên qua điểm gãy 01/05/2026 mà không có cờ chế độ = học trung bình của **hai** chính sách khác nhau.
8. **Backtest > 10s/run** ⇒ giảm event stream, **giữ đủ 5 seed + metric**. Đừng tối ưu code, cắt dữ liệu.

---

## ⭐ Ghi `progress.md`

```markdown
| H+03 | BE2 | seed/ prior commit | ✅ DONE | `git show <sha>` · 7 file · golden gap verified | BE1,BE3,FE1,FE2 |
| H+01 | BE2 | generate_data.py runtime | ✅ DONE | chạy hết 47 phút — ghi lại cho cả đội | — |
```

- `✅ DONE` **phải** có lệnh test + output hoặc commit sha.
- **Dòng `seed/` commit ở H3 là dòng 4 người đang chờ.** Ghi ngay khi xong.
- Đo được thời gian chạy generator ⇒ ghi vào `progress.md`, cả đội cần biết.
- Checkpoint H2/6/10/14/18/23/26/30: ghi 1 dòng dù không có gì mới.

# BE2 — Forecast / Bid-Price / Backtest

**Đọc trước:** `00_MASTER_PLAN.md` (bắt buộc — §0, §2.1, §4, §8).
**BE1 sở hữu toàn bộ dataset + `seed/`. Bạn KHÔNG chạm dataset 4 GB, KHÔNG chạm `.parquet` — bạn nhận `seed/forecast.json` và event stream đã hiệu chuẩn từ BE1, rồi xây thuật toán forecast/bid/backtest lên trên đó.**

---

## Bạn sở hữu

| Đường dẫn | Nội dung |
|---|---|
| `src/forecast/` | Forecast deterministic + bid-price approximation |
| `src/backtest/` | Backtest engine, baseline, metrics |

**Bạn KHÔNG sở hữu:** `seed/`, `scripts/extract_seed.py`, `requirements.txt`, dataset gốc — tất cả là của **BE1**. Cần đổi số/shape trong `seed/` ⇒ nhờ BE1, đừng tự sửa (đó là file BE1 ghi, cả đội đọc).

---

## Vì sao bạn không phải critical path của dữ liệu

Master §3.1 đã khóa: `seed/` dựng từ spec, hiệu chuẩn bằng dataset — việc đó BE1 làm. Bạn chỉ cần **schema** của `seed/forecast.json` và `seed/backtest/events-*.jsonl` (thống nhất với BE1 giờ 2) để bắt đầu code thuật toán ngay, không cần chờ dataset chạy xong hay số liệu thật. Khi BE1 commit `seed/` (giờ 3, dù là prior hay đã hiệu chuẩn), bạn chỉ việc trỏ vào — **không đổi code**, vì schema không đổi.

---

## Nhiệm vụ theo giờ

### H0–H2 · Thống nhất schema (cùng BE1)

- [ ] Chốt shape `seed/forecast.json`: `forecast_remaining/leg`, `confidence`, `forecast_version`
- [ ] Chốt shape event stream backtest: `backtest/events-seed-*.jsonl`
- [ ] Chốt định nghĩa 5 metric (bảng dưới) — không mập mờ đơn vị/mẫu số

### H2–H6 · Forecast + bid price — code trước khi có số thật

- [ ] Viết `src/forecast/` đọc theo schema đã chốt, dùng dữ liệu giả (bất kỳ số nào khớp schema) để test logic trước
- [ ] **Bid-price approximation** — công thức đã khóa, đừng sáng tạo:
  ```python
  pressure = forecast_remaining_s / max(remaining_capacity_s, 1)
  scarcity = clip((pressure - p_low) / (p_high - p_low), 0, 1)
  bid_s    = round_to_1k(reference_yield_per_km * distance_km_s * scarcity)
  ```
- [ ] Unit test: low-pressure fixture ⇒ bid **thấp hơn** bottleneck; **không NaN, không âm**; `round_to_1k` đúng
- [ ] Khi BE1 commit `seed/` thật (giờ 3) ⇒ trỏ vào, chạy lại test — không sửa logic

> ### ⛔ Bẫy chết người dành riêng cho bạn
>
> `_ground_truth/offline_optimum.parquet` **có sẵn cột `bid_price`**. Nó **CẤM** dùng ở runtime và cấm làm feature — kể cả khi BE1 nhắc tới nó trong log hiệu chuẩn, bạn cũng không được đọc file đó.
> Bid price ở MVP **phải tính lúc chạy** từ forecast. Nó có thể trùng `z_opt`? Không, và **không sao cả** — đó là điểm của bài.
>
> Gọi đúng tên: **"demo bid-price approximation"**. **KHÔNG** gọi là EMSR-b (doc `03` cấm claim này — giám khảo sẽ hỏi và bạn không chứng minh được).

### H6–H10 · Backtest engine

- [ ] Replay event stream (do BE1 cấp trong `seed/backtest/`) + metric aggregation
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
```

---

## Bẫy dành riêng cho bạn

1. **`_ground_truth/` là đáp án** — xem khung cảnh báo trên. Đây là cách nhanh nhất để mất tư cách.
2. **MASE / pinball / CRPS — KHÔNG MAPE.** Dữ liệu O–D thưa và có nhiều 0; MAPE chia cho 0.
3. **`che_do_gia` là feature bắt buộc** khi diễn giải forecast qua điểm gãy 01/05/2026 — nếu forecast của bạn không phân biệt chế độ giá, số sẽ lẫn trung bình của **hai** chính sách khác nhau. (Việc training/feature dùng dataset thô là của BE1 — bạn chỉ cần đảm bảo `forecast.json` có `che_do_gia`/`forecast_version` để dùng đúng.)
4. **Backtest > 10s/run** ⇒ báo BE1 giảm event stream trong `seed/`, **giữ đủ 5 seed + metric**. Đừng tự cắt dữ liệu (không phải file của bạn) và đừng cố tối ưu code để bù dữ liệu quá lớn.
5. **Đừng tự viết script đọc `.parquet`** — nếu thấy mình sắp `import pandas` để đọc `generated_data/data/`, dừng lại, đó là việc của BE1.

---

## ⭐ Ghi `progress.md`

```markdown
| H+06 | BE2 | bid-price approximation | ✅ DONE | `pytest tests/test_bid.py -q` → 5 passed | BE3 (so bid trong offer) |
| H+10 | BE2 | baseline rejects golden request | ✅ DONE | `pytest -k baseline_rejects -q` → 1 passed | FE2 (S04) |
```

- `✅ DONE` **phải** có lệnh test + output hoặc commit sha.
- `⛔ BLOCKED` phải ghi chờ ai/chờ gì (thường là chờ BE1 cấp `seed/`). Block > 30 phút ⇒ báo BE1 ngay.
- Checkpoint H2/6/10/14/18/23/26/30: ghi 1 dòng dù không có gì mới.

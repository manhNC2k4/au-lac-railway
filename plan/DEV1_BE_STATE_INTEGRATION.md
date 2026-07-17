# BE1 — Database / Data Pipeline / Integration Lead

**Đọc trước:** `00_MASTER_PLAN.md` (bắt buộc, đặc biệt §0, §2.1, §2.2, §3, §4, §7, §8).
**Bạn sở hữu toàn bộ tầng dữ liệu — từ dataset thô 4 GB đến API — và là owner merge, người duy nhất được sửa shared contract.**

---

## Bạn sở hữu

| Đường dẫn | Nội dung |
|---|---|
| `openapi.yaml` | Hợp đồng public API v1 — **nguồn duy nhất** |
| `migrations/` | PostgreSQL DDL |
| `src/state/` | `SeatStateManager`, `Clock`, repository |
| `src/api/` | FastAPI routes, error envelope |
| `docker-compose.yml` | Postgres |
| `seed/` | Gói dữ liệu chung — **cả đội đọc, chỉ bạn ghi** |
| `scripts/extract_seed.py` | Dataset → `seed/` → DB (offline, chạy 1 lần) |
| `requirements.txt` | Bạn tạo, giờ 0 |

**Bạn KHÔNG sở hữu:** thuật toán pricing, merging, forecast/backtest (BE2/BE3 tự thiết kế logic — bạn chỉ cấp **dữ liệu** cho họ), frontend. Đừng sửa — gửi proposal cho owner.

## Bạn là single writer + single dataset owner

> `SeatStateManager` là **transaction boundary duy nhất** cho matrix. Mọi module khác **chỉ đọc snapshot** và trả decision/recommendation. Nếu code của BE2/BE3 ghi thẳng vào `seat_segment_state`, đó là bug — reject PR.

> **Bạn cũng là người DUY NHẤT chạm dataset 4 GB và toàn bộ pipeline convert nó vào DB.** BE2, BE3, FE1, FE2 không bao giờ đọc Parquet, không cài DuckDB, không chờ dataset — họ chỉ đọc `seed/` hoặc DB do bạn nạp. Điều này giữ 4 người kia code song song từ giờ 0 mà không ai block ai.

---

## ⚠️ Sự thật phũ phàng cần xử lý trong giờ đầu

**Dataset KHÔNG có trên máy.** `.gitignore` loại trừ `generated_data/data/` và `_ground_truth/`; không file parquet nào tồn tại. `README_data.md` mô tả một run đã chạy ở **máy khác**. `pandas`/`numpy`/`pyarrow` cũng chưa cài.

**Nhưng — đừng hoảng.** Master §3.1 đã khóa quyết định: **`seed/` dựng từ spec, KHÔNG extract từ dataset.** Lý do:

- 40 ghế ≠ 448 ghế thật, 8 ga ≠ 22 ga thật ⇒ mọi "extract" đều là downsample, không phải trích trung thực
- Golden gap (`C01-S017` FREE đúng `THO→DHO`) **không tự nhiên xuất hiện** trong dataset — phải dựng có chủ đích **dù có dataset hay không**
- `seed/` chỉ ~50 KB, viết tay/script 150 dòng, chạy 1 giây

⇒ **Dataset dùng để HIỆU CHUẨN `seed/` cho thật (số), không phải để copy (schema).** Nếu generator chạy 3 tiếng, bạn vẫn commit `seed/` prior đúng giờ hạn — generator chỉ làm số chính xác hơn sau đó.

---

## Nhiệm vụ theo giờ

### H0 · Bốn việc, theo đúng thứ tự này — cả đội đang chờ

- [ ] **1. `requirements.txt`** (5 phút):
  ```
  fastapi, uvicorn, pydantic, sqlalchemy, psycopg[binary], alembic,
  numpy, pandas, pyarrow, pyyaml, lunardate, scipy, pytest, httpx
  ```
- [ ] **2. Chạy generator NỀN, ngay lập tức** — nó là thứ lâu nhất, khởi động trước rồi làm việc khác:
  ```bash
  cd generated_data && python generate_data.py --skip-lp > gen.log 2>&1 &
  ```
  `--skip-lp` bỏ LP offline optimum (Master §2.1 — cấm dùng ở runtime nên chỉ để tham khảo).
  **Đo và ghi thời gian chạy vào `progress.md`** — chưa ai biết con số này.
- [ ] **3. `openapi.yaml` + enum/error envelope + migration skeleton + `docker-compose.yml`** — xem H0–H2 dưới
- [ ] **4. `seed/` prior từ YAML** — **không chờ generator**. Deliverable H3 của bạn.

### H0–H2 · Contract freeze — cả đội chờ bạn

**2 giờ quan trọng nhất của 30 giờ.** 4 người khác không code core được cho tới khi bạn freeze.

- [ ] `openapi.yaml` — 8 endpoint ở Master §7, **có canonical example cho mỗi request/response**
- [ ] Enums: `SeatState`, `OfferDecision`, `HoldStatus` (Master §7)
- [ ] Error envelope + 8 reason code + mapping HTTP 409/410/422/503
- [ ] `docker-compose.yml` (postgres:16, volume sạch, healthcheck)
- [ ] Migration skeleton
- [ ] Interface `Clock` + `SeatStateManager` (Protocol) — **tái dùng `demo/ssm/ssm_contract.py`**
- [ ] `seed/scenario.json` schema (shape, không cần số thật) — BE2 cần shape này để dựng forecast module song song, FE1 cần để sinh mock client
- [ ] `PricingBreakdown`/`SeatPlan`/`SafetyDecision` schema — thống nhất cùng BE3
- [ ] Xác nhận danh sách S01–S06 với FE1/FE2 (Master §5.2)

> **Stop-rule:** hết giờ 2 mà còn câu hỏi P0 về schema ⇒ **cả đội dừng code core**, chốt canonical example trước. Đây là luật, không phải gợi ý.

**Ghi `progress.md` ngay khi freeze — 4 người đang chờ dòng đó.**

### H0–H3 · `seed/` — deliverable dữ liệu quan trọng nhất

Freeze schema **giờ 2** (cùng lúc với contract), commit **giờ 3**.

```
seed/
├─ scenario.json              # 8 ga, 7 leg, 40 ghế, service_run, clock, seed
├─ initial_bookings.jsonl     # ⭐ CHỨA golden gap C01-S017
├─ forecast.json              # forecast_remaining/leg + confidence + forecast_version (shape cùng BE2 định)
├─ fare_products.json         # giá O-D int64 đồng, versioned
├─ pricing_policy.json        # sàn/trần, max delta, CSXH, policy_version   ← shape cùng BE3
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

**Fixture bắt buộc** (thiếu cái nào là thiếu evidence cho cả đội):
- [ ] 2 hold cạnh tranh cùng seat/leg → chỉ 1 thành công
- [ ] Offer stale + hold expired với expected error/status
- [ ] Pricing proposal **vượt ceiling** để guardrail clamp thật (BE3 cần)
- [ ] Protected passenger: nhận same-seat option, **không** nhận option `requires_seat_change`
- [ ] Scenario invalid / booking interval chồng lấn → từ chối **toàn bộ**
- [ ] 5 event stream có checksum — baseline và Âu Lạc dùng **cùng** checksum

**Số hiệu chuẩn lấy từ đâu:** `demo/eda_dataset_for_5_subproblems.py` **đã viết sẵn và chạy được**. Chạy nó khi generator xong, lấy số (LF/đoạn, gap/chuyến, booking curve, giá theo chế độ), cập nhật `seed/` — **chỉ đổi số, không đổi schema**. Đồng thời chạy `demo/build_forecast_features.py` (feature pickup, split 01/05, MASE — đã leakage-safe) để lấy tham số đưa vào `seed/forecast.json`, rồi bàn giao cho BE2.

> Nếu generator chưa xong lúc H3: commit `seed/` với tham số prior từ `04_THAM_SO_CAU_HINH_MO_PHONG.yaml` (`kappa0`, `theta`, `varsigma`, `rho_t`, `gia_neo`). Golden path chạy được ngay. **Đây là fallback đã khóa, không phải thất bại.**

### H2–H6 · Tracer bullet

- [ ] `service_run` table + row `SE1_2026-06-15_LE`
- [ ] `POST /demo/scenarios/{id}/reset` — nạp `seed/scenario.json` + `initial_bookings.jsonl`, **không partial load**, trả checksum + versions
- [ ] `seat_segment_state` repository + `matrix_version`
- [ ] `GET /demo/state` (read-only)
- [ ] `POST /offers`, `POST /holds` **stub** trả fixture — để FE1/FE2 nối được ngay
- [ ] Giờ 6: fixture `offer→hold→confirm` chạy trong UI (cùng FE1)

### H6–H10 · Core transaction — phần khó nhất của bạn

- [ ] **Atomic multi-cell CAS**: `POST /holds` giữ **toàn bộ** leg trong **một** transaction. 1 cell fail ⇒ **rollback tất cả**. Không bao giờ partial.
- [ ] `expected_matrix_version` mismatch ⇒ **409 `STALE_SNAPSHOT`**
- [ ] Cell đã bị chiếm ⇒ **409 `SEAT_CONFLICT`**
- [ ] Idempotency: cùng `Idempotency-Key` ⇒ **cùng kết quả**, không tạo hold thứ 2
- [ ] `confirm`: HELD→SOLD, **không tính lại giá**, dùng nguyên price/seat plan của hold, idempotent, **410 `HOLD_EXPIRED`** nếu hết hạn
- [ ] `expire_due_holds(now)` chạy **trước mọi state read/write** và qua demo tick

**Cách làm (rung thang thấp nhất còn đúng):**

```sql
-- Postgres lo atomicity. Đừng tự viết lock manager.
BEGIN;
  SELECT version FROM seat_segment_state
   WHERE service_run_id=$1 AND seat_id=$2 AND segment_id = ANY($3)
   FOR UPDATE;                       -- khóa toàn bộ cells cùng lúc
  -- kiểm tra: mọi cell FREE + version khớp; sai bất kỳ ⇒ ROLLBACK
  UPDATE seat_segment_state SET status='HELD', hold_id=$4, ... ;
COMMIT;
```

> `SELECT ... FOR UPDATE` trên toàn bộ cells + `UNIQUE(service_run_id, seat_id, segment_id)` là đủ cho MVP. **Không** Redis, **không** distributed lock, **không** optimistic retry loop. Order các `segment_id` **tăng dần** trong mọi transaction để tránh deadlock — 1 dòng `sorted()`, rẻ.

> **Clock abstraction, không `datetime.now()` rải rác.** Demo cần tick thời gian để chứng minh expiry. Inject `Clock` một chỗ.

### H10–H14 · Integration 1 — bạn điều phối

Thay adapter **đúng thứ tự này**, mỗi lần **một** cái, chạy contract test + golden E2E **trước khi** thay cái kế tiếp:

```
state → resolver (BE3) → pricing (BE3) → allocation/bid (BE2) → hold/confirm
```

- [ ] Bạn giải quyết contract conflict. **Owner module sửa implementation — cấm frontend workaround.**
- [ ] **Gate giờ 14:** real API tạo offer → hold **2 leg nguyên tử** (L3+L4) → confirm → heatmap cập nhật

### H14–H18 · Release candidate

- [ ] Nối hết module thật
- [ ] **Khóa release candidate giờ 18.** Sau đó chỉ nhận bugfix **có reproduction + regression test**.

### H18–H30

- [ ] H18–23: concurrency, idempotency, expiry, deterministic replay, p95
- [ ] H23: smoke 3/3 (cùng FE1)
- [ ] H28–30: checksum artifacts, đóng gói, submit (cùng FE2). **Cấm refactor, cấm upgrade dependency.**

---

## Data model tối thiểu

| Entity | Trường bắt buộc | Quy tắc |
|---|---|---|
| `service_run` | `service_run_id, train_id, service_date, direction, status` | Khóa chuyến thực |
| `seat_segment_state` | `service_run_id, seat_id, segment_id, status, hold_id, hold_expires_at, version` | **`UNIQUE(service_run_id, seat_id, segment_id)`** |
| `seat_hold` | `hold_id, offer_id, status, expires_at, idempotency_key` | Giá + seat plan **khóa suốt hold** |
| `booking` | `hold_id, status, created/confirmed/cancelled_at` | `quantity=1`; confirm **không tính lại** |

Index theo `service_run_id`. Tiền = `BIGINT` đồng.

---

## Test bắt buộc (DoD của bạn)

```python
# State / transaction
def test_two_competing_holds_one_wins()        # 1 thành công, 1 → 409, 0 partial
def test_no_partial_hold_on_conflict()         # rollback toàn bộ khi 1 cell fail
def test_same_idempotency_key_same_result()
def test_confirm_after_expiry_returns_410()
def test_expiry_releases_all_legs()            # đủ MỌI leg, không sót
def test_price_and_seat_plan_unchanged_offer_to_confirm()
def test_invalid_scenario_reset_does_not_mutate_state()
def test_reset_deterministic_same_checksum()
def test_stale_matrix_version_returns_409()

# Seed / dataset pipeline
def test_seed_package_matches_expected_checksums()
def test_no_ground_truth_import()               # CI gate: grep -r "_ground_truth" src/
```

**`test_two_competing_holds_one_wins` là test quan trọng nhất trong toàn bộ MVP.** Nó chứng minh G04. Viết nó **trước** khi viết CAS.

---

## Bẫy dành riêng cho bạn

1. **Dataset không có HELD/offer/hold** (Master §2.2) — vòng đời này là **code mới của bạn**, không trích được từ đâu. Đừng đi tìm.
2. **`seed/` dựng từ spec, không extract downsample** (Master §3.1) — 40 ghế ≠ 448 ghế thật, extract = downsample sai. Golden gap phải dựng có chủ đích.
3. **Đừng cố extract 40 ghế từ 448** hay 8 ga từ 22 ga — luôn dựng từ spec, chỉ hiệu chuẩn **số** bằng dataset.
4. **Vé ghép nhiều ghế chỉ lưu ghế đầu trong dataset** (~0,06%) — `demo/ssm/seat_state_matrix.py` đã ghi rõ. Bất biến giữ được là **tải từng đoạn**, không phải danh tính ghế.
5. **`_ground_truth/offline_optimum.parquet` có cột `bid_price` — CẤM TUYỆT ĐỐI** dùng ở runtime hay làm feature, kể cả khi bạn là người chạm dataset gần nó nhất. `_ground_truth/` là **đáp án chấm điểm**, không phải input.
6. **`demo/ssm/seat_state_matrix.py` đã có semantics đúng** (`assign` nguyên tử: có xung đột ⇒ không ghi gì). Port sang Postgres, giữ nguyên ý nghĩa. Đừng thiết kế lại từ đầu.
7. **Không JWT production, không Redis, không worker phân tán** trong P0. Nếu thấy mình đang cài chúng — dừng lại.
8. **`SELECT FOR UPDATE` phải order segment_id tăng dần** — thiếu là deadlock lúc demo, đúng lúc đông người xem nhất.
9. **Chia dữ liệu theo `ngay_chay` + embargo 169 ngày khi chạy `build_forecast_features.py`, KHÔNG theo `thoi_diem_mua`** — vé Tết bán trước 169 ngày, chia theo buy-time là rò rỉ qua booking horizon. `demo/build_forecast_features.py` đã split đúng ở `2026-05-01` — tái dùng, đừng tự chia lại.
10. **Backtest event stream > 10s/run ở BE2** ⇒ nếu do bạn cấp quá nhiều dữ liệu, giảm event stream nhưng **giữ đủ 5 seed + metric**. Đừng bắt BE2 tối ưu code của họ để bù dữ liệu thô của bạn.

---

## ⭐ Ghi `progress.md`

Xong mục nào → **append ngay** vào `plan/progress.md` (đừng để cuối ngày):

```markdown
| H+02 | BE1 | contract freeze v1.0 | ✅ DONE | `git show <sha>` · openapi.yaml 8 endpoints + examples | BE2,BE3,FE1,FE2 |
| H+03 | BE1 | seed/ prior commit | ✅ DONE | `git show <sha>` · 7 file · golden gap verified | BE2,BE3,FE1,FE2 |
```

- `✅ DONE` **phải** có lệnh test + output hoặc commit sha.
- **Dòng `seed/` commit ở H3 là dòng 4 người đang chờ.** Ghi ngay khi xong.
- Đo được thời gian chạy generator ⇒ ghi vào `progress.md`, cả đội cần biết.
- Bạn là merge owner ⇒ **mọi `⚠️ CONTRACT CHANGE` phải có chữ ký của bạn.**
- Checkpoint H2/6/10/14/18/23/26/30: ghi 1 dòng dù không có gì mới.

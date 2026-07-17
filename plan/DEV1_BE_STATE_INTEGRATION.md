# BE1 — Integration / State Lead

**Đọc trước:** `00_MASTER_PLAN.md` (bắt buộc, đặc biệt §0, §2.2, §7, §8).
**Bạn là owner merge và là người duy nhất được sửa shared contract.**

---

## Bạn sở hữu

| Đường dẫn | Nội dung |
|---|---|
| `openapi.yaml` | Hợp đồng public API v1 — **nguồn duy nhất** |
| `migrations/` | PostgreSQL DDL |
| `src/state/` | `SeatStateManager`, `Clock`, repository |
| `src/api/` | FastAPI routes, error envelope |
| `docker-compose.yml` | Postgres |

**Bạn KHÔNG sở hữu:** pricing, merging, forecast, `seed/`, frontend. Đừng sửa — gửi proposal cho owner.

## Bạn là single writer

> `SeatStateManager` là **transaction boundary duy nhất** cho matrix. Mọi module khác **chỉ đọc snapshot** và trả decision/recommendation. Nếu code của BE2/BE3 ghi thẳng vào `seat_segment_state`, đó là bug — reject PR.

---

## Nhiệm vụ theo giờ

### H0–H2 · Contract freeze — cả đội chờ bạn

**Đây là 2 giờ quan trọng nhất của 30 giờ.** 4 người khác không code core được cho tới khi bạn freeze.

- [ ] `openapi.yaml` — 8 endpoint ở Master §7, **có canonical example cho mỗi request/response**
- [ ] Enums: `SeatState`, `OfferDecision`, `HoldStatus` (Master §7)
- [ ] Error envelope + 8 reason code + mapping HTTP 409/410/422/503
- [ ] `docker-compose.yml` (postgres:16, volume sạch, healthcheck)
- [ ] Migration skeleton
- [ ] Interface `Clock` + `SeatStateManager` (Protocol) — **tái dùng `demo/ssm/ssm_contract.py`**
- [ ] Xác nhận danh sách S01–S06 với FE1/FE2 (Master §5.2)

> **Stop-rule:** hết giờ 2 mà còn câu hỏi P0 về schema ⇒ **cả đội dừng code core**, chốt canonical example trước. Đây là luật, không phải gợi ý.

**Ghi `progress.md` ngay khi freeze — 4 người đang chờ dòng đó.**

### H2–H6 · Tracer bullet

- [ ] `service_run` table + row `SE1_2026-06-15_LE`
- [ ] `POST /demo/scenarios/{id}/reset` — nạp `seed/scenario.json` + `initial_bookings.jsonl`, **không partial load**, trả checksum + versions
- [ ] `seat_segment_state` repository + `matrix_version`
- [ ] `GET /demo/state` (read-only)
- [ ] `POST /offers`, `POST /holds` **stub** trả fixture — để FE1/FE2 nối được ngay
- [ ] Giờ 6: fixture `offer→hold→confirm` chạy trong UI (cùng FE1)

> Nếu `seed/` của BE2 chưa có lúc H2, dùng `scenario.json` tạm bạn tự viết **theo đúng schema đã freeze**. Đừng chờ. Số sẽ đổi, schema thì không.

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
def test_two_competing_holds_one_wins()        # 1 thành công, 1 → 409, 0 partial
def test_no_partial_hold_on_conflict()         # rollback toàn bộ khi 1 cell fail
def test_same_idempotency_key_same_result()
def test_confirm_after_expiry_returns_410()
def test_expiry_releases_all_legs()            # đủ MỌI leg, không sót
def test_price_and_seat_plan_unchanged_offer_to_confirm()
def test_invalid_scenario_reset_does_not_mutate_state()
def test_reset_deterministic_same_checksum()
def test_stale_matrix_version_returns_409()
```

**`test_two_competing_holds_one_wins` là test quan trọng nhất trong toàn bộ MVP.** Nó chứng minh G04. Viết nó **trước** khi viết CAS.

---

## Bẫy dành riêng cho bạn

1. **Dataset không có HELD/offer/hold** (Master §2.2) — vòng đời này là **code mới của bạn**, không trích được từ đâu. Đừng đi tìm.
2. **Đừng chờ `seed/`** — schema freeze trước, số điền sau.
3. **`demo/ssm/seat_state_matrix.py` đã có semantics đúng** (`assign` nguyên tử: có xung đột ⇒ không ghi gì). Port sang Postgres, giữ nguyên ý nghĩa. Đừng thiết kế lại từ đầu.
4. **Không JWT production, không Redis, không worker phân tán** trong P0. Nếu thấy mình đang cài chúng — dừng lại.
5. **`SELECT FOR UPDATE` phải order segment_id tăng dần** — thiếu là deadlock lúc demo, đúng lúc đông người xem nhất.

---

## ⭐ Ghi `progress.md`

Xong mục nào → **append ngay** vào `plan/progress.md` (đừng để cuối ngày):

```markdown
| H+02 | BE1 | contract freeze v1.0 | ✅ DONE | `git show <sha>` · openapi.yaml 8 endpoints + examples | BE2,BE3,FE1,FE2 |
```

- `✅ DONE` **phải** có lệnh test + output hoặc commit sha.
- `⛔ BLOCKED` phải ghi chờ ai/chờ gì. Block > 30' ⇒ báo ngay.
- Bạn là merge owner ⇒ **mọi `⚠️ CONTRACT CHANGE` phải có chữ ký của bạn.**
- Checkpoint H2/6/10/14/18/23/26/30: ghi 1 dòng dù không có gì mới.

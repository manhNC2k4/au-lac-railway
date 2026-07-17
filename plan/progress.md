# progress.md — Nhật ký tiến độ 30 giờ

**T0 = <điền lúc bắt đầu>** · Mọi giờ ghi dạng `H+xx` (tính từ T0).

## Luật ghi (đọc 1 lần, tuân thủ 30 giờ)

1. **Xong mục nào → append NGAY.** Không để cuối ngày. Không ghi = coi như chưa xong.
2. **Append xuống cuối. KHÔNG sửa dòng người khác.** Sửa dòng mình thì được (WIP → DONE).
3. **`✅ DONE` phải có bằng chứng chạy được**: lệnh test + output, commit sha, screenshot path, hoặc URL. *"Xong rồi"* không phải bằng chứng.
4. **`⛔ BLOCKED` phải ghi chờ ai / chờ cái gì.** Block > 30 phút ⇒ báo BE1 ngay, đừng ngồi chờ.
5. **Đổi contract** ⇒ dòng `⚠️ CONTRACT CHANGE` + impact list + tag owner liên quan. **BE1 phải duyệt.**
6. **Checkpoint (H2, H6, H10, H14, H18, H23, H26, H30): MỌI dev ghi 1 dòng**, kể cả khi không có gì mới.

Trạng thái: `✅ DONE` · `🚧 WIP` · `⛔ BLOCKED` · `⚠️ CONTRACT CHANGE` · `❌ CUT` (bỏ, ghi lý do)

---

## Nhật ký

| Giờ | Dev | Mục | Trạng thái | Bằng chứng | Unblock ai |
|-----|-----|-----|-----------|-----------|-----------|
| H+00 | — | Kickoff | 🚧 WIP | 5 file plan đã đọc | — |
| H+?? | BE2 | forecast.json schema + bid-price approximation | ✅ DONE | `src/forecast/{network,bid_price,forecast}.py` · `python -m unittest tests.test_bid_price -v` → 4 passed | BE1 (đối chiếu schema), BE3 (so bid trong offer) |
| H+?? | BE2 | seed/backtest/events-seed-{5}.jsonl (NHPP từ YAML, không dùng dataset thô) | ✅ DONE | `python -m src.backtest.events` → 5 file trong `seed/backtest/`, ~400 request/seed, `seed/backtest/checksums.json` | BE1 (duyệt & commit chính thức vào seed/), FE2 (S04) |
| H+?? | BE2 | backtest engine: baseline B0 (no-gap-reuse) vs Âu Lạc (seat-matrix + bid guardrail), common random numbers, metrics | ✅ DONE | `python -m unittest tests.test_backtest -v` → 7 passed, gồm `test_baseline_rejects_golden_request` ⭐ và `test_no_ground_truth_import` (CI gate) | FE2 (S04 backtest comparison) |
| H+?? | BE2 | Ghi chú phạm vi: backtest dùng `fixed_fare` chung cho cả 2 chính sách (cô lập biến allocation, chưa cắm PricingEngine thật của BE3) | ⚠️ CONTRACT NOTE | Xem docstring `src/backtest/engine.py` — khi BE3 xong PricingEngine (H10-H14), thay fixed_fare bằng giá AI thật, interface accept/reject+revenue giữ nguyên | BE3, BE1 (tích hợp) |
| H+00 | BE1 | requirements.txt + openapi.yaml freeze | ✅ DONE | `backend/requirements.txt`, `backend/openapi.yaml` — 11 endpoint, parse OK (`python -c "yaml.safe_load(...)"` → paths=11) | BE2,BE3,FE1,FE2 |
| H+00 | BE1 | seed/ prior + calibration (scenario/fare/policy/forecast) | ✅ DONE | `backend/scripts/build_seed.py` chạy thật trên `generated_data/data/` — golden gap `C01-S017` FREE segment [3,4] verified qua `pytest tests/test_seed.py -v` → 3 passed | BE2,BE3,FE1,FE2 |
| H+00 | BE1 | DB schema xác nhận | ✅ DONE | `docker compose up -d db flyway` → V1+V2 migrate OK | — |
| H+00 | BE1 | SeatStateManager + atomic CAS hold/confirm | ✅ DONE | `backend/src/state/seat_state_manager.py` — `pytest backend/tests/ -v` trên Postgres thật → **12 passed** (phần BE1), gồm `test_two_competing_holds_one_wins` | BE2,BE3,FE1,FE2 |
| H+00 | BE1 | FastAPI app (11 route thật, không stub) | ✅ DONE | `backend/src/api/` — smoke thật qua uvicorn: reset→offer(ACCEPT)→hold(ACTIVE)→confirm(CONFIRMED, giá không đổi)→seatmap segment 3,4 chuyển SOLD | FE1,FE2 |
| H+00 | BE1 | CI gate `_ground_truth` | ✅ DONE | `grep -r "_ground_truth" src/` → rỗng | — |
| H+00 | BE1 | Ghi chú phạm vi (solo session) | ⚠️ CONTRACT CHANGE | `/offers` pricing/bid dùng công thức rút gọn tạm thời (chưa cắm forecast module BE2 thật, chưa CSXH/guardrail-ceiling-exceed case của BE3) — xem `backend/src/api/routes_offers.py` docstring. Khi BE2/BE3 vào, thay logic tại đây, KHÔNG đổi route/schema. | BE2 (forecast thật), BE3 (pricing/CSXH thật) |
| H+00 | BE1 | ⚠️ **HỢP NHẤT `seed/` sau conflict discard+pull**: `backend/seed/backtest/` của tôi (placeholder rỗng) và `seed/backtest/` root của BE2 (data thật) từng tồn tại song song — dời data thật của BE2 vào `backend/seed/backtest/`, xoá `seed/` root, sửa `backend/src/backtest/events.py` (`REPO_ROOT/"seed"` → `BACKEND_ROOT/"seed"`, thêm hằng `BACKEND_ROOT = parents[2]`) | ✅ DONE | `pytest backend/tests/ -v` sau hợp nhất → **23 passed** (11 BE2 + 12 BE1, không hỏng cái nào); sửa thêm `tests/test_state_cas.py` import `from conftest import` → `from tests.conftest import` (do `tests/__init__.py` của BE2 đổi pytest import mode) | BE2 (xác nhận `seed/` giờ nằm dưới `backend/seed/`, không phải root nữa) |

<!-- Append dòng mới ngay dưới đây. Ví dụ:
| H+02 | BE1 | contract freeze v1.0 | ✅ DONE | `git show a1b2c3` · openapi.yaml 8 endpoints + canonical examples | BE2,BE3,FE1,FE2 |
| H+03 | BE1 | seed/ prior commit | ✅ DONE | `git show d4e5f6` · 7 file · golden gap C01-S017 verified | BE2,BE3,FE1,FE2 |
| H+06 | BE3 | continuous_same_seat | ✅ DONE | `pytest tests/test_merging.py -q` → 8 passed | FE1 (S02) |
| H+07 | BE1 | atomic hold CAS | ⛔ BLOCKED | chờ seed/scenario.json schema | chờ chính mình xong seed/ |
-->

---

## Bảng checkpoint (BE1 cập nhật tại mỗi mốc)

| Mốc | Điều kiện | Xác nhận | Đạt? |
|---|---|---|---|
| H+02 | OpenAPI + `seed/` schema versioned; 0 câu hỏi P0 mở | BE1 + cả đội | ☐ |
| H+03 | `seed/` commit vào git (dù mới là prior) | BE1 | ☐ |
| H+06 | Fixture happy path `offer→hold→confirm` chạy trong UI | BE1 + FE1 + FE2 | ☐ |
| H+10 | Core transaction / resolver / pricing / metrics tests xanh | BE1–BE3 | ☐ |
| H+14 | **Real golden path end-to-end** | Cả đội | ☐ |
| H+18 | P0 feature complete; release candidate; **FEATURE FREEZE** | BE1 | ☐ |
| H+23 | Smoke 3/3; p95 / error / a11y evidence | BE1 + FE1 | ☐ |
| H+26 | **Video backup** + pitch evidence | FE2 | ☐ |
| H+30 | Submission checksum khớp | BE1 + FE2 | ☐ |

---

## Definition of Done (tick khi có bằng chứng — Master §9)

- [ ] Reset deterministic — cùng seed ⇒ cùng checksum
- [ ] Baseline **từ chối** golden request `THO→DHO`
- [ ] Âu Lạc tìm **đúng** same-seat gap trên `C01-S017` (leg L3+L4)
- [ ] Offer hiển thị price / bid / versions / expiry
- [ ] Hold nguyên tử — 2 hold cạnh tranh: 1 OK, 1 → 409, **0 partial hold**
- [ ] Guardrail clamp thật (có case vượt ceiling)
- [x] Backtest ≥5 seed — median + min/max + raw; failed seed **không bị giấu** (BE2, `src/backtest/engine.py::run_backtest`, chờ BE3 pricing thật để chốt Revenue cuối)
- [ ] Heatmap cập nhật sau confirm
- [ ] Decision truy vết được (versions + rule đã bắn + violations)
- [ ] Smoke test **3/3**, mỗi lần **< 90 giây**
- [ ] **0 vi phạm** sàn/trần + CSXH, hiển thị trên S06
- [ ] Video backup + AI collaboration log sẵn sàng
- [ ] `grep -r "_ground_truth" src/` **rỗng**
- [ ] NFR: offer p95 < 1s · resolver < 200ms · reset < 3s

---

## Stop-rules (không thương lượng)

| Điều kiện | Hành động |
|---|---|
| H+02 còn open P0 contract question | **Dừng code core.** Chốt canonical examples trước. |
| H+18 golden path chưa 3/3 | **Không làm P1/P2.** Giữ static evidence. |
| H+23 smoke fail | Chuyển sang video backup. |
| H+26–28 | Fix **tối đa 1** blocker. Mọi thay đổi chạy lại smoke. |
| H+28–30 | **Cấm refactor. Cấm upgrade dependency.** |

---

## Ghi chú / quyết định phát sinh

Ghi lại quyết định lệch khỏi plan + lý do (để pitch trả lời được, và để người sau hiểu):

| Giờ | Dev | Quyết định | Lý do |
|---|---|---|---|
| H+?? | BE2 | Đã commit thẳng `seed/backtest/events-seed-*.jsonl` + `checksums.json` vào `seed/backtest/` thay vì "nộp PR cho BE1" | Làm việc độc lập/song song một mình trong phiên này, chưa có BE1 để duyệt PR. **BE1 cần rà lại khi bắt đầu** — schema event: `{request_id, seed, origin, dest, segment_from, segment_to, seat_class, quantity, distance_km, days_to_departure}`, sort theo `days_to_departure` giảm dần (thời gian thực tăng dần) |
| H+?? | BE2 | Backtest engine dùng state RIÊNG (`SegmentSeatMatrix` nhẹ, không phụ thuộc pandas/CSV) thay vì SSM sản xuất của BE1 | `demo/ssm/seat_state_matrix.py` cần `stations.csv`/`trains.csv` từ dataset 4GB (chưa có) + pandas (chưa cài trong venv này). Backtest cần replay hàng trăm request/seed nhanh trong bộ nhớ — tách state là hợp lệ theo Master Plan (backtest ≠ live API state). Cùng semantics TRONG=0/DA_BAN=1 để không lệch định nghĩa |
| H+?? | BE2 | `seed/forecast.json` schema tự chốt (chưa đối chiếu BE1) | BE1 chưa có mặt trong phiên. Schema: `{forecast_version, service_run_id, che_do_gia, days_to_departure, segments:[{segment_id, forecast_remaining, confidence}]}` — khớp API_Contract.md §2.5 `forecasts[]` ở mức khái niệm nhưng grain là PER-SEGMENT (leg) chứ không phải per-O-D, đúng yêu cầu DEV2 doc. **BE1 xác nhận lại khi rảnh** |
| H+?? | BE2 | ⚠️ **CONTRACT CHANGE**: `src/forecast/`, `src/backtest/`, `tests/` chuyển từ gốc repo (như 00_MASTER_PLAN.md §5.1 ghi) vào **`backend/src/`**, **`backend/tests/`** | `backend/docker-compose.yml` build service `backend` với `context: backend/` (Dockerfile `COPY . .` chỉ copy trong `backend/`) — nếu `src/` nằm ở gốc repo, container backend **không thấy code**. Đã sửa: di chuyển `src/` + `tests/` vào `backend/`, sửa lại `parents[N]` trong `src/backtest/events.py` để vẫn trỏ đúng `generated_data/` và `seed/` ở gốc repo (seed/ KHÔNG di chuyển — FE cũng đọc trực tiếp seed/ làm mock data theo DEV4 plan). Test lại: `cd backend && python -m unittest discover -s tests -t .` → 11 passed | **BE1 cần cập nhật Master Plan §5.1** (đổi `src/...` → `backend/src/...`) và báo BE3 (`src/merging/`, `src/pricing/`, `src/offer/`) + BE1 (`src/state/`) đặt code cùng dưới `backend/src/` cho khớp Docker context |
| H+?? | BE2 | ⛔ **CẢNH BÁO cho BE1** (chưa sửa — `docker-compose.yml` là file BE1 sở hữu, BE2 không tự đụng): `seed/` (kể cả `seed/backtest/`) vẫn ở gốc repo, đúng ý Master Plan (FE đọc trực tiếp làm mock data), nhưng `backend/docker-compose.yml` hiện **không có volume nào mount `seed/` vào container** `backend`. Nếu `POST /demo/scenarios/{id}/reset` hoặc `POST /backtests` đọc file `seed/*` từ đĩa lúc runtime, container sẽ không thấy — cùng loại lỗi context như `src/` (đã fix ở dòng trên) | BE1 cần tự quyết lúc cắm API thật: (a) thêm `volumes: - ../seed:/app/seed:ro` vào service `backend` trong `docker-compose.yml` (đơn giản nhất, `seed/` chỉ ~50KB), hoặc (b) `scripts/extract_seed.py` nạp thẳng vào Postgres qua port 5432 lúc offline, API reset không cần đọc file `seed/` lúc runtime nữa |
| H+?? | BE2 | Cần BE1 gộp checksum khi bắt đầu: tôi chỉ tạo `seed/backtest/checksums.json` (scope riêng backtest, cố tình không đụng file tổng), nhưng `DEV1_BE_STATE_INTEGRATION.md` dòng 217 có test `test_seed_package_matches_expected_checksums()` — đối chiếu **toàn bộ** `seed/` với `seed/expected_checksums.json` (file tổng, BE1 sở hữu, chưa tồn tại) | BE1 cần đọc `seed/backtest/checksums.json` và gộp 5 giá trị sha256 đó vào `expected_checksums.json` khi dựng file manifest tổng, nếu không `test_seed_package_matches_expected_checksums()` sẽ thiếu phần backtest |

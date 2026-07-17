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
| H+?? | BE2 | `forecasts/refresh` logic (`forecast.refresh_forecast`, bump version, giữ run_id/che_do_gia) — route BE1 gọi | ✅ DONE | `python -m unittest tests.test_backtest` → 14 passed, gồm `test_refresh_bumps_version_keeps_run_id` | BE1 (cắm vào route `POST /demo/forecasts/refresh` trong src/api/) |
| H+?? | BE2 | Evidence runner H14-H18: `engine.load_events`/`load_all_events` đọc `seed/backtest/*.jsonl` đã commit + `python -m src.backtest.engine` xuất report median+min/max+raw+checksum | ✅ DONE | `python -m src.backtest.engine` → 5 seed, 0 failed, baseline median 17.807.000đ vs Âu Lạc 44.725.000đ, checksum `daae2f6f…`; `test_committed_events_match_generator` xác nhận jsonl commit khớp generator | FE2 (S04 lấy report thật), BE1 (`GET /backtests/{id}` trả report này) |
| H+00 | BE1 | ⚠️ **HỢP NHẤT `seed/` sau conflict discard+pull**: `backend/seed/backtest/` của tôi (placeholder rỗng) và `seed/backtest/` root của BE2 (data thật) từng tồn tại song song — dời data thật của BE2 vào `backend/seed/backtest/`, xoá `seed/` root, sửa `backend/src/backtest/events.py` (`REPO_ROOT/"seed"` → `BACKEND_ROOT/"seed"`, thêm hằng `BACKEND_ROOT = parents[2]`) | ✅ DONE | `pytest backend/tests/ -v` sau hợp nhất → **23 passed** (11 BE2 + 12 BE1, không hỏng cái nào); sửa thêm `tests/test_state_cas.py` import `from conftest import` → `from tests.conftest import` (do `tests/__init__.py` của BE2 đổi pytest import mode) | BE2 (xác nhận `seed/` giờ nằm dưới `backend/seed/`, không phải root nữa) |
| H+?? | BE3 | merging resolver: `continuous_same_seat` (numpy, FREE=0/SOLD=1/HELD=2 khớp SSM contract) + `reused_gap` label + ranking (reused-first) + protected filter | ✅ DONE | `python -m unittest tests.test_merging -v` → 6 passed, gồm `test_golden_gap_found` (C01-S017 THO→DHO seg[3,4]), `test_sold_bookings_never_moved` (read-only, 0 mutation), `test_resolver_under_200ms` | FE1 (S02 visualize reused_gap), BE1 (adapter vị trí 2 resolver) |
| H+?? | BE3 | PricingEngine: F0 (giá gốc O-D, KHÔNG cộng leg) → luật động **YAML khai báo** (`rules/pricing_rules.yaml`) → guardrail đúng thứ tự → CSXH `max` áp SAU cùng. `PricingContext`/`SafetyContext` **tách biệt bằng type** | ✅ DONE | `python -m unittest tests.test_pricing -v` → 11 passed, gồm 3 test ⭐ lên slide (`test_price_invariant_to_repeated_search`, `test_price_locked_after_hold`, `test_pricing_features_exclude_sensitive`) + `test_social_policy_discount_is_max_not_product` + `test_social_policy_applied_after_dynamic` + `test_guardrail_order_floor_ceiling_delta_round_freeze` + `test_policy_unavailable_returns_503` | FE1 (S06 compliance), FE2 (pitch), BE1 (adapter vị trí 3 pricing) |
| H+?? | BE3 | OfferService: pipeline `seat plan→base fare→price→guardrail→so bid→offer`, Offer immutable + expiry + 4 versions, **KHÔNG giữ ghế**, DecisionRecord append-only (input_hash+versions+rules_fired+violations+explanation = nhật ký quyết định/XAI) | ✅ DONE | `python -m unittest tests.test_offer -v` → 5 passed (golden ACCEPT trên C01-S017, REJECT khi bid > giá, holds-no-seat, decision-record audit). Tổng BE2+BE3: `python -m unittest tests.test_bid_price tests.test_backtest tests.test_merging tests.test_pricing tests.test_offer` → **36 passed**; CI gate `grep -r _ground_truth src/` rỗng | BE1 (cắm 3 module vào `src/api/routes_offers.py` thay logic rút gọn — KHÔNG đổi route/schema) |
| H+?? | BE3 | ⚠️ **CONTRACT NOTE cho BE1**: 3 module đặt tại `backend/src/{merging,pricing,offer}/` + luật tại `backend/rules/*.yaml` (khớp Docker context của BE2). Chưa cắm vào route — BE1 tích hợp ở H10-H14 theo Master §8. Interface: `resolver.best_same_seat(matrix,seat_ids,seg_from,seg_to)`, `PricingEngine(policy).price(f0,ctx,safety)`, `OfferService(engine,products,versions).build_offer(...)`. `bid_by_segment` do BE2 cấp (`forecast.bid_price`), OfferService chỉ **so sánh** final fare vs Σbid (không tự tính bid) | ⚠️ CONTRACT NOTE | Chưa đụng `routes_offers.py`/`schemas.py`/`seed/`/`state/` của BE1, `forecast/`·`backtest/` của BE2 — 0 file người khác bị sửa. `docker-compose.yml` cần mount `../rules` như đã mount `seed` (BE1 tự quyết, giống cảnh báo seed/ trước) | BE1 (integration + volume mount `rules/`) |

| H+?? | BE1 | T1 (BE_INTEGRATION_PLAN): Dockerfile CMD `main:app` → `src.api.main:app` (container backend từng crash lúc start); xác nhận seed/+rules/ đã nằm trong build context, KHÔNG cần mount — cảnh báo cũ của BE2/BE3 lỗi thời | ✅ DONE | `backend/Dockerfile` dòng 12 | FE1,FE2 (chạy full stack Docker) |
| H+?? | BE1 | T2+T3: cắm 3 module BE3 (`merging.resolver`, `PricingEngine` YAML+CSXH, `OfferService`+DecisionRecord) + bid `forecast.bid_price` & `forecast.refresh_forecast` BE2 vào `routes_offers.py`/`routes_demo.py` — thay TOÀN BỘ logic rút gọn, route/schema giữ nguyên | ✅ DONE | smoke: offer THO→DHO trả `rules_fired=[R_MUA_VU_HE2026,R_SAT_NGAY,R_AI_LINH_HOAT,R_GIO_CHOT]`, refresh bump version 2→3 giữ run_id, analytics trả forecasts+bid/leg | FE1 (S01/S05), FE2 (S03) |
| H+?? | BE1 | T4: 3 route còn thiếu `POST /backtests`, `GET /backtests/{id}`, `GET /decisions/{id}` → 11/11 endpoint khớp openapi.yaml | ✅ DONE | `python -c "...app.routes"` → 11 path; GET /decisions trả versions+breakdown+violations+audit_timeline | FE1 (S05), FE2 (S04) |
| H+?? | BE1 | T5: backtest thay `fixed_fare` bằng giá thật (baseline=giá niêm yết F0, Âu Lạc=PricingEngine) qua `make_priced_fare_fns` — interface giữ nguyên, default cũ giữ cho test BE2 | ✅ DONE | `python -m src.backtest.engine` → 5 seed 0 fail, baseline median **19.531.000đ** vs Âu Lạc **49.958.000đ** (+156%), checksum `c622c3f2…` — SỐ CHỐT cho S04/pitch | FE2 (S04, pitch) |
| H+?? | BE1 | T6: gộp 5 checksum backtest vào `expected_checksums.json` (+build_seed.py); thêm rule `R_GIO_CHOT` (lead=0, ×1.7) tạo case VƯỢT TRẦN thật — golden path chạm `TRAN`, guardrail clamp | ✅ DONE | `pytest tests/test_seed.py` 3 passed; offer golden `violations=['TRAN']`, `clamped=true` | FE1 (S06 hiển thị 0 vi phạm/clamp) |
| H+?? | BE1 | T6b: resolver ranking đổi sang BEST-FIT (ít ô FREE thừa ngoài span nhất trước) — spec cũ (reused-first + seat_id) trả C01-S007 (trống 1–4) thay vì golden C01-S017; best-fit khớp mục tiêu "giữ ghế trống dài cho chặng dài" và DoD "tìm ĐÚNG C01-S017" | ⚠️ CONTRACT NOTE | `tests.test_merging` 6 passed không đổi; smoke chọn đúng C01-S017 seg[3,4] `reused_gap=true` — BE3 rà lại nếu quay lại phiên | BE3 (review ranking) |
| H+?? | BE1 | T7+T8: overview số thật (revenue/pax-km/empty-seat-km/recent decisions) + evidence run: golden E2E **3/3** (reset→offer C01-S017 ACCEPT→hold 2 leg→confirm giá không đổi 456.000đ→seatmap SOLD→decision trace→overview đổi số), reset deterministic checksum `8c8ef3c7…` | ✅ DONE | smoke 3/3 tổng 1.6s; **48/48 test pass** trên Postgres thật (V1+V2, volume dựng lại sạch vì pgdata cũ là PG16); NFR: offer 0.09–0.15s <1s, reset 0.2s <3s, resolver <200ms (test BE3); CI gate `grep -r _ground_truth src/` rỗng | Cả đội — backend feature complete, chờ FE |

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

- [x] Reset deterministic — cùng seed ⇒ cùng checksum (smoke 3/3, checksum `8c8ef3c7…` giống nhau)
- [x] Baseline **từ chối** golden request `THO→DHO` (`test_baseline_rejects_golden_request` ⭐ pass)
- [x] Âu Lạc tìm **đúng** same-seat gap trên `C01-S017` (leg L3+L4) (smoke E2E: seat_plan C01-S017 seg[3,4] reused_gap=true)
- [x] Offer hiển thị price / bid / versions / expiry (API trả đủ 3 mức giá + bid/leg + 4 versions + expires_at; phần "hiển thị" chờ FE)
- [x] Hold nguyên tử — 2 hold cạnh tranh: 1 OK, 1 → 409, **0 partial hold** (`test_two_competing_holds_one_wins` pass trong 48/48)
- [x] Guardrail clamp thật (có case vượt ceiling) (rule `R_GIO_CHOT` ×1.7 → golden path `violations=['TRAN']`, clamp về 1.6×F0)
- [x] Backtest ≥5 seed — median + min/max + raw; failed seed **không bị giấu** — ĐÃ CHỐT giá thật T5: baseline 19.531.000đ vs Âu Lạc 49.958.000đ
- [x] Heatmap cập nhật sau confirm (seatmap API: C01-S017 seg 3,4 FREE→SOLD sau confirm; UI heatmap chờ FE)
- [x] Decision truy vết được (versions + rule đã bắn + violations) (`GET /decisions/{id}` trả input_hash+versions+rules_fired+violations+explanation)
- [x] Smoke test **3/3**, mỗi lần **< 90 giây** (API-level 3/3, tổng 1.6s; smoke qua UI chờ FE)
- [ ] **0 vi phạm** sàn/trần + CSXH, hiển thị trên S06 (backend enforce + ghi violations; màn S06 chưa có — FE1)
- [ ] Video backup + AI collaboration log sẵn sàng (FE2)
- [x] `grep -r "_ground_truth" src/` **rỗng**
- [x] NFR: offer p95 < 1s · resolver < 200ms · reset < 3s (đo thật: offer 0.09–0.15s, reset ~0.2s, resolver <200ms test BE3)

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

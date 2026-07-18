
# Kế hoạch hoàn thiện Backend — tích hợp H10–H18

**Ngày lập:** 18/07/2026 · **Căn cứ:** rà soát code `backend/` đối chiếu `00_MASTER_PLAN.md` §7–§9, `progress.md` dòng 26/33/39/40/109.
**Hiện trạng:** thuật toán BE2/BE3 xong (36 test pass), nhưng API đang chạy logic rút gọn của phiên solo BE1 — chưa cắm module thật. Đây là plan cho giai đoạn Integration (Master §8, H10–H14) + chốt evidence (H14–H18).

**Nguyên tắc (giữ nguyên từ Master):** thay adapter từng cái một, chạy test + golden E2E trước khi thay cái kế tiếp. KHÔNG đổi route/schema — chỉ thay ruột. Thứ tự: `state → resolver → pricing → bid/forecast → backtest → evidence`.

---

## T1 — Sửa Dockerfile CMD (5 phút, chặn mọi thứ chạy trong Docker)

`backend/Dockerfile` dòng 12: `uvicorn main:app` → **`src.api.main:app`**. App nằm ở `src/api/main.py`, CMD hiện tại crash lúc container start.

- Lưu ý: KHÔNG cần mount `seed/`/`rules/` vào compose nữa — cả hai đã nằm trong `backend/` build context (`COPY . .` bao gồm). Cảnh báo cũ của BE2/BE3 trong progress.md đã lỗi thời.
- **Bằng chứng:** `docker compose up -d` → `curl localhost:8000/api/v1/demo/overview?service_run_id=SE1_2026-06-15_LE` trả 200.

## T2 — Cắm 3 module BE3 vào `POST /offers` (việc lớn nhất)

File sửa: `backend/src/api/routes_offers.py` (thay ruột, giữ route + response shape).

Thay logic rút gọn bằng pipeline thật, đúng interface BE3 đã công bố (progress dòng 40):

1. **Resolver:** `merging.resolver.best_same_seat(matrix, seat_ids, seg_from, seg_to)` thay cho `ssm.find_continuous_same_seat` — lấy `reused_gap` label thật (có booking trước/sau khoảng yêu cầu) thay vì suy diễn `(seg_to - seg_from) >= 1` đang sai bản chất.
2. **Pricing:** `PricingEngine(policy).price(f0, ctx, safety)` — nạp policy từ `rules/pricing_rules.yaml` + `rules/policy_constraints.yaml`. Được ngay: luật động (`R_HE2026_XA_NGAY`…), guardrail đủ 5 bước (floor→ceiling→max-delta→round-1k→freeze), CSXH `max` áp SAU cùng, `rules_fired` thật (đang trả `[]`).
3. **Offer:** `OfferService(engine, products, versions).build_offer(...)` — offer immutable + expiry + đủ 4 versions + DecisionRecord append-only (input_hash, versions, rules_fired, violations, explanation). Giữ nguyên: KHÔNG giữ ghế, REJECT khi `gia_cuoi < Σ bid`.
4. `bid_by_segment` lấy từ `forecast.bid_price` của BE2 (T3) — OfferService chỉ **so sánh**, không tự tính bid.

- Ràng buộc phải giữ khi nối: `PricingContext` không thấy `SafetyContext` (đã enforce bằng type + test của BE3 — đừng "tiện tay" truyền request nguyên con vào engine).
- **Bằng chứng:** toàn bộ test hiện có vẫn xanh (`pytest backend/tests/ -v`), thêm smoke qua uvicorn: golden request THO→DHO trả `rules_fired` ≠ rỗng, price breakdown 3 mức khớp `PricingEngine` chạy tay.

## T3 — Cắm forecast + bid thật của BE2

File sửa: `backend/src/api/routes_demo.py`, `routes_offers.py` (phần bid).

1. `POST /demo/forecasts/refresh`: thay stub trả cứng `forecast_version: 1` bằng `forecast.refresh_forecast` (đã có, test `test_refresh_bumps_version_keeps_run_id` pass) — bump version, ghi vào `demand_forecast`, giữ `run_id`/`che_do_gia`.
2. `POST /offers`: thay công thức bid inline (`REF_YIELD_PLACEHOLDER = 700`) bằng `forecast.bid_price` — cùng công thức "demo bid-price approximation" nhưng dùng `reference_yield_per_km` hiệu chuẩn từ seed thay vì hằng số bịa.
3. `GET /demo/analytics`: điền `forecasts[]` từ `demand_forecast` (đang trả rỗng — FE1 S01 cần).

- **Bằng chứng:** refresh 2 lần → `forecast_version` tăng; offer sau refresh dùng version mới (bất biến 4-versions Master §7.1).

## T4 — Thêm 3 route còn thiếu (openapi có 11 path, FastAPI mới có 8)

File mới: `backend/src/api/routes_backtests.py` (đăng ký trong `main.py`); sửa nhỏ: route decisions có thể nằm chung file demo hoặc tách.

1. `POST /backtests`: gọi `backtest.engine.run_backtest` trên 5 file `seed/backtest/events-seed-*.jsonl` đã commit (loader `engine.load_all_events` có sẵn). Chạy đồng bộ là đủ (5 seed × ~400 events, engine đã chạy < vài giây) — trả `report_id`, lưu report vào bảng/JSON.
2. `GET /backtests/{report_id}`: trả median + min/max + raw từng seed + failed runs không giấu (report format engine đã xuất sẵn, checksum `daae2f6f…`).
3. `GET /decisions/{decision_id}`: SELECT từ `decision_record` (dữ liệu đã ghi từ /offers) — versions, price/bid breakdown, violations, rules_fired.

- **Bằng chứng:** POST /backtests → GET report khớp số đã có (baseline median 17.807.000đ vs Âu Lạc 44.725.000đ); GET /decisions/{id} của một offer vừa tạo trả đủ trace.

## T5 — Thay `fixed_fare` trong backtest bằng PricingEngine thật

File sửa: `backend/src/backtest/engine.py` (theo đúng contract note BE2 để lại — interface accept/reject + revenue giữ nguyên).

- Cắm `PricingEngine` của BE3 vào nhánh Âu Lạc để Revenue cuối là giá AI thật; baseline B0 giữ giá niêm yết. Chạy lại 5 seed → chốt con số median/range **cuối cùng** cho FE2 (S04) và pitch.
- **Bằng chứng:** `python -m src.backtest.engine` → report mới + checksum mới; `python -m unittest tests.test_backtest` xanh; cập nhật số vào progress.md (FE2 đang chờ số này).

## T6 — Gộp checksum + bổ sung fixture seed (DEV1 §fixture, dòng 111–117)

File sửa: `backend/seed/expected_checksums.json`, `backend/seed/initial_bookings.jsonl` (hoặc test), `backend/scripts/build_seed.py`.

1. Gộp 5 sha256 từ `seed/backtest/checksums.json` vào `expected_checksums.json` để `test_seed_package_matches_expected_checksums` phủ đủ toàn bộ gói seed (yêu cầu BE2, progress dòng 109).
2. Fixture còn thiếu — quyết định luôn tại đây: **cover bằng test/API call thay vì nhét vào seed** (2 hold cạnh tranh đã có `test_two_competing_holds_one_wins`; hold là trạng thái runtime, không hợp với seed tĩnh). Riêng **case giá vượt ceiling** là mục DoD riêng ("guardrail clamp thật") → thêm 1 O-D hoặc 1 rule trong `pricing_rules.yaml` mà đề xuất động vượt trần, để demo và S06 hiển thị clamp + violation thật.
3. Protected passenger fixture: 1 request mẫu có `SafetyContext` protected → nhận same-seat option, không nhận `requires_seat_change` (test BE3 đã có filter — chỉ cần 1 case gọi qua API).

- **Bằng chứng:** `pytest tests/test_seed.py -v` xanh với manifest đầy đủ; 1 offer bị clamp có `clamped: true` + violation trong DecisionRecord.

## T7 — Điền số thật cho `/demo/overview`

File sửa: `backend/src/api/routes_demo.py`.

- `total_revenue_vnd` (Σ `final_price_vnd` các booking CONFIRMED), `recent_decisions` (5 dòng cuối `decision_record`), `passenger_km`/`empty_seat_km` (tính từ seatmap × bảng km đã có), `false_sold_out_rate` (từ decision REJECT/NO_SAME_SEAT trên tổng request — hoặc bỏ khỏi response nếu FE1 không dùng, chốt với FE1 trước khi viết).
- **Bằng chứng:** sau confirm golden path, overview đổi số; heatmap seatmap cập nhật (mục DoD "Heatmap cập nhật sau confirm").

## T8 — Evidence run: golden E2E + NFR + tick DoD

Không viết feature mới — chỉ chạy, đo, ghi.

1. **Golden E2E 3/3:** reset → offer THO→DHO (ACCEPT trên C01-S017, seg [3,4], reused_gap) → hold 2 leg nguyên tử → confirm (giá không đổi) → seatmap SOLD. Mỗi lần < 90s.
2. **NFR:** đo offer p95 < 1s, resolver < 200ms (test BE3 có sẵn), reset < 3s. Ghi số thật.
3. **CI gate:** `grep -r "_ground_truth" src/` rỗng (chạy lại sau mọi thay đổi).
4. **Reset deterministic:** reset 2 lần cùng seed → cùng checksum.
5. Tick từng dòng DoD trong `progress.md` **kèm bằng chứng** (lệnh + output), append dòng mới cho mỗi mục T1–T7 xong.

---

## Thứ tự & phụ thuộc

```
T1 ─→ (mọi thứ chạy được trong Docker)
T2 ─→ T3 ─→ T4(decisions cần T2 ghi DecisionRecord thật)
T2 + BE2 ─→ T5 (backtest cần PricingEngine đã cắm được)
T6 độc lập (làm xen kẽ), T7 sau T2/T3, T8 cuối cùng
```

Mỗi task xong → **append `progress.md` ngay** (luật Master §11). Sau T8 là FEATURE FREEZE — phần còn lại của dự án là FE (`web/` chưa tồn tại) + pitch, ngoài scope backend.

## Ngoài scope (đừng làm)

- Không JWT/Redis/worker/min-cost matching (P2 theo SDD Review G01).
- Không sửa dataset generator, không đụng 2 mô men lệch M8b/M9.
- Không refactor module BE2/BE3 đang xanh — chỉ nối.
- Không đổi `openapi.yaml`/schema response — FE mock theo nó rồi.

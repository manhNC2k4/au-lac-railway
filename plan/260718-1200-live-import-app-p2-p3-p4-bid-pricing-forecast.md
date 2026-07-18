# Kế hoạch: P2/P3/P4 — backend live-import `app/` (bid DLP + pricing elasticity + forecast model)

**Ngày lập:** 18/07/2026 · **Tiếp nối:** `plan/MODEL_BASE_INTEGRATION_PLAN.md` (P0-P8) + `plan/progress.md`.
**Đã xong trước đó (đọc để có context):** P0.1 (dataset local có), P0.4 (adapter `backend/src/adapters/model_adapter.py` done), P0.6 (`scripts/audit_constants.py` done), P1 (seed hiệu chuẩn từ dataset thật, xem `backend/scripts/calibrate_seed_from_dataset.py`), P6 (backtest số thật: baseline 18.848.000đ vs Âu Lạc 23.396.000đ = +24.1%, xem `backend/scripts/calibrate_backtest_lambda.py`).

**Quyết định vừa chốt (phiên trước, KHÔNG đảo lại nếu không có lý do mới):** P2/P3/P4 đi theo lối **live import `app/`** (đúng `BACKEND_GUIDE.md` + `MODEL_BASE_INTEGRATION_PLAN.md` §P0-P4 gốc) — KHÔNG offline-bake như P1/P6. Nghĩa là backend runtime sẽ import trực tiếp `app.bt3_allocation`, `app.bt5_pricing`, `app.bt1_forecast` — chấp nhận thêm scipy/sklearn vào backend, đổi Docker context.

**Blocker gốc — ĐÃ GIẢI QUYẾT:** `app/bt3_allocation.py` (và có thể `bt5_pricing.py`) import pandas ở **module-level**. Verified `backend/scripts/audit_constants.py:20` — `SRC = backend/scripts/../src`, cả 2 gate (`_ground_truth`, `import pandas`) và sweep literal đều `SRC.rglob("*.py")`, scope cố định `backend/src/`, KHÔNG quét `app/`. Gate không chặn `app/` → live-import hợp lệ, không cần sửa gate.

**Kiến trúc import — ĐÃ CHỐT:** import trực tiếp `app/` vào backend process (đúng plan gốc §3.3), KHÔNG tách subprocess/service riêng.

---

## Việc cần làm (theo thứ tự, mỗi bước xong chạy `pytest backend/tests/ -v` trước khi sang bước sau)

### Bước 1 — Docker context + dependencies (rủi ro thấp, làm trước)
- `backend/docker-compose.yml`: đổi service `backend` build `context: ..` (repo root), `dockerfile: backend/Dockerfile`.
- Thêm `.dockerignore` ở repo root: loại `generated_data/`, `demo/`, `web/`, `.git/` (tránh image phình — dataset ~380M đã sinh).
- `backend/requirements.txt` += `scikit-learn, scipy, joblib` — **pin đúng version đã dùng để train** `models/artifacts/bt1_forecast_hgb.joblib` (check version trong `models/train_bt1_forecast.py` hoặc chạy `pip show scikit-learn` lúc train nếu ghi lại, nếu không có thì dùng version hiện cài local khi train — verify bằng cách load thử joblib sau khi cài).
- Smoke: `docker compose up -d` → `curl localhost:8000/api/v1/demo/overview?service_run_id=SE1_2026-06-15_LE` trả 200.

### Bước 2 — Verify adapter còn đúng (đã có sẵn, chỉ verify)
- `backend/src/adapters/model_adapter.py` + `backend/tests/test_adapter.py` — chạy lại, xác nhận round-trip span 1-based inclusive `[from,to]` ⇄ 0-based nửa mở `[a,b)` của `app/bt2_ssm.py`, golden `[3,4]` ⇄ `[2,4)` đúng.

### Bước 3 — Boot sequence nạp artifact (`backend/src/api/deps.py`)
- Theo `BACKEND_GUIDE.md §2`: nạp `Pricer.load(use_elasticity=True)` (từ `models/artifacts/bt5_pricing_params.json` + `elasticity_params.json`), `DemandModel.load()` (`bt1_forecast_hgb.joblib`+`bt1_feature_spec.json`+`bt1_booking_curves.json`) — 1 lần lúc app start, KHÔNG mỗi request.
- **Fail-closed:** artifact thiếu/load lỗi ⇒ app vẫn boot nhưng endpoint pricing/bid trả 503 `POLICY_UNAVAILABLE` — viết test cho case này.

### Bước 4 — P2: Bid price = DLP thật (session này DỪNG ở scouting+quyết định kiến trúc, CHƯA CODE — resume từ đây)

**Bối cảnh đã xác nhận (không cần scout lại):**
- `app.bt3_allocation.analyze_run(ssm, pricer, chuyen_id, forecast)` (nguồn: `app/bt3_allocation.py:105-167`) đọc thẳng **private attrs** của `app.bt2_ssm.SeatStateMatrix`: `ssm._span[chuyen_id]` (tuple lo,hi ga idx), `ssm.st.ga_id`/`ssm.st.ly_trinh_km` (**pandas.DataFrame**, từ `stations.csv`), cộng method `.get_state(chuyen_id,cls)`, `.get_segment_meta(chuyen_id)`, `.load_factor(chuyen_id)`, `.seg_range(chuyen_id,ga_di,ga_den)`. `SeatStateMatrix.__init__` tự build ma trận RỖNG từ `generated_data/data/*.csv` — KHÔNG liên quan Postgres runtime state của mình. Return dict có key `bid_price_theo_lop` (dict theo seat_class), `lf_theo_doan`, `quota`, `doan_nghen`, `doan_trong`, `lf_max` (dùng ở Bước 5 cho trần động).
- `load_factor_route(ssm, chuyen_id, ga_di, ga_den, bid_by_class, seat_class)` (nguồn: `app/bt3_allocation.py:170-184`) — input trực tiếp cho BT5, cũng cần cùng shim `ssm`.
- **Quyết định đã chốt (user xác nhận):** viết shim thay `SeatStateMatrix`, đặt tại **`integration/ssm_from_postgres.py`** (KHÔNG phải `backend/src/`) — vì shim bắt buộc `.st` là `pandas.DataFrame` (khớp `ssm.st.ga_id`), nếu đặt trong `backend/src/` sẽ có literal `import pandas` dính CI gate `audit_constants.py`. `backend/src/allocation/cache.py` chỉ `from integration.ssm_from_postgres import build_shim` — không có literal `import pandas` trong `backend/src/` → qua gate. Khớp pattern có sẵn: multiseat resolver cũng port từ `integration/resolver_multiseat.py` (xem `plan/progress.md` dòng P5). Pandas THỰC THI trong request qua `app.bt3_allocation` là hệ quả đã chấp nhận khi chốt live-import trực tiếp ở Bước 1 (không phải vi phạm mới).

**Việc cần làm khi resume:**
1. `integration/ssm_from_postgres.py` (mới, cần pandas — được phép ở `integration/`):
   - Class shim (tên gợi ý `PostgresSeatStateMatrix` hoặc tương tự) nạp từ Postgres golden scenario (8 ga/40 ghế/7 leg, `service_run_id=SE1_2026-06-15_LE`) qua `backend/src/state/seat_state_manager.py` (snapshot) + `backend/src/adapters/model_adapter.py` (seatmap↔matrix, span↔cols).
   - `.st`: DataFrame cột `ga_id`, `ly_trinh_km` — build từ 8 ga golden (đã có trong `backend/seed/` — đọc từ đó, KHÔNG từ `generated_data/`).
   - `._span = {chuyen_id: (0, 7)}` (0-based half-open, 7 leg).
   - `.get_state(chuyen_id, cls)` → ma trận int8 TRONG/DA_BAN/DANG_GIU cho seat_class đó (chỉ `NGOI_MEM_DH` có 40 ghế thật; 2 lớp còn lại golden không có — trả ma trận rỗng `(0, 7)` để DLP ra bid=0 cho lớp đó, KHÔNG lỗi).
   - `.get_segment_meta(chuyen_id)` → per-segment `khu_gian_id`/`ga_dau`/`ga_cuoi` (từ seed, không phải CSV).
   - `.load_factor(chuyen_id)` → mảng LF theo 7 segment (occupancy thật từ snapshot).
   - `.seg_range(chuyen_id, ga_di, ga_den)` → `(a,b)` 0-based half-open theo tên ga (dùng `model_adapter.span_to_cols` nếu map được ga→segment index, nếu không thì viết logic riêng theo thứ tự 8 ga golden).
2. `backend/src/allocation/cache.py` (mới): cache key `(service_run_id, matrix_version, forecast_version)` → gọi `app.bt3_allocation.analyze_run(shim, pricer, chuyen_id, forecast_df)` qua `integration.ssm_from_postgres`. Refresh lúc `POST /demo/scenarios/{id}/reset` và `POST /demo/forecasts/refresh` (KHÔNG mỗi request — giữ p95 thấp). LP fail (`_solve_dlp` lỗi/exception) ⇒ không cache ⇒ đọc cache rỗng ⇒ route trả 503, KHÔNG fallback công thức cũ.
3. `routes_offers.py`: `bid_by_segment` đổi nguồn — đọc từ cache `allocation/cache.py` thay vì `forecast/bid_price.py`. **Xoá** `backend/src/forecast/bid_price.py` (công thức scarcity đóng cũ ×0.6) sau khi cache DLP thay thế hoàn toàn — kiểm tra không còn import nào trỏ tới trước khi xoá.
4. Đổi ngôn ngữ docs (`CLAUDE.md` phần "demo bid-price approximation", `docs/TECHNICAL_OVERVIEW.md` nếu có) → "DLP bid price (LP dual)" — vẫn KHÔNG claim EMSR-b.
5. **Bằng chứng cần có trước khi coi Bước 4 DONE:**
   - Test mới (`backend/tests/test_allocation_cache.py` hoặc tương tự): so `bid_price_theo_lop` từ cache với gọi tay `app.bt3_allocation.analyze_run` cùng input (qua shim) → khớp.
   - Offer golden ACCEPT/REJECT nhất quán so với trước khi đổi bid source (giá có thể đổi nhưng logic ACCEPT/REJECT phải hợp lý, không random).
   - Đo p95 offer request sau khi thêm cache (mục tiêu vẫn <1s theo NFR gốc — cache phải hit, không giải LP mỗi request).
   - `pytest backend/tests/ -v` toàn bộ xanh (hiện tại 84/84 trước Bước4).
   - **Sửa `tests/test_api_e2e.py`** dùng `with TestClient(app) as client:` (hoặc gọi `deps.load_models()` thủ công trong fixture) trước khi route pricing/bid thật sự cần `get_pricer()`/`get_demand_model()` — đã cảnh báo ở Bước 3, PHẢI sửa ở Bước 4/5 nếu không sẽ có 503 giả trong e2e test.
6. Sau khi code xong: append `plan/progress.md` theo format hiện có (append cuối bảng, dòng đánh dấu `H+??|INT|...`), rồi mới sang Bước 5.

**Trạng thái session trước khi dừng:** Bước 1/2/3/4 ✅ DONE (xem `plan/progress.md`). Bước 4 evidence: `pytest backend/tests/ -v` → 87 passed, `python tests/test_invariants.py` → 9/9 PASS. Tiếp theo: Bước 5 (P3 pricing = elasticity optimizer thật).

### Bước 5 — P3: Pricing = elasticity optimizer thật
- `backend/src/pricing/engine.py` v2: bước "đề xuất giá động" gọi `app.bt5_pricing.Pricer` chế độ elasticity (tối đa `P(mua|r)·(p−c)`, `c=Σ bid DLP` từ bước 4; trần động `1+0.15·LF_max`, sàn `1−0.05·(1−LF_max)`; mùa vụ từ `bt5_pricing_params.json`). `rules_fired` lấy từ `rule_ids`+`explain` của Pricer.
- **Giữ nguyên tuyệt đối** (test hiện có phải xanh, không sửa): guardrail 5 bước floor→ceiling→max-delta→round-1k→freeze, cap ±5%, held price bất khả xâm phạm, CSXH `max` SAU CÙNG, `PricingContext`≠`SafetyContext`, giá tất định, int64.
- Xoá `he_so` bịa tay trong `backend/rules/pricing_rules.yaml` (đặc biệt `R_GIO_CHOT` ×1.7 — cố ý bịa tạo case vượt trần). Thay case-vượt-trần bằng scenario phụ thật (ngày Tết, phụ thu mùa vụ thật + LF nghẽn thật chạm trần).
- **Bằng chứng:** test pricing cũ (11 test) + `tests/test_invariants.py` (tier-2, repo root) 9/9 xanh; đoạn nghẽn giá > F0, đoạn ế giá ≈ F0.

### Bước 6 — P4: Forecast runtime = DemandModel
- Boot nạp `bt1_booking_curves.json`; `POST /demo/forecasts/refresh`: `total = sold/F(u)` từ booking CONFIRMED thật trong DB, blend 0.5 với seed forecast (`DemandModel.update`), bump version, ghi `divergence` log.
- **Ghi rõ trong docs/pitch:** số golden tuyệt đối vẫn từ seed hiệu chuẩn (P1); DemandModel cấp CƠ CHẾ update/divergence — không claim model HGB (train trên 22 ga/448 chỗ) dự báo trực tiếp chuyến 40 ghế.
- **Bằng chứng:** refresh sau khi confirm thêm vé → forecast_version tăng theo sold thật; offer dùng version mới.

### Bước 7 — Nghiệm thu
- Chạy toàn bộ: `pytest backend/tests/ -v` + `python tests/test_invariants.py` (tier-2, repo root, 9/9) + golden E2E smoke (`THO→DHO` request qua uvicorn) + đo p95 offer (mục tiêu <1s theo NFR gốc, DLP/elasticity chạy nền cache theo version).
- Cập nhật `plan/progress.md` (append, không sửa dòng người khác) — ghi rõ bước nào done, bằng chứng lệnh+output.
- Cập nhật `CLAUDE.md` phần "bid-price approximation" → "DLP bid price thật" nếu xong.

---

## Rủi ro cần lưu ý khi bắt đầu session mới

1. Pin sklearn/scipy version đúng bản train artifact — version lệch có thể làm joblib load lỗi hoặc kết quả khác.
2. Giá golden sẽ đổi sau P3 (guardrail/elasticity khác công thức cũ) → báo FE fixture/video đổi 1 lần duy nhất, đừng để FE chạy theo nhiều lần.
3. Effort thực tế ước ~2-3 ngày-người (không phải việc 1 lượt chat).
4. Import trực tiếp `app/` vào backend process (đã chốt, không subprocess) — nếu p95/memory footprint có vấn đề khi test thật, quay lại cân nhắc tách process (chưa cần làm trước).

## Câu hỏi mở
Không còn — cả 2 câu hỏi trước (scope CI gate, kiến trúc import) đã chốt (xem đầu file).

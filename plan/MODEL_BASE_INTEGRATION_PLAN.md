# KẾ HOẠCH v2 — Backend chạy trên MODEL/APP, KHÔNG số bịa

**Ngày lập:** 18/07/2026 (v2, thay toàn bộ v1) · **Căn cứ:** audit code `backend/src/` + `backend/scripts/` +
`backend/rules/` + `app/` + `integration/` đối chiếu NOTE_DEV, BACKEND_GUIDE, BAO_CAO_KY_THUAT, Master Plan.

**End-state (định nghĩa "xong"):** sau khi hoàn thành plan này —
1. Mọi quyết định runtime (bid price, giá động, forecast, ghép chặng) do **lớp `app/` tính**, backend chỉ
   bọc API/transaction/audit (đúng kiến trúc BACKEND_GUIDE).
2. **Không còn con số nào trong runtime + seed là bịa/chọn tay**: mọi hằng số truy nguyên được về một
   trong các nguồn hợp lệ ở §2, có ghi nguồn tại chỗ khai báo.
3. Mọi bất biến cũ giữ nguyên: dataset ≠ runtime, thứ tự toán tử giá + CSXH max-last, int64,
   PricingContext ≠ SafetyContext, held price, CAS nguyên tử, `_ground_truth/` cấm runtime,
   route/response API v1 không đổi (chỉ MỞ RỘNG có kiểm soát cho multiseat + endpoint mới).

**Phân biệt quan trọng:** *kịch bản demo* (8 ga/40 ghế/golden gap C01-S017) là **spec dựng có chủ đích**
(Master §3.1) — không phải "số đo" nên không phải fake, nhưng phải công bố trong pitch. "Không fake số"
áp cho: hệ số giá, cầu dự báo, occupancy, bid, cường độ event, ngưỡng — những thứ giả danh số đo/hiệu chuẩn.

---

## 1. AUDIT SỐ BỊA HIỆN TẠI (đã xác minh từng dòng, 18/07/2026)

| # | Vị trí | Số bịa | Thay bằng (nguồn thật) | Task |
|---|---|---|---|---|
| A1 | `backend/scripts/build_seed.py:101` | `target_occ = {1:0.55, 2:0.60, 3:0.95, 4:0.70, 5:0.65, 6:0.30, 7:0.75}` — "chosen to match API_Contract example" | LF theo leg tương đương của SE1 trung tuần tháng 6 tính offline từ dataset (`demo/eda_dataset_for_5_subproblems.py` / `app.bt3` fill matrix), scale về 40 ghế; golden gap giữ nguyên (spec) | P1 |
| A2 | `backend/scripts/build_seed.py:183` | `forecast_remaining = remaining_cap × 0.6` phẳng mọi đoạn | `integration/forecast_seed_ref.py::build_forecast_calibrated` với `intensity[s] = (đã_bán + tìm-kiếm-bị-từ-chối-HẾT_CHO)/sức_chứa` tính offline từ search_log (lưu ý: số intensity trong `__main__` của file đó là minh hoạ — PHẢI tính lại từ dataset) | P1 |
| A3 | `backend/scripts/build_seed.py:184` + `integration/forecast_seed_ref.py:49` | `confidence: 0.85` chọn tay | Suy từ metric validation BT1 (`bt1_feature_spec.json` metrics — vd theo MASE/coverage), một công thức, ghi nguồn | P1 |
| A4 | `backend/scripts/build_seed.py:189` | `build_backtest_placeholders()` — dead code (BE2 đã đè events thật) | Xoá; events từ P6 | P1 |
| A5 | `backend/scripts/build_seed.py:32` | `RHO_T = 1.1` hardcode | Đọc từ `trains.csv`/YAML (giá trị vẫn 1.1 nhưng đọc từ nguồn, không gõ tay) | P1 |
| A6 | `backend/src/forecast/bid_price.py:18-19` | `DEFAULT_P_LOW=0.5, DEFAULT_P_HIGH=0.9` — ngưỡng bịa của công thức scarcity đóng | **Bỏ cả công thức**: bid runtime = DLP dual thật (`app/bt3_allocation.py`, LP HiGHS <10ms/chuyến) | P2 |
| A7 | `backend/src/api/routes_offers.py:131` | fallback inline `remaining_by_seg[s] * 0.6` | Xoá — forecast thiếu ⇒ 503 POLICY_UNAVAILABLE (fail-closed, nhất quán §API) | P2 |
| A8 | `backend/rules/pricing_rules.yaml` | Toàn bộ `he_so` chỉnh tay: 1.075, 1.045, 0.92, 1.06, 0.85 (`R_AI_LINH_HOAT` — đã chứng minh LỖ vì β=−1.19) | Mùa vụ: hệ số DGP thật từ `bt5_pricing_params.json` (xuất từ YAML). Động: **optimizer elasticity runtime** (`app/bt5_pricing.py` + `app/elasticity.py`), không còn he_so tĩnh | P3 |
| A9 | `backend/rules/pricing_rules.yaml:44-49` | `R_GIO_CHOT` ×1.7 — **cố ý bịa** để tạo case vượt trần | Xoá. DoD "guardrail clamp thật" chuyển thành: (a) unit test clamp (đã có), (b) scenario phụ Tết dùng phụ thu mùa vụ THẬT từ YAML + nghẽn thật để chạm trần sống trên UI | P3 |
| A10 | `backend/src/backtest/events.py:30-31` | `HORIZON_DAYS=90`, `TARGET_TOTAL_REQUESTS=400` chọn tay; NHPP lấy shape từ YAML prior chứ không từ dữ liệu quan sát | λ per O-D từ search_log SE1 (map leg 8-ga), scale sức chứa `40/448` (phép biến đổi tất định, ghi công thức); horizon = `H_horizon` thật của 15/06 từ `calendar_events.csv` (đợt HE_2026) | P6 |
| A11 | Số pitch backtest "+156%" (baseline 19.5tr vs 50.0tr) | Artifact của kịch bản demo (baseline từ chối gần hết) — không phải uplift doanh thu | Evidence chính = backtest model trên dữ liệu thật (`models/artifacts/backtest_report.json`): Tết +2.3%, 89.0% tối ưu offline, ghế trống cục bộ −52%, MASE 0.515, 0 vi phạm | P6 |

**Số KHÔNG phải fake — giữ nguyên, chỉ bổ sung ghi nguồn tại chỗ:**
κ₀/θ=0.87/sàn 0.55/trần 1.6/max-delta 5% (YAML DGP + neo [THẬT] SE1 1.152.000đ/1726km);
lý trình ga (thật); `weight` ga (YAML §1 mang_luoi); CSXH 0.15/0.25/0.10/0.30 (NĐ 16/2026, khớp
`seed/pricing_policy.json`); β_ln(r)=−1.19 (ước lượng từ search_log); `elastic_markup_max=0.15 /
markdown=0.05 / lf_ref / BOTTLENECK_LF=0.85 / SLACK_LF=0.35 / dwell 5' / U=14 / DIV_THRESHOLD=15%`
(tham số chính sách của lớp model, đã validate bằng backtest — BAO_CAO §7.3: re-tune trên tập validate
riêng trước khi khoá, không tinh chỉnh trên tập test).

---

## 2. NGUỒN SỐ HỢP LỆ (whitelist truy nguyên — mọi hằng số mới phải thuộc 1 trong 5)

1. **Dataset qua pipeline offline** (`models/*.py`, `demo/eda_*`, `app/bt3` offline) → khoá vào seed/artifact.
2. **YAML DGP** `04_THAM_SO_CAU_HINH_MO_PHONG.yaml` (nguồn số duy nhất của thế giới mô phỏng) + neo [THẬT].
3. **Văn bản pháp lý/chính sách** (NĐ 16/2026 — CSXH, sàn/trần).
4. **Artifact model đã ước lượng** (`models/artifacts/*.json|.joblib` — elasticity, F(u), forecast, DLP).
5. **Spec kịch bản demo** (8 ga/40 ghế/golden gap/5 seeds/demo clock) — được phép vì là thiết kế, phải công bố.

Quy tắc thi hành: hằng số trong `backend/src/` phải có comment `# nguồn: <1..5 + trỏ file/mục>`.
P8 có bước sweep kiểm toàn bộ literal.

---

## 3. NGUYÊN TẮC KIẾN TRÚC (khoá trước khi code)

1. **Postgres = nguồn sự thật giao dịch** (CAS hold/confirm/offer/decision_record — DoD đã pass, không đụng).
   `app/` = tầng tính toán **thuần đề xuất**: backend đọc snapshot DB → adapter → hàm `app/` → persist.
2. **Dataset ≠ runtime tuyệt đối**: runtime chỉ nạp artifact (json/joblib, vài MB) một lần lúc boot.
   Không pandas/parquet trong request path — thêm CI gate `grep "import pandas" backend/src/` rỗng.
3. **Import `app/` trực tiếp, không copy code** (tránh 2 bản lệch nhau). Hệ quả: đổi Docker build context
   lên **repo root** (compose `context: ..`, `dockerfile: backend/Dockerfile`), thêm `.dockerignore`
   loại `generated_data/`, `demo/`, `web/`. Image chứa `backend/ + app/ + models/artifacts/`.
4. **Một adapter duy nhất** `backend/src/adapters/model_adapter.py`: 1-based inclusive `[from,to]` + `seat_id`
   ⇄ 0-based nửa mở `[a,b)` + index; snapshot DB ⇄ ma trận int8 của `app/bt2`. Có test round-trip.
   Cấm convert tay trong route.
5. **Fail-closed**: artifact thiếu / LP fail / forecast thiếu ⇒ 503 POLICY_UNAVAILABLE. Không còn nhánh
   fallback dùng số mặc định (đó chính là nơi số bịa chui vào).
6. **Chốt 1 nguồn forecast (NOTE_DEV §4, quyết định cả team, ghi vào progress.md):** model `feat`
   LightGBM làm nguồn số chính thức (MASE 0.50, chống rò rỉ chuẩn nhất) → downstream `app/`
   (F(u)/DLP/elasticity/backtest) → runtime đọc qua seed + artifact.
7. **Route/schema API v1 giữ nguyên**; mở rộng duy nhất: nhánh multiseat của Offer (P5) + endpoint mới (P7).
   Đổi contract = impact list + BE1 duyệt (Master §5.1). Mỗi task xong → append `progress.md`.

---

## 4. LỘ TRÌNH — 9 đợt (P0 → P8)

### P0 — Tiền đề & khung tích hợp (BE1, ~½ ngày)

| Việc | Chi tiết |
|---|---|
| P0.1 Xác nhận dataset local | `generated_data/data/*.parquet` phải có trên máy seed-extractor (P1, P6 cần). Thiếu ⇒ chạy `generate_data.py` (~30–90'). **Chỉ chặn P1/P6**, P2–P5 vẫn tiến hành song song |
| P0.2 Dependencies | `backend/requirements.txt` += `scikit-learn, scipy, joblib` (numpy đã có); `ortools` optional (group seating có fallback greedy). Pin version = version đã train artifact |
| P0.3 Docker context | Đổi context lên repo root (nguyên tắc §3.3) để image thấy `app/` + `models/artifacts/`; `.dockerignore` loại generated_data/demo/web. Smoke: `docker compose up` → 11 endpoint sống |
| P0.4 Adapter | `backend/src/adapters/model_adapter.py` + `tests/test_adapter.py` (round-trip index/seat_id/matrix; golden gap [3,4] ⇄ [2,4) đúng) |
| P0.5 Boot sequence | Theo BACKEND_GUIDE §2: nạp `Pricer.load(use_elasticity=True)`, `DemandModel.load()`, artifact 1 lần trong `api/deps.py`; artifact thiếu ⇒ app vẫn boot nhưng endpoint pricing trả 503 (fail-closed, test) |
| P0.6 CI gates mới | (a) `grep -r "_ground_truth" backend/src/ app/` rỗng (giữ); (b) `grep "import pandas" backend/src/` rỗng; (c) khung script `scripts/audit_constants.py` cho P8 |

### P1 — Seed hiệu chuẩn 100% từ dataset (BE2, cần P0.1; ~1 ngày)

Sửa `backend/scripts/build_seed.py` (offline — được phép pandas):

1. **A1**: `target_occ` ← LF theo leg của SE1 các chuyến trung tuần 06/2026 trong dataset (map 22 ga → 8 ga
   theo lý trình), scale 40 ghế. Ghi lệnh sinh + ngày chạy vào comment. Golden gap C01-S017 dựng đè lên nền
   occupancy thật (spec — công bố).
2. **A2**: `build_forecast` ← `build_forecast_calibrated` với intensity tính bằng
   `demand_intensity_from_unmet(sold, unmet_search, capacity)` trên leg tương đương từ search_log.
3. **A3**: `confidence` ← công thức từ metric BT1 (`bt1_feature_spec.json`), ghi nguồn.
4. **A4**: xoá `build_backtest_placeholders`. **A5**: `RHO_T` đọc từ nguồn.
5. Rebuild seed → checksum mới vào `expected_checksums.json` → **báo FE một lần** (số/fixture đổi).

**Bằng chứng:** `pytest backend/tests/test_seed.py` xanh; `GET /demo/analytics` cho pressure/bid phân hoá
theo đoạn (nghẽn L3 cao, ế L6 ~0); smoke golden vẫn chọn C01-S017 seg[3,4].

### P2 — Bid price = DLP thật (BE2; ~1 ngày)

1. Module mới `backend/src/allocation/` — alloc-cache theo `(service_run_id, matrix_version, forecast_version)`:
   gọi `app.bt3_allocation.analyze_run` qua adapter (input = snapshot DB + forecast DB) → cache
   `bid_price_theo_lop` + LF + quota + bottleneck. Refresh khi reset / forecasts-refresh / mỗi N confirm.
2. `routes_offers.py`: `bid_by_segment` ← cache DLP; **xoá** `forecast/bid_price.py` (A6) và fallback
   `*0.6` (A7). LP fail ⇒ 503 (không rơi về công thức xấp xỉ — nguyên tắc §3.5).
3. Ngôn ngữ/docs: "demo bid-price approximation" → **"DLP bid price (LP dual)"** — đúng bản chất mới;
   vẫn KHÔNG claim EMSR-b; vẫn không đụng `_ground_truth`.

**Bằng chứng:** test so bid DLP với `app/bt3` chạy tay cùng input; offer golden REJECT/ACCEPT nhất quán;
p95 offer < 1s (LP cache nền, backtest model đo 6–7ms/request).

### P3 — Pricing = elasticity optimizer thật (BE3; ~1–1.5 ngày)

1. `pricing/engine.py` v2: bước "đề xuất giá động" ← `app/bt5_pricing.Pricer` chế độ elasticity
   (tối đa `P(mua|r)·(p − c)`, `c = Σ bid DLP` từ P2; trần động `1+0.15·LF_max`, sàn `1−0.05·(1−LF_max)`;
   mùa vụ từ `bt5_pricing_params.json` — hệ số DGP thật, hết 1.075/1.045 gõ tay). `rules_fired` lấy từ
   `rule_ids` + `explain` của Pricer (audit/XAI giữ nguyên chất lượng).
2. **Giữ nguyên tuyệt đối** (test sẵn, chạy lại hết): guardrail 5 bước floor→ceiling→max-delta→round-1k→freeze,
   cap ±5% theo `gia_truoc`, held `gia_da_khoa`, CSXH `max` SAU CÙNG, PricingContext ≠ SafetyContext,
   giá tất định, int64.
3. **A8/A9**: xoá `he_so` bịa trong `pricing_rules.yaml`; xoá `R_GIO_CHOT`. DoD clamp: unit test (có sẵn)
   + **scenario phụ Tết** (`service_run` thứ 2, ngày trong cửa sổ Tết: phụ thu mùa vụ thật + LF nghẽn thật
   ⇒ chạm trần 1.6 sống trên S06). Seed scenario phụ do P1 pipeline sinh (cùng code, khác ngày).
4. Tham số policy (`elastic_markup_max`…) nạp từ `app/config.DEFAULT_POLICY` — một nguồn, ghi provenance.

**Bằng chứng:** 11 test pricing cũ + `tests/test_invariants.py` 9/9 của app xanh; cùng trạng thái ⇒ cùng giá;
demo case: đoạn nghẽn giá > F0, đoạn ế giá ≈ F0 (đúng "khan hiếm theo đoạn").

### P4 — Forecast runtime = DemandModel (BE2; ~½–1 ngày)

1. Boot nạp `bt1_booking_curves.json` (+ `bt1_forecast_hgb.joblib` cho cơ chế); `POST /demo/forecasts/refresh`:
   unconstrain `total = sold/F(u)` từ booking CONFIRMED thực tế trong DB, blend 0.5 với seed forecast
   (đúng `DemandModel.update`), bump version, ghi `divergence` log.
2. **Trung thực về grain, ghi vào pitch:** số tuyệt đối của golden đến từ seed hiệu chuẩn (P1);
   DemandModel cấp **cơ chế** update/divergence/drift — không claim model HGB dự báo trực tiếp chuyến 40 ghế.

**Bằng chứng:** refresh sau khi confirm thêm vé → forecast_version tăng + số đổi theo sold thật;
divergence log xuất hiện; offer dùng version mới (bất biến 4-versions).

### P5 — Ghép chặng đầy đủ BT4, gồm nhiều ghế (BE3 + BE1 + FE2; ~1–1.5 ngày)

1. `merging/resolver.py`: giữ same-seat best-fit; khi rỗng → `resolve_multiseat_options`
   (port `integration/resolver_multiseat.py` — đã đúng convention 1-based/inclusive/FREE-SOLD-HELD,
   dwell ≥5', loại trừ `priority_passenger`, tất định).
2. `api/schemas.py`: nhánh `seat_plan[]` nhiều leg + `requires_customer_consent` + `change_station_ids`
   + `so_lan_doi_cho` (⚠️ CONTRACT CHANGE — impact list cho FE, BE1 duyệt).
3. `/holds` + `state/seat_state_manager.py`: CAS **nhiều cell-set trong MỘT transaction**, all-or-nothing
   (mở rộng logic 1 ghế; test 2-ghế-2-leg: 1 cell fail ⇒ rollback tất cả).
4. Dwell: `scenario.json` thêm `dwell_minutes` per ga từ biểu đồ chạy tàu thật (nguồn 1/2 — không bịa).
5. FE: disclosure bắt buộc (số lần đổi + ga đổi), chỉ tiếp tục khi khách bấm đồng ý — không auto-accept.
6. Scenario phụ demo đổi chỗ; **golden 1-ghế giữ nguyên** cho luồng chính.

**Bằng chứng:** test nhóm ưu tiên KHÔNG BAO GIỜ nhận phương án ghép (chạy qua API); test consent-required;
CAS multi-set nguyên tử; golden path không đổi hành vi.

### P6 — Backtest & bằng chứng không số bịa (BE2; ~1 ngày, cần P0.1)

1. **A10**: `backtest/events.py` v2 — λ per O-D từ search_log SE1 (map leg 8-ga), scale `40/448`
   (biến đổi tất định, ghi công thức trong docstring); horizon = `H_horizon` của 15/06 từ
   `calendar_events.csv`. Giữ 5 seeds `20260717..20260721`, deterministic, checksum.
2. Engine: nhánh Âu Lạc = Pricer elasticity (P3) + DLP gating (P2); baseline FCFS = giá niêm yết F0.
   Chạy lại 5 seed → số S04 cuối.
3. `GET /backtests` trả thêm **report dữ liệu thật** của model (`models/artifacts/backtest_report.json`) —
   nguồn evidence chính: Tết **+2.3% DT** (89.0% tối ưu offline vs FCFS 87.0%), ghế trống cục bộ **−52%**,
   MASE **0.515**, β=−1.19, p95 6–7ms, **0 vi phạm**.
4. **A11**: mọi chỗ dùng "+156%" (pitch/S04/progress) sửa lại thành minh hoạ cơ chế kịch bản,
   uplift doanh thu chỉ claim bằng số backtest dữ liệu thật.

**Bằng chứng:** `python -m src.backtest.engine` → 5 seed 0 fail, checksum mới; report API khớp
`backtest_report.json`; docstring có công thức scale.

### P7 — Tính năng vận hành từ `app/` (Phase 2 đề bài; BE1/BE2/BE3; ~1.5–2 ngày)

| Việc | Nội dung | Owner |
|---|---|---|
| P7.1 Audit ProposalLog | Migration V3 bảng `proposal_log`; persist mọi `_log` từ quote/realloc + `model_version` + ai áp, lúc nào | BE1 |
| P7.2 C2 tái phân bổ + phê duyệt + rollback | `POST /allocation/refresh` → `app.reallocation.propose_reallocation` → queue duyệt (role điều độ viên, approve/reject); QuotaTable version hoá; rollback = áp lại bản cũ | BE2 + BE1 |
| P7.3 C5 hàng chờ | `NO_SAME_SEAT_OPTION` ⇒ `waitlist.add`; worker `expire_holds` ⇒ `waitlist.match` (YC6→YC7) | BE1 |
| P7.4 C4 xếp nhóm | `POST /group/quote` → `app.group_seating.plan_group` (CP-SAT 1 worker seed cố định; fallback greedy) | BE3 |
| P7.5 Drift monitor | Log `divergence` theo (chuyến, băng), alert ≥15% (`reallocation.DIV_THRESHOLD`) lên `GET /demo/overview` alerts | BE2 |
| P7.6 Manual override | Ghi đè giá/quota TRONG sàn–trần, log lý do vào ProposalLog | BE1 |

### P8 — Sweep số + nghiệm thu tổng (cả đội; ~½ ngày)

1. `scripts/audit_constants.py`: quét literal số trong `backend/src/` — mỗi hằng phải thuộc whitelist
   kỹ thuật (0/1/-1/1000-round/HTTP codes/kích thước mảng) hoặc có comment `# nguồn:`. Output = bảng
   provenance cuối, đính vào docs (giám khảo hỏi "số này ở đâu ra" → trả lời được từng số).
2. Chạy toàn bộ: test backend (48+ mới) + `tests/test_invariants.py` 9/9 + golden E2E 3/3 + scenario phụ
   (Tết clamp, multiseat) + NFR (offer p95 <1s, resolver <200ms, reset <3s) + reset determinism
   + 3 CI gates (P0.6).
3. Cập nhật tài liệu cho khớp thực tế mới: `CLAUDE.md` (bid approximation → DLP; trạng thái repo),
   `BACKEND_GUIDE.md` (boot sequence thực tế), `openapi.yaml` (nhánh multiseat + endpoint P7),
   `NOTE_DEV.md` (đánh dấu §3 đã xử lý), append `progress.md` từng mục P0–P8 kèm bằng chứng.

---

## 5. THỨ TỰ & PHỤ THUỘC

```
P0 (khung + deps + adapter + docker context)
 ├─ P1 seed hiệu chuẩn  ──────────────┐        (cần dataset local P0.1)
 ├─ P2 bid DLP  ──► P3 pricing elasticity ──► P6 backtest & evidence
 │                        │                        (P6 cần P1 + P3)
 │                        └─► P4 forecast runtime
 ├─ P5 multiseat (độc lập P1–P4; cần BE1+BE3+FE)
 └──────► P7 ops features (sau P2/P3 vì realloc cần DLP + divergence)
                └─► P8 sweep + nghiệm thu (FEATURE FREEZE sau P8)
```

- **Đường găng:** P0 → P2 → P3 → P6 → P8 (xương sống "model thật + số thật").
- P1 song song ngay khi có dataset; P5, P7 song song theo người.
- Effort thô: ~7–9 ngày-người; 3 BE chia theo owner Master §5.1 → ~3 ngày lịch.
- **Chốt giá golden MỘT LẦN sau P3** (P1 và P3 đều làm giá đổi) rồi mới cập nhật fixture FE + video —
  tránh FE chạy theo 2 lần.

## 6. RỦI RO & ĐỐI SÁCH

| Rủi ro | Đối sách |
|---|---|
| Dataset không có local (chặn P1/P6) | Chạy generator sớm nhất có thể (30–90'); P2–P5 không chờ; TUYỆT ĐỐI không "tạm điền số" — đó là con đường quay lại fake |
| Docker context root làm image phình | `.dockerignore` chặt (generated_data/demo/web); artifact chỉ copy file cần |
| sklearn/scipy version lệch artifact | Pin đúng version đã train trong requirements; test load artifact lúc CI |
| Giá golden đổi → FE fixture/video lệch | Chốt số 1 lần sau P3 (xem §5); báo FE bằng 1 dòng CONTRACT CHANGE |
| Optimizer elasticity ngoại suy vùng thiên lệch nội sinh (BAO_CAO §2.3) | Giữ dải hẹp quanh F0 như `app/` đã cài; KHÔNG nới `elastic_markup_max` để "demo cho đẹp" |
| Grain HGB (22 ga/448 chỗ) vs golden (8 ga/40 ghế) | Số tuyệt đối từ seed hiệu chuẩn; DemandModel = cơ chế update/divergence — nói đúng như vậy trong pitch (P4.2) |
| Mất case clamp khi xoá R_GIO_CHOT | Scenario phụ Tết (phụ thu thật chạm trần) + unit test — DoD giữ nguyên, bằng chứng thật hơn |
| NFR p95 khi thêm LP/optimizer | DLP cache theo version (không giải per-request); backtest model đo 6–7ms/request — dư 30× so target 200ms |
| Tất định (reset cùng checksum) | HiGHS deterministic; CP-SAT 1 worker + seed; artifact versioned trong ProposalLog |
| Xung đột ownership | Giữ owner Master §5.1; schema change qua BE1; append progress.md từng mục |

## 7. DoD CUỐI — checklist "backend base on model, 0 số bịa"

- [ ] A1–A11 (§1) xử lý xong, từng dòng có bằng chứng (commit + test/output)
- [ ] `audit_constants.py` pass: mọi literal có nguồn thuộc whitelist §2
- [ ] Runtime: bid = DLP dual (`app.bt3`) · giá động = elasticity optimizer (`app.bt5`) · forecast refresh = `DemandModel` F(u) · merge = BT4 đầy đủ (same-seat + multiseat + consent + dwell + loại trừ ưu tiên)
- [ ] `pricing_rules.yaml` không còn `he_so` gõ tay; mùa vụ từ `bt5_pricing_params.json`
- [ ] Golden E2E 3/3 (C01-S017, seg[3,4]) + scenario phụ Tết-clamp + scenario phụ multiseat chạy
- [ ] Test: backend toàn bộ + `tests/test_invariants.py` 9/9 + adapter round-trip + CAS multi-set
- [ ] 3 CI gates rỗng: `_ground_truth` · `import pandas` trong `backend/src/` · literal không nguồn
- [ ] Evidence: `GET /backtests` trả cả 5-seed calibrated lẫn report dữ liệu thật; pitch không còn "+156%"
- [ ] NFR giữ: offer p95 <1s · resolver <200ms · reset <3s · reset deterministic
- [ ] Docs khớp thực tế (CLAUDE.md, BACKEND_GUIDE.md, openapi.yaml, NOTE_DEV.md) + progress.md append đủ

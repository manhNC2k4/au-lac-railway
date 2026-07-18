# 5 Bài toán con — Model + FastAPI

Triển khai đầy đủ 5 bài toán con của sơ đồ phân rã (`Decompose.docx`), chạy trên
dataset tổng hợp trong `generated_data/data/`. Tất cả module đọc/ghi qua **Seat State
Matrix** (bảng hợp đồng chung); output bài trước = input bài sau.

```
app/                     mã nguồn model + thuật toán (lớp hoàn thiện, đóng băng contract)
  contracts.py           A1 — bảng hợp đồng dataclass (đường may cho Backend)
  config.py              hằng số & chính sách dùng chung
  bt1_forecast.py        B  — Forecaster + DemandModel (lead-time, update, drift)
  bt2_ssm.py             A2 — Seat State Matrix + hold expiry + sổ giá khoá
  bt3_allocation.py      C1 — DLP theo lớp chỗ: quota + booking limit + bid price
  bt4_merge.py           C3 — ghép chặng đủ ràng buộc (dwell/hạng chỗ/disclosure/loại trừ)
  elasticity.py          đường cầu P(mua|r) + bộ tối ưu E[đóng góp] (từ search_log)
  bt5_pricing.py         C6 — định giá tối ưu DT: elasticity + bid-floor, cap ±5%, held, CSXH cuối
  reallocation.py        C2 — nhả hold + tái phân bổ động theo lệch dự báo
  group_seating.py       C4 — xếp nhóm CP-SAT (cùng toa/khoang, ghế liền)
  waitlist.py            C5 — hàng chờ thông minh, tự khớp khi nhả ghế
  api.py                 FastAPI demo wiring
models/
  train_bt1_forecast.py  TRAIN + export model BT1
  build_bt1_curves.py    export booking curve F(u) cho DemandModel
  estimate_elasticity.py ước lượng đường cầu P(mua|r) từ search_log
  make_backtest_forecast.py  forecast cho ngày backtest (train cutoff, không leakage)
  export_bt5_params.py   export tham số giá BT5
  artifacts/             *** FILE MODEL + report ***
eval/
  replay.py              D1 — replay search_log, 2 chính sách AI vs FCFS
  metrics.py             D2 — bộ chỉ số chấm điểm đề bài
  backtest.py            D3/D4 — backtest Phase 1 + fill matrix (heatmap data)
tests/test_invariants.py E  — 9 bất biến (guardrail, CSXH, held, tất định, ...)
run_all.py               chạy hoàn chỉnh, xuất output tổng hợp
BACKEND_GUIDE.md         *** hướng dẫn tích hợp cho đội Backend ***
```

## Cài & chạy

```bash
pip install -r requirements.txt

# 1) build file model (1 lần)
python models/export_bt5_params.py          # -> bt5_pricing_params.json
python models/train_bt1_forecast.py         # -> bt1_forecast_hgb.joblib + spec + contract
python models/build_bt1_curves.py           # -> bt1_booking_curves.json
python models/estimate_elasticity.py        # -> elasticity_params.json (đường cầu)

# 2) chạy hoàn chỉnh 5 bài toán, xem output
python run_all.py                           # -> models/artifacts/run_all_outputs.json

# 3) backtest Phase 1 (AI vs FCFS)
python models/make_backtest_forecast.py --cutoff 2026-02-01 --dates 2026-02-14
python eval/backtest.py --dates 2026-02-14,2026-05-20 --trains SE1,SE3,SE5,SE7

# 4) chạy API
uvicorn app.api:app --port 8000             # docs: http://127.0.0.1:8000/docs
```

## Model & artifact xuất ra (`models/artifacts/`)

| File | Bài toán | Loại | Nội dung |
|---|---|---|---|
| `bt1_forecast_hgb.joblib` | BT1 | **ML thật** | HistGradientBoostingRegressor(loss=poisson) đã fit |
| `bt1_feature_spec.json` | BT1 | schema | cột số/hạng mục + vocab category + metrics |
| `forecast_output_contract.csv` | BT1→BT3 | dữ liệu | bảng dự báo `{origin,dest,date,train_id,seat_class,forecast_demand}` |
| `bt5_pricing_params.json` | BT5 | rule config | kappa0, theta, varsigma, rho_t, sàn/trần, tham số AI |
| `bt1_booking_curves.json` | BT1 | model | đường cong đặt chỗ F(u) theo băng×Tết (lead-time) |
| `elasticity_params.json` | BT5 | **ML thật** | logistic P(mua\|r) — hệ số co giãn giá từ search_log |
| `backtest_report.json` | eval | báo cáo | AI vs FCFS + so với tối ưu offline (đủ chỉ số chấm) |
| `fill_matrix_*_*.csv` | eval | heatmap | ma trận LF chuyến×đoạn (dữ liệu heatmap) |
| `bt2_snapshot_*.npz`/`.meta.json` | BT2 | state | ma trận ghế×đoạn đã build (nạp nhanh, khỏi replay) |
| `bt3_allocation_*.json` | BT3 | dữ liệu | LF đoạn + quota (đoạn,băng) + bottleneck/slack + z_opt |
| `run_all_outputs.json` | tất cả | tổng hợp | output 5 bài toán cho các kịch bản demo |

BT2 và BT4 là **service thuật toán** (không có "model train"): trạng thái của chúng
là chính Seat State Matrix. BT3/BT5 là **tối ưu/rule-engine** cấu hình hoá; artifact là
tham số + bảng tiền tính. Chỉ BT1 là model học máy đúng nghĩa.

## Mô hình từng bài

- **BT1 Demand Forecasting.** Grain `(train_id, O, D, seat_class, ngày)`. Đặc trưng
  leakage-safe tại `u=14` (pickup `da_ban_truoc_u14`, tốc độ bán, lịch âm tương đối
  `tau_tet`, băng cự ly, lag 7 / rolling 28). Loss Poisson (dữ liệu đếm thưa → dùng
  MASE/Poisson deviance, không MAPE). Split theo `ngay_chay` tại điểm gãy 01/5/2026
  (train=LUAT, test=AI) — không split theo lúc mua (tránh rò rỉ horizon Tết 169 ngày).
- **BT2 Seat State Matrix.** Ma trận `ghế × đoạn`, ô ∈ {0 trống,1 đã_bán,2 đang_giữ}.
  Build bằng replay giao dịch first-fit; API `get_state / load_factor / apply_transaction`.
- **BT3 Segment Load + Allocation.** LF từng khu gian; quota `(đoạn, băng)` từ DLP
  `max Σ f·y s.t. A y ≤ chỗ_còn` (ma trận phủ đoạn → tổng đơn modular → nghiệm nguyên);
  bid price = dual sức chứa; liệt kê đoạn nghẽn (LF≥0.85) & trống (LF≤0.35).
- **BT4 Segment Merging.** Xếp hạng: (1) ghế xuyên suốt, (2) ghế lấp gap khít nhất,
  (3) ghép ≥2 ghế (`cần_đổi_ghế=true`) — ẩn với khách nhóm ưu tiên. Kèm ghế/đoạn, số
  lần đổi, ga đổi.
- **BT5 Dynamic Pricing.** `F0 = rho·varsigma·kappa0·d^theta` (khớp `gia_goc` dataset)
  → delta mùa vụ → delta động theo LF đoạn (phụ thu khi nghẽn / giảm AI khi ế) →
  guardrail sàn/trần. Trả giá int64 + `rule_ids` + câu giải thích.

## Chuỗi nối (booking)

`POST /booking/quote` minh hoạ output→input: **BT4** chọn ghế → **BT3** cấp LF hành
trình → **BT5** ra giá. Tất cả trên cùng một Seat State Matrix của `(chuyến, ngày)`.

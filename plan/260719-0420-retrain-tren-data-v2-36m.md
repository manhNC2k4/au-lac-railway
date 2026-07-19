# Plan: Retrain model tier-2 trên data mới V2 (36 tháng, 2023-07 → 2026-06)

**Ngày:** 2026-07-19 · **Trạng thái:** ✅ ĐÃ THỰC HIỆN XONG (cùng ngày)

> Kết quả: 4 model retrain OK (BT1 MASE 0.54, deviance 0.277; elasticity β=-5.49),
> `run_all.py` chạy trọn 5 bài toán, backtest fold 2026-05-20 & 2026-06-15
> (AI vs FCFS: DT +1.0%/+0.9%, ghế trống cục bộ -13%/-15%), 9/9 invariants PASS.
> Phát sinh ngoài plan: chuẩn hoá calendar V2 (`load_calendar()` trong app/config.py —
> tau_tet chỉ có quanh Tết, la_le 0/1, dot_ban_ve trống) và dedupe trains.csv
> (140 dòng/116 mã). Chi tiết xem git log + summary phiên làm việc.

## Bối cảnh — việc đã làm (dọn dẹp)

- Đã **xoá** data cũ 12 tháng (2025-07→2026-06, ~538 MB, gitignored, tái tạo được):
  `generated_data/data/` và `generated_data/_ground_truth/`.
- Đã **symlink** data mới V1-shaped 36 tháng vào đúng chỗ pipeline cũ đọc — không sửa `app/config.py`:
  - `generated_data/data` → `../../v2-as-v1-2023-07-01_2026-06-30/data`
  - `generated_data/_ground_truth` → `../../v2-as-v1-2023-07-01_2026-06-30/_ground_truth`
  - `Hackathon/v2-as-v1` → `v2-as-v1-2023-07-01_2026-06-30` (để default path của
    `backend/scripts/load_mock_from_dataset.py` chạy được).
- Sửa `.gitignore` (bỏ `/` cuối 2 pattern) để symlink cũng được ignore.
- Đã smoke-test: 36 partition transactions load OK qua `app.config.DATA`; các chuyến kịch bản
  `RUN:SE1:2026-02-14`, `RUN:SE7:2026-05-20`, `RUN:SE1:2026-06-15` đều tồn tại trong `run_summary.csv`.

## Khác biệt data V2 so với V1 cũ (đã xác minh, quyết định plan)

| Điểm | V1 cũ | V2 mới | Ảnh hưởng |
|---|---|---|---|
| `chuyen_id` | `SE7_2026-05-20` | `RUN:SE7:2026-05-20` | **Gãy** mọi chỗ `rsplit("_",1)` / f-string `{tau}_{ngay}` |
| `loai_cho` | tier (`NAM_K6_T1`…) | macro (`NAM_K6`, `NAM_K4`, `NGOI_MEM_DH`) | **Gãy ngầm**: `MACRO_CLASS.map()` → NaN, mất 2/3 lớp chỗ |
| Ga / tàu | 22 ga, ~SE* | 25 ga, 116 mã (thêm `HOL24-SE1`, `SUM26-SE5`, `HD1`…) | OK — code đọc từ `stations.csv`/`trains.csv` |
| `_ground_truth/offline_optimum` | phủ cả năm | **chỉ fold 2026-05-19 → 2026-06-30** (1 548 rows); `bid_price` là cột *defaulted* theo manifest | Backtest Tết 2026-02-14 **không chấm được** vs optimum; không dùng `bid_price` GT để chấm |
| `wtp` / `demand_true` | keyed đủ cột | chỉ `yeu_cau_id/wtp/phan_khuc` và `chuyen_id/ga_di/ga_den/lambda_thuc` (lossy, xem manifest `loss_notes`) | `eval/replay.py`, `eval/backtest.py` cần rà cột trước khi chạy |
| Regime break | 2026-05-01 | giữ nguyên (2024-01 toàn LUAT, 2026-06 có AI) | `REGIME_BREAK`, split train giữ nguyên |
| `ket_qua` search_log | có `BO_VI_GIA` | có (`BO_VI_GIA` 173 k rows/tháng 6) | elasticity chạy được |

## Bước 0 — Vá tương thích (bắt buộc trước khi train)

1. **`app/config.py`**: thêm identity key vào `MACRO_CLASS`:
   `{"NAM_K6": "NAM_K6", "NAM_K4": "NAM_K4"}` (giữ key tier cũ để không gãy chỗ khác).
2. **Helper chuyen_id** (đặt trong `app/config.py`), hỗ trợ cả 2 format:
   - `make_chuyen_id(mac_tau, ngay)` → `f"RUN:{mac_tau}:{ngay}"`
   - `mac_tau_of(chuyen_id)` → parse `RUN:x:y` trước, fallback `rsplit("_",1)`
   Thay tại các điểm gãy đã định vị:
   - `app/bt2_ssm.py:45` (`_ensure`) — chỗ gãy ngầm nhất: KeyError bị nuốt trong
     `build_date` → mọi vé đếm thành `failed`, ma trận rỗng mà không báo lỗi.
   - `app/api.py:174` và `:190`
   - `eval/backtest.py:28` (`runs = [f"{t}_{date}" ...]`)
   - `run_all.py` — các literal `"SE7_2026-05-20"`, `"SE1_2026-02-14"`
   - rà thêm `eval/replay.py`, `models/make_backtest_forecast.py` cùng pattern.
3. Rà `eval/backtest.py` khớp cột `offline_optimum` mới (`z_opt`, `z_fcfs` — có sẵn, chỉ cần xác nhận).

## Bước 1 — Train (thứ tự cố định, chạy ở repo root với `.venv`)

```bash
.venv/bin/python models/export_bt5_params.py       # bt5_pricing_params.json
.venv/bin/python models/train_bt1_forecast.py      # bt1_forecast_hgb.joblib + spec (36 tháng ~15M rows, RAM ~vài GB)
.venv/bin/python models/build_bt1_curves.py        # bt1_booking_curves.json (train < 2026-05-01 — giờ có 34 tháng LUAT thay vì 10)
.venv/bin/python models/estimate_elasticity.py     # elasticity_params.json
```

Kỳ vọng: nhiều history hơn (x3) → curve/forecast LUAT ổn định hơn; kiểm tra MAE in ra
của `train_bt1_forecast.py` so với số cũ trong `models/artifacts/` (đang tracked trong git — diff được).

## Bước 2 — Pipeline 5 bài toán + backtest

```bash
.venv/bin/python run_all.py                                        # sau khi vá Bước 0
.venv/bin/python models/make_backtest_forecast.py --cutoff 2026-02-01 --dates 2026-02-14
.venv/bin/python eval/backtest.py --dates 2026-05-20,2026-06-15 --trains SE1,SE3,SE5,SE7
.venv/bin/python tests/test_invariants.py                          # 9 invariants tier-2
```

- **Chọn ngày backtest trong fold 2026-05-19 → 2026-06-30** khi cần so với `offline_optimum`.
  Ngày Tết 2026-02-14 vẫn chạy replay/AI-vs-FCFS được nhưng bỏ cột so-với-optimum.
- Không dùng `offline_optimum.bid_price` làm thước đo (cột defaulted theo manifest).

## Bước 3 — Hậu kiểm & bàn giao

- Diff `models/artifacts/*.json` (tracked) — số mới vs cũ; cập nhật số liệu pitch nếu lệch nhiều.
- Commit: `.gitignore`, các vá Bước 0, artifacts mới, plan này.
- (Tuỳ chọn) nạp lại mock DB runtime:
  `cd backend/scripts && python load_mock_from_dataset.py --self-check` rồi chạy thật
  (symlink `Hackathon/v2-as-v1` đã trỏ đúng, default path hoạt động).

## Lưu ý còn treo

- `models/export_bt5_params.py` đọc YAML `Synthetic_DATA_guide/04_...yaml` — là config của
  **generator V1 cũ**; data V2 sinh từ generator khác. Policy (sàn/trần/δ) vẫn là chính sách
  chủ đích nên tạm giữ, nhưng nếu có bản YAML V2 thì đối chiếu lại.
- Manifest V2 (`v2-as-v1-.../manifest.json`) có `loss_notes` từng bảng — đọc trước khi
  dùng cột nào của `_ground_truth` để chấm điểm.

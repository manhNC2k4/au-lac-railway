# README_data — Dataset tổng hợp đường sắt hành khách Việt Nam (12 tháng)

**Sinh bởi:** `generate_data.py` | **Seed:** 20260717 | **Khoảng:** 2025-07-01 → 2026-06-30
**Bản chất:** Dataset **TỔNG HỢP (synthetic)**, KHÔNG phải dữ liệu vận hành của VNR.
Được hiệu chuẩn theo các mô men công bố công khai của VNR/Traravico (M1–M18, xem
`Synthetic_DATA_guide/04_THAM_SO_CAU_HINH_MO_PHONG.yaml` §12) và tái tạo bộ luật giá
hiện hành + sự kiện gián đoạn có thật (lũ 11/2025).

## Cấu trúc

```
data/
├─ stations.csv          # 24 ga trục Thống Nhất (lý trình km, tỉnh sau 01/7/2025)
├─ trains.csv            # mác tàu + sức chứa theo loại chỗ
├─ seat_inventory.csv    # snapshot lúc chốt sổ: (chuyến, khu gian, loại chỗ) → đã bán/sức chứa
├─ calendar_events.csv   # lịch âm-dương (tau_tet), lễ, đợt bán vé, H horizon, điểm gãy chế độ
├─ run_summary.csv       # mỗi chuyến: số vé, doanh thu, số gap, LF bình quân
├─ refunds.parquet       # trả vé (khấu trừ 30%) + hủy thiên tai (hoàn 100%)
├─ transactions/thang=YYYY-MM/part.parquet    # giao dịch vé (tiền = int64 đồng)
├─ search_log/thang=YYYY-MM/part.parquet      # ⭐ log MỌI yêu cầu, kể cả bị từ chối
└─ manifest.json         # seed, hash YAML, kết quả mô men
_ground_truth/           # ⚠️ CHỈ ĐỂ CHẤM ĐIỂM — cấm dùng làm feature
├─ demand_true.parquet   # Λ thật theo (chuyến, O–D)
├─ wtp.parquet           # WTP từng yêu cầu + phân khúc
└─ offline_optimum.parquet  # z_opt (hindsight LP), z_fcfs, bid_price π_e
```

## Cột quan trọng (transactions)

| Cột | Ý nghĩa |
|---|---|
| `lead_time_ngay` | u = số ngày trước giờ chạy lúc mua |
| `gia_goc / gia_niem_yet / gia_cuoi` | F0 → sau δ động (clip sàn/trần) → sau giảm CSXH |
| `doi_tuong_csxh, muc_giam_csxh` | giảm MAX một mức, áp SAU giảm động (Điều 40 NĐ 16/2026) |
| `rule_ids` | luật giá đã bắn (XA_NGAY, TET_CHIEU_RONG, SAT_NGAY, AI:x.xxx, CLIP…) — audit trail |
| `che_do_gia` | LUAT (trước 01/5/2026) / AI (từ 01/5/2026) — ⭐ điểm gãy chế độ |
| `so_lan_doi_cho` | M−1 (ghép chặng); đối tượng ưu tiên luôn = 0 |
| `trang_thai` | HIEU_LUC / BI_HUY_DO_THIEN_TAI |

`search_log.ket_qua`: MUA / BO_VI_GIA / TU_CHOI_HET_CHO / TU_CHOI_DOI_CHO /
TU_CHOI_GIAN_DOAN / VAO_HANG_CHO — dùng đo cầu chưa đáp ứng & unconstraining.

## Cơ chế mô phỏng (tóm tắt)

1. Cầu tiềm ẩn: gravity (P, Θ, ma sát cự ly) × mode-split logit (giá vé vào tiện ích;
   IV: thu phí cao tốc 15/7/2026) × bất đối xứng chiều quanh Tết × luồng KCN >900km.
2. NHPP conditional sampling (tương đương chính xác thinning Lewis–Shedler, không chia
   bin); đường cong đặt chỗ Beta-mixture: chặng ngắn đến SAU chặng dài.
3. Giá: F0 = ρ_t·ς_c·κ0·d^θ → δ mùa/lead/Tết chiều rỗng/sát ngày/AI (từ 01/5/2026,
   độ sâu tất định theo hash trạng thái) → clip sàn/trần → CSXH max sau cùng.
4. Gán chỗ first-fit 1 chỗ liên tục; hết mới ghép ≥2 chỗ (min interval cover, tham
   lam); khách phải đồng ý (σ model); trả vé (hazard) sinh khoảng trống → nguồn cung
   ghép chặng.
5. Gián đoạn: lũ 11/2025 hard-code + NHPP thinning theo vùng×mùa. Vé bị hủy ⟺ hành
   trình GIAO đoạn phong tỏa (không ngẫu nhiên đều) → hoàn vé BQ > giá vé BQ (M14).

## Kết quả hiệu chuẩn (run chốt 17/7/2026, seed 20260717)

7.644.889 vé | 16.044.435 yêu cầu tìm kiếm | 0 vi phạm ràng buộc cứng.

| Mô men | Kết quả | Target | Sai số | Đạt |
|---|---|---|---|---|
| M1 khách 6T/2026 | 4.077.184 | 3,90M | +4,5% | ✅ |
| M5 giá vé BQ | 507.959 đ | 514.000 đ | −1,2% | ✅ |
| M8 giá vé BQ Tết | 610.037 đ | 714.000 đ | −14,6% | ⚠️ |
| M8b tỷ số Tết/năm | 1,201 (mix cự ly +21%) | 1,39 | −13,6% | ⚠️ |
| M9 LF 22–29/4/2026 | 0,655 | 0,79 | −17,1% | ⚠️ |
| M14 hoàn vé BQ thiên tai | 679.315 đ; **tỷ số/BQ = 1,34** (biên 1,10–1,40 ✅) | 615.000 đ | +10,5% | ⚠️ sát biên |
| M15 tỷ lệ giảm AI/DT gộp | 0,206 | 0,207 | −0,5% | ✅ |

⚠️ **M8b/M9 chưa vào biên** — người dùng chấp nhận có chủ đích (2 vòng hiệu chuẩn).
M8b bị chặn cấu trúc: sức chứa Tết bind làm cầu chặng dài bị từ chối, mix bán không
dịch đủ. Knob để chỉnh tiếp: hệ số giảm cầu ngắn/trung dịp Tết (`Demand.lam`),
`aug_tet_runs`, `aug_base_runs` (M9) trong `generate_data.py` §STRUCT.

## Giới hạn đã biết (trung thực khoa học)

- **Phạm vi**: chỉ trục Thống Nhất + khu đoạn có lý trình trong YAML (SE1–10, SE17–22,
  SE29/30, NA1/2, SNT1/2, HĐ1–4). SPT1 (thiếu lý trình Phan Thiết) và tuyến nhánh
  HN–HP/HN–LC bị loại. **Chuyến `*TC*` (tăng cường) là proxy cho phần cung ngoài phạm
  vi** để tổng cung khớp mô men toàn mạng M1/M9.
- `tong_cho` trong YAML (546) mâu thuẫn với cấu trúc toa (448) — dùng cấu trúc toa.
- `kappa0` YAML mâu thuẫn neo giá [THẬT] — hiệu chỉnh lại từ neo SE1 HN–SG.
- `dist_tilt` (bão hòa 900km) + `SOLD_MIX_ADJ` là knob SMM rút gọn khớp M5; hiệu
  chuẩn đầy đủ CMA-ES 18 mô men chưa chạy.
- Thời tiết chưa gắn ERA5 (doc 03 §4.2) — gián đoạn mô phỏng dùng mùa vụ trực tiếp.
- Choice model rút gọn: WTP-threshold + recapture xác suất, chưa phải nested logit
  đầy đủ; hàng chờ chỉ log, chưa khớp nối lại.

## Tái lập

```
python generate_data.py                  # đầy đủ 12 tháng
python generate_data.py --start ... --end ... --kappa X --skip-lp   # tùy chọn
```
Một seed + một YAML ⇒ một dataset. Hash YAML ghi trong `manifest.json`.

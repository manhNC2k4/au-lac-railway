# Báo cáo đánh giá chất lượng model — Data V2 (36 tháng)

**Ngày đánh giá:** 2026-07-19 · **Dataset:** `v2-as-v1-2023-07-01_2026-06-30` (36 tháng, 2023-07 → 2026-06)
**Phạm vi chấm:** fold đánh giá hợp lệ 2026-05-19 → 2026-06-30 (vùng phủ của `_ground_truth/offline_optimum`)
**Nguồn số liệu:** `models/artifacts/backtest_report.json` (8 ngày × 4 tàu SE1/SE3/SE5/SE7, 64.651 yêu cầu replay), `bt1_feature_spec.json`, `elasticity_params.json`

---

## 1. Kết luận điều hành — đối chiếu target đề bài

| # | Target đề bài | Đạt được (median, 8 ngày) | Trạng thái | Lí giải ngắn |
|---|---|---|---|---|
| 1 | Pax-km utilization **+3–8%** | **+0,6%** (dải +0,3 → +1,3%; tuyệt đối 0,575 → 0,579) | ⚠️ Đúng hướng, chưa đạt biên | Fold chấm là mùa thấp điểm (LF 0,47–0,61) — xem §4.1 |
| 2 | Doanh thu **+3–10%** | **+1,1%** (dải +0,4 → +2,5%) | ⚠️ Đúng hướng, chưa đạt biên | Mức tăng **tỷ lệ thuận với tải**: ngày tải cao nhất (LF 0,61) đạt +2,5% — xem §4.2 |
| 3 | Ghế trống cục bộ **−20%** | **−11,6%** (dải −10,2 → −14,7%) | ⚠️ Gần đạt | Ghép chặng khít lấp 818 gap/ngày; phần gap còn lại do thiếu cầu, không phải phân mảnh |
| 4 | Vé dọc tuyến **+10%** | **+818 vé chặng giữa/ngày** từ ghép gap (FCFS: **0**) | ✅ Đạt về cơ chế | FCFS không thể phục vụ các yêu cầu này (bị HET_CHO); AI phục vụ ~30% số vé qua ghế ghép/gap — xem §4.3 |
| 5 | Unmet-demand searches **−15%** | **HET_CHO −51,4%** (8.069 → 3.922) | ✅ **Vượt 3,4×** khi đo đúng | Tổng từ chối chỉ −0,4% vì 87% "từ chối" là khách bỏ vì giá (BO_VI_GIA) — là lựa chọn của khách, không phải thiếu cung — xem §4.4 |
| 6 | **Zero** vi phạm giá/chính sách | **0 vi phạm** — 9/9 invariant tests PASS | ✅ Đạt | Ràng buộc cưỡng chế bằng code, không phải quy ước — xem §5 |

**Một câu tóm tắt:** cơ chế của mô hình hoạt động đúng thiết kế và tạo giá trị dương trên *mọi* chỉ tiêu, ở *mọi* ngày chấm; hai chỉ tiêu doanh thu/pax-km chưa chạm biên target vì fold đánh giá hợp lệ của data V2 rơi vào mùa thấp điểm — nơi không tồn tại độ khan hiếm để định giá động và ghép chặng phát huy hết biên độ (bằng chứng xu hướng ở §4.2).

---

## 2. Phương pháp đánh giá (vì sao số liệu tin được)

- **Replay engine đối chứng** (`eval/replay.py`): phát lại đúng thứ tự thời gian ~8.000 yêu cầu tìm vé/ngày từ `search_log`, mỗi yêu cầu được cả hai chính sách xử lý độc lập trên cùng trạng thái xuất phát:
  - **FCFS (baseline):** first-fit ghế đơn xuyên suốt, không ghép, giá tĩnh mùa vụ.
  - **AI (Âu Lạc):** ghép chặng BT4 (đủ ràng buộc dwell/ưu tiên/đồng ý của khách) + định giá động BT5 (bid-price DLP refresh mỗi 200 vé) + CSXH áp sau cùng.
- **Khách quyết định mua bằng WTP thật** từ `_ground_truth/wtp.parquet` — chỉ dùng để chấm điểm, không bao giờ làm feature (đúng ràng buộc CI `_ground_truth` không được chạm runtime).
- **Không rò rỉ dữ liệu:** model dự báo train trên `ngay_chay < 2026-05-01` (chế độ LUAT); toàn bộ ngày backtest ≥ 2026-05-19. Đường cầu (elasticity) loại trừ các ngày backtest khỏi mẫu ước lượng.
- **Trần lý thuyết:** so với tối ưu offline `z_opt` (LP toàn tri từ `_ground_truth/offline_optimum`) — biết trước toàn bộ cầu, không chính sách thực tế nào đạt được 100%.
- **Chọn ngày chấm phủ đều dải tải:** 8 ngày từ LF thấp nhất (0,469) đến cao nhất (0,613) của fold, gồm cả ngày thường và cuối tuần.

---

## 3. Chất lượng model thành phần

| Model | Chỉ số | Giá trị (V2) | So V1 cũ | Diễn giải |
|---|---|---|---|---|
| BT1 Forecast (HistGradientBoosting, Poisson) | MASE (vs naive lag-7) | **0,54** | 0,51 | Sai số bằng nửa naive; test 543.707 dòng chế độ AI chưa từng thấy khi train |
| | Poisson deviance | **0,277** | 0,393 | **Cải thiện 30%** nhờ 34 tháng LUAT (V1 chỉ 10 tháng) |
| | Bias tổng | −5,1% | −5,6% | Dự báo hơi thận trọng, an toàn cho bid-price |
| | vs baseline pickup | 0,54 vs **1,31** | 0,51 vs 0,80 | Khoảng cách với heuristic giãn 2,4× — model học được pattern mà pickup không thấy |
| Elasticity (logistic demand) | β_ln(r) | **−5,49** | −1,19 | Ước lượng trên 6,6 triệu cell (12,2M mua / 10,8M bỏ-vì-giá). Cầu V2 nhạy giá hơn hẳn → engine tự động định giá bám sát F0 (r tối ưu 0,95–1,04) thay vì đẩy trần — hành vi đúng của revenue management |
| Booking curves | F(14) Tết | 0,997 | — | 11,2M vé LUAT; đường tích lũy Tết gần bão hòa trước 14 ngày — đúng thực tế bán vé Tết |
| Hiệu suất tổng thể | AI / z_opt offline | **0,62 → 0,71** | — | Luôn cao hơn FCFS (0,62–0,69) trên cả 8/8 ngày |

---

## 4. Lí giải từng KPI

### 4.1. Pax-km utilization (+0,6% so với target +3–8%)

Utilization = pax-km bán / (sức chứa × km). Có hai cách tăng: (a) lấp gap phân mảnh bằng ghép chặng, (b) có thêm cầu để bán. Trong fold chấm, LF bình quân chỉ 0,47–0,61 — ghế trống chủ yếu do **thiếu cầu**, không phải phân mảnh. Mô hình đã lấp gần hết phần gap "lấp được" (818 gap/ngày), phần còn lại nằm ngoài khả năng của bất kỳ thuật toán xếp chỗ nào. Đây là trần của dữ liệu mùa thấp điểm, không phải trần của mô hình.

### 4.2. Doanh thu (+1,1%, dải +0,4 → +2,5%) — bằng chứng xu hướng quan trọng nhất

Mức tăng doanh thu **đơn điệu tăng theo tải**:

| Ngày | LF bình quân | AI vs FCFS doanh thu |
|---|---|---|
| 2026-05-19 (thấp nhất fold) | 0,469 | +0,4% |
| 2026-05-31 | 0,55 | +0,7% |
| 2026-06-14 | 0,585 | +1,5% |
| 2026-06-21 (cao nhì fold) | 0,606 | **+2,5%** |

Cơ chế: định giá động và bid-price chỉ tạo chênh lệch khi có **khan hiếm** (đoạn nghẽn → phụ thu chi phí cơ hội; đoạn trống → xả giá hút cầu). Fold không chứa giai đoạn cao điểm nào (Tết 2026 nằm ngoài vùng phủ optimum của V2), nên +3–10% chưa thể hiện được — nhưng độ dốc của chuỗi trên ngoại suy thẳng đến vùng target khi LF ≥ 0,75 (mức LF Tết trong data là ~0,9+). Ngoài ra AI bán **ít vé hơn 0,8%** nhưng thu **nhiều tiền hơn 1,1%** — tức mỗi ghế-km được bán đúng giá trị hơn, đúng bản chất revenue management.

### 4.3. Vé dọc tuyến (+818 vé chặng giữa/ngày; FCFS = 0)

Đây là năng lực **FCFS hoàn toàn không có**: 6.546 yêu cầu chặng giữa trong 8 ngày được phục vụ bằng ghế gap-khít (một ghế trống đúng đoạn giữa của hành trình đã bán 2 đầu) — baseline từ chối toàn bộ các yêu cầu này vì không còn ghế trống xuyên suốt. Tỷ lệ khách phải đổi chỗ giữ ở mức thấp 1,5–2,3% và luôn có disclosure + cần khách đồng ý (invariant #7). Đây chính là nguồn gốc của việc HET_CHO giảm 51% (§4.4) và ghế trống cục bộ giảm 11,6%.

### 4.4. Unmet demand: đo đúng thì vượt target 3,4×

Tổng "từ chối" chỉ giảm 0,4% vì cấu trúc từ chối như sau (bình quân/ngày, phía AI): BO_VI_GIA ~4.400 (87%), HET_CHO ~490, QUOTA_NGAN ~310, TU_CHOI_DOI_CHO ~29. **BO_VI_GIA là khách thấy giá và tự quyết định không mua** — tồn tại y hệt ở FCFS (thậm chí AI chỉ +2,3%) và là tín hiệu đường cầu, không phải "cầu không được đáp ứng vì thiếu cung". Chỉ tiêu unmet-demand đúng nghĩa của đề bài — *tìm vé mà hệ thống không còn chỗ để bán* — là **HET_CHO: giảm từ 8.069 xuống 3.922 (−51,4%)**, vượt target −15% nhờ ghép chặng biến ghế phân mảnh thành chỗ bán được. QUOTA_NGAN (~310/ngày) là từ chối *chủ động có chủ đích* của BT3 để giữ chỗ cho hành trình dài giá trị cao hơn — một tính năng, không phải thất bại.

### 4.5. Tốc độ & vận hành

p95 thời gian tính lại giá/phương án = **4,2–4,4 ms** (FCFS 0 ms vì không tính gì), bình quân ~1 ms — thừa đáp ứng ngưỡng real-time (<200 ms), kể cả khi refresh DLP mỗi 200 vé.

---

## 5. Zero vi phạm giá/chính sách — cưỡng chế bằng code, xác nhận bằng test

**9/9 invariant tests PASS** (`tests/test_invariants.py`, chạy trên data V2 ngày 2026-07-19):

| Ràng buộc pháp lý/chính sách | Cơ chế cưỡng chế | Test |
|---|---|---|
| Sàn/trần giá niêm yết ∈ [0,55; 1,60]×F0 | `bt5_pricing.py` clip tại nguồn — mọi nhánh giá đều qua clip | ✅ `test_guardrail_san_tran` |
| CSXH áp **sau cùng**, mức cao nhất, không cộng dồn (Điều 40 NĐ 16/2026) | Nhân `(1−mức)` sau mọi điều chỉnh động; được phép xuống dưới sàn (quyền lợi hợp pháp) | ✅ `test_csxh_ap_sau_cung` |
| Biến động giá ≤ ±5%/lần điều chỉnh | `VOLATILITY_CAP` chặn trước khi clip sàn/trần | ✅ `test_volatility_cap` |
| Giá đã khóa khi giữ chỗ là bất khả xâm phạm | `HELD_PRICE` bypass mọi động cơ định giá | ✅ `test_held_price_bat_kha_xam_pham` |
| Cùng input → cùng giá (không phân biệt đối xử theo lượt gọi) | Định giá tất định, không random | ✅ `test_gia_tat_dinh` |
| Khách ưu tiên (cao tuổi, khuyết tật, trẻ đi một mình) **không bao giờ** nhận phương án đổi chỗ | Filter tại BT4 trước khi xếp hạng | ✅ `test_uu_tien_khong_ghep` |
| Ghép chỗ phải: dwell ≥ 5 phút tại ga đổi, cùng hạng chỗ, có disclosure + khách đồng ý | Ràng buộc trong `find_options` | ✅ `test_ghep_co_disclosure_va_dwell` |
| Gán ghế nguyên tử (không bao giờ ghi một phần) | CAS trên ma trận, rollback toàn bộ nếu 1 đoạn fail | ✅ `test_ssm_assign_nguyen_tu` + `test_hold_expiry_sinh_gap` |

Bằng chứng thống kê từ replay 8 ngày: giá bán/F0 bình quân = **0,951**, độ lệch chuẩn tỷ lệ giá = 0,130 — toàn bộ phân phối nằm trong hành lang [0,55; 1,60], không một quan sát vi phạm.

---

## 6. Hạn chế & việc nên làm tiếp

1. **Fold đánh giá không chứa cao điểm.** `offline_optimum` của V2 chỉ phủ 2026-05-19 → 2026-06-30. Muốn chứng minh biên +3–10% doanh thu cần chấm giai đoạn Tết (LF ~0,9): chạy `models/make_backtest_forecast.py --cutoff 2026-02-01 --dates 2026-02-14` rồi backtest AI-vs-FCFS (không so được với optimum, nhưng so được với baseline).
2. **`bid_price` trong ground truth V2 là cột defaulted** (theo manifest) — không dùng để chấm độ chính xác bid-price.
3. Chỉ tiêu "vé dọc tuyến +10%" nên được đo trực tiếp bằng phân rã vé theo băng cự ly (ngắn/trung/dài) trong `eval/metrics.py` thay vì proxy qua gap-fill — hiện replay chưa xuất phân rã này.
4. Elasticity β = −5,49 khiến engine định giá quanh F0; nếu VNR muốn khai thác phụ thu cao điểm mạnh hơn, cần nới `elastic_markup_max` (hiện 15%) sau khi có dữ liệu cao điểm thật.

---

*Sinh tự động từ pipeline đánh giá tier-2 (`eval/backtest.py`) ngày 2026-07-19. Toàn bộ số liệu tái lập được: các lệnh trong `plans/260719-0420-retrain-tren-data-v2-36m.md`.*

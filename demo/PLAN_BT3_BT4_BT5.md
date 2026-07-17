# KẾ HOẠCH XÂY DỰNG BT3 → BT4 → BT5

> Chốt ngày 17/07/2026, sau khi BT1 (forecast v1, MASE 0.505) và BT2 (Seat State Matrix) hoàn thành.
> Quyết định đã thống nhất: **BT3 làm cả heuristic lẫn DLP để so sánh · BT4 replay search_log · BT5 hybrid LF + bid price.**

---

## 0. Bối cảnh — pipeline đang đứt ở đâu?

5 bài toán con phụ thuộc nhau như sau (theo `Decompose.docx`):

```
BT1 Forecast ─────┐
                  ▼
BT2 SSM ────► BT3 Load + Quota ──► BT5 Pricing ◄── BT4 Merging ◄── BT2 SSM
                  (π_e, LF)            ▲                (phương án ghế)
                                       └── yêu cầu đặt vé mới
```

Hiện tại BT1 + BT2 đã xong, **BT3/4/5 chưa có dòng code nào** — demo chưa chạy được end-to-end.
Mục tiêu của plan này: hoàn thiện 3 bài còn lại, mỗi bài 1 module độc lập + output file làm bằng chứng,
cuối cùng chấm điểm bằng **RO score** so với luật AI thật của VNR (baseline B2).

**Tiêu chí thành công tổng thể** (doc 03 §8): *"Nếu B4 (giải pháp của mình) không vượt B2 (luật VNR),
bài dự thi chưa có giá trị gia tăng."*

---

## Giai đoạn 0 — Nối contract từ model v1 (nửa buổi)

**Việc:** xuất lại `demo/features/forecast_output_contract.csv` từ `demo/train_out/model_final.pkl`
(bản hiện tại đang là pickup heuristic cũ). Format giữ nguyên:

```csv
origin,dest,date,train_id,seat_class,forecast_demand
HAN,SGO,2026-05-20,SE1,K6,3.7
HAN,VIN,2026-05-20,SE1,NGOI,1.2
```

Đây là input chính thức của BT3. Không đổi format = không phải sửa gì ở downstream.

---

## Giai đoạn 1 — BT3: Segment Load Analysis + Quota (`demo/load_analysis/`)

### 1.1. Bài toán bằng lời

Một chuyến SE1 Hà Nội→Sài Gòn đi qua 23 đoạn (khu gian). **Một vé dài chiếm nhiều đoạn,
một vé ngắn chiếm ít đoạn, nhưng tất cả dùng chung một kho ghế.** Câu hỏi: nên để dành bao
nhiêu ghế cho khách đi dài (giá cao), bao nhiêu được phép bán cho khách đi ngắn (giá thấp)?
Bán bừa cho khách ngắn thì hết chỗ cho khách dài → mất doanh thu; giữ khư khư cho khách dài
mà họ không đến → ghế chạy rỗng.

### 1.2. Ví dụ tối giản (3 ga, 2 ghế) — hiểu DLP và bid price trong 2 phút

Tàu chạy `A → B → C`, có **2 ghế**, tức mỗi đoạn (A–B và B–C) có sức chứa 2.

Dự báo nhu cầu và giá vé:

| Sản phẩm (O–D) | Giá vé | Dự báo khách |
|---|---|---|
| A→C (dài, chiếm cả 2 đoạn) | 100k | 2 người |
| A→B (ngắn, chiếm đoạn 1)   | 40k  | 2 người |
| B→C (ngắn, chiếm đoạn 2)   | 30k  | 1 người |

Giải LP: `max 100k·y_AC + 40k·y_AB + 30k·y_BC` với ràng buộc từng đoạn ≤ 2 ghế:

- Đoạn A–B: `y_AC + y_AB ≤ 2`
- Đoạn B–C: `y_AC + y_BC ≤ 2`

Nghiệm tối ưu: **y_AC = 2, y_AB = 0, y_BC = 0** → doanh thu 200k.
(Nếu tham lam bán 2 vé A→B trước — ai đến trước bán trước — thì chỉ thu được 40+40+30 = 110k,
vì khách A→C đến sau hết chỗ. Đây chính là cái FCFS làm sai.)

**Bid price π_e** = giá trị đối ngẫu của ràng buộc mỗi đoạn = "bán thêm 1 chỗ trên đoạn này
thì mất bao nhiêu cơ hội". Ở ví dụ trên π_AB ≈ 70k, π_BC ≈ 30k (tổng = giá vé dài 100k).
Quy tắc vàng cho BT5 sau này: **chỉ bán vé (i,j) nếu giá ≥ Σ π_e của các đoạn nó chiếm.**
Ví dụ: khách hỏi vé A→B giá 40k < π_AB=70k → từ chối (giữ chỗ cho khách dài) — trừ khi
tàu sắp chạy mà ghế vẫn rỗng (lúc đó π giảm về ~0, bán giá nào cũng hơn ghế trống).

Vì ma trận "vé nào chiếm đoạn nào" là **totally unimodular** (các đoạn 1 vé chiếm luôn
liên tiếp nhau), LP tự cho nghiệm nguyên — không cần solver MILP nặng. `scipy linprog
(method="highs")` giải mỗi chuyến trong vài mili-giây.

### 1.3. Hai bản cài đặt (đã chốt: làm cả hai để so sánh)

| | `quota_heuristic.py` (baseline) | `quota_dlp.py` (bản chính) |
|---|---|---|
| Ý tưởng | Đoạn nào dự báo nghẽn → khóa X% ghế cho hành trình dài (X theo tỷ trọng dự báo) | LP như ví dụ 1.2, mỗi chuyến một bài |
| Input | forecast contract (BT1) | forecast contract + giá trung vị theo (O,D,lớp) từ transactions giai đoạn train |
| Output | quota theo (đoạn × băng dài/trung/ngắn) | quota **+ bid price π_e từng đoạn** |
| Dùng cho | so sánh, dashboard | BT5 (mỏ neo giá), so sánh |

### 1.4. File và contract output

```
demo/load_analysis/
├─ segment_load.py     # replay SSM 1 ngày → LF từng đoạn, top nghẽn/trống
├─ quota_heuristic.py
├─ quota_dlp.py
└─ out/
   ├─ segment_lf.parquet      # (chuyen_id, khu_gian_id) → lf
   ├─ quota.parquet           # (chuyen_id, khu_gian_id, band) → quota  [cả 2 bản, cột method]
   ├─ bid_price.parquet       # (chuyen_id, khu_gian_id) → pi_e         [chỉ DLP]
   └─ so_sanh_quota.txt       # heuristic vs DLP: doanh thu kỳ vọng, số ghế khóa
```

`segment_load.py` gần như có sẵn nguyên liệu: `SeatStateMatrix.load_factor()` (BT2) đã trả
vector LF theo đoạn — chỉ cần replay + xếp hạng.

---

## Giai đoạn 2 — BT4: Gap Merging (`demo/merging/`)

### 2.1. Bài toán bằng lời + ví dụ

Ghế 12 toa 5 của SE1 đã bán cho 2 khách: một người đi **Hà Nội→Vinh**, một người đi
**Đà Nẵng→Sài Gòn**. Vậy ghế này **trống từ Vinh đến Đà Nẵng** — một "gap". Giờ có khách
mới muốn đi **Vinh→Nha Trang**. Không ghế nào trống suốt Vinh→Nha Trang, bình thường sẽ
bị từ chối. Nhưng nếu chịu **đổi ghế 1 lần** thì đi được:

```
Ghế 12:  HN ████ Vinh ------------ ĐN ████████ SG      (---- = gap)
Ghế 34:  HN ██████████████████████ ĐN ---------- SG

Khách Vinh→Nha Trang:  ngồi ghế 12 (Vinh→ĐN)  →  đổi sang ghế 34 (ĐN→Nha Trang)
                                        ↑ đổi ghế tại ga Đà Nẵng
```

Đây chính là "ghép chặng" — nguồn cung của nó là các gap sinh ra do trả vé + do bán lệch chặng.

### 2.2. Thuật toán (doc 02 §5.3 đã chốt, không cần sáng tạo thêm)

Ba tầng phương án, trả về theo thứ tự ưu tiên:

1. **1 ghế suốt** — dùng `first_fit` có sẵn của SSM. Hết mới xuống tầng 2.
2. **1 ghế có gap ôm khít hành trình** — ưu tiên gap vừa nhất (ít lãng phí).
3. **Ghép nhiều ghế** — chọn dãy ghế phủ hành trình với **ít lần đổi nhất**: thuật toán
   greedy quét trái→phải, mỗi bước chọn gap vươn xa nhất về bên phải (min interval cover —
   toán đã chứng minh greedy là tối ưu, O(K log K)).

**Ràng buộc cứng** (vi phạm = loại phương án, không phải trừ điểm):
- Khách nhóm ưu tiên (người già, khuyết tật, CSXH...) → **chỉ nhận phương án M=1** (không bắt đổi ghế).
- Các mảnh ghép phải **cùng loại chỗ** (không nửa hành trình nằm K4, nửa ngồi mềm).
- Ga đổi phải đủ thời gian dừng. *Giả định khai báo rõ:* 24 ga trục trong dataset đều là ga
  chính (dwell ≥ 5 phút) → cho phép đổi tại mọi ga; dữ liệu chưa có dwell theo tàu.

Output mỗi phương án: `[(ghế, đoạn_từ, đoạn_đến)...]`, số lần đổi `M−1`, ga đổi.

### 2.3. Demo bằng gì? (đã chốt: replay search_log)

`search_log` có 16 triệu yêu cầu, trong đó các dòng `ket_qua ∈ {TU_CHOI_HET_CHO,
TU_CHOI_DOI_CHO}` là **khách bị từ chối thật**. Kịch bản demo:

1. Chọn ngày (vd. cao điểm + ngày thường), dựng SSM đúng trạng thái tại thời điểm mỗi yêu cầu
   (replay giao dịch theo thứ tự mua — cùng cơ chế `replay_date` của BT2).
2. Đẩy từng yêu cầu bị từ chối qua engine ghép chặng.
3. Báo cáo: **"X% yêu cầu bị từ chối lẽ ra cứu được"**, phân bố số lần đổi ghế, đoạn nào
   cứu được nhiều nhất → khớp thẳng mục tiêu đề bài *"tìm kiếm không thành −15%"*.

Kèm vài kịch bản tổng hợp nhỏ (như hình 2.1) làm unit test cho engine.

```
demo/merging/
├─ merge_engine.py      # 3 tầng phương án + ràng buộc cứng
├─ replay_rejected.py   # replay search_log → báo cáo % cứu được
├─ test_merge_engine.py # kịch bản tổng hợp nhỏ
└─ out/rescue_report.txt / rescue_detail.parquet
```

---

## Giai đoạn 3 — BT5: Dynamic Pricing (`demo/pricing/`)

### 3.1. Nguyên tắc kiến trúc

**Luật giá là config khai báo (`pricing_rules.yaml`), không phải code Python** — vì luật đổi
theo mùa, cần log chính sách + rollback, và bản ghi "luật nào đã bắn" chính là audit trail
kiêm lời giải thích XAI. Engine chỉ là trình thông dịch luật.

Tín hiệu đầu vào của luật (đã chốt hybrid): **LF đoạn (từ BT3) + Σπ_e bid price (từ BT3)
+ lead time + băng cự ly.** Dùng mỗi LF thì ta chỉ tái tạo được luật VNR (B2); thêm bid price
mới là chỗ tạo giá trị gia tăng (B4 > B2).

### 3.2. Ví dụ tính giá một vé — đi qua đủ 4 tầng

Khách 62 tuổi (được giảm người cao tuổi 15%) đồng thời là thương binh (giảm 30%),
mua vé chặng ngắn Huế→Đà Nẵng, tàu còn 10 ngày nữa chạy, đoạn này LF mới 35%:

```
Tầng 1  Giá niêm yết F0:                                     200.000 đ
Tầng 2  Luật động (YAML):
        - RULE ai_giam_chang_ngan: LF 35% < 40%, chặng ngắn,
          lead ≥ 7 ngày  → đề xuất giảm 30%          → 140.000 đ
        - RULE san_bid_price: Σπ_e các đoạn = 152.000 đ
          → 140k < 152k: nâng lên đúng sàn cơ hội    → 152.000 đ   ⭐ khác biệt vs luật VNR
Tầng 3  Clip sàn/trần pháp lý (vd sàn 50%, trần 150% F0):    152.000 đ (trong biên, giữ nguyên)
Tầng 4  CSXH — áp SAU CÙNG, lấy MAX không cộng dồn:
        max(30% thương binh, 15% cao tuổi) = 30%     → 106.400 đ
─────────────────────────────────────────────────────────────
Giá cuối: 106.400 đ
rule_ids: [AI_GIAM_CHANG_NGAN:0.30, SAN_BID_PRICE, CSXH_THUONG_BINH:0.30]
Giải thích: "Giảm 30% vì đoạn Huế–ĐN mới lấp 35%; chặn sàn theo chi phí cơ hội 152k;
             áp giảm thương binh 30% (mức cao nhất, không cộng dồn) theo Đ.40 NĐ 16/2026."
```

Sai thứ tự tầng 3↔4 hoặc cộng dồn 30%+15% = sai doanh thu **và** sai quyền lợi hành khách —
gate kiểm tra `số vi phạm = 0` là điều kiện cứng, không phải điểm trừ.

### 3.3. Chấm điểm — vì sao không chấm trên transactions tĩnh được?

Đổi giá thì hành vi mua đổi theo (khách thấy giá cao hơn WTP thì bỏ đi) — doanh thu trên
transactions cũ là vô nghĩa. Cách chấm đúng (doc 03 §9.2 Pha 1): **replay phản thực trên
ground truth**:

1. Lấy dòng yêu cầu + WTP thật của từng khách từ `_ground_truth/wtp.parquet`
   (ground truth được phép dùng ĐỂ CHẤM — chỉ cấm làm feature).
2. Với mỗi policy (B0 giá cố định / B2 luật VNR / B4 của mình): khách mua ⟺ giá ≤ WTP,
   cập nhật SSM, cộng doanh thu → ra Z_B0, Z_B2, Z_B4.
3. Quy về thang chuẩn bằng **RO (Revenue Opportunity)**, dùng Z_opt và Z_fcfs có sẵn trong
   `_ground_truth/offline_optimum.parquet`:

```
        Z_policy − Z_fcfs          ví dụ:  Z_fcfs=100 tỷ, Z_opt=120 tỷ
RO = ─────────────────────         B2 = 106 tỷ → RO = 0.30
        Z_opt − Z_fcfs             B4 = 110 tỷ → RO = 0.50  ✅ B4 > B2 là thành công
```

RO ∈ [0,1]: 0 = chẳng hơn gì bán kiểu ai-đến-trước-bán-trước; 1 = bằng nhà tiên tri biết
trước toàn bộ nhu cầu. Đây là "chỉ số vàng" vì không phụ thuộc quy mô hay mùa vụ.

```
demo/pricing/
├─ pricing_rules.yaml   # luật khai báo; khởi tạo THEO ĐÚNG luật VNR (doc 01 §3) rồi mới nới
├─ price_engine.py      # thông dịch luật: 4 tầng như ví dụ 3.2 + đếm vi phạm (phải = 0)
├─ evaluate_ro.py       # replay WTP → Z_B0/Z_B2/Z_B4 → bảng RO
└─ out/ro_report.txt / pricing_log.parquet
```

Lưu ý khởi tạo: B2 và B4 **chia sẻ cùng khung luật YAML** (B4 = B2 + biến bid price) —
so sánh mới công bằng, khác biệt đo được là do bid price chứ không do khung luật khác nhau.

---

## Giai đoạn 4 — Quay lại forecast v1.1 (sau khi pipeline chạy)

- Thêm feature "mức giảm giá đang áp trên O–D" (biết tại thời điểm dự báo, hợp lệ leakage)
  → mục tiêu thu hẹp bias −8% ở giai đoạn AI.
- Chuyển dự báo điểm → **dự báo phân phối** (quantile), phục vụ quota kiểu newsvendor
  `y* = F⁻¹(1 − f₂/f₁)` (doc 02 §10.1).
- Rolling-origin evaluation thay cho single split.

---

## Thứ tự thi công & nghiệm thu

| Bước | Việc | Bằng chứng nghiệm thu |
|---|---|---|
| 0 | Contract từ model pkl | `forecast_output_contract.csv` mới, so tổng dự báo vs bản pickup |
| 1 | BT3 | `segment_lf/quota/bid_price.parquet` + bảng so sánh heuristic vs DLP |
| 2 | BT4 | `rescue_report.txt`: % yêu cầu bị từ chối cứu được, unit test pass |
| 3 | BT5 | `ro_report.txt`: RO của B0/B2/B4, **B4 > B2**, vi phạm = 0 |
| 4 | v1.1 | MASE/bias mới vs v1, pinball loss các quantile |

Quy ước chung (giữ nguyên phong cách BT1/BT2): mỗi module 1 script chạy độc lập bằng
`.venv/bin/python`, tiếng Việt cho tên cột/khái niệm nghiệp vụ, tiền `int64` đồng,
mọi split theo `ngay_chay`, không bao giờ đụng `_ground_truth` ngoài script chấm điểm.

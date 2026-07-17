# CÁC BƯỚC VÀ KHUYẾN NGHỊ KỸ THUẬT ĐỂ TẠO DATASET ĐÚNG CHUẨN

**Đọc cùng:** Tài liệu 01 (số liệu thực) và Tài liệu 02 (mô hình toán). Tài liệu này là phần **thi công**.

---

## 0. Lộ trình 12 bước (tổng ~4–6 tuần cho nhóm 4 người)

| # | Bước | Đầu ra | Ước lượng |
|---|---|---|---|
| 1 | Thu thập dữ liệu tham chiếu thật (ga, lý trình, biểu đồ, biểu giá) | `ref/*.csv` | 4–5 ngày |
| 2 | Số hóa **bộ luật giá** thành cấu hình khai báo | `rules/pricing_rules.yaml` | 2–3 ngày |
| 3 | Dựng lịch âm/dương + lễ + sự kiện + đợt bán vé | `ref/calendar.csv` | 1–2 ngày |
| 4 | Dựng chuỗi thời tiết & quá trình gián đoạn | `ref/weather.parquet`, `ref/disruption.parquet` | 3 ngày |
| 5 | Hiệu chuẩn tham số cầu (SMM) | `config/params_fitted.yaml` | 5–7 ngày |
| 6 | Cài đặt bộ mô phỏng sự kiện rời rạc | `sim/` | 7–10 ngày |
| 7 | Sinh dataset `pilot` + `full` | `data/`, `_ground_truth/` | 1–2 ngày (máy) |
| 8 | Bộ kiểm định chất lượng dữ liệu (DQ + fidelity) | báo cáo `qa/` | 3 ngày |
| 9 | Feature store có as-of join, chống rò rỉ | `features/` | 3–4 ngày |
| 10 | Baselines (FCFS, DLP/bid-price, hindsight LP) | `baselines/` | 3 ngày |
| 11 | Giao thức backtest 3 pha + A/B | `eval/` | 3 ngày |
| 12 | Đóng gói, datasheet, hash, giấy phép | `DATASHEET.md` | 2 ngày |

> **Nguyên tắc thứ tự:** Bước 1–4 là **sự thật**, không được bịa. Bước 5–7 là **mô phỏng**, phải bị ràng buộc bởi Bước 1–4. Nhóm nào đảo thứ tự (viết simulator trước, tìm số liệu sau) sẽ phải viết lại.

---

## 1. Kiến trúc thư mục chuẩn

```
duongsat-ai/
├─ ref/                         # DỮ LIỆU THẬT — bất biến, có nguồn
│  ├─ ga.csv                    # station master (SCD-2 theo tỉnh)
│  ├─ khu_gian.csv
│  ├─ mac_tau.csv
│  ├─ lich_chay_mau.csv         # biểu đồ chạy tàu theo thời kỳ hiệu lực
│  ├─ thanh_phan_doan_tau.csv
│  ├─ bieu_gia_co_ban.csv       # cào từ dsvn.vn
│  ├─ calendar.csv              # dương + âm + lễ + đợt bán vé
│  ├─ su_kien.csv
│  └─ SOURCES.md                # ⭐ mỗi dòng ref phải truy vết được về 1 URL/văn bản
├─ rules/
│  ├─ pricing_rules.yaml        # bộ luật giá khai báo (không hard-code!)
│  └─ policy_constraints.yaml   # sàn/trần, CSXH, cấm feature nhạy cảm
├─ config/
│  ├─ params_prior.yaml
│  └─ params_fitted.yaml        # sau SMM
├─ sim/                         # bộ mô phỏng
├─ data/                        # ⭐ ĐẦU RA GIAO CHO MÔ HÌNH (observable)
├─ _ground_truth/               # ⭐ CHỈ DÙNG ĐỂ CHẤM ĐIỂM — không được đưa vào feature
├─ features/
├─ baselines/
├─ eval/
└─ qa/
```

**Quy tắc sắt:** không một dòng code huấn luyện nào được `import` từ `_ground_truth/`. Thực thi bằng CI: `grep -r "_ground_truth" src/ && exit 1`.

---

## 2. Bước 1 — Thu thập dữ liệu tham chiếu THẬT

### 2.1. Nguồn bắt buộc (theo thứ tự ưu tiên pháp lý)

| Loại | Nguồn ưu tiên 1 | Nguồn ưu tiên 2 |
|---|---|---|
| Ga, lý trình | **Công lệnh tốc độ / công lệnh tải trọng VNR**; `vr.com.vn` | Wikipedia (Ga Đà Nẵng: Km 791+400 — đã kiểm chứng chéo) |
| Biểu đồ chạy tàu | **dsvn.vn** (tra cứu giờ tàu), công bố biểu đồ của VNR | Thông cáo báo chí VNR/Traravico |
| Biểu giá | **dsvn.vn** — cào có hệ thống | Đại lý (chỉ để đối chiếu, **không dùng làm nguồn chính**) |
| Chính sách giá | **vr.com.vn**, `cophanvantaiduongsat.vn` | Báo Nhân Dân / Báo Xây dựng / PLO |
| Miễn giảm CSXH | **Nghị định 16/2026/NĐ-CP Điều 40**, Luật ĐS 95/2025/QH15 | NĐ 65/2018 (nền) |
| Lịch nghỉ lễ | **Thông báo Bộ Nội vụ** (TB 9441/TB-BNV ngày 16/10/2025; CV 3383/BNV-CVL ngày 10/4/2026) | Báo chí |
| Thiên tai | **Quyết định công bố tình huống khẩn cấp của Bộ Xây dựng**; VNR | Báo Chính phủ |
| Dân số/du lịch | **Cục Thống kê**, Cục Du lịch Quốc gia | – |

### 2.2. Kỹ thuật cào biểu giá dsvn.vn — làm cho ĐÚNG

```
Thiết kế lưới truy vấn (query grid), KHÔNG cào mù:
  ga_đi   ∈ {22 ga chính}          (không cần 184 ga)
  ga_đến  ∈ {22 ga chính}, ga_đến > ga_đi
  ngày    ∈ {mẫu phân tầng: 2 ngày thường/tuần × 12 tuần
             + toàn bộ cao điểm Tết + 30/4 + hè}
  mác tàu ∈ {SE1..SE10, SE19/20, SE21/22, NA1/2, SNT1/2, HP/LP, SP}
⇒ ~231 O–D × ~60 ngày × ~14 mác ≈ 194k truy vấn — quá nhiều.

Rút gọn thông minh: giá cơ bản KHÔNG phụ thuộc ngày (chỉ δ phụ thuộc ngày).
⇒ Tách 2 pha:
  Pha A (biểu giá gốc): 231 O–D × 14 mác × 8 loại chỗ, 1 ngày thấp điểm
        ⇒ ~26k điểm giá ⇒ fit ln F = ln κ + θ ln d + α_t + γ_c   (Tài liệu 02, §7.1)
  Pha B (kiểm chứng δ): ~30 cặp O–D "thăm dò" nằm hai bên NGƯỠNG 300/400/600/900/1000 km,
        quan trắc mỗi ngày trong 90 ngày ⇒ dựng đường cong giá theo lead time
        ⇒ đo trực tiếp δ_lead và δ_AI. ⭐ Đây là dữ liệu VÀNG cho RDD (Tài liệu 02, §7.4).
```

**Đạo đức & kỹ thuật:** tôn trọng `robots.txt`, giới hạn ≤ 1 req/s, có `User-Agent` định danh nhóm + email, **cache tại chỗ**, không đặt vé thật, không dựng tài khoản giả. Ghi rõ trong DATASHEET rằng dữ liệu giá là **công khai, không chứa dữ liệu cá nhân**.

**Cấu trúc lưu:** `bieu_gia_co_ban.csv` với `(mac_tau, ga_di, ga_den, loai_cho, gia_goc, ngay_quan_trac, nguon_url, hieu_luc_tu, hieu_luc_den)` — **SCD Type-2**, vì giá đổi 5–10% giữa các mùa.

### 2.3. Xử lý sáp nhập tỉnh (bẫy #7)

```
ga.csv:
  ga_id, ten_ga, ly_trinh_km, loai_ga, so_duong_don_tien,
  tinh_id, hieu_luc_tu, hieu_luc_den, la_ban_ghi_hien_hanh
```
Ga Tuy Hòa có **2 bản ghi**: (`tinh='Phú Yên'`, hiệu lực → 30/6/2025) và (`tinh='Đắk Lắk'`, hiệu lực 1/7/2025 →). Mọi join với dữ liệu dân số/du lịch **phải là as-of join theo ngày**, không phải join khóa đơn.

---

## 3. Bước 2 — Số hóa bộ luật giá thành CẤU HÌNH KHAI BÁO

**Không hard-code luật giá trong Python.** Lý do: (i) luật đổi mỗi mùa (Tết/hè/sau hè); (ii) đề bài yêu cầu **log thay đổi chính sách** và **rollback**; (iii) chỉ có cấu hình khai báo mới cho phép **audit trail** đúng nghĩa.

```yaml
# rules/pricing_rules.yaml  (trích)
- rule_id: R_HE2026_XA_NGAY
  ten: "Mua xa ngày >=20 ngày, chặng dài, hè 2026"
  hieu_luc: {tu: 2026-05-15, den: 2026-08-16}
  dieu_kien:
    - {field: lead_time_days, op: ">=", value: 20}
    - {field: mac_tau, op: "in", value: [SE1,SE2,...,SE12], and_: {field: cu_ly_km, op: ">=", value: 900}}
    - {field: mac_tau, op: "in", value: [SE21,SE22], and_: {field: cu_ly_km, op: ">=", value: 600}}
    - {field: mac_tau, op: "in", value: [SE29,SE30], and_: {field: cu_ly_km, op: ">=", value: 400}}
    - {field: mac_tau, op: "in", value: [SNT1,SNT2], and_: {field: cu_ly_km, op: ">=", value: 300}}
  loai_tru:
    - {mac_tau: SE3,   loai_cho: NAM_K4}
    - {mac_tau: [SNT1,SNT2,SPT1,SPT2], loai_cho: NAM_K4}
  tac_dong: {kieu: "nhan", he_so_min: 0.90, he_so_max: 0.95}
  han_muc:  {don_vi: "ve", pham_vi: "chuyen_x_loai_cho", so_luong: 20}   # ⭐ 20 vé/loại chỗ/đoàn tàu
  nguon: "https://plo.vn/mo-ban-ve-tau-he-2026-...-post903784.html"

- rule_id: R_CSXH_ME_VNAH
  hieu_luc: {tu: 2026-01-14, den: null}
  can_cu_phap_ly: "Điều 40 Nghị định 16/2026/NĐ-CP"
  dieu_kien: [{field: doi_tuong, op: "==", value: "ME_VN_ANH_HUNG"}]
  tac_dong: {kieu: "giam_phan_tram", value: 0.90}
  hop_thanh: "MAX_KHONG_CONG_DON"     # ⭐
  ap_dung_sau: ["*"]                  # ⭐ áp SAU mọi δ động
  bat_buoc: true                      # ⭐ ràng buộc cứng, không được tối ưu bỏ qua

- rule_id: R_AI_GIA_LINH_HOAT
  hieu_luc: {tu: 2026-05-01, den: null}
  che_do: "AI"
  dieu_kien:
    - {field: max_lf_khu_gian, op: ">=", value: 0.60}
    - {field: min_lf_tren_hanh_trinh, op: "<=", value: 0.50}
    - {field: lead_time_days, op: "<=", value: 14}
  tac_dong:
    kieu: "giam_phan_tram_theo_tuyen"
    bien_do: {min: 0.15, max: 0.35}
    tran_theo_tuyen: {HUE_DANANG: 0.30, HN_HP: 0.25, HN_LC: 0.25, HN_DN: 0.25, SG_NT: 0.25, THONG_NHAT_NGAN: 0.35}
  hien_thi: {mau: "xanh_nhat", hien_muc_giam: true}
  nguon: "https://anninhthudo.vn/duong-sat-ap-dung-ai-ban-ve-tau-...-post647666.antd"
```

**Bộ máy thực thi (rule engine)** phải xuất ra, cho **mỗi lần định giá**, một bản ghi:
```
{gia_goc, [rule_id đã bắn, hệ số, thứ tự áp dụng], gia_niem_yet, gia_cuoi,
 rang_buoc_cham: [SAN|TRAN|HAN_MUC_20VE], che_do_gia, phien_ban_quy_tac_hash}
```
⇒ Đây **chính là "nhật ký quyết định/phê duyệt"** mà Mục 9 & 15 đề bài yêu cầu, và cũng là thứ cho phép **XAI thật** (giải thích = liệt kê luật đã bắn), không cần SHAP.

---

## 4. Bước 3–4 — Lịch, thời tiết, gián đoạn

### 4.1. Lịch

```python
# Dùng thư viện âm lịch, KHÔNG tự tính
# pip install lunardate  (hoặc lunarcalendar)
from lunardate import LunarDate
tet = {y: LunarDate(y,1,1).toSolarDate() for y in range(2023, 2028)}
# Kiểm tra bắt buộc: tet[2026] == date(2026,2,17)  # ⭐ 28 Chạp = 15/2 theo công bố VNR
```

`calendar.csv` phải có tối thiểu:
`ngay, thu, am_lich_ngay, am_lich_thang, tau_tet (=ngay - mung1), la_le, ten_le, so_ngay_nghi_lien_tuc, khoang_cach_toi_le_gan_nhat, dot_ban_ve, ngay_mo_ban, H_horizon, la_cao_diem, che_do_gia`

**Các mốc bắt buộc có mặt:**
`2025-09-20` (mở bán Tết), `2026-01-01` (Luật ĐS), `2026-01-19..23` (Đại hội XIV), `2026-02-03..2026-03-08` (cao điểm Tết), `2026-02-14..22` (nghỉ Tết), `2026-02-17` (mùng 1), `2026-02-23..27` (giảm 40% giường nằm SE chẵn), `2026-04-25..27` (Giỗ Tổ), `2026-04-30..05-03`, `2026-05-01` (AI giá linh hoạt), `2026-05-15` (đổi/trả vé online + biểu đồ mới), `2026-05-15..08-16` (cao điểm hè), `2026-07-01..08-16` (giảm 10% nhiên liệu), `2026-07-15` (thu phí cao tốc BN), `2026-08-17..12-30` (sau hè), `2026-09-01..02` (Quốc khánh).

### 4.2. Thời tiết — dùng dữ liệu THẬT, đừng bịa

**Khuyến nghị mạnh:** dùng **ERA5 reanalysis** (Copernicus/CDS, miễn phí, có API) hoặc **Open-Meteo Historical API** (miễn phí, không cần key) để lấy chuỗi ngày cho ~15 điểm dọc tuyến (trùng lý trình các ga chính): `t2m_max, t2m_min, precip_mm, wind_gust, rh`.
→ Điều này biến "mô phỏng thời tiết" thành **dữ liệu thật gắn với lý trình thật** — mạnh hơn nhiều so với sinh ngẫu nhiên và **kiểm chứng được** bởi giám khảo.

Sau đó ánh xạ ga → khu gian bằng nội suy tuyến tính theo lý trình.

### 4.3. Gián đoạn

Hai lớp:
1. **Sự kiện lịch sử THẬT (hard-coded, không mô phỏng):** đợt 6–22/11/2025 với các đoạn Km1123+600–1139+100, Km1204+200–1219+742, Km1337+900–1339+850; chuyển tải Tuy Hòa↔Giã từ 23/11; 44 tàu dừng; 39.000 vé hoàn. Sự cố hầm Bãi Gió/Chí Thạnh 2024 (>20 ngày).
2. **Sự kiện mô phỏng (cho các năm/kịch bản khác):** NHPP theo Tài liệu 02, §8.2, hiệu chuẩn sao cho **kỳ vọng số chuyến hủy/năm ≈ 300** và **khách chuyển tải/năm ≈ 8.500**.

**Liên kết với thời tiết:** $\Pr(\text{gián đoạn}_e \mid \text{mưa 3 ngày} > \text{ngưỡng}) $ — dùng logistic trên lượng mưa tích lũy 72h tại lý trình đó. Điều này làm chuỗi thời tiết trở nên **có tác dụng**, không phải trang trí.

---

## 5. Bước 6–7 — Bộ mô phỏng & lược đồ dữ liệu

### 5.1. Kiến trúc mô phỏng: Discrete-Event Simulation

```
Hàng đợi sự kiện ưu tiên theo thời gian thực t (không phải theo u):
  [REQUEST(r, ω, c, g)]        ← NHPP thinning (Lewis–Shedler)
  [CANCEL(ticket_id)]          ← hazard
  [SALE_WINDOW_OPEN(đợt)]
  [PRICE_REFRESH(r)]           ← mỗi 15 phút hoặc mỗi K sự kiện
  [DISRUPTION_START/END(e_range)]
  [WAITLIST_MATCH]
  [DEPARTURE(r)]               ← chốt sổ, tính LF, PKU, ghế rỗng
```

**Sinh NHPP đúng cách — dùng thinning, không dùng "chia bin rồi Poisson từng bin":**
```python
# Lewis & Shedler (1979)
def nhpp_thinning(lam_func, T, lam_max, rng):
    t, out = 0.0, []
    while True:
        t -= math.log(rng.random()) / lam_max      # bước Poisson thuần nhất
        if t > T: return out
        if rng.random() <= lam_func(t) / lam_max:  # chấp nhận/loại bỏ
            out.append(t)
```
Chia bin sẽ **triệt tiêu cấu trúc đuôi** ở giai đoạn cận ngày (nơi mọi chuyện thú vị xảy ra).

**Reproducibility:** một `PCG64` **riêng cho từng chuyến** với seed dẫn xuất: `seed_r = hash(master_seed, train_code, date)`. Nhờ đó (i) chạy song song được, (ii) **common random numbers** khi so sánh 2 chính sách ⇒ giảm phương sai ước lượng chênh lệch doanh thu **cực mạnh** (đây là mẹo đánh giá A/B tốt nhất trong mô phỏng).

### 5.2. Lược đồ dữ liệu (DDL rút gọn)

```sql
-- ================= REF =================
CREATE TABLE ga (
  ga_id            TEXT, ten_ga TEXT, ly_trinh_km NUMERIC(8,3),
  loai_ga          TEXT,        -- ga_chinh | ga_khu_doan | ga_doc_duong
  thoi_gian_dung_mac_dinh_phut INT,
  tinh_id          TEXT, hieu_luc_tu DATE, hieu_luc_den DATE,   -- SCD-2
  PRIMARY KEY (ga_id, hieu_luc_tu)
);

CREATE TABLE khu_gian (
  khu_gian_id INT PRIMARY KEY, ga_dau TEXT, ga_cuoi TEXT,
  km_dau NUMERIC(8,3), km_cuoi NUMERIC(8,3), chieu_dai_km NUMERIC(8,3),
  vung_thien_tai TEXT      -- BAC | BAC_TRUNG | TRUNG_TRUNG | NAM_TRUNG | NAM
);

CREATE TABLE chuyen_tau (               -- train-run, grain = 1 chuyến
  chuyen_id TEXT PRIMARY KEY, mac_tau TEXT, ngay_chay DATE,
  chieu TEXT,                            -- LE | CHAN     ⭐
  gio_xuat_phat TIMESTAMP, tap_ga_dung TEXT[],  -- thứ tự lý trình
  bieu_do_hieu_luc_tu DATE, trang_thai TEXT      -- BINH_THUONG | HUY | CHAY_CUT
);

CREATE TABLE cho (                      -- grain = 1 chỗ vật lý trên 1 chuyến
  chuyen_id TEXT, toa_so INT, khoang_so INT, cho_so INT, tang INT,
  loai_cho TEXT,   -- NGOI_MEM_DH | NAM_K6_T1..T3 | NAM_K4_T1..T2 | VIP
  PRIMARY KEY (chuyen_id, toa_so, cho_so)
);

-- ================= OBSERVABLE =================
CREATE TABLE yeu_cau_tim_kiem (         -- ⭐⭐ BẢNG QUAN TRỌNG NHẤT
  yeu_cau_id BIGINT PRIMARY KEY,
  thoi_diem TIMESTAMP,                  -- thời gian thực
  ngay_di_mong_muon DATE, ga_di TEXT, ga_den TEXT,
  so_khach INT, co_tre_em BOOL, co_nguoi_cao_tuoi BOOL,
  kenh TEXT,                            -- WEB|APP|VI|GA|DAI_LY
  linh_hoat_ngay INT, linh_hoat_loai_cho BOOL, chap_nhan_doi_cho BOOL,
  ket_qua TEXT,                         -- MUA | TU_CHOI_HET_CHO | BO_VI_GIA | BO_KHAC | VAO_HANG_CHO
  chuyen_id_da_chon TEXT, ly_do_that_bai TEXT
);

CREATE TABLE giao_dich_ve (
  ve_id BIGINT PRIMARY KEY, yeu_cau_id BIGINT,
  thoi_diem_mua TIMESTAMP, lead_time_ngay NUMERIC(6,2),
  chuyen_id TEXT, ga_di TEXT, ga_den TEXT,
  ki_hieu_khu_gian_dau INT, ki_hieu_khu_gian_cuoi INT,   -- (i, j] — denormalize để join nhanh
  cu_ly_km NUMERIC(8,3),
  toa_so INT, cho_so INT, loai_cho TEXT,
  gia_goc BIGINT, gia_niem_yet BIGINT, gia_cuoi BIGINT,
  doi_tuong_giam TEXT, muc_giam_csxh NUMERIC(4,3),
  rule_ids_ap_dung TEXT[], che_do_gia TEXT,     -- LUAT | AI      ⭐
  nhom_id TEXT, so_lan_doi_cho INT,             -- M-1
  trang_thai TEXT                                -- HIEU_LUC | DA_TRA | DA_DOI | BI_HUY_DO_THIEN_TAI
);

CREATE TABLE trang_thai_ton_kho (       -- snapshot, grain = (chuyến, khu gian, loại chỗ, mốc thời gian)
  chuyen_id TEXT, khu_gian_id INT, loai_cho TEXT, thoi_diem TIMESTAMP,
  suc_chua INT, da_ban INT, dang_giu INT, con_trong INT,
  he_so_su_dung NUMERIC(5,4),
  PRIMARY KEY (chuyen_id, khu_gian_id, loai_cho, thoi_diem)
);

CREATE TABLE quyet_dinh_ai (            -- nhật ký quyết định & phê duyệt  ⭐ Mục 9,15 đề bài
  qd_id BIGINT PRIMARY KEY, thoi_diem TIMESTAMP, chuyen_id TEXT,
  loai TEXT,           -- QUOTA | GIA | NHA_CHO | GHEP_CHANG | XEP_NHOM
  dau_vao JSONB, dau_ra JSONB,
  bid_price NUMERIC[],                  -- π_e
  ly_do TEXT,          -- RULE:<id> | MODEL:<ver> | EXPLORE | MANUAL_OVERRIDE   ⭐
  nguoi_phe_duyet TEXT, trang_thai_phe_duyet TEXT,
  phien_ban_mo_hinh TEXT, hash_cau_hinh TEXT, co_the_rollback BOOL
);

CREATE TABLE hang_cho (...);  CREATE TABLE tra_ve (...);
CREATE TABLE gian_doan (su_kien_id, tu, den, khu_gian_dau, khu_gian_cuoi, muc_do, ga_chuyen_tai_1, ga_chuyen_tai_2, nguon);
CREATE TABLE thoi_tiet (ngay, ly_trinh_km, t2m_max, mua_mm, mua_tich_luy_72h, gio_giat, nguon);
CREATE TABLE su_kien (su_kien_id, ten, tu, den, tap_ga[], cuong_do);

-- ================= GROUND TRUTH (KHÔNG giao cho mô hình) =================
CREATE TABLE gt_cau_tiem_an (chuyen_id, ga_di, ga_den, loai_cho, lambda_thuc NUMERIC);
CREATE TABLE gt_wtp        (yeu_cau_id, wtp BIGINT, phan_khuc TEXT);
CREATE TABLE gt_toi_uu_offline (chuyen_id, z_opt BIGINT, z_fcfs BIGINT, phuong_an JSONB);
```

### 5.3. ⭐ Privacy-by-design cho định giá (ràng buộc kiểm chứng được)

Đề bài: *"không định giá theo dữ liệu cá nhân nhạy cảm, không tăng giá do tìm kiếm lặp lại"*. Cách biến điều này từ lời hứa thành **bằng chứng**:

```sql
-- View DUY NHẤT mà rule engine + model pricing được phép đọc
CREATE VIEW pricing_features AS
SELECT chuyen_id, khu_gian_id, loai_cho, lead_time_ngay, cu_ly_km,
       he_so_su_dung_khu_gian, toc_do_ban, du_bao_cau, ngay_le, mua_vu, mac_tau
FROM  ...;
-- ⚠️ KHÔNG có: user_id, so_lan_tim_kiem, thiet_bi, ip, gioi_tinh, tuoi, lich_su_mua
```
Cộng thêm test tự động:
```python
FORBIDDEN = {"user_id","so_lan_tim_kiem","thiet_bi","ip","gioi_tinh","tuoi","lich_su_mua","dia_chi"}
def test_pricing_features_clean():
    assert FORBIDDEN.isdisjoint(set(pricing_model.feature_names_in_))
def test_price_invariant_to_search_count():
    # cùng trạng thái, đổi số lần tìm kiếm 1→50 ⇒ giá KHÔNG đổi
    assert price(state, searches=1) == price(state, searches=50)
def test_price_locked_after_hold():
    assert price_at_payment(hold_id) == price_at_hold(hold_id)
```
⇒ Ba test này nên được **đưa thẳng vào slide dự thi**. Nó chứng minh "tuân thủ" bằng kỹ thuật, không bằng lời.

### 5.4. Định dạng & hiệu năng

- **Parquet + partition theo `ngay_chay` (và `mac_tau` nếu `full`)**, nén ZSTD. Không dùng CSV cho bảng lớn.
- **DuckDB** cho phân tích cục bộ (đọc parquet trực tiếp, không cần server) — phù hợp quy mô 8–60 triệu dòng trên laptop.
- Kiểu dữ liệu: tiền = `BIGINT` (đồng, **không dùng float** — sai số làm hỏng kiểm toán sàn/trần); thời gian = `TIMESTAMP` có timezone `Asia/Ho_Chi_Minh`; lý trình = `NUMERIC`, không float.
- Kích thước ước tính: `pilot` ~3–6 GB; `full` ~25–40 GB.

---

## 6. Bước 8 — Kiểm định chất lượng dữ liệu (bắt buộc, có ngưỡng)

### 6.1. Tầng 1 — Tính toàn vẹn (phải PASS 100%, nếu không thì dataset sai)

| Kiểm tra | Biểu thức | Ngưỡng |
|---|---|---|
| Bảo toàn sức chứa | $\forall e,c$: `da_ban + dang_giu ≤ suc_chua` | 0 vi phạm |
| Không chồng lấn chỗ | $\forall k$: các khoảng trong $\Pi_k$ rời nhau | 0 vi phạm |
| Nhất quán khoảng ↔ ga | `khu_gian_cuoi - khu_gian_dau + 1` = số khu gian giữa `ga_di`,`ga_den` | 0 vi phạm |
| Cộng tính phân cấp | $x_e = \sum_\omega A_{e\omega} q_\omega$ | sai lệch = 0 |
| Sàn/trần giá | $\underline F \le$ `gia_cuoi` $\le \overline F$ | **0 vi phạm** |
| CSXH | mọi đối tượng CSXH được đúng mức `max` | **0 vi phạm** |
| Không cộng dồn | mỗi vé ≤ 1 ưu đãi CSXH | 0 vi phạm |
| Nhân quả thời gian | `thoi_diem_mua < gio_xuat_phat`; `thoi_diem_tra ≥ thoi_diem_mua`; `thoi_diem_tra ≤ gio_xuat_phat - 24h` (cá nhân) | 0 vi phạm |
| Khóa & trùng lặp | PK duy nhất; FK toàn vẹn | 0 |
| Ưu tiên không đổi chỗ | `so_lan_doi_cho > 0` ⇒ tại thời điểm đó **không** còn chỗ liên tục nào | 0 vi phạm |
| Đối tượng ưu tiên | người cao tuổi/khuyết tật/trẻ đi một mình ⇒ `so_lan_doi_cho = 0` | **0 vi phạm** |

### 6.2. Tầng 2 — Độ trung thực thống kê (fidelity)

| Kiểm tra | Phương pháp | Ngưỡng gợi ý |
|---|---|---|
| Khớp mô men M1–M18 | sai số tương đối | **< 5%** cho M1–M9; < 15% cho phần còn lại |
| Phân phối cự ly vé | KS test mô phỏng vs. tham chiếu | $p > 0{,}05$ hoặc KS < 0,05 |
| Đường cong đặt chỗ | so sánh $\mathbb{E}[u]$ theo băng cự ly | lệch < 15% |
| Tính chu kỳ tuần | mật độ phổ (periodogram) có đỉnh tại $f = 1/7$ | có, nổi bật |
| Phân tán (dispersion) | $\hat\phi = \frac{1}{n-p}\sum \frac{(q-\hat\mu)^2}{\hat\mu}$ | 0,8 – 3,0 (Poisson/NB hợp lý) |
| Tự tương quan phần dư | Ljung–Box trên chuỗi ngày | không bác bỏ ở lag ≤ 14 |
| Tương quan chéo O–D | so sánh ma trận tương quan | Frobenius chuẩn hóa < 0,2 |
| **Hoàn vé bình quân khi thiên tai > giá vé bình quân** | 615k vs 514k | **tỷ số ∈ [1,1; 1,4]** ⭐ |
| **Giá BQ Tết / giá BQ năm** | 1,39; và phân rã: giá ≤ 1,05, mix ≥ 1,32 | ⭐ **bắt buộc** |
| Hệ số sử dụng chỗ | 79% (tuần 22–29/4/2026) | ±3 điểm % |

### 6.3. Tầng 3 — Chống rò rỉ (leakage)

```python
# Quy tắc vàng: MỌI feature phải có cột `thoi_diem_biet` (knowledge time)
# và as-of join phải dùng: feature.thoi_diem_biet <= label.thoi_diem_du_bao
FORBIDDEN_AS_FEATURE = {
  "he_so_su_dung_cuoi_cung",   # biết sau khi tàu chạy
  "tong_ve_ban_cua_chuyen",    # nt
  "z_opt", "z_fcfs",           # ground truth
  "lambda_thuc",               # ground truth
  "co_bi_huy_do_thien_tai",    # biết sau
  "so_ve_tra_cuoi_cung",
}
```
**Test rò rỉ bằng đối kháng (adversarial validation):** huấn luyện một bộ phân loại `train vs test`; nếu AUC > 0,65 ⇒ có rò rỉ hoặc dịch chuyển phân phối nghiêm trọng ⇒ điều tra.
**Test rò rỉ bằng hoán vị thời gian:** xáo trộn nhãn theo thời gian; nếu điểm số chỉ giảm nhẹ ⇒ mô hình đang đọc trộm tương lai.

---

## 7. Bước 9 — Feature store & thiết kế đặc trưng

### 7.1. Nhóm đặc trưng đề xuất (grain: `(chuyen_id, ga_di, ga_den, loai_cho, thoi_diem_du_bao)`)

| Nhóm | Đặc trưng |
|---|---|
| Cấu trúc | `cu_ly_km`, `so_khu_gian_phu`, `mac_tau`, `chieu`, `loai_cho`, `tang`, `gio_xuat_phat_bin` |
| Lịch | `tau_tet`, `dow`, `la_le`, `khoang_cach_toi_le`, `Fourier(doy, K=6)`, `Fourier(tau_tet, K=4)`, `dot_ban_ve`, `H_horizon` |
| Đặt chỗ | `lead_time`, `z = 1 - u/H`, `da_ban_luy_ke`, `toc_do_ban_7ngay`, `da_ban / du_bao_tai_u` |
| Tồn kho | `min_lf_tren_hanh_trinh`, `max_lf_tren_hanh_trinh`, `lf_nut_co_chai`, `so_cho_lien_tuc_con`, `so_gap_ghep_duoc`, `bid_price_hien_tai` ⭐ |
| Giá | `gia_niem_yet`, `gia/gia_goc`, `gia_doi_thu_bay`, `gia_doi_thu_bo`, `gia_xang_dau` |
| Cạnh tranh nội bộ | `so_cho_con_cua_tau_khac_cung_ngay_cung_OD` ⭐ |
| Ngoại sinh | `mua_tich_luy_72h_tren_hanh_trinh`, `t2m_max_ga_den`, `co_su_kien_ga_den`, `co_gian_doan_tren_hanh_trinh` |
| Trễ | `q_lag_364` (cùng ngày năm ngoái theo **âm lịch**, không phải dương lịch!) ⭐, `q_lag_7`, `rolling_mean_28` |
| Chế độ | `che_do_gia` (LUAT/AI), `sau_15_5_2026` (trả vé online) |

**`bid_price_hien_tai` là đặc trưng mạnh nhất và ít nhóm nghĩ ra**: nó tóm tắt toàn bộ trạng thái tương lai của tuyến thành một con số/khu gian, và có nền tảng lý thuyết (đối ngẫu LP).

### 7.2. Hai kỹ thuật bắt buộc

1. **Unconstraining (giải kiểm duyệt cầu).** Vé bán $= \min(D, \text{chỗ còn})$. Với các chuyến "cháy vé", ta chỉ quan sát **cận dưới** của cầu. Dùng **EM cho dữ liệu bị kiểm duyệt**:
   $$\hat\Lambda^{(k+1)} = \frac{1}{n}\Big[\sum_{i \notin \mathcal{C}} q_i + \sum_{i \in \mathcal{C}} \mathbb{E}\big[D \mid D \ge q_i;\ \hat\Lambda^{(k)}\big]\Big]$$
   ($\mathcal{C}$ = tập chuyến bị kiểm duyệt). **Ưu thế của dataset mô phỏng: bạn có $\Lambda$ thật ở `_ground_truth/` ⇒ đo được sai số unconstraining** — điều không hãng nào làm được với dữ liệu thật. **Hãy biến điều này thành một mục riêng trong báo cáo dự thi.**
2. **Hòa giải phân cấp MinT** (Tài liệu 02, §10.2) — chạy sau khi dự báo, trước khi tối ưu.

---

## 8. Bước 10 — Baselines bắt buộc (không có = không đánh giá được gì)

| Baseline | Mô tả | Vai trò |
|---|---|---|
| **B0 — FCFS + biểu giá cố định** | Ai đến trước phục vụ trước, không quota, giá theo biểu | **Cận dưới**; mô phỏng "luật cố định" hiện tại |
| **B1 — Quota tĩnh theo luật** | Giữ chỗ cứng cho ga trung gian theo tỷ lệ cố định | Thực trạng VNR trước 1/5/2026 |
| **B2 — Luật "AI Giá vé linh hoạt" của VNR** | Giảm 15–35% chặng ngắn khi $\max_e \mathrm{LF} \ge \varrho$ | **Đối thủ thực tế phải vượt** ⭐ |
| **B3 — DLP + bid price (tái tối ưu)** | Tài liệu 02, §5.1 | Chuẩn học thuật |
| **B4 — DLP + dự báo ML (nhóm)** | Thay $\mathbb{E}[D]$ bằng dự báo của nhóm | **Đóng góp của nhóm** |
| **B5 — Hindsight LP** | Biết trước toàn bộ yêu cầu | **Cận trên $Z^{\text{opt}}$** |

Báo cáo $\mathrm{RO} = \frac{Z-Z_{B0}}{Z_{B5}-Z_{B0}}$ cho B1..B4. **Nếu B4 không vượt B2, bài dự thi chưa có giá trị gia tăng** — hãy biết điều này sớm, không phải trước hôm nộp.

---

## 9. Bước 11 — Giao thức đánh giá (bám đúng 3 pha của đề bài)

### 9.1. Chia dữ liệu — theo THỜI GIAN, không bao giờ ngẫu nhiên

```
Train:      2024-01-01 → 2025-12-31
Validation: 2026-01-01 → 2026-04-30      # ⭐ chế độ LUAT (trước AI)
Test-A:     2026-05-01 → 2026-08-16      # ⭐ chế độ AI  → đo tính bền vững khi ĐỔI CHẾ ĐỘ
Test-B:     giữ riêng đợt Tết 2026 (2026-02-03 → 03-08)  → đo cực trị
Test-C:     giữ riêng đợt gián đoạn 11/2025               → đo chống sốc
```
**Rolling-origin CV (forward chaining):** gốc dự báo trượt theo tuần, horizon = 1..90 ngày; báo cáo lỗi **theo từng horizon**, không gộp. Lý do: quota ở $u=60$ và $u=3$ là hai bài toán khác nhau.

**Khoảng đệm (embargo):** để trống ≥ `H_max` ngày giữa train và test, vì một vé bán ngày $D$ có thể thuộc chuyến chạy ngày $D+169$ (Tết) ⇒ **train/test chồng lấn qua booking horizon** nếu chia theo `thoi_diem_mua`. **Chia theo `ngay_chay` + embargo theo `H_max`.** Đây là cái bẫy tinh vi nhất trong toàn bộ tài liệu này.

### 9.2. Ba pha (đúng Mục 13 đề bài)

- **Pha 1 — Backtest lịch sử.** Chạy chính sách trên `_ground_truth` của các chuyến quá khứ; so với kết quả thực. **Lưu ý phản thực:** không thể "phát lại" đơn giản, vì nếu đổi giá thì tập yêu cầu cũng đổi. ⇒ **Bắt buộc dùng simulator làm môi trường phản thực**; đây chính là lý do simulator phải có choice model (Tài liệu 02, §6). Với dữ liệu thật, phải dùng **off-policy evaluation** (IPS/Doubly-Robust) và cần chính sách cũ có tính ngẫu nhiên — nên Pha 3 phải bật $\varepsilon$-exploration.
- **Pha 2 — Shadow mode.** AI khuyến nghị, người quyết. Đo **tỷ lệ đồng thuận (agreement rate)** + phân tích ca bất đồng. Ghi vào `quyet_dinh_ai` với `trang_thai_phe_duyet`.
- **Pha 3 — A/B có kiểm soát.** **Đơn vị ngẫu nhiên hóa = chuyến tàu (train-run), không phải hành khách.** Vì tồn kho được chia sẻ trong một chuyến ⇒ ngẫu nhiên hóa theo khách vi phạm SUTVA (can thiệp lên khách A làm đổi tồn kho của khách B). Dùng **switchback design theo (mác tàu × ngày)** để kiểm soát mùa vụ; phân tích bằng CUPED để giảm phương sai.

### 9.3. Bảng mục tiêu (Mục 12 đề bài) — cách đo đúng

| Mục tiêu đề bài | Công thức | Ghi chú |
|---|---|---|
| PKU **+3…8%** | $\frac{\sum_e x_e \ell_e}{\sum_e C_e \ell_e}$, so B4 vs B0 | mẫu số = ghế-km cung ứng |
| Doanh thu **+3…10%** | $\Delta Z$ với common random numbers | CRN giảm sai số ~5–10× |
| Ghế rỗng cục bộ **−20%** | $\sum_e (C_e - x_e)\ell_e$ | có trọng số km |
| Vé dọc đường **+10%** | # vé có `ga_di ∉ {ga đầu}` | |
| Tìm kiếm không thành **−15%** | từ `yeu_cau_tim_kiem.ket_qua` | **chỉ đo được nếu có log tìm kiếm** |
| **0 vi phạm giá/chính sách** | §6.1 | hard gate |
| Tốc độ gần thời gian thực | p95 $T_{\text{recalc}}$ | < 200 ms |

---

## 10. Bước 12 — Đóng gói, tài liệu, quản trị

### 10.1. DATASHEET (theo Gebru et al., *Datasheets for Datasets*)

Bắt buộc trả lời: động cơ; thành phần; quy trình thu thập; **rõ ràng đây là dữ liệu TỔNG HỢP (synthetic), không phải dữ liệu vận hành của VNR**; tiền xử lý; công dụng; phân phối; bảo trì; **hạn chế đã biết**.

> ⚠️ **Trung thực là điều kiện sống còn về mặt liêm chính khoa học.** Không được trình bày dữ liệu mô phỏng như dữ liệu thật của VNR. Cách trình bày đúng: *"Dataset tổng hợp, được hiệu chuẩn theo 18 mô men công bố công khai của VNR/Traravico giai đoạn 2024–2026, tái tạo nguyên vẹn bộ luật giá hiện hành và các sự kiện gián đoạn có thật."* Cách này **mạnh hơn** về mặt thuyết phục vì nó kiểm chứng được.

### 10.2. Tái lập & kiểm toán

```
manifest.json:
  master_seed: 20260717
  git_commit: <sha>
  config_hash: sha256(params_fitted.yaml)
  rules_hash:  sha256(pricing_rules.yaml)
  ref_hashes:  {ga.csv: <sha>, bieu_gia_co_ban.csv: <sha>, ...}
  moments_achieved: {M1: 3.91e6, M5: 517_300, M8: 719_000, ...}
  generated_at: 2026-07-20T10:00:00+07:00
```
Ghi `config_hash` vào **metadata của mỗi file parquet**. Đề bài yêu cầu **rollback** ⇒ có hash + version quy tắc ⇒ rollback là thao tác trỏ lại phiên bản, không phải khôi phục từ backup.

### 10.3. Giấy phép & pháp lý

- Dữ liệu tổng hợp: đề xuất **CC BY 4.0**; mã nguồn: **Apache-2.0** hoặc **MIT**.
- `ref/` chứa dữ kiện công khai (lý trình, biểu đồ, biểu giá): là **dữ kiện**, không phải tác phẩm ⇒ ghi rõ nguồn trong `SOURCES.md`. **Không sao chép nguyên văn** nội dung có bản quyền của báo chí; chỉ trích số liệu + dẫn link.
- **Không thu thập, không sinh, không lưu bất kỳ dữ liệu cá nhân nào.** Khách trong mô phỏng là ID tổng hợp, không ánh xạ tới người thật.

---

## 11. Ngăn xếp công nghệ khuyến nghị

| Lớp | Lựa chọn | Lý do |
|---|---|---|
| Mô phỏng | Python + **NumPy/Numba**, hoặc **SimPy** cho DES | Numba cho vòng lặp thinning: ~50–100× |
| LP / bid price | **HiGHS** (qua `scipy.optimize.linprog` hoặc `highspy`) | Nhanh, miễn phí, đủ cho ma trận TU |
| Tối ưu tổ hợp (xếp nhóm) | **OR-Tools CP-SAT** | Xử lý ràng buộc kề/khoang |
| Lưu trữ / truy vấn | **Parquet + DuckDB** | Không cần server; xử lý 60M dòng trên laptop |
| Dự báo | **LightGBM** (đích Poisson/Tweedie) + **quantile** cho lượng vị; so sánh với **statsforecast** (ETS/Croston cho O–D thưa) | Croston/TSB **đúng bài** cho chuỗi ngắt quãng |
| Hòa giải | `hierarchicalforecast` (Nixtla) hoặc tự cài MinT | |
| Nhân quả | **EconML** / **DoubleML** | Ước lượng co giãn giá không thiên lệch |
| DQ | **Great Expectations** hoặc **pandera** | Ràng buộc §6.1 thành test |
| Theo dõi | **MLflow** + **Evidently** (data drift, model drift — Mục 15 đề bài) | |
| API | **FastAPI** + Pydantic | Mục 9 đề bài: API tích hợp hệ thống bán vé |
| Giao diện | Tiếng Việt (Mục 15), heatmap khu gian × thời gian | `plotly`/`ECharts` |

**Về hiệu năng "near real-time":** nhờ Định lý 1 (ma trận TU ⇒ LP nguyên), việc tính lại bid price cho 1 chuyến (≤ 40 khu gian, ≤ 600 O–D) mất **< 10 ms** với HiGHS. Kết hợp cache + cập nhật gia tăng ⇒ p95 < 200 ms là dư sức. **Hãy nêu rõ luận điểm này** — nó biến "near real-time" từ một rủi ro thành một điểm mạnh có chứng minh.

---

## 12. Kiểm thử — bộ test tối thiểu (đưa vào CI)

```python
# --- Bất biến vật lý ---
def test_capacity_never_exceeded()          # ∀e,c: x_e ≤ C
def test_seat_intervals_disjoint()          # ∀k: Π_k rời nhau
def test_interval_matrix_is_C1P()           # mỗi cột A là dãy 1 liên tiếp
def test_offline_optimum_is_upper_bound()   # Z_policy ≤ Z_opt (∀ chính sách)
def test_greedy_assignment_uses_omega_colors()  # Định lý 2

# --- Tuân thủ pháp lý ---
def test_no_price_below_floor_or_above_cap()
def test_social_policy_discount_is_max_not_product()
def test_social_policy_applied_after_dynamic()
def test_priority_passengers_never_forced_to_change_seat()
def test_price_invariant_to_repeated_search()
def test_price_locked_after_confirmation()
def test_pricing_features_exclude_sensitive()

# --- Hiệu chuẩn ---
def test_moment_M5_avg_fare_within_5pct()          # ≈ 514.000 đ
def test_moment_M8_tet_fare_ratio_1_39()           # và mix ≥ 1,32 chứ không phải giá
def test_disruption_refund_higher_than_avg_fare()  # 615k > 514k
def test_load_factor_apr2026_near_79pct()

# --- Chống rò rỉ ---
def test_no_ground_truth_in_features()
def test_adversarial_auc_below_0_65()
def test_train_test_embargo_covers_max_horizon()   # ⭐ 169 ngày cho Tết
```

---

## 13. Mười khuyến nghị cuối — theo thứ tự tác động

1. **Log yêu cầu tìm kiếm là bảng quan trọng nhất.** Không có nó, 3/9 chỉ số đánh giá của đề bài (tìm kiếm không thành công, chuyển đổi, cầu chưa đáp ứng) **không tồn tại**, và dự báo bị thiên lệch có hệ thống ở đúng chỗ cần tối ưu.
2. **Đưa `bid_price` vào cả dữ liệu lẫn giao diện.** Nó là câu trả lời toán học cho Mục 7 đề bài, và là đặc trưng dự báo mạnh nhất.
3. **Tôn trọng điểm gãy 01/5/2026.** Huấn luyện xuyên qua nó mà không có cờ chế độ = học một chính sách trung bình của hai chính sách khác nhau.
4. **Đừng để bài toán mất khi bỏ chọn lựa.** Nested logit + recapture + cạnh tranh nội bộ. Không có chúng, mọi kết quả pricing đều lạc quan giả.
5. **Chia dữ liệu theo `ngay_chay` với embargo 169 ngày.** Đây là lỗi mà 90% nhóm sẽ mắc.
6. **MASE/pinball/CRPS, không MAPE.** Dữ liệu O–D thưa và có 0.
7. **Hòa giải MinT.** Dự báo O–D phải cộng ra dự báo khu gian.
8. **Common random numbers khi so sánh chính sách.** Giảm phương sai 5–10× miễn phí.
9. **Ràng buộc CSXH và sàn/trần là hard gate, kiểm toán tự động, hiển thị "0 vi phạm" trên dashboard.** Đề bài chấm chỉ tiêu này.
10. **Trung thực về nguồn gốc dữ liệu (synthetic, calibrated).** Một bộ dữ liệu tổng hợp *được hiệu chuẩn công khai và kiểm chứng được* đáng tin hơn nhiều so với một bộ dữ liệu tự nhận là "thật" mà không ai xác minh được.

---

## 14. Rủi ro dự án & phương án dự phòng

| Rủi ro | Xác suất | Giảm thiểu |
|---|---|---|
| dsvn.vn chặn cào / đổi cấu trúc | Cao | Cào sớm, cache đầy đủ; dự phòng: dựng biểu giá từ công thức $\kappa d^\theta$ + neo giá đã có ở Tài liệu 01 §2.3/02 §7.1 |
| Không lấy được lý trình chính xác toàn bộ 184 ga | Trung bình | Dùng 22–35 ga chính (đủ cho 231–595 O–D); nội suy tuyến tính; ghi rõ giả định |
| Hiệu chuẩn SMM không hội tụ | Trung bình | Giảm chiều: cố định các tham số có nguồn; ưu tiên khớp M1–M9 |
| Simulator quá chậm | Trung bình | Numba + song song theo chuyến (seed độc lập) |
| Nhóm hết thời gian | Cao | **Ưu tiên `pilot` (SE1–SE4 + SE19/20 + NA1/2)**; `full` là tùy chọn |
| Giám khảo hỏi "sao không dùng dữ liệu thật?" | **Chắc chắn** | Trả lời: dữ liệu vé là dữ liệu kinh doanh của VNR, không công khai; nhóm đã hiệu chuẩn theo **18 mô men công bố chính thức** và tái tạo **nguyên vẹn bộ luật giá hiện hành** + **các sự kiện gián đoạn có thật**; đồng thời cung cấp `_ground_truth` cho phép **đánh giá phản thực** — điều mà dữ liệu thật **không** cho phép |

> **Luận điểm kết:** với bài toán tối ưu tồn kho–giá, dữ liệu lịch sử thật *một mình nó không đủ*, vì nó chỉ chứa kết quả của **một** chính sách. Muốn biết chính sách khác tốt hơn bao nhiêu, bắt buộc phải có **môi trường phản thực**. Vì vậy, một simulator được hiệu chuẩn nghiêm ngặt **không phải là giải pháp thay thế cho dữ liệu thật — nó là một thành phần bắt buộc của lời giải**. Hãy trình bày nó như vậy.

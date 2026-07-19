# Âu Lạc Railway — Tổng quan kỹ thuật (đọc hiểu không cần nền tảng lập trình)

> Tài liệu này giải thích **hệ thống đang làm gì, tại sao làm vậy, và code nằm ở đâu** —
> đi từ bức tranh lớn xuống từng file. Không giả định người đọc biết lập trình;
> các thuật ngữ kỹ thuật được giải thích ngay khi xuất hiện lần đầu.
>
> Phạm vi: toàn bộ repo, tập trung sâu vào `backend/`. Trạng thái tại thời điểm viết
> (18/07/2026, sau khi P5 ghép nhiều ghế merge): backend có đủ 11/11 API, **93/93 test
> pass** (backend) + 9/9 test bất biến tier-2 (`tests/test_invariants.py`); bid-price
> live giờ là DLP thật (`app.bt3_allocation`) và giá động dùng elasticity optimizer
> thật (`app.elasticity`) — không còn công thức/luật giá gõ tay. `web/` (giao diện
> người dùng) **chưa được xây**.

---

## Mục lục

1. [Bài toán đang giải là gì](#1-bài-toán-đang-giải-là-gì)
2. [Kiến trúc tổng thể](#2-kiến-trúc-tổng-thể)
3. [Luồng dữ liệu tổng quát](#3-luồng-dữ-liệu-tổng-quát)
4. [Luồng end-to-end cho từng tình huống cụ thể](#4-luồng-end-to-end-cho-từng-tình-huống-cụ-thể)
5. [Mổ xẻ từng thư mục/file trong `backend/src`](#5-mổ-xẻ-từng-thư-mụcfile-trong-backendsrc)
6. [Cơ sở dữ liệu (Postgres)](#6-cơ-sở-dữ-liệu-postgres)
7. [Vai trò của từng file/thư mục trong toàn repo](#7-vai-trò-của-từng-filethư-mục-trong-toàn-repo)
8. [Các bất biến (invariant) mà mọi thay đổi phải tôn trọng](#8-các-bất-biến-invariant-mà-mọi-thay-đổi-phải-tôn-trọng)
9. [Bảng thuật ngữ Việt–Anh](#9-bảng-thuật-ngữ-việtanh)

---

## 1. Bài toán đang giải là gì

Đây là **bản demo AI định giá & phân bổ ghế cho Đường sắt Việt Nam (VNR)**, minh
họa 3 khả năng mà hệ thống bán vé truyền thống không làm được:

1. **Cắt chặng (leg-splitting)** — một vé không nhất thiết phải là "trọn tuyến";
   hệ thống tách hành trình dài thành các đoạn (leg) nhỏ để bán linh hoạt hơn.
2. **Ghép chặng / tái sử dụng khoảng trống (gap-merging)** — nếu một ghế đã bán
   đoạn đầu và đoạn cuối nhưng **đoạn giữa còn trống**, hệ thống truyền thống coi
   ghế đó là "hết chỗ" cho hành khách đi đoạn giữa. Âu Lạc phát hiện khoảng trống
   này và bán tiếp trên **cùng một ghế vật lý**.
3. **Giá vé linh hoạt (dynamic pricing)** — giá không cố định theo bảng giấy, mà
   thay đổi theo mùa cao điểm, ngày đặt trước, độ đầy tàu... trong một khung có
   kiểm soát (sàn/trần), và **vẫn tôn trọng chính sách xã hội** (giảm giá cho
   người cao tuổi, khuyết tật, trẻ em, người có công) như luật hiện hành.
4. **Ghép nhiều ghế (multi-seat merge, P5)** — khi không còn ghế nào trống liên
   tục suốt hành trình, hệ thống thử phủ hành trình bằng ≥2 ghế, đổi chỗ tại ga
   dừng đủ lâu (≥5 phút). Hành khách phải được hỏi ý kiến rõ ràng trước khi giữ
   chỗ (`requires_customer_consent`), và **không bao giờ** áp dụng cho hành khách
   ưu tiên (cao tuổi/khuyết tật/trẻ đi một mình).

Cách chứng minh: dựng **một kịch bản vàng (golden scenario)** cụ thể — tàu SE1,
chạy ngày 15/06/2026, 8 ga, 40 ghế — trong đó có sẵn một ghế (`C01-S017`) đã bán
đoạn đầu và đoạn cuối, còn trống đúng đoạn giữa (Thanh Hóa → Đồng Hới). Hệ thống
bán truyền thống sẽ từ chối khách muốn đi đoạn này ("hết chỗ" giả — false sold-out);
Âu Lạc phát hiện và bán được. Đây là "khoảng trống vàng" (**golden gap**) mà toàn
bộ code, dữ liệu mẫu (seed) và test đều xoay quanh.

---

## 2. Kiến trúc tổng thể

### 2.1 Hai tầng KHÔNG BAO GIỜ chạm nhau lúc vận hành

Đây là quy tắc quan trọng nhất của cả dự án:

```
generated_data/   (bộ dữ liệu giả lập 12 tháng, ~4 GB, KHÔNG nằm trong git)
      │
      │  chỉ dùng để "hiệu chỉnh con số" — KHÔNG copy dữ liệu thẳng
      ▼
backend/seed/     (~50 KB JSON, có trong git — "hạt giống" khởi tạo hệ thống)
      │
      ▼
PostgreSQL  ──►  Backend API (FastAPI)  ──►  Frontend (web/, chưa xây)
```

- `generated_data/` là một **bộ mô phỏng ngoại tuyến** (12 tháng dữ liệu bán vé
  giả định của toàn mạng lưới đường sắt) — dùng để tính ra các con số hợp lý
  (giá tiền/km, tỷ lệ lấp đầy, đường cong đặt vé sớm/muộn...). Không có dòng code
  nào của backend "gọi" vào bộ dữ liệu này lúc chạy thật.
- `backend/seed/` là dữ liệu **được viết tay theo đặc tả** (8 ga, 40 ghế, kịch
  bản vàng) — không phải trích xuất từ bộ 4 GB kia (40 ghế ≠ 448 ghế thật, 8 ga
  ≠ 22 ga thật). Mục đích: đảm bảo golden gap luôn tồn tại đúng vị trí để demo
  chạy được, dù máy demo không có 4 GB dữ liệu hay Python/pandas.

### 2.2 Các thành phần chính

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| **Backend API** | Python, FastAPI (khung web nhẹ, không cần trình duyệt để hiểu — nó nhận HTTP request và trả JSON) | "Bộ não" — tính giá, tìm ghế, giữ chỗ, xác nhận, backtest |
| **Cơ sở dữ liệu** | PostgreSQL 15 (chạy trong Docker) | Nguồn sự thật duy nhất về: ghế nào trống/đang giữ/đã bán, giá bao nhiêu, quyết định nào đã ra |
| **Flyway** | Công cụ quản lý version cho cấu trúc DB | Chạy các file `.sql` để tạo/sửa bảng theo đúng thứ tự, một lần khi khởi động |
| **Luật giá động** | Mùa vụ thật (`models/artifacts/bt5_pricing_params.json`) + optimizer elasticity (`app.elasticity`, sống trong `app/` — tier 2) | Không còn file YAML luật giá gõ tay (`rules/pricing_rules.yaml` đã xóa, P3) — hệ số mùa vụ đọc từ artifact đã ước lượng, phần "động theo khan hiếm" tối đa hoá `P(mua\|r)·(p−c)` |
| **Bid-price (giá sàn cơ hội)** | DLP thật (`app.bt3_allocation`, live-import qua `backend/src/allocation/cache.py`) | Không còn công thức xấp xỉ scarcity cho route `/offers` sống — công thức cũ (`forecast/bid_price.py`) chỉ còn dùng lại cho backtest replay (lý do NFR, xem §5.7) |
| **Frontend** | *(chưa xây)* | Giao diện xem sơ đồ ghế, đặt vé demo |

### 2.3 Vì sao chia thành các module nhỏ (state / merging / pricing / forecast / offer / backtest)

Dự án được 5 người cùng phát triển song song, mỗi người "sở hữu" một hoặc vài
thư mục để tránh giẫm code lên nhau (`plan/00_MASTER_PLAN.md §5.1`). Ranh giới
module không phải ngẫu nhiên — nó phản ánh đúng **các bước trong một quyết định
bán vé** (xem §3). Vì vậy khi đọc code, mỗi thư mục trong `backend/src/` tương ứng
đúng một bước trong pipeline dưới đây.

---

## 3. Luồng dữ liệu tổng quát

Mọi yêu cầu đặt vé đi qua đúng trình tự cố định này (không được đảo thứ tự):

```
1. Đọc "ảnh chụp" trạng thái ghế nhất quán (một lần đọc, không đọc rải rác)
2. Ánh xạ ga đi–ga đến (O-D) sang dải đoạn tàu (segment span), vd Thanh Hóa→Đồng Hới = đoạn 3..4
3. Tìm một ghế trống LIÊN TỤC suốt dải đó (kể cả nếu ghế đã có vé ở đoạn khác — đây chính là gap-merging)
4. Tra giá gốc theo chặng O-D (không cộng dồn giá từng đoạn nhỏ)
5. Áp luật giá động (mùa cao điểm, đặt sớm/muộn, độ đầy tàu...) theo YAML
6. Áp rào chắn cứng (guardrail): sàn giá, trần giá, mức thay đổi tối đa, làm tròn nghìn, hoặc đóng băng giá
7. So giá cuối với "giá sàn cơ hội" (bid-price) của từng đoạn — nếu giá không đủ bù, TỪ CHỐI
8. Tạo Offer (đề nghị giá) — CHƯA giữ ghế, chỉ là một đề xuất có hạn dùng 15 phút
9. Khách đồng ý → POST /holds giữ TẤT CẢ các ô ghế cần trong MỘT giao dịch DB (được hết cùng được, hỏng hết cùng hỏng)
10. Khách xác nhận thanh toán → POST /bookings/{hold_id}/confirm — chuyển HELD → SOLD, KHÔNG tính lại giá
11. Ghi lại toàn bộ quyết định vào "sổ nhật ký không thể sửa" (DecisionRecord) để giải trình sau này
```

Sơ đồ trách nhiệm theo module:

```
                    ┌─────────────────────────────────────────────┐
                    │              FastAPI routes (api/)           │
                    └─────────────────────────────────────────────┘
                       │            │              │           │
                 routes_demo   routes_offers   routes_holds  routes_backtests
                       │            │              │           │
        ┌──────────────┘            │              │           └──────────┐
        ▼                           ▼              ▼                      ▼
  state/ (SeatStateManager)   merging/(resolver) state/(SeatStateManager) backtest/(engine)
  forecast/(forecast,network)  pricing/(engine,context)                   forecast/ + pricing/
                               offer/(service) ──► DecisionRecord
```

- **`state/`** — "người viết duy nhất" (single writer) vào 2 bảng lõi
  (`seat_segment_state`, `service_run.matrix_version`). Không module nào khác
  được phép ghi trực tiếp vào 2 bảng này — mọi thay đổi trạng thái ghế đi qua đây.
- **`merging/`** — chỉ đọc (read-only), tìm ghế trống liên tục cho một dải đoạn.
- **`pricing/`** — tính giá theo luật + rào chắn + chính sách xã hội. Không biết
  gì về ghế, không biết gì về hành khách (xem §8.3).
- **`forecast/`** — dự báo nhu cầu còn lại + tính "giá sàn cơ hội" (bid-price)
  cho từng đoạn tàu.
- **`offer/`** — nhạc trưởng: gọi resolver → pricing → so bid → tạo Offer +
  DecisionRecord. Không giữ ghế.
- **`backtest/`** — mô phỏng hàng trăm yêu cầu đặt vé để so sánh doanh thu giữa
  cách bán truyền thống (baseline) và Âu Lạc, chạy độc lập với DB thật.

---

## 4. Luồng end-to-end cho từng tình huống cụ thể

### 4.1 Reset kịch bản demo — `POST /demo/scenarios/{id}/reset`

Dùng để đưa hệ thống về trạng thái ban đầu trước khi bắt đầu demo (có thể bấm
lại nhiều lần).

1. Route (`routes_demo.py`) gọi `SeatStateManager.reset_scenario()`.
2. Hàm này đọc 5 file trong `backend/seed/`: `scenario.json` (ga, đoạn, ghế),
   `initial_bookings.jsonl` (những vé đã bán sẵn — bao gồm golden gap),
   `fare_products.json` (giá gốc từng O-D), `pricing_policy.json` (sàn/trần/CSXH),
   `forecast.json` (dự báo ban đầu).
3. Xóa sạch dữ liệu cũ của `service_run_id` này trong DB (booking, hold, offer,
   trạng thái ghế, giá, dự báo) — **xóa toàn bộ rồi dựng lại**, không sửa từng phần,
   để tránh còn sót dữ liệu cũ gây sai lệch.
4. Tạo lại 40 ghế × 7 đoạn = 280 ô, tất cả `FREE`, rồi áp các booking có sẵn từ
   `initial_bookings.jsonl` (đây là bước tạo ra golden gap: ghế `C01-S017` bị
   đánh dấu `SOLD` ở đoạn 1-2 và 5-7, còn đoạn 3-4 vẫn `FREE`).
5. Nạp giá, chính sách, dự báo vào DB.
6. Tất cả nằm trong MỘT giao dịch (transaction) — nếu bất kỳ bước nào lỗi, toàn
   bộ được hoàn tác (`rollback`), không để DB ở trạng thái nửa vời.
7. Trả về `matrix_version=1`, các version khác, và một **checksum** (mã băm) để
   xác nhận dữ liệu vừa nạp khớp với seed — dùng để chứng minh "demo tất định",
   chạy lại nhiều lần cho kết quả giống hệt nhau.

### 4.2 Yêu cầu đặt vé THÀNH CÔNG qua golden gap — `POST /offers` (Thanh Hóa → Đồng Hới)

Đây là kịch bản "hero" chứng minh giá trị của Âu Lạc.

1. **Route nhận request** (`routes_offers.py::create_offer`) với `origin=THO,
   dest=DHO`. Ánh xạ sang đoạn `seg_from=3, seg_to=4` (`seg_range()`).
2. **Snapshot nhất quán**: đọc toàn bộ sơ đồ ghế 1 lần (`ssm.get_seatmap()`),
   chuyển thành ma trận numpy 40×7 (`_matrix_from_seatmap`). Ghi nhớ
   `matrix_version` tại thời điểm đọc — mọi bước sau dùng đúng bản chụp này,
   không đọc lại DB giữa chừng (tránh tình trạng ghế bị người khác mua trong lúc
   đang tính giá).
3. **Resolver** (`merging/resolver.py::best_same_seat`) quét cột 3-4 của ma trận,
   tìm các ghế `FREE` toàn bộ dải này. Ghế `C01-S017` xuất hiện trong danh sách
   vì đoạn 3-4 của nó đang trống — dù đoạn 1-2 và 5-7 đã bán. Trong số các ứng
   viên, resolver xếp hạng "vừa khít nhất" lên đầu (ghế có ít ô trống *thừa* ngoài
   dải yêu cầu nhất) — ghế `C01-S017` chỉ trống đúng đoạn cần, nên luôn được chọn
   trước ghế trống hoàn toàn (giữ ghế trống dài cho khách đi xa hơn).
4. **Tra giá gốc O-D**: đọc thẳng bảng `fare_product` theo đúng cặp `THO→DHO`
   (không cộng giá từng đoạn nhỏ lại — giá theo chặng đã có sẵn số).
5. **Tính bid-price từng đoạn** — gọi `allocation/cache.py` (cache theo
   `service_run_id`+`matrix_version`+`forecast_version`, làm mới lúc reset/refresh)
   đọc kết quả **LP dual thật** từ `app.bt3_allocation.analyze_run` (tier 2, live-import
   qua shim `integration/ssm_from_postgres.py` để không cần `import pandas` trong
   `backend/src/`) — càng khan hiếm, bid càng cao; cache miss ⇒ 503
   `POLICY_UNAVAILABLE` (không bịa fallback). Với golden gap THO→DHO, bid = 0đ vì
   cầu dự báo đoạn 3-4 (~3,6/16,2 vé) thấp hơn nhiều sức chứa còn lại — **đúng**,
   không phải lỗi.
6. **PricingContext** được dựng CHỈ từ tín hiệu hợp pháp (mùa cao điểm, số ngày
   trước khởi hành, độ đầy tàu...) — tuyệt đối không có thông tin hành khách.
7. **PricingEngine** (`pricing/engine.py`) chạy:
   - Đề xuất giá động = hệ số mùa vụ thật (đọc từ
     `models/artifacts/bt5_pricing_params.json`, rule_id `MUA_VU:HE`/`MUA_VU:TET`)
     **+** optimizer elasticity thật (`app.elasticity.Elasticity.optimal_price`, tối
     đa hoá `P(mua|r)·(p−c)` với `c` = Σ bid DLP bước 5, rule_id `ELASTIC:r=<tỷ lệ>`)
     — không còn hệ số `he_so` gõ tay trong file YAML nào.
   - Ép giá vào khung sàn/trần (`floor_ratio`/`ceiling_ratio` × giá gốc), giới
     hạn mức thay đổi tối đa nếu có giá công bố trước, làm tròn về nghìn đồng.
   - Áp giảm giá chính sách xã hội (CSXH) **sau cùng**, chỉ lấy MỘT mức cao nhất
     nếu khách thuộc nhiều diện — không cộng dồn.
8. **So sánh**: nếu giá cuối ≥ tổng bid-price các đoạn → `decision = ACCEPT`;
   ngược lại `REJECT`.
9. **OfferService** (`offer/service.py`) đóng gói tất cả thành một `Offer` bất
   biến (immutable) kèm hạn dùng 15 phút, và một `DecisionRecord` ghi lại: giá
   gốc, luật nào bắn, rào chắn nào chạm, lý do chấp nhận/từ chối bằng câu văn dễ
   hiểu (`explanation`).
10. Route ghi `offer` và `decision_record` vào DB, trả JSON đầy đủ: giá 3 tầng
    (gốc / niêm yết / cuối), bid từng đoạn, seat_plan, 4 version, hạn dùng.

### 4.3 Yêu cầu KHÔNG có ghế cùng-ghế-liên-tục — ghép nhiều ghế (P5) hoặc lỗi `NO_SAME_SEAT_OPTION`

Nếu resolver same-seat không tìm được ghế nào trống suốt cả dải (ví dụ mọi ghế
đều đã bán một phần trong dải đó), route **thử ghép nhiều ghế** trước khi từ
chối (`merging/resolver.py::best_multiseat`): phủ dải yêu cầu bằng ≥2 ghế, chỉ
đặt điểm đổi chỗ tại ga có thời gian dừng ≥5 phút (`forecast/network.py::DWELL_MINUTES`).
Tìm được ⇒ `decision_record`/`Offer` vẫn `ACCEPT` bình thường nhưng
`requires_customer_consent=true` + `so_lan_doi_cho`/`change_station_ids` được
điền — FE bắt buộc hiển thị disclosure và đợi khách đồng ý trước khi `/holds`.
Hành khách **ưu tiên** (`priority_passenger=true` trong request — cao tuổi/khuyết
tật/trẻ đi một mình) **không bao giờ** nhận nhánh này (resolver tự lọc rỗng).
Cả hai nhánh cùng rỗng ⇒ 422 `NO_SAME_SEAT_OPTION`.

### 4.4 Yêu cầu bị TỪ CHỐI vì giá không bù được cơ hội — lỗi `ALLOCATION_REJECTED`

Nếu tìm được ghế nhưng giá cuối (sau mọi luật + rào chắn + CSXH) vẫn thấp hơn
tổng bid-price các đoạn (ví dụ khách có CSXH giảm sâu vào đúng lúc tàu rất khan
ghế), hệ thống vẫn **ghi lại DecisionRecord với result=REJECT** (để có bằng
chứng kiểm toán) rồi mới trả lỗi 422 `ALLOCATION_REJECTED` cho khách — không
âm thầm bỏ qua.

### 4.5 Giữ ghế — `POST /holds`

1. Client gửi `offer_id` + `expected_matrix_version` (giá trị đọc được từ bước
   4.2) + một `Idempotency-Key` (khóa chống gửi trùng — client tự sinh, nếu gửi
   lại đúng khóa này thì server trả lại đúng kết quả cũ, không giữ ghế 2 lần).
2. Server tra `offer` trong DB; nếu hết hạn (`expires_at` đã qua) → lỗi 410
   `OFFER_EXPIRED`.
3. `SeatStateManager.hold()`:
   - Dọn các hold quá hạn trước (`expire_due_holds`) — luôn chạy trước MỌI đọc/ghi khác.
   - Nếu `idempotency_key` đã tồn tại → trả lại kết quả hold cũ (không tạo mới).
   - Khóa dòng `service_run` (`SELECT ... FOR UPDATE`), so `expected_matrix_version`
     với giá trị hiện tại trong DB. **Không khớp** → lỗi 409 `STALE_SNAPSHOT` (ai
     đó đã thay đổi sơ đồ ghế từ lúc client đọc offer đến giờ, client phải lấy
     offer mới).
   - Khóa tất cả các ô ghế cần giữ (theo thứ tự `segment_id` tăng dần — tránh
     deadlock khi nhiều giao dịch chạy song song), kiểm tra **toàn bộ đang FREE**.
     Chỉ cần một ô đã bị người khác giữ/mua → lỗi 409 `SEAT_CONFLICT`, KHÔNG ô
     nào trong nhóm được cập nhật (all-or-nothing).
   - Nếu mọi ô đều FREE: cập nhật tất cả thành `HELD`, tăng `matrix_version`
     — **tất cả trong cùng một giao dịch Postgres**, Postgres tự đảm bảo tính
     nguyên tử (atomicity), code không tự viết cơ chế khóa/riêng Redis.
4. Trả `hold_id`, hạn giữ chỗ và `matrix_version` mới. API trực tiếp dùng 10 phút; luồng admin duyệt tiếp tục dùng đúng mốc hết hạn 15 phút của phương án.

### 4.6 Xác nhận thanh toán — `POST /bookings/{hold_id}/confirm`

1. Nếu `hold_id` đã có `booking` (đã confirm trước đó, ví dụ do client gọi lại
   vì mất mạng) → trả lại booking cũ, không tạo booking thứ hai (idempotent).
2. Nếu hold không tồn tại hoặc đã hết hạn/không còn `ACTIVE` → lỗi 410 `HOLD_EXPIRED`.
3. Ngược lại: chuyển các ô ghế từ `HELD` → `SOLD`, đánh dấu hold `CONFIRMED`, tạo
   `booking` mới. **Không tính lại giá** — giá dùng đúng giá đã chốt lúc tạo Offer,
   dù giá thị trường lúc confirm có thể đã đổi (khách đã "chốt" giá khi giữ chỗ).

### 4.7 Refresh dự báo — `POST /demo/forecasts/refresh`

Dùng để mô phỏng việc dự báo nhu cầu cập nhật theo thời gian (ví dụ sau khi có
thêm booking mới). Đếm số ghế đã bán mỗi đoạn hiện tại, tính lại nhu cầu còn lại
kỳ vọng dựa trên số ngày còn lại đến khởi hành (đường cong pickup), rồi ghi một
bản dự báo MỚI với `forecast_version` tăng thêm 1 — không sửa bản cũ (giữ lịch
sử để một Offer cũ vẫn tham chiếu đúng version đã dùng).

### 4.8 Backtest so sánh baseline vs Âu Lạc — `POST /backtests` + `GET /backtests/{id}`

Đây là "bằng chứng" định lượng cho toàn bộ demo, không dùng DB thật mà chạy
hoàn toàn trong bộ nhớ:

1. `backend/seed/backtest/*.jsonl` chứa 5 chuỗi sự kiện (5 "seed" cố định:
   `20260717..20260721`, đã commit vào git) — mỗi dòng là một yêu cầu đặt vé giả
   lập (ga đi/đến, số ngày trước khởi hành...). λ mỗi cặp O-D tính thật từ
   `search_log` SE1 tháng 6/2026 (map 22 ga → 8 ga theo lý trình), scale sức
   chứa `40/448` (phép biến đổi tất định, công thức trong docstring
   `backtest/events.py`) — **không còn** số tay `TARGET_TOTAL_REQUESTS=400`/
   `HORIZON_DAYS=90`; horizon giờ = cửa sổ thật quanh 15/06 (`calendar_events.csv`).
2. Với mỗi seed, engine chạy đồng thời 2 kịch bản trên **cùng một chuỗi yêu cầu**
   (kỹ thuật "common random numbers" — đảm bảo so sánh công bằng, không phải do
   may rủi khác luồng khách):
   - **Baseline** (`BaselineQuota`): mô phỏng hệ thống bán vé truyền thống — một
     khi một ghế đã dính bất kỳ booking nào, coi như "không còn trinh nguyên",
     không tái sử dụng khoảng trống giữa 2 vé trên cùng ghế đó. Giá bán = giá
     niêm yết cố định (không có luật động).
   - **Âu Lạc** (`SegmentSeatMatrix.first_fit`): tìm ghế trống liên tục thật sự
     (bao gồm cả các khoảng trống giữa 2 vé cũ), giá qua `PricingEngine` thật
     (mùa vụ + elasticity optimizer, giống route `/offers` sống), phải ≥ tổng
     bid-price mới nhận khách. Bid gating trong backtest **cố ý giữ** công thức
     xấp xỉ scarcity (`forecast/bid_price.py`) thay vì gọi DLP `app.bt3_allocation`
     mỗi request — lý do NFR: LP solve × ~2.000 event/backtest không khả thi,
     và cache DLP gắn với snapshot Postgres, không khớp state in-memory của backtest.
3. Kết quả mỗi seed: doanh thu, tỷ lệ chấp nhận. Gộp 5 seed lại lấy **trung vị
   (median)** + khoảng min/max (chống 1 seed may rủi làm lệch kết luận).
4. Trả về `report_id`; client gọi `GET /backtests/{report_id}` lấy báo cáo đầy
   đủ kèm `checksum` (mã băm để xác nhận báo cáo không bị chỉnh sửa sau khi
   sinh ra).
5. **Số hiện tại** (chạy `python -m src.backtest.engine`, 5 seed, 0 fail):
   doanh thu baseline trung vị **18.848.000đ** vs Âu Lạc **23.438.000đ** trên
   cùng chuỗi yêu cầu = **+24,4%**. ⚠️ Con số "+156%" (baseline 19,5tr vs Âu Lạc
   50,0tr) từng dùng cho pitch là **artifact của kịch bản demo cũ** (baseline từ
   chối gần hết request giả, chưa calibrate λ từ dữ liệu thật) — **không phải**
   bằng chứng doanh thu chuẩn, không dùng số đó nữa. Bằng chứng chính cho pitch
   nên trích từ model backtest chạy trên dữ liệu thật cả năm
   (`models/artifacts/backtest_report.json`): Tết **+2,3%** doanh thu, **89,0%**
   tối ưu offline (vs FCFS 87,0%), ghế trống cục bộ **−52%**, MASE **0,515**,
   p95 **6–7ms**, **0 vi phạm** guardrail/CSXH.

### 4.9 Tra cứu một quyết định đã ra — `GET /decisions/{decision_id}`

Đọc thẳng bảng `decision_record` theo khóa chính, trả lại toàn bộ "hồ sơ" của
một lần định giá: giá gốc, giá AI đề xuất, giá cuối, tổng bid-price, những rào
chắn đã chạm, và lời giải thích bằng văn bản — phục vụ minh bạch/giải trình
(explainability), không cần công cụ AI phức tạp (SHAP...) vì luật đã khai báo
tường minh trong YAML.

---

## 5. Mổ xẻ từng thư mục/file trong `backend/src`

### 5.1 `src/api/` — lớp giao tiếp HTTP (mỏng, không chứa logic nghiệp vụ)

| File | Vai trò |
|---|---|
| `main.py` | Khởi tạo ứng dụng FastAPI, gắn 4 nhóm route, và **bộ bắt lỗi chung**: mọi `DomainError` (lỗi nghiệp vụ đã định nghĩa) tự động biến thành JSON đúng mã lỗi + HTTP status — route không cần tự viết `try/except` lặp lại. |
| `deps.py` | "Nguồn cấp" cho mỗi request: đường dẫn thư mục `seed/`, đồng hồ hệ thống (`Clock`), và một `SeatStateManager` mới gắn với kết nối DB mới cho mỗi request — tránh chia sẻ kết nối/trạng thái giữa các request. |
| `routes_demo.py` | 4 endpoint chỉ phục vụ demo: reset kịch bản, refresh dự báo, xem tổng quan (`overview` — doanh thu, tỷ lệ lấp đầy, điểm nghẽn), xem sơ đồ ghế (`seatmap`), xem phân tích (`analytics` — dự báo + bid theo từng đoạn). |
| `routes_offers.py` | Endpoint quan trọng nhất — toàn bộ pipeline tạo Offer (mô tả chi tiết ở §4.2). |
| `routes_holds.py` | Giữ chỗ (`/holds`) + xác nhận thanh toán (`/bookings/{hold_id}/confirm`). |
| `routes_backtests.py` | Chạy backtest, lấy báo cáo, tra cứu quyết định. Báo cáo backtest lưu **tạm trong bộ nhớ** (không phải DB) — vì đây là demo chạy 1 tiến trình duy nhất; đã ghi chú rõ (`ponytail:`) nếu cần sống sót qua restart thì phải chuyển sang bảng Postgres. |
| `schemas.py` | Định nghĩa hình dạng dữ liệu đầu vào (Pydantic — tự động kiểm tra kiểu dữ liệu, ví dụ `quantity` phải ≥ 1) khớp với `openapi.yaml`. |

### 5.2 `src/state/` — nơi DUY NHẤT được phép thay đổi trạng thái ghế

Đây là module nhạy cảm nhất về mặt an toàn dữ liệu (concurrency — nhiều người
đặt vé cùng lúc).

| File | Vai trò |
|---|---|
| `seat_state_manager.py` | Toàn bộ logic đọc/ghi 2 bảng lõi. Các thao tác chính: `reset_scenario` (nạp lại từ seed), `get_seatmap` (đọc snapshot), `find_continuous_same_seat`, `hold_multi` (CAS **nhiều ghế·nhiều đoạn cùng lúc**, dùng chung 1 `hold_id` — P5; `hold` là hàm tiện cho trường hợp riêng 1 ghế), `confirm` (chốt bán — xem §4.6), `expire_due_holds` (tự động giải phóng các chỗ giữ quá 10 phút không thanh toán). Nguyên tắc cốt lõi: mọi CAS (compare-and-swap — "chỉ đổi nếu vẫn đúng như kỳ vọng, nếu không thì báo lỗi thay vì đè lên") đều dựa vào khả năng khóa dòng của chính Postgres (`SELECT ... FOR UPDATE`), **không tự viết cơ chế khóa riêng, không dùng Redis, không có vòng lặp thử lại** — đơn giản hết mức có thể mà vẫn đúng. `hold_multi` khóa+verify FREE **toàn bộ** leg trước (chưa ghi gì), chỉ UPDATE khi mọi leg sạch — 1 leg xung đột ⇒ rollback tất cả, không leg nào bị giữ một phần. |
| `db.py` | Mở kết nối Postgres bằng thư viện `psycopg` thuần (không dùng ORM — công cụ ánh xạ bảng thành object — trên đường CAS, để không có tầng trung gian nào che giấu hành vi khóa/giao dịch thật). Đọc `DATABASE_URL` từ biến môi trường. |
| `clock.py` | Bọc "giờ hiện tại" thành một lớp (`Clock`) thay vì gọi `datetime.now()` rải rác khắp nơi. Lý do: cần một `FixedClock` cho test — có thể "tua" thời gian tới trước để kiểm tra hold hết hạn sau 10 phút mà không cần thực sự chờ 10 phút. |
| `errors.py` | Danh sách lỗi nghiệp vụ, mỗi lỗi gắn với đúng 1 mã HTTP + 1 `error_code` theo `docs/API_Contract.md` (ví dụ: hết chỗ liên tục → 422 `NO_SAME_SEAT_OPTION`; xung đột giữ chỗ → 409 `SEAT_CONFLICT`; hết hạn Offer → 410 `OFFER_EXPIRED`). |

### 5.3 `src/merging/resolver.py` — "bộ não ghép chặng"

Chỉ đọc dữ liệu (không bao giờ ghi vào DB — nếu resolver ghi trực tiếp, đó là
bug vì phá vỡ nguyên tắc "một người viết duy nhất" ở §5.2). Nhận vào ma trận
ghế × đoạn (dùng thư viện tính toán số `numpy` cho nhanh), trả về danh sách ghế
khả dụng đã xếp hạng.

- `continuous_same_seat`: một dòng numpy — lọc các ghế `FREE` trên toàn bộ dải
  đoạn yêu cầu.
- `_is_reused_gap`: đánh dấu ghế này có phải "tái sử dụng khoảng trống" hay
  không (có booking trước điểm đi hoặc sau điểm đến) — chỉ là **nhãn hiển thị**,
  không ảnh hưởng đến việc có chọn ghế đó hay không.
- Cách xếp hạng ("best-fit"): ưu tiên ghế có **ít ô trống thừa nhất** ngoài dải
  cần dùng — tức ưu tiên "nhét khít" vào khoảng trống nhỏ, để dành ghế trống dài
  cho khách đi xa. Ghế `C01-S017` (golden gap) luôn thắng vì nó không thừa ô nào.
  Khi bằng nhau, xếp theo `seat_id` để kết quả luôn tất định (deterministic) —
  chạy lại nhiều lần ra cùng một ghế.
- **Ghép nhiều ghế (P5)** — khi `resolve_same_seat_options` rỗng,
  `resolve_multiseat_options`/`best_multiseat` thử phủ dải yêu cầu bằng ≥2 ghế
  (greedy min-cover), chỉ đặt điểm đổi chỗ tại ga có `dwell_phut ≥ 5`
  (`forecast/network.py::DWELL_MINUTES`, nguồn: YAML tham số mô phỏng). Loại trừ
  tuyệt đối hành khách ưu tiên (`priority_passenger=True` ⇒ trả rỗng ngay, không
  thử cover). Vẫn read-only, tất định, không tự gán ghế — gán thật vẫn qua
  `POST /holds` (CAS nhiều ghế·nhiều đoạn trong MỘT transaction, xem §5.2).

### 5.4 `src/pricing/` — định giá

- **`context.py`**: định nghĩa 2 "hộp dữ liệu" tách biệt bằng kiểu dữ liệu Python
  (không chỉ bằng quy ước, mà `PricingContext` **về mặt cấu trúc không có chỗ**
  chứa các trường bị cấm — có một danh sách đen `FORBIDDEN_PRICING_FEATURES`
  và một kiểm tra tự động ném lỗi nếu ai đó lỡ thêm trường cấm vào class này).
  `SafetyContext` là nơi duy nhất chứa thông tin hành khách (người cao tuổi,
  khuyết tật...) và không bao giờ được đưa vào `PricingContext`.
- **`engine.py`** (`PricingEngine`): 3 bước tuần tự, đúng thứ tự bắt buộc:
  1. `apply_dynamic` — đề xuất giá động = hệ số mùa vụ **thật** (đọc từ
     `models/artifacts/bt5_pricing_params.json`, đã ước lượng từ DGP, rule_id
     `MUA_VU:HE`/`MUA_VU:TET`) **nhân với** kết quả optimizer elasticity **thật**
     (`app.elasticity.Elasticity.optimal_price`, tối đa hoá `P(mua|r)·(p−c)` với
     `c` = Σ bid-price DLP, rule_id `ELASTIC:r=<tỷ lệ>`), đồng thời **ghi lại luật
     nào đã bắn** (đây chính là "giải thích được"). Không còn file YAML luật giá
     gõ tay (`rules/pricing_rules.yaml` — xóa ở P3, kể cả luật `R_GIO_CHOT` từng
     cố tình tạo case vượt trần).
  2. `apply_guardrail` — nếu chưa có chính sách giá được duyệt, **từ chối phục
     vụ (503) thay vì tự bịa một giá mặc định** (fail closed); nếu có, ép giá vào
     khung sàn/trần, giới hạn mức thay đổi tối đa so với giá công bố trước (nếu
     có), làm tròn về nghìn đồng.
  3. `csxh_apply` — áp giảm giá chính sách xã hội **sau cùng**, dựa trên giá đã
     qua guardrail, lấy **một mức giảm cao nhất** nếu khách đủ điều kiện nhiều
     diện (không cộng dồn) — đúng tinh thần Điều 40 Nghị định 16/2026.

### 5.5 `src/forecast/` — dự báo & giá sàn cơ hội

- **`network.py`**: các hằng số "địa lý" của kịch bản vàng — 8 ga, khoảng cách
  từng đoạn, 40 ghế, ID ghế vàng. Đây là "bản đồ" mà mọi module khác tra cứu
  khoảng cách/đoạn từ đó, tránh mỗi nơi tự định nghĩa một bộ số khác nhau.
- **`forecast.py`**: một mô hình dự báo **tất định, đơn giản có chủ đích** (không
  phải machine learning thật) — ước lượng bao nhiêu chỗ còn lại sẽ được bán dựa
  trên số ngày còn lại đến ngày khởi hành (đường cong "pickup": càng gần ngày
  chạy, nhu cầu càng "chín"). Đủ để nuôi số liệu cho bước tính bid-price, không
  cần mô hình phức tạp hơn vì đây là demo.
- **`bid_price.py`**: công thức xấp xỉ 3 bước — *áp lực* (nhu cầu dự báo / số ghế
  còn trống) → *độ khan hiếm* (chuẩn hóa áp lực về khoảng 0-1) → *giá sàn* = đơn
  giá tham chiếu (đồng/km, hiệu chỉnh từ một mốc giá thật SE1 Hà Nội–Sài Gòn) ×
  khoảng cách đoạn × độ khan hiếm. **Không còn dùng cho route `/offers` sống**
  (P2) — bid-price live giờ là **DLP dual thật** (`app.bt3_allocation`, qua
  `allocation/cache.py`); công thức này chỉ còn backing cho `backtest/engine.py`
  replay (lý do NFR — xem §4.8). **Cố ý không gọi đây là "EMSR-b"** dù cả hai
  đường (công thức xấp xỉ lẫn DLP) đều không phải cài đặt đầy đủ thuật toán đó.
- **`allocation/cache.py`** (mới, P2) + **`integration/ssm_from_postgres.py`**
  (shim, sống ngoài `backend/src/` để giữ CI gate "không `import pandas`" đúng
  nghĩa đen): cache bid-price DLP theo `(service_run_id, matrix_version,
  forecast_version)`, refresh lúc reset/forecasts-refresh — không giải LP mỗi
  request. Cache miss ⇒ 503 `POLICY_UNAVAILABLE`, không fallback công thức cũ.

### 5.6 `src/offer/service.py` — nhạc trưởng ghép mọi thứ lại

`OfferService.build_offer()` là hàm duy nhất gọi đến cả `merging` (gián tiếp,
nhận `seat_plan` đã tính sẵn từ route), `pricing` (trực tiếp), và tạo ra 2 vật
thể bất biến:

- **`Offer`**: đề xuất giá đầy đủ, có hạn dùng 15 phút, CHƯA giữ ghế thật.
- **`DecisionRecord`**: "biên bản" không thể sửa của quyết định — bao gồm một
  `input_hash` (mã băm của mọi input đầu vào, dùng để phát hiện nếu có ai cố
  tình sửa lại input sau này mà giả vờ là quyết định cũ), danh sách luật đã bắn,
  rào chắn đã chạm, và một câu giải thích bằng tiếng Việt dễ hiểu (ví dụ thật,
  golden path THO→DHO hiện tại):
  *"F0=285000đ → MUA_VU:HE(×1.075), ELASTIC:r=1.08(×1.0788) → niêm yết 307000đ
  → cuối 307000đ vs Σbid 0đ ⇒ ACCEPT"*.
- **P5 (ghép nhiều ghế)**: `Offer.seat_plan` giờ là **mảng ≥1 phần tử** (1 =
  same-seat, ≥2 = ghép nhiều ghế); `Offer` có thêm `requires_customer_consent`,
  `change_station_ids`, `so_lan_doi_cho`. `build_offer()` nhận
  `SeatPlan | MergedSeatPlan` — additive, không phá offer same-seat cũ.

### 5.7 `src/backtest/` — phòng thí nghiệm so sánh, tách biệt khỏi DB thật

- **`events.py`**: sinh 5 chuỗi "yêu cầu đặt vé giả lập" cố định (dùng công thức
  xác suất tái lập được từ đúng 1 con số "seed" — chạy lại luôn cho ra cùng kết
  quả), mô phỏng theo hình dạng đường cong đặt vé thật (đặt sớm cho chặng dài,
  sát ngày cho chặng ngắn) lấy từ file cấu hình tham số của bộ dữ liệu lớn,
  nhưng **không đọc trực tiếp dữ liệu 4 GB** — chỉ đọc file cấu hình tham số nhỏ.
- **`seat_matrix.py`**: một phiên bản "ghế × đoạn" **gọn nhẹ, chỉ dùng nội bộ cho
  backtest** (khác với `SeatStateManager` dùng cho API thật) — vì backtest cần
  chạy hàng nghìn yêu cầu trong vài giây, không thể mỗi yêu cầu lại mở giao dịch
  Postgres thật.
- **`engine.py`**: chạy song song 2 chính sách (baseline vs Âu Lạc) trên cùng
  một chuỗi yêu cầu, tính doanh thu, tỷ lệ chấp nhận, tỷ lệ "hết chỗ giả"
  (false sold-out — baseline từ chối nhưng Âu Lạc nhận được), gộp 5 seed lấy
  trung vị + khoảng min/max, và tính `checksum` để báo cáo không thể bị sửa sau
  khi sinh ra mà không bị phát hiện.

---

## 6. Cơ sở dữ liệu (Postgres)

Cấu trúc bảng được quản lý bởi 2 file SQL chạy tuần tự lúc khởi động (Flyway
migration — công cụ đảm bảo mọi môi trường có đúng cùng một cấu trúc DB, chạy
theo đúng thứ tự, không ai được sửa tay trực tiếp trên DB production):

- **`V1__init_schema.sql`**: tạo toàn bộ ~20 bảng theo đặc tả thiết kế ban đầu
  (bao gồm cả những bảng chưa dùng ở MVP như `users`, `promotion`, `waiting_list`
  — dành cho các giai đoạn mở rộng sau).
- **`V2__fix_contract_gaps.sql`**: vá 3 lỗ hổng phát hiện khi review kỹ hợp đồng
  API — thêm cột `matrix_version` toàn cục vào `service_run` (dùng cho CAS ở
  §4.5), đổi sàn/trần giá từ số tuyệt đối (đồng) sang **tỷ lệ trên giá gốc** (vì
  mỗi chặng có giá gốc khác nhau, sàn/trần phải theo tỷ lệ), thêm ràng buộc
  `CHECK`/`UNIQUE` để chính Postgres từ chối dữ liệu sai thay vì phải kiểm tra
  bằng code ứng dụng.

Các bảng quan trọng nhất với luồng nghiệp vụ (tất cả tên bảng/cột giữ tiếng
Việt hoặc thuật ngữ miền — đây là quy ước có chủ đích của dự án):

| Bảng | Vai trò |
|---|---|
| `seat_segment_state` | Trạng thái từng ô (ghế × đoạn): FREE / HELD / SOLD, cùng `version` riêng của ô đó và (nếu đang giữ) `hold_id`, `hold_expires_at`. |
| `service_run` | Một chuyến tàu cụ thể (vd `SE1_2026-06-15_LE`) + `matrix_version` toàn cục dùng cho CAS. |
| `fare_product` | Giá gốc (F0) theo từng cặp ga đi–đến + hạng ghế, có `version` để lịch sử giá không mất khi thay đổi. |
| `pricing_policy` | Chính sách giá đang duyệt: sàn/trần theo tỷ lệ, mức thay đổi tối đa, `policy_version`. |
| `demand_forecast` | Dự báo nhu cầu còn lại theo đoạn, có `forecast_version`. |
| `offer` | Đề xuất giá đã tạo (bất biến), kèm đủ 3 version (matrix/forecast/policy) để có thể truy vết chính xác lúc đó hệ thống "biết" những gì. |
| `seat_hold` | Một lần giữ chỗ — trạng thái ACTIVE/CONFIRMED/EXPIRED/CANCELLED, khóa bằng `idempotency_key` duy nhất. |
| `booking` | Vé đã xác nhận thanh toán, tham chiếu tới `hold_id`. |
| `decision_record` | "Sổ nhật ký" append-only của mọi quyết định định giá (kể cả REJECT) — phục vụ kiểm toán/giải trình. |

---

## 7. Vai trò của từng file/thư mục trong toàn repo

```
au-lac-railway/
├── CLAUDE.md                  Hướng dẫn quy ước dự án cho AI-assistant (không phải code)
├── plan/                      Tài liệu kế hoạch — "hợp đồng" giữa 5 dev, đọc TRƯỚC khi đổi code
│   ├── 00_MASTER_PLAN.md          Kế hoạch vận hành chính: hằng số kịch bản, ai sở hữu file nào
│   ├── AuLac_Railway_Final_Plan_Review.md   Bản hợp đồng đã "khóa cứng" mà master plan tham chiếu
│   ├── BE_INTEGRATION_PLAN.md      Kế hoạch nối các module BE1/BE2/BE3 lại với nhau
│   ├── DEV1..DEV5_*.md             Nhiệm vụ chi tiết từng dev (state/data/pricing/frontend...)
│   └── progress.md                 Nhật ký tiến độ — CHỈ ĐƯỢC THÊM DÒNG, không sửa dòng người khác
├── docs/                       Tài liệu đặc tả hệ thống
│   ├── API_Contract.md             Đặc tả REST API v1 (endpoint, mã lỗi, hình dạng JSON)
│   ├── SDD_Update_Recommendations.md
│   └── *.docx                      Tài liệu thiết kế hệ thống (Word)
├── generated_data/             Bộ mô phỏng dữ liệu 12 tháng — CHỈ để hiệu chỉnh số liệu, không chạm runtime
│   ├── generate_data.py            Script sinh dữ liệu (numpy/pandas/pyarrow), chứa class `Pricer`
│   │                                (logic định giá gốc mà backend/src/pricing "chép lại logic")
│   ├── README_data.md              Giải thích bộ dữ liệu, các điểm lệch chuẩn có chủ đích
│   └── Synthetic_DATA_guide/       4 tài liệu đặc tả TOÁN HỌC của bộ dữ liệu (tham số, công thức)
├── demo/                       Module phân tích dùng lại được (đọc dữ liệu 4GB, cần máy có local data)
│   ├── ssm/ssm_contract.py         "Hợp đồng" trạng thái ghế đông cứng — backend/src/state kế thừa đúng ngữ nghĩa này
│   ├── ssm/seat_state_matrix.py    Bản gốc thao tác ma trận ghế trong bộ nhớ (nguồn cảm hứng cho backend/src/state)
│   ├── build_forecast_features.py Xây đặc trưng dự báo an toàn (không rò rỉ tương lai)
│   └── eda_dataset_for_5_subproblems.py   Tính các con số hiệu chỉnh cho seed/
├── app/ + models/artifacts/    Tier 2 (offline reference) — GIỜ ĐƯỢC LIVE-IMPORT thẳng vào backend
│                                process lúc runtime (P2-P4): app.bt3_allocation (DLP bid), app.elasticity
│                                (optimizer giá), app.bt1_forecast (DemandModel). KHÔNG copy code — backend
│                                Docker context = repo root để thấy được 2 thư mục này (xem backend/ dưới).
├── integration/                Shim nối tier 2 ⇄ tier 3 khi tier 2 cần pandas mà backend/src/ thì cấm:
│   ├── ssm_from_postgres.py        `PostgresSeatStateMatrix` — nạp snapshot Postgres đã convert qua
│   │                                adapter vào interface mà app.bt3_allocation cần (thay dataset 4GB)
│   └── resolver_multiseat.py       Bản tham chiếu port sang backend/src/merging/resolver.py (P5)
└── backend/                    Ứng dụng thật — API + DB (mô tả chi tiết ở §5-6 phía trên)
    ├── docker-compose.yml          Build context = REPO ROOT (`context: ..`) — image thấy được `app/`+`models/artifacts/` để live-import tier 2
    ├── Dockerfile                  Đóng gói backend + app/ + models/artifacts thành container
    ├── requirements.txt            += scikit-learn/joblib (pin đúng version train `bt1_forecast_hgb.joblib`)
    ├── openapi.yaml                Đặc tả API chính thức (nguồn chân lý cao hơn API_Contract.md khi có xung đột)
    ├── flyway/sql/                 2 file SQL tạo/sửa cấu trúc DB (V1, V2) — KHÔNG đổi cho P5 (schema seat_hold vốn đã hỗ trợ nhiều seat/hold_id)
    ├── seed/                       ~50KB dữ liệu khởi tạo kịch bản vàng (xem §2.1, §4.1) — hiệu chỉnh 100% từ dataset thật, không còn số bịa
    ├── scripts/{build_seed,calibrate_seed_from_dataset,calibrate_backtest_lambda,audit_constants}.py   Sinh seed/ + CI gate sweep literal
    ├── src/                        Mã nguồn ứng dụng (chi tiết ở §5) — thêm `allocation/` (cache DLP), `adapters/` (convert 1-based⇄0-based/index/matrix)
    └── tests/                      93 test đơn vị/tích hợp — mỗi module có 1 file test tương ứng

# rules/pricing_rules.yaml đã XÓA (P3) — luật giá không còn khai báo YAML gõ tay,
# thay bằng models/artifacts/bt5_pricing_params.json (mùa vụ) + app/elasticity.py (động)
```

---

## 8. Các bất biến (invariant) mà mọi thay đổi phải tôn trọng

Đây là những quy tắc "bất di bất dịch" — vi phạm sẽ âm thầm phá hỏng tính đúng
đắn hoặc tính minh bạch của hệ thống, dù code vẫn "chạy được":

1. **Dataset 4GB (`generated_data/`) không bao giờ chạm runtime.** Đây vẫn giữ
   nguyên. ⚠️ **Cập nhật quan trọng (P2)**: bất biến CŨ "0 `import pandas` nào
   thực thi lúc request" đã **đổi phạm vi có chủ đích** — `backend/src/` vẫn
   0 dòng `import pandas` theo đúng nghĩa đen (CI gate `grep "import pandas"
   backend/src/` vẫn rỗng), nhưng route `/offers` giờ **live-import thật**
   `app.bt3_allocation` (tier 2, có `import pandas` ở module-level) qua shim
   `integration/ssm_from_postgres.py` để lấy DLP bid-price thật — nghĩa là
   pandas **có** thực thi trong tiến trình request, chỉ không có literal
   `import pandas` nằm trong cây `backend/src/`. Đây là hệ quả **đã chấp nhận**
   khi chốt kiến trúc "import `app/` trực tiếp thay vì copy code" (P0.6/Bước4),
   không phải vi phạm mới lọt lưới.
2. **`_ground_truth/` là "thuốc độc" lúc chạy.** Đây là dữ liệu chỉ dùng để CHẤM
   ĐIỂM (so sánh với đáp án đúng tuyệt đối), không phải để hệ thống "học lỏm" đáp
   án — hệ thống phải tự tính bid-price bằng DLP thật (`app.bt3_allocation`) của
   chính nó, không đọc `_ground_truth/offline_optimum.bid_price`.
3. **CSXH (chính sách xã hội) áp SAU CÙNG, lấy MAX, không cộng dồn.** Đảo thứ tự
   này sẽ vừa sai doanh thu vừa sai quyền lợi hành khách.
4. **Tiền luôn là số nguyên (đồng), không dùng số thực (float)** — số thực có
   sai số làm tròn, phá vỡ khả năng kiểm tra sàn/trần chính xác.
5. **`PricingContext` không bao giờ được nhìn thấy thông tin hành khách nhạy
   cảm** (tuổi, giới tính, số lần tìm kiếm, thiết bị, lịch sử mua...) — bảo đảm
   bằng chính cấu trúc dữ liệu (type), có test riêng kiểm tra điều này, không chỉ
   dựa vào quy ước "ai viết code gì".
6. **Một Offer dùng đúng MỘT bộ 4 version** (matrix/forecast/policy, cộng service_run)
   xuyên suốt — không được lấy version mới hơn giữa chừng pipeline.
7. **Frontend (khi được xây) không bao giờ tự ghép quyết định nghiệp vụ** từ
   nhiều response riêng lẻ (allocation + pricing tách rời) — backend luôn trả
   về MỘT quyết định đã hoàn chỉnh.
8. **Hành khách ưu tiên (P5) không bao giờ nhận phương án ghép nhiều ghế.**
   `priority_passenger=true` ⇒ resolver tự lọc rỗng nhánh multiseat trước khi
   route thấy — không phải một điều kiện UI có thể tắt/bật.
9. **Ghép nhiều ghế bắt buộc có sự đồng ý rõ ràng của khách** trước khi giữ chỗ
   — `POST /holds` từ chối (422 `CONSENT_REQUIRED`) nếu `seat_plan` ≥2 leg mà
   thiếu `consent: true`. Không có "đồng ý ngầm định".

---

## 9. Bảng thuật ngữ Việt–Anh

| Thuật ngữ | Giải thích ngắn |
|---|---|
| **Golden scenario / golden gap** | Kịch bản mẫu cố định dùng để demo; "khoảng trống vàng" là đoạn ghế trống được dựng sẵn để chứng minh gap-merging. |
| **Leg / segment (đoạn/chặng)** | Một đoạn đường giữa 2 ga liền kề trên hành trình tàu (7 đoạn cho 8 ga). |
| **O-D (Origin-Destination)** | Cặp ga đi – ga đến của một hành khách, có thể trải dài qua nhiều đoạn. |
| **Same-seat option (ghép chặng cùng ghế)** | Vé được phục vụ trên một ghế duy nhất suốt hành trình, kể cả khi ghế đó có phần đã bán ở đoạn khác. |
| **Ghép nhiều ghế / multi-seat merge (P5)** | Khi không còn ghế nào trống liên tục suốt hành trình, phủ hành trình bằng ≥2 ghế, đổi chỗ tại ga dừng đủ lâu (≥5'). Luôn cần khách đồng ý rõ ràng, không áp dụng cho hành khách ưu tiên. |
| **DLP bid-price (LP dual)** | Giá sàn cơ hội tính bằng bài toán quy hoạch tuyến tính động (Dynamic LP), lấy giá trị dual — thay cho công thức xấp xỉ cũ trên route sống, từ P2. |
| **Bid-price (giá sàn cơ hội)** | Giá tối thiểu một chỗ ngồi "đáng giá" dựa trên độ khan hiếm dự báo — nếu giá bán thấp hơn tổng bid-price các đoạn, bán sẽ lỗ cơ hội. |
| **Guardrail (rào chắn)** | Giới hạn cứng (sàn, trần, mức thay đổi tối đa) áp lên giá sau khi luật động đã tính, để giá không bao giờ vượt quá biên độ cho phép. |
| **CSXH (chính sách xã hội)** | Giảm giá theo luật cho người cao tuổi/khuyết tật/trẻ em/người có công. |
| **CAS (Compare-And-Swap)** | Kỹ thuật "chỉ ghi đè nếu giá trị vẫn đúng như kỳ vọng" — chống 2 người cùng sửa 1 dữ liệu mà đè mất thay đổi của nhau. |
| **Idempotency key (khóa chống trùng)** | Một mã do client tự sinh gửi kèm request — nếu request bị gửi lại (do mất mạng, thử lại...), server nhận diện và trả về đúng kết quả cũ thay vì thực hiện hành động 2 lần. |
| **DecisionRecord (biên bản quyết định)** | Bản ghi không thể sửa của một lần định giá/chấp nhận/từ chối — phục vụ kiểm toán và giải thích quyết định. |
| **Backtest** | Chạy thử hệ thống trên dữ liệu/yêu cầu giả lập trong quá khứ để đo hiệu quả, không ảnh hưởng dữ liệu thật. |
| **Baseline (B0)** | Mô hình hệ thống bán vé truyền thống dùng để so sánh — không tái sử dụng khoảng trống ghế. |
| **Seed (hạt giống dữ liệu)** | Bộ dữ liệu nhỏ, viết tay theo đặc tả, dùng để khởi tạo một trạng thái demo tất định (không phải dữ liệu ngẫu nhiên thật). |

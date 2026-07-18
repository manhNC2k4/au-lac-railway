# DEV7 — Kế hoạch chi tiết theo pha (mỗi pha = 1 màn hình test được ngay)

> Nguồn gốc: `plan/DEV7_FE_SCREENS_BOOKING.md`. File này chia nhỏ thành các pha sao cho
> **xong mỗi pha là xong trọn 1 màn**, mở đúng URL là test được ngay, không phụ thuộc pha sau.

## Thực trạng (đọc trước khi bắt tay)

Bản gốc DEV7 mô tả **Vite + `features/`** — thực tế repo là **Next.js App Router** (`web/app/**`),
API client đã typed sẵn (`web/src/api/`), nav đã trỏ đủ 5 màn. **4/5 màn đã dựng gần xong**; chỉ
màn "So sánh chiến lược" còn thiếu **khối bằng chứng cả năm (offline)**. Bảng ánh xạ:

| Màn DEV7 | Route thật (Next.js) | File | Trạng thái |
|---|---|---|---|
| Dashboard | `/admin/overview` → `/ops` | `app/ops/page.tsx` | ✅ dựng xong — chỉ verify |
| Ma trận ghế × chặng | `/admin/seat-matrix` → `/ops/seatmap` | `app/ops/seatmap/page.tsx` | ✅ dựng xong (golden gap có highlight) — verify |
| Dự báo – phân bổ | `/admin/analytics` → `/forecast` | `app/forecast/page.tsx` | ✅ dựng xong (3 tab, xử lý bid=0) — verify |
| AI-suggest giá | `/admin/decisions/{id}` | `app/decisions/[decisionId]/page.tsx` | ✅ dựng xong — verify + copy "AI đề xuất" |
| So sánh chiến lược | `/admin/backtest` → `/backtest` | `app/backtest/page.tsx` | ⚠️ **chỉ có khối "sống"; thiếu khối offline cả năm (§6)** |

Kết luận: khối lượng thật còn lại chủ yếu là **Pha 6** (khối offline) + **verify/polish** 4 màn kia.
Đừng viết lại cái đã có (ladder rung #2).

---

## Pha 0 — Chạy được để test (bắt buộc, làm 1 lần)

Không phải "màn", nhưng không có pha này thì không test được pha nào.

**Việc:**
1. Bật backend + DB: `cd backend && docker compose up -d` (Postgres :5432, API :8000).
2. Kiểm tra API sống: `curl "localhost:8000/api/v1/demo/overview?service_run_id=SE1_2026-06-15_LE"` phải trả JSON.
3. Nếu DB rỗng/không có run SE1 (xem invariant "dataset ≠ runtime" đang bị SUSPEND trong `CLAUDE.md`):
   `POST /api/v1/demo/scenarios/{id}/reset` hoặc chạy loader để có dữ liệu golden.
4. Bật FE: `cd web && npm install && npm run dev` → http://localhost:3000.
   FE proxy sang API qua `API_SERVER_URL=http://127.0.0.1:8000` (đã set trong `.env.local`).

**Test:** mở http://localhost:3000/admin/overview thấy KPI có số (không phải skeleton mãi / ErrorState).
**DoD:** cả 5 route `/admin/*` load không lỗi mạng.

---

## Pha 1 — Dashboard (`/admin/overview`)

**Nguồn:** `GET /demo/overview` + `GET /demo/analytics` (cho dải tải theo chặng).
**Trạng thái:** đã dựng. Việc còn lại là **verify từng field khớp DEV7 §2**, sửa nếu lệch.

**Checklist verify (mở `/admin/overview`):**
- [ ] 5 card KPI: `overall_occupancy`, `total_revenue_vnd`, `empty_seat_km`, `passenger_km`, `false_sold_out_rate`.
- [ ] Dải "Tải theo chặng" L1–L7 tô màu theo `occupancy`.
- [ ] `bottlenecks[]` / `underused[]` hiện tên ga (tra từ `segment_id`, API không trả tên).
- [ ] Bảng "Quyết định gần đây" dùng field **`result`** (không phải `action`); link "Chi tiết" sang `/admin/decisions/{id}`.
- [ ] Empty state khi list rỗng (không crash).

**DoD:** số trên card = số trong `curl .../demo/overview`; click 1 dòng decision sang được màn Pha 4.

---

## Pha 2 — Ma trận ghế × chặng (`/admin/seat-matrix`)

**Nguồn:** `GET /demo/seatmap`.
**Trạng thái:** đã dựng (217 dòng), nút "Tìm ghế C01-S017" + auto-scroll + highlight golden gap có sẵn.

**Checklist verify (mở `/admin/seat-matrix`):**
- [ ] Heatmap 40 ghế × 7 leg từ `seats[].states`.
- [ ] 3 trạng thái FREE/HELD/SOLD phân biệt bằng **cả màu lẫn ký tự/pattern** (a11y — màu không phải tín hiệu duy nhất).
- [ ] Ghế `C01-S017` nổi bật: SOLD L1–L2, **FREE L3–L4 (THO→DHO)**, SOLD L5–L7 (golden gap).
- [ ] Nút "Tìm ghế C01-S017" cuộn tới đúng hàng.

**DoD:** nhìn 1 giây thấy ngay khoảng vàng L3–L4 của C01-S017.

---

## Pha 3 — Dự báo nhu cầu – phân bổ chỗ (`/admin/analytics`)

**Nguồn:** `GET /demo/analytics`.
**Trạng thái:** đã dựng, 3 tab: Nhu cầu / Tải / Bid-price.

**Checklist verify:**
- [ ] Tab **Nhu cầu** (`?tab=demand`): `forecasts[].forecast_remaining` + `confidence` (badge màu theo ngưỡng, `null` → "—").
- [ ] Tab **Tải** (`?tab=load`): `segment_loads[].occupancy` + `remaining_capacity`.
- [ ] Tab **Bid-price** (`?tab=allocation`): `allocations[].bid_price_vnd`.
- [ ] **`bid_price_vnd = 0` không bị coi là bug**: phân biệt "cache miss (chưa refresh version)" vs "đoạn không nghẽn" — 2 trạng thái khác nhau, đừng gộp (DEV7 §4). Golden gap có đoạn bid=0 là ĐÚNG.

**DoD:** đổi tab qua URL `?tab=` giữ nguyên state; bid=0 hiển thị có chú thích, không cảnh báo đỏ.

---

## Pha 4 — AI-suggest giá vé (`/admin/decisions/{id}`)

**Nguồn:** `GET /decisions/{decision_id}` (id lấy từ bảng "Quyết định gần đây" ở Pha 1).
**Trạng thái:** đã dựng: 3 tầng giá, bid theo chặng, bảng luật, versions, violations.

**Checklist verify:**
- [ ] 3 tầng giá: `base_fare → ai_suggested_price → final_price` (label "AI đề xuất", **không** "AI quyết định" — khớp định vị sản phẩm, xem memory `ai-suggest-positioning`).
- [ ] `audit_timeline.explanation` hiển thị **nguyên câu**.
- [ ] `audit_timeline.rules_fired[]` sắp đúng thứ tự `thu_tu`, hiện `rule_id` + `he_so`.
- [ ] `bid_price_breakdown` theo chặng + tổng; `versions.{matrix,forecast,policy}`; `violations[]`.
- [ ] **Không tự suy accept/reject** từ so `bid` vs `giá` — dùng thẳng field backend (bất biến #7).

**DoD:** mở 1 decision_id thật từ Pha 1, mọi field render đúng; soát toàn UI không còn chữ "AI quyết định".

---

## Pha 5 — So sánh chiến lược: khối "sống" (`/admin/backtest`)

**Nguồn:** `POST /backtests` → `GET /backtests/{report_id}` (5 seed committed `20260717..20260721`).
**Trạng thái:** đã dựng: chọn seed, chạy, poll RUNNING, bảng theo seed + median/min/max.

**Checklist verify:**
- [ ] Bấm "Chạy so sánh" → poll tới DONE → hiện `baseline_metrics` vs `ai_metrics` (median/min/max).
- [ ] Bảng `raw[seed]`: revenue, acceptance_rate mỗi bên, false_sold_out_rate.
- [ ] Nhãn rõ đây là **"Mô phỏng trực tiếp (5 kịch bản)"**.
- [ ] Số chốt baseline median **18.848.000đ** vs Âu Lạc **23.438.000đ** = **+24,4%**. **KHÔNG dùng "+156%"** (artifact lỗi thời).

**DoD:** bấm nút chạy ra kết quả thật từ backend, nhãn nguồn rõ ràng.

---

## Pha 6 — So sánh chiến lược: khối "bằng chứng cả năm" (offline) — **VIỆC MỚI THẬT SỰ**

Đây là phần **chưa có**. Bổ sung vào cùng màn `/admin/backtest`, **tách khối rõ ràng** với Pha 5.

**Nguồn:** `models/artifacts/backtest_report.json` (file JSON ~3.7KB, **KHÔNG** phải dataset 4GB).

**Việc:**
1. Copy file vào static của FE: `web/public/backtest_report.json` (thêm 1 bước copy vào script build,
   hoặc commit thẳng — nó tĩnh theo thiết kế). **KHÔNG viết endpoint backend mới** để load nó (evidence offline, không phải runtime — xem "Reuse before rewriting" trong `CLAUDE.md`).
2. Fetch tĩnh `/backtest_report.json` (một `fetch` thường, không qua api-client) và render như **trích dẫn tĩnh**.
3. Hiển thị các số: Tết **+2,3% doanh thu**, **89,0% tối ưu offline** (vs FCFS 87,0%), ghế trống cục bộ **−52%**, **MASE 0,515**.
4. Dán nhãn khối: **"Bằng chứng backtest cả năm (ngoại tuyến)"** — đặt cạnh/dưới khối "sống", có gạch phân cách + câu chú thích "hai nguồn số liệu khác nhau, không phải cùng một phép tính" (DEV7 §6 + Luật vàng #3).

**Test:** mở `/admin/backtest`, cuộn xuống thấy khối offline với đúng các con số trên; xác nhận
**hai khối không trộn** (nguồn "sống" = nút chạy, nguồn "offline" = trích dẫn tĩnh).
**DoD:** giám khảo phân biệt được ngay 2 nguồn; số offline khớp `models/artifacts/backtest_report.json`.

---

## Thứ tự đề xuất

`Pha 0` (bắt buộc) → `Pha 6` (việc mới, ưu tiên) → `Pha 1–5` chỉ là **verify/polish** (làm nhanh, song song).

## Bẫy (giữ nguyên từ DEV7)
1. Không tự định nghĩa type response — sinh từ `openapi.yaml` (`src/api/schema.d.ts` đã có).
2. Không đọc `_ground_truth/` hay `generated_data/` cho bất kỳ số nào — chỉ API runtime hoặc `models/artifacts/*.json`.
3. Không chạm `web/app/booking/**`, `web/app/admin/booking-lab/**` hay backend (của DEV6).

## Ghi tiến độ
Append 1 dòng/pha vào `plan/progress.md` kèm bằng chứng (URL chạy được / screenshot / commit sha).

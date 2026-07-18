# DEV7 — Dashboard, Ma trận ghế, Dự báo-Phân bổ, AI-suggest giá, So sánh chiến lược

**Đọc trước:** `CLAUDE.md`, `docs/API_Contract.md` §2, §4 (toàn bộ endpoint bạn dùng đã có sẵn), `docs/TECHNICAL_OVERVIEW.md` §4.1-4.4, §4.8 (luồng end-to-end + backtest).

**Bối cảnh:** 5 màn của bạn đều **read-only** (không tạo offer/hold/booking) và đều đã có API thật, chạy được (`docker compose up -d` rồi gọi thẳng) — không cần viết backend. Đặt vé + duyệt chặng ngắn giờ thuộc về DEV6 (2 màn đó phụ thuộc lẫn nhau nên gộp về 1 người), bạn không cần quan tâm tới field `requires_staff_review`/`review_id` của họ.

---

## Bạn sở hữu

| Đường dẫn | Nội dung | Nguồn dữ liệu |
|---|---|---|
| `web/src/features/dashboard/**` | Dashboard tổng quan | `GET /demo/overview` |
| `web/src/features/seatmap/**` | Ma trận ghế × chặng (heatmap) | `GET /demo/seatmap` |
| `web/src/features/forecast/**` | Dự báo nhu cầu – phân bổ chỗ | `GET /demo/analytics` |
| `web/src/features/pricing/**` | AI-suggest giá vé (giải thích quyết định) | `GET /decisions/{decision_id}` |
| `web/src/features/strategy/**` | So sánh chiến lược cũ/mới | `POST /backtests` + `GET /backtests/{report_id}` (live, 5 seed) **và** `models/artifacts/backtest_report.json` (offline, cả năm — xem §6) |
| `web/src/lib/api-client.ts` | Typed client dùng chung — ai rảnh trước dựng, người kia pull |

**Bạn KHÔNG sở hữu / KHÔNG sửa:** `web/src/features/{short-leg-review,booking}/**`, bất kỳ file backend nào (`backend/src/review/`, `routes_review.py`, hay sửa `routes_offers.py`/`routes_holds.py`) — đó là của DEV6.

**Stack:** React + Vite + TypeScript, giao diện tiếng Việt.

---

## Luật vàng

> **Frontend không tự ghép quyết định kinh doanh từ nhiều response riêng lẻ.** `CLAUDE.md` bất biến #7: backend luôn trả một quyết định đã hoàn chỉnh — bạn hiển thị nguyên, không tự so `bid` vs `giá` để suy ra accept/reject.

> **`bid.total_vnd = 0` cho golden gap là ĐÚNG, không phải bug** (`API_Contract.md` §3.1) — đừng dựng demo kỳ vọng số > 0 mọi đoạn.

> **2 nguồn "so sánh chiến lược" KHÔNG được trộn lẫn** — xem §6. Một cái chạy sống trên seed 5 ngày (runtime), một cái là bằng chứng tĩnh cả năm (offline, tier-2). Nói rõ nguồn nào cho số nào, đừng để trông như cùng một phép tính.

---

## Việc cần làm

### 1. Scaffold `web/` (nếu DEV6 chưa dựng — chỉ 1 người dựng khung, người kia pull)

- [ ] Vite + React + TS + router
- [ ] `api-client.ts` — typed client sinh type theo `backend/openapi.yaml` (nguồn chân lý cao nhất khi xung đột với `API_Contract.md`)
- [ ] Design tokens dùng chung (màu, spacing) — 30 phút, không hơn

### 2. Dashboard

- [ ] Card: `overall_occupancy`, `total_revenue_vnd`, `empty_seat_km`, `passenger_km`, `false_sold_out_rate`
- [ ] Danh sách `bottlenecks[]`/`underused[]` — tự tra tên ga từ `segment_id` (API không trả `name`, dùng bảng tĩnh 8 ga hoặc tra qua `seatmap`)
- [ ] `recent_decisions[]` — chú ý field là **`result`**, không phải `action`

### 3. Ma trận ghế × chặng

- [ ] Heatmap 40 ghế × 7 leg từ `seatmap.seats[].states`
- [ ] 3 trạng thái FREE/HELD/SOLD — **màu không phải tín hiệu duy nhất**, thêm ký tự/pattern (a11y)
- [ ] Ghế `C01-S017` (golden gap) phải nổi bật ngay — tự so `states` với request gần nhất để tô "khoảng vàng" (API không trả field này tĩnh)

### 4. Dự báo nhu cầu – phân bổ chỗ

- [ ] Bảng từ `analytics`: `forecasts[].{forecast_remaining, confidence}`, `segment_loads[].occupancy`, `allocations[].bid_price_vnd`
- [ ] Xử lý rõ trường hợp `bid_price_vnd = 0` (chưa `reset`/`refresh` cho version hiện tại, hoặc đoạn không nghẽn) — 2 trạng thái khác nhau, đừng gộp làm một

### 5. AI-suggest giá vé

- [ ] 3 tầng giá (`base_fare → ai_suggested_price → final_price`) từ `GET /decisions/{id}`
- [ ] `audit_timeline.{explanation, rules_fired[]}` — hiển thị **nguyên câu** giải thích + từng luật theo đúng thứ tự `thu_tu`
- [ ] Luôn frame là **"AI đề xuất"** trong copy UI (không dùng chữ "AI quyết định") — khớp định vị sản phẩm đã chốt

### 6. So sánh chiến lược cũ/mới — 2 nguồn, không trộn

- [ ] **Khối "sống" (runtime):** trigger `POST /backtests`, hiển thị `GET /backtests/{report_id}` — `baseline_metrics`/`ai_metrics` median/min/max + `raw[seed]` (false_sold_out_rate, empty_seat_km, acceptance_rate mỗi bên). Đây là 5 seed committed (`20260717..20260721`), chạy thật lúc bấm nút. Số chốt: baseline median **18.848.000đ** vs Âu Lạc **23.438.000đ** = **+24,4%**. **KHÔNG dùng "+156%"** — artifact kịch bản cũ đã ghi rõ lỗi thời trong `API_Contract.md` §4.2.
- [ ] **Khối "bằng chứng cả năm" (offline, tĩnh):** đọc trực tiếp `models/artifacts/backtest_report.json` (file JSON nhỏ, KHÔNG phải dataset 4GB) và hiển thị như trích dẫn tĩnh — Tết +2,3% doanh thu, 89,0% tối ưu offline (vs FCFS 87,0%), ghế trống cục bộ −52%, MASE 0,515. Copy file này vào `web/public/` lúc build hoặc fetch qua static route — **không** viết endpoint backend mới để "load" nó (đây là evidence offline cho pitch, không phải dữ liệu runtime — xem bảng "Reuse before rewriting" trong `CLAUDE.md`).
- [ ] UI phải dán nhãn rõ 2 khối khác nguồn (vd "Mô phỏng trực tiếp (5 kịch bản)" vs "Bằng chứng backtest cả năm (ngoại tuyến)") — đừng để giám khảo tưởng nhầm là cùng một con số.

### Definition of Done

- Cả 5 màn chạy với dữ liệu thật từ API, không hard-code số (trừ khối offline ở mục 6, vốn dĩ tĩnh theo thiết kế).
- Màn so sánh chiến lược phân biệt rõ ràng 2 nguồn số liệu.

---

## Bẫy dành riêng cho bạn

1. Đừng tự định nghĩa type response trong FE — sinh từ `openapi.yaml`. Contract đổi ⇒ sinh lại.
2. Đừng đọc `_ground_truth/` hay `generated_data/` trực tiếp cho bất kỳ số nào — chỉ dùng API runtime hoặc `models/artifacts/*.json` đã tính sẵn.
3. Đừng chạm `web/src/features/{short-leg-review,booking}/**` hay bất kỳ file backend nào — kể cả khi tiện tay.

---

## Ghi `plan/progress.md`

Append 1 dòng mỗi mục xong, `✅ DONE` kèm bằng chứng (URL chạy được/screenshot/commit sha). Component dùng chung (`api-client.ts`) xong ⇒ ghi ngay + tag DEV6.

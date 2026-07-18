# DEV6 — Duyệt vé chặng ngắn (thông báo → A/B → lựa chọn nhân viên) + Đặt vé (user)

**Đọc trước:** `CLAUDE.md` (bất biến toàn repo), `docs/API_Contract.md` §2-3 (offer/hold/decision hiện có), `docs/TECHNICAL_OVERVIEW.md` §4.2-4.6 (luồng `/offers`→`/holds`→`/confirm` thật).

**Bối cảnh:** Bạn giờ ôm **cả 2 đầu** của một luồng — màn duyệt của nhân viên (admin) và màn đặt vé của khách (user) — vì 2 màn này phụ thuộc chặt vào nhau (khách đặt chặng ngắn ghép khoảng trống ⇒ phải chờ đúng cái mà màn duyệt tạo ra). Gộp về 1 người sở hữu để khỏi cần "hợp đồng liên-dev" cho phần này — bạn tự quyết định tên field, tự đổi cả 2 phía cùng lúc, không phải chờ ai duyệt tên biến.

Vị trí duyệt KHÔNG tồn tại trong code hiện tại (đã grep `backend/src` cho `duyet|approval|notification|pending_review` → 0 kết quả). `POST /offers` hiện tự động trả `decision: ACCEPT|REJECT`, khách có thể đi thẳng `/holds`→`/confirm` không qua ai duyệt — bạn thêm 1 lớp duyệt chỉ cho các trường hợp chặng ngắn ghép khoảng trống, đúng định vị sản phẩm "AI đề xuất, nhân viên quyết" (giai đoạn "thử nghiệm có kiểm soát với sự phê duyệt thủ công" trong pitch).

---

## Bạn sở hữu

| Đường dẫn | Nội dung |
|---|---|
| `backend/src/review/` (mới) | Logic xác định "cần duyệt", tạo bản ghi review, quyết định của nhân viên |
| `backend/flyway/sql/V6__review_queue.sql` (mới — xác nhận V5 là bản mới nhất trước khi đặt tên) | Bảng `booking_review` |
| `backend/src/api/routes_review.py` (mới) | `GET /reviews`, `GET /reviews/{id}`, `POST /reviews/{id}/decide` |
| `backend/src/api/routes_offers.py`, `routes_holds.py` (SỬA, không phải file mới) | 1 lời gọi thêm sau khi tạo offer + 1 guard đầu `/holds` — xem §Tích hợp nội bộ |
| `web/src/features/short-leg-review/**` (mới) | Bell/danh sách thông báo, màn so sánh A/B, nút quyết định (admin) |
| `web/src/features/booking/**` (mới) | Đặt vé: chọn ghế, ghép chặng, trạng thái chờ duyệt (user) |

**Bạn KHÔNG sở hữu / KHÔNG sửa:** logic tính giá/bid bên trong `pricing/`, `merging/`, `forecast/`, `state/` — chỉ được **đọc** kết quả offer đã tạo để hiển thị, không viết lại công thức. `web/src/features/{dashboard,seatmap,forecast,pricing,strategy}/**` (DEV7).

**Stack:** Backend Python/FastAPI khớp convention có sẵn (psycopg thuần, không ORM). Frontend React + Vite + TypeScript, giao diện tiếng Việt, dùng chung design system với DEV7.

---

## Luật vàng

> **Không đổi thứ tự/logic pipeline `/offers` gốc.** Chỉ thêm 1 lời gọi sau khi `OfferService.build_offer` đã trả kết quả — không viết lại công thức giá hay bid.

> **Vế "baseline sẽ từ chối" phải tính thật, không bịa câu văn tĩnh.** Gọi lại `merging.resolver.continuous_same_seat` nhưng loại các ghế có `reused_gap=true` khỏi ứng viên (baseline không tái dùng khoảng trống) — nếu rỗng thì đúng là baseline từ chối thật.

> **Vì bạn sở hữu cả 2 màn, không có "hợp đồng đóng băng" nào cần người khác duyệt ở đây** — nhưng vẫn viết field/API ra giấy trước khi code 2 màn song song với chính mình, để không tự mâu thuẫn giữa BE bạn viết sáng nay và FE bạn viết chiều nay.

---

## Tích hợp nội bộ: offer → review → holds (đọc kỹ trước khi code cả 2 màn)

Chặn ở **`/holds`**, không phải `/offers` (offer vẫn là quote 5 phút, vô hại dù có cần duyệt hay không).

1. `POST /offers` — sau khi build xong, nếu offer ACCEPT + `seat_plan[].reused_gap==true` + `loai_hanh_trinh=="ngan"` (tái dùng enum có sẵn ở P7.2) → insert `booking_review` status `PENDING`, response offer thêm 2 field additive: `requires_staff_review: bool`, `review_id: string|null`.
2. Màn **booking** (user): nếu `requires_staff_review=true` → hiện "Đang chờ nhân viên duyệt", poll `GET /reviews/{review_id}` mỗi 3–5s cho tới khi `status=DECIDED`.
3. Màn **review** (admin): bell/danh sách poll `GET /reviews?status=PENDING`, click vào 1 review → màn A/B (baseline vs AI, dữ liệu lấy nguyên từ offer đã lưu, không tính lại) → nhân viên bấm chọn → `POST /reviews/{id}/decide`.
4. `POST /holds` — thêm guard đầu hàm: nếu offer có `review_id` và review chưa ở trạng thái `DECIDED(chosen=AI)` → `422 REVIEW_PENDING` (mã lỗi mới trong `state/errors.py`). Đây là lớp phòng thủ (khách F5 lúc đang chờ vẫn không giữ ghế được) — luồng chính là bước 2 tự không gọi `/holds` khi đang chờ.
5. Sau `DECIDED`: `chosen=AI` → màn booking tự động gọi `/holds` bằng `offer_id` gốc, tiếp tục bình thường. `chosen=BASELINE` → hiện từ chối, không gọi `/holds`.
6. **Polling, không WebSocket.** Backend không có hạ tầng push nào (mỗi request tự mở kết nối DB riêng — `deps.py`), và tính năng gần nhất (`waitlist/match`) đã tự nhận bằng comment có sẵn "ops-trigger tường minh, không worker nền". `# ponytail: polling 3-5s cho cả bell (bước 3) và trạng thái chờ (bước 2), nâng cấp SSE/WebSocket nếu sau này nhiều điều độ viên theo dõi đồng thời thật.`
7. ⚠️ **Ceiling cố ý chấp nhận, không phải bug:** offer hết hạn 5 phút không đổi vì có review. Duyệt chậm hơn 5 phút ⇒ `/holds` trả `410 OFFER_EXPIRED` dù `chosen=AI`. Không tự chế cơ chế gia hạn cho demo — chỉ cần lỗi hiển thị rõ ở màn booking.

---

## Việc cần làm

### 1. Backend — bảng + tiêu chí + gate

- [ ] Migration `V6__review_queue.sql`: bảng `booking_review` (`review_id`, `offer_id` FK, `service_run_id`, `status PENDING|DECIDED`, `ai_decision`, `baseline_would_reject bool`, `chosen NULL|AI|BASELINE`, `decided_by`, `created_at`, `decided_at`).
- [ ] Hàm xác định "cần duyệt" trong `routes_offers.py` (1 lời gọi thêm, xem §Tích hợp bước 1).
- [ ] Hàm tính vế baseline (đúng Luật vàng), lưu `baseline_would_reject`.
- [ ] Guard `REVIEW_PENDING` trong `routes_holds.py` (§Tích hợp bước 4) + mã lỗi mới trong `state/errors.py`.

### 2. Backend — API

- [ ] `GET /reviews?service_run_id=...&status=PENDING` → danh sách chờ duyệt (offer_id, origin/dest, giá, explanation, baseline_would_reject).
- [ ] `GET /reviews/{review_id}` → 1 review đơn lẻ (dùng để màn booking poll).
- [ ] `POST /reviews/{review_id}/decide` — body `{chosen: "AI"|"BASELINE", decided_by}`, role gate `X-Actor-Role: revenue_manager|admin` (giống pattern `POST /offers/{id}/override` P7.6). Ghi `proposal_log` qua `audit/log.py::persist` có sẵn.
- [ ] Cập nhật `backend/openapi.yaml` + `docs/API_Contract.md`.

### 3. Frontend — màn duyệt (admin)

- [ ] Bell/badge số lượng `PENDING`, poll `GET /reviews`.
- [ ] Click → 2 cột: "Baseline" (nếu `baseline_would_reject=true` hiện "Hết chỗ"; nếu false thì ẩn — không có gì để so sánh, không tạo review giả) vs "AI" (giá 3 tầng + `explanation` + `rules_fired` nguyên từ offer).
- [ ] 2 nút quyết định gọi `POST /reviews/{id}/decide`.

### 4. Frontend — màn đặt vé (user)

- [ ] Form O-D → `POST /offers` → hiển thị `seat_plan`, giá, hạn dùng (`expires_at`).
- [ ] `requires_customer_consent=true` (ghép nhiều ghế, P5): **bắt buộc** disclosure (`so_lan_doi_cho`, `change_station_ids`, từng leg) trước khi tiếp tục — chỉ gọi `/holds` với `consent:true` sau khi khách bấm đồng ý (bất biến #9 `CLAUDE.md`).
- [ ] `requires_staff_review=true`: hiện "Đang chờ nhân viên duyệt", poll theo §Tích hợp bước 2, tự chuyển tiếp khi `DECIDED`.
- [ ] Map error code → tiếng Việt: `NO_SAME_SEAT_OPTION`, `SOLD_OUT_TRUE`, `STALE_SNAPSHOT`(409), `SEAT_CONFLICT`(409), `OFFER_EXPIRED`/`HOLD_EXPIRED`(410), `POLICY_UNAVAILABLE`(503), `ALLOCATION_REJECTED`, `CONSENT_REQUIRED`(422), `REVIEW_PENDING`(422, mới).

### Definition of Done

- Demo được đúng câu chuyện end-to-end bằng chính user: khách đặt THO→DHO (hoặc leg tương tự golden gap) → thấy "đang chờ duyệt" → (song song, màn admin) nhân viên thấy thông báo → mở A/B → chọn AI → khách tự chuyển sang giữ chỗ → xác nhận thanh toán thành công.
- ≥1 file test mới (`backend/tests/test_review.py`) theo convention "mỗi module có 1 file test".
- 4 version (`service_run_id`, `matrix_version`, `forecast_version`, `policy_version`) hiển thị được ở màn đặt vé — bất biến trung tâm của repo.

---

## Bẫy dành riêng cho bạn

1. Đừng viết lại công thức giá/bid — chỉ đọc kết quả offer đã có.
2. Review-queue chỉ chặn các offer rơi đúng diện chặng ngắn ghép khoảng trống — mọi offer khác đi thẳng `/holds` như cũ, đừng biến guard thành chặn toàn bộ.
3. `X-Actor-Role` chỉ là header check thô (tiền lệ `ponytail` trong `state/errors.py::Forbidden`) — không tự chế RBAC/JWT thật.
4. Đừng tự định nghĩa type response 2 lần (1 cho màn admin, 1 cho màn booking) — dùng chung 1 type sinh từ `openapi.yaml` cho field `requires_staff_review`/`review_id`.

---

## Ghi `plan/progress.md`

Append 1 dòng khi xong mỗi mục, `✅ DONE` kèm bằng chứng chạy được (lệnh test + output, hoặc URL), `⛔ BLOCKED` ghi rõ chờ ai.

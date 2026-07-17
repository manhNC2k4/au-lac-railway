# FE1 — Frontend nền tảng + Ops (S01, S02, S05, S06)

**Đọc trước:** `00_MASTER_PLAN.md` (bắt buộc — §0, §5.2, §7.1).
**Bạn xây nền cho cả 2 frontend. FE2 dùng component + client của bạn ⇒ giao sớm, đừng cầu toàn.**

---

## Bạn sở hữu

| Đường dẫn | Nội dung |
|---|---|
| `web/src/api/` | Typed client sinh từ `openapi.yaml` + fixture adapter |
| `web/src/components/` | Design system dùng chung — **FE2 phụ thuộc** |
| `web/src/pages/ops/` | S01 Ops Overview, S02 Seat-Leg Matrix |
| `web/src/pages/decision/` | S05 Decision Detail, S06 Compliance Panel |

**Bạn KHÔNG sở hữu:** `web/src/pages/booking/`, `web/src/pages/backtest/` (FE2). Không sửa.

**Stack:** React + Vite + TypeScript. **Giao diện tiếng Việt** (đề bài Mục 15).

---

## Luật vàng của frontend

> **Frontend KHÔNG tự ghép response của Allocation / Merging / Pricing thành quyết định kinh doanh.**
> Backend trả quyết định **đã hoàn chỉnh**; bạn **hiển thị** nó. Nếu thấy mình đang viết `if (bid > price) reject`, dừng lại — đó là việc của BE3.

> **Typed client SINH từ contract đã freeze. KHÔNG tự định nghĩa shape trong frontend.** Contract đổi ⇒ sinh lại. Tự gõ type = trôi contract, phát hiện lúc giờ 14.

---

## Nhiệm vụ theo giờ

### H0–H2 · Khung + mock client

- [ ] Vite + React + TS + router, khung route **S01–S06**
- [ ] **Typed mock client** — đọc `seed/` JSON, cùng shape với `openapi.yaml`
- [ ] Xác nhận danh sách S01–S06 với BE1 (Master §5.2)
- [ ] Design tokens: màu, spacing, typography. **30 phút, không hơn.**

> BE1 freeze `openapi.yaml` giờ 2. Trước đó dùng mock theo shape bạn *nghĩ*; giờ 2 sinh lại từ contract thật. Đừng ngồi chờ.

### H2–H6 · Tracer bullet — chạy hoàn toàn bằng fixture

- [ ] **S02 Seat-Leg Matrix** — heatmap 40 ghế × 7 leg. Màn hình khó nhất của bạn, làm trước.
- [ ] **S01 Ops Overview** — LF theo leg, alerts, versions, last_updated
- [ ] Decision panel (khung S05)
- [ ] **Gate giờ 6: fixture `offer→hold→confirm` chạy trong UI** (cùng BE1 + FE2)

#### S02 — heatmap, làm cho đúng

```
        L1   L2   L3   L4   L5   L6   L7
C01-S016 ▓    ▓    ░    ░    ░    ░    ░
C01-S017 ▓    ▓    ·    ·    ▓    ▓    ▓   ← GOLDEN GAP (L3,L4 FREE)
C01-S018 ░    ░    ░    ▓    ▓    ░    ░
         ▓ SOLD   ▒ HELD   ░ FREE   · gap ghép được
```

- [ ] 3 trạng thái `FREE | HELD | SOLD` + highlight `reused_gap`
- [ ] **Legend bắt buộc.** Màu **không được là tín hiệu duy nhất** — dùng thêm ký tự/pattern. Đây là a11y **và** là yêu cầu NFR, không phải nice-to-have.
- [ ] Golden gap `C01-S017` phải **nhìn thấy ngay** — đó là toàn bộ câu chuyện demo. Giám khảo phải "à!" trong 2 giây.

### H6–H10 · Hoàn thiện states

- [ ] Mọi trạng thái: `loading / empty / stale / conflict / expired / clamped / no-option / confirmed`
- [ ] Mỗi state có **retry/action rõ ràng** — không có ngõ cụt
- [ ] Map error code → tiếng Việt dễ hiểu (dùng chung với FE2):

| Code | Hiển thị |
|---|---|
| `NO_SAME_SEAT_OPTION` | Không tìm được chỗ liên tục cho hành trình này |
| `SOLD_OUT_TRUE` | Đã hết chỗ |
| `STALE_SNAPSHOT` (409) | Dữ liệu đã thay đổi — tải lại |
| `SEAT_CONFLICT` (409) | Chỗ vừa được người khác giữ |
| `OFFER_EXPIRED` / `HOLD_EXPIRED` (410) | Đề nghị/giữ chỗ đã hết hạn |
| `POLICY_UNAVAILABLE` (503) | Chính sách giá chưa sẵn sàng |
| `ALLOCATION_REJECTED` | Từ chối theo quota |

### H10–H14 · Integration

- [ ] Thay fixture adapter → API thật, **từng module một** (BE1 điều phối)
- [ ] **Gate giờ 14:** heatmap cập nhật thật sau confirm

### H14–H18 · S05 + S06 — feature freeze H18

- [ ] **S05 Decision Detail** — price breakdown (`gia_goc → gia_niem_yet → gia_cuoi`), bid, **rule đã bắn theo thứ tự**, violations, 4 versions, input_hash
- [ ] **S06 Compliance Panel** — **"0 vi phạm"** sàn/trần + CSXH

> **S06 là màn hình đề bài chấm trực tiếp** (doc `03` §13 khuyến nghị #9). Nó nhỏ nhưng ăn điểm. Đừng để nó xuống cuối rồi cắt.

> **S05 là XAI thật của bài này** — giải thích = liệt kê luật đã bắn, không cần SHAP. Hiển thị chuỗi rule + hệ số + thứ tự áp. Nói được điều này là ăn điểm Mục 9/15.

### H18–H23 · Stabilize

- [ ] Accessibility: keyboard nav, contrast, legend
- [ ] Error-state polish
- [ ] **Smoke test 3/3 dưới 90 giây mỗi lần** (cùng BE1)

---

## NFR của bạn

- [ ] Heatmap có legend; **màu không là tín hiệu duy nhất**
- [ ] Keyboard + contrast cơ bản
- [ ] Empty / stale / conflict / expired / failed đều có retry/action
- [ ] Golden path **3/3, < 90 giây/lần**

---

## Bẫy dành riêng cho bạn

1. **Đừng ghép quyết định ở frontend** — xem Luật vàng.
2. **Đừng tự gõ type** — sinh từ `openapi.yaml`.
3. **4 versions phải hiển thị** (`service_run_id`, `matrix_version`, `forecast_version`, `policy_version`). Đây là bất biến trung tâm — giám khảo sẽ hỏi "làm sao biết offer này nhất quán?" và câu trả lời là màn hình của bạn.
4. **Đừng chờ API thật.** Fixture adapter cho tới giờ 14. Nếu API chưa sẵn giờ 10 → **giữ fixture**, đó là fallback đã khóa.
5. **Màu không là tín hiệu duy nhất** — vừa a11y vừa NFR. Rẻ nếu làm từ đầu, đắt nếu retrofit giờ 20.
6. **FE2 chờ component của bạn** ⇒ giao sớm, xấu cũng được, polish sau. Block FE2 = mất 2 người.

---

## ⭐ Ghi `progress.md`

```markdown
| H+06 | FE1 | S02 heatmap fixture | ✅ DONE | `npm run dev` → localhost:5173/ops · golden gap hiện đúng | FE2 (dùng SeatGrid) |
```

- `✅ DONE` **phải** có bằng chứng: screenshot path, URL chạy được, hoặc commit sha.
- **Component dùng chung xong ⇒ ghi ngay + tag FE2.**
- `⛔ BLOCKED` phải ghi chờ ai/chờ gì. Block > 30' ⇒ báo BE1.
- Checkpoint H2/6/10/14/18/23/26/30: ghi 1 dòng dù không có gì mới.

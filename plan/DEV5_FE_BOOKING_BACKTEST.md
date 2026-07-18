# FE2 — Frontend luồng bán + Pitch (S03, S04) + Evidence

**Đọc trước:** `00_MASTER_PLAN.md` (bắt buộc — §0, §2.8, §5.2, §9).
**Bạn sở hữu màn hình ăn tiền của demo (S03) và toàn bộ pitch. Nếu S03 không chạy, cả bài không có gì để trình bày.**

---

## Bạn sở hữu

| Đường dẫn | Nội dung |
|---|---|
| `web/src/pages/booking/` | **S03 Booking Lab** |
| `web/src/pages/backtest/` | **S04 Backtest Comparison** |
| `pitch/` | Video, screenshots, Q&A, architecture narrative, AI collaboration log |

**Bạn KHÔNG sở hữu:** `web/src/api/`, `web/src/components/`, `web/src/pages/ops/`, `web/src/pages/decision/` (FE1). Cần đổi component dùng chung ⇒ nhờ FE1, đừng tự sửa.

---

## Luật vàng của frontend

> **Frontend KHÔNG tự ghép response của Allocation / Merging / Pricing thành quyết định kinh doanh.**
> Backend trả quyết định đã hoàn chỉnh; bạn hiển thị nó. `if (bid > price) reject` ở frontend = sai kiến trúc.

---

## Nhiệm vụ theo giờ

### H0–H2 · Wireframe bằng fixture

- [ ] S03 Booking Lab wireframe — chạy hoàn toàn bằng `seed/` JSON
- [ ] S04 Backtest Comparison wireframe
- [ ] Thống nhất với FE1: bạn dùng component nào của họ (thỏa thuận **giờ 0**, đừng để giờ 10 mới phát hiện trùng)

> FE1 chưa giao component ⇒ dùng thẻ HTML thô. Thay sau. **Đừng chờ, đừng tự viết component dùng chung** (sẽ trùng với FE1).

### H2–H6 · S03 Booking Lab — làm trước, làm kỹ

**Đây là màn hình quyết định thắng thua.** Kịch bản golden phải chạy mượt:

```
Nhập: THO → DHO, ngày 2026-06-15, 1 khách, NGOI_MEM_DH
  ↓  POST /offers
Hiện: seat plan (C01-S017, leg L3+L4)
      giá: gia_goc → gia_niem_yet → gia_cuoi   (đủ 3 mức)
      bid price từng leg + tổng
      decision: ACCEPT
      expiry đếm ngược
      4 versions
  ↓  POST /holds   (Idempotency-Key + expected_matrix_version)
Hiện: HELD — giá KHÓA, không đổi
  ↓  POST /bookings/{hold_id}/confirm
Hiện: CONFIRMED — giá y hệt lúc hold
      → heatmap S02 của FE1 cập nhật
```

- [ ] **Gate giờ 6:** fixture `offer → hold → confirm` chạy trong UI (cùng BE1 + FE1)
- [ ] Hiển thị **rõ ràng** rằng giá **không đổi** qua offer → hold → confirm. Đây là bằng chứng "khóa giá sau khi giữ chỗ" — một trong 3 test lên slide.

> **Nút "so sánh baseline"**: cùng request `THO→DHO`, baseline **TỪ CHỐI** (`ALLOCATION_REJECTED`), Âu Lạc **PHỤC VỤ** trên cùng một ghế qua 2 leg. **Đây là toàn bộ luận điểm của bài.** Nếu chỉ làm được 1 màn hình, làm cái này.

### H6–H10 · States

- [ ] Mọi trạng thái: `accept / reject / clamped / conflict / expired / confirmed / no-option`
- [ ] Dùng bảng error code → tiếng Việt **của FE1** (đừng viết bản thứ 2)
- [ ] Đếm ngược expiry → hết hạn hiện `OFFER_EXPIRED` (410) với action rõ ràng

### H10–H14 · Integration

- [ ] Fixture → API thật (BE1 điều phối thứ tự)
- [ ] **Gate giờ 14:** S03 chạy real offer → hold 2 leg nguyên tử → confirm

### H14–H18 · S04 Backtest — feature freeze H18

- [ ] Baseline vs Âu Lạc, **5 seed**
- [ ] Hiện **median + min/max + raw result từng seed**
- [ ] **Failed seed PHẢI hiển thị**, không được ẩn. Giấu 1 seed fail = mất uy tín cả bài.
- [ ] Metric có **đơn vị + mẫu số**: false sold-out, empty seat-km, passenger-km, revenue, acceptance rate

### H23–H26 · Pitch — trách nhiệm riêng của bạn

- [ ] **Video backup** (bắt buộc xong **giờ 26** — live demo lỗi thì đây là cứu cánh)
- [ ] Screenshots
- [ ] Architecture narrative
- [ ] **AI collaboration log**
- [ ] Q&A prep — xem §Q&A dưới

### H26–H30

- [ ] H26–28: dress rehearsal, fix **tối đa 1** blocker, chạy lại toàn bộ smoke
- [ ] H28–30: đóng gói source/seed/docs/video, checksum, submit (cùng BE1). **Cấm refactor.**

---

## ⭐ Q&A — chuẩn bị TRƯỚC, giám khảo chắc chắn hỏi

### "Sao không dùng dữ liệu thật?"

> Dữ liệu vé là dữ liệu kinh doanh của VNR, **không công khai**. Nhóm đã hiệu chuẩn theo **18 mô men công bố chính thức** của VNR/Traravico và tái tạo **nguyên vẹn bộ luật giá hiện hành** + **các sự kiện gián đoạn có thật** (lũ 11/2025). Đồng thời cung cấp `_ground_truth` cho phép **đánh giá phản thực** — điều dữ liệu thật **không** cho phép.
>
> Với bài toán tối ưu tồn kho–giá, dữ liệu lịch sử thật **một mình nó không đủ**: nó chỉ chứa kết quả của **một** chính sách. Muốn biết chính sách khác tốt hơn bao nhiêu, **bắt buộc** phải có môi trường phản thực. Simulator được hiệu chuẩn nghiêm ngặt **không phải giải pháp thay thế dữ liệu thật — nó là thành phần bắt buộc của lời giải.**

### "Mô men M8b / M9 lệch biên?" — họ sẽ tìm ra, nói trước đi

Trả lời **thẳng**, đừng vòng vo (Master §2.8):

> Đúng. `README_data.md` ghi rõ và nhóm **chấp nhận có chủ đích** sau 2 vòng hiệu chuẩn:
> - **M8b = 1,201** (target 1,39, lệch −13,6%)
> - **M9 = 0,655** (target 0,79, lệch −17,1%)
>
> Nguyên nhân: **M8b bị chặn cấu trúc** — sức chứa Tết bind làm cầu chặng dài bị từ chối, mix bán không dịch đủ. Knob để chỉnh đã ghi trong README (`Demand.lam`, `aug_tet_runs`, `aug_base_runs`).
> **Không ảnh hưởng golden path** — demo chạy 15/06/2026, không phải Tết.

> **Trung thực là điều kiện sống còn về liêm chính khoa học** (doc `03` §10.1). Một dataset tổng hợp *được hiệu chuẩn công khai và kiểm chứng được* **đáng tin hơn nhiều** so với dataset tự nhận là "thật" mà không ai xác minh được. Nói trước còn hơn để giám khảo tìm ra.

### "8 ga? SE1 dừng 22 ga mà?"

> Demo gộp còn 8 ga / 7 leg cho heatmap đọc được trên 1 màn hình. **Lý trình từng ga là số thật** (`04_THAM_SO_CAU_HINH_MO_PHONG.yaml`, đối chiếu công lệnh VNR — Ga Đà Nẵng Km 791+400). Giá theo `κ·d^θ` vẫn đúng. 40 ghế (SE1 thật 448 chỗ) cũng là thu nhỏ có chủ đích.

### "AI định giá có phân biệt đối xử không?"

> Không, và chúng tôi **chứng minh bằng test, không bằng lời hứa**:
> - `test_price_invariant_to_repeated_search` — tìm 1 lần hay 50 lần, **giá y hệt**
> - `test_price_locked_after_hold` — khóa giá sau khi giữ chỗ
> - `test_pricing_features_exclude_sensitive` — `PricingContext` **không thấy** `user_id`, `so_lan_tim_kiem`, `thiet_bi`, `ip`, `tuoi`, `lich_su_mua`
>
> Giảm CSXH áp **SAU** giảm động, dùng **`max` không cộng dồn** — đúng **Điều 40 NĐ 16/2026/NĐ-CP**. Dashboard S06 hiển thị **"0 vi phạm"**.

### "Bid price tính thế nào? Có phải EMSR-b?"

> **Không.** Gọi đúng tên: **demo bid-price approximation**. Công thức: `pressure → scarcity → bid = round_to_1k(yield × km × scarcity)`. Có version + fixtures. Chúng tôi **không** claim EMSR-b vì chưa chứng minh được.
> Nền tảng lý thuyết: ma trận incidence **totally unimodular** (hành trình phủ các đoạn liên tiếp) ⇒ LP relaxation **đã nguyên** ⇒ HiGHS giải 1 chuyến **< 10 ms** ⇒ p95 < 200 ms là **có chứng minh**, không phải hy vọng.

### "XAI đâu?"

> S05 Decision Detail: **giải thích = liệt kê luật đã bắn** + hệ số + thứ tự áp + ràng buộc chạm. **Không cần SHAP** — rule engine khai báo *chính là* audit trail và *chính là* lời giải thích. Đây cũng là "nhật ký quyết định/phê duyệt" đề bài yêu cầu ở Mục 9 & 15.

---

## Bẫy dành riêng cho bạn

1. **Video backup xong giờ 26 — không phải giờ 29.** Live demo lỗi sau giờ 23 là rủi ro "chắc chắn xảy ra" trong plan gốc. Video là fallback đã khóa.
2. **Đừng tự viết component dùng chung** — FE1 sở hữu. Trùng = conflict lúc merge.
3. **Đừng ghép quyết định ở frontend.**
4. **Failed seed phải hiện** ở S04. Giấu = mất uy tín toàn bài.
5. **S03 quan trọng hơn S04.** Hết thời gian thì cắt S04 xuống bảng tĩnh, **không** cắt S03.
6. **Giá phải nhìn thấy là không đổi** qua offer → hold → confirm. Đó là bằng chứng, không phải chi tiết UI.
7. **AI collaboration log** — ghi **dần từ giờ 0**, đừng bịa lại lúc giờ 25.

---

## ⭐ Ghi `progress.md`

```markdown
| H+06 | FE2 | S03 fixture offer→hold→confirm | ✅ DONE | screenshot pitch/s03_h6.png · gate H6 đạt | — |
| H+26 | FE2 | video backup | ✅ DONE | pitch/demo_backup.mp4 (4:12) | — |
```

- `✅ DONE` **phải** có bằng chứng: screenshot path, URL, hoặc commit sha.
- `⛔ BLOCKED` phải ghi chờ ai/chờ gì. Block > 30' ⇒ báo BE1.
- Checkpoint H2/6/10/14/18/23/26/30: ghi 1 dòng dù không có gì mới.
- **Giờ 26 không có video ⇒ ghi `⛔` và báo cả đội ngay.** Đây là mốc không được trượt.

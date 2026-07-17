# progress.md — Nhật ký tiến độ 30 giờ

**T0 = <điền lúc bắt đầu>** · Mọi giờ ghi dạng `H+xx` (tính từ T0).

## Luật ghi (đọc 1 lần, tuân thủ 30 giờ)

1. **Xong mục nào → append NGAY.** Không để cuối ngày. Không ghi = coi như chưa xong.
2. **Append xuống cuối. KHÔNG sửa dòng người khác.** Sửa dòng mình thì được (WIP → DONE).
3. **`✅ DONE` phải có bằng chứng chạy được**: lệnh test + output, commit sha, screenshot path, hoặc URL. *"Xong rồi"* không phải bằng chứng.
4. **`⛔ BLOCKED` phải ghi chờ ai / chờ cái gì.** Block > 30 phút ⇒ báo BE1 ngay, đừng ngồi chờ.
5. **Đổi contract** ⇒ dòng `⚠️ CONTRACT CHANGE` + impact list + tag owner liên quan. **BE1 phải duyệt.**
6. **Checkpoint (H2, H6, H10, H14, H18, H23, H26, H30): MỌI dev ghi 1 dòng**, kể cả khi không có gì mới.

Trạng thái: `✅ DONE` · `🚧 WIP` · `⛔ BLOCKED` · `⚠️ CONTRACT CHANGE` · `❌ CUT` (bỏ, ghi lý do)

---

## Nhật ký

| Giờ | Dev | Mục | Trạng thái | Bằng chứng | Unblock ai |
|-----|-----|-----|-----------|-----------|-----------|
| H+00 | — | Kickoff | 🚧 WIP | 5 file plan đã đọc | — |

<!-- Append dòng mới ngay dưới đây. Ví dụ:
| H+02 | BE1 | contract freeze v1.0 | ✅ DONE | `git show a1b2c3` · openapi.yaml 8 endpoints + canonical examples | BE2,BE3,FE1,FE2 |
| H+03 | BE2 | seed/ prior commit | ✅ DONE | `git show d4e5f6` · 7 file · golden gap C01-S017 verified | BE1,BE3,FE1,FE2 |
| H+06 | BE3 | continuous_same_seat | ✅ DONE | `pytest tests/test_merging.py -q` → 8 passed | FE1 (S02) |
| H+07 | BE1 | atomic hold CAS | ⛔ BLOCKED | chờ seed/scenario.json schema | chờ BE2 |
-->

---

## Bảng checkpoint (BE1 cập nhật tại mỗi mốc)

| Mốc | Điều kiện | Xác nhận | Đạt? |
|---|---|---|---|
| H+02 | OpenAPI + `seed/` schema versioned; 0 câu hỏi P0 mở | BE1 + cả đội | ☐ |
| H+03 | `seed/` commit vào git (dù mới là prior) | BE2 | ☐ |
| H+06 | Fixture happy path `offer→hold→confirm` chạy trong UI | BE1 + FE1 + FE2 | ☐ |
| H+10 | Core transaction / resolver / pricing / metrics tests xanh | BE1–BE3 | ☐ |
| H+14 | **Real golden path end-to-end** | Cả đội | ☐ |
| H+18 | P0 feature complete; release candidate; **FEATURE FREEZE** | BE1 | ☐ |
| H+23 | Smoke 3/3; p95 / error / a11y evidence | BE1 + FE1 | ☐ |
| H+26 | **Video backup** + pitch evidence | FE2 | ☐ |
| H+30 | Submission checksum khớp | BE1 + FE2 | ☐ |

---

## Definition of Done (tick khi có bằng chứng — Master §9)

- [ ] Reset deterministic — cùng seed ⇒ cùng checksum
- [ ] Baseline **từ chối** golden request `THO→DHO`
- [ ] Âu Lạc tìm **đúng** same-seat gap trên `C01-S017` (leg L3+L4)
- [ ] Offer hiển thị price / bid / versions / expiry
- [ ] Hold nguyên tử — 2 hold cạnh tranh: 1 OK, 1 → 409, **0 partial hold**
- [ ] Guardrail clamp thật (có case vượt ceiling)
- [ ] Backtest ≥5 seed — median + min/max + raw; failed seed **không bị giấu**
- [ ] Heatmap cập nhật sau confirm
- [ ] Decision truy vết được (versions + rule đã bắn + violations)
- [ ] Smoke test **3/3**, mỗi lần **< 90 giây**
- [ ] **0 vi phạm** sàn/trần + CSXH, hiển thị trên S06
- [ ] Video backup + AI collaboration log sẵn sàng
- [ ] `grep -r "_ground_truth" src/` **rỗng**
- [ ] NFR: offer p95 < 1s · resolver < 200ms · reset < 3s

---

## Stop-rules (không thương lượng)

| Điều kiện | Hành động |
|---|---|
| H+02 còn open P0 contract question | **Dừng code core.** Chốt canonical examples trước. |
| H+18 golden path chưa 3/3 | **Không làm P1/P2.** Giữ static evidence. |
| H+23 smoke fail | Chuyển sang video backup. |
| H+26–28 | Fix **tối đa 1** blocker. Mọi thay đổi chạy lại smoke. |
| H+28–30 | **Cấm refactor. Cấm upgrade dependency.** |

---

## Ghi chú / quyết định phát sinh

Ghi lại quyết định lệch khỏi plan + lý do (để pitch trả lời được, và để người sau hiểu):

| Giờ | Dev | Quyết định | Lý do |
|---|---|---|---|
| | | | |

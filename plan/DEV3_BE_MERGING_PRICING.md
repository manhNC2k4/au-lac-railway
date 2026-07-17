# BE3 — Decision (Merging / Safety + Pricing / Governance)

**Đọc trước:** `00_MASTER_PLAN.md` (bắt buộc — §2.1, §2.5, §2.7, §4, §8).
**Bạn gộp D3+D4 của plan gốc. Bù lại: resolver nhỏ hơn bạn tưởng, pricing đã có code tham chiếu.**

---

## Bạn sở hữu

| Đường dẫn | Nội dung |
|---|---|
| `src/merging/` | `continuous_same_seat`, `reused_gap`, ranking, protected filter |
| `src/pricing/` | `PricingEngine`, guardrail, `FareProduct` |
| `src/offer/` | `OfferService`, `DecisionRecord`, explanation |
| `rules/pricing_rules.yaml`, `rules/policy_constraints.yaml` | **Luật giá khai báo — KHÔNG hard-code Python** |

**Bạn read-only với matrix.** BE1 là single writer. Bạn đọc snapshot, trả decision. Ghi thẳng vào `seat_segment_state` = bug.

---

## ⭐ Trước khi thiết kế bất cứ thứ gì: đọc `generate_data.py` class `Pricer` (dòng 404)

**Logic giá đã đúng luật, đã chạy, đã sinh 7,6 triệu vé với 0 vi phạm.** Nó đã cài đúng:
- `F0 = ρ_t · ς_c · κ₀ · d^θ` (tham số ở `04_THAM_SO_CAU_HINH_MO_PHONG.yaml`: `kappa0`, `theta`, `varsigma`, `rho_t`, `gia_neo`)
- δ mùa / lead / Tết chiều rỗng / sát ngày / AI
- clip sàn/trần
- **CSXH `max`, áp SAU cùng** (`csxh_apply`, dòng 482)

**Chép logic, đừng chép cấu trúc.** `Pricer` viết cho batch generation; MVP cần per-request + audit trail. Nhưng thứ tự phép toán và tham số thì **giữ nguyên** — nó đã được kiểm chứng, bạn viết lại từ đầu là tự tạo bug.

> **Đừng đọc lại 4 file spec để tìm công thức giá.** Nó nằm trong `Pricer`, đã chạy được. Rung thang: tái dùng > tự dựng.

---

## Nhiệm vụ theo giờ

### H0–H2 · Contract freeze (cùng BE1)

- [ ] `SeatPlan` schema — seat_id, segments[], `reused_gap: bool`, `requires_seat_change: bool`
- [ ] `SafetyDecision` schema
- [ ] `PricingBreakdown` schema — `gia_goc → gia_niem_yet → gia_cuoi` + rule đã bắn + thứ tự áp
- [ ] `GuardrailViolation`, `Offer`, `DecisionRecord` schema
- [ ] `pricing_policy.json` (cùng BE1 — họ commit trong `seed/`, bạn định nghĩa shape)

### H2–H6 · Tracer bullet

- [ ] `continuous_same_seat` + golden gap test
- [ ] `FareProduct` O-D (giá O-D, **không cộng mơ hồ từ base fare từng leg** — G06)
- [ ] Price proposal + guardrail + `DecisionRecord` fixture

#### Resolver — nhỏ hơn bạn nghĩ

```python
def continuous_same_seat(matrix, seg_from, seg_to):
    """matrix: (n_seats, n_segments) int8. Ghế nào FREE suốt [seg_from, seg_to)?"""
    ok = (matrix[:, seg_from:seg_to] == FREE).all(axis=1)
    return np.flatnonzero(ok)
```

Đó là cốt lõi. `demo/ssm/seat_state_matrix.py::first_fit` đã có sẵn pattern này. Thêm vào:
- `reused_gap = True` ⟺ ghế có booking **trước** `origin` **hoặc sau** `destination` (nó chỉ là **label**, không phải cơ chế — G02)
- Ranking các option
- **Không di chuyển booking SOLD.** SOLD→SOLD là **P2, ngoài scope** (G09). Nếu thấy mình đang viết code dời vé đã bán — dừng.
- Duyệt **cùng một snapshot** cho mọi leg. Đọc 2 snapshot khác nhau = race condition.

NFR: **resolver < 200ms**. Với 40 ghế × 7 leg thì đây là numpy 1 dòng — dư sức. Đừng tối ưu sớm.

### H6–H10 · Core

- [ ] Resolver tích hợp snapshot thật + ranking + performance fixture
- [ ] **`OfferService` áp ĐÚNG pipeline** (Master §8) — thứ tự bất di bất dịch:
  ```
  seat plan → base fare → price proposal → guardrail → so bid → offer
  ```
- [ ] Offer **immutable**, có expiry, đủ 4 versions. **Tạo offer KHÔNG giữ ghế** (bước 8, không phải bước 9).
- [ ] `DecisionRecord` **append-only** — input_hash, versions, result, violations, explanation_code, actor, created_at

#### Guardrail — đúng thứ tự, không đảo

```
1. Policy phải TỒN TẠI và APPROVED  → thiếu ⇒ 503 POLICY_UNAVAILABLE (không phải default!)
2. floor / ceiling
3. max delta
4. round_to_1k
5. freeze
```

> `POLICY_UNAVAILABLE → 503`. **Không** im lặng dùng giá mặc định. Không có policy = không được bán, không phải bán bừa.

#### Rule engine xuất audit trail

Mỗi lần định giá **phải** ghi:
```json
{"gia_goc": 0, "rules_fired": [{"rule_id": "R_HE2026_XA_NGAY", "he_so": 0.92, "thu_tu": 1}],
 "gia_niem_yet": 0, "gia_cuoi": 0, "rang_buoc_cham": ["TRAN"],
 "che_do_gia": "AI", "phien_ban_quy_tac_hash": "..."}
```

**Đây CHÍNH LÀ "nhật ký quyết định/phê duyệt"** đề bài yêu cầu (Mục 9 & 15), **và** là XAI thật — giải thích = liệt kê luật đã bắn. **Không cần SHAP.** Nói điều này trong pitch.

### H10–H14 · Integration

BE1 thay adapter của bạn ở vị trí **2 (resolver)** và **3 (pricing)**. Sẵn sàng trước H10.

### H14–H18 · Governance evidence — freeze H18

- [ ] Protected case hoàn chỉnh
- [ ] Hỗ trợ visualize `reused_gap` cho FE1 (S02)
- [ ] Clamp/freeze audit evidence + decision detail cho FE1 (S05)

---

## Ràng buộc CỨNG — 0 vi phạm, không phải soft penalty

### 1. CSXH áp SAU, `max`, không cộng dồn

```python
gia_niem_yet = clip(F0 * delta_dong, san, tran)       # 1. giá động, clip
muc_giam     = max(g for g in cac_uu_dai_du_dieu_kien)  # 2. MAX — KHÔNG ∏
gia_cuoi     = round_to_1k(gia_niem_yet * (1 - muc_giam))  # 3. áp SAU CÙNG
```

Căn cứ: **Điều 40 Nghị định 16/2026/NĐ-CP** — giảm áp lên **giá bán thực tế**, tức **sau** giảm động.
Mỗi vé **≤ 1** ưu đãi, lấy mức **cao nhất**.
Sai thứ tự = **sai doanh thu VÀ sai quyền lợi hành khách**. Tham chiếu: `csxh_apply` dòng 482.

### 2. PricingContext KHÔNG được thấy PassengerSafetyContext

Pricing **không** biết hành khách là người cao tuổi/khuyết tật/trẻ đi một mình.

```python
FORBIDDEN = {"user_id","so_lan_tim_kiem","thiet_bi","ip","gioi_tinh","tuoi",
             "lich_su_mua","dia_chi","support_need"}
```

> Bạn viết **cả hai** module (merging/safety **và** pricing). Ràng buộc này **không** được đảm bảo bằng cách chia người nữa — nó phải đảm bảo bằng **type + test**. Hai `dataclass` riêng biệt, không có đường dẫn nào từ `SafetyContext` sang `PricingContext`. Test nó.

### 3. Đối tượng ưu tiên: `so_lan_doi_cho = 0`

Người cao tuổi / khuyết tật / trẻ đi một mình: nhận same-seat option, **không bao giờ** nhận option `requires_seat_change`. 0 vi phạm.

### 4. Protection ≠ HELD (G11)

Chỉ **TTL hoặc hủy** mới giải phóng customer hold. Đừng phát minh cơ chế "protected hold" riêng.

### 5. Giá `int64` đồng, `round_to_1k` mọi ngã ra

Không float. Float làm hỏng kiểm toán sàn/trần.

---

## Test bắt buộc (DoD của bạn)

```python
# Merging
def test_golden_gap_found()                      # C01-S017, THO→DHO, 2 leg
def test_no_held_or_sold_leg_returned()
def test_reused_gap_label_correct()
def test_sold_bookings_never_moved()
def test_resolver_under_200ms()

# Pricing / compliance — lên slide dự thi
def test_no_price_below_floor_or_above_cap()
def test_social_policy_discount_is_max_not_product()      # ⭐
def test_social_policy_applied_after_dynamic()            # ⭐
def test_priority_passengers_never_forced_to_change_seat()
def test_price_invariant_to_repeated_search()             # searches 1→50, giá KHÔNG đổi
def test_price_locked_after_hold()
def test_pricing_features_exclude_sensitive()
def test_pricing_context_has_no_safety_context()          # ⭐ vì bạn viết cả 2
def test_guardrail_order_floor_ceiling_delta_round_freeze()
def test_policy_unavailable_returns_503()
```

> **3 test này đi thẳng lên slide** (doc `03` §5.3): `test_price_invariant_to_repeated_search`, `test_price_locked_after_hold`, `test_pricing_features_exclude_sensitive`. Chúng chứng minh "tuân thủ" **bằng kỹ thuật, không bằng lời hứa**.

---

## Bẫy dành riêng cho bạn

1. **`bid_price` KHÔNG phải của bạn** — BE2 cấp. Bạn chỉ **so sánh** final offered fare vs Σ bid (Master §8 bước 7). Đừng tự tính, và tuyệt đối đừng đọc `_ground_truth/`.
2. **Ngày golden = 15/06/2026 ⇒ `che_do_gia = AI`**, không phải LUAT. Fixture giá phải phản ánh. Cũng nằm trong **cao điểm hè** ⇒ `R_HE2026_XA_NGAY` có hiệu lực (`lead_time ≥ 20` ngày, hạn mức **20 vé/loại chỗ/đoàn tàu**).
3. **Luật giá là YAML khai báo, không phải Python.** Lý do: luật đổi mỗi mùa; đề bài yêu cầu **log thay đổi chính sách + rollback**; chỉ config khai báo mới cho audit trail đúng nghĩa. Hard-code `if lead_time >= 20:` = mất điểm ở Mục 9/15.
4. **`FareProduct` là giá O-D**, không phải tổng giá leg (G06). Cộng giá leg = sai mô hình giá đường sắt.
5. **Tạo offer KHÔNG giữ ghế.** Đây là bước 8; giữ ghế là bước 9 của BE1.
6. **Đừng làm min-cost multi-seat matching.** P2, ngoài scope. `quantity=1`.

---

## ⭐ Ghi `progress.md`

```markdown
| H+06 | BE3 | continuous_same_seat | ✅ DONE | `pytest tests/test_merging.py -q` → 8 passed | FE1 (S02), BE1 |
```

- `✅ DONE` **phải** có lệnh test + output hoặc commit sha.
- Compliance test xanh ⇒ ghi rõ — FE1 cần cho S06 và FE2 cần cho pitch.
- `⛔ BLOCKED` phải ghi chờ ai/chờ gì. Block > 30' ⇒ báo BE1.
- Checkpoint H2/6/10/14/18/23/26/30: ghi 1 dòng dù không có gì mới.

# HƯỚNG DẪN BACKEND — tích hợp lớp Model + Thuật toán

Tài liệu cho đội backend: lớp model/thuật toán trong `app/` đã **hoàn thiện và đóng
băng contract**. Backend KHÔNG sửa logic trong `app/` — chỉ gọi hàm, lưu log, bọc
phê duyệt/rollback/UI. Mọi cấu trúc trao đổi nằm ở `app/contracts.py`.

---

## 1. Bức tranh tổng

```
                      ┌──────────────────────────────────────────┐
   e-ticketing  ───►  │            BACKEND (bạn xây)             │
   (yêu cầu vé)       │  API · auth/role · audit DB · approval   │
                      │  rollback · dashboard · streaming        │
                      └───────┬──────────────────────┬───────────┘
                              │ gọi hàm (contracts)  │ lưu ProposalLog
                      ┌───────▼──────────────────────▼───────────┐
                      │        LỚP MODEL + THUẬT TOÁN (app/)     │
                      │  BT1 forecast · BT2 SSM · BT3 alloc      │
                      │  BT4 merge · BT5 price · realloc ·       │
                      │  group · waitlist                        │
                      └───────┬──────────────────────────────────┘
                              │ nạp artifact 1 lần lúc boot
                      ┌───────▼──────────────────────────────────┐
                      │  models/artifacts/ (joblib + json + npz) │
                      └──────────────────────────────────────────┘
```

**Nguyên tắc vàng:** mọi hàm trong `app/` là **THUẦN ĐỀ XUẤT** — không hàm nào tự
áp giá/tự gán ghế vĩnh viễn trừ khi backend gọi `assign/confirm_hold`. Mỗi output
kèm `_log` (ProposalLog) và `explain` → backend chỉ việc persist làm audit trail.

## 2. Boot sequence (nạp artifact 1 lần)

```python
from app.bt2_ssm import SeatStateMatrix
from app.bt5_pricing import Pricer
from app.bt1_forecast import DemandModel
from app.waitlist import WaitlistManager

pricer  = Pricer.load()          # bt5_pricing_params.json
demand  = DemandModel.load()     # bt1_forecast_hgb.joblib + spec + booking_curves
ssm     = SeatStateMatrix()      # + load_snapshot(path) nếu có snapshot .npz
waitlist = WaitlistManager(pricer)
```

Artifact bắt buộc (build bằng `models/export_bt5_params.py`, `models/train_bt1_forecast.py`,
`models/build_bt1_curves.py`):

| File | Dùng bởi |
|---|---|
| `bt1_forecast_hgb.joblib` + `bt1_feature_spec.json` | DemandModel |
| `bt1_booking_curves.json` | DemandModel (lead-time) |
| `bt5_pricing_params.json` | Pricer |
| `elasticity_params.json` | Pricer (bộ tối ưu giá theo cầu; thiếu file => Pricer tự fallback rule heuristic) |
| `bt2_snapshot_*.npz/.meta.json` | SSM warm-start (tùy chọn) |

**Hai chế độ định giá** (chọn khi boot): `Pricer.load(use_elasticity=True)` — tối đa
E[đóng góp]=P(mua\|r)·(giá−chi_phí_cơ_hội) trong dải hẹp quanh F0 (trần co theo LF
đoạn để phản ánh khan hiếm); `use_elasticity=False` — luật heuristic (bid-floor +
phụ thu LF). Cả hai đều đi qua cùng guardrail/cap±5%/held/CSXH. `elasticity_params.json`
ước lượng từ search_log — KHÔNG dùng dữ liệu cá nhân, giá là niêm yết chung theo trạng thái.

## 3. Luồng nghiệp vụ chính (endpoint gợi ý)

### 3.1 `POST /booking/quote` — báo giá 1 yêu cầu (chain BT4→BT3→BT5)

```python
from app.bt4_merge import find_options
from app.bt3_allocation import analyze_run, load_factor_route
from app.contracts import BookingRequest, PassengerProfile

req = BookingRequest(...)                        # từ payload e-ticketing
opts = find_options(ssm, req.chuyen_id, req.loai_cho,
                    req.ga_di, req.ga_den, req.profile)
if not opts["kha_thi"]:
    e = waitlist.add(req)                        # YC7: vào hàng chờ
    return {"kha_thi": False, "waitlist_id": e.id}

alloc = alloc_cache.get(req.chuyen_id) or analyze_run(ssm, pricer, req.chuyen_id, fc_df)
lfr = load_factor_route(ssm, req.chuyen_id, req.ga_di, req.ga_den,
                        alloc["bid_price_theo_lop"], opts["seat_class"])
q = pricer.quote(mac_tau, req.ga_di, req.ga_den, tier,
                 ctx,                            # từ calendar: tau_tet, dow, che_do_gia, u
                 lfr,
                 gia_truoc=req.gia_truoc,        # cap ±5%/lần
                 gia_da_khoa=req.gia_da_khoa,    # honor held price
                 muc_giam_csxh=req.profile.muc_giam_csxh)   # CSXH áp SAU CÙNG
# LƯU AUDIT: pricer.quote_log(q, req.to_dict()) -> bảng audit
```

**Bắt buộc UI:** nếu phương án chọn có `can_khach_chap_nhan=True` (ghép chặng),
backend PHẢI hiện disclosure (số lần đổi, ga đổi) và chỉ đi tiếp khi khách bấm
đồng ý — không auto-accept.

### 3.2 `POST /booking/hold` → `confirm` — giữ chỗ & khoá giá

```python
idx = ssm.hold_with_expiry(cid, cls, a, b, now_u=u, ttl_ngay=1.0)
ssm.lock_price(f"{cid}|{idx}|{a}|{b}", q.gia_de_xuat)      # giá khoá bất khả xâm phạm
# ... khách thanh toán:
ssm.confirm_hold(cid, cls, idx, a, b)
```

Cron/worker định kỳ: `expired = ssm.expire_holds(now_u)` → mỗi lần nhả xong gọi
`waitlist.match(ssm)` để khớp hàng chờ (YC6→YC7 nối nhau).

### 3.3 `POST /allocation/refresh` — tái phân bổ động (cần PHÊ DUYỆT)

```python
from app.reallocation import propose_reallocation
prop = propose_reallocation(ssm, pricer, demand, cid,
                            rows_by_band, sold_by_band, u, old_quota)
# prop["de_xuat"] = [{khu_gian_id, action: MO_THEM|SIET_LAI, limit_cu, limit_moi}]
# => đưa vào queue phê duyệt (role: điều độ viên) — CHỈ áp sau khi duyệt
# => rollback = áp lại old_quota (backend giữ version quota theo thời gian)
```

### 3.4 `POST /group/quote` — đoàn khách

```python
from app.group_seating import plan_group
plan = plan_group(ssm, cid, loai_ghe, ga_di, ga_den, n_khach)  # CP-SAT, tất định
```

### 3.5 Dashboard / heatmap

- `analyze_run(...)["lf_theo_doan"]` → heatmap fill-rate (mỗi phần tử có `khu_gian_id,
  ga_dau, ga_cuoi, lf, phan_loai, bid_price`).
- `list_mergeable_gaps(ssm, cid)` → danh sách khoảng trống ghép được (output đề bài).
- `eval/backtest.py` xuất `fill_matrix_<policy>_<date>.csv` — ma trận chuyến × đoạn.

### 3.6 Model ops

- **Cập nhật liên tục:** `demand.update(row, sold_to_date, u)` mỗi khi chốt thêm vé
  (không cần retrain). Retrain định kỳ = chạy lại `models/train_bt1_forecast.py`.
- **Drift monitor:** log `demand.divergence(...)["divergence"]` theo (chuyến, băng);
  cảnh báo khi |lệch| ≥ 15% kéo dài — ngưỡng ở `reallocation.DIV_THRESHOLD`.
- **Versioning:** mỗi ProposalLog có `model_version`; artifact đổi = bump version.

## 4. Bất biến KHÔNG ĐƯỢC phá (đã có test ở `tests/`)

1. **Giá tất định** — cùng trạng thái ⇒ cùng giá. Cấm đưa user-id/số lần tìm kiếm vào pricing.
2. **Thứ tự toán tử giá:** mùa vụ → động → cap ±5% → sàn/trần → **CSXH SAU CÙNG (max, không cộng dồn)**. Giá cuối CSXH được phép < sàn.
3. **Held price bất khả xâm phạm** — `gia_da_khoa` trả nguyên vẹn.
4. **Nhóm ưu tiên không bao giờ nhận phương án ghép** (`thuoc_nhom_uu_tien`).
5. **Ghép chặng:** chỉ khi bất khả kháng; ga đổi dwell ≥ 5p; cùng lớp chỗ; phải có bước khách đồng ý.
6. **SSM nguyên tử** — `assign` chồng lấn trả `False` và không ghi gì; backend không được ghi thẳng vào `_store`.
7. **Tiền là int64 đồng** — không float.
8. **`_ground_truth/` cấm động vào runtime** — chỉ eval/backtest được đọc.

Chạy test trước mỗi lần deploy: `python tests/test_invariants.py` (9 bất biến).

## 5. Việc backend cần tự xây (ngoài phạm vi lớp này)

| Hạng mục | Gợi ý |
|---|---|
| Audit DB | persist mọi `ProposalLog` (+ user áp dụng, thời điểm áp) |
| Role & approval | quota/realloc/giá ngoài dải mặc định ⇒ cần duyệt trước khi áp |
| Rollback | version hoá QuotaTable & policy dict; áp lại bản cũ |
| Manual override | endpoint ghi đè giá/quota TRONG sàn–trần, log lý do |
| Near-real-time | mỗi giao dịch mới → `ssm.apply_transaction(txn)`; refresh `analyze_run` mỗi N vé (replay dùng N=200) hoặc theo timer |
| Adaptor e-ticketing | map schema vé hiện có → `TXN_SCHEMA`/`BookingRequest` |
| A/B (Phase 3) | policy dict của `pricer.quote` nhận override theo nhóm thử nghiệm |

## 6. Hiệu năng đo được (backtest)

- p95 mỗi yêu cầu (tìm ghế + DLP cache + giá): **~6–7ms** (mục tiêu đề: <200ms).
- DLP refresh 1 chuyến (3 lớp chỗ): ~50–80ms — chạy nền, cache theo chuyến.
- `build_date` (replay 1 ngày, 2 tàu): vài giây; production dùng `apply_transaction`
  incremental + snapshot `.npz` thay vì replay.

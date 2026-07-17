**VIETNAM AI INNOVATION CHALLENGE 2026**

**KẾ HOẠCH TỔNG HỢP CUỐI CÙNG**

Âu Lạc Railway - SDD v2 và MVP 5 dev / 30 giờ

| **Trạng thái** | FINAL REVIEW DRAFT         | **Phiên bản** | 2.0-plan                     |
| -------------- | -------------------------- | ------------- | ---------------------------- |
| **Ngày**       | 17/07/2026                 | **Đội hình**  | 5 developers                 |
| **Thời lượng** | 30 giờ liên tục            | **Stack**     | FastAPI · PostgreSQL · React |
| **Phạm vi**    | 1 service run · quantity=1 | **Dữ liệu**   | Synthetic · seed trước T0    |

**QUYẾT ĐỊNH ĐỀ NGHỊ PHÊ DUYỆT**

Phát hành SDD v2 dưới dạng target MVP design; khóa contract trong 2 giờ đầu; seed một golden scenario trước T0; triển khai theo năm workstream độc lập nhưng tích hợp tăng dần từ giờ 10; feature freeze ở giờ 18.

**Mục đích tài liệu.** Tổng hợp toàn bộ kết luận từ SDD 1.0 và báo cáo Review thành một kế hoạch duy nhất để reviewer xác nhận trước khi đội bắt đầu triển khai.

**Nguyên tắc đọc.** Mục 1-4 khóa thiết kế và hợp đồng; Mục 5-7 khóa phân công và timeline; Mục 8-10 là quality gate, risk control và checklist review.

# Mục lục

Mục lục 2

1\. Tóm tắt điều hành 4

1.1 Các quyết định đã khóa 4

1.2 Deliverables 4

2\. Phạm vi MVP và non-goals 4

2.1 In scope - P0 4

2.2 Có thể làm sau feature freeze - P1 5

2.3 Ngoài phạm vi demo - P2 5

3\. Kiến trúc mục tiêu và hợp đồng tích hợp 5

3.1 Pipeline quyết định chuẩn 5

3.2 Ownership và data flow 6

3.3 Mô hình dữ liệu tối thiểu 6

3.4 Thuật toán đã khóa 7

3.5 Public API v1 7

3.6 Kiểu và lỗi chuẩn 7

4\. Gói dữ liệu seed trước T0 8

4.1 Golden scenario 8

4.2 Fixture bắt buộc 8

4.3 Artifact seed bàn giao 8

5\. Phân công năm workstream 9

5.1 File ownership và change control 9

6\. Timeline 30 giờ 9

6.1 0-2h - Contract freeze 10

6.2 2-6h - Tracer bullet 10

6.3 6-10h - Core implementation 10

6.4 10-14h - Integration 1 10

6.5 14-18h - Evidence và feature freeze 10

6.6 18-30h - Stabilize, pitch và submit 11

7\. Chiến lược tích hợp và Git 11

7.1 Checkpoint bắt buộc 11

8\. Test strategy và Definition of Done 11

8.1 Unit và contract tests 11

8.2 Transaction và integration tests 12

8.3 Backtest và metric tests 12

8.4 NFR và demo acceptance 12

9\. Rủi ro và fallback 12

10\. Ma trận traceability Review G01-G20 13

11\. Checklist dành cho reviewer 14

11.1 Quyết định cần xác nhận 14

11.2 Quality gate tài liệu 14

11.3 Sign-off 14

Phụ lục A. Lịch sử phiên bản 15

# 1\. Tóm tắt điều hành

SDD hiện tại đúng hướng về quản trị tồn kho cấp leg, same-seat gap, định giá theo khan hiếm và guardrail. Tuy nhiên, bản 1.0 chưa đủ chặt để năm dev code song song an toàn: thiếu service_run, pipeline quyết định thống nhất, transaction giữ nhiều leg, vòng đời offer/hold, hợp đồng API orchestration, metric backtest và ranh giới dữ liệu an toàn.

Kế hoạch này cắt MVP thành một vertical slice có thể chứng minh end-to-end: nạp scenario → tạo snapshot → tìm continuous same-seat gap → đề xuất và kiểm soát giá → tạo offer → giữ toàn bộ leg nguyên tử → xác nhận → cập nhật heatmap → chạy backtest công bằng.

## 1.1 Các quyết định đã khóa

- SDD v2 là target MVP design, không tuyên bố là as-built vì workspace hiện chưa có mã ứng dụng.
- Một service run, một ngày chạy, một chiều, một hạng NGOI_MEM_DH và quantity=1.
- FastAPI + PostgreSQL một instance + React/Vite/TypeScript; không Redis, không worker phân tán và không JWT production trong P0.
- SeatStateManager là single writer; mọi module khác chỉ đọc snapshot và trả decision/recommendation.
- Multi-seat, seat-change consent, full ML, production HA/RBAC và đa tuyến nằm ở P2 roadmap.
- Dữ liệu seed được chuẩn bị trước T0; không tải toàn bộ hàng triệu dòng Parquet vào demo runtime.

## 1.2 Deliverables

| **Đầu ra**          | **Nội dung**                                                                                        | **Gate hoàn thành**                                   |
| ------------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| SDD v2.0            | Kiến trúc, data model, thuật toán, API, UI, NFR, deployment profile và roadmap đã sửa theo G01-G20. | Traceability 20/20; render và kiểm tra toàn bộ trang. |
| MVP source          | Vertical slice offer → hold → confirm, dashboard, backtest và audit.                                | Golden path chạy 3/3; zero partial hold.              |
| Seed package        | Scenario nhỏ, 5 event streams, policies, expected checksum và golden fixtures.                      | Reset deterministic; cùng seed cùng checksum.         |
| Evidence pack       | Test output, metric definitions, screenshots, video backup và AI collaboration log.                 | Sẵn sàng trước giờ 26.                                |
| Implementation plan | Ownership, timeline, handoff, stop-rule, risk và Definition of Done.                                | Reviewer phê duyệt trước T0.                          |

# 2\. Phạm vi MVP và non-goals

## 2.1 In scope - P0

- Scenario loader/reset deterministic và service_run rõ train/date/direction.
- Seat State Matrix FREE/HELD/SOLD theo seat × leg, có matrix_version.
- Forecast baseline deterministic; allocation snapshot; demo bid-price approximation.
- Continuous same-seat resolver, reused_gap label và protected-passenger safety gate.
- Dynamic price proposal, hard guardrail, immutable offer và DecisionRecord.
- Atomic hold, idempotent confirm, TTL/expiry và conflict recovery.
- Ops Overview, Seat-Leg Matrix, Booking Lab, Backtest Comparison và Decision Detail.
- Backtest baseline vs Âu Lạc trên cùng event stream, tối thiểu 5 seed.

## 2.2 Có thể làm sau feature freeze - P1

- Approve/reject/override recommendation có reason, expected_version và audit.
- What-if preview trên cloned snapshot, không mutation state thật.
- Luồng cancel/expire trực quan và các cải tiến UX không chặn golden path.

## 2.3 Ngoài phạm vi demo - P2

- Min-cost multi-seat matching, active consent và re-accommodation sau bán.
- Gradient boosting, EM unconstraining đầy đủ, model registry và drift automation.
- Redis, distributed worker, PostgreSQL HA, production JWT/RBAC và payment integration.
- Group booking, waitlist, đa mác tàu, đa tuyến và rollout production. *(Schema đã tạo sẵn trong V1 — xem ghi chú §3.3 — nhưng logic vẫn ngoài P0.)*

**CUT LINE**

Không bắt đầu P1/P2 trước khi P0 chạy end-to-end trên cùng golden scenario và smoke test đạt 3/3. Feature freeze bắt buộc tại giờ 18.

# 3\. Kiến trúc mục tiêu và hợp đồng tích hợp

## 3.1 Pipeline quyết định chuẩn

- Load một snapshot nhất quán của service_run và matrix_version.
- Ánh xạ O-D thành dải leg và tìm continuous same-seat option.
- Tính base O-D fare; đề xuất giá từ scarcity; áp hard guardrail.
- So final offered fare với tổng bid-price của các leg.
- Tạo immutable Offer có expiry và đầy đủ versions; bước này chưa giữ ghế.
- POST /holds compare-and-set toàn bộ cells trong một transaction; một cell fail thì rollback tất cả.
- Confirm idempotent chuyển HELD→SOLD và dùng nguyên price/seat plan của hold.
- Ghi DecisionRecord và trả state mới cho dashboard/backtest evidence.

**BẤT BIẾN TRUNG TÂM**

Mọi bước của một offer dùng cùng service_run_id, matrix_version, forecast_version và policy_version. Frontend không tự ghép response của Allocation, Merging và Pricing thành quyết định kinh doanh.

## 3.2 Ownership và data flow

| **Thành phần**           | **Quyền**                                                | **Đầu ra chính**                                        |
| ------------------------ | -------------------------------------------------------- | ------------------------------------------------------- |
| SeatStateManager         | Single writer; transaction boundary duy nhất cho matrix. | Snapshot, atomic hold, confirm, expiry, matrix_version. |
| Forecasting / Allocation | Read-only đối với matrix.                                | forecast_version, load, remaining capacity, bid-price.  |
| Merging / Safety         | Read-only; lọc option trước khi trả API.                 | SeatPlan, reused_gap, safety reason.                    |
| Pricing / Guardrail      | Không thấy PassengerSafetyContext.                       | Base/suggested/final price, violations, policy_version. |
| OfferService             | Orchestrator; không tự mutate matrix.                    | Immutable offer và DecisionRecord.                      |
| Frontend                 | Chỉ gọi public orchestration API.                        | Vietnamese UI, retry/error states, evidence links.      |

## 3.3 Mô hình dữ liệu tối thiểu

| **Entity**           | **Trường bắt buộc**                                                             | **Quy tắc**                                             |
| -------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------- |
| service_run          | service_run_id, train_id, service_date, direction, status                       | Khóa chuyến thực; thay train_id + service_date rời rạc. |
| seat_segment_state   | service_run_id, seat_id, segment_id, status, hold_id, hold_expires_at, version  | Unique(service_run_id, seat_id, segment_id).            |
| allocation_snapshot  | matrix_version, forecast_version, formula_version, generated_at, leg metrics    | Immutable theo bộ versions.                             |
| fare_product         | origin, destination, seat_class, base_fare_vnd, version                         | Giá O-D, không cộng mơ hồ từ base fare leg.             |
| offer                | offer_id, versions, decision, seat_plan, final_price_vnd, expires_at            | Immutable; không giữ ghế khi tạo.                       |
| seat_hold            | hold_id, offer_id, status, expires_at, idempotency_key                          | Giá và seat plan khóa suốt hold.                        |
| booking              | hold_id, status, created/confirmed/cancelled_at                                 | MVP quantity=1; confirm không tính lại.                 |
| decision_record      | input_hash, versions, result, violations, explanation_code, actor, created_at   | Append-only; không log mô tả y tế.                      |
| forecast_observation | result_status, rejection_reason, quantity, days_to_departure, source, dedup key | Dùng cho forecast; cấm đưa vào PricingContext.          |

**Cập nhật đối chiếu DB (17/07/2026, sau `backend/flyway/sql/V1__init_schema.sql`).** Migration V1 đã tạo thêm `users`, `refresh_tokens`, `promotion`, `external_factor`, `waiting_list`, `audit_log`, `demand_forecast`, `bid_price` theo `docs/SDD_Update_Recommendations.md`. Các bảng này **đã tồn tại trong DB** nhưng **không đổi phạm vi P0/P1/P2 ở §2** — waitlist, group booking (`booking.group_id`) và auth production (`users`/`refresh_tokens`) vẫn là P2, chỉ là schema được chuẩn bị sẵn, chưa có logic P0 nào phụ thuộc vào chúng.

Bảng `offer` trong V1 đã có đủ `matrix_version`, `forecast_version`, `policy_version` (cùng `service_run_id`) — đủ 4 versions cho "bất biến trung tâm" §3.1.

## 3.4 Thuật toán đã khóa

**Continuous same-seat.** Duyệt ghế đúng hạng và kiểm tra mọi leg trong \[origin_seq, destination_seq) đều FREE tại cùng snapshot. reused_gap=true khi ghế có booking trước origin hoặc sau destination. Không di chuyển booking SOLD.

**Bid-price demo.** pressure_s = forecast_remaining_s / max(remaining_capacity_s, 1); scarcity_s = clip((pressure_s - p_low)/(p_high - p_low), 0, 1); bid_s = round_to_1k(reference_yield_per_km × distance_km_s × scarcity_s). Đây là approximation cho demo, không gọi là EMSR-b.

**Guardrail.** Policy phải tồn tại và approved; sau đó áp floor/ceiling, max delta, round-to-1k và freeze. Giá là số nguyên VND.

**Expiry.** Demo dùng Clock abstraction; expire_due_holds(now) chạy trước mọi state read/write và qua demo tick. Production worker là roadmap.

## 3.5 Public API v1

| **Method** | **Path**                           | **Vai trò**          | **Điểm bắt buộc**                                         |
| ---------- | ---------------------------------- | -------------------- | --------------------------------------------------------- |
| POST       | /api/v1/demo/scenarios/{id}/reset  | Nạp/reset scenario   | Không partial load; trả checksum và versions.             |
| GET        | /api/v1/demo/state                 | Dashboard state      | Matrix/load/alerts/last_updated; read-only.               |
| POST       | /api/v1/offers                     | Tạo booking decision | Seat plan + price + bid + expiry + versions.              |
| POST       | /api/v1/holds                      | Giữ toàn bộ leg      | Idempotency-Key; expected_matrix_version; all-or-nothing. |
| POST       | /api/v1/bookings/{hold_id}/confirm | Xác nhận booking     | Không tính lại; idempotent; 410 nếu expired.              |
| POST       | /api/v1/backtests                  | So sánh strategy     | Cùng event stream, seed set và metric definitions.        |
| GET        | /api/v1/backtests/{report_id}      | Đọc report           | Median, range, raw seed và failed runs.                   |
| GET        | /api/v1/decisions/{decision_id}    | Explain/audit        | Input versions, price/bid breakdown, violations.          |

## 3.6 Kiểu và lỗi chuẩn

- SeatState: FREE | HELD | SOLD.
- OfferDecision: ACCEPT | REJECT.
- HoldStatus: ACTIVE | CONFIRMED | EXPIRED | CANCELLED.
- Reason/error codes: NO_SAME_SEAT_OPTION, SOLD_OUT_TRUE, ALLOCATION_REJECTED, STALE_SNAPSHOT, SEAT_CONFLICT, OFFER_EXPIRED, HOLD_EXPIRED, POLICY_UNAVAILABLE.
- 409 dùng cho stale/conflict; 410 cho offer/hold hết hạn; 422 cho validation; 503 khi policy hoặc dependency bắt buộc không sẵn sàng.
- Mọi thao tác ghi nhận Idempotency-Key; request/response dùng JSON UTF-8 và timestamp ISO-8601 UTC.

# 4\. Gói dữ liệu seed trước T0

## 4.1 Golden scenario

| **Thuộc tính** | **Giá trị khóa**                                                                 |
| -------------- | -------------------------------------------------------------------------------- |
| service_run_id | SE1_2026-06-15_LE                                                                |
| Ga             | HNO, NBI, THO, VIN, DHO, HUE, DNA, SGO - 8 ga / 7 leg                            |
| Ghế            | 40 ghế NGOI_MEM_DH; quantity=1                                                   |
| Golden gap     | Ghế C01-S017 SOLD HNO→THO, FREE THO→DHO, SOLD DHO→SGO                            |
| Golden request | THO→DHO: baseline từ chối theo quota, Âu Lạc phục vụ trên cùng một ghế qua 2 leg |
| Backtest seeds | 20260717, 20260718, 20260719, 20260720, 20260721                                 |
| Nguồn          | Chỉ phần observable từ VAIC/data; \_ground_truth không được dùng làm feature     |

## 4.2 Fixture bắt buộc

- Hai hold cạnh tranh cùng seat/leg; chỉ một thành công.
- Offer stale và hold expired với expected error/status.
- Pricing proposal vượt ceiling để guardrail clamp thật.
- Protected passenger nhận same-seat option nhưng không nhận option requires_seat_change.
- Scenario invalid hoặc booking interval chồng lấn bị từ chối toàn bộ.
- Năm event stream có checksum; baseline và Âu Lạc dùng cùng checksum.

## 4.3 Artifact seed bàn giao

- scenario.json: ga, leg, ghế, service run, clock và random seed.
- initial_bookings.jsonl: các booking/hold ban đầu theo timestamp.
- forecast.json: forecast_remaining, confidence và forecast_version.
- fare_products.json và pricing_policy.json: số nguyên VND, versioned.
- backtest/events-seed-\*.jsonl: năm stream nhỏ, deterministic.
- expected_checksums.json: matrix checksum, event checksum và expected contract shape.

# 5\. Phân công năm workstream

| **Dev** | **Vai trò**                      | **P0 sở hữu**                                                                         | **Handoff chính**                           |
| ------- | -------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------- |
| D1      | Integration / State Lead         | OpenAPI, PostgreSQL, service_run, SeatStateManager, atomic hold/confirm, integration. | Contract v2.0 giờ 2; owner merge.           |
| D2      | Forecast / Allocation / Backtest | Seed adapter, forecast, load, bid approximation, baseline strategy, metrics.          | Forecast fixture giờ 3; snapshot giờ 6.     |
| D3      | Merging / Safety                 | continuous_same_seat, reused_gap, ranking, protected filter, performance.             | Resolver fixture giờ 4; không làm min-cost. |
| D4      | Pricing / Governance             | PricingEngine, guardrail, OfferService, DecisionRecord, explanation.                  | Pricing fixture giờ 4; clamp case giờ 8.    |
| D5      | Frontend / UX / Pitch            | S01-S06, typed client, fixture adapter, errors, video, AI log.                        | UI fixture giờ 6; API thật giờ 14.          |

## 5.1 File ownership và change control

- D1 là owner duy nhất của shared OpenAPI, DB migration và matrix transaction code.
- D2-D4 sở hữu module và contract fixture của mình; không sửa shared schema trực tiếp.
- D5 sinh typed client từ contract đã freeze; không tạo shape riêng trong frontend.
- Mọi đề nghị đổi contract là proposal có impact list, migration note và xác nhận của D1 cùng các owner liên quan.
- Không để hai dev sửa cùng một file shared trong cùng time block.

# 6\. Timeline 30 giờ

| **Khung giờ** | **Mục tiêu**                                                                 | **Gate / stop-rule**                        |
| ------------- | ---------------------------------------------------------------------------- | ------------------------------------------- |
| 0-2           | Contract freeze: schema, enums, errors, golden scenario, metric definitions. | Nếu chưa freeze, không tách nhánh core.     |
| 2-6           | Tracer bullet bằng fixture: matrix seed, offer/hold stub, Booking Lab.       | Giờ 6 phải chạy fixture offer→hold→confirm. |
| 6-10          | Core algorithms và transaction path.                                         | Core unit/integration tests xanh.           |
| 10-14         | Integration 1: thay fixture từng module bằng service thật.                   | Giờ 14 real offer→hold→confirm chạy được.   |
| 14-18         | Backtest + UI + safety/governance cases.                                     | Feature freeze giờ 18.                      |
| 18-23         | Stabilize, error states, concurrency, p95, accessibility.                    | Không P1 nếu golden path chưa 3/3.          |
| 23-26         | Pitch assets, evidence, video backup.                                        | Giờ 26 có video chạy được.                  |
| 26-28         | Dress rehearsal và fix tối đa một blocker.                                   | Mọi thay đổi chạy lại smoke test.           |
| 28-30         | Đóng gói và submit.                                                          | Cấm refactor hoặc upgrade dependency.       |

## 6.1 0-2h - Contract freeze

- D1: khóa OpenAPI, enum/error envelope, migration skeleton và interface Clock/SeatStateManager.
- D2: khóa forecast/allocation/backtest fixture và định nghĩa năm metric.
- D3: khóa SeatPlan, reused_gap và SafetyDecision schema.
- D4: khóa PricingBreakdown, GuardrailViolation, Offer và DecisionRecord schema.
- D5: tạo typed mock client và khung route S01-S06.

## 6.2 2-6h - Tracer bullet

- D1: service_run, scenario reset, matrix repository, demo state và offer/hold stub.
- D2: seed loader, deterministic forecast, allocation fixture và bid unit tests.
- D3: continuous_same_seat + golden gap + safety unit tests.
- D4: fare product, price proposal, guardrail và DecisionRecord fixture.
- D5: Booking Lab, heatmap và decision panel chạy hoàn toàn bằng fixture.

## 6.3 6-10h - Core implementation

- D1: atomic multi-cell CAS, rollback, idempotency, confirm và expiry.
- D2: forecast/load/bid snapshot thật; backtest replay và metric aggregation.
- D3: resolver tích hợp snapshot, ranking và performance fixture.
- D4: OfferService áp đúng pipeline price→guardrail→bid decision.
- D5: hoàn thiện các trạng thái accept/reject/clamped/conflict/expired/confirmed.

## 6.4 10-14h - Integration 1

- Thay adapters theo thứ tự: state → resolver → pricing → allocation → hold/confirm.
- Mỗi lần thay một adapter phải chạy contract test và golden E2E trước khi thay module kế tiếp.
- D1 giải quyết contract conflict; owner module sửa implementation, không sửa frontend workaround.
- Gate giờ 14: real API tạo offer, hold hai leg nguyên tử, confirm và heatmap cập nhật.

## 6.5 14-18h - Evidence và feature freeze

- D2 hoàn thiện backtest 5 seed và raw-result trace.
- D3 hoàn thiện protected case và reused-gap visualization support.
- D4 hoàn thiện clamp/freeze audit evidence và decision detail.
- D5 nối S01-S06 với API thật; D1 khóa release candidate tại giờ 18.

## 6.6 18-30h - Stabilize, pitch và submit

- 18-23h: concurrency, idempotency, expiry, deterministic replay, p95, accessibility và error-state polish.
- 23-26h: video backup, screenshots, Q&A, architecture narrative và AI collaboration log.
- 26-28h: dress rehearsal; chỉ fix một blocker nghiêm trọng; chạy lại toàn bộ smoke suite.
- 28-30h: checksum artifacts, đóng gói source/seed/docs/video và submit.

# 7\. Chiến lược tích hợp và Git

- Freeze contract v2.0 và commit golden fixtures trước khi tách nhánh.
- Mỗi workstream triển khai sau interface/adapter của mình; tests đọc cùng canonical fixtures.
- Merge theo tracer bullet nhỏ, không chờ đến giờ 20 để big-bang integration.
- Mỗi merge phải có test command, output, prompt/AI log và rollback note.
- Release candidate tạo tại giờ 18; sau đó chỉ nhận bugfix có reproduction và regression test.

## 7.1 Checkpoint bắt buộc

| **Mốc** | **Bằng chứng**                                                   | **Owner xác nhận** |
| ------- | ---------------------------------------------------------------- | ------------------ |
| Giờ 2   | OpenAPI/schema/fixtures versioned; no open P0 contract question. | D1 + D2-D5         |
| Giờ 6   | Fixture happy path chạy trong UI.                                | D1 + D5            |
| Giờ 10  | Core transaction, resolver, pricing và metrics tests xanh.       | D1-D4              |
| Giờ 14  | Real golden path chạy end-to-end.                                | Cả đội             |
| Giờ 18  | P0 feature complete; release candidate và feature freeze.        | D1                 |
| Giờ 23  | Smoke 3/3; p95/error/accessibility evidence.                     | D1 + D5            |
| Giờ 26  | Video backup và pitch evidence hoàn tất.                         | D5                 |
| Giờ 30  | Submission checksum khớp.                                        | D1 + D5            |

# 8\. Test strategy và Definition of Done

## 8.1 Unit và contract tests

- Golden gap được tìm đúng; không trả bất kỳ leg HELD/SOLD nào.
- Low-pressure fixture có bid thấp hơn bottleneck; không NaN/âm; round_to_1k đúng.
- Guardrail floor/ceiling/max-delta/freeze chạy đúng thứ tự.
- PricingContext không có PassengerSafetyContext, search history hoặc support_need.
- Public endpoint request/response khớp OpenAPI canonical examples.

## 8.2 Transaction và integration tests

- Hai hold cạnh tranh: một thành công, một 409; không partial hold.
- Retry cùng Idempotency-Key trả cùng kết quả.
- Confirm sau expiry trả 410; expiry giải phóng đủ mọi leg.
- Giá và seat plan không đổi qua offer → hold → confirm.
- Scenario invalid/reset lỗi không làm thay đổi state đang chạy.

## 8.3 Backtest và metric tests

- Baseline và Âu Lạc nhận cùng event checksum cho từng seed.
- Báo median + min/max + raw result; failed seed không bị loại im lặng.
- Metric có đơn vị và mẫu số: false sold-out, empty seat-km, passenger-km, revenue, acceptance rate.
- Cùng seed/input tạo cùng report checksum.

## 8.4 NFR và demo acceptance

- Offer p95 < 1 giây; resolver < 200 ms; scenario reset < 3 giây ở seed scale.
- Màu heatmap có legend và không là tín hiệu duy nhất; keyboard/contrast cơ bản.
- Empty, stale, conflict, expired và failed states có retry/action rõ ràng.
- Golden path chạy 3/3 dưới 90 giây mỗi lần.
- Không nhập PII thật; không dùng \_ground_truth làm feature.

**DEFINITION OF DONE**

Demo chỉ được coi là hoàn thành khi: reset deterministic; baseline từ chối golden request; Âu Lạc tìm đúng same-seat gap; offer hiển thị price/bid/versions/expiry; hold nguyên tử; guardrail clamp thật; backtest nhiều seed; heatmap cập nhật; decision truy vết được; smoke test 3/3; video và AI log sẵn sàng.

# 9\. Rủi ro và fallback

| **Rủi ro**                | **Tác động**           | **Fallback đã khóa**                                                     | **Trigger**                   |
| ------------------------- | ---------------------- | ------------------------------------------------------------------------ | ----------------------------- |
| Contract chưa freeze      | Vỡ tích hợp            | Dừng code core; chốt canonical examples trước.                           | Sau giờ 2 còn open P0 schema. |
| Forecast trễ              | Block allocation       | Dùng deterministic forecast fixture versioned.                           | Không có output giờ 3.        |
| Backtest chậm             | Thiếu evidence         | Giảm event stream nhưng giữ đủ 5 seed và metric.                         | Một run > 10 giây.            |
| PostgreSQL lỗi môi trường | Block transaction path | Dùng Docker volume sạch và seed reset; không đổi sang SQLite giữa chừng. | Không recover trong 30 phút.  |
| UI chờ backend            | Mất thời gian          | Giữ fixture adapter; thay service từng module.                           | API thật chưa sẵn giờ 10.     |
| P1 chiếm thời gian        | P0 không ổn định       | Không triển khai P1; giữ prototype/static evidence.                      | Golden path chưa 3/3 giờ 18.  |
| Live demo lỗi             | Pitch thất bại         | Video backup + screenshots + checksum evidence.                          | Bất kỳ smoke fail sau giờ 23. |

# 10\. Ma trận traceability Review G01-G20

| **ID** | **Nội dung cần sửa**     | **Cách xử lý trong plan/SDD v2**                               | **Mức** |
| ------ | ------------------------ | -------------------------------------------------------------- | ------- |
| G01    | Cắt scope 30h            | P0/P1/P2 và cut line rõ; bỏ production extras khỏi MVP.        | P0      |
| G02    | Semantics merging        | Một continuous_same_seat; reused_gap chỉ là label.             | P0      |
| G03    | Decision pipeline        | Snapshot→seat→price→guardrail→bid→offer→hold→confirm.          | P0      |
| G04    | Atomic multi-leg hold    | CAS toàn bộ cells trong một transaction; rollback all.         | P0      |
| G05    | service_run              | Khóa train/date/direction dùng xuyên suốt.                     | P0      |
| G06    | Fare/quote lifecycle     | FareProduct O-D; expiry; freeze; round-to-1k.                  | P0      |
| G07    | Offer contract           | Public orchestration APIs và typed responses/errors.           | P0      |
| G08    | Quantity/profile/consent | quantity=1; safety context tách; consent ở P2.                 | P0      |
| G09    | Bỏ SOLD→SOLD             | Không di chuyển confirmed booking trong MVP.                   | P0      |
| G10    | Bid-price trung thực     | Công thức approximation, version và fixtures.                  | P0      |
| G11    | Protection ≠ HELD        | Chỉ TTL/hủy giải phóng customer hold.                          | P0      |
| G12    | Metric tái lập           | Cùng stream, 5 seed, checksum, median/range.                   | P0      |
| G13    | Forecast observations    | Result/reason/quantity/horizon/source/dedup.                   | P1      |
| G14    | Decision metadata        | Append-only DecisionRecord với versions/input hash.            | P1      |
| G15    | Approve/override         | P1 lifecycle có reason, expected_version và audit.             | P1      |
| G16    | NFR/test                 | Latency, determinism, recovery, accessibility, contract tests. | P1      |
| G17    | UI states                | Loading/empty/stale/conflict/expired/clamped/no-option.        | P1      |
| G18    | Index/ownership          | service_run indexes; SeatStateManager single writer.           | P1      |
| G19    | Dữ liệu nhạy cảm         | SafetyContext tách PricingContext; log code tối thiểu.         | P1      |
| G20    | Chất lượng tài liệu      | TOC/headings/tables/revision/traceability/render QA.           | P1      |

# 11\. Checklist dành cho reviewer

## 11.1 Quyết định cần xác nhận

\[ \] Chấp thuận SDD v2 là target MVP design thay vì as-built.

\[ \] Chấp thuận FastAPI + PostgreSQL + React và loại Redis/worker/JWT production khỏi P0.

\[ \] Chấp thuận scope một service run, một chiều, một hạng và quantity=1.

\[ \] Chấp thuận seed chuẩn bị trước T0 và năm seed backtest cố định.

\[ \] Chấp thuận feature freeze giờ 18 và stop-rule không làm P1/P2 nếu P0 chưa 3/3.

## 11.2 Quality gate tài liệu

\[ \] Mọi G01-G20 có vị trí xử lý và không còn mâu thuẫn với phần MVP.

\[ \] Không còn từ khóa/claim sai: demo 48h, quantity=2, EMSR-b chưa chứng minh, protected_ok, SOLD→SOLD tự động.

\[ \] TOC, heading, caption, cross-reference, table geometry và page numbering hoạt động.

\[ \] Tất cả trang đã render và kiểm tra ở 100%; không clipping, overlap, font lỗi hoặc bảng vỡ.

## 11.3 Sign-off

| **Reviewer**   | \_**\_**\_**\_**\_**\_**\_**\_**                         | **Ngày**      | \_**\_/ \_\_** / 2026 |
| -------------- | -------------------------------------------------------- | ------------- | --------------------- |
| **Quyết định** | Approve / Approve with changes / Reject                  | **Phiên bản** | 2.0-plan              |
| **Ghi chú**    | \_**\_**\_**\_**\_**\_**\_**\_**\_**\_**\_**\_**\_\_\_\_ | **Owner**     | Integration Lead      |

**KHUYẾN NGHỊ CUỐI**

Phê duyệt kế hoạch này làm nguồn duy nhất cho giai đoạn triển khai. Các tài liệu cũ được lưu archive để truy vết nhưng không tiếp tục dùng làm contract.

# Phụ lục A. Lịch sử phiên bản

| **Phiên bản**  | **Ngày**   | **Trạng thái**     | **Thay đổi**                               |
| -------------- | ---------- | ------------------ | ------------------------------------------ |
| 1.0            | 17/07/2026 | Superseded         | SDD kiến trúc ban đầu.                     |
| Review MVP 30h | 17/07/2026 | Superseded         | Rà soát G01-G20 và kế hoạch 6 người.       |
| 2.0-plan       | 17/07/2026 | Final review draft | Kế hoạch hợp nhất cho SDD v2 và 5 dev/30h. |
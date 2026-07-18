# Prompt cho agent sinh giao dien FE

Dung prompt duoi day de dua cho mot coding/design agent tao giao dien web cho du an Au Lac Railway. Bo anh mockup hien co nam tai Google Drive:
https://drive.google.com/drive/folders/1bl63jMuiBgWWI9hwjjv_Y6mVVdCExc2Y

Hay dinh kem link/anh mockup vao cung prompt nay va yeu cau agent xem anh nhu visual reference, khong copy may moc tung pixel.

```text
Ban la senior frontend engineer + UI/UX designer. Hay xay dung giao dien web MVP cho he thong Au Lac Railway Revenue Management / Booking Demo dua tren repo hien co va bo anh mockup toi dinh kem.

Mockup reference:
- Google Drive folder: https://drive.google.com/drive/folders/1bl63jMuiBgWWI9hwjjv_Y6mVVdCExc2Y
- Truoc khi code, hay xem tat ca anh mockup trong folder nay.
- Dung mockup de nam layout, nhom thong tin, flow man hinh va visual direction.
- Khong copy may moc neu mockup con hoc thuat/qua phuc tap; hay giu cau truc thong tin nhung lam lai de nhan vien van hanh de hieu hon, gon hon, it chu hon.
- Neu folder khong truy cap duoc, dung noi dung prompt nay lam source chinh va bao ro can cap quyen xem anh.

Muc tieu san pham:
- Day la cong cu noi bo cho nhan vien dieu do, revenue manager va nguoi demo nghiep vu duong sat.
- Giao dien phai than thien voi nhan vien van hanh, de hieu trong 2 giay, khong hoc thuat, khong giong dashboard nghien cuu.
- Toi uu cho thao tac nhanh: xem tau, xem ghe, tao offer, giu cho, confirm, xem ly do gia, xem bang chung compliance/backtest.
- Ngon ngu hien thi: tieng Viet.

Ngu canh can doc trong repo:
- `docs/TECHNICAL_OVERVIEW.md`
- `docs/API_Contract.md`
- `backend/openapi.yaml`
- `plan/00_MASTER_PLAN.md`
- `plan/DEV4_FE_OPS_MATRIX.md`
- `plan/DEV5_FE_BOOKING_BACKTEST.md`
- `backend/seed/`

Tech stack FE de xuat va phai dung:
- Next.js + React + TypeScript, uu tien App Router.
- Tailwind CSS cho styling.
- shadcn/ui hoac Radix UI cho Dialog, Tabs, Select, Tooltip, Toast, Sheet.
- lucide-react cho icon.
- TanStack Query cho API state, loading, retry, cache invalidation.
- Typed API client sinh tu `backend/openapi.yaml`, khong tu viet type tay neu co the generate.
- Fixture adapter doc `backend/seed/` khi API that chua san sang, nhung shape response phai khop OpenAPI.
- Recharts hoac Apache ECharts cho chart/backtest; uu tien Recharts neu can gon.
- Vitest + React Testing Library cho unit/component test.
- Playwright cho smoke test cac luong chinh.
- Dung Server Components cho layout/static shell khi hop ly; cac man tuong tac nhu heatmap, booking lab, countdown, chart dung Client Components (`"use client"`).
- API base URL cau hinh bang `NEXT_PUBLIC_API_BASE_URL`; fixture mode cau hinh bang `NEXT_PUBLIC_USE_FIXTURES=true`.

Kien truc thu muc mong muon:
- `web/app/`: Next.js App Router, route groups/layouts/pages.
- `web/app/ops/page.tsx`: S01 Ops Overview.
- `web/app/ops/seatmap/page.tsx`: S02 Seat-Leg Matrix.
- `web/app/booking/page.tsx`: S03 Booking Lab.
- `web/app/backtest/page.tsx`: S04 Backtest Comparison.
- `web/app/decisions/[decisionId]/page.tsx`: S05 Decision Detail.
- `web/app/compliance/page.tsx`: S06 Compliance Panel.
- `web/src/api/`: typed client, fixture client, query keys.
- `web/src/components/`: design system dung chung, layout, table, status badge, money, segment label, seat heatmap.
- `web/src/lib/`: format money VND, date/time, error mapping, idempotency key helper.
- `web/src/providers/`: TanStack Query provider, theme provider neu can.

Nguyen tac nghiep vu bat buoc:
- Frontend KHONG tu ghep quyet dinh kinh doanh. Backend tra decision hoan chinh thi FE chi hien thi.
- Khong viet logic kieu `if (bid > price) reject` trong FE.
- Khong doc `generated_data/data/*.parquet` trong runtime FE.
- Tien la int64 VND, format ro rang, lam tron nghin neu hien thi.
- Segment/leg danh so 1-based: L1..L7.
- `seat_plan` dung `segment_from`, `segment_to` bao gom ca hai dau.
- Seat id format: `C01-S017`.
- Golden scenario: `service_run_id = SE1_2026-06-15_LE`.
- Golden request: `THO -> DHO`, ngay `2026-06-15`, seat class `NGOI_MEM_DH`, quantity `1`.
- Golden gap: ghe `C01-S017`, FREE o L3-L4, SOLD o L1-L2 va L5-L7.
- Gia phai the hien ro rang khong doi qua flow offer -> hold -> confirm.
- Moi thao tac ghi `/holds` va `/bookings/{hold_id}/confirm` phai co `Idempotency-Key`.
- Luon hien 4 version/identity quan trong khi co offer: `service_run_id`, `matrix_version`, `forecast_version`, `policy_version`.

Phong cach UI:
- Lay bo anh mockup dinh kem lam huong bo cuc, nhung hay lam gon va than thien hon.
- Phong cach: operational, toi gian, sang, ro, khong academic.
- Nen trang/xam rat nhat, chu dam de doc, dung mau chuc nang co y nghia:
  - xanh la: co the ban / accept / confirmed
  - vang: dang giu / can chu y / clamped
  - do: tu choi / loi / vi pham
  - xanh duong: thong tin / selected / AI suggestion
  - xam: free/neutral/inactive
- Khong dung palette mot mau qua nang, khong dung gradient lon, khong dung hero marketing.
- Bo cuc desktop uu tien sidebar trai + top status bar + content dense. Mobile/tablet phai responsive.
- Card chi dung cho widget/lap lai/thong tin dong khung; khong long card trong card.
- Text ngan, dung ngon ngu nhan vien: "Co the ban", "Dang giu", "Da ban", "Khoang trong ban lai", "Gia khoa", "Can tai lai", "Het han".
- Moi icon-only button phai co tooltip va aria-label.

Man hinh can xay:

1. S01 Ops Overview
- Hien tong quan chuyen `SE1_2026-06-15_LE`: occupancy, revenue, empty seat-km, passenger-km, false sold-out rate.
- Hien bottlenecks va underused segments.
- Hien recent decisions.
- Co nut reset scenario va refresh forecast.
- Co status versions/checksum/last updated.
- API lien quan: `POST /api/v1/demo/scenarios/{scenario_id}/reset`, `POST /api/v1/demo/forecasts/refresh`, `GET /api/v1/demo/overview`.

2. S02 Seat-Leg Matrix
- Heatmap ghe x doan: 40 ghe x 7 leg.
- Cot: L1 HNO-NBI, L2 NBI-THO, L3 THO-VIN, L4 VIN-DHO, L5 DHO-HUE, L6 HUE-DNA, L7 DNA-SGO.
- Hang: seat id `C01-S001` den `C01-S040`.
- Trang thai: FREE, HELD, SOLD, reused_gap.
- Golden gap `C01-S017` L3-L4 phai noi bat ngay lap tuc.
- Bat buoc co legend. Mau khong duoc la tin hieu duy nhat: them pattern/icon/text viet tat trong cell.
- Co filter theo seat class/status va nut focus "Golden gap".
- API lien quan: `GET /api/v1/demo/seatmap`, `GET /api/v1/demo/analytics`.

3. S03 Booking Lab
- Man hinh quan trong nhat cho demo.
- Form request mac dinh:
  - service_run_id `SE1_2026-06-15_LE`
  - origin `THO`
  - dest `DHO`
  - seat_class `NGOI_MEM_DH`
  - quantity `1`
- Flow:
  1. Tao offer qua `POST /api/v1/offers`.
  2. Hien seat plan: `C01-S017`, segment L3-L4, reused_gap true.
  3. Hien price breakdown 3 muc: `gia_goc_vnd -> gia_niem_yet_vnd -> gia_cuoi_vnd`.
  4. Hien bid total va bid theo segment.
  5. Hien decision ACCEPT/REJECT, decision_record_id, expires_at countdown.
  6. Bam "Giu cho" goi `POST /api/v1/holds` voi Idempotency-Key va expected_matrix_version.
  7. Hien HELD va noi ro "Gia da khoa".
  8. Bam "Xac nhan" goi `POST /api/v1/bookings/{hold_id}/confirm`.
  9. Hien CONFIRMED, booking_id, final_price_vnd y het gia da khoa.
- Co nut "So sanh baseline" de noi cau chuyen: baseline tu choi, Au Lac phuc vu duoc tren khoang trong ghe.

4. S04 Backtest Comparison
- Chay backtest voi 5 seed: `20260717`, `20260718`, `20260719`, `20260720`, `20260721`.
- Hien baseline vs Au Lac:
  - revenue median
  - acceptance rate
  - false sold-out
  - empty seat-km
  - passenger-km
  - min/max va raw result tung seed
- Khong an seed fail. Failed seed phai hien ro va co ly do.
- API lien quan: `POST /api/v1/backtests`, `GET /api/v1/backtests/{report_id}`.

5. S05 Decision Detail
- Man hinh giai thich/audit cho mot `decision_id`.
- Hien:
  - base fare, AI suggested price, final price
  - bid price total va breakdown
  - rules fired theo thu tu
  - violations/guardrails/clamped
  - audit timeline
  - input_hash va versions
- Day la XAI bang rule trail, khong can SHAP hay bieu do phuc tap.
- API lien quan: `GET /api/v1/decisions/{decision_id}`.

6. S06 Compliance Panel
- Hien tinh trang compliance: san/tran gia, max delta, CSXH ap sau cung, price lock sau hold, pricing khong dung sensitive features.
- Trang thai ly tuong: "0 vi pham".
- Hien bang cac rule/guardrail va ket qua pass/fail.
- Neu co violation thi dung mau do + noi cach xu ly, khong chi dung icon.

Error states bat buoc:
- `NO_SAME_SEAT_OPTION`: Khong tim duoc cho lien tuc cho hanh trinh nay.
- `SOLD_OUT_TRUE`: Da het cho that.
- `ALLOCATION_REJECTED`: Tu choi theo quota/gia san co hoi.
- `STALE_SNAPSHOT`: Du lieu da thay doi - tai lai.
- `SEAT_CONFLICT`: Cho vua duoc nguoi khac giu.
- `OFFER_EXPIRED`: De nghi da het han - tao offer moi.
- `HOLD_EXPIRED`: Giu cho da het han - chon lai.
- `POLICY_UNAVAILABLE`: Chinh sach gia chua san sang.
- Moi loi phai co hanh dong tiep theo: Tai lai, Tao offer moi, Thu lai, Quay ve overview.

Accessibility va UX:
- Contrast dat WCAG AA.
- Font body toi thieu 14-16px, line-height de doc.
- Touch target toi thieu 44px.
- Keyboard navigation day du cho form, modal, table/heatmap focus.
- Loading skeleton cho dashboard/seatmap.
- Empty state co action.
- Retry ro rang khi API fail.
- Hien countdown offer/hold bang so de doc, khong chi mau.
- Heatmap khong duoc phu thuoc vao mau duy nhat.

Tieu chi hoan thanh:
- `npm install`, `npm run dev` chay duoc.
- Co route toi thieu: `/ops`, `/ops/seatmap`, `/booking`, `/backtest`, `/decisions/[decisionId]`, `/compliance`.
- Mac dinh vao `/booking` hoac `/ops` la thay ngay golden scenario.
- Fixture mode chay duoc neu backend chua bat.
- API mode co the cau hinh bang env `NEXT_PUBLIC_API_BASE_URL`.
- Fixture mode co the bat bang env `NEXT_PUBLIC_USE_FIXTURES=true`.
- Tao offer -> hold -> confirm chay duoc bang fixture va san sang doi sang API that.
- Chay `npm run typecheck`, `npm run lint`, `npm run build` khong loi.
- Co README ngan trong `web/` huong dan chay.
```

Ghi chu khi dung voi anh mockup:
- Hay dua toan bo anh mockup cho agent trong cung request.
- Neu anh la giao dien cu/hoc thuat, noi ro: "giu cau truc thong tin, nhung lam lai visual de nhan vien van hanh de hieu hon".
- Yeu cau agent sau khi implement phai chup screenshot desktop va mobile de tu so voi mockup.

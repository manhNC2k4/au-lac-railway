# UI/API design: booking approval flow with human in the loop

## 1. Muc tieu luong moi

Luong hien tai dang la:

1. User tim ve.
2. FE goi `POST /api/v1/offers`.
3. Server tra ngay 1 offer gom ghe + gia.
4. User giu cho bang `POST /holds`, roi thanh toan bang `POST /bookings/{hold_id}/confirm`.

Luong moi can la:

1. User chon hanh trinh/ve.
2. User thay man hinh cho: "Dang gui yeu cau len trung tam dieu hanh".
3. Server xu ly request, sinh cac phuong an ghe + gia + ghe AI goi y.
4. Admin nhan tung yeu cau trong hang doi, xem giai thich AI, duyet/tu choi/chinh gia trong guardrail.
5. Sau khi admin duyet, man hinh user tu cap nhat va hien danh sach ghe + gia + ghe AI goi y.
6. User chon ghe, giu cho, thanh toan.
7. Sau confirm, DB co ban ghi `booking` + audit/proposal log de nguoi van hanh doc lai.

## 2. Ket luan sau khi xem API contract hien tai

API hien co dung duoc cho nua sau cua flow:

- `POST /offers`: tinh gia + tao offer + decision record.
- `POST /offers/{offer_id}/override`: admin chinh gia offer trong guardrail.
- `POST /holds`: giu ghe atomic theo offer da chon.
- `POST /bookings/{hold_id}/confirm`: xac nhan thanh toan, tao booking.
- `GET /decisions/{decision_id}`: xem giai thich AI/audit.
- `proposal_log`, `decision_record`, `offer`, `seat_hold`, `booking`: da co nen co the trace duoc luong.

Thieu cho dung yeu cau moi:

- Chua co "booking request" de user cho admin duyet.
- `POST /offers` hien tra gia ngay cho user, chua co trang thai `PENDING_ADMIN`.
- `POST /offers` hien chi tra 1 phuong an offer, chua tra danh sach nhieu ghe/gia de user chon.
- Chua co API list hang doi duyet tung request cho admin.
- Chua co API user polling/SSE de biet yeu cau da duyet chua.

## 3. Trang thai nghiep vu de xuat

Them entity `booking_request` lam lop nam giua user search va offer/hold.

Trang thai:

- `SUBMITTED`: user vua gui yeu cau.
- `AI_PROCESSING`: server dang tinh ghe/gia.
- `PENDING_ADMIN`: co de xuat AI, dang cho admin duyet.
- `APPROVED`: admin da duyet, user duoc xem danh sach ghe/gia.
- `REJECTED`: admin tu choi, user thay ly do va hanh dong tiep theo.
- `EXPIRED`: het thoi gian cho hoac offer het han.
- `SELECTED`: user da chon 1 phuong an va tao hold.
- `CONFIRMED`: thanh toan xong, da co booking.

Candidate status:

- `AI_SUGGESTED`: server sinh ra.
- `APPROVED`: admin cho hien voi user.
- `REJECTED`: admin an phuong an nay.
- `PRICE_OVERRIDDEN`: admin sua gia trong guardrail.
- `SELECTED`: user chon phuong an nay.

## 4. Luong UI user

### Screen U1 - Tim ve

Route de xuat: `/booking`

Noi dung:

- Form ga di, ga den, ngay di, so khach, loai ghe.
- Nut primary: "Gui yeu cau".
- Sau submit khong hien gia ngay. Chuyen sang waiting screen.

API:

```http
POST /api/v1/booking-requests
```

Response:

```json
{
  "data": {
    "request_id": "br_8f13c2",
    "status": "SUBMITTED",
    "service_run_id": "SE1_2026-06-15_LE",
    "created_at": "2026-06-15T09:00:00Z",
    "expires_at": "2026-06-15T09:15:00Z"
  }
}
```

### Screen U2 - Man hinh cho khach hang

Route de xuat: `/booking/requests/{request_id}/waiting`

Noi dung:

- Stepper: `Gui yeu cau` -> `AI tinh gia` -> `Cho admin duyet` -> `Chon ghe`.
- Skeleton/loader, thoi gian da cho, ma yeu cau.
- Khong hien gia khi chua duyet.
- Nut phu: "Huy yeu cau", "Doi hanh trinh".

Polling moi 2-3 giay:

```http
GET /api/v1/booking-requests/{request_id}
```

Neu muon realtime tot hon:

```http
GET /api/v1/booking-requests/{request_id}/events
```

SSE event:

```json
{ "status": "APPROVED", "request_id": "br_8f13c2" }
```

### Screen U3 - Danh sach ghe va gia da duyet

Route de xuat: `/booking/requests/{request_id}/offers`

Hien khi request `APPROVED`.

Noi dung:

- Danh sach ghe/candidate da duyet.
- Ghe AI goi y dat len dau, co badge "AI goi y".
- Moi dong ghe gom: seat id, toa, chang ap dung, gia cuoi, ly do ngan gon, can doi ghe hay khong.
- Neu ghe ghep nhieu leg: hien disclosure ga doi + so lan doi cho.
- Nut primary tren tung candidate: "Chon ghe nay".

Response mau:

```json
{
  "data": {
    "request_id": "br_8f13c2",
    "status": "APPROVED",
    "approved_at": "2026-06-15T09:02:10Z",
    "candidates": [
      {
        "candidate_id": "bc_01",
        "offer_id": "offer_abc",
        "rank": 1,
        "ai_recommended": true,
        "seat_plan": [
          { "seat_id": "C01-S017", "segment_from": 3, "segment_to": 4, "requires_seat_change": false }
        ],
        "pricing": {
          "gia_goc_vnd": 285000,
          "gia_niem_yet_vnd": 307000,
          "gia_cuoi_vnd": 307000
        },
        "decision_record_id": "dr_edfab201f59b",
        "explanation_short": "Gia du bid-price, ghe lien tuc, tan dung khoang trong cuc bo.",
        "expires_at": "2026-06-15T09:07:10Z"
      }
    ]
  }
}
```

Khi user chon:

```http
POST /api/v1/holds
Idempotency-Key: <uuid>
```

Body dung API hien co:

```json
{
  "offer_id": "offer_abc",
  "expected_matrix_version": 5,
  "passenger_name": "Nguyen Van A",
  "consent": false
}
```

### Screen U4 - Thanh toan

Route de xuat: `/booking/hold`

Dung API hien co:

```http
POST /api/v1/bookings/{hold_id}/confirm
Idempotency-Key: <uuid>
```

Sau confirm:

- Hien `booking_id`.
- Hien gia da khoa bang dung `final_price_vnd`.
- Hien link/ma audit neu co.

## 5. Luong UI admin

### Screen A1 - Hang doi duyet booking

Route de xuat: `/admin/booking-requests`

Layout:

- Bang yeu cau dang `PENDING_ADMIN`.
- Cot: thoi gian cho, hanh trinh, so khach, loai ghe, doanh thu AI, muc uu tien, trang thai, SLA.
- Filter theo chuyến tau, trang thai, ga, loai ghe.
- Badge can chu y: gia cham guardrail, ghep nhieu ghe, bid-price cao, khach uu tien.

API:

```http
GET /api/v1/admin/booking-requests?status=PENDING_ADMIN&service_run_id=...
X-Actor-Role: revenue_manager
```

### Screen A2 - Chi tiet yeu cau can duyet

Route de xuat: `/admin/booking-requests/{request_id}`

Bo cuc 3 vung:

- Trai: thong tin hanh trinh, user input, thoi gian cho, SLA.
- Giua: danh sach candidate ghe/gia do AI sinh.
- Phai: audit/giai thich, bid-price, rule fired, guardrail, matrix/forecast/policy version.

Admin action:

- Duyet tat ca candidate hop le.
- Duyet rieng 1-vai candidate.
- Sua gia candidate trong guardrail.
- Tu choi request voi ly do.
- Yeu cau server tinh lai neu seat conflict/stale.

API duyet:

```http
POST /api/v1/admin/booking-requests/{request_id}/approve
X-Actor-Role: revenue_manager
```

Body:

```json
{
  "decided_by": "nguyen_van_dieu_do",
  "approved_candidates": [
    { "candidate_id": "bc_01" },
    { "candidate_id": "bc_02", "override_price_vnd": 300000, "reason": "Can bang gia gan voi gia niem yet" }
  ],
  "note": "Duyet 2 ghe tot nhat cho khach chon."
}
```

API tu choi:

```http
POST /api/v1/admin/booking-requests/{request_id}/reject
X-Actor-Role: revenue_manager
```

Body:

```json
{
  "decided_by": "nguyen_van_dieu_do",
  "reason_code": "NO_CAPACITY_FOR_REQUEST",
  "note": "Khong con ghe phu hop trong guardrail."
}
```

## 6. API contract de xuat them

### Passenger APIs

```http
POST /booking-requests
GET /booking-requests/{request_id}
DELETE /booking-requests/{request_id}
POST /booking-requests/{request_id}/select
GET /booking-requests/{request_id}/events
```

`POST /booking-requests/{request_id}/select` la wrapper tien loi. No co the goi logic giong `/holds` nhung truyen `candidate_id` thay vi `offer_id`.

```json
{
  "candidate_id": "bc_01",
  "passenger_name": "Nguyen Van A",
  "consent": false
}
```

Tra ve:

```json
{
  "data": {
    "hold_id": "hold_a7d2d70f2163",
    "status": "ACTIVE",
    "expires_at": "2026-06-15T09:12:10Z",
    "new_matrix_version": 6
  }
}
```

### Admin APIs

```http
GET /admin/booking-requests
GET /admin/booking-requests/{request_id}
POST /admin/booking-requests/{request_id}/approve
POST /admin/booking-requests/{request_id}/reject
POST /admin/booking-requests/{request_id}/recompute
```

### Ghi chu tuong thich voi API hien co

- Moi candidate approved nen co `offer_id` that de tai su dung `/holds`.
- Neu admin override gia, co the tai su dung logic cua `POST /offers/{offer_id}/override`.
- `POST /bookings/{hold_id}/confirm` giu nguyen, vi day la diem tao booking that.

## 7. DB de xuat them

Them bang request:

```sql
CREATE TABLE booking_request (
    request_id VARCHAR(50) PRIMARY KEY,
    service_run_id VARCHAR(50) REFERENCES service_run(service_run_id),
    origin_station_id VARCHAR(20) REFERENCES station(station_id),
    dest_station_id VARCHAR(20) REFERENCES station(station_id),
    seat_class VARCHAR(20) NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    priority_passenger BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL,
    selected_candidate_id VARCHAR(50),
    hold_id VARCHAR(50),
    booking_id VARCHAR(50),
    reject_reason_code VARCHAR(80),
    reject_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

Them bang candidate:

```sql
CREATE TABLE booking_candidate (
    candidate_id VARCHAR(50) PRIMARY KEY,
    request_id VARCHAR(50) REFERENCES booking_request(request_id),
    offer_id VARCHAR(50) REFERENCES offer(offer_id),
    rank INT NOT NULL,
    ai_recommended BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL,
    seat_plan JSONB NOT NULL,
    original_price_vnd BIGINT NOT NULL,
    approved_price_vnd BIGINT,
    decision_record_id VARCHAR(50) REFERENCES decision_record(decision_id),
    admin_note TEXT,
    decided_by VARCHAR(50),
    decided_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

Audit:

- Moi request tao ghi `proposal_log.loai = 'PRICE'` hoac them `loai = 'BOOKING_REQUEST'`.
- Moi approval/reject ghi `proposal_log.actor = decided_by`.
- Moi override gia tiep tuc ghi `proposal_log.loai = 'OVERRIDE'`.
- Booking confirmed giu bang `booking` hien co.

## 8. Logic backend de xuat

Khi `POST /booking-requests`:

1. Tao `booking_request` status `SUBMITTED`.
2. Chuyen `AI_PROCESSING`.
3. Sinh candidate.
   - MVP nhanh: goi lai logic `OfferService.build_offer()` nhieu lan theo cac ghe tot nhat.
   - Ban chuan: tach resolver de tra top N seat plans, moi plan tinh pricing rieng.
4. Insert cac `offer` an voi user.
5. Insert `booking_candidate`.
6. Chuyen request sang `PENDING_ADMIN`.

Khi admin approve:

1. Kiem role `revenue_manager|admin`.
2. Kiem request dang `PENDING_ADMIN`.
3. Neu override price: validate guardrail nhu `/offers/{offer_id}/override`.
4. Mark candidate `APPROVED`.
5. Mark request `APPROVED`.
6. User polling/SSE nhan status moi.

Khi user select:

1. Kiem request `APPROVED`.
2. Kiem candidate `APPROVED`.
3. Goi hold logic theo `offer_id` va `expected_matrix_version`.
4. Mark request `SELECTED`, candidate `SELECTED`.
5. Chuyen sang payment.

Khi confirm:

1. Goi `POST /bookings/{hold_id}/confirm`.
2. Mark request `CONFIRMED`.
3. DB da co `booking`, `seat_hold`, `offer`, `decision_record`, `proposal_log`.

## 9. UX notes quan trong

- User waiting screen khong nen la spinner rong; phai co ma yeu cau, trang thai, thoi gian cho, va nut huy.
- Admin screen phai toi uu thao tac nhanh: keyboard-friendly, table dense, action ro rang.
- Khong dung mau lam y nghia duy nhat: status phai co text + icon/badge.
- Gia tien dung tabular number de khong nhay layout.
- Khi offer/candidate het han, user khong duoc hold nua; hien "Yeu cau da het han, tao yeu cau moi".
- Neu admin tu choi, user can thay ly do ngan gon va nut "Tim hanh trinh khac".
- Neu ghep nhieu ghe, bat buoc disclosure truoc khi user hold.

## 10. Thu tu implement khuyen nghi

1. Them API/DB `booking_request` + `booking_candidate`.
2. Them admin queue `/admin/booking-requests`.
3. Doi `/booking` submit sang `POST /booking-requests`, them waiting page.
4. Them approved offers page cho user.
5. Noi candidate approved vao `/holds` va `/confirm` hien co.
6. Them polling truoc, SSE/WebSocket de sau neu con thoi gian.

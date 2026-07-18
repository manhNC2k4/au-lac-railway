# Âu Lạc Railway Frontend

Frontend Next.js cho luồng đặt vé và màn vận hành. Ứng dụng chỉ dùng API thật theo
[`docs/API_Contract.md`](../docs/API_Contract.md); không có fixture hoặc fallback dữ liệu nghiệp vụ.

## Chạy local

Backend phải chạy ở `http://127.0.0.1:8000` hoặc địa chỉ được cấu hình qua `API_SERVER_URL`.

```bash
cd backend
docker compose up -d --build

cd ../web
cp .env.example .env.local
npm install
npm run dev
```

Mở `http://localhost:3000`. Next.js proxy `/api/v1/*` sang backend nên trình duyệt
không cần cấu hình CORS. `NEXT_PUBLIC_API_BASE_URL` chỉ cần dùng khi muốn trình duyệt
gọi trực tiếp một API đã bật CORS.

## Route chính

| Route | Chức năng |
|---|---|
| `/booking` | Luồng hành khách: offer → hold → confirm |
| `/admin/overview` | KPI và cảnh báo vận hành |
| `/admin/seat-matrix` | Ma trận ghế theo chặng |
| `/admin/analytics` | Dự báo, tải và bid-price theo chặng |
| `/admin/decisions` | Nhật ký và giải thích quyết định |
| `/admin/backtest` | So sánh backtest theo seed |
| `/admin/booking-lab` | Công cụ kiểm tra pipeline booking |

## Kiểm tra

```bash
npm run typecheck
npm test
npm run build
npm run test:e2e  # cần backend đang chạy
```

Tiền là số nguyên VND; segment đánh số `L1..L7`; mọi thao tác hold và confirm gửi
`Idempotency-Key`. Offer nhiều leg chỉ được giữ sau khi hành khách xác nhận đổi ghế.

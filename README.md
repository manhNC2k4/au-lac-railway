# 🚆 Âu Lạc Railway

**AI Cắt chặng · Ghép chặng · Giá vé linh hoạt cho vận tải hành khách đường sắt.**
Dự báo nhu cầu + tối ưu hoá phân bổ ghế theo **từng đoạn tuyến** — tối ưu doanh thu, giảm
ghế trống, trong hành lang pháp lý, có thể giải thích và kiểm toán.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-DB-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-000000?logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![LightGBM](https://img.shields.io/badge/LightGBM-Poisson-9ACD32)
![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-F7931E?logo=scikitlearn&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-HiGHS%20LP-8CAAE6?logo=scipy&logoColor=white)
![OR-Tools](https://img.shields.io/badge/OR--Tools-CP--SAT-EA4335?logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## Bài toán

Trên một chuyến tàu, **một ghế phục vụ nhiều khách trên các đoạn nối tiếp** (bán A→C, rồi
bán tiếp C→E). Phân bổ không tối ưu ⇒ ghế **trống ở đoạn này trong khi khách bị từ chối ở
đoạn khác**, báo "hết chỗ" oan, giá không phản ánh cung–cầu theo đoạn.

## Giải pháp

AI **dự báo cầu** theo (O–D, ngày, tàu, loại chỗ, lead-time) rồi **tối ưu ghế × đoạn**:

- **Dự báo** — Gradient Boosting **Poisson**, MASE ≈ 0.5 (thắng naïve), cập nhật liên tục.
- **Tách/Phân bổ** — **DLP** (LP đơn modular → nghiệm nguyên) + **bid price** theo đoạn (<10ms/chuyến).
- **Ghép chặng** — lấp khoảng trống & ghép nhiều ghế *chỉ khi bắt buộc*; đổi chỗ có đồng ý,
  loại trừ người cao tuổi/khuyết tật/trẻ đi một mình.
- **Xếp nhóm** — OR-Tools CP-SAT (cùng toa, ghế liền).
- **Định giá động** — tối đa `P(mua|r)·(giá − bid)` từ đường cầu; guardrail sàn/trần, cap
  ±5%/lần, giữ giá đã khoá, **giảm CSXH sau cùng**, **không** dùng dữ liệu cá nhân.
- **Nhả/tái phân bổ ghế** + **hàng chờ thông minh**.

## Kiểm chứng (Backtest)

Phát lại **đúng dòng yêu cầu lịch sử** qua 2 chính sách (**hệ cũ** vs **Âu Lạc AI**) trên
**cùng khách + cùng WTP** — so sánh phản thực có cặp, common random numbers.

```bash
python eval/backtest.py --dates 2026-02-14,2026-05-20 --trains SE1,SE3,SE5,SE7
```
**Mục tiêu pilot:** pax-km **+3–8%** · doanh thu **+3–10%** · ghế trống **−20%** · vé dọc
tuyến **+10%** · unmet **−15%** · **0 vi phạm** giá/chính sách · tính lại **near-real-time**.

## Bắt đầu nhanh

```bash
# Backend (API + DB)
cd backend && docker compose up -d db flyway && pip install -r requirements.txt
uvicorn src.api.main:app --reload            # docs: http://127.0.0.1:8000/docs

# Frontend (2 giao diện: user + admin)
cd web && npm install && npm run dev          # http://localhost:3000

# Model + thuật toán (offline) + backtest
pip install -r requirements.txt
python models/train_bt1_forecast.py && python models/estimate_elasticity.py
python eval/backtest.py --dates ... --trains ...
```
> Dữ liệu tổng hợp: `cd generated_data && python generate_data.py`. Trỏ dataset khác qua
> biến môi trường `AULAC_DATA=<path>` (và `AULAC_GT=<path>`).

## Công nghệ

`Python` · `FastAPI` · `PostgreSQL` · `Docker` · `Next.js` · `TypeScript` ·
`LightGBM`/`scikit-learn` (Poisson) · `SciPy HiGHS` (LP) · `OR-Tools CP-SAT` · `Parquet`

## Ghi chú

Dữ liệu **tổng hợp**, hiệu chuẩn theo mô men công bố của VNR (không phải dữ liệu vận hành
thật). Định giá **trong hành lang đã duyệt**, có **nhật ký kiểm toán**, tôn trọng đầy đủ
chính sách xã hội. Giao diện & thuật ngữ nghiệp vụ bằng **tiếng Việt**.

## License

Phát hành theo giấy phép **MIT** — xem [LICENSE](LICENSE).

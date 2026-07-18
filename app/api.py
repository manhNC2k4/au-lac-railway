# -*- coding: utf-8 -*-
"""FastAPI phục vụ 5 bài toán con — nạp model artifact, expose REST.

Chạy:  uvicorn app.api:app --reload --port 8001
Docs :  http://127.0.0.1:8001/docs

Lưu ý: cổng 8000 là của backend/docker-compose (tier 3, backend/src) — dùng 8001
ở đây để hai API không đụng cổng khi chạy song song.

Endpoint:
  GET  /health
  POST /bt1/forecast            — dự báo cầu 1 grain (model HGB Poisson)
  POST /bt2/ssm/state           — ma trận ghê×đoạn + LF (Seat State Matrix)
  POST /bt2/ssm/transaction     — áp 1 giao dịch real-time (BUY/HOLD/RELEASE)
  POST /bt3/analyze             — LF đoạn + quota + đoạn nghẽn/trống (DLP)
  POST /bt4/merge               — phương án ghế xếp hạng (ghép chặng)
  POST /bt5/price               — giá đề xuất + log giải thích
  POST /booking/quote           — CHAIN BT4→BT3→BT5 cho 1 yêu cầu đặt vé
"""
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.bt1_forecast import Forecaster
from app.bt2_ssm import SeatStateMatrix
from app.bt3_allocation import analyze_run, load_factor_route
from app.bt4_merge import find_options
from app.bt5_pricing import Pricer
from app.config import DATA

app = FastAPI(title="Au Lac Railway — 5 sub-problems", version="1.0")

# ---- artifact nạp 1 lần ----
_pricer = Pricer.load()
_forecaster = None            # nạp lười (model có thể chưa train khi mới mở)
_cal = pd.read_csv(DATA / "calendar_events.csv")
_cal = _cal[pd.to_numeric(_cal.tau_tet, errors="coerce").notna()].copy()
_cal["ngay"] = _cal["ngay"].astype(str)
_CAL_IDX = _cal.set_index("ngay").to_dict("index")


def get_forecaster():
    global _forecaster
    if _forecaster is None:
        _forecaster = Forecaster.load()
    return _forecaster


@lru_cache(maxsize=16)
def get_ssm(ngay_chay: str, mac_tau_csv: str | None) -> SeatStateMatrix:
    ssm = SeatStateMatrix()
    flt = mac_tau_csv.split(",") if mac_tau_csv else None
    ssm.build_date(ngay_chay, flt)
    return ssm


def _ctx(ngay_chay: str) -> dict:
    row = _CAL_IDX.get(ngay_chay, {})
    return {"ngay": ngay_chay, "tau_tet": int(row.get("tau_tet", 99)),
            "dow": int(row.get("dow", 0)), "la_le": str(row.get("la_le")) == "True",
            "dot_ban_ve": row.get("dot_ban_ve", "THUONG"),
            "H_horizon": int(row.get("H_horizon", 60)),
            "che_do_gia": row.get("che_do_gia", "LUAT")}


# ============ Schemas ============
class ForecastReq(BaseModel):
    origin: str; dest: str; date: str; train_id: str; seat_class: str = Field(examples=["K4"])
    da_ban_truoc_u14: int = 0; toc_do_ban_7d: int = 0; cu_ly_km: float = 0.0

class SSMReq(BaseModel):
    ngay_chay: str; chuyen_id: str; seat_class: str | None = None
    mac_tau_filter: str | None = None

class TxnReq(BaseModel):
    ngay_chay: str; chuyen_id: str; ga_di: str; ga_den: str; loai_cho: str
    action: str = Field(examples=["BUY", "HOLD", "RELEASE"]); seat_idx: int | None = None
    mac_tau_filter: str | None = None

class AnalyzeReq(BaseModel):
    ngay_chay: str; chuyen_id: str; mac_tau_filter: str | None = None

class MergeReq(BaseModel):
    ngay_chay: str; chuyen_id: str; ga_di: str; ga_den: str; loai_ghe: str
    uu_tien: bool = False; mac_tau_filter: str | None = None

class PriceReq(BaseModel):
    ngay_chay: str; chuyen_id: str; ga_di: str; ga_den: str; tier: str
    policy: dict | None = None; mac_tau_filter: str | None = None

class BookingReq(BaseModel):
    ngay_chay: str; chuyen_id: str; ga_di: str; ga_den: str; tier: str
    uu_tien: bool = False; policy: dict | None = None; mac_tau_filter: str | None = None


# ============ Endpoints ============
@app.get("/health")
def health():
    return {"status": "ok", "pricer": True, "forecaster_loaded": _forecaster is not None}


@app.post("/bt1/forecast")
def bt1_forecast(r: ForecastReq):
    ctx = _ctx(r.date)
    row = {"mac_tau": r.train_id, "ga_di": r.origin, "ga_den": r.dest,
           "seat_class": r.seat_class, "band": None, "dot_ban_ve": ctx["dot_ban_ve"],
           "che_do_gia": ctx["che_do_gia"], "dow": ctx["dow"],
           "da_ban_truoc_u14": r.da_ban_truoc_u14, "toc_do_ban_7d": r.toc_do_ban_7d,
           "cu_ly_km": r.cu_ly_km, "tau_tet": ctx["tau_tet"], "la_le": int(ctx["la_le"]),
           "H_horizon": ctx["H_horizon"], "sau_15_5": int(r.date >= "2026-05-15"),
           "q_lag_7": None, "rolling_mean_28": None}
    import numpy as np
    band = pd.cut([r.cu_ly_km], [0, 300, 900, 1800], labels=["ngan", "trung", "dai"])[0]
    row["band"] = band if isinstance(band, str) else (str(band) if band is not None else None)
    try:
        yhat = get_forecaster().predict_one(row)
    except FileNotFoundError:
        raise HTTPException(503, "Model BT1 chưa train — chạy models/train_bt1_forecast.py")
    return {"origin": r.origin, "dest": r.dest, "date": r.date, "train_id": r.train_id,
            "seat_class": r.seat_class, "forecast_demand": round(yhat, 3)}


@app.post("/bt2/ssm/state")
def bt2_state(r: SSMReq):
    ssm = get_ssm(r.ngay_chay, r.mac_tau_filter)
    try:
        seg = ssm.get_segment_meta(r.chuyen_id)
    except KeyError:
        raise HTTPException(404, f"chuyến {r.chuyen_id} không có trong ngày {r.ngay_chay}")
    lf = ssm.load_factor(r.chuyen_id)
    resp = {"chuyen_id": r.chuyen_id, "n_segments": int(len(seg)),
            "load_factor_theo_doan": [round(float(x), 4) for x in lf],
            "segment_meta": seg.to_dict("records")}
    if r.seat_class:
        m = ssm.get_state(r.chuyen_id, r.seat_class)
        resp["matrix_shape"] = list(m.shape)
        resp["occupied_cells"] = int((m != 0).sum())
    return resp


@app.post("/bt2/ssm/transaction")
def bt2_txn(r: TxnReq):
    ssm = get_ssm(r.ngay_chay, r.mac_tau_filter)
    ok = ssm.apply_transaction(r.model_dump(exclude_none=True))
    return {"applied": bool(ok), "chuyen_id": r.chuyen_id, "action": r.action}


@app.post("/bt3/analyze")
def bt3_analyze(r: AnalyzeReq):
    ssm = get_ssm(r.ngay_chay, r.mac_tau_filter)
    fc = None
    try:
        return analyze_run(ssm, _pricer, r.chuyen_id, fc)
    except KeyError:
        raise HTTPException(404, f"chuyến {r.chuyen_id} không tồn tại")


@app.post("/bt4/merge")
def bt4_merge(r: MergeReq):
    ssm = get_ssm(r.ngay_chay, r.mac_tau_filter)
    try:
        return find_options(ssm, r.chuyen_id, r.loai_ghe, r.ga_di, r.ga_den, r.uu_tien)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/bt5/price")
def bt5_price(r: PriceReq):
    ssm = get_ssm(r.ngay_chay, r.mac_tau_filter)
    lf = load_factor_route(ssm, r.chuyen_id, r.ga_di, r.ga_den)
    ctx = _ctx(r.ngay_chay)
    mac_tau = r.chuyen_id.rsplit("_", 1)[0]
    return _pricer.quote(mac_tau, r.ga_di, r.ga_den, r.tier, ctx, lf, r.policy)


@app.post("/booking/quote")
def booking_quote(r: BookingReq):
    """CHAIN: BT4 chọn ghế -> BT3 LF hành trình -> BT5 định giá. Output = input nối tiếp."""
    ssm = get_ssm(r.ngay_chay, r.mac_tau_filter)
    from app.config import MACRO_CLASS
    macro = MACRO_CLASS.get(r.tier, r.tier)
    opts = find_options(ssm, r.chuyen_id, macro, r.ga_di, r.ga_den, r.uu_tien)
    if not opts["kha_thi"]:
        return {"kha_thi": False, "ly_do": opts["ly_do"], "phuong_an_ghe": [], "gia": None}
    chosen = opts["phuong_an"][0]
    lf = load_factor_route(ssm, r.chuyen_id, r.ga_di, r.ga_den)
    ctx = _ctx(r.ngay_chay)
    mac_tau = r.chuyen_id.rsplit("_", 1)[0]
    price = _pricer.quote(mac_tau, r.ga_di, r.ga_den, r.tier, ctx, lf, r.policy)
    return {"kha_thi": True, "phuong_an_ghe_chon": chosen,
            "tat_ca_phuong_an": opts["phuong_an"], "dinh_gia": price}

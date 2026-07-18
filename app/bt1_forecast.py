# -*- coding: utf-8 -*-
"""BÀI TOÁN CON 1 — inference wrapper cho model demand forecasting đã train.

Nạp artifacts/bt1_forecast_hgb.joblib + bt1_feature_spec.json, dựng đúng dtype hạng
mục (khóa vocab) rồi predict. Dùng bởi FastAPI và run_all.py.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.config import ARTIFACTS


class Forecaster:
    def __init__(self, model, spec: dict):
        self.model = model
        self.spec = spec
        self.cat_cols = spec["cat_cols"]
        self.num_cols = spec["num_cols"]
        self.cats = spec["cat_categories"]

    @classmethod
    def load(cls, art_dir: Path = ARTIFACTS) -> "Forecaster":
        model = joblib.load(Path(art_dir) / "bt1_forecast_hgb.joblib")
        spec = json.loads((Path(art_dir) / "bt1_feature_spec.json").read_text(encoding="utf-8"))
        return cls(model, spec)

    def _prep(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df.copy()
        for c in self.cat_cols:
            X[c] = pd.Categorical(X[c].astype(str) if c == "dow" else X[c],
                                  categories=self.cats[c])
        for c in self.num_cols:
            if c not in X:
                X[c] = np.nan
            X[c] = pd.to_numeric(X[c], errors="coerce")
        return X[self.cat_cols + self.num_cols]

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return np.clip(self.model.predict(self._prep(df)), 0, None)

    def predict_one(self, row: dict) -> float:
        return float(self.predict(pd.DataFrame([row]))[0])


class DemandModel:
    """B1–B4: dự báo TỔNG + CẦU CÒN LẠI theo lead-time u, cập nhật liên tục, drift.

    total(row)            : tổng vé dự kiến của grain (model HGB Poisson).
    F(u|band,tet)         : tỷ lệ đã bán trước mốc u (booking curve từ data).
    remaining(row,u)      : total × (1 − F(u)) — cầu còn lại từ u đến giờ chạy.
    update(row,sold,u)    : blend model với pickup unconstrain sold/F(u) — cập nhật
                            khi có vé mới, KHÔNG cần retrain (near-real-time-ready).
    divergence(row,sold,u): (thực bán − kỳ vọng)/kỳ vọng — tín hiệu cho C2 nhả ghế.
    """

    BLEND_W = 0.5      # trọng số pickup khi update (0=chỉ model, 1=chỉ pickup)

    def __init__(self, forecaster: Forecaster, curves: dict):
        self.fc = forecaster
        self.u_grid = curves["u_grid"]
        self.curves = curves["curves"]

    @classmethod
    def load(cls, art_dir: Path = ARTIFACTS) -> "DemandModel":
        curves = json.loads((Path(art_dir) / "bt1_booking_curves.json").read_text(encoding="utf-8"))
        return cls(Forecaster.load(art_dir), curves)

    def _F(self, band: str, is_tet: bool, u: float) -> float:
        key = f"{band}|{int(is_tet)}"
        F = self.curves.get(key) or self.curves.get(f"trung|{int(is_tet)}")
        ui = min(max(int(round(u)), 0), len(F) - 1)
        return max(F[ui], 1e-4)

    def total(self, row: dict) -> float:
        return self.fc.predict_one(row)

    def remaining(self, row: dict, u: float) -> dict:
        band = row.get("band") or "trung"
        is_tet = abs(int(row.get("tau_tet", 99))) <= 21
        tot = self.total(row)
        F = self._F(band, is_tet, u)
        rem = tot * (1 - F)
        return {"total_demand": round(tot, 3), "remaining_demand": round(rem, 3),
                "F_u": round(F, 4), "u": u,
                "explain": (f"tổng={tot:.1f} vé (model Poisson; pickup={row.get('da_ban_truoc_u14',0)}, "
                            f"tau_tet={row.get('tau_tet')}, band={band}); "
                            f"F({u:.0f})={F:.2f} => còn lại {rem:.1f} vé")}

    def update(self, row: dict, sold_to_date: float, u: float) -> dict:
        """Cập nhật liên tục theo vé đã bán: unconstrain pickup rồi blend với model."""
        band = row.get("band") or "trung"
        is_tet = abs(int(row.get("tau_tet", 99))) <= 21
        F = self._F(band, is_tet, u)
        tot_model = self.total(row)
        tot_pickup = sold_to_date / F
        tot = (1 - self.BLEND_W) * tot_model + self.BLEND_W * tot_pickup
        rem = max(tot - sold_to_date, 0.0)
        return {"total_demand": round(tot, 3), "remaining_demand": round(rem, 3),
                "total_model": round(tot_model, 3), "total_pickup": round(tot_pickup, 3),
                "F_u": round(F, 4),
                "explain": (f"update tại u={u:.0f}: đã bán {sold_to_date:.0f}, F={F:.2f} "
                            f"=> pickup {tot_pickup:.1f}, model {tot_model:.1f}, "
                            f"blend {tot:.1f}, còn lại {rem:.1f}")}

    def divergence(self, row: dict, sold_to_date: float, u: float) -> dict:
        """Tín hiệu lệch dự báo (B3) cho C2: <0 = bán chậm hơn dự báo => nên nhả ghế giữ."""
        band = row.get("band") or "trung"
        is_tet = abs(int(row.get("tau_tet", 99))) <= 21
        expected = self.total(row) * self._F(band, is_tet, u)
        div = (sold_to_date - expected) / max(expected, 1e-6)
        return {"expected_sold": round(expected, 2), "actual_sold": sold_to_date,
                "divergence": round(div, 4),
                "explain": f"kỳ vọng đã bán {expected:.0f} tại u={u:.0f}, thực {sold_to_date:.0f} "
                           f"=> lệch {div:+.0%}"}

# -*- coding: utf-8 -*-
"""Đường cầu (elasticity) + bộ tối ưu giá kỳ vọng doanh thu.

P(mua | r, ngữ cảnh) = sigmoid(β0 + β_r·ln r + β_band + β_tet + β_lead), với
r = giá/F0. Ước lượng bởi models/estimate_elasticity.py từ search_log (KHÔNG cá nhân).

Tối ưu: chọn giá p trong [sàn, trần] tối đa E[đóng góp] = P(mua|p)·(p − c), với c =
chi phí cơ hội hành trình (tổng bid price DLP từ BT3). Cơ chế này:
  * đoạn NGHẼN (c cao) => giá tối ưu cao (bảo vệ chỗ cho khách giá trị cao)
  * đoạn TRỐNG (c thấp) => giá tối ưu thấp (hút khách, làm mượt cầu, tăng fill)
  * KHÔNG dùng dữ liệu cá nhân — giá niêm yết chung theo trạng thái, công bằng.
"""
import json
from pathlib import Path

import numpy as np

from app.config import ARTIFACTS, BAND_EDGES, BAND_LABELS


class Elasticity:
    def __init__(self, params: dict):
        self.p = params
        self.b0 = params["intercept"]
        self.coef = params["coef"]
        self.lead_edges = params["lead_edges"]
        self.lead_labels = params["lead_labels"]

    @classmethod
    def load(cls, path: Path = ARTIFACTS / "elasticity_params.json") -> "Elasticity | None":
        p = Path(path)
        if not p.exists():
            return None
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def _band(self, d_km: float) -> str:
        for i in range(len(BAND_LABELS)):
            if d_km <= BAND_EDGES[i + 1]:
                return BAND_LABELS[i]
        return BAND_LABELS[-1]

    def _lead_bin(self, u: float) -> str:
        for i in range(len(self.lead_labels)):
            if u <= self.lead_edges[i + 1]:
                return self.lead_labels[i]
        return self.lead_labels[-1]

    def prob_buy(self, r: float, d_km: float, is_tet: bool, u: float) -> float:
        z = self.b0 + self.coef["ln_r"] * np.log(max(r, 1e-3))
        band = self._band(d_km)
        for b in BAND_LABELS[1:]:
            if band == b:
                z += self.coef.get(f"band_{b}", 0.0)
        z += self.coef.get("is_tet", 0.0) * (1.0 if is_tet else 0.0)
        lb = self._lead_bin(u)
        for x in self.lead_labels[1:]:
            if lb == x:
                z += self.coef.get(f"lead_{x}", 0.0)
        return float(1.0 / (1.0 + np.exp(-z)))

    def optimal_price(self, f0: int, c_opportunity: float, d_km: float,
                      is_tet: bool, u: float, floor_r: float, ceil_r: float,
                      n_grid: int = 40) -> dict:
        """Tối đa E[đóng góp] = P(mua)·(p − c) trên lưới giá trong [floor_r, ceil_r]·F0."""
        rs = np.linspace(floor_r, ceil_r, n_grid)
        best = None
        for r in rs:
            p = r * f0
            pb = self.prob_buy(r, d_km, is_tet, u)
            contrib = pb * (p - c_opportunity)       # đóng góp kỳ vọng (net displacement)
            rev = pb * p                             # doanh thu kỳ vọng (để báo cáo)
            if best is None or contrib > best["contrib"]:
                best = {"r": float(r), "p": int(round(p)), "prob_buy": round(pb, 4),
                        "contrib": contrib, "exp_rev": rev}
        return best

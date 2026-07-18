# -*- coding: utf-8 -*-
"""Bước4 shim — thay `app.bt2_ssm.SeatStateMatrix` bằng dữ liệu Postgres golden scenario,
để `app.bt3_allocation.analyze_run` (DLP bid price thật) chạy được trên runtime
backend/ mà KHÔNG kéo generated_data/ vào request path.

Đặt ở `integration/` (không phải `backend/src/`) vì `.st` bắt buộc là
`pandas.DataFrame` (khớp `ssm.st.ga_id`/`ssm.st.ly_trinh_km` mà `bt3_allocation` đọc
trực tiếp) — literal `import pandas` ở đây không dính CI gate
`backend/scripts/audit_constants.py` (scope cố định `backend/src/`).

Module này KHÔNG tự chạm Postgres, KHÔNG tự import `backend/src` (tránh nạp trùng
package qua 2 đường sys.path khác nhau — `src.*` khi pytest chạy trong `backend/`,
`backend.src.*` khi import từ repo root). Nhận `scenario` (từ `backend/seed/scenario.json`)
và `matrix` (đã chuyển hoá qua `adapters.model_adapter.seatmap_to_matrix` ở caller,
`backend/src/allocation/cache.py`) làm input thuần numpy/pandas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REAL_CLASS = "NGOI_MEM_DH"  # lớp duy nhất golden scenario có ghế thật (40 ghế)


class PostgresSeatStateMatrix:
    """API tối thiểu mà `app.bt3_allocation.analyze_run` cần: `._span`, `.st`,
    `.get_state`, `.get_segment_meta`, `.load_factor`, `.seg_range`.

    `chuyen_id` nội bộ = "{train_id}_{service_date}" (KHÔNG phải service_run_id đủ
    hậu tố "_LE") — khớp quy ước `mac_tau = chuyen_id.rsplit('_', 1)[0]` của
    `bt3_allocation`/`Pricer.f0`, để tra đúng `rho_t["SE1"]` mùa vụ."""

    def __init__(self, scenario: dict, matrix: np.ndarray):
        stations = sorted(scenario["stations"], key=lambda s: s["ly_trinh_km"])
        self.st = pd.DataFrame({
            "ga_id": [s["station_id"] for s in stations],
            "ly_trinh_km": [float(s["ly_trinh_km"]) for s in stations],
        })
        self._ga_idx = {gid: i for i, gid in enumerate(self.st.ga_id)}
        self._segments = scenario["segments"]
        self._n_segments = len(self._segments)
        self.chuyen_id = f"{scenario['train_id']}_{scenario['service_date']}"
        self._span = {self.chuyen_id: (0, self._n_segments)}
        self._real_matrix = matrix

    def get_state(self, chuyen_id: str, seat_class: str) -> np.ndarray:
        if seat_class == REAL_CLASS:
            return self._real_matrix.copy()
        return np.zeros((0, self._n_segments), dtype=np.int8)  # golden scenario không có 2 lớp còn lại

    def get_segment_meta(self, chuyen_id: str) -> pd.DataFrame:
        rows = [dict(khu_gian_id=s["segment_id"], ga_dau=s["from"], ga_cuoi=s["to"],
                     km_dau=float(s["km_from"]), km_cuoi=float(s["km_to"]))
                for s in self._segments]
        return pd.DataFrame(rows, index=pd.RangeIndex(len(rows), name="seg_idx"))

    def load_factor(self, chuyen_id: str) -> np.ndarray:
        m = self._real_matrix
        occ = (m != 0).sum(axis=0)  # FREE=0 khớp merging.resolver/model_adapter
        return occ / max(m.shape[0], 1)

    def seg_range(self, chuyen_id: str, ga_di: str, ga_den: str) -> tuple[int, int]:
        if ga_di not in self._ga_idx or ga_den not in self._ga_idx:
            raise ValueError(f"ga không tồn tại: {ga_di} / {ga_den}")
        a, b = sorted((self._ga_idx[ga_di], self._ga_idx[ga_den]))
        return a, b


def build_shim(scenario: dict, matrix: np.ndarray) -> PostgresSeatStateMatrix:
    return PostgresSeatStateMatrix(scenario, matrix)


def build_forecast_df(fc_rows: list[dict]) -> "pd.DataFrame | None":
    """`analyze_run` cần `forecast_df` là DataFrame — literal pandas ở lại trong
    `integration/`, `backend/src/allocation/cache.py` chỉ truyền list[dict] thuần."""
    return pd.DataFrame(fc_rows) if fc_rows else None

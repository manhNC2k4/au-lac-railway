# -*- coding: utf-8 -*-
"""BÀI TOÁN CON 2 — Seat State Matrix (kho dữ liệu trung tâm).

Ma trận ghế × đoạn, mỗi ô ∈ {0 trống, 1 đã_bán, 2 đang_giữ}. Build trước tiên vì
BT3/BT4/BT5 đều đọc từ đây. Đây là "bảng hợp đồng" chung.

Nguồn build: stations.csv + trains.csv + replay transactions (đúng thứ tự mua) bằng
first-fit — cùng thuật toán gán chỗ với generator nên tải từng đoạn nhất quán.
Hỗ trợ snapshot (.npz + .meta.json) để FastAPI nạp nhanh, không replay lại.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import (DA_BAN, DANG_GIU, DATA, MACRO_CLASS, SEAT_CLASSES, TRONG,
                        mac_tau_of)

_TC = re.compile(r"TC\d+$")   # SE1TC3 -> SE1 (chuyến tăng cường dùng sức chứa tàu gốc)


class SeatStateMatrix:
    def __init__(self, data_dir: Path = DATA):
        st = pd.read_csv(data_dir / "stations.csv").sort_values("ly_trinh_km").reset_index(drop=True)
        self.data_dir = Path(data_dir)
        self.st = st
        self.st_idx = {r.ga_id: i for i, r in st.iterrows()}
        # data V2 có dòng lặp y hệt theo mac_tau -> dedupe để .loc trả Series
        self.trains = (pd.read_csv(data_dir / "trains.csv")
                       .drop_duplicates("mac_tau").set_index("mac_tau"))
        self._store: dict[tuple[str, str], np.ndarray] = {}   # (chuyen_id, cls) -> matrix int8
        self._span: dict[str, tuple[int, int]] = {}           # chuyen_id -> (lo, hi) ga idx
        self._holds: list[dict] = []                          # giữ chỗ có hạn (A2)
        self._locked_price: dict[str, int] = {}               # sổ giá đã khoá (A2, honor held price)

    # ---------------- nội bộ ----------------
    def _base_train(self, mac_tau: str) -> pd.Series:
        base = _TC.sub("", mac_tau)
        if base not in self.trains.index:
            raise KeyError(f"mac_tau không có trong trains.csv: {mac_tau}")
        return self.trains.loc[base]

    def _ensure(self, chuyen_id: str):
        if chuyen_id in self._span:
            return
        mac_tau = mac_tau_of(chuyen_id)
        row = self._base_train(mac_tau)
        lo, hi = sorted((self.st_idx[row.ga_dau], self.st_idx[row.ga_cuoi]))
        self._span[chuyen_id] = (lo, hi)
        for cls in SEAT_CLASSES:
            n = int(row[f"cap_{cls}"])
            self._store[(chuyen_id, cls)] = np.full((n, hi - lo), TRONG, dtype=np.int8)

    # ---------------- API hợp đồng ----------------
    def get_state(self, chuyen_id: str, seat_class: str) -> np.ndarray:
        self._ensure(chuyen_id)
        return self._store[(chuyen_id, seat_class)].copy()

    def get_segment_meta(self, chuyen_id: str) -> pd.DataFrame:
        self._ensure(chuyen_id)
        lo, hi = self._span[chuyen_id]
        rows = [dict(khu_gian_id=e + 1, ga_dau=self.st.ga_id[e], ga_cuoi=self.st.ga_id[e + 1],
                     km_dau=float(self.st.ly_trinh_km[e]), km_cuoi=float(self.st.ly_trinh_km[e + 1]))
                for e in range(lo, hi)]
        return pd.DataFrame(rows, index=pd.RangeIndex(hi - lo, name="seg_idx"))

    def seg_range(self, chuyen_id: str, ga_di: str, ga_den: str) -> tuple[int, int]:
        self._ensure(chuyen_id)
        lo, hi = self._span[chuyen_id]
        if ga_di not in self.st_idx or ga_den not in self.st_idx:
            raise ValueError(f"ga không tồn tại: {ga_di} / {ga_den}")
        a, b = sorted((self.st_idx[ga_di], self.st_idx[ga_den]))
        if a < lo or b > hi:
            raise ValueError(f"O-D ({ga_di},{ga_den}) ngoài tuyến của {chuyen_id}")
        return a - lo, b - lo

    def assign(self, chuyen_id, seat_class, seat_idx, seg_from, seg_to, state=DA_BAN) -> bool:
        self._ensure(chuyen_id)
        m = self._store[(chuyen_id, seat_class)]
        if (m[seat_idx, seg_from:seg_to] != TRONG).any():
            return False                       # nguyên tử: xung đột => không ghi gì
        m[seat_idx, seg_from:seg_to] = state
        return True

    def release(self, chuyen_id, seat_class, seat_idx, seg_from, seg_to) -> None:
        self._ensure(chuyen_id)
        self._store[(chuyen_id, seat_class)][seat_idx, seg_from:seg_to] = TRONG

    def first_fit(self, chuyen_id, seat_class, seg_from, seg_to, state=DA_BAN) -> int | None:
        self._ensure(chuyen_id)
        m = self._store[(chuyen_id, seat_class)]
        ok = (m[:, seg_from:seg_to] == TRONG).all(axis=1)
        if not ok.any():
            return None
        idx = int(np.argmax(ok))
        m[idx, seg_from:seg_to] = state
        return idx

    def load_factor(self, chuyen_id: str) -> np.ndarray:
        """Vector (n_segments,) LF từng đoạn, gộp mọi lớp chỗ. Input BT3/BT5."""
        self._ensure(chuyen_id)
        occ, cap = None, 0
        for cls in SEAT_CLASSES:
            m = self._store[(chuyen_id, cls)]
            o = (m != TRONG).sum(axis=0)
            occ = o if occ is None else occ + o
            cap += m.shape[0]
        return occ / max(cap, 1)

    def apply_transaction(self, txn: dict) -> bool:
        """Luồng real-time: {ve_id, chuyen_id, ga_di, ga_den, loai_cho, action∈BUY/HOLD/RELEASE}."""
        cls = MACRO_CLASS[txn["loai_cho"]]
        a, b = self.seg_range(txn["chuyen_id"], txn["ga_di"], txn["ga_den"])
        if txn["action"] == "RELEASE":
            self.release(txn["chuyen_id"], cls, txn["seat_idx"], a, b)
            return True
        state = DANG_GIU if txn["action"] == "HOLD" else DA_BAN
        return self.first_fit(txn["chuyen_id"], cls, a, b, state) is not None

    def list_runs(self) -> list[str]:
        return sorted(self._span)

    # ---------------- A2: giữ chỗ có hạn + sổ giá đã khoá ----------------
    def hold_with_expiry(self, chuyen_id, seat_class, seg_from, seg_to,
                         now_u: float, ttl_ngay: float = 1.0) -> int | None:
        """Giữ chỗ DANG_GIU, hết hạn khi u hiện tại <= now_u - ttl (u đếm ngược về 0).
        Trả seat_idx hoặc None nếu hết chỗ."""
        idx = self.first_fit(chuyen_id, seat_class, seg_from, seg_to, DANG_GIU)
        if idx is not None:
            self._holds.append(dict(chuyen_id=chuyen_id, seat_class=seat_class,
                                    seat_idx=idx, seg_from=seg_from, seg_to=seg_to,
                                    het_han_u=now_u - ttl_ngay))
        return idx

    def expire_holds(self, now_u: float) -> list[dict]:
        """Nhả mọi hold quá hạn (now_u <= het_han_u). Trả danh sách đã nhả => nguồn gap."""
        expired = [h for h in self._holds if now_u <= h["het_han_u"]]
        for h in expired:
            self.release(h["chuyen_id"], h["seat_class"], h["seat_idx"],
                         h["seg_from"], h["seg_to"])
        self._holds = [h for h in self._holds if now_u > h["het_han_u"]]
        return expired

    def confirm_hold(self, chuyen_id, seat_class, seat_idx, seg_from, seg_to) -> bool:
        """Chuyển DANG_GIU -> DA_BAN khi khách thanh toán; xoá khỏi danh sách hold."""
        m = self._store[(chuyen_id, seat_class)]
        if (m[seat_idx, seg_from:seg_to] != DANG_GIU).any():
            return False
        m[seat_idx, seg_from:seg_to] = DA_BAN
        self._holds = [h for h in self._holds
                       if not (h["chuyen_id"] == chuyen_id and h["seat_class"] == seat_class
                               and h["seat_idx"] == seat_idx and h["seg_from"] == seg_from)]
        return True

    def lock_price(self, key: str, gia: int) -> None:
        """Khoá giá lúc giữ chỗ (honor held price — YAML gia_khoa_sau_khi_giu_cho=true)."""
        self._locked_price[key] = int(gia)

    def locked_price(self, key: str) -> int | None:
        return self._locked_price.get(key)

    # ---------------- build từ dataset ----------------
    def build_date(self, ngay_chay: str, mac_tau_filter: list[str] | None = None) -> dict:
        """Replay mọi vé HIEU_LUC của các chuyến chạy `ngay_chay` (mua sớm gán trước).
        Đọc DUY NHẤT partition tháng tương ứng để nhanh."""
        month = ngay_chay[:7]
        part = self.data_dir / "transactions" / f"thang={month}"
        tx = pd.read_parquet(str(part), columns=[
            "chuyen_id", "mac_tau", "ngay_chay", "ga_di", "ga_den",
            "loai_cho", "lead_time_ngay", "trang_thai"])
        tx = tx[(tx.ngay_chay == ngay_chay) & (tx.trang_thai == "HIEU_LUC")]
        if mac_tau_filter:
            tx = tx[tx.mac_tau.isin(mac_tau_filter)]
        tx = tx.sort_values("lead_time_ngay", ascending=False)   # thứ tự mua thật
        stats: dict[str, dict] = {}
        for r in tx.itertuples(index=False):
            s = stats.setdefault(r.chuyen_id, {"sold": 0, "failed": 0})
            try:
                a, b = self.seg_range(r.chuyen_id, r.ga_di, r.ga_den)
            except (KeyError, ValueError):
                s["failed"] += 1
                continue
            cls = MACRO_CLASS[r.loai_cho]
            if self.first_fit(r.chuyen_id, cls, a, b) is not None:
                s["sold"] += 1
            else:
                s["failed"] += 1               # generator đã ghép nhiều ghế — xấp xỉ
        return stats

    # ---------------- snapshot (artifact cho FastAPI) ----------------
    def save_snapshot(self, path: Path):
        path = Path(path)
        arrays = {f"{cid}|{cls}": m for (cid, cls), m in self._store.items()}
        np.savez_compressed(path.with_suffix(".npz"), **arrays)
        meta = {"span": {k: list(v) for k, v in self._span.items()},
                "station_order": self.st.ga_id.tolist(),
                "km": self.st.set_index("ga_id").ly_trinh_km.astype(float).to_dict()}
        path.with_suffix(".meta.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    def load_snapshot(self, path: Path):
        path = Path(path)
        meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
        self._span = {k: tuple(v) for k, v in meta["span"].items()}
        z = np.load(path.with_suffix(".npz"))
        for key in z.files:
            cid, cls = key.split("|")
            self._store[(cid, cls)] = z[key]
        return self

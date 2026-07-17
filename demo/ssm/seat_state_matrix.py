# -*- coding: utf-8 -*-
"""Seat State Matrix (bài toán con 2) — kho dữ liệu trung tâm, implement ssm_contract.

Nguồn build: generated_data/data/{stations,trains}.csv + transactions (replay).
Ghi chú replay: dataset chỉ lưu ghế ĐẦU của vé ghép nhiều ghế (0,06% vé), nên replay
gán lại first-fit theo đúng thứ tự mua (lead_time giảm dần) — cùng thuật toán với
generator => ma trận nhất quán về tải từng đoạn (bất biến quan trọng), có thể khác
số ghế cụ thể ở nhóm vé ghép.

Chạy demo nhanh:  python demo/ssm/seat_state_matrix.py --date 2026-05-20 --trains SE1,SE7
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ssm_contract import (DA_BAN, DANG_GIU, MACRO_CLASS, SEAT_CLASSES, TRONG)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = Path(__file__).resolve().parents[2] / "generated_data" / "data"
_TC = re.compile(r"TC\d+$")   # SE1TC3 -> SE1 (chuyến tăng cường dùng sức chứa tàu gốc)


class SeatStateMatrix:
    """Kho trạng thái ghế × đoạn cho nhiều chuyến. API theo ssm_contract."""

    def __init__(self, data_dir: Path = DATA):
        st = pd.read_csv(data_dir / "stations.csv").sort_values("ly_trinh_km").reset_index(drop=True)
        self.st_idx = {r.ga_id: i for i, r in st.iterrows()}
        self.st = st
        tr = pd.read_csv(data_dir / "trains.csv").set_index("mac_tau")
        self.trains = tr
        self._store: dict[tuple[str, str], np.ndarray] = {}   # (train_id, cls) -> matrix
        self._span: dict[str, tuple[int, int]] = {}           # train_id -> (lo, hi) ga idx

    # ---------- nội bộ ----------
    def _base_train(self, mac_tau: str) -> pd.Series:
        base = _TC.sub("", mac_tau)
        if base not in self.trains.index:
            raise KeyError(f"mac_tau không có trong trains.csv: {mac_tau}")
        return self.trains.loc[base]

    def _ensure(self, train_id: str):
        if train_id in self._span:
            return
        mac_tau = train_id.rsplit("_", 1)[0]
        row = self._base_train(mac_tau)
        lo, hi = sorted((self.st_idx[row.ga_dau], self.st_idx[row.ga_cuoi]))
        self._span[train_id] = (lo, hi)
        n_seg = hi - lo
        for cls in SEAT_CLASSES:
            n_seats = int(row[f"cap_{cls}"])
            self._store[(train_id, cls)] = np.full((n_seats, n_seg), TRONG, dtype=np.int8)

    # ---------- API hợp đồng ----------
    def get_state(self, train_id: str, seat_class: str) -> np.ndarray:
        self._ensure(train_id)
        return self._store[(train_id, seat_class)].copy()

    def get_seat_meta(self, train_id: str, seat_class: str) -> pd.DataFrame:
        self._ensure(train_id)
        n = self._store[(train_id, seat_class)].shape[0]
        return pd.DataFrame({"loai_cho": [seat_class] * n},
                            index=pd.RangeIndex(n, name="seat_idx"))

    def get_segment_meta(self, train_id: str) -> pd.DataFrame:
        self._ensure(train_id)
        lo, hi = self._span[train_id]
        rows = []
        for e in range(lo, hi):
            rows.append(dict(khu_gian_id=e + 1, ga_dau=self.st.ga_id[e], ga_cuoi=self.st.ga_id[e + 1],
                             km_dau=self.st.ly_trinh_km[e], km_cuoi=self.st.ly_trinh_km[e + 1]))
        return pd.DataFrame(rows, index=pd.RangeIndex(hi - lo, name="seg_idx"))

    def seg_range(self, train_id: str, ga_di: str, ga_den: str) -> tuple[int, int]:
        self._ensure(train_id)
        lo, hi = self._span[train_id]
        a, b = sorted((self.st_idx[ga_di], self.st_idx[ga_den]))
        if a < lo or b > hi:
            raise ValueError(f"O-D ({ga_di},{ga_den}) ngoài tuyến của {train_id}")
        return a - lo, b - lo

    def assign(self, train_id, seat_class, seat_idx, seg_from, seg_to, state=DA_BAN) -> bool:
        self._ensure(train_id)
        m = self._store[(train_id, seat_class)]
        if (m[seat_idx, seg_from:seg_to] != TRONG).any():
            return False                       # nguyên tử: có xung đột => không ghi gì
        m[seat_idx, seg_from:seg_to] = state
        return True

    def release(self, train_id, seat_class, seat_idx, seg_from, seg_to) -> None:
        self._ensure(train_id)
        self._store[(train_id, seat_class)][seat_idx, seg_from:seg_to] = TRONG

    def load_factor(self, train_id: str) -> np.ndarray:
        self._ensure(train_id)
        occ, cap = None, 0
        for cls in SEAT_CLASSES:
            m = self._store[(train_id, cls)]
            o = (m != TRONG).sum(axis=0)
            occ = o if occ is None else occ + o
            cap += m.shape[0]
        return occ / max(cap, 1)

    # ---------- tiện ích trên hợp đồng ----------
    def first_fit(self, train_id, seat_class, seg_from, seg_to, state=DA_BAN) -> int | None:
        """Ghế đầu tiên trống suốt dải; gán và trả seat_idx, None nếu hết."""
        m = self._store[(train_id, seat_class)]
        ok = (m[:, seg_from:seg_to] == TRONG).all(axis=1)
        if not ok.any():
            return None
        idx = int(np.argmax(ok))
        m[idx, seg_from:seg_to] = state
        return idx

    def apply_transaction(self, txn: dict) -> bool:
        """Luồng real-time theo TXN_SCHEMA: BUY/HOLD gán first-fit, RELEASE trả dải."""
        cls = MACRO_CLASS[txn["loai_cho"]]
        a, b = self.seg_range(txn["train_id"], txn["ga_di"], txn["ga_den"])
        if txn["action"] == "RELEASE":
            self.release(txn["train_id"], cls, txn["seat_idx"], a, b)
            return True
        state = DANG_GIU if txn["action"] == "HOLD" else DA_BAN
        return self.first_fit(txn["train_id"], cls, a, b, state) is not None

    # ---------- replay từ dataset ----------
    def replay_date(self, date: str, mac_tau_filter: list[str] | None = None) -> dict:
        """Replay mọi vé HIEU_LUC của các chuyến chạy `date` (mua sớm gán trước).
        Trả thống kê {chuyen_id: {sold, failed}}; failed>0 = vé ghép nhiều ghế xấp xỉ."""
        tx = pd.read_parquet(str(DATA / "transactions"),
                             columns=["chuyen_id", "mac_tau", "ngay_chay", "ga_di", "ga_den",
                                      "loai_cho", "lead_time_ngay", "trang_thai"])
        tx = tx[(tx.ngay_chay == date) & (tx.trang_thai == "HIEU_LUC")]
        if mac_tau_filter:
            tx = tx[tx.mac_tau.isin(mac_tau_filter)]
        tx = tx.sort_values("lead_time_ngay", ascending=False)   # thứ tự mua thật
        stats: dict[str, dict] = {}
        for r in tx.itertuples(index=False):
            s = stats.setdefault(r.chuyen_id, {"sold": 0, "failed": 0})
            cls = MACRO_CLASS[r.loai_cho]
            try:
                a, b = self.seg_range(r.chuyen_id, r.ga_di, r.ga_den)
            except (KeyError, ValueError):
                s["failed"] += 1
                continue
            if self.first_fit(r.chuyen_id, cls, a, b) is not None:
                s["sold"] += 1
            else:
                s["failed"] += 1               # generator đã ghép nhiều ghế — xấp xỉ
        return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-05-20")
    ap.add_argument("--trains", default="SE1,SE7")
    args = ap.parse_args()
    ssm = SeatStateMatrix()
    stats = ssm.replay_date(args.date, args.trains.split(","))
    for rid, s in stats.items():
        lf = ssm.load_factor(rid)
        print(f"{rid}: sold={s['sold']} failed={s['failed']} | LF min={lf.min():.2f} "
              f"max={lf.max():.2f} mean={lf.mean():.2f}")


if __name__ == "__main__":
    main()

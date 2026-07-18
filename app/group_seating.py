# -*- coding: utf-8 -*-
"""C4 / YC5 — Group seating: xếp nhóm cùng toa/khoang, ghế liền, tối thiểu tách.

Solver: OR-Tools CP-SAT (doc 03 §11); fallback greedy nếu thiếu lib.
Mô hình toa/khoang: seat_idx // CAR_SIZE = toa; trong toa, // COMPARTMENT_SIZE = khoang.
Mục tiêu (ưu tiên giảm dần): (1) ít toa nhất, (2) ít khoang nhất, (3) dải ghế hẹp nhất.
Thuần đề xuất — không mutate kho.
"""
import numpy as np

from app.config import CAR_SIZE, COMPARTMENT_SIZE, MACRO_CLASS, TRONG
from app.contracts import GroupPlan, ProposalLog, SeatSegment

try:
    from ortools.sat.python import cp_model
    HAS_CPSAT = True
except ImportError:
    HAS_CPSAT = False


def _free_seats(ssm, chuyen_id, cls, a, b):
    m = ssm.get_state(chuyen_id, cls)
    return np.flatnonzero((m[:, a:b] == TRONG).all(axis=1))


def _plan_from_seats(ssm, chuyen_id, cls, seats, a, b, solver_name):
    car_sz, comp_sz = CAR_SIZE[cls], COMPARTMENT_SIZE[cls]
    cars = sorted({int(s) // car_sz for s in seats})
    comps = {(int(s) // car_sz, (int(s) % car_sz) // comp_sz) for s in seats}
    seats = sorted(int(s) for s in seats)
    # điểm liền kề: cặp ghế cạnh nhau / tổng cặp
    adj = sum(1 for i in range(len(seats) - 1) if seats[i + 1] - seats[i] == 1)
    lien_ke = adj / max(len(seats) - 1, 1)
    lo, _ = ssm._span[chuyen_id]
    segs = [SeatSegment(seat_idx=s, seg_from=a, seg_to=b,
                        ga_di=ssm.st.ga_id[lo + a], ga_den=ssm.st.ga_id[lo + b])
            for s in seats]
    return GroupPlan(kha_thi=True, seat_class=cls, assignments=segs, toa=cars,
                     diem_lien_ke=round(lien_ke, 3), so_lan_tach=len(comps) - 1,
                     ghi_chu=f"{solver_name}: {len(seats)} khách / {len(cars)} toa / "
                             f"{len(comps)} khoang, liền kề {lien_ke:.0%}")


def plan_group(ssm, chuyen_id: str, loai_ghe: str, ga_di: str, ga_den: str,
               n_khach: int, time_limit_s: float = 5.0) -> dict:
    cls = MACRO_CLASS.get(loai_ghe, loai_ghe)
    a, b = ssm.seg_range(chuyen_id, ga_di, ga_den)
    free = _free_seats(ssm, chuyen_id, cls, a, b)
    if len(free) < n_khach:
        out = GroupPlan(kha_thi=False, seat_class=cls, assignments=[], toa=[],
                        diem_lien_ke=0.0, so_lan_tach=0,
                        ghi_chu=f"chỉ còn {len(free)} ghế trống suốt, cần {n_khach}")
        return {"plan": out.to_dict(), "_log": ProposalLog(
            loai="GROUP", input={"chuyen_id": chuyen_id, "n": n_khach},
            output={"kha_thi": False}, explain=out.ghi_chu).to_dict()}

    car_sz, comp_sz = CAR_SIZE[cls], COMPARTMENT_SIZE[cls]
    if HAS_CPSAT:
        plan = _solve_cpsat(free, n_khach, car_sz, comp_sz, time_limit_s)
        solver = "CP-SAT"
    else:
        plan = _solve_greedy(free, n_khach, car_sz, comp_sz)
        solver = "greedy"
    gp = _plan_from_seats(ssm, chuyen_id, cls, plan, a, b, solver)
    return {"plan": gp.to_dict(), "_log": ProposalLog(
        loai="GROUP", input={"chuyen_id": chuyen_id, "od": [ga_di, ga_den],
                             "cls": cls, "n": n_khach},
        output={"kha_thi": True, "toa": gp.toa, "so_lan_tach": gp.so_lan_tach},
        explain=gp.ghi_chu).to_dict()}


def _solve_cpsat(free, n, car_sz, comp_sz, tl):
    """CP-SAT: chọn n ghế, tối thiểu (số toa, số khoang, bề rộng dải ghế)."""
    free = [int(s) for s in free]
    cars = sorted({s // car_sz for s in free})
    comps = sorted({(s // car_sz, (s % car_sz) // comp_sz) for s in free})
    mdl = cp_model.CpModel()
    x = {s: mdl.NewBoolVar(f"x{s}") for s in free}
    uc = {c: mdl.NewBoolVar(f"c{c}") for c in cars}
    uk = {k: mdl.NewBoolVar(f"k{k}") for k in comps}
    mdl.Add(sum(x.values()) == n)
    for s in free:
        mdl.AddImplication(x[s], uc[s // car_sz])
        mdl.AddImplication(x[s], uk[(s // car_sz, (s % car_sz) // comp_sz)])
    lo_v = mdl.NewIntVar(min(free), max(free), "lo")
    hi_v = mdl.NewIntVar(min(free), max(free), "hi")
    for s in free:
        mdl.Add(lo_v <= s).OnlyEnforceIf(x[s])
        mdl.Add(hi_v >= s).OnlyEnforceIf(x[s])
    span = mdl.NewIntVar(0, max(free) - min(free), "span")
    mdl.Add(span == hi_v - lo_v)
    # trọng số từ vựng: toa >> khoang >> span
    mdl.Minimize(10000 * sum(uc.values()) + 100 * sum(uk.values()) + span)
    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = tl
    sv.parameters.random_seed = 20260717
    sv.parameters.num_search_workers = 1          # tất định
    if sv.Solve(mdl) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [s for s in free if sv.Value(x[s])]
    return _solve_greedy(np.array(free), n, car_sz, comp_sz)


def _solve_greedy(free, n, car_sz, comp_sz):
    """Fallback: ưu tiên khoang chứa đủ, rồi toa chứa đủ dải liền, rồi lấp dần."""
    free = sorted(int(s) for s in free)
    by_comp: dict = {}
    for s in free:
        by_comp.setdefault((s // car_sz, (s % car_sz) // comp_sz), []).append(s)
    # 1 khoang đủ chỗ
    for k, seats in by_comp.items():
        if len(seats) >= n:
            return seats[:n]
    # 1 toa đủ chỗ, chọn cửa sổ hẹp nhất
    by_car: dict = {}
    for s in free:
        by_car.setdefault(s // car_sz, []).append(s)
    best = None
    for c, seats in by_car.items():
        if len(seats) >= n:
            for i in range(len(seats) - n + 1):
                w = seats[i + n - 1] - seats[i]
                if best is None or w < best[0]:
                    best = (w, seats[i:i + n])
    if best:
        return best[1]
    # rải nhiều toa: lấy tuần tự
    return free[:n]

# -*- coding: utf-8 -*-
"""E — Contract & invariant tests cho lớp model + thuật toán.

Chạy: python -m pytest tests/ -q   (hoặc python tests/test_invariants.py)
Nhóm: guardrail giá, thứ tự CSXH, cap biến động, held price, loại trừ ưu tiên,
      dwell-time, tính tất định, nguyên tử SSM.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.bt2_ssm import SeatStateMatrix
from app.bt4_merge import find_options
from app.bt5_pricing import VOLATILITY_CAP, Pricer
from app.contracts import PassengerProfile
from app.config import DA_BAN, TRONG, make_chuyen_id

DATE, TRAIN = "2026-02-14", "SE1"
_ssm_cache = {}


def get_ssm():
    if "x" not in _ssm_cache:
        s = SeatStateMatrix()
        s.build_date(DATE, [TRAIN])
        _ssm_cache["x"] = s
    return _ssm_cache["x"]


def lfr(pr, ssm):
    from app.bt3_allocation import load_factor_route
    return load_factor_route(ssm, make_chuyen_id(TRAIN, DATE), "HNO", "DNA")


CTX = {"che_do_gia": "LUAT", "tau_tet": -3, "dot_ban_ve": "TET_2026", "dow": 5, "la_le": True}


def test_guardrail_san_tran():
    pr = Pricer.load()
    q = pr.quote(TRAIN, "HNO", "DNA", "NGOI_MEM_DH", CTX, lfr(pr, get_ssm()))
    f0 = q.gia_goc_F0
    # giá NIÊM YẾT (trước CSXH) luôn trong [0.55, 1.6]×F0
    ny = q.gia_de_xuat  # csxh=0 => niêm yết = đề xuất
    assert 0.55 * f0 - 1 <= ny <= 1.6 * f0 + 1, f"vi phạm sàn/trần: {ny} vs F0={f0}"


def test_csxh_ap_sau_cung():
    pr = Pricer.load()
    route = lfr(pr, get_ssm())
    q0 = pr.quote(TRAIN, "HNO", "DNA", "NGOI_MEM_DH", CTX, route)
    q9 = pr.quote(TRAIN, "HNO", "DNA", "NGOI_MEM_DH", CTX, route, muc_giam_csxh=0.9)
    # CSXH áp trên giá niêm yết cuối (sau mọi điều chỉnh động) — đúng tỷ lệ 10%
    assert abs(q9.gia_de_xuat - q0.gia_de_xuat * 0.1) <= 1
    assert "CSXH" in q9.rule_ids
    # được phép < sàn (quyền lợi hợp pháp)
    assert q9.gia_de_xuat < 0.55 * q9.gia_goc_F0


def test_volatility_cap():
    pr = Pricer.load()
    prev = 600_000
    q = pr.quote(TRAIN, "HNO", "DNA", "NGOI_MEM_DH", CTX, lfr(pr, get_ssm()), gia_truoc=prev)
    assert q.gia_de_xuat <= prev * (1 + VOLATILITY_CAP) + 1
    assert q.gia_de_xuat >= prev * (1 - VOLATILITY_CAP) - 1


def test_held_price_bat_kha_xam_pham():
    pr = Pricer.load()
    q = pr.quote(TRAIN, "HNO", "DNA", "NGOI_MEM_DH", CTX, lfr(pr, get_ssm()),
                 gia_da_khoa=650_000)
    assert q.gia_de_xuat == 650_000 and q.held and "HELD_PRICE" in q.rule_ids


def test_gia_tat_dinh():
    """Cùng input => cùng giá (không phân biệt theo số lần gọi)."""
    pr = Pricer.load()
    route = lfr(pr, get_ssm())
    a = pr.quote(TRAIN, "HNO", "DNA", "NGOI_MEM_DH", CTX, route).gia_de_xuat
    b = pr.quote(TRAIN, "HNO", "DNA", "NGOI_MEM_DH", CTX, route).gia_de_xuat
    assert a == b


def test_uu_tien_khong_ghep():
    ssm = get_ssm()
    for prof in (PassengerProfile(cao_tuoi=True), PassengerProfile(khuyet_tat=True),
                 PassengerProfile(tre_di_mot_minh=True), PassengerProfile(can_ho_tro=True)):
        r = find_options(ssm, make_chuyen_id(TRAIN, DATE), "NGOI_MEM_DH", "HNO", "DNA", prof)
        assert not any(o["loai"] == "ghep_nhieu" for o in r["phuong_an"])


def test_ghep_co_disclosure_va_dwell():
    r = find_options(get_ssm(), make_chuyen_id(TRAIN, DATE), "NGOI_MEM_DH", "HNO", "DNA",
                     PassengerProfile())
    merges = [o for o in r["phuong_an"] if o["loai"] == "ghep_nhieu"]
    for o in merges:
        assert o["can_khach_chap_nhan"] is True
        assert o["dwell_du"] is True and o["cung_hang_cho"] is True
        assert o["so_lan_doi_cho"] == len(o["ga_doi"]) == len(o["ghe_theo_doan"]) - 1


def test_ssm_assign_nguyen_tu():
    ssm = SeatStateMatrix()
    ssm._span["T_x"] = (0, 5)
    import numpy as np
    for c in ("NGOI_MEM_DH", "NAM_K6", "NAM_K4"):
        ssm._store[("T_x", c)] = np.full((2, 5), TRONG, dtype=np.int8)
    assert ssm.assign("T_x", "NAM_K6", 0, 0, 3, DA_BAN)
    # chồng lấn => từ chối và KHÔNG ghi gì
    assert not ssm.assign("T_x", "NAM_K6", 0, 2, 5, DA_BAN)
    assert (ssm.get_state("T_x", "NAM_K6")[0, 3:5] == TRONG).all()


def test_hold_expiry_sinh_gap():
    ssm = SeatStateMatrix()
    ssm._span["T_y"] = (0, 5)
    import numpy as np
    for c in ("NGOI_MEM_DH", "NAM_K6", "NAM_K4"):
        ssm._store[("T_y", c)] = np.full((2, 5), TRONG, dtype=np.int8)
    idx = ssm.hold_with_expiry("T_y", "NAM_K4", 0, 3, now_u=10, ttl_ngay=1)
    assert idx is not None
    assert ssm.expire_holds(9.5) == []          # chưa hết hạn (9.5 > 9)
    exp = ssm.expire_holds(8.9)                  # quá hạn
    assert len(exp) == 1
    assert (ssm.get_state("T_y", "NAM_K4")[idx, 0:3] == TRONG).all()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print(f"✅ {f.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests PASS")

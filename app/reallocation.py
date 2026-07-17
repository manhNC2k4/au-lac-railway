# -*- coding: utf-8 -*-
"""C2 — Seat release & reallocation động (YC3 + YC6).

Khi thực tế bán lệch dự báo (tín hiệu divergence từ DemandModel.B3):
  1. expire_holds : nhả mọi giữ chỗ quá hạn (nguồn gap mới cho BT4)
  2. divergence<θ : cầu dài THẤP hơn dự báo => hạ protection chặng dài,
                    mở booking limit chặng ngắn (re-solve DLP với cầu cập nhật)
  3. divergence>θ : cầu CAO hơn dự báo => siết chặng ngắn thêm
Output: danh sách ĐỀ XUẤT (không tự áp) + ProposalLog để backend duyệt/rollback.
"""
import pandas as pd

from app.bt3_allocation import analyze_run
from app.contracts import ProposalLog

DIV_THRESHOLD = 0.15      # |lệch| >= 15% mới đề xuất tái phân bổ


def propose_reallocation(ssm, pricer, demand_model, chuyen_id: str,
                         rows_by_band: dict, sold_by_band: dict, u: float,
                         old_quota: list[dict] | None = None) -> dict:
    """rows_by_band: {band: feature-row đại diện} | sold_by_band: {band: vé đã bán}.

    Trả: {holds_da_nha, divergence, de_xuat[], quota_moi} — thuần đề xuất.
    """
    # 1) nhả hold quá hạn
    expired = ssm.expire_holds(u)

    # 2) đo divergence từng băng
    divs = {}
    for band, row in rows_by_band.items():
        d = demand_model.divergence(row, sold_by_band.get(band, 0), u)
        divs[band] = d

    # 3) dự báo còn lại đã cập nhật -> re-solve DLP
    fc_rows = []
    for band, row in rows_by_band.items():
        upd = demand_model.update(row, sold_by_band.get(band, 0), u)
        fc_rows.append(dict(origin=row["ga_di"], dest=row["ga_den"],
                            train_id=row["mac_tau"], seat_class=row["seat_class"],
                            remaining_demand=upd["remaining_demand"]))
    fc = pd.DataFrame(fc_rows) if fc_rows else None
    new_alloc = analyze_run(ssm, pricer, chuyen_id, fc)

    # 4) diff quota cũ/mới -> đề xuất hành động
    proposals = []
    if old_quota:
        old_map = {(q["khu_gian_id"], q["loai_hanh_trinh"], q["seat_class"]): q["booking_limit"]
                   for q in old_quota}
        for q in new_alloc["quota"]:
            key = (q["khu_gian_id"], q["loai_hanh_trinh"], q["seat_class"])
            old = old_map.get(key)
            if old is not None and old != q["booking_limit"]:
                act = "MO_THEM" if q["booking_limit"] > old else "SIET_LAI"
                proposals.append(dict(khu_gian_id=q["khu_gian_id"],
                                      loai_hanh_trinh=q["loai_hanh_trinh"],
                                      seat_class=q["seat_class"], action=act,
                                      limit_cu=old, limit_moi=q["booking_limit"]))
    big_div = {b: d for b, d in divs.items() if abs(d["divergence"]) >= DIV_THRESHOLD}
    explain = (f"nhả {len(expired)} hold quá hạn; lệch dự báo: "
               + ", ".join(f"{b}={d['divergence']:+.0%}" for b, d in divs.items())
               + f"; {len(proposals)} thay đổi limit đề xuất")
    return {
        "chuyen_id": chuyen_id, "u": u,
        "holds_da_nha": expired,
        "divergence": {b: d for b, d in divs.items()},
        "canh_bao_lech": list(big_div),
        "de_xuat": proposals,
        "quota_moi": new_alloc["quota"],
        "bid_price_moi": new_alloc["bid_price_theo_lop"],
        "_log": ProposalLog(loai="RELEASE", input={"chuyen_id": chuyen_id, "u": u},
                            output={"n_expired": len(expired), "n_proposals": len(proposals)},
                            explain=explain).to_dict(),
    }

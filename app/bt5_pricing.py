# -*- coding: utf-8 -*-
"""C6 / BÀI TOÁN CON 5 — Dynamic Pricing tối ưu doanh thu (rule engine + bid price).

Input : LF + bid price hành trình (BT3), phương án ghế (BT4), tham số chính sách,
        BookingRequest (có giá đã khoá / giá lần trước / hồ sơ CSXH).
Output: Quote (contracts) — giá qua guardrail + audit breakdown + giải thích.

Thứ tự toán tử (bất biến pháp lý & chính sách):
  F0 -> mùa vụ -> ĐỘNG (max(bid-price floor, LF surcharge) hoặc giảm AI/off-peak)
     -> cap biến động ±5%/lần -> clip sàn/trần trên F0   = GIÁ NIÊM YẾT
  -> giảm CSXH SAU CÙNG (max một mức, không cộng dồn)     = GIÁ CUỐI
  Giá đã khoá (held) => trả nguyên giá khoá, bỏ qua mọi điều chỉnh.
  KHÔNG dùng dữ liệu cá nhân / số lần tìm kiếm để phân biệt giá — giá chỉ phụ
  thuộc trạng thái tồn kho + lịch, tất định.
"""
import json
from pathlib import Path

from app.config import ARTIFACTS, DEFAULT_POLICY
from app.contracts import ProposalLog, Quote

# cap biến động mỗi lần điều chỉnh (YAML san_tran.bien_do_thay_doi_toi_da_moi_lan)
VOLATILITY_CAP = 0.05
# Bật/tắt sàn giá mùa vụ cho MỌI đợt phụ thu (Tết luôn bật) — xem _price_elastic
import os as _os
SEASONAL_FLOOR = _os.environ.get("AULAC_SEASONAL_FLOOR", "0") == "1"
# off-peak: thứ 3/4 (dow 1,2) ngoài lễ/Tết được giảm để hút khách thấp điểm
OFFPEAK_DOW = {1, 2}
OFFPEAK_DISC = 0.05


class Pricer:
    def __init__(self, params: dict, elasticity=None):
        self.p = params
        self.km = params["km"]
        self.varsigma = params["varsigma"]
        self.rho_t = params["rho_t"]
        self.theta = params["theta"]
        self.kappa0 = params["kappa0"]
        self.elast = elasticity        # None => dùng luật heuristic; có => tối ưu cầu

    @classmethod
    def load(cls, path: Path = ARTIFACTS / "bt5_pricing_params.json",
             use_elasticity: bool = True) -> "Pricer":
        params = json.loads(Path(path).read_text(encoding="utf-8"))
        elast = None
        if use_elasticity:
            from app.elasticity import Elasticity
            elast = Elasticity.load()
        return cls(params, elast)

    def f0(self, mac_tau: str, ga_di: str, ga_den: str, tier: str) -> int:
        d_km = abs(self.km[ga_den] - self.km[ga_di])
        rho = self.rho_t.get(mac_tau, 1.0)
        return int(round(rho * self.varsigma[tier] * self.kappa0 * d_km ** self.theta))

    def _delta_mua(self, ctx: dict) -> tuple[float, str]:
        tau = ctx.get("tau_tet")
        if tau is not None and abs(tau) <= 21:
            return self.p["delta_mua"]["tet"], "MUA_VU:TET"
        if ctx.get("dot_ban_ve") == "HE_2026":
            return self.p["delta_mua"]["he"], "MUA_VU:HE"
        return 0.0, ""

    def _ai_cap(self, ga_di: str, ga_den: str) -> float:
        t = self.p["ai"]["tran_theo_tuyen"]
        d_km = abs(self.km[ga_den] - self.km[ga_di])
        if {ga_di, ga_den} == {"HUE", "DNA"}:
            return t["HUE_DANANG"]
        if d_km < 300:
            return t["THONG_NHAT_CHANG_NGAN"]
        return t.get("SG_DANANG", 0.25)

    # ------------------------------------------------------------------
    def quote(self, mac_tau: str, ga_di: str, ga_den: str, tier: str,
              ctx: dict, lf_route: dict, policy: dict | None = None,
              gia_da_khoa: int | None = None, gia_truoc: int | None = None,
              muc_giam_csxh: float = 0.0) -> Quote:
        """lf_route = {'segments':[{khu_gian_id,ga_dau,ga_cuoi,lf,bid_price}], 'bid_price_route':int}."""
        pol = {**DEFAULT_POLICY, **(policy or {})}
        f0 = self.f0(mac_tau, ga_di, ga_den, tier)
        rules, comps = [], []

        # 0) honor held price — giá đã khoá là bất khả xâm phạm
        if gia_da_khoa is not None:
            gia_cuoi = int(round(gia_da_khoa * (1 - muc_giam_csxh)))
            return Quote(gia_de_xuat=gia_cuoi, gia_goc_F0=f0, gia_mua_vu=gia_da_khoa,
                         delta_mua=0.0, delta_dong=0.0, bid_price_route=0,
                         rule_ids=["HELD_PRICE"] + (["CSXH"] if muc_giam_csxh else []),
                         giai_thich=f"giữ nguyên giá đã khoá {gia_da_khoa:,}đ"
                                    + (f", giảm CSXH {muc_giam_csxh:.0%} sau cùng" if muc_giam_csxh else ""),
                         thanh_phan=[{"buoc": "held", "gia": gia_da_khoa}],
                         held=True, csxh_muc=muc_giam_csxh)

        segs = lf_route.get("segments", []) or []
        bp_route = int(lf_route.get("bid_price_route", 0))
        lf_max = max((s["lf"] for s in segs), default=0.0)
        lf_min = min((s["lf"] for s in segs), default=0.0)
        dmua, _ = self._delta_mua(ctx)

        if self.elast is not None:
            price, delta_dyn, explain = self._price_elastic(
                mac_tau, ga_di, ga_den, tier, f0, ctx, pol, segs, bp_route, lf_max, dmua, rules, comps)
            gia_mua_vu = int(round(f0 * (1 + dmua)))
        else:
            price, delta_dyn, explain, gia_mua_vu = self._price_heuristic(
                ga_di, ga_den, f0, ctx, pol, segs, bp_route, lf_max, lf_min, dmua, rules, comps)

        # 3) cap biến động ±5% so với giá báo lần trước
        if gia_truoc is not None and gia_truoc > 0:
            lo_v, hi_v = gia_truoc * (1 - VOLATILITY_CAP), gia_truoc * (1 + VOLATILITY_CAP)
            capped = min(max(price, lo_v), hi_v)
            if abs(capped - price) > 0.5:
                rules.append("VOLATILITY_CAP")
                comps.append({"buoc": "volatility_cap", "gia_truoc": gia_truoc,
                              "truoc_cap": int(price), "sau_cap": int(capped)})
                explain += f" | cap biến động ±{VOLATILITY_CAP:.0%}/lần so với {gia_truoc:,}đ"
                price = capped

        # 4) guardrail sàn/trần trên F0 => GIÁ NIÊM YẾT
        lo, hi = pol["san_ty_le"] * f0, pol["tran_ty_le"] * f0
        clipped = min(max(price, lo), hi)
        if abs(clipped - price) > 0.5:
            rules.append("CLIP")
            comps.append({"buoc": "guardrail", "san": int(lo), "tran": int(hi)})
            explain += f" | chạm guardrail [{int(lo):,};{int(hi):,}]"
        gia_niem_yet = int(round(clipped))

        # 5) CSXH SAU CÙNG — max một mức, không cộng dồn (Điều 40 NĐ 16/2026)
        gia_cuoi = int(round(gia_niem_yet * (1 - muc_giam_csxh)))
        if muc_giam_csxh:
            rules.append("CSXH")
            comps.append({"buoc": "csxh", "muc": muc_giam_csxh,
                          "niem_yet": gia_niem_yet, "cuoi": gia_cuoi})
            explain += f" | giảm CSXH {muc_giam_csxh:.0%} áp SAU CÙNG"

        return Quote(gia_de_xuat=gia_cuoi, gia_goc_F0=f0, gia_mua_vu=int(round(gia_mua_vu)),
                     delta_mua=dmua, delta_dong=round(delta_dyn, 4),
                     bid_price_route=bp_route, rule_ids=rules, giai_thich=explain,
                     thanh_phan=comps, held=False, csxh_muc=muc_giam_csxh)

    # ------------------------------------------------------------------
    def _price_elastic(self, mac_tau, ga_di, ga_den, tier, f0, ctx, pol,
                       segs, bp_route, lf_max, dmua, rules, comps):
        """Tối đa E[đóng góp]=P(mua|r)·(r·F0−bid) trên [sàn, trần_động(LF)]."""
        d_km = abs(self.km[ga_den] - self.km[ga_di])
        is_tet = ctx.get("tau_tet") is not None and abs(ctx["tau_tet"]) <= 21
        u = float(ctx.get("u", 30))
        lf = min(max(lf_max, 0.0), 1.0)
        # dải giá ĐỘNG hẹp quanh F0 (vùng dữ liệu dày, không ngoại suy):
        #   đoạn đầy  -> [F0 , F0·(1+markup)]   (khan hiếm => cho phép tăng)
        #   đoạn trống -> [F0·(1-markdown) , F0] (ế => cho phép giảm hút khách)
        # trần tự co theo LF đã phản ánh thấp điểm (LF thấp => trần gần F0), nên
        # KHÔNG cần cap off-peak riêng (thừa & làm mất doanh thu ngày tải vừa).
        ceil_r = 1.0 + pol["elastic_markup_max"] * lf
        floor_r = 1.0 - pol["elastic_markdown_max"] * (1.0 - lf)
        offpeak = ctx.get("dow") in OFFPEAK_DOW and not ctx.get("la_le") and lf_max < pol["lf_ref"]
        if is_tet or (dmua > 0 and SEASONAL_FLOOR):
            # nền giá + mùa vụ: không bán DƯỚI giá mùa vụ khi mùa vụ đang phụ thu
            # (Tết luôn bật; các đợt khác bật qua AULAC_SEASONAL_FLOOR — A/B cho
            # thấy bán quanh F0 khi FCFS thu F0(1+δ) là mất doanh thu cao điểm)
            ceil_r = max(ceil_r, 1.0 + dmua + pol["elastic_markup_max"] * lf)
            floor_r = max(floor_r, 1.0 + dmua)
        floor_r = min(floor_r, ceil_r)
        opt = self.elast.optimal_price(f0, bp_route, d_km, is_tet, u, floor_r, ceil_r)
        price = float(opt["p"])
        rules.append(f"ELASTIC:r={opt['r']:.2f}")
        if offpeak:
            rules.append("OFF_PEAK")
        explain = (f"giá tối ưu doanh thu r={opt['r']:.2f} "
                   f"(P(mua)={opt['prob_buy']:.0%}, E[DT]={opt['exp_rev']:,.0f}đ); "
                   f"trần động r≤{ceil_r:.2f} theo LF max {lf_max:.0%}; "
                   f"chi phí cơ hội {bp_route:,}đ" + (" ; giảm off-peak" if offpeak else ""))
        comps.append({"buoc": "elastic", "r": round(opt["r"], 3),
                      "prob_buy": opt["prob_buy"], "ceil_r": round(ceil_r, 3),
                      "floor_r": round(floor_r, 3), "lf_max": round(lf_max, 3),
                      "bp_route": bp_route, "exp_rev": int(opt["exp_rev"]), "gia": int(price)})
        return price, round(opt["r"] - 1.0, 4), explain

    def _price_heuristic(self, ga_di, ga_den, f0, ctx, pol, segs, bp_route,
                         lf_max, lf_min, dmua, rules, comps):
        """Luật cũ (fallback khi chưa có elasticity): mùa vụ + delta động theo LF."""
        price = float(f0)
        if dmua:
            price *= 1 + dmua
            rules.append("MUA_VU:TET" if (ctx.get("tau_tet") and abs(ctx["tau_tet"]) <= 21)
                         else "MUA_VU:HE")
        gia_mua_vu = price
        comps.append({"buoc": "mua_vu", "delta": dmua, "gia": int(price)})
        bind = max(segs, key=lambda s: s["lf"]) if segs else None
        slack = min(segs, key=lambda s: s["lf"]) if segs else None
        delta_dyn, explain = 0.0, "giá giữ nguyên (LF trung bình)"
        if bp_route > price:
            delta_dyn = min(bp_route / price - 1.0, pol["delta_max"])
            rules.append(f"BID_PRICE_FLOOR:{delta_dyn:.3f}")
            explain = f"giá +{delta_dyn:.0%} vì chi phí cơ hội {bp_route:,}đ > giá mùa vụ"
        elif lf_max > pol["lf_ref"]:
            delta_dyn = min(pol["k_surcharge"] * (lf_max - pol["lf_ref"]), pol["delta_max"])
            rules.append(f"LF_SURCHARGE:{delta_dyn:.3f}")
            explain = f"giá +{delta_dyn:.0%} vì đoạn {bind['ga_dau']}→{bind['ga_cuoi']} lấp {lf_max:.0%}"
        price *= 1 + delta_dyn
        comps.append({"buoc": "dong", "delta": round(delta_dyn, 4), "gia": int(price)})
        return price, round(delta_dyn, 4), explain, int(round(gia_mua_vu))

    def quote_log(self, q: Quote, req: dict) -> dict:
        return ProposalLog(loai="PRICE", input=req, output=q.to_dict(),
                           explain=q.giai_thich).to_dict()

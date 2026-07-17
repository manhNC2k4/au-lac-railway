# -*- coding: utf-8 -*-
"""C5 / YC7 — Smart waitlist: hàng chờ thông minh, tự khớp khi có ghế nhả.

Priority score (tất định, KHÔNG dùng dữ liệu cá nhân để phân biệt giá):
  score = w_fare·(F0 chuẩn hoá)            — giá trị doanh thu tiềm năng
        + w_urgency·1/(1+u)                — càng sát giờ càng ưu tiên khớp
        + w_scarcity·(bid_price chuẩn hoá) — đoạn khan hiếm khớp trước
        + w_csxh·(cờ CSXH)                 — bảo đảm quyền lợi chính sách xã hội
Khớp: duyệt theo score giảm dần; thử ghế đơn trước (xuyen_suot/gap_khit), chỉ đề
xuất ghép nếu hồ sơ cho phép. Kết quả là ĐỀ XUẤT — backend xác nhận mới gán thật.
"""
from app.bt4_merge import find_options
from app.contracts import BookingRequest, ProposalLog, WaitlistEntry

W = {"fare": 0.4, "urgency": 0.3, "scarcity": 0.2, "csxh": 0.1}
F0_NORM = 1_500_000.0        # chuẩn hoá giá về ~[0,1]
BP_NORM = 150_000.0


class WaitlistManager:
    def __init__(self, pricer):
        self.pricer = pricer
        self.entries: list[WaitlistEntry] = []
        self._next_id = 1

    def add(self, req: BookingRequest, bid_price_route: int = 0) -> WaitlistEntry:
        mac_tau = req.chuyen_id.rsplit("_", 1)[0]
        tier = req.loai_cho if req.loai_cho in self.pricer.varsigma else "NGOI_MEM_DH"
        f0 = self.pricer.f0(mac_tau, req.ga_di, req.ga_den, tier)
        score = (W["fare"] * min(f0 / F0_NORM, 1.0)
                 + W["urgency"] * 1.0 / (1.0 + max(req.u, 0))
                 + W["scarcity"] * min(bid_price_route / BP_NORM, 1.0)
                 + W["csxh"] * (1.0 if req.profile.doi_tuong_csxh != "KHONG" else 0.0))
        e = WaitlistEntry(id=self._next_id, request=req, priority_score=round(score, 4))
        self._next_id += 1
        self.entries.append(e)
        return e

    def pending(self) -> list[WaitlistEntry]:
        return sorted([e for e in self.entries if e.trang_thai == "CHO"],
                      key=lambda e: (-e.priority_score, e.id))

    def match(self, ssm, max_matches: int = 50) -> dict:
        """Khớp hàng chờ với chỗ trống hiện tại (gọi sau mỗi đợt nhả ghế/refund)."""
        matched, still = [], 0
        for e in self.pending()[:max_matches * 4]:
            r = e.request
            try:
                opts = find_options(ssm, r.chuyen_id, r.loai_cho, r.ga_di, r.ga_den, r.profile)
            except (KeyError, ValueError):
                e.trang_thai = "HUY"
                continue
            if opts["kha_thi"]:
                e.trang_thai = "KHOP"
                matched.append({"entry_id": e.id, "score": e.priority_score,
                                "od": [r.ga_di, r.ga_den],
                                "phuong_an": opts["phuong_an"][0]})
                if len(matched) >= max_matches:
                    break
            else:
                still += 1
        explain = f"khớp {len(matched)} yêu cầu hàng chờ, còn {still} chưa khớp"
        return {"matched": matched, "con_cho": still,
                "_log": ProposalLog(loai="WAITLIST",
                                    input={"n_pending": len(self.pending()) + len(matched)},
                                    output={"n_matched": len(matched)},
                                    explain=explain).to_dict()}

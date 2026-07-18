# -*- coding: utf-8 -*-
"""A1 — BẢNG HỢP ĐỒNG chung (dataclasses) giữa 5+ module & Backend.

Đây là "đường may" để Backend ghép vào: mọi module nhận/trả các cấu trúc ở đây,
không tự định nghĩa format riêng. Dùng dataclass stdlib (Backend có thể bọc pydantic).
Mọi struct có .to_dict() để serialize JSON/audit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def _clean(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


# Enum CSXH KHỚP DEV (backend/seed/pricing_policy.json). Là nguồn duy nhất cho tên đối
# tượng + mức giảm — mọi module (waitlist/pricing/merge) dùng chung, tránh lệch với dev.
CSXH_DEV_MUC_GIAM = {
    "NGUOI_CAO_TUOI": 0.15,
    "NGUOI_KHUYET_TAT": 0.25,
    "TRE_EM": 0.10,
    "NGUOI_CO_CONG": 0.30,
    "KHONG": 0.0,
}


# ---------------- Hồ sơ khách & yêu cầu ----------------
@dataclass
class PassengerProfile:
    cao_tuoi: bool = False
    khuyet_tat: bool = False
    tre_di_mot_minh: bool = False
    can_ho_tro: bool = False
    doi_tuong_csxh: str = "KHONG"       # KHỚP DEV: NGUOI_CAO_TUOI/NGUOI_KHUYET_TAT/TRE_EM/NGUOI_CO_CONG
    muc_giam_csxh: float = 0.0          # 0..1, quyền lợi giảm giá (áp SAU CÙNG)

    @property
    def thuoc_nhom_uu_tien(self) -> bool:
        """Nhóm được LOẠI TRỪ đổi chỗ (YC4) — ánh xạ với PassengerSafetyContext của dev."""
        return self.cao_tuoi or self.khuyet_tat or self.tre_di_mot_minh or self.can_ho_tro

    def csxh_dev(self) -> tuple[str, float]:
        """(doi_tuong, muc_giam) theo enum DEV, suy từ cờ an toàn nếu chưa set tường minh."""
        if self.doi_tuong_csxh != "KHONG":
            return self.doi_tuong_csxh, CSXH_DEV_MUC_GIAM.get(self.doi_tuong_csxh, self.muc_giam_csxh)
        if self.cao_tuoi:
            return "NGUOI_CAO_TUOI", CSXH_DEV_MUC_GIAM["NGUOI_CAO_TUOI"]
        if self.khuyet_tat:
            return "NGUOI_KHUYET_TAT", CSXH_DEV_MUC_GIAM["NGUOI_KHUYET_TAT"]
        return "KHONG", 0.0

    def to_dict(self):
        return {**asdict(self), "thuoc_nhom_uu_tien": self.thuoc_nhom_uu_tien}


@dataclass
class BookingRequest:
    chuyen_id: str
    ga_di: str
    ga_den: str
    loai_cho: str                       # tier hoặc macro class
    ngay_chay: str
    u: float = 14.0                     # lead time (ngày trước chạy)
    so_khach: int = 1
    profile: PassengerProfile = field(default_factory=PassengerProfile)
    gia_da_khoa: int | None = None      # giá đã khoá lúc giữ chỗ (nếu có)
    gia_truoc: int | None = None        # giá báo lần trước (để cap biến động)

    def to_dict(self):
        d = asdict(self); d["profile"] = self.profile.to_dict(); return d


# ---------------- BT2/BT4: ghế theo đoạn ----------------
@dataclass
class SeatSegment:
    seat_idx: int
    seg_from: int
    seg_to: int
    ga_di: str
    ga_den: str

    def to_dict(self):
        return asdict(self)


@dataclass
class SeatOption:
    loai: str                           # xuyen_suot | gap_khit | ghep_nhieu
    seat_class: str
    ghe_theo_doan: list[SeatSegment]
    so_lan_doi_cho: int = 0
    ga_doi: list[str] = field(default_factory=list)
    can_doi_cho: bool = False
    can_khach_chap_nhan: bool = False   # disclosure: khách phải chủ động đồng ý
    dwell_du: bool = True               # đủ thời gian dừng tại ga đổi
    cung_hang_cho: bool = True          # cùng/tương đương hạng chỗ
    rank: int = 0
    do_khit: int | None = None
    ghi_chu: str = ""

    def to_dict(self):
        d = asdict(self); d["ghe_theo_doan"] = [s.to_dict() for s in self.ghe_theo_doan]; return d


# ---------------- BT3: tải đoạn + quota ----------------
@dataclass
class SegmentLoad:
    khu_gian_id: int
    ga_dau: str
    ga_cuoi: str
    lf: float
    suc_chua: int
    con_trong: int
    phan_loai: str                      # nghen | trong | binh_thuong
    bid_price: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class QuotaRow:
    khu_gian_id: int
    loai_hanh_trinh: str                # ngan | trung | dai (through=dai)
    seat_class: str
    quota: int
    booking_limit: int
    bid_price: int

    def to_dict(self):
        return asdict(self)


# ---------------- BT1: dự báo ----------------
@dataclass
class ForecastRow:
    origin: str
    dest: str
    date: str
    train_id: str
    seat_class: str
    u: float
    total_demand: float
    remaining_demand: float
    explain: str = ""

    def to_dict(self):
        return asdict(self)


# ---------------- BT5: báo giá ----------------
@dataclass
class Quote:
    gia_de_xuat: int
    gia_goc_F0: int
    gia_mua_vu: int
    delta_mua: float
    delta_dong: float
    bid_price_route: int
    rule_ids: list[str]
    giai_thich: str
    thanh_phan: list[dict] = field(default_factory=list)
    held: bool = False
    csxh_muc: float = 0.0

    def to_dict(self):
        return asdict(self)


# ---------------- BT7: waitlist ----------------
@dataclass
class WaitlistEntry:
    id: int
    request: BookingRequest
    priority_score: float
    trang_thai: str = "CHO"             # CHO | KHOP | HET_HAN | HUY

    def to_dict(self):
        return {"id": self.id, "request": self.request.to_dict(),
                "priority_score": self.priority_score, "trang_thai": self.trang_thai}


# ---------------- BT5(group): xếp nhóm ----------------
@dataclass
class GroupPlan:
    kha_thi: bool
    seat_class: str
    assignments: list[SeatSegment]
    toa: list[int]
    diem_lien_ke: float                 # 0..1, càng cao càng liền
    so_lan_tach: int
    ghi_chu: str = ""

    def to_dict(self):
        d = asdict(self); d["assignments"] = [s.to_dict() for s in self.assignments]; return d


# ---------------- Audit: log đề xuất/quyết định ----------------
@dataclass
class ProposalLog:
    loai: str                           # FORECAST | ALLOCATION | MERGE | PRICE | RELEASE | GROUP | WAITLIST
    input: dict
    output: dict
    explain: str
    model_version: str = "1.0"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return _clean(asdict(self))

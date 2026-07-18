#!/usr/bin/env python
"""
Inverse-of-export loader: rebuild the FULL runtime DB (~23 tables) from the
lossy V1-shaped export in v2-as-v1/data/, for one month (default 2026-06).

Mental model: the export is `full_db --JOIN/aggregate--> data/`. This is the
reverse. Columns marked lossy:false in v1_compatibility.json invert exactly;
everything else is synthesized deterministically under the DB constraints and
flagged with `# FABRICATED:` below.

WARNING: this CLEARS every table and overwrites the golden-demo scenario on
purpose (see CLAUDE.md "dataset never connects to runtime"). Only run against a
DB you are willing to wipe.

Usage:
    python load_mock_from_dataset.py                 # 2026-06, full FREE grid
    python load_mock_from_dataset.py --month 2026-05
    python load_mock_from_dataset.py --sold-only     # skip FREE cells (fast/light)
    python load_mock_from_dataset.py --self-check     # no DB, test the mapping logic
    AULAC_DSN=postgresql://u:p@host/db python load_mock_from_dataset.py
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, uuid
from datetime import datetime, timedelta, time, timezone

DATA_DIR = os.environ.get(
    "AULAC_DATA_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__),
                                 "..", "..", "..", "v2-as-v1", "data")),
)
DSN = os.environ.get("AULAC_DSN", "postgresql://aulac_user:aulac_password@localhost:5432/aulac_db")
TZ = timezone(timedelta(hours=7))  # Asia/Ho_Chi_Minh

# trang_thai (V1) -> (booking.status, hold.status, offer.decision)
TX_STATUS = {
    "HIEU_LUC": ("CONFIRMED", "CONFIRMED", "ACCEPT"),   # valid, seat occupied
    "DA_TRA":   ("CANCELLED", "CONFIRMED", "ACCEPT"),   # refunded, seat released
    "HUY":      ("CANCELLED", "CANCELLED", "ACCEPT"),   # cancelled, seat released
}
# search_log ket_qua -> forecast_observation.result_status
KETQUA = {
    "MUA": ("PURCHASED", None), "KHONG_MUA": ("NO_PURCHASE", None),
    "BO_VI_GIA": ("REJECTED", "PRICE"), "TU_CHOI_HET_CHO": ("REJECTED", "CAPACITY"),
    "TU_CHOI_DOI_CHO": ("REJECTED", "SPLIT"),
}
NS = uuid.UUID("00000000-0000-0000-0000-00000000a17c")  # stable namespace for synth UUIDs


def sid(*parts) -> str:
    return str(uuid.uuid5(NS, ":".join(str(p) for p in parts)))


def h16(*parts) -> str:
    return hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()[:16]


def parse_cho_so(cho_so: str):
    """'NGOI_MEM_DH:0004@0-1|NAM_K6_T3:0000@1-3' -> primary seat_id, used for the
    whole ticket OD. Berth tier collapses to the V1 aggregate class the ticket
    was sold under, so seat_id uses <agg_class>-<num>. Returns (class_num_str)."""
    first = cho_so.split("|")[0]
    label = first.split("@")[0]            # NGOI_MEM_DH:0004
    cls, num = label.rsplit(":", 1)
    return cls, num                        # aggregate class already in cho_so's label


def seat_id_of(agg_class: str, num: str) -> str:
    return f"{agg_class}-{int(num):04d}"


def od_segments(pos_di: int, pos_den: int):
    """1-based stop seqs -> inclusive DB segment range [seg_from, seg_to].
    Travel stop a..b occupies segments a..b-1 (segment i joins stop i, i+1)."""
    return pos_di, pos_den - 1


def self_check():
    cls, num = parse_cho_so("NGOI_MEM_DH:0004@0-1")
    assert (cls, num) == ("NGOI_MEM_DH", "0004"), (cls, num)
    assert seat_id_of("NAM_K6", "12") == "NAM_K6-0012"
    cls, num = parse_cho_so("NAM_K6_T3:0000@1-3|NAM_K6_T3:0000@3-5")
    assert (cls, num) == ("NAM_K6_T3", "0000")
    assert od_segments(1, 3) == (1, 2)     # stops 1->3 => segments 1,2
    assert od_segments(2, 3) == (2, 2)     # one segment
    # a 4-stop run: HNO(1) VIN(2) HUE(3) SGO(4); ticket HNO->HUE covers seg 1,2
    stops = {"HNO": 1, "VIN": 2, "HUE": 3, "SGO": 4}
    f, t = od_segments(stops["HNO"], stops["HUE"])
    assert (f, t) == (1, 2)
    print("self-check OK")


# --------------------------------------------------------------------------- #
def main():
    import pandas as pd

    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="2026-06")
    ap.add_argument("--sold-only", action="store_true",
                    help="skip FREE seat_segment_state cells (much smaller/faster)")
    ap.add_argument("--dsn", default=DSN)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()

    import psycopg

    def rd(name):
        p = os.path.join(DATA_DIR, name)
        return pd.read_csv(p) if name.endswith(".csv") else pd.read_parquet(p)

    print(f"data dir : {DATA_DIR}")
    print(f"month    : {args.month}")
    stations = rd("stations.csv")
    trains = rd("trains.csv")
    run_sum = rd("run_summary.csv")
    tx = rd(f"transactions/thang={args.month}")
    search = rd(f"search_log/thang={args.month}")
    run_sum = run_sum[run_sum["ngay_chay"].astype(str).str.startswith(args.month)].copy()
    print(f"loaded   : {len(tx):,} tickets, {len(search):,} searches, {len(run_sum):,} runs")

    km = dict(zip(stations["ga_id"], stations["ly_trinh_km"].astype(float)))
    train_dir = dict(zip(trains["mac_tau"], trains["chieu"]))
    train_dep = dict(zip(trains["mac_tau"], trains["gio_xp"]))
    cap = {r.mac_tau: {"NGOI_MEM_DH": int(r.cap_NGOI_MEM_DH),
                       "NAM_K6": int(r.cap_NAM_K6), "NAM_K4": int(r.cap_NAM_K4)}
           for r in trains.itertuples()}
    run_train = dict(zip(run_sum["chuyen_id"], run_sum["mac_tau"]))

    # ---- reconstruct per-train stop list (run_stops was dropped in V1) -------
    # FABRICATED topology: the true intermediate-stop set is gone; we ground it
    # in the stations that actually appear as ga_di/ga_den in this month's data
    # for the train, ordered along the corridor in travel direction.
    served = {}
    for col in ("ga_di", "ga_den"):
        for tr, gg in zip(tx["mac_tau"], tx[col]):
            served.setdefault(tr, set()).add(gg)
    stop_seq = {}          # train -> {station_code: 1-based seq}
    stop_list = {}         # train -> [station_code ...] in travel order
    for tr, codes in served.items():
        codes = [c for c in codes if c in km]
        origin_hi = km.get(trains.set_index("mac_tau").loc[tr, "ga_dau"] if tr in train_dir else None, 0)
        ordered = sorted(codes, key=lambda c: km[c])
        # orient so the train's ga_dau (origin) is sequence 1
        if tr in train_dir:
            ga_dau = trains.set_index("mac_tau").loc[tr, "ga_dau"]
            if ga_dau in km and km[ga_dau] > (km[ordered[0]] if ordered else 0):
                ordered = ordered[::-1]
        stop_list[tr] = ordered
        stop_seq[tr] = {c: i + 1 for i, c in enumerate(ordered)}

    # observed max seat index per (train, agg_class) so the FREE grid always
    # contains every SOLD seat even if it exceeds the trains.csv capacity.
    obs_cap = {}
    tx_cls, tx_num = [], []
    for cs in tx["cho_so"]:
        c, n = parse_cho_so(str(cs))
        agg = "NAM_K6" if c.startswith("NAM_K6") else "NAM_K4" if c.startswith("NAM_K4") else c
        tx_cls.append(agg); tx_num.append(int(n))
    tx["dagg_class"] = tx_cls
    tx["dseat_num"] = tx_num
    for tr, agg, n in zip(tx["mac_tau"], tx["dagg_class"], tx["dseat_num"]):
        obs_cap[(tr, agg)] = max(obs_cap.get((tr, agg), 0), n + 1)

    def run_cap(tr, agg):
        return max(cap.get(tr, {}).get(agg, 0), obs_cap.get((tr, agg), 0))

    # per-ticket derived geometry (reused by seat_segment_state + offer.seat_plan)
    seg_from, seg_to, seat_ids = [], [], []
    for tr, di, den, agg, num in zip(tx["mac_tau"], tx["ga_di"], tx["ga_den"],
                                     tx["dagg_class"], tx["dseat_num"]):
        smap = stop_seq.get(tr, {})
        pf, pt = smap.get(di), smap.get(den)
        if pf is None or pt is None or pt <= pf:
            seg_from.append(None); seg_to.append(None); seat_ids.append(None); continue
        f, t = od_segments(pf, pt)
        seg_from.append(f); seg_to.append(t)
        seat_ids.append(seat_id_of(agg, str(num)))
    tx["dseg_from"] = seg_from
    tx["dseg_to"] = seg_to
    tx["dseat_id"] = seat_ids

    # purchased_at = service_date - lead_time_ngay, at 10:00 local (sub-day precision was dropped)
    def bought_at(ngay, lead):
        d = datetime.fromisoformat(str(ngay)).date()
        return datetime.combine(d - timedelta(days=int(lead)), time(10, 0), TZ)
    tx["dbought"] = [bought_at(d, l) for d, l in zip(tx["ngay_chay"], tx["lead_time_ngay"])]

    conn = psycopg.connect(args.dsn, autocommit=False)
    cur = conn.cursor()

    def copy(table, cols, rows):
        n = 0
        with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
            for r in rows:
                cp.write_row(r)
                n += 1
        print(f"  {table:<22} {n:>10,}")

    TABLES = ["refresh_tokens", "audit_log", "external_factor", "bid_price",
              "proposal_log", "quota_version", "waiting_list", "allocation_snapshot",
              "demand_forecast", "forecast_observation", "decision_record",
              "booking", "seat_hold", "offer", "seat_segment_state", "fare_product",
              "service_run", "train_stop", "promotion", "pricing_policy",
              "train", "station", "users"]
    print("truncating…")
    cur.execute("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE")

    print("loading…")
    # 1. users  — FABRICATED: dataset is anonymous. 1 admin, 2 managers, 17 pax.
    users = []
    for i in range(20):
        role = "admin" if i == 0 else "revenue_manager" if i < 3 else "user"
        uid = sid("user", i)
        users.append((uid, f"user{i:02d}", f"user{i:02d}@aulac.local",
                      "x", role, datetime(2025, 7, 1, tzinfo=TZ), datetime(2025, 7, 1, tzinfo=TZ)))
    pax = [u[0] for u in users if u[4] == "user"]
    copy("users", ["user_id", "username", "email", "password_hash", "role", "created_at", "updated_at"], users)

    # 2. station (exact invert; DB has no dwell/province cols)
    copy("station", ["station_id", "station_name", "ly_trinh_km"],
         ((r.ga_id, r.ten_ga, round(float(r.ly_trinh_km))) for r in stations.itertuples()))

    # 3. train (exact; train_name FABRICATED from code)
    copy("train", ["train_id", "train_name", "capacity"],
         ((r.mac_tau, f"Tàu {r.mac_tau}", int(r.suc_chua)) for r in trains.itertuples()))

    # 4. pricing_policy — FABRICATED single active policy (ratios from V2 migration)
    copy("pricing_policy", ["name", "max_delta_percent", "is_active", "floor_ratio", "ceiling_ratio", "policy_version"],
         [("default", 60.0, True, 0.55, 1.60, 1)])
    # promotion: none in dataset -> leave empty.

    # 5. train_stop — FABRICATED times (interpolated from km @ 60 km/h, dwell 180s)
    def stop_rows():
        for tr, codes in stop_list.items():
            if not codes:
                continue
            dep0 = str(train_dep.get(tr, "08:00"))
            hh, mm = (int(x) for x in dep0.split(":"))
            base = datetime(2000, 1, 1, hh, mm)
            k0 = km[codes[0]]
            for seq, c in enumerate(codes, start=1):
                mins = abs(km[c] - k0)  # 60 km/h => 1 min/km
                arr = base + timedelta(minutes=mins)
                dep = arr + timedelta(minutes=3)
                a = None if seq == 1 else arr.time()
                d = None if seq == len(codes) else dep.time()
                yield (tr, c, seq, a, d, 180)
    copy("train_stop", ["train_id", "station_id", "stop_sequence", "arrival_time", "departure_time", "dwell_seconds"],
         stop_rows())

    # 6. service_run (exact; direction from train)
    copy("service_run", ["service_run_id", "train_id", "service_date", "direction", "status", "matrix_version"],
         ((r.chuyen_id, r.mac_tau, r.ngay_chay, train_dir.get(r.mac_tau, "LE"), "ACTIVE", 1)
          for r in run_sum.itertuples()))

    # 7. fare_product — invert w/ loss: median gia_goc per (run, OD, class)
    fp = (tx.groupby(["chuyen_id", "ga_di", "ga_den", "loai_cho"])["gia_goc"]
            .median().round().astype("int64").reset_index())
    copy("fare_product", ["service_run_id", "origin_station_id", "dest_station_id", "seat_class", "base_fare_vnd", "version"],
         ((r.chuyen_id, r.ga_di, r.ga_den, r.loai_cho, int(r.gia_goc), 1) for r in fp.itertuples()))

    # 8. seat_segment_state — the heavy one. SOLD from HIEU_LUC tickets (occupied);
    #    DA_TRA/HUY released their seats -> FREE. Full grid unless --sold-only.
    valid = tx[(tx["trang_thai"] == "HIEU_LUC") & tx["dseg_from"].notna()]
    sold_by_run = {}
    for run, sidd, f, t in zip(valid["chuyen_id"], valid["dseat_id"],
                               valid["dseg_from"], valid["dseg_to"]):
        s = sold_by_run.setdefault(run, {})
        for seg in range(int(f), int(t) + 1):
            s.setdefault(sidd, set()).add(seg)

    def sss_rows():
        for run in run_sum["chuyen_id"]:
            tr = run_train.get(run)
            codes = stop_list.get(tr) or []
            nseg = len(codes) - 1
            if nseg < 1:
                continue
            sold = sold_by_run.get(run, {})
            if args.sold_only:
                for sidd, segs in sold.items():
                    for seg in segs:
                        yield (run, sidd, seg, "SOLD", None, None, 1)
                continue
            for agg in ("NGOI_MEM_DH", "NAM_K6", "NAM_K4"):
                for i in range(run_cap(tr, agg)):
                    sidd = seat_id_of(agg, str(i))
                    ssegs = sold.get(sidd, ())
                    for seg in range(1, nseg + 1):
                        yield (run, sidd, seg, "SOLD" if seg in ssegs else "FREE", None, None, 1)
    copy("seat_segment_state",
         ["service_run_id", "seat_id", "segment_id", "status", "hold_id", "hold_expires_at", "version"],
         sss_rows())

    # 9-11-… ticket lifecycle: offer / seat_hold / booking / decision_record (1 per ticket)
    def seat_plan(r):
        if r.dseat_id is None:
            return json.dumps([])
        return json.dumps([{"seat_id": r.dseat_id,
                            "segment_from": int(r.dseg_from), "segment_to": int(r.dseg_to)}])

    copy("offer",
         ["offer_id", "service_run_id", "matrix_version", "forecast_version", "policy_version",
          "decision", "seat_plan", "final_price_vnd", "expires_at", "created_at",
          "origin_station_id", "dest_station_id", "seat_class"],
         ((f"O-{r.ve_id}", r.chuyen_id, 1, 1, 1,
           TX_STATUS.get(r.trang_thai, ("", "", "ACCEPT"))[2], seat_plan(r),
           int(r.gia_cuoi), r.dbought + timedelta(minutes=15), r.dbought,
           r.ga_di, r.ga_den, r.loai_cho) for r in tx.itertuples()))

    copy("seat_hold", ["hold_id", "offer_id", "status", "idempotency_key", "expires_at", "created_at"],
         ((f"H-{r.ve_id}", f"O-{r.ve_id}", TX_STATUS.get(r.trang_thai, ("", "ACTIVE"))[1],
           f"idem-{r.ve_id}", r.dbought + timedelta(minutes=15), r.dbought) for r in tx.itertuples()))

    def booking_rows():
        for i, r in enumerate(tx.itertuples()):
            bstat = TX_STATUS.get(r.trang_thai, ("CONFIRMED",))[0]
            confirmed = r.dbought
            cancelled = None if bstat == "CONFIRMED" else r.dbought + timedelta(hours=1)
            yield (f"B-{r.ve_id}", f"H-{r.ve_id}", pax[i % len(pax)], None, "WEB", None,
                   bstat, r.dbought, confirmed, cancelled)
    copy("booking",
         ["booking_id", "hold_id", "user_id", "group_id", "booking_channel", "promo_id",
          "status", "created_at", "confirmed_at", "cancelled_at"], booking_rows())

    copy("decision_record",
         ["decision_id", "input_hash", "versions", "result", "base_fare_vnd",
          "ai_suggested_price_vnd", "final_price_vnd", "explanation_code", "actor", "created_at"],
         ((f"D-{r.ve_id}", h16(r.ve_id, r.gia_cuoi),
           json.dumps({"matrix": 1, "forecast": 1, "policy": 1}), "ACCEPT",
           int(r.gia_goc), int(r.gia_niem_yet), int(r.gia_cuoi),
           str(r.che_do_gia), "system", r.dbought) for r in tx.itertuples()))

    # 12. forecast_observation <- search_log funnel (grounded)
    def fo_rows():
        for r in search.itertuples():
            rs, rr = KETQUA.get(str(r.ket_qua), ("NO_PURCHASE", None))
            yield (rs, rr, 1, int(r.lead_time_ngay), "search_log", str(r.yeu_cau_id),
                   datetime.fromisoformat(str(r.ngay_di)).replace(tzinfo=TZ))
    copy("forecast_observation",
         ["result_status", "rejection_reason", "quantity", "days_to_departure", "source", "dedup_key", "created_at"],
         fo_rows())

    # 13. demand_forecast — FABRICATED: realized ticket counts stand in for the
    #     (unrecoverable) true forecast, per (run, OD, class).
    df = tx.groupby(["chuyen_id", "ga_di", "ga_den", "loai_cho"]).size().reset_index(name="n")
    copy("demand_forecast",
         ["service_run_id", "origin_station_id", "dest_station_id", "seat_class",
          "forecast_demand", "confidence_score", "forecast_version"],
         ((r.chuyen_id, r.ga_di, r.ga_den, r.loai_cho, int(r.n), None, 1) for r in df.itertuples()))

    # 14. allocation_snapshot — one per run from run_summary aggregates
    copy("allocation_snapshot",
         ["service_run_id", "matrix_version", "forecast_version", "formula_version", "leg_metrics"],
         ((r.chuyen_id, 1, 1, 1,
           json.dumps({"lf_bq": float(r.lf_bq), "so_gap": int(r.so_gap),
                       "so_ve": int(r.so_ve), "doanh_thu": int(r.doanh_thu)}))
          for r in run_sum.itertuples()))

    # 15. waiting_list — capacity-rejected searches. FABRICATED seat_class
    #     (search_log dropped it) -> NGOI_MEM_DH; runs already departed -> EXPIRED.
    wl = search[search["ket_qua"] == "TU_CHOI_HET_CHO"]
    def wl_rows():
        for i, r in enumerate(wl.itertuples()):
            run = r.chuyen_id if isinstance(r.chuyen_id, str) else None
            if not run:
                continue
            yield (pax[i % len(pax)], run, r.ga_di, r.ga_den, "NGOI_MEM_DH", 0, "EXPIRED",
                   datetime.fromisoformat(str(r.ngay_di)).replace(tzinfo=TZ), None, False, 1, None)
    copy("waiting_list",
         ["user_id", "service_run_id", "origin_station_id", "dest_station_id", "seat_class",
          "priority_score", "status", "created_at", "expires_at", "priority_passenger", "quantity", "matched_hold_id"],
         wl_rows())

    conn.commit()
    print("done. committed.")
    # empty on purpose (no export source): refresh_tokens, audit_log, external_factor,
    # bid_price, proposal_log, quota_version.


if __name__ == "__main__":
    main()

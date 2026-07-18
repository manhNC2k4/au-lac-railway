# -*- coding: utf-8 -*-
"""SeatStateManager — TRANSACTION BOUNDARY DUY NHẤT cho seat_segment_state +
service_run.matrix_version (DEV1 plan §"Bạn là single writer"). Không module nào
khác được ghi thẳng vào 2 bảng này.

CAS: SELECT ... FOR UPDATE toàn bộ cells trong MỘT transaction, order segment_id
tăng dần (deadlock guard), verify FREE + version khớp, UPDATE + bump
service_run.matrix_version cùng transaction. Postgres lo atomicity — không lock
manager tự viết, không Redis, không retry loop (theo plan, rung thang thấp nhất).
"""
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

from .clock import Clock
from .errors import HoldExpired, SeatConflict, StaleSnapshot

HOLD_TTL_SECONDS = 600  # nguồn: spec (docs/API_Contract.md — hold_expires_at ~10 phút sau)


@dataclass
class HoldResult:
    hold_id: str
    status: str
    expires_at: datetime
    new_matrix_version: int


@dataclass
class ConfirmResult:
    booking_id: str
    status: str
    final_price_vnd: int
    decision_record_id: str | None


class SeatStateManager:
    def __init__(self, conn: psycopg.Connection, clock: Clock):
        self.conn = conn
        self.clock = clock

    # ------------------------------------------------------------------
    # Expiry — chạy trước MỌI state read/write khác (plan yêu cầu)
    # ------------------------------------------------------------------
    def expire_due_holds(self, service_run_id: str | None = None) -> int:
        now = self.clock.now()
        with self.conn.cursor() as cur:
            if service_run_id:
                cur.execute(
                    """UPDATE seat_hold SET status='EXPIRED'
                       WHERE status='ACTIVE' AND expires_at <= %s
                         AND offer_id IN (SELECT offer_id FROM offer WHERE service_run_id=%s)
                       RETURNING hold_id""",
                    (now, service_run_id),
                )
            else:
                cur.execute(
                    """UPDATE seat_hold SET status='EXPIRED'
                       WHERE status='ACTIVE' AND expires_at <= %s
                       RETURNING hold_id""",
                    (now,),
                )
            expired_ids = [r[0] for r in cur.fetchall()]
            if not expired_ids:
                self.conn.commit()
                return 0
            cur.execute(
                """UPDATE seat_segment_state
                   SET status='FREE', hold_id=NULL, hold_expires_at=NULL, version=version+1
                   WHERE hold_id = ANY(%s)""",
                (expired_ids,),
            )
            if service_run_id:
                cur.execute(
                    "UPDATE service_run SET matrix_version = matrix_version + 1 WHERE service_run_id=%s",
                    (service_run_id,),
                )
        self.conn.commit()
        return len(expired_ids)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get_matrix_version(self, service_run_id: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT matrix_version FROM service_run WHERE service_run_id=%s", (service_run_id,))
            row = cur.fetchone()
            return row[0] if row else 0

    def get_seatmap(self, service_run_id: str) -> dict:
        self.expire_due_holds(service_run_id)
        with self.conn.cursor() as cur:
            cur.execute("SELECT matrix_version FROM service_run WHERE service_run_id=%s", (service_run_id,))
            row = cur.fetchone()
            matrix_version = row[0] if row else 0
            cur.execute(
                """SELECT seat_id, segment_id, status FROM seat_segment_state
                   WHERE service_run_id=%s ORDER BY seat_id, segment_id""",
                (service_run_id,),
            )
            rows = cur.fetchall()
        seats: dict[str, dict] = {}
        for seat_id, segment_id, status in rows:
            seats.setdefault(seat_id, {})[str(segment_id)] = status
        return {"matrix_version": matrix_version, "seats": seats}

    def find_continuous_same_seat(self, service_run_id: str, seg_from: int, seg_to: int) -> str | None:
        """Trả seat_id đầu tiên (thứ tự alphabet) mà TOÀN BỘ [seg_from,seg_to] đang FREE."""
        segs = list(range(seg_from, seg_to + 1))
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT seat_id FROM seat_segment_state
                   WHERE service_run_id=%s AND segment_id = ANY(%s) AND status='FREE'
                   GROUP BY seat_id HAVING COUNT(*) = %s
                   ORDER BY seat_id LIMIT 1""",
                (service_run_id, segs, len(segs)),
            )
            row = cur.fetchone()
            return row[0] if row else None

    # ------------------------------------------------------------------
    # Reset — all-or-nothing, deterministic checksum
    # ------------------------------------------------------------------
    def reset_scenario(self, seed_dir: Path) -> dict:
        scenario = json.loads((seed_dir / "scenario.json").read_text(encoding="utf-8"))
        bookings = [json.loads(line) for line in
                    (seed_dir / "initial_bookings.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        fare_products = json.loads((seed_dir / "fare_products.json").read_text(encoding="utf-8"))["products"]
        pricing_policy = json.loads((seed_dir / "pricing_policy.json").read_text(encoding="utf-8"))
        forecast = json.loads((seed_dir / "forecast.json").read_text(encoding="utf-8"))

        service_run_id = scenario["service_run_id"]
        seats = scenario["seats"]
        n_segments = len(scenario["segments"])

        try:
            with self.conn.cursor() as cur:
                for st in scenario["stations"]:
                    cur.execute(
                        """INSERT INTO station (station_id, station_name, ly_trinh_km)
                           VALUES (%s,%s,%s)
                           ON CONFLICT (station_id) DO UPDATE
                           SET station_name=EXCLUDED.station_name, ly_trinh_km=EXCLUDED.ly_trinh_km""",
                        (st["station_id"], st["name"], round(st["ly_trinh_km"])),
                    )
                cur.execute(
                    """INSERT INTO train (train_id, train_name, capacity)
                       VALUES (%s,%s,%s)
                       ON CONFLICT (train_id) DO UPDATE SET train_name=EXCLUDED.train_name""",
                    (scenario["train_id"], scenario["train_id"], len(seats)),
                )
                cur.execute(
                    """INSERT INTO service_run (service_run_id, train_id, service_date, direction, status, matrix_version)
                       VALUES (%s,%s,%s,%s,'ACTIVE',1)
                       ON CONFLICT (service_run_id) DO UPDATE
                       SET service_date=EXCLUDED.service_date, direction=EXCLUDED.direction,
                           status='ACTIVE', matrix_version=1""",
                    (service_run_id, scenario["train_id"], scenario["service_date"], scenario["direction"]),
                )
                # clear + rebuild matrix (không partial: hết mọi cell về FREE trước khi replay bookings)
                cur.execute(
                    """DELETE FROM booking WHERE hold_id IN (
                           SELECT hold_id FROM seat_hold WHERE offer_id IN (
                               SELECT offer_id FROM offer WHERE service_run_id=%s))""",
                    (service_run_id,),
                )
                cur.execute("DELETE FROM seat_hold WHERE offer_id IN (SELECT offer_id FROM offer WHERE service_run_id=%s)", (service_run_id,))
                cur.execute("DELETE FROM offer WHERE service_run_id=%s", (service_run_id,))
                cur.execute("DELETE FROM seat_segment_state WHERE service_run_id=%s", (service_run_id,))
                # P7: reset cũng dọn sạch bảng vận hành scoped theo service_run_id — nếu
                # không, waitlist/quota/audit cũ từ trước reset sẽ tồn đọng và bị match()/
                # rollback() nhầm là dữ liệu hiện hành của phiên mới.
                cur.execute("DELETE FROM waiting_list WHERE service_run_id=%s", (service_run_id,))
                cur.execute("DELETE FROM quota_version WHERE service_run_id=%s", (service_run_id,))
                cur.execute("DELETE FROM proposal_log WHERE service_run_id=%s", (service_run_id,))
                rows = [(service_run_id, seat_id, seg) for seat_id in seats for seg in range(1, n_segments + 1)]
                cur.executemany(
                    """INSERT INTO seat_segment_state (service_run_id, seat_id, segment_id, status, version)
                       VALUES (%s,%s,%s,'FREE',1)""",
                    rows,
                )
                for b in bookings:
                    cur.execute(
                        """UPDATE seat_segment_state SET status=%s, version=version+1
                           WHERE service_run_id=%s AND seat_id=%s AND segment_id = ANY(%s)""",
                        (b["status"], service_run_id, b["seat_id"], b["segments"]),
                    )
                cur.execute("DELETE FROM fare_product WHERE service_run_id=%s", (service_run_id,))
                for p in fare_products:
                    cur.execute(
                        """INSERT INTO fare_product (service_run_id, origin_station_id, dest_station_id, seat_class, base_fare_vnd, version)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (service_run_id, p["origin_station_id"], p["dest_station_id"], p["seat_class"],
                         p["gia_goc_vnd"], p["version"]),
                    )
                cur.execute(
                    """INSERT INTO pricing_policy (name, max_delta_percent, is_active, floor_ratio, ceiling_ratio, policy_version)
                       VALUES (%s,%s,TRUE,%s,%s,%s)""",
                    (f"{service_run_id}_policy", pricing_policy["max_delta_ratio"] * 100,
                     pricing_policy["floor_ratio"], pricing_policy["ceiling_ratio"], pricing_policy["policy_version"]),
                )
                cur.execute("DELETE FROM demand_forecast WHERE service_run_id=%s", (service_run_id,))
                for seg in forecast["segments"]:
                    cur.execute(
                        """INSERT INTO demand_forecast
                           (service_run_id, origin_station_id, dest_station_id, seat_class, forecast_demand, confidence_score, forecast_version)
                           VALUES (%s,NULL,NULL,%s,%s,%s,%s)""",
                        (service_run_id, seg["seat_class"], round(seg["forecast_remaining_demand"]),
                         seg["confidence"], forecast["forecast_version"]),
                    )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()

        checksum_payload = {"scenario": scenario, "bookings": bookings}
        checksum = hashlib.sha256(
            json.dumps(checksum_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return {
            "service_run_id": service_run_id,
            "matrix_version": 1,
            "forecast_version": forecast["forecast_version"],
            "policy_version": pricing_policy["policy_version"],
            "checksum": checksum,
        }

    # ------------------------------------------------------------------
    # Hold — atomic multi-cell CAS (H6-H10 hardest part)
    # ------------------------------------------------------------------
    def hold(self, service_run_id: str, seat_id: str, segments: list[int],
              expected_matrix_version: int, idempotency_key: str, offer_id: str) -> HoldResult:
        """1 ghế nhiều đoạn — trường hợp riêng của hold_multi (same-seat, MVP)."""
        return self.hold_multi(service_run_id, [(seat_id, segments)],
                               expected_matrix_version, idempotency_key, offer_id)

    def hold_multi(self, service_run_id: str, legs: list[tuple[str, list[int]]],
                    expected_matrix_version: int, idempotency_key: str, offer_id: str) -> HoldResult:
        """CAS nhiều ghế·nhiều đoạn (P5 ghép nhiều ghế) — MỘT transaction, tất-cả-hoặc-không:
        khoá + verify FREE toàn bộ leg trước, chỉ UPDATE khi mọi leg đều sạch; 1 hold_id
        dùng chung cho mọi cell (schema seat_hold không ràng buộc 1 seat_id — không cần migration)."""
        self.expire_due_holds(service_run_id)

        with self.conn.cursor() as cur:
            cur.execute("SELECT hold_id FROM seat_hold WHERE idempotency_key=%s", (idempotency_key,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "SELECT hold_id, status, expires_at FROM seat_hold WHERE hold_id=%s", (existing[0],))
                hold_id, status, expires_at = cur.fetchone()
                mv = self.get_matrix_version(service_run_id)
                self.conn.commit()
                return HoldResult(hold_id, status, expires_at, mv)

        legs_sorted = sorted((seat_id, sorted(segs)) for seat_id, segs in legs)  # seat_id tăng dần — deadlock guard
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT matrix_version FROM service_run WHERE service_run_id=%s FOR UPDATE",
                    (service_run_id,),
                )
                row = cur.fetchone()
                current_mv = row[0] if row else None
                if current_mv is None or current_mv != expected_matrix_version:
                    self.conn.rollback()
                    raise StaleSnapshot(
                        "expected_matrix_version không khớp",
                        {"expected": expected_matrix_version, "actual": current_mv},
                    )

                # Pha 1: khoá + verify FREE của MỌI leg trước — chưa UPDATE gì.
                for seat_id, segs_sorted in legs_sorted:
                    cur.execute(
                        """SELECT segment_id, status FROM seat_segment_state
                           WHERE service_run_id=%s AND seat_id=%s AND segment_id = ANY(%s)
                           ORDER BY segment_id FOR UPDATE""",
                        (service_run_id, seat_id, segs_sorted),
                    )
                    rows = cur.fetchall()
                    if len(rows) != len(segs_sorted) or any(status != "FREE" for _, status in rows):
                        self.conn.rollback()
                        raise SeatConflict(
                            "Ghế vừa bị người khác giữ/mua",
                            {"seat_id": seat_id, "segments": segs_sorted},
                        )

                # Pha 2: mọi leg đã sạch — UPDATE tất cả dùng chung 1 hold_id.
                now = self.clock.now()
                expires_at = now + timedelta(seconds=HOLD_TTL_SECONDS)
                hold_id = f"hold_{uuid.uuid4().hex[:12]}"

                for seat_id, segs_sorted in legs_sorted:
                    cur.execute(
                        """UPDATE seat_segment_state
                           SET status='HELD', hold_id=%s, hold_expires_at=%s, version=version+1
                           WHERE service_run_id=%s AND seat_id=%s AND segment_id = ANY(%s)""",
                        (hold_id, expires_at, service_run_id, seat_id, segs_sorted),
                    )
                cur.execute(
                    """INSERT INTO seat_hold (hold_id, offer_id, status, idempotency_key, expires_at)
                       VALUES (%s,%s,'ACTIVE',%s,%s)""",
                    (hold_id, offer_id, idempotency_key, expires_at),
                )
                cur.execute(
                    "UPDATE service_run SET matrix_version = matrix_version + 1 WHERE service_run_id=%s RETURNING matrix_version",
                    (service_run_id,),
                )
                new_mv = cur.fetchone()[0]
        except (StaleSnapshot, SeatConflict):
            raise
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return HoldResult(hold_id, "ACTIVE", expires_at, new_mv)

    # ------------------------------------------------------------------
    # Confirm — idempotent HELD->SOLD, KHÔNG tính lại giá
    # ------------------------------------------------------------------
    def confirm(self, hold_id: str, idempotency_key: str) -> ConfirmResult:
        self.expire_due_holds()

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT booking_id, status, hold_id FROM booking WHERE hold_id=%s", (hold_id,))
            existing_booking = cur.fetchone()

            cur.execute(
                """SELECT sh.status, sh.expires_at, sh.offer_id, o.final_price_vnd
                   FROM seat_hold sh JOIN offer o ON o.offer_id = sh.offer_id
                   WHERE sh.hold_id=%s""",
                (hold_id,),
            )
            row = cur.fetchone()
        # decision_record_id không lưu trên offer (V1 schema không có cột này —
        # locked, không sửa migration ở P0); truy vết decision qua offer_id riêng.
        decision_record_id = None

        if existing_booking:
            booking_id, status, _ = existing_booking
            final_price = row[3] if row else 0
            self.conn.commit()
            return ConfirmResult(booking_id, "CONFIRMED", final_price, decision_record_id)

        if not row:
            self.conn.rollback()
            raise HoldExpired("Hold không tồn tại hoặc đã hết hạn", {"hold_id": hold_id})
        status, expires_at, offer_id, final_price = row
        if status != "ACTIVE":
            self.conn.rollback()
            raise HoldExpired("Hold đã quá hạn thanh toán", {"hold_id": hold_id, "status": status})

        try:
            with self.conn.cursor() as cur:
                booking_id = f"bk_{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """UPDATE seat_segment_state SET status='SOLD', hold_id=NULL, hold_expires_at=NULL, version=version+1
                       WHERE hold_id=%s""",
                    (hold_id,),
                )
                cur.execute("UPDATE seat_hold SET status='CONFIRMED' WHERE hold_id=%s", (hold_id,))
                cur.execute(
                    """INSERT INTO booking (booking_id, hold_id, status, confirmed_at)
                       VALUES (%s,%s,'CONFIRMED',%s)""",
                    (booking_id, hold_id, self.clock.now()),
                )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return ConfirmResult(booking_id, "CONFIRMED", final_price, decision_record_id)

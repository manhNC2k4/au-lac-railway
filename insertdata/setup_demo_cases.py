#!/usr/bin/env python
"""Create two deterministic demo runs from the two newest service runs.

Case A (newest run): only three seats in the selected class remain available:
  - seat 1: segments 1..5
  - seat 2: segments 1..7
  - seat 3: segments 1..10

Case B (second-newest run): only two seats remain available:
  - seat 1: segment 4
  - seat 2: segments 5..6

The passenger requests are intentionally not inserted. They are submitted from
the web UI after this script prepares inventory. Fare and forecast data are not
changed, so dynamic pricing continues through the normal offer pipeline.

Usage:
    python setup_demo_cases.py --self-check
    python setup_demo_cases.py --dry-run
    python setup_demo_cases.py
    python setup_demo_cases.py --seat-class NAM_K6

Production VPS (run from the repository root):
    docker compose --env-file .env -f docker-compose.prod.yml run --rm \
      -v "$PWD/insertdata:/insertdata:ro" backend \
      python /insertdata/setup_demo_cases.py --dry-run
    docker compose --env-file .env -f docker-compose.prod.yml run --rm \
      -v "$PWD/insertdata:/insertdata:ro" backend \
      python /insertdata/setup_demo_cases.py

The backend container already has psycopg and DATABASE_URL. AULAC_DSN or
--dsn can override DATABASE_URL when connecting to an external PostgreSQL.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any


DEFAULT_DSN = (
    os.environ.get("AULAC_DSN")
    or os.environ.get("DATABASE_URL")
    or "postgresql://aulac_user:aulac_password@localhost:5432/aulac_db"
)

CASE_SEGMENTS = {
    "A": (set(range(1, 6)), set(range(1, 8)), set(range(1, 11))),
    "B": ({4}, {5, 6}),
}

BACKUP_DDL = """
CREATE TABLE IF NOT EXISTS demo_case_backup (
    service_run_id varchar(50) NOT NULL,
    seat_id varchar(50) NOT NULL,
    segment_id int NOT NULL,
    seat_class varchar(20) NOT NULL,
    seat_index int NOT NULL,
    status text NOT NULL,
    hold_id text,
    hold_expires_at timestamptz,
    version int,
    backed_up_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (service_run_id, seat_id, segment_id)
)
"""

BACKUP_COLUMNS = {
    "service_run_id", "seat_id", "segment_id", "seat_class", "seat_index",
    "status", "hold_id", "hold_expires_at", "version", "backed_up_at",
}

REQUIRED_TABLES = {
    "flyway_schema_history", "service_run", "seat_segment_state",
    "train_seat_class", "train_seat_layout", "train_stop", "station",
    "booking_request", "booking_candidate", "offer", "seat_hold", "booking",
}


def free_cells(case: str, nseg: int, seats: list[str]) -> dict[str, set[int]]:
    """Return the exact FREE geometry requested for a demo case."""
    if case not in CASE_SEGMENTS:
        raise ValueError(f"unknown case: {case}")
    patterns = CASE_SEGMENTS[case]
    required_segment = max(max(segments) for segments in patterns)
    if nseg < required_segment:
        raise RuntimeError(
            f"Case {case} needs at least {required_segment} segments; got {nseg}"
        )
    if len(seats) < len(patterns):
        raise RuntimeError(
            f"Case {case} needs at least {len(patterns)} seats; got {len(seats)}"
        )
    return {seats[index]: set(segments) for index, segments in enumerate(patterns)}


def _self_check() -> None:
    seats = [f"S{i:03d}" for i in range(40)]
    assert free_cells("A", 24, seats) == {
        "S000": {1, 2, 3, 4, 5},
        "S001": {1, 2, 3, 4, 5, 6, 7},
        "S002": {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
    }
    assert free_cells("B", 24, seats) == {
        "S000": {4},
        "S001": {5, 6},
    }
    print("self-check OK: Case A=1..5/1..7/1..10, Case B=4/5..6")


def _validate_database(conn: Any) -> None:
    """Fail before mutation when the VPS points at a wrong or partial database."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user, current_setting('server_version')")
        database, user, version = cur.fetchone()
        missing = []
        for table in sorted(REQUIRED_TABLES):
            cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
            if cur.fetchone()[0] is None:
                missing.append(table)
        if missing:
            raise RuntimeError(
                "database is missing required Flyway tables: " + ", ".join(missing)
            )
        cur.execute(
            "SELECT COUNT(*), COALESCE(MAX(installed_rank), 0) "
            "FROM flyway_schema_history WHERE success"
        )
        migration_count, latest_rank = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM flyway_schema_history WHERE NOT success")
        failed_migrations = cur.fetchone()[0]
        if failed_migrations:
            raise RuntimeError(f"Flyway history contains {failed_migrations} failed migration(s)")
    conn.commit()
    print(
        f"Connected database={database} user={user} PostgreSQL={version} "
        f"Flyway={migration_count} successful migration(s), latest rank={latest_rank}"
    )


def _od(cur: Any, run: str, seg_from: int, seg_to: int) -> str:
    """Build the station label corresponding to a 1-based segment range."""
    cur.execute(
        "SELECT s.station_id, s.station_name FROM train_stop ts "
        "JOIN station s ON s.station_id = ts.station_id "
        "WHERE ts.train_id = (SELECT train_id FROM service_run WHERE service_run_id = %s) "
        "ORDER BY ts.stop_sequence",
        (run,),
    )
    stops = cur.fetchall()
    if seg_to >= len(stops):
        raise RuntimeError(
            f"run {run} has {len(stops)} stops, cannot label segment {seg_to}"
        )
    origin, destination = stops[seg_from - 1], stops[seg_to]
    return (
        f"{origin[0]} -> {destination[0]}  "
        f"({origin[1]} -> {destination[1]})"
    )


def _assert_backup_schema(cur: Any) -> None:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='demo_case_backup'"
    )
    columns = {row[0] for row in cur.fetchall()}
    if columns != BACKUP_COLUMNS:
        raise RuntimeError(
            "demo_case_backup has an old/incompatible schema; run rollback or "
            "drop that backup table before setup"
        )


def _prepare_transactions(cur: Any, run: str, seat_class: str) -> None:
    """Expire old work and reject inventory changes that would corrupt live sales."""
    cur.execute(
        """SELECT b.booking_id
             FROM booking b
             JOIN seat_hold sh ON sh.hold_id=b.hold_id
             JOIN offer o ON o.offer_id=sh.offer_id
            WHERE o.service_run_id=%s AND o.seat_class=%s
              AND b.status='CONFIRMED'
            LIMIT 1""",
        (run, seat_class),
    )
    confirmed = cur.fetchone()
    if confirmed:
        raise RuntimeError(
            f"run {run} class {seat_class} has confirmed booking {confirmed[0]}; "
            "use a clean demo run"
        )

    cur.execute(
        """UPDATE booking_request
              SET status='EXPIRED', updated_at=CURRENT_TIMESTAMP
            WHERE service_run_id=%s AND seat_class=%s
              AND status IN ('SUBMITTED','AI_PROCESSING','PENDING_ADMIN','APPROVED','SELECTED')
              AND expires_at <= CURRENT_TIMESTAMP""",
        (run, seat_class),
    )

    cur.execute(
        """SELECT request_id, status FROM booking_request
            WHERE service_run_id=%s AND seat_class=%s
              AND status IN ('SUBMITTED','AI_PROCESSING','PENDING_ADMIN','APPROVED','SELECTED')
            LIMIT 1""",
        (run, seat_class),
    )
    active_request = cur.fetchone()
    if active_request:
        raise RuntimeError(
            f"run {run} class {seat_class} has active booking request "
            f"{active_request[0]} ({active_request[1]})"
        )

    cur.execute(
        """SELECT sh.hold_id
             FROM seat_hold sh JOIN offer o ON o.offer_id=sh.offer_id
            WHERE o.service_run_id=%s AND o.seat_class=%s
              AND sh.status='ACTIVE' AND sh.expires_at > CURRENT_TIMESTAMP
            LIMIT 1""",
        (run, seat_class),
    )
    active_hold = cur.fetchone()
    if active_hold:
        raise RuntimeError(
            f"run {run} class {seat_class} has active hold {active_hold[0]}"
        )

    cur.execute(
        """UPDATE seat_hold sh SET status='EXPIRED'
              FROM offer o
             WHERE o.offer_id=sh.offer_id
               AND o.service_run_id=%s AND o.seat_class=%s
               AND sh.status='ACTIVE' AND sh.expires_at <= CURRENT_TIMESTAMP
         RETURNING sh.hold_id""",
        (run, seat_class),
    )
    expired_ids = [row[0] for row in cur.fetchall()]
    if expired_ids:
        cur.execute(
            """UPDATE seat_segment_state
                  SET status='FREE', hold_id=NULL, hold_expires_at=NULL,
                      version=COALESCE(version, 0) + 1
                WHERE service_run_id=%s AND seat_class=%s
                  AND hold_id=ANY(%s)""",
            (run, seat_class, expired_ids),
        )


def _physical_inventory(cur: Any, run: str, seat_class: str) -> list[dict[str, Any]]:
    """Return model seats joined to the derived physical train layout."""
    cur.execute(
        """SELECT DISTINCT ON (sss.seat_index)
                  sss.seat_id, sss.seat_index, tsl.coach_number, tsl.seat_number,
                  tsl.row_number, tsl.column_code, tsl.position_code,
                  tsl.compartment_number, tsl.berth_level
             FROM seat_segment_state sss
             JOIN service_run sr ON sr.service_run_id=sss.service_run_id
             JOIN train_seat_layout tsl
               ON tsl.train_id=sr.train_id
              AND tsl.seat_class=sss.seat_class
              AND tsl.seat_index=sss.seat_index
            WHERE sss.service_run_id=%s AND sss.seat_class=%s
            ORDER BY sss.seat_index, sss.seat_id""",
        (run, seat_class),
    )
    rows = cur.fetchall()
    inventory = [
        {
            "seat_id": row[0], "seat_index": row[1], "coach": row[2],
            "seat_number": row[3], "row": row[4], "column": row[5],
            "position": row[6], "compartment": row[7], "berth": row[8],
        }
        for row in rows
    ]

    cur.execute(
        """SELECT COUNT(DISTINCT sss.seat_index), MAX(sss.segment_id), COUNT(*)
             FROM seat_segment_state sss
            WHERE sss.service_run_id=%s AND sss.seat_class=%s""",
        (run, seat_class),
    )
    seat_count, nseg, cell_count = cur.fetchone()
    if not seat_count or not nseg:
        raise RuntimeError(f"run {run} has no inventory for class {seat_class}")
    cur.execute(
        """SELECT tsc.capacity, tsc.source
             FROM service_run sr
             JOIN train_seat_class tsc
               ON tsc.train_id=sr.train_id AND tsc.seat_class=%s
            WHERE sr.service_run_id=%s""",
        (seat_class, run),
    )
    capacity_row = cur.fetchone()
    if capacity_row is None or capacity_row[0] != seat_count:
        declared = capacity_row[0] if capacity_row else None
        raise RuntimeError(
            f"input capacity mismatch for {run}/{seat_class}: "
            f"declared={declared}, state seats={seat_count}"
        )
    malformed_ids = [
        item["seat_id"] for item in inventory
        if not item["seat_id"].startswith(f"{seat_class}:")
    ]
    if malformed_ids:
        raise RuntimeError(
            f"model seat IDs do not match class {seat_class}: {malformed_ids[:3]}"
        )
    if len(inventory) != seat_count:
        raise RuntimeError(
            f"physical layout mismatch for {run}/{seat_class}: "
            f"state seats={seat_count}, mapped seats={len(inventory)}"
        )
    if cell_count != seat_count * nseg:
        raise RuntimeError(
            f"incomplete seat grid for {run}/{seat_class}: "
            f"expected {seat_count * nseg} cells, got {cell_count}"
        )
    return inventory


def _physical_label(seat: dict[str, Any]) -> str:
    location = f"coach {seat['coach']} seat {seat['seat_number']}"
    if seat["compartment"] is not None:
        location += f" compartment {seat['compartment']} {seat['berth']}"
    else:
        location += f" row {seat['row']} column {seat['column']}"
    return f"{seat['seat_id']} ({location}, {seat['position']})"


def apply(conn: Any, seat_class: str, *, dry_run: bool = False) -> None:
    with conn.cursor() as cur:
        cur.execute(BACKUP_DDL)
        _assert_backup_schema(cur)
        cur.execute(
            """SELECT service_run_id, service_date, train_id, status
                 FROM service_run
                ORDER BY service_date DESC, service_run_id DESC
                LIMIT 2 FOR UPDATE"""
        )
        runs = cur.fetchall()
        if len(runs) < 2:
            raise RuntimeError("need at least two service runs in the database")

        for case, (run, date, train_id, status) in zip(("A", "B"), runs):
            if status != "ACTIVE":
                raise RuntimeError(f"run {run} is not ACTIVE (status={status})")
            _prepare_transactions(cur, run, seat_class)
            inventory = _physical_inventory(cur, run, seat_class)
            seats = [item["seat_id"] for item in inventory]

            cur.execute(
                "SELECT MAX(segment_id) FROM seat_segment_state "
                "WHERE service_run_id=%s AND seat_class=%s",
                (run, seat_class),
            )
            nseg = cur.fetchone()[0]
            free = free_cells(case, nseg, seats)

            cur.execute(
                "SELECT 1 FROM demo_case_backup "
                "WHERE service_run_id=%s AND seat_class=%s LIMIT 1",
                (run, seat_class),
            )
            if cur.fetchone() is None:
                cur.execute(
                    """INSERT INTO demo_case_backup
                       (service_run_id, seat_id, segment_id, seat_class, seat_index,
                        status, hold_id, hold_expires_at, version)
                       SELECT service_run_id, seat_id, segment_id, seat_class, seat_index,
                              status, hold_id, hold_expires_at, version
                         FROM seat_segment_state
                        WHERE service_run_id=%s AND seat_class=%s""",
                    (run, seat_class),
                )

            cur.execute(
                """UPDATE seat_segment_state
                      SET status='SOLD', hold_id=NULL, hold_expires_at=NULL,
                          version=COALESCE(version, 0) + 1
                    WHERE service_run_id=%s AND seat_class=%s""",
                (run, seat_class),
            )
            for seat_id, segments in free.items():
                cur.execute(
                    """UPDATE seat_segment_state
                          SET status='FREE', hold_id=NULL, hold_expires_at=NULL,
                              version=COALESCE(version, 0) + 1
                        WHERE service_run_id=%s AND seat_class=%s
                          AND seat_id=%s AND segment_id=ANY(%s)""",
                    (run, seat_class, seat_id, sorted(segments)),
                )
            cur.execute(
                "UPDATE service_run SET matrix_version=matrix_version+1 "
                "WHERE service_run_id=%s",
                (run,),
            )

            request_segments = (1, 1) if case == "A" else (4, 6)
            print(
                f"\nCase {case} run={run} date={date} train={train_id} "
                f"class={seat_class} segments={nseg}"
            )
            for seat_id, segments in free.items():
                physical = next(item for item in inventory if item["seat_id"] == seat_id)
                print(f"  FREE {_physical_label(physical)} -> {min(segments)}..{max(segments)}")
            print(
                "  Web request: "
                + _od(cur, run, request_segments[0], request_segments[1])
            )

    if dry_run:
        conn.rollback()
        print("\nDRY RUN complete. The transaction was rolled back; no data was changed.")
    else:
        conn.commit()
        print("\nDONE. Fare and forecast data were not changed; dynamic pricing remains enabled.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic short-trip and merged-seat demo inventory."
    )
    parser.add_argument("--seat-class", default="NGOI_MEM_DH")
    parser.add_argument(
        "--dsn", default=DEFAULT_DSN,
        help="PostgreSQL DSN; defaults to AULAC_DSN, DATABASE_URL, then local dev DB",
    )
    parser.add_argument("--connect-timeout", type=int, default=15)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="validate and execute inside a transaction, then roll everything back",
    )
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        _self_check()
        return

    try:
        import psycopg
    except ModuleNotFoundError as exc:
        print(
            "ERROR: psycopg is not installed. Use the backend virtualenv, install "
            "backend/requirements.txt, or run this script in the backend container.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    try:
        with psycopg.connect(
            args.dsn,
            connect_timeout=args.connect_timeout,
            application_name="aulac_setup_demo_cases",
        ) as conn:
            _validate_database(conn)
            apply(conn, args.seat_class, dry_run=args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

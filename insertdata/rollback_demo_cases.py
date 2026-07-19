#!/usr/bin/env python
"""Restore seat inventory captured by setup_demo_cases.py.

This restores seat status and hold references, then advances row and matrix
versions so stale clients cannot reuse an old snapshot. It does not delete
offers, booking requests, holds, or bookings created while the demo was active.
Use it only after those demo transactions have finished or been discarded.

Production VPS (run from the repository root):
    docker compose --env-file .env -f docker-compose.prod.yml run --rm \
      -v "$PWD/insertdata:/insertdata:ro" backend \
      python /insertdata/rollback_demo_cases.py --dry-run
    docker compose --env-file .env -f docker-compose.prod.yml run --rm \
      -v "$PWD/insertdata:/insertdata:ro" backend \
      python /insertdata/rollback_demo_cases.py
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


def _validate_database(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user, current_setting('server_version')")
        database, user, version = cur.fetchone()
        for table in ("service_run", "seat_segment_state", "demo_case_backup"):
            cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
            if cur.fetchone()[0] is None:
                raise RuntimeError(f"database is missing required table: {table}")
    conn.commit()
    print(f"Connected database={database} user={user} PostgreSQL={version}")


def rollback(conn: Any, *, dry_run: bool = False) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.demo_case_backup')")
        if cur.fetchone()[0] is None:
            raise RuntimeError("no demo_case_backup table; nothing to roll back")

        cur.execute(
            "SELECT DISTINCT service_run_id, seat_class "
            "FROM demo_case_backup ORDER BY service_run_id, seat_class"
        )
        targets = cur.fetchall()
        if not targets:
            raise RuntimeError("demo_case_backup is empty; nothing to roll back")

        for run, seat_class in targets:
            cur.execute(
                "SELECT service_run_id FROM service_run "
                "WHERE service_run_id=%s FOR UPDATE",
                (run,),
            )
            if cur.fetchone() is None:
                raise RuntimeError(f"service run {run} no longer exists")
            cur.execute(
                """UPDATE seat_segment_state ss
                      SET status=b.status,
                          hold_id=b.hold_id,
                          hold_expires_at=b.hold_expires_at,
                          version=GREATEST(COALESCE(ss.version, 0), COALESCE(b.version, 0)) + 1
                     FROM demo_case_backup b
                    WHERE ss.service_run_id=b.service_run_id
                      AND ss.seat_id=b.seat_id
                      AND ss.segment_id=b.segment_id
                      AND b.service_run_id=%s AND b.seat_class=%s""",
                (run, seat_class),
            )
            restored_cells = cur.rowcount
            cur.execute(
                "UPDATE service_run SET matrix_version=matrix_version+1 "
                "WHERE service_run_id=%s",
                (run,),
            )
            print(f"restored {restored_cells} cells for {run}/{seat_class}")

        cur.execute("DROP TABLE demo_case_backup")

    if dry_run:
        conn.rollback()
        print(
            f"DRY RUN complete for {len(targets)} run/class target(s). "
            "The transaction was rolled back; no data was changed."
        )
    else:
        conn.commit()
        print(f"DONE. Rolled back {len(targets)} run/class target(s).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore inventory backed up by setup_demo_cases.py."
    )
    parser.add_argument(
        "--dsn", default=DEFAULT_DSN,
        help="PostgreSQL DSN; defaults to AULAC_DSN, DATABASE_URL, then local dev DB",
    )
    parser.add_argument("--connect-timeout", type=int, default=15)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="validate and execute inside a transaction, then roll everything back",
    )
    args = parser.parse_args()

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
            application_name="aulac_rollback_demo_cases",
        ) as conn:
            _validate_database(conn)
            rollback(conn, dry_run=args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

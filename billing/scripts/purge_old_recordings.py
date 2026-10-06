#!/usr/bin/env python3
"""Delete recording files whose retention period has expired for wlabel PBX.

Can be run:
  1. Once via cron: python3 purge_old_recordings.py
  2. In dry-run mode (safe preview): python3 purge_old_recordings.py --dry-run
  3. As a persistent daemon: python3 purge_old_recordings.py --loop
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Support both psycopg (v3, used in billing venv) and psycopg2 (standard on Linux servers)
try:
    import psycopg

    def db_connect(params: dict[str, str | int]):
        return psycopg.connect(**params)
except ImportError:
    try:
        import psycopg2

        def db_connect(params: dict[str, str | int]):
            return psycopg2.connect(**params)
    except ImportError:
        print("[PURGE] FATAL: Neither 'psycopg' nor 'psycopg2' is installed.", file=sys.stderr)
        sys.exit(1)


DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "bala_billing")
DB_USER = os.getenv("DB_USER", "bill_eng1")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Bill2k26x")
RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "/opt/recordings")).resolve()

DB_PARAMS = {
    "host": DB_HOST,
    "port": DB_PORT,
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
}


def purge_once(dry_run: bool = False) -> None:
    """Find expired recordings in the cdr table and unlink their files."""
    try:
        conn = db_connect(DB_PARAMS)
    except Exception as exc:
        print(f"[PURGE] DB connection error to {DB_HOST}:{DB_PORT}/{DB_NAME}: {exc}")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT call_uuid, customer_id
                FROM cdr
                WHERE recording_days > 0
                  AND recording = TRUE
                  AND start_time < NOW() - (recording_days || ' days')::INTERVAL
            """)
            rows = cur.fetchall()

        deleted = missing = errors = 0
        for row in rows:
            call_uuid = str(row[0]).strip()
            customer_id = str(row[1]).strip()
            if not call_uuid or not customer_id:
                continue

            # Candidate paths: try exact customer_id, with 'U' prefix (wlabel standard), or stripped 'U'
            candidates = [
                RECORDINGS_DIR / customer_id / f"{call_uuid}.mp3",
            ]
            if customer_id.startswith(("U", "u")):
                candidates.append(RECORDINGS_DIR / customer_id[1:] / f"{call_uuid}.mp3")
            else:
                candidates.append(RECORDINGS_DIR / f"U{customer_id}" / f"{call_uuid}.mp3")
            candidates.append(RECORDINGS_DIR / f"{call_uuid}.mp3")

            rec_path = None
            for cand in candidates:
                cand_res = cand.resolve()
                if str(cand_res).startswith(str(RECORDINGS_DIR)) and cand_res.is_file():
                    rec_path = cand_res
                    break

            if rec_path is None:
                rec_path = candidates[0].resolve()
                if not str(rec_path).startswith(str(RECORDINGS_DIR)):
                    print(f"[PURGE] SKIP path traversal attempt: {customer_id}/{call_uuid}")
                    continue

            try:
                if rec_path.is_file():
                    if dry_run:
                        print(f"[PURGE] [DRY RUN] Would delete: {rec_path}")
                    else:
                        rec_path.unlink()
                    deleted += 1
                else:
                    if dry_run:
                        print(f"[PURGE] [NOT ON DISK] {rec_path}")
                    missing += 1
            except Exception as exc:
                action = "checking" if dry_run else "deleting"
                print(f"[PURGE] ERROR {action} {rec_path}: {exc}")
                errors += 1

        label = "would_delete" if dry_run else "deleted"
        status = "Dry run complete" if dry_run else "Complete"
        print(f"[PURGE] {status}: {label}={deleted} missing={missing} errors={errors}")
    except Exception as exc:
        print(f"[PURGE] Query error: {exc}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge expired call recordings.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the purge without deleting any files.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously, repeating every 24 hours (86400 seconds).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=86400,
        help="Interval in seconds when running in --loop mode (default: 86400).",
    )
    args = parser.parse_args()

    mode_info = " [DRY RUN MODE]" if args.dry_run else ""
    print(f"[PURGE] Starting recording purge worker{mode_info}")
    print(f"[PURGE] Target directory: {RECORDINGS_DIR}")
    print(f"[PURGE] Database: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    if not args.loop:
        purge_once(dry_run=args.dry_run)
        return

    while True:
        purge_once(dry_run=args.dry_run)
        print(f"[PURGE] Sleeping for {args.interval}s until next purge cycle...")
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("[PURGE] Interrupted by user, shutting down.")
            break


if __name__ == "__main__":
    main()

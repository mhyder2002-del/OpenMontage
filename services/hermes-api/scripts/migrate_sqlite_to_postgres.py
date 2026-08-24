#!/usr/bin/env python3
"""One-time SQLite → Postgres copy. Do not run on production unless you opt in.

Usage (local / empty target only):
  DATABASE_URL=postgresql://hermes:hermes@127.0.0.1:5432/hermes \\
    python scripts/migrate_sqlite_to_postgres.py [--sqlite PATH]

Cost note (quote, do not purchase): $0 extra on existing VPS 187.77.98.177 vs
advertised intro ~$6.49/mo new Hostinger KVM 1 (paid upfront). This script never
starts Docker and never buys a KVM.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import db  # noqa: E402

_TABLES = (
    "campaigns",
    "knowledge_nodes",
    "walking_scripts",
    "walking_storyboards",
    "walking_thumbnails",
)


def _sqlite_conn(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"SQLite file not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=None,
        help="Source SQLite path (default HERMES_DB_PATH or data/hermes.db)",
    )
    parser.add_argument(
        "--allow-prod",
        action="store_true",
        help="Required if PUBLIC_DOMAIN looks production-locked. Still does not start Docker.",
    )
    args = parser.parse_args()

    url = db.database_url()
    if not url.startswith("postgres"):
        raise SystemExit("Set DATABASE_URL to a postgresql:// URL before migrating.")

    domain = (os.environ.get("PUBLIC_DOMAIN") or "").strip().lower()
    if domain in {"hermestudios.com", "www.hermestudios.com"} and not args.allow_prod:
        raise SystemExit(
            "Refusing to migrate while PUBLIC_DOMAIN is production. "
            "This helper is local-only; do not run it on prod. Pass --allow-prod only after an explicit OK."
        )

    src_path = args.sqlite or db.sqlite_path()
    src = _sqlite_conn(src_path)
    dst = db.connect()
    try:
        db.init_schema(dst)
        copied = 0
        for table in _TABLES:
            rows = list(src.execute(f"SELECT * FROM {table}"))
            if not rows:
                continue
            cols = rows[0].keys()
            placeholders = ", ".join("?" for _ in cols)
            col_sql = ", ".join(cols)
            for row in rows:
                values = tuple(row[c] for c in cols)
                dst.execute(
                    f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders}) "
                    f"ON CONFLICT({cols[0]}) DO NOTHING",
                    values,
                )
                copied += 1
        if hasattr(dst, "commit"):
            dst.commit()
    finally:
        src.close()
        dst.close()
    print(f"Copied up to {copied} row(s) from {src_path} → Postgres (conflicts skipped).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

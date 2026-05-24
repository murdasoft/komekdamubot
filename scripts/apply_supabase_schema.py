#!/usr/bin/env python3
"""Apply Supabase SQL migrations (reads credentials from env)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "001_clients_and_sessions.sql"


def main() -> int:
    sql = MIGRATION.read_text(encoding="utf-8")
    db_url = (
        os.getenv("komek_POSTGRES_URL_NON_POOLING")
        or os.getenv("DATABASE_URL")
        or os.getenv("SUPABASE_DB_URL")
    )
    if not db_url:
        print("Set komek_POSTGRES_URL_NON_POOLING or DATABASE_URL", file=sys.stderr)
        return 1

    try:
        import psycopg2
    except ImportError:
        print("Install: pip install psycopg2-binary", file=sys.stderr)
        return 1

    print(f"Applying migration: {MIGRATION.name}")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    cur.close()
    conn.close()
    print("OK: schema applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

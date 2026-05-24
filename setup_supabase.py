#!/usr/bin/env python3
"""Verify Supabase connection and tables."""

from app.supabase_client import get_supabase, is_supabase_configured


def main() -> None:
    if not is_supabase_configured():
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        return
    sb = get_supabase()
    if not sb:
        print("Supabase client failed")
        return
    for table in ("clients", "sessions", "messages", "leads"):
        try:
            r = sb.table(table).select("*", count="exact").limit(1).execute()
            n = len(r.data or [])
            print(f"OK {table}: sample_rows={n}")
        except Exception as e:
            print(f"FAIL {table}: {e}")
    print("Run scripts/apply_supabase_schema.py if tables are missing.")


if __name__ == "__main__":
    main()

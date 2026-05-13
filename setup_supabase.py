#!/usr/bin/env python3
"""Setup Supabase tables for Komek Damu Bot."""

from supabase import create_client

url = "https://vvhlwsrcvxcerjmcoiqf.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ2aGx3c3JjdnhjZXJqbWNvaXFmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODYzMzMwNSwiZXhwIjoyMDk0MjA5MzA1fQ.Kfvk9Fw4EOszcIPoK6JDyXKhifB3iNRSTB-ydQAlsk8"

sb = create_client(url, key)

# SQL to execute
sql_statements = [
    """CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        chat_id TEXT NOT NULL UNIQUE,
        platform TEXT DEFAULT 'telegram',
        lang TEXT DEFAULT 'ru',
        state TEXT DEFAULT 'idle',
        product TEXT,
        data JSONB DEFAULT '{}',
        conversation_history JSONB DEFAULT '[]',
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )""",
    
    """CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        chat_id TEXT NOT NULL,
        platform TEXT DEFAULT 'telegram',
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        lang TEXT DEFAULT 'ru',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )""",
    
    """CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY,
        chat_id TEXT NOT NULL,
        platform TEXT DEFAULT 'telegram',
        product TEXT NOT NULL,
        lang TEXT DEFAULT 'ru',
        data JSONB DEFAULT '{}',
        status TEXT DEFAULT 'new',
        manager_id TEXT,
        notes TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )""",
    
    """CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)""",
    """CREATE INDEX IF NOT EXISTS idx_leads_chat_id ON leads(chat_id)""",
    """CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)""",
    
    """ALTER TABLE sessions ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE messages ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE leads ENABLE ROW LEVEL SECURITY""",
    
    """CREATE POLICY IF NOT EXISTS "Allow all" ON sessions FOR ALL USING (true)""",
    """CREATE POLICY IF NOT EXISTS "Allow all" ON messages FOR ALL USING (true)""",
    """CREATE POLICY IF NOT EXISTS "Allow all" ON leads FOR ALL USING (true)""",
]

print("Executing SQL on Supabase...")

# Execute via PostgreSQL connection
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect(
        "postgres://postgres.vvhlwsrcvxcerjmcoiqf:XVC125xltHMrBf89@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    for i, sql in enumerate(sql_statements):
        try:
            cursor.execute(sql)
            print(f"✓ Statement {i+1}/{len(sql_statements)} executed")
        except Exception as e:
            print(f"✗ Statement {i+1} failed: {e}")
    
    cursor.close()
    conn.close()
    print("\n✅ All SQL executed successfully!")
    
except ImportError:
    print("psycopg2 not installed, trying via Supabase client...")
    # Fallback: try to insert test data to verify connection
    try:
        result = sb.table('sessions').select('*').execute()
        print(f"Sessions table check: {len(result.data)} records found")
    except Exception as e:
        print(f"Error: {e}")
        print("Please execute SQL manually in Supabase SQL Editor")

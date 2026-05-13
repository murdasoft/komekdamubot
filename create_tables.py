import psycopg2

url = "postgres://postgres.vvhlwsrcvxcerjmcoiqf:XVC125xltHMrBf89@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"

sql = """CREATE TABLE IF NOT EXISTS sessions (
    chat_id TEXT PRIMARY KEY,
    platform TEXT DEFAULT 'telegram',
    lang TEXT DEFAULT 'ru',
    state TEXT DEFAULT 'idle',
    product TEXT,
    data JSONB DEFAULT '{}',
    conversation_history JSONB DEFAULT '[]',
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    chat_id TEXT,
    platform TEXT,
    role TEXT,
    text TEXT,
    lang TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);"""

conn = psycopg2.connect(url)
cursor = conn.cursor()
cursor.execute(sql)
conn.commit()
cursor.close()
conn.close()
print("Tables created successfully")

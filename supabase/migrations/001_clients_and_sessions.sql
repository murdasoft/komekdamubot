-- KOMEK DAMU: clients CRM + extended sessions
-- Run once in Supabase SQL Editor or via scripts/apply_supabase_schema.py

-- Clients (профиль клиента, язык, город, контекст)
CREATE TABLE IF NOT EXISTS clients (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL UNIQUE,
    platform TEXT NOT NULL DEFAULT 'whatsapp',
    contact_name TEXT,
    phone TEXT,
    city TEXT,
    lang TEXT NOT NULL DEFAULT 'kk',
    lang_locked BOOLEAN NOT NULL DEFAULT FALSE,
    last_product TEXT,
    last_state TEXT DEFAULT 'idle',
    context_topic TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sessions (runtime + полный контекст диалога)
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL UNIQUE,
    platform TEXT DEFAULT 'whatsapp',
    lang TEXT DEFAULT 'kk',
    lang_locked BOOLEAN DEFAULT FALSE,
    state TEXT DEFAULT 'idle',
    product TEXT,
    contact_name TEXT,
    city TEXT,
    context_topic TEXT,
    flow_step TEXT,
    handoff_until DOUBLE PRECISION DEFAULT 0,
    submenu TEXT,
    data JSONB DEFAULT '{}',
    conversation_history JSONB DEFAULT '[]',
    session_json JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Добавить колонки, если sessions уже существовала
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS lang_locked BOOLEAN DEFAULT FALSE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS contact_name TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS city TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS context_topic TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS flow_step TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS handoff_until DOUBLE PRECISION DEFAULT 0;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS submenu TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS session_json JSONB DEFAULT '{}';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS city_confirmed BOOLEAN DEFAULT FALSE;

ALTER TABLE sessions ALTER COLUMN lang SET DEFAULT 'kk';

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    platform TEXT DEFAULT 'whatsapp',
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    lang TEXT DEFAULT 'kk',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leads (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    platform TEXT DEFAULT 'whatsapp',
    product TEXT NOT NULL,
    lang TEXT DEFAULT 'kk',
    data JSONB DEFAULT '{}',
    status TEXT DEFAULT 'new',
    manager_id TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clients_chat_id ON clients(chat_id);
CREATE INDEX IF NOT EXISTS idx_clients_last_seen ON clients(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_clients_city ON clients(city);
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_leads_chat_id ON leads(chat_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);

ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'clients' AND policyname = 'service_role_all_clients'
    ) THEN
        CREATE POLICY service_role_all_clients ON clients FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'sessions' AND policyname = 'service_role_all_sessions'
    ) THEN
        CREATE POLICY service_role_all_sessions ON sessions FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'messages' AND policyname = 'service_role_all_messages'
    ) THEN
        CREATE POLICY service_role_all_messages ON messages FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'leads' AND policyname = 'service_role_all_leads'
    ) THEN
        CREATE POLICY service_role_all_leads ON leads FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;

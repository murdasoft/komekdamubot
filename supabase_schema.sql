-- Supabase Schema for Komek Damu Bot
-- Run this in Supabase SQL Editor

-- Sessions table (stores user sessions)
CREATE TABLE IF NOT EXISTS sessions (
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
);

-- Messages table (conversation logs)
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    platform TEXT DEFAULT 'telegram',
    role TEXT NOT NULL, -- 'user' or 'assistant'
    text TEXT NOT NULL,
    lang TEXT DEFAULT 'ru',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Leads table (collected leads)
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    platform TEXT DEFAULT 'telegram',
    product TEXT NOT NULL,
    lang TEXT DEFAULT 'ru',
    data JSONB DEFAULT '{}',
    status TEXT DEFAULT 'new', -- new, contacted, converted, closed
    manager_id TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Analytics table (daily stats)
CREATE TABLE IF NOT EXISTS analytics (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE DEFAULT CURRENT_DATE,
    total_messages INTEGER DEFAULT 0,
    total_leads INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    ai_responses INTEGER DEFAULT 0,
    operator_handoffs INTEGER DEFAULT 0
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_leads_chat_id ON leads(chat_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);

-- Enable Row Level Security (RLS)
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics ENABLE ROW LEVEL SECURITY;

-- Create policies (allow all for service role)
CREATE POLICY "Allow all" ON sessions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON messages FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON leads FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON analytics FOR ALL USING (true) WITH CHECK (true);

-- Function to update analytics
CREATE OR REPLACE FUNCTION update_analytics_message()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO analytics (date, total_messages)
    VALUES (CURRENT_DATE, 1)
    ON CONFLICT (date)
    DO UPDATE SET total_messages = analytics.total_messages + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_analytics_message
AFTER INSERT ON messages
FOR EACH ROW
EXECUTE FUNCTION update_analytics_message();

-- Function to update analytics for leads
CREATE OR REPLACE FUNCTION update_analytics_lead()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO analytics (date, total_leads)
    VALUES (CURRENT_DATE, 1)
    ON CONFLICT (date)
    DO UPDATE SET total_leads = analytics.total_leads + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_analytics_lead
AFTER INSERT ON leads
FOR EACH ROW
EXECUTE FUNCTION update_analytics_lead();

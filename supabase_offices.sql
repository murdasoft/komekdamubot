-- Offices for KOMEK DAMU Bot (run in Supabase SQL Editor)

CREATE TABLE IF NOT EXISTS offices (
    city_key TEXT PRIMARY KEY,
    city_name_ru TEXT NOT NULL,
    city_name_kk TEXT NOT NULL,
    text_ru TEXT NOT NULL,
    text_kk TEXT NOT NULL,
    phone TEXT,
    whatsapp TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE offices ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all offices" ON offices FOR ALL USING (true) WITH CHECK (true);

INSERT INTO offices (city_key, city_name_ru, city_name_kk, text_ru, text_kk, phone, whatsapp) VALUES
('almaty', 'Алматы', 'Алматы',
 'Алматы, ул. Муратбаева 134, каб. 311',
 'Алматы, Муратбаева 134, 311 каб',
 '8 707 339 10 39', '7 707 339 10 39'),
('astana', 'Астана', 'Астана',
 'Астана, ул. Сыганак 47, каб. 433',
 'Астана, Сығанақ 47, 433 каб',
 '8 702 187 97 26', '7 702 187 97 26'),
('shymkent', 'Шымкент', 'Шымкент',
 'Шымкент, ул. Мадели Кожа 45, каб. 7',
 'Шымкент, Мадели Кожа 45, 7 каб',
 '8 705 810 28 81', '7 705 810 28 81'),
('atyrau', 'Атырау', 'Атырау',
 'Атырау, ул. Досмухамедова 139а, каб. 9',
 'Атырау, Досмухамедова 139а, 9 каб',
 '8 706 686 83 00', '7 706 686 83 00'),
('aktau', 'Актау', 'Ақтау',
 'Актау',
 'Ақтау',
 '8 705 112 99 22', '7 705 112 99 22')
ON CONFLICT (city_key) DO UPDATE SET
  text_ru = EXCLUDED.text_ru,
  text_kk = EXCLUDED.text_kk,
  phone = EXCLUDED.phone,
  whatsapp = EXCLUDED.whatsapp,
  updated_at = NOW();

-- Format full text for bot (optional denormalized)
UPDATE offices SET
  text_ru = '📍 ' || text_ru || E'\n📞 ' || phone || ' | WhatsApp: ' || whatsapp,
  text_kk = '📍 ' || text_kk || E'\n📞 ' || phone || ' | WhatsApp: ' || whatsapp;

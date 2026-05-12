# KOMEK DAMU Bot

AI-чат-бот для финансовой компании KOMEK DAMU. Поддерживает кредиты, ипотеку, программу DAMU 12,6%, рефинансирование.

**Каналы:** Telegram + WhatsApp (Green API)  
**Языки:** Русский + Казахский  
**AI:** Groq API (LLaMA 3.1 + Whisper для голосовых)

## Возможности

- 🤖 AI-понимание свободного текста
- 🎤 Транскрибация голосовых сообщений (ru + kk)
- 💬 Сценарии для 6 продуктов:
  - Кредит для физлиц
  - Кредит для бизнеса
  - DAMU 12,6%
  - Ипотека (госпрограмма + обычная)
  - Рефинансирование
  - Сложные случаи
- 📊 Интеграция с Bitrix24
- 🔔 Уведомления менеджеру в Telegram
- 👨‍💼 Handoff к оператору

## Быстрый старт

### 1. Локальный запуск

```bash
# Клонировать репозиторий
cd komek-damu-bot

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt

# Запуск (Groq API уже настроен в .env)
uvicorn app.main:app --reload --port 8000
```

### 2. Проверка работы

Открой в браузере: http://localhost:8000/

Должно показать:
```json
{
  "status": "ok",
  "telegram_configured": false,
  "whatsapp_configured": false,
  "groq_configured": true
}
```

## Настройка Telegram

1. Напиши @BotFather → `/newbot`
2. Скопируй токен в `.env`:
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
WEBHOOK_BASE_URL=https://your-project.vercel.app
```

3. Деплой на Vercel или ngrok для локального теста:
```bash
ngrok http 8000
# Используй https URL в WEBHOOK_BASE_URL
```

## Настройка WhatsApp (Green API)

1. Зарегистрируйся: https://green-api.com/
2. Создай инстанс, получи:
   - `idInstance`
   - `apiTokenInstance`
3. Добавь в `.env`:
```
GREEN_API_INSTANCE_ID=your_instance_id
GREEN_API_TOKEN=your_token
```

## Настройка Bitrix24

1. В Bitrix24 создай входящий вебхук
2. URL добавь в `.env`:
```
BITRIX24_WEBHOOK_URL=https://your-domain.bitrix24.ru/rest/xx/xxxxxx/
```

## Деплой на Vercel

```bash
# Установи Vercel CLI
npm i -g vercel

# Деплой
vercel

# Установи переменные окружения
vercel env add GROQ_API_KEY
vercel env add TELEGRAM_BOT_TOKEN
vercel env add WEBHOOK_BASE_URL

# Передеплой
vercel --prod
```

## Структура проекта

```
komek-damu-bot/
├── api/
│   └── index.py              # Vercel entry point
├── app/
│   ├── __init__.py
│   ├── config.py             # Настройки из env
│   ├── main.py               # FastAPI + webhooks
│   ├── telegram_api.py         # Telegram Bot API
│   ├── green_api.py            # WhatsApp Green API
│   ├── groq_client.py          # Groq AI (LLM + STT)
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py       # Главная логика
│   │   ├── content.py        # Тексты (ru + kk)
│   │   ├── flows.py          # Сценарии заявок
│   │   └── knowledge_base.py  # База знаний
│   ├── storage/
│   │   ├── __init__.py
│   │   └── db.py             # Хранилище сессий
│   └── ai/
│       └── (не используется — всё через Groq)
├── .env                      # Локальные секреты
├── .env.example              # Шаблон
├── requirements.txt
├── vercel.json
└── README.md
```

## API Endpoints

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/` | GET | Health check |
| `/health` | GET | Проверка здоровья |
| `/webhook/telegram` | POST | Вебхук Telegram |
| `/webhook/whatsapp` | POST | Вебхук Green API |
| `/setup` | GET | Ручная установка вебхуков |
| `/debug/session/{id}` | GET | Просмотр сессии |

## Groq API

Уже подключен твой ключ:
- **LLM:** `llama3-70b-8192` — быстрый ответ, до 8192 токенов
- **STT:** `whisper-large-v3` — транскрибация голосовых

Бесплатный лимит: до 20 запросов/мин, 1,500,000 токенов/день.

## Документация Groq

- **Console:** https://console.groq.com/
- **Models:** https://console.groq.com/docs/models
- **STT:** https://console.groq.com/docs/speech-to-text

## Лицензия

MIT License — используй свободно для коммерческих проектов.

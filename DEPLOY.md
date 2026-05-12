# Деплой на Vercel (clean-bot-omega.vercel.app)

## Способ 1: Git push (рекомендуется)

```bash
cd /Users/aleksandr/Project/komek-damu-bot

# Добавить remote (если есть доступ)
git remote add origin https://github.com/murdasoft/clean-bot.git

# Форс-пуш в main (заменит код)
git push -f origin main

# Vercel автоматически задеплоит
```

## Способ 2: Vercel Dashboard

1. Зайди: https://vercel.com/murdasoft-9183/clean-bot
2. → **Settings** → **Git**
3. Переключи на новый репозиторий или загрузи zip

## Способ 3: Vercel CLI

```bash
npm i -g vercel

# Логин
vercel login

# Линк к существующему проекту
vercel link
# ? Link to existing project? [y/N] y
# ? What's your project name? [clean-bot]

# Деплой
vercel --prod
```

## Настройка Environment Variables

После деплоя, зайди:
https://vercel.com/murdasoft-9183/clean-bot/settings/environment-variables

Добавь эти переменные:

| Variable | Value |
|----------|-------|
| `GROQ_API_KEY` | `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` |
| `TELEGRAM_BOT_TOKEN` | `8747075596:AAEu-Ni-ZzcVGflZW0E9Lm2bv8nf8llezR8` |
| `TELEGRAM_WEBHOOK_SECRET` | `vcp_7iU3jVDFxx9mmSQKph0Ic58Y2qaM6h51owoUmnxBtcFMcMCIMb3Q2hYT` |
| `WEBHOOK_BASE_URL` | `https://clean-bot-omega.vercel.app` |

## Установка Webhook (после деплоя)

```bash
curl https://clean-bot-omega.vercel.app/setup

# Или в браузере открой:
# https://clean-bot-omega.vercel.app/setup
```

## Проверка работы

1. Открой: https://clean-bot-omega.vercel.app/
2. Должно показать:
   ```json
   {
     "status": "ok",
     "telegram_configured": true,
     "whatsapp_configured": false,
     "groq_configured": true
   }
   ```

3. Напиши боту в Telegram: https://t.me/komekdamubot (или как назовешь)

## Структура проекта

```
komek-damu-bot/
├── api/index.py           # Vercel entry point
├── app/
│   ├── main.py            # FastAPI + webhooks
│   ├── telegram_api.py    # Telegram Bot API
│   ├── groq_client.py     # Groq AI (LLM + STT)
│   ├── bot/
│   │   ├── handlers.py    # Главная логика
│   │   ├── content.py     # Тексты ru/kk
│   │   ├── flows.py       # Сценарии
│   │   └── knowledge_base.py  # Продукты
│   └── storage/db.py      # Сессии
├── requirements.txt
└── vercel.json
```

## Если деплой не работает

1. Проверь логи: https://vercel.com/murdasoft-9183/clean-bot/logs
2. Проверь env vars установлены
3. Проверь `/setup` вызвался и webhook установлен

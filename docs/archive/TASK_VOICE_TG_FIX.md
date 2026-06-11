# ТЗ: Исправление голосовых сообщений в Telegram (komek-damu-bot)

## Проблема
Голосовые сообщения в Telegram боте (komek-damu-bot) **не обрабатываются** — бот пишет "🎤 Дауыстық хабарламаны тыңдап жатырмын..." и замолкает, не давая ответ.

Работает: WhatsApp голосовые — работают нормально.
Не работает: Telegram голосовые — зависают.

## История: что уже исправлено

1. ✅ Убрано 16 параллельных HTTP-запросов в STT — сделано 3 максимум
2. ✅ Все таймауты снижены до 30 секунд
3. ✅ Убран `city_confirmed` из прямых колонок upsert — он не существовал в БД, вызывал ошибку
4. ✅ Telegram хендлер обёрнут в try/except с fallback
5. ❌ **Голосовые ВСЁ ЕЩЁ НЕ РАБОТАЮТ**

## Текущее состояние кода (где искать)

### Основной файл
`/Users/aleksandr/Project/bots-for-business/komek-damu-bot/app/bot/handlers.py`

Обработчик: `_handle_telegram_update_inner()` (строки ~906+)
Голосовые обрабатываются в блоке `if is_voice_message(body)` (строки ~992)

### Voice STT модуль
`/Users/aleksandr/Project/bots-for-business/komek-damu-bot/app/bot/voice_stt.py`
Функция `transcribe_voice_message()` — максимум 3 запроса к Groq

### Groq клиент
`/Users/aleksandr/Project/bots-for-business/komek-damu-bot/app/groq_client.py`
Метод `transcribe()` — timeout 30 секунд

### Supabase клиент
`/Users/aleksandr/Project/bots-for-business/komek-damu-bot/app/supabase_client.py`
`save_session()`, `upsert_client()`

### Тестовые аудио
`/Users/aleksandr/Project/bots-for-business/audio/`
- `audio_2026-05-27_10-50-13.ogg`
- `audio_2026-05-27_11-10-34.ogg`
- `audio_2026-05-27_11-10-53.ogg`
- `audio_2026-05-27_11-30-44.ogg`
- `audio_2026-05-27_11-31-01.ogg`

## Диагностика: что нужно выяснить

### Гипотеза 1: Groq STT падает с ошибкой
Проверить: прогнать тестовые аудио через `groq_client.transcribe()` локально.

```python
# Тестовый скрипт
import asyncio
from app.groq_client import GroqClient

async def test():
    client = GroqClient(os.environ["GROQ_API_KEY"])
    with open("/Users/aleksandr/Project/bots-for-business/audio/audio_2026-05-27_11-10-34.ogg", "rb") as f:
        audio = f.read()
    text, err = await client.transcribe(audio, filename="voice.ogg")
    print(f"text={text}, err={err}")

asyncio.run(test())
```

Если text=None и err есть → проблема в Groq API (rate limit, 429, etc).

### Гипотеза 2: Сессия не сохраняется, бот теряет состояние
Проверить логи Vercel на `save_session` errors.

Если `save_session` возвращает `False` → сессия не сохраняется → при следующем хуке загружается пустая → бот "забывает" что слушал голосовое.

### Гипотеза 3: Telegram хендлер падает молча
Возможно, исключение внутри `try/except` не логируется или обработка голосового идёт по пути где нет `return` и код проваливается дальше.

## Требования к исправлению

### 1. Добавить детальное логирование в обработчик голосовых
В `handlers.py` в блоке обработки голосового, на КАЖДОМ шаге:
- "Voice: got file_id={file_id}"
- "Voice: downloaded {len} bytes"
- "Voice: STT started"
- "Voice: STT result={transcribed[:50]}"
- "Voice: sending response"
- "Voice: ERROR {exception}"

### 2. Проверить работоспособность Groq STT локально
Запустить тестовый скрипт с тестовыми аудио. Убедиться что:
- Groq отвечает без rate limit
- Транскрипция возвращает текст
- Нет ошибок сети/таймаутов

### 3. Убедиться что сессия сохраняется ПОСЛЕ голосового
После `await save_session(chat_id, session)` должен быть лог успеха.

### 4. Универсальный fallback — бот НЕ молчит
Если ГЛЮБАЯ ошибка в голосовом — бот должен ответить:
- "Не удалось распознать голосовое. Попробуйте текстом или отправьте ещё раз."

### 5. Вернуть показ распознанного текста
Как было раньше (14 мая): "🖊 Распознано: ..."

## Критерии приёмки

- [ ] Голосовое 2-3 секунды на казахском → бот отвечает за 5-10 секунд
- [ ] Голосовое 2-3 секунды на русском → бот отвечает за 5-10 секунд
- [ ] Бот показывает "Распознано: ..." перед ответом
- [ ] При ошибке STT — бот пишет понятное сообщение об ошибке, не молчит
- [ ] После голосового сессия сохраняется (язык, город не сбрасываются)

## Доступы

### Vercel
Token: из `~/.vercel/auth.json` или `vercel login`

### Supabase
URL: из ENV `SUPABASE_URL`
Key: из ENV `SUPABASE_SERVICE_ROLE_KEY`

### Telegram Bot Token
из `.env` → `TELEGRAM_BOT_TOKEN`

### Groq API Key
из `.env` → `GROQ_API_KEY`

## Запуск теста

```bash
cd /Users/aleksandr/Project/bots-for-business/komek-damu-bot
python3 -c "
import asyncio
from app.groq_client import GroqClient

async def test():
    client = GroqClient(os.environ['GROQ_API_KEY'])
    with open('/Users/aleksandr/Project/bots-for-business/audio/audio_2026-05-27_11-10-34.ogg', 'rb') as f:
        audio = f.read()
    text, err = await client.transcribe(audio)
    print(f'text={text}')
    print(f'err={err}')

asyncio.run(test())
"
```

## Деплой после фикса

```bash
git add -A && git commit -m "fix: voice messages in Telegram" && git push
```

Vercel автодеплой: https://komek-damu-bot.vercel.app

## Контекст

- Бот: komek-damu-bot
- Платформа: Telegram + WhatsApp
- AI: Groq (LLaMA 3.3 70B + Whisper)
- Хостинг: Vercel serverless (60 сек лимит)
- БД: Supabase (PostgreSQL + PostgREST)

---

**Создано:** 27.05.2026
**Приоритет:** P0 (блокирует использование)

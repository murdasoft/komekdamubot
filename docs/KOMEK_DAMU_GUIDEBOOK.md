# KOMEK DAMU Bot — Полный гайдбук

**Версия:** 2026-06-15  
**Проект:** [murdasoft/komekdamubot](https://github.com/murdasoft/komekdamubot)  
**Production:** https://komek-damu-bot.vercel.app  
**Языки:** қазақша (по умолчанию) + русский  

Этот документ — операционный и технический справочник для разработчиков, владельца продукта и поддержки. Охватывает архитектуру, все пользовательские сценарии, события webhook, голосовой пайплайн, выбор моделей, известные баги и пошаговые решения.

---

## Содержание

1. [Введение и цели бота](#1-введение-и-цели-бота)
2. [Архитектура системы](#2-архитектура-системы)
3. [Карта событий (все входящие сообщения)](#3-карта-событий-все-входящие-сообщения)
4. [Пользовательские сценарии (wizard → меню → заявка)](#4-пользовательские-сценарии)
5. [Telegram: webhook и обработка](#5-telegram-webhook-и-обработка)
6. [WhatsApp (Green API)](#6-whatsapp-green-api)
7. [Голосовые сообщения (STT)](#7-голосовые-сообщения-stt)
8. [Языковая политика kk / ru](#8-языковая-политика-kk--ru)
9. [AI, FAQ и гибридный ответ](#9-ai-faq-и-гибридный-ответ)
10. [Матрица моделей: что когда использовать](#10-матрица-моделей-что-когда-использовать)
11. [База знаний и продукты](#11-база-знаний-и-продукты)
12. [Сессии, Supabase, лиды](#12-сессии-supabase-лиды)
13. [Казахские корпуса и Vercel Blob](#13-казахские-корпуса-и-vercel-blob)
14. [Деплой и окружения](#14-деплой-и-окружения)
15. [Мониторинг голоса (voice debug)](#15-мониторинг-голоса-voice-debug)
16. [Энциклопедия багов и решений](#16-энциклопедия-багов-и-решений)
17. [Troubleshooting: чеклисты](#17-troubleshooting-чеклисты)
18. [Тестирование](#18-тестирование)
19. [Безопасность и секреты](#19-безопасность-и-секреты)
20. [Как двигаться дальше (roadmap)](#20-как-двигаться-дальше-roadmap)
21. [Приложения](#21-приложения)

---

## 1. Введение и цели бота

### 1.1 Что делает бот

**KOMEK DAMU** — чат-бот микрофинансовой организации для Казахстана. Он:

- консультирует по кредитам (ИП, ТОО, физлицо, ипотека, DAMU 12,6%, рефинанс);
- ведёт пользователя по wizard (язык → город → меню);
- принимает **текст и голос** на казахском и русском;
- собирает заявки (лиды) и передаёт менеджеру;
- работает в **Telegram** и **WhatsApp**.

### 1.2 Принципы UX (не нарушать)

| Принцип | Реализация |
|---------|------------|
| Казахский — основной | `DEFAULT_LANG = kk` |
| Не показывать транскрипт голоса клиенту | Только внутренний STT + debug-отчёт |
| Не писать «меню» (путают с рестораном) | «разделы» / «бөлімдер» |
| Ипотека — только через офис | Жёстко в промптах и FAQ |
| Телефоны — plain text | Без `tel:` в WhatsApp |
| Голос ≈ текст | Одинаковая маршрутизация после STT |

### 1.3 Кто читает этот гайд

- **Разработчик** — деплой, баги, STT, env.
- **Владелец / менеджер** — сценарии, handoff, мониторинг голоса.
- **Новый человек в команде** — быстрый вход без чтения 2400 строк `handlers.py`.

---

## 2. Архитектура системы

### 2.1 Стек

```
Клиент (TG / WA)
       │
       ▼
Vercel Serverless (Python 3.12, max 60s)
  api/index.py → Mangum → FastAPI (app/main.py)
       │
       ├── handlers.py      ← главный оркестратор
       ├── voice_stt.py     ← распознавание речи
       ├── voice_router.py  ← голос → цифра меню / FAQ
       ├── ai_agent.py      ← LLM с базой знаний
       ├── faq_matcher.py   ← быстрые ответы без LLM
       └── supabase_client  ← сессии, лиды
       │
       ├── Together API     (чат + Whisper STT)
       ├── Groq API         (чат + Whisper STT)
       ├── HuggingFace      (казахский Whisper)
       ├── Supabase         (PostgreSQL)
       └── Vercel Blob      (корпуса kk)
```

### 2.2 Ключевые файлы

| Файл | Назначение |
|------|------------|
| `app/bot/handlers.py` | Вся логика TG/WA (~2400 строк) |
| `app/bot/voice_stt.py` | Ensemble STT |
| `app/bot/voice_router.py` | Маршрутизация после STT |
| `app/bot/lang_policy.py` | Правила kk/ru |
| `app/bot/lang_detect.py` | Детекция языка по тексту |
| `app/bot/hybrid_flow.py` | AI во время wizard |
| `app/bot/flows.py` | Многошаговые заявки |
| `app/bot/knowledge_base.py` | Продукты, FAQ, intent |
| `app/config.py` | Все env → Settings |
| `vercel.json` | `maxDuration: 60` |
| `.env.example` | Шаблон переменных |

### 2.3 Состояние сессии

Поля в памяти + Supabase (`sessions.session_json`):

| Поле | Значения | Смысл |
|------|----------|-------|
| `state` | `idle`, `selecting_lang`, `selecting_city`, `in_flow`, `handoff` | Этап диалога |
| `lang` | `kk`, `ru` | Язык ответов |
| `lang_locked` | bool | Язык зафиксирован после выбора |
| `city` | `almaty`, `astana`, … | Город |
| `city_confirmed` | bool | Город выбран |
| `product` | ключ продукта | Текущий продукт |
| `flow_step` | имя шага | Wizard заявки |
| `data` | dict | Собранные поля заявки |
| `handoff_until` | timestamp | До когда бот молчит (менеджер) |
| `from_voice` | bool | Последний ввод — голос |
| `last_voice_raw` | str | Сырой STT |
| `conversation_history` | list | Последние 10 реплик |

**Важно:** без Supabase сессия теряется при cold start Vercel.

---

## 3. Карта событий (все входящие сообщения)

### 3.1 Telegram — типы update

| Событие | Условие | Действие |
|---------|---------|----------|
| **Webhook POST** | `/webhook/telegram` | `handle_telegram_update` |
| **Secret token** | `X-Telegram-Bot-Api-Secret-Token` | 403 если неверный |
| **Rate limit** | >20/мин или >100/час | 200, без ответа |
| **callback_query** | Inline-кнопка | `handle_nav_callback` |
| **voice / audio** | `message.voice` | STT → текст → общий пайплайн |
| **photo / document** | без текста | Подсказка «напишите цифру» |
| **text** | обычное сообщение | Полный handler |
| **/start, /menu, список** | триггеры | Сброс → выбор языка |
| **99** | в любом месте | Шаг языка |
| **98** | в любом месте | Шаг города |
| **0** | в любом месте | Назад / главное меню |
| **/reply** | только из `TELEGRAM_ALERT_CHAT_ID` | Прокси ответа пользователю |

### 3.2 WhatsApp — типы webhook

| typeWebhook | Обработка |
|-------------|-----------|
| `incomingMessageReceived` | Основной |
| `incomingMessageText` | Текст |
| `incomingMessageVoice` | Голос |
| Статусы доставки | 200 OK, игнор |

### 3.3 Внутренние события (побочные эффекты)

| Событие | Триггер | Результат |
|---------|---------|-----------|
| `save_session` | После каждого ответа | Upsert в Supabase |
| `log_message` | Реплики user/bot | Таблица `messages` |
| `create_lead` | Завершение flow | Таблица `leads` |
| `_notify_manager` | handoff, заявка | TG в `TELEGRAM_ALERT_CHAT_ID` |
| `_send_to_bitrix24` | Завершение flow | POST на webhook CRM |
| `voice_debug.flush` | Конец обработки голоса (TG) | Отчёт оператору |

---

## 4. Пользовательские сценарии

### 4.1 Wizard (новый пользователь)

```
/start или первое сообщение
    → selecting_lang (1=KK, 2=RU или свободный текст)
    → selecting_city (1–4 или название города)
    → idle + главное меню 1–7
```

**Города:** 1 Алматы, 2 Астана, 3 Шымкент, 4 Ақтау/Актау.

### 4.2 Главное меню

| Цифра | Продукт | Дальше |
|-------|---------|--------|
| 1 | ИП / ЖК | Инфо или flow |
| 2 | ТОО | Инфо или flow |
| 3 | Физлицо | Инфо или flow |
| 4 | Ипотека | Подменю (гос / обычная) |
| 5 | DAMU 12,6% | Инфо + flow |
| 6 | Рефинанс | Инфо + flow |
| 7 | Менеджер | **handoff** |

### 4.3 Свободный текст (idle)

Порядок обработки:

1. Явная смена языка (`русский`, `қазақша`, 1/2)
2. Навигация 0 / 98 / 99
3. Цифра меню 1–7
4. «Хочу кредит» без продукта → FAQ/AI + меню выбора
5. Калькулятор (сумма + срок)
6. FAQ matcher (мгновенно)
7. Hybrid AI agent (LLM + KB)
8. FAQ guide (короткий уточняющий вопрос)
9. Universal fallback

### 4.4 Handoff (менеджер)

- Триггеры: `7`, «менеджер», «оператор», запрос телефона на шаге города.
- `state = handoff`, `handoff_until = now + 24h` (настраивается).
- Бот молчит до слова `бот` / `bot` или истечения таймаута.
- Уведомление менеджеру с chat_id и `/reply CHAT_ID текст`.

### 4.5 Расписание (опционально)

`BOT_SCHEDULE_ENABLED=true` → в будни 09:00–18:00 (Asia/Almaty) бот **не отвечает** (работает менеджер).

В `.env.example` по умолчанию `false` — проверьте прод.

---

## 5. Telegram: webhook и обработка

### 5.1 Регистрация webhook

На Vercel **lifespan отключён** (`Mangum lifespan="off"`), поэтому после каждого деплоя:

```bash
curl https://komek-damu-bot.vercel.app/setup
```

Или `scripts/deploy-vercel.sh` (нужен `VERCEL_TOKEN`).

### 5.2 Индикатор «слушаю»

Вместо текста «🎤 Дауыстық хабарламаны тыңдап жатырмын…» используется:

```python
send_chat_action(chat_id, "record_voice")  # kk
send_chat_action(chat_id, "upload_voice")  # ru
```

### 5.3 Голос в Telegram

```
voice message
  → download file (httpx, 20s)
  → warmup kk_stt_vocab (parallel)
  → transcribe_voice_message (55s timeout)
  → resolve_voice_lang
  → prepare_voice_input (router)
  → обработка как text
```

Ошибки пользователю:

- Пустой STT: «Естіген жоқпын…» / «Не расслышал…»
- Timeout: «Дауыстықты уақытында тану мүмкін болмады…»
- Exception: «Дауыстықты тану мүмкін болмады…»

---

## 6. WhatsApp (Green API)

### 6.1 Настройка

| Переменная | Описание |
|------------|----------|
| `GREEN_API_INSTANCE_ID` | ID инстанса |
| `GREEN_API_TOKEN` | API token |
| `GREEN_API_URL` | Регион API (7107, …) |
| `GREEN_API_WEBHOOK_TOKEN` | Bearer для входящих |

Webhook URL: `{WEBHOOK_BASE_URL}/webhook/whatsapp`

### 6.2 Отличия от Telegram

- Нет inline-кнопок — только **цифры** в тексте.
- Подсказки `0` / `98` / `99` добавляются в каждый ответ (`add_wa_back_hint`).
- Markdown упрощается (`clean_whatsapp_text`).
- Голос: ранний `try_dispatch_voice_menu` до полного пайплайна.

### 6.3 Типичный баг WA

**Invalid authorization header: Bearer komek...** — неверный `GREEN_API_WEBHOOK_TOKEN` на стороне Green API или в env Vercel.

---

## 7. Голосовые сообщения (STT)

### 7.1 Провайдеры (ensemble)

| Провайдер | Модель | Когда |
|-----------|--------|-------|
| **Together** | `openai/whisper-large-v3` | Основной, kk + auto |
| **Groq** | `whisper-large-v3` | Параллельно, резерв |
| **HuggingFace** | `abilmansplus/whisper-turbo-kaz-rus-v1` | Если score < 22 |
| **Local** | `LOCAL_WHISPER_URL` | VPS / dev |

Env: `VOICE_STT_PROVIDER=ensemble`

### 7.2 Промпты по длительности

| Профиль | Длительность | Размер |
|---------|--------------|--------|
| compact | < 4 с | ≤ 896 UTF-8 **байт** |
| standard | 4–15 с | ≤ 896 байт (Groq лимит!) |
| rich | 15+ с | до 2200 символов (Together) |

**Критично:** Groq считает лимит prompt в **байтах UTF-8** (896), не в символах. Казахский текст ~1.5–2 байта/символ → «680 символов» = ошибка 400.

Исправление: `app/bot/stt_prompt_utils.py` + truncate в `groq_client.py`.

### 7.3 Постобработка STT

1. **Scoring** — длина, kk-буквы, финансовые слова.
2. **LLM refine** (`STT_LLM_REFINE=true`) — Together чинит «менінше» → «мен несие».  
   - **Не применяется** к чистому русскому без kk-маркеров.  
   - Отсекает утечки промпта (`Кіріс:`, `STT транскрипт`).
3. **normalize_stt_voice_text** — словарные замены.
4. **strip_foreign_scripts** — удаляет `电话` → `📞`.

### 7.4 Маршрутизация голоса

`voice_router.route_voice_text`:

1. Вопрос про кредит без продукта → raw (в AI).
2. Короткая фраза → spoken digit / menu phrase.
3. **Длинная фраза (>8 слов)** → **не** сворачивать в цифру меню (баг «7» из мусора).
4. Опционально Groq intent (`GROQ_VOICE_INTENT`).

### 7.5 Очистка чужих символов

LLM иногда вставляет китайский (`电话`). Функция `strip_foreign_scripts()` в:

- `sanitize_for_telegram`
- `clean_whatsapp_text`
- `finalize_bot_response`
- `stt_normalize`

---

## 8. Языковая политика kk / ru

### 8.1 Правила (актуальные)

| Ситуация | Язык ответа |
|----------|-------------|
| `lang_locked` + сохранённый язык | Как в сессии |
| Хотя бы 1 kk-слово / буква (әіңғүұқөһ) / слово из словаря | **Қазақша** |
| Явный русский текст, **без** kk-маркеров | **Русский** |
| Сессия уже `ru`, kk-слов нет | **Русский** |
| Смесь ru+kk, есть kk-слово | **Қазақша** (приоритет) |
| Иначе | **Қазақша** (default) |

### 8.2 Функции

- `has_kazakh_marker(text)` — `lang_detect.py`
- `detect_message_lang(text)` — ru только при явных маркерах
- `resolve_reply_lang(text, session)` — для текста
- `resolve_voice_lang(text, session, stt_lang)` — после голоса
- `apply_lang_switch` — `1`/қазақша → kk, `2`/русский → ru + lock

### 8.3 Не путать язык

Слова `кредит`, `несие`, `ипотека`, `менеджер` — **не** маркер языка (ambiguous list).

### 8.4 STT и язык

- `_stt_prefer_kk` — kk STT, кроме `lang_locked` + `ru`.
- Не форсировать `detected = "kk"` в `_finalize_transcript`.
- `stt_refine` пропускает русский транскрипт.

---

## 9. AI, FAQ и гибридный ответ

### 9.1 Цепочка `_get_bot_reply` (HYBRID_AI=true)

```
1. ai_agent.run_kb_agent     ← LLM + полная KB
2. faq_matcher               ← правила, <50ms
3. faq_guide                 ← короткий наводящий вопрос
4. fallback message
```

### 9.2 Флаги

| Env | Default | Эффект |
|-----|---------|--------|
| `HYBRID_AI` | true | AI + меню |
| `FAST_FAQ` | true | Мгновенные FAQ |
| `FAQ_GUIDE_LLM` | true | Гид при промахе правил |
| `STT_LLM_REFINE` | true | Постправка kk STT |

### 9.3 Промпты LLM

`app/prompts.py` + `get_agent_system_prompt(lang)`:

- Отвечать **только** из базы знаний.
- Не выдумывать ставки.
- Ипотека — только офис.
- DAMU — залог 12,6%, 10 лет.
- Маркеры `[DONE]`, `[NOTIFY_MANAGER]`.

### 9.4 Fallback при сбое LLM

1. Groq → Together (по `AI_PROVIDER`)
2. Gemini 2.0 Flash при 429
3. Статическое сообщение `get_ai_fallback_message`

---

## 10. Матрица моделей: что когда использовать

### 10.1 Production (облако, Vercel)

| Задача | Рекомендация | Env |
|--------|--------------|-----|
| **Чат (основной)** | Together `Meta-Llama-3.1-8B-Instruct-Turbo` | `AI_PROVIDER=together` |
| **Чат (качество)** | Groq `openai/gpt-oss-120b` | `AI_PROVIDER=groq` |
| **STT казахский** | Ensemble Together+Groq+HF | `VOICE_STT_PROVIDER=ensemble` |
| **STT постправка** | Together LLM (тот же ключ) | `STT_LLM_REFINE=true` |
| **Голос → цифра меню** | Правила; опционально Groq `llama-3.1-8b-instant` | `GROQ_VOICE_INTENT` |
| **Авария 429** | Gemini 2.0 Flash | `GOOGLE_API_KEY` |
| **Только FAQ, без LLM** | — | `HYBRID_AI=false`, `FAST_FAQ=true` |

### 10.2 Локальный VPS (8 GB RAM)

См. `docs/LOCAL_MODELS.md`:

| Задача | Модель |
|--------|--------|
| Чат быстрый | Ollama `qwen2.5:3b` |
| Чат RU качество | `t-tech/t-lite-it-2.1:q4_K_M` |
| STT | faster-whisper `small` int8 |
| **Не ставить** | qwen2.5:7b, llama3.1:8b, Whisper medium на CPU |

### 10.3 Сравнение провайдеров STT

| | Together Whisper | Groq Whisper | HF kaz-rus-v1 |
|--|------------------|--------------|---------------|
| Скорость | Средняя | Быстрая | Медленная / cold |
| KK качество | Хорошее | Хорошее | Лучше для kk, но API нестабилен |
| Prompt limit | ~2200 chars | **896 UTF-8 bytes** | 15s timeout |
| Стоимость | Pay per use | Pay per use | HF credits |

### 10.4 Когда что менять

| Симптом | Действие |
|---------|----------|
| Много 429 от Groq | `AI_PROVIDER=together` |
| Плохой kk голос | Проверить Blob корпуса; `STT_LLM_REFINE=true` |
| Дорого | `FAST_FAQ=true`, короче `max_tokens` |
| Latency > 50s на Vercel | Убрать HF из hot path; `GROQ_VOICE_INTENT=false` |
| Полная приватность | VPS + `AI_PROVIDER=local` |

---

## 11. База знаний и продукты

### 11.1 Источники

- `app/bot/knowledge_base.py` — PRODUCTS, FAQ, `detect_intent`
- `app/bot/faq_matcher.py` — паттерны ключевых слов
- `docs/archive/КОМЕК ДАМУ ЧАТБОТ ИИ2026.md` — бизнес-ответы работодателя

### 11.2 Intent → меню

`detect_intent` → `intent_to_menu_digit` → цифра 1–7.

### 11.3 Офисы

`app/bot/formatting.py` — CITY_OFFICES (телефоны, адреса).  
Атырау удалён (`supabase/migrations/002_remove_atyrau.sql`).

---

## 12. Сессии, Supabase, лиды

### 12.1 Таблицы

- `clients` — chat_id, platform, name
- `sessions` — session_json
- `messages` — лог (до 8000 символов)
- `leads` — заявки

### 12.2 Env (алиасы)

```
SUPABASE_URL / NEXT_PUBLIC_komek_SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY / komek_SUPABASE_SERVICE_ROLE_KEY
```

### 12.3 Схема

```bash
python scripts/apply_supabase_schema.py
```

### 12.4 Debug

```
GET /debug/session/{chat_id}
```

---

## 13. Казахские корпуса и Vercel Blob

### 13.1 Зачем

Промпты Whisper с финансовой лексикой kk улучшают STT. Файлы ~5 MB — в Blob, не в git bundle.

### 13.2 Файлы

| Файл | В git | В Blob |
|------|-------|--------|
| `kk_stt_vocab.json` | ✅ (~423 KB) | ✅ |
| `kk_dictionary.json` | ❌ gitignore | ✅ |
| `kk_phrases_top10k.json` | ❌ gitignore | ✅ |

### 13.3 Сборка и загрузка

```bash
python scripts/download_kk_datasets.py
python scripts/build_kk_stt_vocab.py
python scripts/upload_kk_corpus_blob.py   # нужен BLOB_READ_WRITE_TOKEN
```

### 13.4 Env Blob

```
BLOB_READ_WRITE_TOKEN=
BLOB_STORE_ID=store_OTuiNVlUkxdaNaAx
BLOB_BASE_URL=https://otuinvlukxdanaax.private.blob.vercel-storage.com
KK_CORPUS_USE_BLOB=true
```

Без токена — fallback на локальный `app/bot/data/kk_stt_vocab.json`.

---

## 14. Деплой и окружения

### 14.1 Vercel

```bash
vercel deploy --prod --yes
curl https://komek-damu-bot.vercel.app/setup
```

Или с токеном:

```bash
export VERCEL_TOKEN=vcp_...
./scripts/deploy-vercel.sh
```

**Лимит:** 60 секунд на invocation (`vercel.json`).

### 14.2 GitHub (SSH)

В `~/.ssh/config`:

```
Host github.com-komekdamu
  HostName github.com
  User git
  IdentityFile ~/.ssh/komekdamubot_deploy
  IdentitiesOnly yes
```

Remote:

```
git@github.com-komekdamu:murdasoft/komekdamubot.git
```

### 14.3 Синхронизация env на Vercel

```bash
python scripts/sync-vercel-env-api.py
# или
python scripts/sync-vercel-env.py
```

### 14.4 Локальная разработка

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 14.5 Чеклист env для прода

| Переменная | Обязательно |
|------------|-------------|
| `WEBHOOK_BASE_URL` | ✅ |
| `TELEGRAM_BOT_TOKEN` | ✅ |
| `TELEGRAM_WEBHOOK_SECRET` | ✅ (не changeme) |
| `TOGETHER_API_KEY` или `GROQ_API_KEY` | ✅ |
| `SUPABASE_URL` + service key | ✅ |
| `BLOB_READ_WRITE_TOKEN` | Желательно (STT) |
| `TELEGRAM_ALERT_CHAT_ID` | Для менеджера |
| `GREEN_API_*` | Для WA |
| `VOICE_DEBUG_*` | Только на период тестов |

---

## 15. Мониторинг голоса (voice debug)

### 15.1 Назначение

На период тестирования: пересылка голосовых **от других пользователей** оператору.

### 15.2 Env

```
VOICE_DEBUG_ENABLED=true
VOICE_DEBUG_CHAT_ID=5450018125
```

### 15.3 Что приходит

1. Пересланное голосовое (forwardMessage).
2. Отчёт: chat/user ID, длительность, STT, routed text, ответ бота.

### 15.4 Исключения

- **Не** мониторит голос от самого `VOICE_DEBUG_CHAT_ID` (чтобы не слать себе).
- **Не** мониторит текстовые сообщения.
- **Не** мониторит WhatsApp (пока только TG).

### 15.5 Отключение

```
VOICE_DEBUG_ENABLED=false
```

---

## 16. Энциклопедия багов и решений

### 16.1 Голос

| # | Симптом | Причина | Решение |
|---|---------|---------|---------|
| G1 | «Естіген жоқпын» на 6с голосе | Groq 400: prompt >896 bytes | `stt_prompt_utils`, truncate в groq_client |
| G2 | Бот молчит после голоса | STT timeout / все провайдеры упали | Проверить ключи; логи Vercel; HF timeout |
| G3 | Казахский мусор на русском голосе | `stt_refine` + force kk | `resolve_voice_lang`, skip refine для ru |
| G4 | Routed «7» на длинной фразе | `extract_spoken_digit` в мусоре | Лимит >8 слов для digit routing |
| G5 | «тыңдап жатырмын» в чате | Старая версия | `send_chat_action` вместо текста |
| G6 | `电话` в ответе | LLM hallucination | `strip_foreign_scripts` |
| G7 | Промпт refine в STT («Кіріс:») | LLM leak | `_REFINE_LEAK_MARKERS` guard |
| G8 | Together 503 | Перегруз API | Fallback Groq; short prompt retry |

### 16.2 Telegram

| # | Симптом | Причина | Решение |
|---|---------|---------|---------|
| T1 | Бот не отвечает | Webhook не зарегистрирован | `GET /setup` |
| T2 | 403 webhook | Неверный secret | `TELEGRAM_WEBHOOK_SECRET` |
| T3 | Сессия сбрасывается | Нет Supabase | Проверить env + логи save_session |
| T4 | Rate limit | >20 msg/min | Подождать; `IGNORED_CHAT_IDS` |

### 16.3 WhatsApp

| # | Симптом | Причина | Решение |
|---|---------|---------|---------|
| W1 | Invalid Bearer | Неверный webhook token | Green API settings |
| W2 | Голос не качается | URL в quotedMessage | Fallback в handlers |
| W3 | Сломанный markdown | `tel:` ссылки | `clean_whatsapp_text` |

### 16.4 Язык

| # | Симптом | Причина | Решение |
|---|---------|---------|---------|
| L1 | Русский → ответ kk | Default kk + нет ru detect | `resolve_voice_lang` |
| L2 | Зацикливание «выберите язык» | Нет lang_locked | `lang_policy` |
| L3 | «кредит» переключил язык | Было до ambiguous list | `lang_detect._AMBIGUOUS` |

### 16.5 Деплой / инфра

| # | Симптом | Причина | Решение |
|---|---------|---------|---------|
| D1 | Function timeout 60s | STT+LLM долго | Убрать HF; короче ответы |
| D2 | Push denied | Неверный SSH ключ | `github.com-komekdamu` host |
| D3 | Blob 404 | Нет upload | `upload_kk_corpus_blob.py` |
| D4 | Cold start без сессии | Memory only | Supabase обязателен |

### 16.6 AI

| # | Симптом | Причина | Решение |
|---|---------|---------|---------|
| A1 | Выдуманные ставки | LLM игнорирует KB | Ужесточить prompt; FAST_FAQ |
| A2 | 429 Groq | Rate limit | Together primary; Gemini fallback |
| A3 | Длинный ответ | max_tokens | `LOCAL_LLM_MAX_TOKENS=256` на sync |

---

## 17. Troubleshooting: чеклисты

### 17.1 «Бот мёртв» (5 минут)

1. `curl https://komek-damu-bot.vercel.app/health`
2. `curl .../setup`
3. Vercel → Deployments → Logs
4. Проверить `WEBHOOK_BASE_URL`
5. Тестовое сообщение текстом
6. Проверить `handoff` / `BOT_SCHEDULE_ENABLED`

### 17.2 «Голос не работает»

1. Текстом то же фраза — работает?
2. `is_voice_stt_configured` — есть Together/Groq/HF?
3. Vercel logs: `Voice TG: STT result`
4. Включить `VOICE_DEBUG_ENABLED` (чужой аккаунт)
5. Локально: `python scripts/test_groq_stt.py`
6. Проверить Blob: `KK corpus stt_vocab from Blob`

### 17.3 «Неправильный язык»

1. `/debug/session/{chat_id}` → `lang`, `lang_locked`
2. STT raw в voice debug
3. `has_kazakh_marker(raw)` вручную в REPL

### 17.4 «После деплоя сломалось»

1. `GET /setup`
2. Сравнить env с `.env.example`
3. `git log -5` — что менялось
4. `pytest` локально

---

## 18. Тестирование

### 18.1 Полный прогон

```bash
./run_tests.sh
# или
pytest -v --tb=short
pytest --cov=app --cov-report=term-missing
```

### 18.2 Модули по областям

```bash
# Язык
pytest tests/test_lang_policy.py tests/test_lang_detect.py tests/test_strip_foreign.py -v

# Голос
pytest tests/test_voice_stt.py tests/test_voice_router.py tests/test_voice_debug.py -v
pytest tests/test_stt_prompt_profile.py tests/test_stt_kk_prompt.py -v

# FAQ / AI
pytest tests/test_faq_matcher.py tests/test_ai_agent.py tests/test_hybrid_flow.py -v

# Handler / flows
pytest tests/test_handlers.py tests/test_flows.py tests/test_wizard.py -v
```

### 18.3 Ручные проверки после релиза

| # | Действие | Ожидание |
|---|----------|----------|
| 1 | /start | Выбор языка |
| 2 | `1` → город `1` | Меню Алматы |
| 3 | Текст «нужен кредит» ru | Ответ ru |
| 4 | Голос kk «мен несие алғым келеді» | Ответ kk, не транскрипт |
| 5 | Голос ru без kk | Ответ ru |
| 6 | `7` | Handoff + телефон |
| 7 | `бот` после handoff | Возврат к боту |
| 8 | WA текст `1` | Аналог меню |

---

## 19. Безопасность и секреты

### 19.1 Никогда в git

- `.env`, `.env.vercel.*`
- `deploy_key` (приватный SSH)
- Токены API в коде

### 19.2 Ротация

Если токен попал в чат / лог — **сразу** отозвать:

- Vercel token
- Supabase service role
- Telegram bot token (BotFather)
- Groq / Together / HF keys

### 19.3 Открытые endpoints

`/debug/session`, `/admin/stats` — без auth. На hardened prod — закрыть или IP whitelist.

### 19.4 Gemini fallback

Проверить `gemini_client.py` — использовать только `GOOGLE_API_KEY` из env.

---

## 20. Как двигаться дальше (roadmap)

### 20.1 Краткосрочно (стабильность)

- [ ] `VOICE_DEBUG_ENABLED=false` после завершения тестов голоса
- [ ] Убедиться что `BLOB_READ_WRITE_TOKEN` на Vercel + корпуса залиты
- [ ] Supabase всегда в проде
- [ ] `BOT_SCHEDULE_ENABLED` — согласовать с бизнесом
- [ ] Закрыть `/debug/*` или добавить auth

### 20.2 Среднесрочно (качество)

- [ ] LangSmith / structured logging для STT+LLM traces
- [ ] Voice debug для WhatsApp
- [ ] Автотесты с реальными .ogg сэмплами
- [ ] Вынести agent state в LangGraph (см. обсуждение фреймворков)
- [ ] n8n для Bitrix / CRM автоматизаций

### 20.3 Долгосрочно (масштаб)

- [ ] Шаблон `bot-template` репо для новых ботов
- [ ] Отдельный STT microservice (не 60s Vercel limit)
- [ ] KazParC полный корпус при доступе HF
- [ ] A/B промптов STT по метрикам voice debug

### 20.4 Правила хорошего релиза

1. `pytest` зелёный
2. `git push` → Vercel auto-deploy или `vercel deploy --prod`
3. `curl /setup`
4. Smoke: текст + голос kk + голос ru
5. Проверить voice debug с **чужого** аккаунта
6. Обновить этот гайдбук при изменении env или пайплайна

### 20.5 Когда НЕ переписывать всё

Текущий стек (FastAPI + ensemble STT + hybrid FAQ) **рабочий** для kk/ru + голос.  
Платформы типа Botpress — для **новых простых** ботов, не замена Komek core.

---

## 21. Приложения

### A. Переменные окружения (полный список)

См. `.env.example` в корне репозитория — актуальный источник.

### B. HTTP endpoints

| Method | Path | Описание |
|--------|------|----------|
| GET | `/` | Status |
| GET | `/health` | Health check |
| POST | `/webhook/telegram` | Telegram |
| POST | `/webhook/whatsapp` | WhatsApp |
| GET | `/setup` | Register webhooks |
| GET | `/debug/session/{id}` | Session JSON |
| GET | `/admin/stats` | Analytics |
| GET | `/admin/leads` | Leads list |

### C. Навигационные коды

| Код | Действие |
|-----|----------|
| 0 | Назад / разделы |
| 1–7 | Меню продуктов |
| 98 | Сменить город |
| 99 | Сменить язык |

### D. Исторические документы

| Файл | Содержание |
|------|------------|
| `docs/archive/TASK_VOICE_TG_FIX.md` | История бага голоса TG |
| `docs/archive/PLAN_VOICE_AND_UX.md` | План voice UX |
| `docs/LOCAL_MODELS.md` | VPS модели |
| `docs/archive/KOMEK DAMU.md` | Старая KB-выжимка |

### E. Контакты офисов (справочно)

| Город | Телефон |
|-------|---------|
| Астана | 8 702 187 97 26 |
| Алматы | 8 707 339 10 39 |
| Шымкент | 8 705 810 28 81 |
| Актау | 8 705 112 99 22 |

Часы в ответах бота: 10:00–18:00 (`formatting.py`).

### F. Версионирование гайдбка

При каждом значимом изменении:

1. Обновить дату в шапке.
2. Добавить строку в раздел 16 (баги).
3. Обновить матрицу моделей при смене prod env.

---

*Конец гайдбука. Вопросы и правки — в issue GitHub или в комментарии к коммиту.*

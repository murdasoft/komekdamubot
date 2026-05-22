# Бриф: выбор локальных моделей для KOMEK DAMU Bot

Внутренний документ для поиска, A/B-тестов и апгрейда стека.  
Актуально для **Hetzner CX33** (8 GB RAM, 4 vCPU, CPU-only, Helsinki).

---

## 1. Продукт и задача

**KOMEK DAMU Bot** — AI-чат-бот финансовой компании (Казахстан): кредиты, ипотека, DAMU 12,6%, рефинансирование.

| Параметр | Значение |
|----------|----------|
| Каналы | Telegram + WhatsApp (Green API), webhooks, **HTTPS обязателен** |
| Языки | Русский (RU) + Казахский (KK) |
| Продукты | 6 сценариев (физ/бизнес кредит, DAMU, гос/обычная ипотека, рефин, сложные случаи) |
| Стек | Python 3, FastAPI, Ollama, faster-whisper, systemd |
| Репозиторий | `murdasoft/komekdamubot` |

**Что ищем:** self-hosted LLM + STT **без дневных лимитов** (Groq free ~50 msg/day — не подходит).

**Целевая латентность:** ответ пользователю **5–20 сек** на CPU.

**Критично:** не галлюцинировать ставки/условия — факты только из `knowledge_base.py` / RAG.

---

## 2. Железо (жёсткие ограничения)

| Параметр | Значение |
|----------|----------|
| Хостинг | Hetzner Cloud CX33 |
| RAM | **8 GB** |
| CPU | **4 vCPU**, **без GPU** |
| Прод IP | `204.168.223.9` (Helsinki) |
| Путь | `/opt/komek-damu-bot` |

**Одновременно в RAM:** FastAPI + Ollama (LLM) + faster-whisper (STT, порт 11435) + OS + cloudflared.

**Старый CX23 (4 GB):** OOM на `qwen2.5:3b`, Whisper `medium` 30+ сек — не использовать.

**HTTPS:** Cloudflare Tunnel (URL нестабилен); в перспективе — свой домен + nginx + certbot.

---

## 3. Текущий стек (прод)

```env
AI_PROVIDER=local
GROQ_ENABLED=false
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=qwen2.5:3b
LOCAL_WHISPER_URL=http://127.0.0.1:11435
```

| Компонент | Модель | Статус |
|-----------|--------|--------|
| LLM | `qwen2.5:3b` (Q4 ~1.9 GB) | Baseline, 5–15 сек на CPU |
| STT | faster-whisper `small` + int8 | 3–8 сек на короткое голосовое |
| Groq | Выключен | Только аварийно: `GROQ_ENABLED=true` |

См. также: [LOCAL_MODELS.md](./LOCAL_MODELS.md)

---

## 4. Резюме по LLM (CX33, 8 GB, CPU)

### 4.1 Baseline — Qwen2.5-3B

- [Qwen2.5-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-3B) — мультиязычная (в т.ч. RU), instruction-following, JSON.
- [Qwen2.5 blog](https://qwen.ai/blog?id=qwen2.5-llm) — один из лучших малых моделей в своей размерности.
- Уже на сервере: Q4 ~1.9 GB, **5–15 сек** — оптимум «качество / латентность / RAM» для CX33.

### 4.2 Кандидат на апгрейд RU — T-lite-it-2.1:q4_K_M

- [T-lite-it-2.1](https://huggingface.co/t-tech/T-lite-it-2.1-FP8) — русскоязычная на базе Qwen3, дообучена под RU и инструкции.
- [GGUF](https://huggingface.co/t-tech/T-lite-it-2.1-GGUF) — `q4_K_M` ~5 GB.
- [Ollama](https://ollama.com/t-tech/T-lite-it-2.1): `ollama pull t-tech/t-lite-it-2.1:q4_K_M`
- Бенчмарки (Ru Arena Hard, ruIFeval, ruBFCL): заметно сильнее базовых Qwen — [обзор](https://github.com/Orbiter/project-euler-llm-benchmark).
- Лицензия **Apache 2.0** — OK для коммерческого финтех-бота — [Habr/T-Bank](https://habr.com/ru/companies/tbank/articles/865582/).

**Практический вывод:** если критичны RU-лексика и послушность инструкциям — **A/B** `T-lite-it-2.1:q4_K_M` vs `qwen2.5:3b` на продовых диалогах. Компактной модели «лучше RU + 2–3 GB + сильный прирост» на 2025–2026 особо нет.

### 4.3 Почему другие LLM хуже под CX33

| Модель | Проблема |
|--------|----------|
| **ISSAI KAZ-LLM 8B/70B** | [RU+KK+EN](https://issai.nu.edu.kz/2024/12/10/official-release-of-the-issai-kaz-llm-open-source-model-is-available/), но **CC-BY-NC** (некоммерция), 8B на CPU медленно и жрёт RAM |
| **Gemma 2 / GemmaX2-2B** | Мультиязычие, не RU-специалисты — [Gemma 2](https://developers.googleblog.com/en/advancing-multilingual-ai-with-gemma-2-and-a-150k-challenge/) |
| **Phi-3-mini** | Много языков «в среднем», не фокус RU/KK — [NVIDIA blog](https://blogs.nvidia.com/blog/microsoft-open-phi-3-mini-language-models/) |
| **7B / 8B+** | OOM или минуты на CPU без GPU |

### 4.4 RU + KK — компромисс

Нет открытой LLM ≤3–4B, которая одновременно: **RU + KK + коммерческая лицензия + ≤5 GB Q4 + хорошие инструкции + стабильно на CPU**.

Разумная стратегия:

1. Оптимизировать **RU** (T-lite или Qwen2.5-3B).
2. Для **KK**: промпты + RAG + маршрутизация (часть KK → шаблоны/FAQ, сложное — handoff).

---

## 5. STT (RU + KK) на 8 GB CPU

### 5.1 Оставить: faster-whisper small int8

- Компактная модель для CPU — [Astana Hub: fine-tune Whisper Small для KK](https://astanahub.com/en/blog/obuchaem-whisper-small-dlia-raspoznavaniia-kazakhskoi-rechi).
- На CX33: **3–8 сек** на короткое голосовое — хороший компромисс при работе LLM параллельно.
- Компенсация WER: **initial prompt** с доменными терминами (кредит, ипотека, DAMU, несие) — уже в `scripts/whisper-api-fast.py`.

### 5.2 Не для CX33 (только с апгрейдом сервера)

| Вариант | Почему не сейчас |
|---------|------------------|
| [whisper-turbo-kaz-rus-v1](https://huggingface.co/abilmansplus/whisper-turbo-kaz-rus-v1) | Топ WER KK/RU, но large-v3-turbo — десятки сек / OOM на 8 GB + LLM |
| **Vosk KZ** | WER ~51% на KazakhTTS — [исследование](https://ce.journal.satbayev.university/index.php/journal/article/view/1265) |
| **Silero STT** | Отличный RU, **нет KK** — [pypi](https://pypi.org/project/silero/) |
| **ISSAI ASR** | Исследовательский стек, не drop-in замена |

### 5.3 Будущее улучшение STT

- Дообучить **Whisper Small** на своих анонимизированных голосовых — [гайд Astana Hub](https://astanahub.com/en/blog/obuchaem-whisper-small-dlia-raspoznavaniia-kazakhskoi-rechi).
- Датасеты: [kazakh-stt](https://huggingface.co/datasets/farabi-lab/kazakh-stt).

---

## 6. RAM-схема (оценочно)

| Компонент | RAM |
|-----------|-----|
| OS + cloudflared + сервисы | ~1.0–1.5 GB |
| FastAPI + uvicorn | ~0.3–0.6 GB |
| faster-whisper small int8 | ~0.8–1.2 GB (пик) |
| **qwen2.5:3b** Q4 | ~1.9 GB |
| **T-lite q4_K_M** | ~5 GB |

### Сценарий A: Qwen2.5-3B (сейчас)

~1.5 + 0.5 + 1 + 2 ≈ **5 GB** → запас 2–3 GB. Стабильно.

### Сценарий B: T-lite-it-2.1:q4_K_M

~1.5 + 0.5 + 1 + 5 ≈ **8 GB** → почти весь объём. Нужны:

- лимит concurrency;
- жёсткий `max_tokens` и короткая история;
- мониторинг OOM;
- возможно отдельный воркер для LLM.

**Вывод:** T-lite **реалистично попробовать** на CX33, но с осторожностью. Комфортный запас — **CX43 (16 GB)** или GPU.

---

## 7. Рекомендуемый план действий

### Шаг 1 — A/B LLM

```bash
# На сервере (dev/staging или ночной тест)
ollama pull t-tech/t-lite-it-2.1:q4_K_M
# .env для теста:
LOCAL_LLM_MODEL=t-tech/t-lite-it-2.1:q4_K_M
systemctl restart komek-damu-bot
```

Метрики: % корректных ответов, % галлюцинаций по ставкам, средняя и **p95** латентность.  
Порог перехода в прод: p95 ≤ 20 сек + заметный выигрыш по RU.

### Шаг 2 — STT без смены движка

- Оставить `faster-whisper small int8`.
- Расширить initial prompt (продукты KOMEK DAMU, «ипотека 2%», «рефинансирование», kk-термины).

### Шаг 3 — Галлюцинации через логику бота

- LLM: классификация намерения + общий текст.
- Ставки/сроки/условия — **только** из `app/bot/knowledge_base.py`.

### Шаг 4 — Апгрейд сервера (опционально)

| Апгрейд | Что открывает |
|---------|----------------|
| **16 GB RAM** (CX43) | T-lite Q5 + запас под STT |
| **GPU** (L4/RTX класс) | whisper-turbo-kaz-rus, крупные LLM, латентность секунды |

---

## 8. Что уже пробовали

| Решение | Результат |
|---------|-----------|
| Groq LLM + STT | 2–5 сек, лимит ~50 msg/day |
| qwen2.5:1.5b | Быстро, слабые ответы |
| qwen2.5:3b | **Текущий baseline** |
| qwen2.5:7b / 8B | OOM / очень медленно |
| whisper medium | OOM на 4 GB, 35+ сек |
| faster-whisper small int8 | **Работает** |
| Vercel | Ушли на Hetzner |

---

## 9. Критерии выбора (чеклист)

**Обязательно:**

- [ ] Self-hosted, без лимита 50/день
- [ ] 8 GB RAM, CPU-only (или честно «нужен GPU»)
- [ ] RU (желательно KK или компенсация промптами)
- [ ] Ollama / HTTP API
- [ ] Ответ < 20 сек типичный вопрос
- [ ] Коммерческая лицензия

**Желательно:**

- [ ] GGUF Q4_K_M, 2–5 GB
- [ ] Instruction-following, короткие ответы
- [ ] Один STT-стек

---

## 10. Поисковые запросы (RU + EN)

### LLM на 8GB CPU

```
best ollama model 8GB RAM CPU russian 2025 2026
qwen2.5 3b vs t-lite-it-2.1 russian benchmark
t-tech T-lite-it-2.1 q4_K_M RuArena ruIFeval ruBFCL
T-lite-it-2.1 q4_K_M 8GB RAM CPU latency
self-hosted LLM financial chatbot russian low latency CPU
Ollama models 8GB RAM no GPU comparison
llama 3.2 3b vs qwen2.5 3b russian language
Phi-3 mini russian instruction following CPU benchmark
ISSAI KAZ-LLM 8B russian kazakh small quantization
```

### STT RU + KK

```
faster-whisper small vs medium russian WER CPU
whisper kazakh language support accuracy
whisper-large-v3-turbo kazakh russian WER
whisper-turbo kaz-rus-v1 abilmansplus benchmark
best speech to text russian kazakh self-hosted
faster-whisper initial prompt domain vocabulary loan mortgage
vosk kazakh model word error rate
silero STT russian offline benchmark 2024
kazakh ASR ISSAI multilingual speech recognition
```

### Архитектура

```
ollama + faster-whisper same server 8GB RAM memory usage
sequential load LLM STT avoid OOM 8GB
telegram voice bot ollama whisper latency optimization
cpu only LLM 3B 8B tokens per second benchmark
warmup request ollama cold start 8GB RAM
```

### Альтернативы Groq

```
Groq API free tier limit messages per day
open source replacement Groq whisper large v3 CPU
self-hosted alternative Groq STT LLM russian
```

### Казахстан / RU+KK

```
bilingual russian kazakh chatbot LLM small model
Qwen russian kazakh multilingual 3B
ISSAI Kaz-LLM kazakh russian english license
kazakh speech dataset open source 2024 2025
```

---

## 11. Однострочная формулировка (для ChatGPT / Perplexity)

> Self-hosted стек для Telegram/WhatsApp финансового бота (RU+KK): LLM для коротких консультаций по кредитам/ипотеке + STT для голосовых на **Hetzner 8GB RAM, 4 vCPU, без GPU**, ответ **<20 сек**, без Groq (лимит 50 msg/day). Сейчас Ollama `qwen2.5:3b` + faster-whisper `small` int8. Ищу лучшее RU при тех же ресурсах или обоснование апгрейда до 16GB/GPU.

---

## 12. Ссылки

| Ресурс | URL |
|--------|-----|
| T-lite GGUF | https://huggingface.co/t-tech/T-lite-it-2.1-GGUF |
| T-lite Ollama | https://ollama.com/t-tech/T-lite-it-2.1 |
| Qwen2.5-3B | https://huggingface.co/Qwen/Qwen2.5-3B |
| Whisper Kaz/Ru turbo | https://huggingface.co/abilmansplus/whisper-turbo-kaz-rus-v1 |
| ISSAI KAZ-LLM | https://issai.nu.edu.kz/2024/12/10/official-release-of-the-issai-kaz-llm-open-source-model-is-available/ |
| faster-whisper | https://github.com/SYSTRAN/faster-whisper |

---

*Последнее обновление: май 2026. Согласовано с прод-конфигом CX33 и `docs/LOCAL_MODELS.md`.*

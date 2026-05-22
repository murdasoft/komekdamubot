# Локальные модели для KOMEK DAMU Bot (8 GB RAM, CPU)

Groq **не используем** в проде (лимит ~50 сообщений/день на free tier).

## Рекомендация для CX33 (8 GB, 4 vCPU, Helsinki)

| Задача | Модель | Ollama / сервис | RAM | Скорость CPU | Качество RU/KK |
|--------|--------|-----------------|-----|--------------|----------------|
| **Чат (основная)** | `qwen2.5:3b` | `ollama pull qwen2.5:3b` | ~2.2 GB | 5–15 сек | Хорошо ru/kk |
| **Чат (лучший русский)** | `t-tech/t-lite-it-2.1:q4_K_M` | `ollama pull t-tech/t-lite-it-2.1:q4_K_M` | ~5 GB | 10–25 сек | Отлично RU |
| **Голос** | `small` + int8 | faster-whisper (уже на сервере) | ~0.5 GB | 3–8 сек / 16 сек аудио | RU ~8% WER |

На 8 GB **одновременно** помещаются: Ollama `qwen2.5:3b` + Whisper `small`.

## Не ставить на 8 GB

- `qwen2.5:7b`, `llama3.1:8b` — OOM или очень медленно
- Whisper `medium` на CPU — 30+ сек на голосовое
- Две большие модели в Ollama одновременно

## Переключение модели на сервере

```bash
# Вариант A — баланс скорость/качество (по умолчанию)
ollama pull qwen2.5:3b
# В /opt/komek-damu-bot/.env:
LOCAL_LLM_MODEL=qwen2.5:3b

# Вариант B — максимум качества русского
ollama pull t-tech/t-lite-it-2.1:q4_K_M
LOCAL_LLM_MODEL=t-tech/t-lite-it-2.1:q4_K_M

systemctl restart komek-damu-bot
```

## Groq (только аварийно)

```env
GROQ_ENABLED=true
GROQ_API_KEY=gsk_...
```

## Ссылки

- [Ollama: t-tech/T-lite-it-2.1](https://ollama.com/t-tech/T-lite-it-2.1) — русскоязычная модель на Qwen3
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — STT на сервере
- [Ollama 8GB guide 2026](https://webscraft.org/blog/ollama-na-8-gb-ram-yaki-modeli-pratsyuyut-u-2026)

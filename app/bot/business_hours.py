"""
Расписание автоответа чат-бота (часовой пояс Казахстана).

Будни 09:00–18:00 — отвечает менеджер (бот молчит).
Вечер будни 18:00–09:00, суббота, воскресенье, праздники — бот активен.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.config import get_settings

# Гос. праздники РК (дополняются BOT_HOLIDAYS в env)
_KZ_HOLIDAYS_DEFAULT: frozenset[str] = frozenset({
    "2025-01-01", "2025-01-02", "2025-01-07",
    "2025-03-08", "2025-03-21", "2025-03-22", "2025-03-23", "2025-03-24", "2025-03-25",
    "2025-05-01", "2025-05-07", "2025-05-09",
    "2025-07-06",
    "2025-08-30", "2025-12-01", "2025-12-16", "2025-12-17",
    "2026-01-01", "2026-01-02", "2026-01-07",
    "2026-03-08", "2026-03-21", "2026-03-22", "2026-03-23", "2026-03-24", "2026-03-25",
    "2026-05-01", "2026-05-07", "2026-05-09",
    "2026-07-06",
    "2026-08-30", "2026-12-01", "2026-12-16", "2026-12-17",
})


def _parse_time_hhmm(raw: str, default: time) -> time:
    raw = (raw or "").strip()
    if not raw:
        return default
    parts = raw.split(":")
    try:
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        return time(h % 24, m % 60)
    except (ValueError, IndexError):
        return default


def _holiday_dates() -> frozenset[str]:
    settings = get_settings()
    extra = settings.bot_holidays.strip()
    if not extra:
        return _KZ_HOLIDAYS_DEFAULT
    out = set(_KZ_HOLIDAYS_DEFAULT)
    for part in extra.replace(";", ",").split(","):
        d = part.strip()
        if d:
            out.add(d)
    return frozenset(out)


def is_bot_active_now(now: datetime | None = None) -> bool:
    """True — бот может автоответить; False — рабочие часы офиса (менеджер)."""
    settings = get_settings()
    if not settings.bot_schedule_enabled:
        return True

    tz = ZoneInfo(settings.bot_timezone or "Asia/Almaty")
    if now is None:
        now = datetime.now(tz)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    d_str = now.date().isoformat()
    if d_str in _holiday_dates():
        return True
    if now.weekday() >= 5:
        return True

    start = _parse_time_hhmm(settings.bot_human_hours_start, time(9, 0))
    end = _parse_time_hhmm(settings.bot_human_hours_end, time(18, 0))
    t = now.time()
    if start <= t < end:
        return False
    return True


def get_human_hours_reply(lang: str) -> str:
    settings = get_settings()
    start = settings.bot_human_hours_start or "09:00"
    end = settings.bot_human_hours_end or "18:00"
    if lang == "kk":
        return (
            f"🕐 *Қазір жұмыс уақыты* ({start}–{end}, дүйсенбі–жұма).\n\n"
            "Сізге *менеджер* жауап береді.\n"
            f"Чат-бот кешке *{end}*-ден кейін, демалыс және мереке күндері жұмыс істейді."
        )
    return (
        f"🕐 *Сейчас рабочее время офиса* ({start}–{end}, пн–пт).\n\n"
        "Вам ответит *менеджер*.\n"
        f"Чат-бот включится вечером после *{end}*, в выходные и праздники."
    )

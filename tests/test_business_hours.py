"""Расписание: будни 09–18 — менеджер; вечер/выходные — бот."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.bot.business_hours import is_bot_active_now


TZ = ZoneInfo("Asia/Almaty")


def _dt(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=TZ)


def _reset_settings():
    import app.config as cfg

    cfg._settings = None


def test_weekday_morning_bot_off(monkeypatch):
    monkeypatch.setenv("BOT_SCHEDULE_ENABLED", "true")
    _reset_settings()
    # Среда 10:00 — менеджер
    assert is_bot_active_now(_dt(2026, 5, 20, 10)) is False


def test_weekday_evening_bot_on(monkeypatch):
    monkeypatch.setenv("BOT_SCHEDULE_ENABLED", "true")
    _reset_settings()
    # Среда 19:00 — бот
    assert is_bot_active_now(_dt(2026, 5, 20, 19)) is True


def test_saturday_all_day_bot_on(monkeypatch):
    monkeypatch.setenv("BOT_SCHEDULE_ENABLED", "true")
    _reset_settings()
    # Суббота 12:00
    assert is_bot_active_now(_dt(2026, 5, 23, 12)) is True


def test_holiday_bot_on(monkeypatch):
    monkeypatch.setenv("BOT_SCHEDULE_ENABLED", "true")
    _reset_settings()
    # 1 января 2026, понедельник 11:00 — праздник
    assert is_bot_active_now(_dt(2026, 1, 1, 11)) is True


def test_schedule_disabled_always_on(monkeypatch):
    monkeypatch.setenv("BOT_SCHEDULE_ENABLED", "false")
    _reset_settings()
    assert is_bot_active_now(_dt(2026, 5, 20, 12)) is True

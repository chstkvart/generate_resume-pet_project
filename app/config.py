"""Настройки приложения."""

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # ограничение размера запроса (фото) — 5 МБ
    VACANCY_API_TIMEOUT = 30  # секунд; API «Работа России» отвечает за 10–15 с
    VACANCY_CACHE_TTL = 600  # результаты поиска по одной должности кэшируются на 10 минут


class TestConfig(Config):
    TESTING = True

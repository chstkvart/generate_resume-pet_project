"""Открытый API портала «Работа России» (trudvsem.ru). Ключ доступа не требуется."""

import re
import threading
import time

import requests

from app.choices import (
    EMPLOYMENT_TYPES,
    FULL_TIME,
    ON_SITE,
    PART_TIME,
    REMOTE,
    SIDE_JOB,
)
from app.services.vacancy_sources import Vacancy, VacancySourceError

API_URL = "https://opendata.trudvsem.ru/api/v1/vacancies"
PAGE_LIMIT = 100  # максимум, который разрешает API
REMOTE_RE = re.compile(r"удал[её]нн|дистанц|remote")


class TrudvsemSource:
    name = "Работа России"
    url = "https://trudvsem.ru"

    def __init__(self, timeout: float = 30, cache_ttl: float = 600):
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, list[Vacancy]]] = {}
        self._lock = threading.Lock()

    def search(self, query: str) -> list[Vacancy]:
        key = query.strip().lower()
        with self._lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < self.cache_ttl:
                return cached[1]

        vacancies = self._fetch(query)
        with self._lock:
            self._cache[key] = (time.monotonic(), vacancies)
        return vacancies

    def _fetch(self, query: str) -> list[Vacancy]:
        try:
            response = requests.get(
                API_URL, params={"text": query, "limit": PAGE_LIMIT}, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise VacancySourceError("Сервис «Работа России» недоступен.") from exc

        items = (data.get("results") or {}).get("vacancies") or []
        return [parse_vacancy(item["vacancy"]) for item in items if "vacancy" in item]


def _positive_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def parse_formats(raw: dict) -> list[str]:
    """Переводит поля employment и schedule API в варианты формата работы из формы."""
    employment = (raw.get("employment") or "").lower()
    schedule = (raw.get("schedule") or "").lower()
    title = (raw.get("job-name") or "").lower()

    formats = set()
    if "дистанц" in employment or "удален" in employment or REMOTE_RE.search(title):
        formats.add(REMOTE)
    elif employment or schedule:
        formats.add(ON_SITE)

    if "полная" in employment or schedule.startswith("полный"):
        formats.add(FULL_TIME)
    if "частичн" in employment or "неполн" in schedule:
        formats.update({PART_TIME, SIDE_JOB})
    if "временн" in employment or "подработ" in title:
        formats.add(SIDE_JOB)

    return [option for option in EMPLOYMENT_TYPES if option in formats]


def parse_vacancy(raw: dict) -> Vacancy:
    addresses = (raw.get("addresses") or {}).get("address") or []
    requirement = raw.get("requirement") or {}
    experience = requirement.get("experience")
    text_parts = [raw.get("job-name"), raw.get("requirements"), raw.get("duty")]
    text_parts += [s for s in raw.get("skills") or [] if isinstance(s, str)]

    return Vacancy(
        title=raw.get("job-name") or "Без названия",
        url=raw.get("vac_url") or "",
        company=(raw.get("company") or {}).get("name") or "",
        region=(raw.get("region") or {}).get("name") or "",
        address=addresses[0].get("location", "") if addresses else "",
        salary_min=_positive_int(raw.get("salary_min")),
        salary_max=_positive_int(raw.get("salary_max")),
        experience_years=int(experience) if isinstance(experience, int | float) else None,
        schedule=raw.get("schedule") or "",
        text=" ".join(p for p in text_parts if p),
        formats=parse_formats(raw),
    )

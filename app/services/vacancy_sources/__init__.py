"""Источники вакансий. Каждый источник реализует протокол VacancySource."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Vacancy:
    title: str
    url: str
    company: str = ""
    region: str = ""
    address: str = ""
    salary_min: int | None = None
    salary_max: int | None = None
    experience_years: int | None = None  # требуемый опыт
    schedule: str = ""
    text: str = ""  # требования и обязанности — используются для сопоставления навыков
    formats: list[str] = field(default_factory=list)  # значения из choices.EMPLOYMENT_TYPES

    @property
    def salary_mid(self) -> float | None:
        if self.salary_min and self.salary_max:
            return (self.salary_min + self.salary_max) / 2
        return self.salary_min or self.salary_max


class VacancySourceError(Exception):
    """Источник вакансий недоступен или вернул некорректный ответ."""


class VacancySource(Protocol):
    name: str
    url: str

    def search(self, query: str) -> list[Vacancy]: ...

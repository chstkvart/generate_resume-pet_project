from io import BytesIO

import pytest
from PIL import Image

from app import create_app
from app.config import TestConfig
from app.services.vacancy_sources import Vacancy


class FakeVacancySource:
    name = "Тестовый источник"
    url = "https://example.ru"

    def __init__(self, vacancies: list[Vacancy] | None = None):
        self.vacancies = vacancies or []
        self.queries: list[str] = []

    def search(self, query: str) -> list[Vacancy]:
        self.queries.append(query)
        return self.vacancies


@pytest.fixture
def vacancy_source():
    return FakeVacancySource([
        Vacancy("Middle Python-разработчик", "https://example.ru/1", "ООО Альфа", "Город Москва",
                salary_min=150000, salary_max=250000, experience_years=3,
                text="Python, Django, PostgreSQL"),
        Vacancy("Junior Python-разработчик", "https://example.ru/2", "ООО Бета",
                "Ростовская область", salary_min=60000, salary_max=90000, experience_years=1,
                text="Python, Git"),
        Vacancy("Senior Python-разработчик", "https://example.ru/3", "ООО Гамма", "Город Москва",
                salary_min=350000, experience_years=6, text="Python, Kubernetes"),
        Vacancy("Бухгалтер", "https://example.ru/4", "ООО Дельта", "Город Москва",
                salary_min=70000, experience_years=1, text="1С"),
    ])


@pytest.fixture
def app(vacancy_source):
    app = create_app(TestConfig)
    app.extensions["vacancy_source"] = vacancy_source
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def photo_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (800, 600), color=(120, 140, 160)).save(buffer, format="PNG")
    return buffer.getvalue()

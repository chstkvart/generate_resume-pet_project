from unittest.mock import Mock, patch

import pytest
import requests

from app.services.vacancy_sources import VacancySourceError
from app.services.vacancy_sources.trudvsem import TrudvsemSource, parse_formats, parse_vacancy

RAW_VACANCY = {
    "job-name": "Разработчик Python",
    "vac_url": "https://trudvsem.ru/vacancy/card/1/2",
    "company": {"name": "ООО Ромашка"},
    "region": {"name": "Самарская область"},
    "addresses": {"address": [{"location": "г Тольятти, ул. Ленина, 1"}]},
    "salary_min": 90000,
    "salary_max": 0,
    "requirement": {"experience": 1},
    "schedule": "Полный рабочий день",
    "requirements": "Опыт с Flask",
    "duty": "Разработка API",
    "skills": ["Docker"],
}


def api_response(vacancies):
    response = Mock()
    response.json.return_value = {"results": {"vacancies": [{"vacancy": v} for v in vacancies]}}
    return response


def test_parse_vacancy():
    vacancy = parse_vacancy(RAW_VACANCY)

    assert vacancy.title == "Разработчик Python"
    assert vacancy.company == "ООО Ромашка"
    assert vacancy.salary_min == 90000
    assert vacancy.salary_max is None  # 0 в API означает «не указано»
    assert vacancy.experience_years == 1
    assert "Flask" in vacancy.text and "Docker" in vacancy.text


@pytest.mark.parametrize(
    ("employment", "schedule", "title", "expected"),
    [
        ("Полная занятость", "Полный рабочий день", "Программист",
         ["Полная занятость", "На месте работодателя"]),
        ("Дистанционная (удаленная) работа", "Полный рабочий день", "Программист",
         ["Полная занятость", "Удалённо"]),
        (None, "Неполный рабочий день/неполная рабочая неделя", "Программист",
         ["Частичная занятость", "Подработка", "На месте работодателя"]),
        ("Временная работа", None, "Курьер", ["Подработка", "На месте работодателя"]),
        (None, None, "Удалённый оператор", ["Удалённо"]),
        (None, None, "Программист", []),
    ],
)
def test_parse_formats(employment, schedule, title, expected):
    raw = {"employment": employment, "schedule": schedule, "job-name": title}

    assert parse_formats(raw) == expected


def test_search_caches_results():
    source = TrudvsemSource()
    with patch("requests.get", return_value=api_response([RAW_VACANCY])) as get:
        first = source.search("Python")
        second = source.search("python ")

    assert get.call_count == 1
    assert first == second and len(first) == 1


def test_empty_response():
    response = Mock()
    response.json.return_value = {"status": "200", "results": {}}
    with patch("requests.get", return_value=response):
        assert TrudvsemSource().search("Несуществующая профессия") == []


def test_network_error_is_wrapped():
    with (
        patch("requests.get", side_effect=requests.ConnectionError),
        pytest.raises(VacancySourceError),
    ):
        TrudvsemSource().search("Python")

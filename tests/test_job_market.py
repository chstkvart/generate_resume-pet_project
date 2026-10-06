from datetime import date

from app.models import Experience, Resume
from app.services.job_market import (
    SalaryEstimate,
    analyze,
    estimate_salary,
    expectations_verdict,
    format_match,
    is_relevant,
    matched_skills,
    search_queries,
    title_level,
    title_score,
)
from app.services.vacancy_sources import Vacancy, VacancySourceError

TODAY = date(2026, 10, 5)


def middle_resume(**overrides) -> Resume:
    data = {
        "full_name": "Иван",
        "title": "Python-разработчик",
        "skills": ["Python", "Django", "PostgreSQL"],
        "experience": [Experience(start="2023-01", current=True)],  # 3 г. 10 мес.
    }
    data.update(overrides)
    return Resume(**data)


def test_title_score_ignores_word_order_and_endings():
    assert title_score("Python-разработчик", "Разработчика Python") == 1
    assert title_score("Python-разработчик", "Бухгалтер") == 0


def test_matched_skills_uses_whole_words():
    text = "Требуется знание Python, Django и Google Cloud"

    assert matched_skills(["Python", "Go", "Django"], text) == ["Python", "Django"]


def test_irrelevant_and_too_senior_vacancies_are_filtered(vacancy_source):
    report = analyze(middle_resume(), vacancy_source, TODAY)

    titles = [v.title for v in report.vacancies]
    assert "Бухгалтер" not in titles
    assert "Senior Python-разработчик" not in titles  # требует 6 лет при опыте ~4
    assert titles[0] == "Middle Python-разработчик"  # лучшее совпадение по навыкам и уровню
    assert report.vacancies[0].matched_skills == ["Python", "Django", "PostgreSQL"]
    assert report.level == "Middle"


def test_title_level():
    assert title_level("Junior Python-разработчик") == 1
    assert title_level("Ведущий инженер-программист") == 3
    assert title_level("Стажёр-разработчик") == 0
    assert title_level("Разработчик Python") is None


def test_junior_vacancies_rank_lower_for_middle_candidate():
    source_vacancies = [
        Vacancy("Junior Python-разработчик", "", experience_years=1),
        Vacancy("Middle Python-разработчик", "", experience_years=3),
    ]

    class Source:
        name = url = ""

        def search(self, query):
            return source_vacancies

    report = analyze(middle_resume(skills=[]), Source(), TODAY)

    assert [v.title for v in report.vacancies] == [
        "Middle Python-разработчик",
        "Junior Python-разработчик",
    ]


def test_location_raises_score(vacancy_source):
    def rostov_score(location: str) -> float:
        report = analyze(middle_resume(location=location), vacancy_source, TODAY)
        return next(v.score for v in report.vacancies if v.company == "ООО Бета")

    assert rostov_score("Ростов-на-Дону") == rostov_score("") + 1


def test_salary_uses_vacancies_of_candidate_level():
    vacancies = [
        Vacancy("A", "", salary_min=100000, salary_max=140000, experience_years=3),
        Vacancy("B", "", salary_min=150000, experience_years=3),
        Vacancy("C", "", salary_max=200000, experience_years=4),
        Vacancy("D", "", salary_min=40000, experience_years=0),  # ниже уровня — не учитывается
    ]

    estimate = estimate_salary(vacancies, years=4)

    assert estimate.sample_size == 3
    assert estimate.median == 150000
    assert not estimate.approximate


def test_salary_falls_back_to_all_vacancies_when_level_data_is_scarce():
    vacancies = [Vacancy("A", "", salary_min=50000, experience_years=0)]

    estimate = estimate_salary(vacancies, years=10)

    assert estimate.approximate
    assert estimate.median == 50000


def test_title_falls_back_to_last_position(vacancy_source):
    resume = middle_resume(title="")
    resume.experience[0].position = "Python-разработчик"

    analyze(resume, vacancy_source, TODAY)

    assert vacancy_source.queries[0] == "Python-разработчик"


def test_queries_combine_title_and_skills():
    resume = middle_resume(skills=["python-разработчик", "Django", "Docker", "Celery", "SQL"])

    assert search_queries(resume) == ["Python-разработчик", "Django", "Docker"]


def test_search_by_skills_when_no_title(vacancy_source):
    resume = Resume(full_name="Иван", skills=["Python", "Kubernetes", "Git", "Docker"])

    report = analyze(resume, vacancy_source, TODAY)

    assert sorted(vacancy_source.queries) == ["Git", "Kubernetes", "Python"]
    # «Middle» — совпадает только Python, «Senior» — требует 6 лет опыта
    assert [v.title for v in report.vacancies] == ["Junior Python-разработчик"]


def test_vacancy_without_title_match_is_shown_with_two_skills():
    title = "Python-разработчик"
    skills = ["Python", "Django", "Docker", "Celery"]
    backend = Vacancy("Backend-разработчик", "", text="Python, Django")
    devops = Vacancy("DevOps-инженер", "", text="Docker")

    assert is_relevant(backend, title, skills, matched_skills(skills, backend.text))
    assert not is_relevant(devops, title, skills, matched_skills(skills, devops.text))


def test_single_skill_candidate_needs_one_match():
    vacancy = Vacancy("Программист", "", text="Java")

    assert is_relevant(vacancy, "", ["Java"], ["Java"])


def test_salary_expectations_affect_ranking():
    vacancies = [
        Vacancy("Python-разработчик A", "a", salary_min=80000, salary_max=100000),
        Vacancy("Python-разработчик B", "b", salary_min=180000, salary_max=220000),
    ]

    class Source:
        name = url = ""

        def search(self, query):
            return vacancies

    resume = middle_resume(skills=[], salary_from=170000, salary_to=230000)
    report = analyze(resume, Source(), TODAY)

    assert report.vacancies[0].url == "b"


def test_format_match_compares_each_dimension_separately():
    office_full = ["Полная занятость", "На месте работодателя"]
    remote_full = ["Полная занятость", "Удалённо"]

    assert format_match(remote_full, ["Удалённо"]) is True
    assert format_match(office_full, ["Удалённо"]) is False
    # занятость совпала, но место работы — нет
    assert format_match(office_full, ["Полная занятость", "Удалённо"]) is False
    assert format_match(office_full, ["Полная занятость"]) is True
    assert format_match([], ["Удалённо"]) is None
    assert format_match(office_full, []) is None


def test_selected_format_affects_ranking():
    vacancies = [
        Vacancy("Python-разработчик A", "office",
                formats=["Полная занятость", "На месте работодателя"]),
        Vacancy("Python-разработчик B", "remote", formats=["Полная занятость", "Удалённо"]),
    ]

    class Source:
        name = url = ""

        def search(self, query):
            return vacancies

    report = analyze(middle_resume(skills=[], employment=["Удалённо"]), Source(), TODAY)

    assert [v.url for v in report.vacancies] == ["remote", "office"]
    assert report.vacancies[1].format_match is False
    assert report.format_matches == 1


def test_same_vacancy_in_several_regions_is_shown_once():
    vacancies = [
        Vacancy("Python-разработчик", "1", company="ООО Альфа", region="Москва"),
        Vacancy("Python-разработчик", "2", company="ООО Альфа", region="Казань"),
        Vacancy("Python-разработчик", "3", company="ООО Бета"),
    ]

    class Source:
        name = url = ""

        def search(self, query):
            return vacancies

    report = analyze(middle_resume(skills=[]), Source(), TODAY)

    assert sorted(v.url for v in report.vacancies) == ["1", "3"]


def test_expectations_verdict():
    market = SalaryEstimate(median=150000, low=120000, high=180000, sample_size=5,
                            approximate=False)

    assert "выше рынка" in expectations_verdict(Resume(salary_from=250000), market)
    assert "ниже рынка" in expectations_verdict(Resume(salary_to=90000), market)
    assert "соответствуют" in expectations_verdict(
        Resume(salary_from=140000, salary_to=170000), market
    )
    assert expectations_verdict(Resume(), market) == ""


def test_partial_source_failure_keeps_other_results():
    class FlakySource:
        name = url = ""

        def search(self, query):
            if query == "Django":
                raise VacancySourceError("timeout")
            return [Vacancy("Python-разработчик", "1")]

    report = analyze(middle_resume(), FlakySource(), TODAY)

    assert report.message == ""
    assert len(report.vacancies) == 1


def test_no_query_means_no_search(vacancy_source):
    report = analyze(Resume(full_name="Иван"), vacancy_source, TODAY)

    assert vacancy_source.queries == []
    assert "Укажите желаемую должность" in report.message


def test_source_error_is_reported():
    class BrokenSource:
        name = "Сломанный"
        url = ""

        def search(self, query):
            raise VacancySourceError("Сервис недоступен.")

    report = analyze(middle_resume(), BrokenSource(), TODAY)

    assert report.message == "Сервис «Сломанный» недоступен."
    assert report.vacancies == []

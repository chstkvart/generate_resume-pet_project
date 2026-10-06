"""Подбор подходящих вакансий и оценка ожидаемой зарплаты кандидата."""

import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date

from app.choices import EMPLOYMENT_DIMENSIONS
from app.models import Resume
from app.services.career import (
    format_duration,
    level_for,
    level_rank,
    total_experience_months,
)
from app.services.vacancy_sources import Vacancy, VacancySource, VacancySourceError

MAX_RESULTS = 10
MIN_TITLE_SCORE = 0.5  # доля слов желаемой должности, найденных в названии вакансии
SALARY_ROUNDING = 5000
MIN_SALARY_SAMPLES = 3
SKILL_QUERIES = 3  # сколько навыков искать отдельными запросами
MIN_SKILL_MATCHES = 2  # вакансия без совпадения по названию показывается от 2 общих навыков
MAX_SCORED_SKILLS = 6
FORMAT_MATCH_BONUS = 2

WORD_RE = re.compile(r"[a-zа-яё0-9+#]+")

# основы слов в названии вакансии → ранг уровня из career.LEVELS
TITLE_LEVEL_STEMS = {
    "стаж": 0, "intern": 0, "практикант": 0,
    "junior": 1, "младш": 1,
    "middle": 2,
    "senior": 3, "старш": 3, "ведущ": 3, "главн": 3, "lead": 3, "лид": 3,
}


@dataclass
class VacancyMatch:
    title: str
    url: str
    company: str
    region: str
    salary_min: int | None
    salary_max: int | None
    experience_years: int | None
    matched_skills: list[str]
    formats: list[str]
    format_match: bool | None  # совпадает ли формат работы с отмеченным в форме
    score: float


@dataclass
class SalaryEstimate:
    median: int
    low: int
    high: int
    sample_size: int
    approximate: bool  # True — не хватило вакансий нужного уровня, учтены все подходящие


@dataclass
class MarketReport:
    queries: list[str] = field(default_factory=list)
    experience: str = ""
    level: str = ""
    salary: SalaryEstimate | None = None
    expectations: str = ""  # сравнение зарплатных ожиданий с рынком
    vacancies: list[VacancyMatch] = field(default_factory=list)
    total_found: int = 0
    format_matches: int = 0  # сколько подходящих вакансий совпадают по формату работы
    source_name: str = ""
    source_url: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower().replace("ё", "е"))


def _stem(word: str) -> str:
    """Грубое отсечение окончаний: «разработчика» и «разработчик» дают одну основу."""
    return word[: max(4, len(word) - 2)]


def title_score(query: str, title: str) -> float:
    query_stems = {_stem(w) for w in _words(query) if len(w) > 1}
    if not query_stems:
        return 0.0
    title_words = _words(title)
    found = sum(1 for stem in query_stems if any(w.startswith(stem) for w in title_words))
    return found / len(query_stems)


def matched_skills(skills: list[str], text: str) -> list[str]:
    normalized = text.lower().replace("ё", "е")
    found = []
    for skill in skills:
        pattern = re.escape(skill.lower().replace("ё", "е"))
        if re.search(rf"(?<![\w+#]){pattern}(?![\w+#])", normalized):
            found.append(skill)
    return found


def _location_matches(location: str, vacancy: Vacancy) -> bool:
    stems = {_stem(w) for w in _words(location) if len(w) > 2}
    vacancy_words = _words(f"{vacancy.region} {vacancy.address}")
    return any(w.startswith(stem) for stem in stems for w in vacancy_words)


def _level_window(years: float) -> tuple[float, float]:
    """Диапазон требуемого опыта, который считается «своим» уровнем кандидата."""
    return max(0.0, years - 2), years + 1


def title_level(title: str) -> int | None:
    """Уровень, явно указанный в названии вакансии («Junior», «Ведущий» и т.п.)."""
    for word in _words(title):
        for stem, rank in TITLE_LEVEL_STEMS.items():
            if word.startswith(stem):
                return rank
    return None


def _level_bonus(title: str, candidate_rank: int) -> float:
    rank = title_level(title)
    if rank is None:
        return 0
    if rank == candidate_rank or (candidate_rank == 0 and rank == 1):
        return 1
    return -1.5 if rank < candidate_rank else -1


def _round(value: float) -> int:
    return int(round(value / SALARY_ROUNDING) * SALARY_ROUNDING)


def estimate_salary(vacancies: list[Vacancy], years: float) -> SalaryEstimate | None:
    low, high = _level_window(years)
    in_level = [
        v.salary_mid for v in vacancies
        if v.salary_mid and (v.experience_years is None or low <= v.experience_years <= high)
    ]
    approximate = len(in_level) < MIN_SALARY_SAMPLES
    salaries = sorted(v.salary_mid for v in vacancies if v.salary_mid) if approximate else in_level
    if not salaries:
        return None

    if len(salaries) >= 2:
        q1, _, q3 = statistics.quantiles(salaries, n=4, method="inclusive")
    else:
        q1 = q3 = salaries[0]
    return SalaryEstimate(
        median=_round(statistics.median(salaries)),
        low=_round(q1),
        high=_round(q3),
        sample_size=len(salaries),
        approximate=approximate,
    )


def desired_title(resume: Resume) -> str:
    if resume.title:
        return resume.title
    positions = [e.position for e in resume.experience if e.position]
    return positions[0] if positions else ""


def search_queries(resume: Resume) -> list[str]:
    """Запрос по должности плюс отдельные запросы по первым навыкам.

    API ищет вакансии, содержащие все слова запроса, поэтому навыки ищутся по одному —
    так находятся вакансии, где навык упомянут только в требованиях.
    """
    queries = [desired_title(resume), *resume.skills[:SKILL_QUERIES]]
    unique: dict[str, str] = {}
    for query in queries:
        if query and query.lower() not in unique:
            unique[query.lower()] = query
    return list(unique.values())


def _collect(source: VacancySource, queries: list[str]) -> tuple[list[Vacancy], bool]:
    """Выполняет запросы параллельно и объединяет результаты без дублей.

    Возвращает вакансии и признак того, что все запросы завершились ошибкой.
    """
    def run(query: str) -> list[Vacancy] | None:
        try:
            return source.search(query)
        except VacancySourceError:
            return None

    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        results = list(pool.map(run, queries))

    # одна и та же вакансия компании часто размещается в нескольких регионах под разными URL
    unique: dict[tuple[str, str], Vacancy] = {}
    for vacancies in results:
        for vacancy in vacancies or []:
            key = (vacancy.title.strip().lower(), vacancy.company.strip().lower())
            if not vacancy.company:
                key = (key[0], vacancy.url)
            unique.setdefault(key, vacancy)
    return list(unique.values()), all(r is None for r in results)


def min_skill_matches(skills: list[str]) -> int:
    return min(MIN_SKILL_MATCHES, len(skills))


def is_relevant(vacancy: Vacancy, title: str, skills: list[str], matched: list[str]) -> bool:
    """Вакансия подходит, если совпадает название должности или несколько навыков."""
    if title and title_score(title, vacancy.title) >= MIN_TITLE_SCORE:
        return True
    return bool(skills) and len(matched) >= min_skill_matches(skills)


def _overlaps_expectations(vacancy: Vacancy, resume: Resume) -> bool | None:
    """Пересекается ли вилка вакансии с зарплатными ожиданиями; None — сравнить нельзя."""
    if not (resume.salary_from or resume.salary_to):
        return None
    if not (vacancy.salary_min or vacancy.salary_max):
        return None
    vacancy_low = vacancy.salary_min or vacancy.salary_max
    vacancy_high = vacancy.salary_max or vacancy.salary_min
    expected_low = resume.salary_from or 0
    expected_high = resume.salary_to or float("inf")
    return vacancy_high >= expected_low and vacancy_low <= expected_high


def format_match(vacancy_formats: list[str], desired: list[str]) -> bool | None:
    """Сравнивает формат работы по каждому признаку (место работы, занятость) отдельно.

    False — хотя бы по одному признаку вакансия не подходит, True — все известные признаки
    совпали, None — сравнить не с чем.
    """
    result = None
    for dimension in EMPLOYMENT_DIMENSIONS:
        wanted = dimension.intersection(desired)
        offered = dimension.intersection(vacancy_formats)
        if not wanted or not offered:
            continue
        if not wanted & offered:
            return False
        result = True
    return result


def expectations_verdict(resume: Resume, salary: SalaryEstimate | None) -> str:
    if not salary or not (resume.salary_from or resume.salary_to):
        return ""
    expected_low = resume.salary_from or resume.salary_to
    expected_high = resume.salary_to or resume.salary_from
    if expected_low > salary.high:
        return "Ваши ожидания выше рынка для вашего уровня."
    if expected_high < salary.low:
        return "Ваши ожидания ниже рынка — можно просить больше."
    return "Ваши ожидания соответствуют рынку."


def analyze(resume: Resume, source: VacancySource, today: date | None = None) -> MarketReport:
    months = total_experience_months(resume.experience, today)
    years = months / 12
    rank = level_rank(months)
    title = desired_title(resume)
    report = MarketReport(
        queries=search_queries(resume),
        experience=format_duration(months),
        level=level_for(months),
        source_name=source.name,
        source_url=source.url,
    )
    if not report.queries:
        report.message = "Укажите желаемую должность или навыки, чтобы подобрать вакансии."
        return report

    found, failed = _collect(source, report.queries)
    if failed:
        report.message = f"Сервис «{source.name}» недоступен."
        return report

    candidates = []
    for vacancy in found:
        matched = matched_skills(resume.skills, vacancy.text)
        if is_relevant(vacancy, title, resume.skills, matched):
            candidates.append((vacancy, matched))

    report.salary = estimate_salary([v for v, _ in candidates], years)
    report.expectations = expectations_verdict(resume, report.salary)

    # вакансии, требующие заметно больше опыта, чем есть у кандидата, не предлагаем
    suitable = [
        (vacancy, matched) for vacancy, matched in candidates
        if vacancy.experience_years is None or vacancy.experience_years <= years + 1
    ]
    report.total_found = len(suitable)

    low, high = _level_window(years)
    matches = []
    for vacancy, skills in suitable:
        score = min(len(skills), MAX_SCORED_SKILLS)
        if title:
            score += 3 * title_score(title, vacancy.title)
        if resume.location and _location_matches(resume.location, vacancy):
            score += 1
        if vacancy.experience_years is not None and low <= vacancy.experience_years <= high:
            score += 1
        score += _level_bonus(vacancy.title, rank)
        overlap = _overlaps_expectations(vacancy, resume)
        if overlap is not None:
            score += 1 if overlap else -1
        fits_format = format_match(vacancy.formats, resume.employment)
        if fits_format is not None:
            score += FORMAT_MATCH_BONUS if fits_format else -FORMAT_MATCH_BONUS
            report.format_matches += fits_format
        matches.append(VacancyMatch(
            title=vacancy.title,
            url=vacancy.url,
            company=vacancy.company,
            region=vacancy.region,
            salary_min=vacancy.salary_min,
            salary_max=vacancy.salary_max,
            experience_years=vacancy.experience_years,
            matched_skills=skills,
            formats=vacancy.formats,
            format_match=fits_format,
            score=round(score, 2),
        ))
    matches.sort(key=lambda m: m.score, reverse=True)
    report.vacancies = matches[:MAX_RESULTS]

    if not report.vacancies:
        report.message = "Подходящих вакансий не найдено. Попробуйте изменить должность или навыки."
    return report

"""Преобразование данных HTML-формы в модель резюме с валидацией."""

import re
from dataclasses import dataclass, field
from itertools import zip_longest

from werkzeug.datastructures import FileStorage, ImmutableMultiDict, MultiDict

from app.choices import EMPLOYMENT_TYPES, ENGLISH_LEVELS
from app.models import Education, Experience, Resume
from app.services.photo import PhotoError, process_photo

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
YEAR_RE = re.compile(r"^\d{4}$")


@dataclass
class ParseResult:
    resume: Resume
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _split_list(value: str | None) -> list[str]:
    """Разбивает строку по запятым и переносам строк."""
    items = re.split(r"[,\n]", value or "")
    return [item.strip() for item in items if item.strip()]


def _parse_salary(value: str | None) -> int | None:
    """«150 000» → 150000. Нечисловой ввод вызывает ValueError."""
    digits = re.sub(r"\s", "", value or "")
    if not digits:
        return None
    if not digits.isdigit():
        raise ValueError(value)
    return int(digits)


def _parse_employment(form: MultiDict) -> list[str]:
    """Оставляет только допустимые варианты в порядке, заданном в EMPLOYMENT_TYPES."""
    selected = set(form.getlist("employment"))
    return [option for option in EMPLOYMENT_TYPES if option in selected]


def _parse_experience(form: MultiDict) -> list[Experience]:
    rows = zip_longest(
        form.getlist("experience_company"),
        form.getlist("experience_position"),
        form.getlist("experience_start"),
        form.getlist("experience_end"),
        form.getlist("experience_description"),
        form.getlist("experience_current"),
        fillvalue="",
    )
    entries = []
    for company, position, start, end, description, current in rows:
        is_current = current == "1"
        entries.append(Experience(
            company=_clean(company),
            position=_clean(position),
            start=_clean(start),
            end="" if is_current else _clean(end),
            description=_clean(description),
            current=is_current,
        ))
    return [e for e in entries if not e.is_empty()]


def _validate_experience(items: list[Experience]) -> list[str]:
    errors = []
    for item in items:
        name = item.company or item.position or "без названия"
        for value in (item.start, item.end):
            if value and not MONTH_RE.match(value):
                errors.append(f"Опыт «{name}»: дата должна быть в формате ГГГГ-ММ.")
                break
        else:
            if item.start and item.end and item.end < item.start:
                errors.append(f"Опыт «{name}»: дата окончания раньше даты начала.")
    return errors


def _parse_education(form: MultiDict) -> list[Education]:
    rows = zip_longest(
        form.getlist("education_institution"),
        form.getlist("education_degree"),
        form.getlist("education_start"),
        form.getlist("education_end"),
        fillvalue="",
    )
    entries = [Education(*(_clean(v) for v in row)) for row in rows]
    return [e for e in entries if not e.is_empty()]


def _validate_education(items: list[Education]) -> list[str]:
    errors = []
    for item in items:
        name = item.institution or item.degree or "без названия"
        if any(value and not YEAR_RE.match(value) for value in (item.start, item.end)):
            errors.append(f"Образование «{name}»: год должен состоять из четырёх цифр.")
        elif item.start and item.end and item.end < item.start:
            errors.append(f"Образование «{name}»: год окончания раньше года начала.")
    return errors


def parse_resume_form(
    form: MultiDict | ImmutableMultiDict, files: MultiDict | ImmutableMultiDict
) -> ParseResult:
    resume = Resume(
        full_name=_clean(form.get("full_name")),
        title=_clean(form.get("title")),
        email=_clean(form.get("email")),
        phone=_clean(form.get("phone")),
        location=_clean(form.get("location")),
        website=_clean(form.get("website")),
        summary=_clean(form.get("summary")),
        employment=_parse_employment(form),
        skills=_split_list(form.get("skills")),
        english_level=_clean(form.get("english_level")),
        experience=_parse_experience(form),
        education=_parse_education(form),
    )
    result = ParseResult(resume=resume)

    if not resume.full_name:
        result.errors.append("Укажите имя и фамилию.")
    if resume.email and not EMAIL_RE.match(resume.email):
        result.errors.append("Некорректный адрес электронной почты.")
    try:
        resume.salary_from = _parse_salary(form.get("salary_from"))
        resume.salary_to = _parse_salary(form.get("salary_to"))
    except ValueError:
        result.errors.append("Зарплатные ожидания должны быть указаны числом.")
    else:
        if resume.salary_from and resume.salary_to and resume.salary_from > resume.salary_to:
            result.errors.append("Зарплатные ожидания: «от» не может быть больше «до».")
    if resume.english_level and resume.english_level not in ENGLISH_LEVELS:
        result.errors.append("Выберите уровень английского из списка.")
        resume.english_level = ""
    result.errors.extend(_validate_experience(resume.experience))
    result.errors.extend(_validate_education(resume.education))

    photo: FileStorage | None = files.get("photo")
    if photo and photo.filename:
        try:
            resume.photo = process_photo(photo.stream)
        except PhotoError as exc:
            result.errors.append(str(exc))

    return result

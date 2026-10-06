"""Фиксированные варианты выбора в форме резюме."""

REMOTE = "Удалённо"
ON_SITE = "На месте работодателя"
FULL_TIME = "Полная занятость"
PART_TIME = "Частичная занятость"
SIDE_JOB = "Подработка"

EMPLOYMENT_TYPES = (FULL_TIME, PART_TIME, SIDE_JOB, REMOTE, ON_SITE)

# Независимые признаки формата работы: вакансия сравнивается с кандидатом по каждому отдельно
EMPLOYMENT_DIMENSIONS = (
    frozenset({REMOTE, ON_SITE}),
    frozenset({FULL_TIME, PART_TIME, SIDE_JOB}),
)

ENGLISH_LEVELS = {
    "A1": "A1 — начальный",
    "A2": "A2 — элементарный",
    "B1": "B1 — средний",
    "B2": "B2 — выше среднего",
    "C1": "C1 — продвинутый",
    "C2": "C2 — в совершенстве",
}

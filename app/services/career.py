"""Подсчёт стажа кандидата и определение уровня."""

from datetime import date

from app.models import Experience

LEVELS = (  # (стаж от, в месяцах; название уровня); индекс — ранг уровня
    (0, "Стажёр / Junior"),
    (12, "Junior"),
    (36, "Middle"),
    (72, "Senior"),
)


def _month_index(value: str) -> int | None:
    """«2022-03» → порядковый номер месяца."""
    year, _, month = value.partition("-")
    if not (year.isdigit() and month.isdigit()):
        return None
    return int(year) * 12 + int(month) - 1


def total_experience_months(items: list[Experience], today: date | None = None) -> int:
    """Суммарный стаж в месяцах; пересекающиеся периоды учитываются один раз."""
    today = today or date.today()
    current_month = today.year * 12 + today.month - 1

    periods = []
    for item in items:
        start = _month_index(item.start)
        end = current_month if item.current else _month_index(item.end)
        if start is None or end is None or end < start:
            continue
        periods.append((start, min(end, current_month)))

    total = 0
    last_end = -1
    for start, end in sorted(periods):
        start = max(start, last_end + 1)
        if end >= start:
            total += end - start + 1
            last_end = end
    return total


def level_rank(months: int) -> int:
    return max(rank for rank, (threshold, _) in enumerate(LEVELS) if months >= threshold)


def level_for(months: int) -> str:
    return LEVELS[level_rank(months)][1]


def format_duration(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} г.")
    if rest or not years:
        parts.append(f"{rest} мес.")
    return " ".join(parts)

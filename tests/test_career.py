from datetime import date

from app.models import Experience
from app.services.career import format_duration, level_for, total_experience_months

TODAY = date(2026, 10, 5)


def test_single_period_counts_both_months_inclusive():
    items = [Experience(start="2025-01", end="2025-12")]

    assert total_experience_months(items, TODAY) == 12


def test_current_job_counts_until_today():
    items = [Experience(start="2026-01", current=True)]

    assert total_experience_months(items, TODAY) == 10


def test_overlapping_periods_are_counted_once():
    items = [
        Experience(start="2020-01", end="2020-12"),
        Experience(start="2020-07", end="2021-06"),
    ]

    assert total_experience_months(items, TODAY) == 18


def test_entries_without_dates_are_ignored():
    items = [Experience(company="Без дат"), Experience(start="2024-01")]

    assert total_experience_months(items, TODAY) == 0


def test_levels():
    assert level_for(0) == "Стажёр / Junior"
    assert level_for(24) == "Junior"
    assert level_for(40) == "Middle"
    assert level_for(100) == "Senior"


def test_format_duration():
    assert format_duration(0) == "0 мес."
    assert format_duration(12) == "1 г."
    assert format_duration(38) == "3 г. 2 мес."

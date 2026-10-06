from io import BytesIO

from werkzeug.datastructures import FileStorage, MultiDict

from app.services.form_parser import parse_resume_form


def make_form(**overrides) -> MultiDict:
    data = MultiDict({"full_name": "Иван Петров"})
    for key, value in overrides.items():
        if isinstance(value, list):
            data.setlist(key, value)
        else:
            data[key] = value
    return data


def test_valid_minimal_form():
    result = parse_resume_form(make_form(), MultiDict())

    assert result.is_valid
    assert result.resume.full_name == "Иван Петров"
    assert result.resume.photo is None


def test_full_name_is_required():
    result = parse_resume_form(make_form(full_name="   "), MultiDict())

    assert not result.is_valid
    assert "Укажите имя и фамилию." in result.errors


def test_invalid_email():
    result = parse_resume_form(make_form(email="not-an-email"), MultiDict())

    assert not result.is_valid


def test_skills_split_by_commas_and_newlines():
    result = parse_resume_form(make_form(skills="Python, Flask\nSQL,, "), MultiDict())

    assert result.resume.skills == ["Python", "Flask", "SQL"]


def test_empty_experience_entries_are_skipped():
    form = make_form(
        experience_company=["ООО Ромашка", ""],
        experience_position=["Разработчик", ""],
        experience_start=["2020-01", ""],
        experience_end=["2023-05", ""],
        experience_description=["- Писал код", ""],
    )

    result = parse_resume_form(form, MultiDict())

    assert len(result.resume.experience) == 1
    assert result.resume.experience[0].company == "ООО Ромашка"


def test_current_job_ignores_end_date():
    form = make_form(
        experience_company=["ООО Ромашка", "ООО Лютик"],
        experience_start=["2022-03", "2020-01"],
        experience_end=["2023-01", "2021-12"],
        experience_current=["1", "0"],
    )

    result = parse_resume_form(form, MultiDict())

    current, past = result.resume.experience
    assert current.current and current.end == ""
    assert not past.current and past.end == "2021-12"


def test_end_before_start_is_rejected():
    form = make_form(
        experience_company=["ООО Ромашка"],
        experience_start=["2022-03"],
        experience_end=["2021-01"],
    )

    result = parse_resume_form(form, MultiDict())

    assert not result.is_valid
    assert "раньше даты начала" in result.errors[0]


def test_invalid_month_format_is_rejected():
    form = make_form(experience_company=["ООО Ромашка"], experience_start=["март 2022"])

    result = parse_resume_form(form, MultiDict())

    assert not result.is_valid


def test_education_end_before_start_is_rejected():
    form = make_form(
        education_institution=["МГУ"],
        education_start=["2020"],
        education_end=["2016"],
    )

    result = parse_resume_form(form, MultiDict())

    assert not result.is_valid
    assert "раньше года начала" in result.errors[0]


def test_education_invalid_year_is_rejected():
    form = make_form(education_institution=["МГУ"], education_start=["двадцатый"])

    result = parse_resume_form(form, MultiDict())

    assert not result.is_valid


def test_employment_keeps_only_known_options_in_fixed_order():
    form = make_form(employment=["Удалённо", "Неизвестный вариант", "Полная занятость"])

    result = parse_resume_form(form, MultiDict())

    assert result.resume.employment == ["Полная занятость", "Удалённо"]


def test_english_level_from_list():
    result = parse_resume_form(make_form(english_level="B2"), MultiDict())

    assert result.is_valid
    assert result.resume.english_level == "B2"


def test_unknown_english_level_is_rejected():
    result = parse_resume_form(make_form(english_level="Z9"), MultiDict())

    assert not result.is_valid
    assert result.resume.english_level == ""


def test_salary_expectations():
    result = parse_resume_form(make_form(salary_from="150 000", salary_to="200000"), MultiDict())

    assert result.is_valid
    assert (result.resume.salary_from, result.resume.salary_to) == (150000, 200000)


def test_salary_from_greater_than_to_is_rejected():
    result = parse_resume_form(make_form(salary_from="200000", salary_to="100000"), MultiDict())

    assert not result.is_valid


def test_non_numeric_salary_is_rejected():
    result = parse_resume_form(make_form(salary_from="много"), MultiDict())

    assert not result.is_valid


def test_photo_is_processed(photo_bytes):
    files = MultiDict({"photo": FileStorage(BytesIO(photo_bytes), filename="me.png")})

    result = parse_resume_form(make_form(), files)

    assert result.is_valid
    assert result.resume.photo.startswith(b"\xff\xd8")  # сигнатура JPEG


def test_invalid_photo_reports_error():
    files = MultiDict({"photo": FileStorage(BytesIO(b"not an image"), filename="me.png")})

    result = parse_resume_form(make_form(), files)

    assert not result.is_valid
    assert result.resume.photo is None

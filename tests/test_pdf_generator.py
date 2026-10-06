from io import BytesIO

from reportlab.platypus import KeepTogether, Paragraph

from app.models import Education, Experience, Resume
from app.services.pdf_generator import _section, build_pdf
from app.services.photo import process_photo


def test_section_heading_is_kept_with_first_block():
    first = [Paragraph("первый")]
    second = [Paragraph("второй")]

    flowables = _section("Опыт работы", [first, second])

    assert len(flowables) == 2
    assert all(isinstance(f, KeepTogether) for f in flowables)
    heading_block = flowables[0]._content
    assert heading_block[-1] is first[0]
    assert flowables[1]._content == second


def test_minimal_resume_builds_pdf():
    pdf = build_pdf(Resume(full_name="Иван Петров"))

    assert pdf.startswith(b"%PDF")


def test_full_resume_builds_pdf(photo_bytes):
    resume = Resume(
        full_name="Иван Петров",
        title="Python-разработчик",
        email="ivan@example.com",
        phone="+7 900 000-00-00",
        location="Москва",
        website="github.com/ivan",
        summary="Люблю писать чистый код.\n- Пункт <со спецсимволами> & прочим",
        skills=["Python", "Flask"],
        employment=["Полная занятость", "Удалённо"],
        salary_from=150000,
        salary_to=200000,
        english_level="B2",
        experience=[
            Experience("ООО Ромашка", "Разработчик", "2023-01", "", "- Сервис", current=True),
            Experience("ООО Лютик", "Стажёр", "2020-06", "2022-12", "- Сделал сервис\n- Тесты"),
        ],
        education=[Education("МГУ", "Прикладная математика", "2016", "2020")],
        photo=process_photo(BytesIO(photo_bytes)),
    )

    pdf = build_pdf(resume)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000

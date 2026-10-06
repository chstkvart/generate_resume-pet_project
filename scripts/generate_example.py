"""Генерирует пример резюме в docs/example.pdf: python -m scripts.generate_example"""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from app.models import Education, Experience, Resume
from app.services.pdf_generator import build_pdf
from app.services.photo import process_photo

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "example.pdf"


def placeholder_photo() -> bytes:
    image = Image.new("RGB", (600, 750), "#d9dee5")
    draw = ImageDraw.Draw(image)
    draw.ellipse((200, 150, 400, 350), fill="#9aa6b5")
    draw.ellipse((100, 400, 500, 900), fill="#9aa6b5")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return process_photo(buffer)


def example_resume() -> Resume:
    return Resume(
        full_name="Иван Петров",
        title="Python-разработчик",
        email="ivan.petrov@example.com",
        phone="+7 900 123-45-67",
        location="Москва",
        website="github.com/ivan-petrov",
        summary=(
            "Backend-разработчик с опытом 3+ года. Проектирую REST API, "
            "работаю с PostgreSQL и Docker, покрываю код тестами."
        ),
        skills=["Python", "Flask", "FastAPI", "PostgreSQL", "Docker", "Git", "pytest"],
        employment=["Полная занятость", "Удалённо"],
        salary_from=180000,
        salary_to=230000,
        english_level="B2",
        experience=[
            Experience(
                company="ООО «Технологии»",
                position="Python-разработчик",
                start="2022-03",
                current=True,
                description=(
                    "- Разработал сервис обработки заказов на FastAPI\n"
                    "- Сократил время ответа API на 40% за счёт кэширования\n"
                    "- Настроил CI/CD на GitHub Actions"
                ),
            ),
            Experience(
                company="Студия «Веб»",
                position="Junior Python-разработчик",
                start="2020-07",
                end="2022-02",
                description="- Поддержка и развитие внутренних сервисов на Django",
            ),
        ],
        education=[
            Education(
                institution="МГТУ им. Н. Э. Баумана",
                degree="Бакалавр, программная инженерия",
                start="2016",
                end="2020",
            )
        ],
        photo=placeholder_photo(),
    )


if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_bytes(build_pdf(example_resume()))
    print(f"Сохранено: {OUTPUT}")

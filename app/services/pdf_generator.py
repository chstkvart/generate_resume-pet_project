"""Генерация PDF-файла резюме с помощью ReportLab."""

from functools import cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.choices import ENGLISH_LEVELS
from app.models import Education, Experience, Resume

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"

ACCENT = colors.HexColor("#1f3a5f")
MUTED = colors.HexColor("#555555")

PAGE_MARGIN = 18 * mm
FRAME_PADDING = 6  # внутренний отступ фрейма SimpleDocTemplate по умолчанию
PHOTO_WIDTH = 32 * mm
PHOTO_HEIGHT = 40 * mm
BULLET_PREFIXES = ("- ", "• ", "* ")
MONTHS = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)


@cache
def _register_fonts() -> None:
    """ReportLab-шрифты по умолчанию не поддерживают кириллицу, поэтому подключаем DejaVu."""
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, FONTS_DIR / "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFontFamily(FONT_REGULAR, normal=FONT_REGULAR, bold=FONT_BOLD)


@cache
def _styles() -> dict[str, ParagraphStyle]:
    _register_fonts()
    base = ParagraphStyle("base", fontName=FONT_REGULAR, fontSize=10, leading=14)
    return {
        "base": base,
        "name": ParagraphStyle("name", base, fontName=FONT_BOLD, fontSize=22, leading=26),
        "title": ParagraphStyle("title", base, fontSize=13, leading=18, textColor=ACCENT),
        "contacts": ParagraphStyle("contacts", base, fontSize=9.5, textColor=MUTED),
        "section": ParagraphStyle(
            "section", base, fontName=FONT_BOLD, fontSize=12, leading=16,
            textColor=ACCENT, spaceBefore=10,
        ),
        "entry_title": ParagraphStyle("entry_title", base, fontName=FONT_BOLD),
        "entry_subtitle": ParagraphStyle("entry_subtitle", base, textColor=MUTED),
        "dates": ParagraphStyle("dates", base, fontSize=9.5, textColor=MUTED, alignment=TA_RIGHT),
        "bullet": ParagraphStyle("bullet", base, leftIndent=10, bulletIndent=0),
    }


def _text(value: str) -> str:
    """Экранирует пользовательский ввод: Paragraph интерпретирует XML-разметку."""
    return escape(value)


def _format_month(value: str) -> str:
    """«2022-03» → «Март 2022». Значения в другом формате выводятся как есть."""
    year, _, month = value.partition("-")
    if year.isdigit() and month.isdigit() and 1 <= int(month) <= 12:
        return f"{MONTHS[int(month) - 1]} {year}"
    return value


def _period(start: str, end: str) -> str:
    if start and end:
        return f"{start} — {end}"
    return start or end


def _money(value: int) -> str:
    return f"{value:,}".replace(",", "\u00a0")


def _salary_range(low: int | None, high: int | None) -> str:
    if low and high:
        return f"{_money(low)} – {_money(high)} ₽" if low != high else f"{_money(low)} ₽"
    if low:
        return f"от {_money(low)} ₽"
    if high:
        return f"до {_money(high)} ₽"
    return ""


def _experience_period(item: Experience) -> str:
    end = "по настоящее время" if item.current else _format_month(item.end)
    return _period(_format_month(item.start), end)


def _section(title: str, blocks: list[list[Flowable]]) -> list[Flowable]:
    """Каждый блок не разрывается между страницами, а заголовок раздела
    всегда переносится вместе с первым блоком."""
    heading = [
        Paragraph(_text(title.upper()), _styles()["section"]),
        HRFlowable(width="100%", thickness=0.8, color=ACCENT, spaceBefore=2, spaceAfter=6),
    ]
    first, *rest = blocks
    return [KeepTogether(heading + first), *(KeepTogether(block) for block in rest)]


def _multiline(text: str) -> list[Flowable]:
    """Строки, начинающиеся с «-», «•» или «*», превращаются в маркированный список."""
    styles = _styles()
    flowables: list[Flowable] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(BULLET_PREFIXES):
            flowables.append(Paragraph(_text(line[2:].strip()), styles["bullet"], bulletText="•"))
        else:
            flowables.append(Paragraph(_text(line), styles["base"]))
    return flowables


def _entry_header(title: str, subtitle: str, dates: str, width: float) -> Table:
    styles = _styles()
    left: list[Flowable] = [Paragraph(_text(title), styles["entry_title"])]
    if subtitle:
        left.append(Paragraph(_text(subtitle), styles["entry_subtitle"]))
    table = Table(
        [[left, Paragraph(_text(dates), styles["dates"])]],
        colWidths=[width * 0.6, width * 0.4],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def _header(resume: Resume, width: float) -> list[Flowable]:
    styles = _styles()
    info: list[Flowable] = [Paragraph(_text(resume.full_name), styles["name"])]
    if resume.title:
        info.append(Paragraph(_text(resume.title), styles["title"]))
    if resume.employment:
        employment = ", ".join(option.lower() for option in resume.employment)
        info.append(Paragraph(_text(f"Формат работы: {employment}"), styles["contacts"]))
    salary = _salary_range(resume.salary_from, resume.salary_to)
    if salary:
        info.append(Paragraph(_text(f"Зарплатные ожидания: {salary}"), styles["contacts"]))
    if resume.contacts:
        info.append(Spacer(1, 4))
        info.append(Paragraph(_text("  ·  ".join(resume.contacts)), styles["contacts"]))

    if not resume.photo:
        return info

    photo = Image(BytesIO(resume.photo), width=PHOTO_WIDTH, height=PHOTO_HEIGHT)
    gap = 6 * mm
    table = Table([[photo, info]], colWidths=[PHOTO_WIDTH + gap, width - PHOTO_WIDTH - gap])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [table]


def _experience(items: list[Experience], width: float) -> list[Flowable]:
    blocks = [
        [
            _entry_header(item.position or item.company, item.company if item.position else "",
                          _experience_period(item), width),
            *_multiline(item.description),
            Spacer(1, 8),
        ]
        for item in items
    ]
    return _section("Опыт работы", blocks)


def _education(items: list[Education], width: float) -> list[Flowable]:
    blocks = [
        [
            _entry_header(item.institution or item.degree, item.degree if item.institution else "",
                          _period(item.start, item.end), width),
            Spacer(1, 6),
        ]
        for item in items
    ]
    return _section("Образование", blocks)


def build_pdf(resume: Resume) -> bytes:
    """Собирает резюме и возвращает содержимое PDF-файла."""
    styles = _styles()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN,
        title=f"Резюме — {resume.full_name}",
        author=resume.full_name,
    )
    width = doc.width - 2 * FRAME_PADDING

    story: list[Flowable] = _header(resume, width)
    if resume.summary:
        story += _section("О себе", [_multiline(resume.summary)])
    if resume.experience:
        story += _experience(resume.experience, width)
    if resume.education:
        story += _education(resume.education, width)
    if resume.skills:
        skills = Paragraph(_text(", ".join(resume.skills)), styles["base"])
        story += _section("Навыки", [[skills]])
    if resume.english_level:
        english = f"Английский: {ENGLISH_LEVELS[resume.english_level]}"
        story += _section("Языки", [[Paragraph(_text(english), styles["base"])]])

    doc.build(story)
    return buffer.getvalue()

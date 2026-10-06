"""Доменные модели резюме."""

from dataclasses import dataclass, field


@dataclass
class Experience:
    company: str = ""
    position: str = ""
    start: str = ""  # формат YYYY-MM
    end: str = ""  # формат YYYY-MM
    description: str = ""
    current: bool = False

    def is_empty(self) -> bool:
        return not any((self.company, self.position, self.start, self.end, self.description))


@dataclass
class Education:
    institution: str = ""
    degree: str = ""
    start: str = ""
    end: str = ""

    def is_empty(self) -> bool:
        return not any((self.institution, self.degree, self.start, self.end))


@dataclass
class Resume:
    full_name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    summary: str = ""
    salary_from: int | None = None  # зарплатные ожидания, ₽
    salary_to: int | None = None
    employment: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    english_level: str = ""  # ключ из choices.ENGLISH_LEVELS
    experience: list[Experience] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    photo: bytes | None = None

    @property
    def contacts(self) -> list[str]:
        return [c for c in (self.email, self.phone, self.location, self.website) if c]

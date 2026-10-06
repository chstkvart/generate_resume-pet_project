"""Проверка и подготовка фотографии для резюме."""

from io import BytesIO
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
TARGET_SIZE = (600, 750)  # соотношение сторон 4:5


class PhotoError(ValueError):
    """Загруженный файл не подходит в качестве фотографии."""


def process_photo(stream: BinaryIO) -> bytes:
    """Проверяет изображение, обрезает его до 4:5 и возвращает JPEG."""
    try:
        image = Image.open(stream)
        image_format = image.format
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise PhotoError("Не удалось прочитать изображение.") from exc

    if image_format not in ALLOWED_FORMATS:
        raise PhotoError("Фотография должна быть в формате JPEG, PNG или WEBP.")

    image = ImageOps.exif_transpose(image).convert("RGB")
    image = ImageOps.fit(image, TARGET_SIZE, method=Image.Resampling.LANCZOS)

    output = BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()

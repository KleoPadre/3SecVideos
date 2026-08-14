"""Чистые функции отбора медиа для единого приложения."""

from pathlib import Path
import shutil

from PIL import Image


VIDEO_EXTENSIONS = {".avi", ".mkv", ".mov", ".mp4"}


def is_short_video(duration: float, maximum: float) -> bool:
    """Возвращает, не превышает ли длительность заданный порог."""
    return duration <= maximum


def unique_destination(source: Path, destination_root: Path, source_root: Path) -> Path:
    """Возвращает свободный путь, сохраняя вложенность исходного файла."""
    candidate = destination_root / source.relative_to(source_root)
    index = 1
    while candidate.exists():
        candidate = candidate.with_name(f"{source.stem}_{index}{source.suffix}")
        index += 1
    return candidate


def is_screenshot(path: Path) -> bool:
    """Проверяет наличие признака ``Screenshot`` в метаданных изображения."""
    try:
        with Image.open(path) as image:
            metadata = (*image.info.values(), *image.getexif().values())
    except (OSError, SyntaxError, ValueError):
        return False
    return any("Screenshot" in str(value) for value in metadata)


def collect_media(source: Path, mode: str) -> list[Path]:
    """Рекурсивно собирает поддерживаемые файлы для выбранного режима."""
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if mode == "видео":
        return [path for path in files if path.suffix.lower() in VIDEO_EXTENSIONS]
    if mode == "скриншоты":
        return [path for path in files if is_screenshot(path)]
    return []

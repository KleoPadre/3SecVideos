"""Безопасный отбор коротких видео для перемещения или отправки в Корзину."""

from pathlib import Path


def is_short_video(duration: float, max_duration: float) -> bool:
    """Возвращает, не превышает ли длительность заданный порог."""
    return duration <= max_duration


def unique_destination(source: Path, destination_root: Path, source_root: Path) -> Path:
    """Строит свободный путь назначения, сохраняя структуру исходных папок."""
    candidate = destination_root / source.relative_to(source_root)
    index = 1
    while candidate.exists():
        candidate = candidate.with_name(f"{source.stem}_{index}{source.suffix}")
        index += 1
    return candidate

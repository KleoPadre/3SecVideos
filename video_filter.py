"""Безопасный отбор коротких видео для перемещения или отправки в Корзину."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class Options:
    """Параметры обработки видео."""

    source: Path
    action: str
    destination: Path | None
    max_duration: float
    dry_run: bool


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


def check_ffprobe() -> bool:
    """Проверяет, доступна ли утилита определения длительности видео."""
    return shutil.which("ffprobe") is not None


def get_video_duration(path: Path) -> float | None:
    """Возвращает длительность видео в секундах либо ``None`` при ошибке."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def send_to_trash(path: Path) -> None:
    """Отправляет файл в Корзину macOS."""
    escaped_path = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Finder" to delete POSIX file "{escaped_path}"'
    subprocess.run(["osascript", "-e", script], check=True)


def process_video(path: Path, options: Options, duration_getter=get_video_duration) -> str:
    """Обрабатывает одно видео и возвращает краткий результат операции."""
    duration = duration_getter(path)
    if duration is None:
        return "ошибка длительности"
    if not is_short_video(duration, options.max_duration):
        return "длинное видео"
    if options.dry_run:
        return "предпросмотр"
    if options.action == "удалить":
        send_to_trash(path)
        return "удалено"

    if options.destination is None:
        raise ValueError("Для перемещения нужна целевая папка.")
    destination = unique_destination(path, options.destination, options.source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(destination))
    return "перемещено"

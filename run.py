"""Чистые функции отбора медиа для единого приложения."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from PIL import Image


VIDEO_EXTENSIONS = {".avi", ".mkv", ".mov", ".mp4"}


@dataclass(frozen=True)
class Options:
    """Параметры обработки медиафайлов."""

    source: Path
    mode: str
    action: str
    destination: Path | None
    max_duration: float
    dry_run: bool


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


def validate_options(options: Options) -> str | None:
    """Возвращает текст ошибки параметров либо ``None`` для корректных данных."""
    if options.mode not in {"видео", "скриншоты"}:
        return "Режим должен быть «видео» или «скриншоты»."
    if options.max_duration < 0:
        return "Максимальная длительность не может быть отрицательной."
    if options.action not in {"переместить", "удалить"}:
        return "Действие должно быть «переместить» или «удалить»."
    if options.mode == "скриншоты" and options.action != "переместить":
        return "Скриншоты можно только перемещать."
    if not options.source.is_dir():
        return f"Исходная папка не найдена: {options.source}"
    if options.action == "переместить":
        if options.destination is None or not options.destination.is_dir():
            return "Для перемещения укажите существующую целевую папку."
        source = options.source.resolve()
        destination = options.destination.resolve()
        if destination == source or destination.is_relative_to(source):
            return "Целевая папка не должна совпадать с исходной или находиться внутри неё."
    return None


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
    """Отправляет файл в Корзину macOS через Finder."""
    escaped_path = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Finder" to delete POSIX file "{escaped_path}"'
    subprocess.run(["osascript", "-e", script], check=True)


def process_file(path: Path, options: Options, duration_getter=get_video_duration) -> str:
    """Обрабатывает один файл и возвращает краткий результат операции."""
    if options.mode == "видео":
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


def summarize_results(results: list[str]) -> dict[str, int]:
    """Группирует результаты обработки для показа итоговой сводки."""
    summary = {
        "найдено": len(results),
        "перемещено": 0,
        "удалено": 0,
        "предпросмотр": 0,
        "пропущено": 0,
        "ошибки": 0,
    }
    for result in results:
        if result in {"перемещено", "удалено", "предпросмотр"}:
            summary[result] += 1
        elif result in {"длинное видео", "ошибка длительности"}:
            summary["пропущено"] += 1
        else:
            summary["ошибки"] += 1
    return summary


def dependencies_for(mode: str) -> list[str]:
    """Возвращает зависимости, которые UI может предложить установить пользователю."""
    if mode == "видео":
        return ["FFmpeg"]
    if mode == "скриншоты":
        return ["Pillow"]
    return []

"""Безопасный отбор коротких видео для перемещения или отправки в Корзину."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys


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


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def install_ffmpeg() -> bool:
    """Устанавливает Homebrew (при необходимости) и FFmpeg на macOS."""
    if shutil.which("brew") is None:
        print("Homebrew не найден. Будет запущен официальный установщик Homebrew.")
        result = subprocess.run(
            [
                "/bin/bash",
                "-c",
                "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)",
            ],
            check=False,
        )
        if result.returncode != 0:
            return False
    brew = shutil.which("brew")
    if brew is None:
        for candidate in (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew")):
            if candidate.is_file():
                brew = str(candidate)
                break
    if brew is None:
        print("Homebrew установлен, но команда brew недоступна в текущей среде.", file=sys.stderr)
        return False
    result = subprocess.run([brew, "install", "ffmpeg"], check=False)
    return result.returncode == 0 and check_ffprobe()


def ensure_ffprobe(install_missing: bool) -> bool:
    """Проверяет FFmpeg и при явном согласии устанавливает его."""
    if check_ffprobe():
        return True
    print("Не найдена утилита ffprobe из пакета FFmpeg.", file=sys.stderr)
    if not install_missing:
        print(
            "Установите FFmpeg командой: brew install ffmpeg\n"
            "Или перезапустите скрипт с параметром --install-missing.",
            file=sys.stderr,
        )
        return False
    if sys.platform != "darwin":
        print("Автоматическая установка поддерживается только на macOS.", file=sys.stderr)
        return False
    return install_ffmpeg()


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Поиск видео длительностью не более заданного порога."
    )
    parser.add_argument("--source", type=Path, help="Исходная папка")
    parser.add_argument("--action", choices=("переместить", "удалить"), help="Действие")
    parser.add_argument("--destination", type=Path, help="Целевая папка для перемещения")
    parser.add_argument(
        "--max-duration", type=float, default=3.0, help="Максимальная длительность в секундах"
    )
    parser.add_argument("--dry-run", action="store_true", help="Только показать план действий")
    parser.add_argument(
        "--install-missing",
        action="store_true",
        help="Установить FFmpeg при отсутствии (только macOS)",
    )
    return parser.parse_args(argv)


def ask_for_missing_arguments(args: argparse.Namespace) -> argparse.Namespace:
    """Запрашивает обязательные параметры, не заданные в командной строке."""
    if args.source is None:
        args.source = Path(input("Исходная папка: ").strip())
    if args.action is None:
        args.action = input("Действие (переместить/удалить): ").strip().lower()
    if args.action == "переместить" and args.destination is None:
        args.destination = Path(input("Целевая папка: ").strip())
    return args


def validate_arguments(args: argparse.Namespace) -> str | None:
    """Возвращает текст ошибки параметров либо ``None`` для корректных данных."""
    if args.action not in {"переместить", "удалить"}:
        return "Действие должно быть «переместить» или «удалить»."
    if args.max_duration < 0:
        return "Максимальная длительность не может быть отрицательной."
    args.source = args.source.expanduser()
    if args.destination is not None:
        args.destination = args.destination.expanduser()
    if not args.source.is_dir():
        return f"Исходная папка не найдена: {args.source}"
    if args.action == "переместить":
        if args.destination is None or not args.destination.is_dir():
            return "Для перемещения укажите существующую целевую папку."
        source = args.source.resolve()
        destination = args.destination.resolve()
        if destination == source or destination.is_relative_to(source):
            return "Целевая папка не должна совпадать с исходной или находиться внутри неё."
    return None


def iter_videos(source: Path):
    """Перечисляет подходящие видео, не меняя дерево папок во время обхода."""
    return [path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS]


def main(argv: list[str] | None = None) -> int:
    """Запускает интерактивную или аргументную обработку видео."""
    args = ask_for_missing_arguments(parse_arguments(argv))
    error = validate_arguments(args)
    if error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2
    if not ensure_ffprobe(args.install_missing):
        return 1

    options = Options(
        source=args.source.resolve(),
        action=args.action,
        destination=args.destination.resolve() if args.destination else None,
        max_duration=args.max_duration,
        dry_run=args.dry_run,
    )
    videos = iter_videos(options.source)
    summary = {"найдено": len(videos), "перемещено": 0, "удалено": 0, "предпросмотр": 0, "пропущено": 0, "ошибки": 0}
    for index, path in enumerate(videos, start=1):
        try:
            result = process_video(path, options)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            result = f"ошибка: {error}"
        if result in summary:
            summary[result] += 1
        elif result in {"длинное видео", "ошибка длительности"}:
            summary["пропущено"] += 1
        else:
            summary["ошибки"] += 1
        print(f"[{index}/{len(videos)}] {result}: {path}")

    print("\nИтог:")
    print(
        ", ".join(f"{name} — {count}" for name, count in summary.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

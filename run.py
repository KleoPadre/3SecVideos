"""Единое графическое приложение для отбора медиафайлов."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ImportError as error:
    tk = filedialog = messagebox = scrolledtext = ttk = None
    TKINTER_IMPORT_ERROR: ImportError | None = error
else:
    TKINTER_IMPORT_ERROR = None


VIDEO_EXTENSIONS = {".avi", ".mkv", ".mov", ".mp4"}


def fallback_python_for_tkinter(
    current_python: Path,
    *,
    platform: str = sys.platform,
    system_python: Path = Path("/usr/bin/python3"),
    system_exists=lambda path: path.is_file(),
) -> Path | None:
    """Возвращает системный Python macOS для запуска Tkinter, если он доступен."""
    if platform != "darwin" or current_python == system_python or not system_exists(system_python):
        return None
    return system_python


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
    from PIL import Image

    try:
        with Image.open(path) as image:
            metadata = (*image.info.values(), *image.getexif().values())
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
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


def destination_is_inside_source(source: Path, destination: Path) -> bool:
    """Проверяет физическое совпадение назначения с источником или его потомком."""
    try:
        if destination.samefile(source):
            return True
        physical_destination = destination.resolve()
        return any(parent.samefile(source) for parent in physical_destination.parents)
    except OSError:
        resolved_source = source.resolve()
        resolved_destination = destination.resolve()
        return resolved_destination == resolved_source or resolved_destination.is_relative_to(
            resolved_source
        )


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
        if destination_is_inside_source(options.source, options.destination):
            return "Целевая папка не должна совпадать с исходной или находиться внутри неё."
    return None


def build_options(
    mode: str,
    source: str | Path,
    destination: str | Path | None,
    max_duration: str,
    *,
    action: str = "переместить",
    dry_run: bool = False,
) -> tuple[Options | None, str | None]:
    """Создаёт проверенные параметры из значений графического интерфейса."""
    if isinstance(source, str) and not source.strip():
        return None, "Укажите исходную папку."
    duration = 3.0
    if mode == "видео":
        try:
            duration = float(max_duration)
        except (TypeError, ValueError):
            return None, "Укажите максимальную длительность числом."
        if not math.isfinite(duration):
            return None, "Укажите максимальную длительность числом."
    options = Options(
        source=Path(source),
        mode=mode,
        action=action,
        destination=Path(destination) if destination else None,
        max_duration=duration,
        dry_run=dry_run,
    )
    return options, validate_options(options)


def get_video_duration(path: Path) -> float | None:
    """Возвращает длительность видео в секундах либо ``None`` при ошибке."""
    try:
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
    except FileNotFoundError:
        return None
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
    if options.mode == "скриншоты" and options.action != "переместить":
        raise ValueError("Скриншоты можно только перемещать.")
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
        elif result == "длинное видео":
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


def missing_dependency(mode: str) -> str | None:
    """Возвращает отсутствующую зависимость для выбранного режима."""
    if mode == "видео" and shutil.which("ffprobe") is None:
        return "FFmpeg"
    if mode == "скриншоты":
        try:
            importlib.import_module("PIL.Image")
        except ImportError:
            return "Pillow"
    return None


def install_dependency(name: str) -> tuple[bool, str]:
    """Устанавливает зависимость после подтверждения пользователя в UI."""
    if name == "FFmpeg":
        brew = shutil.which("brew")
        if brew is None:
            return False, "Homebrew не найден. Установите его, затем повторите запуск."
        command = [brew, "install", "ffmpeg"]
    elif name == "Pillow":
        command = [sys.executable, "-m", "pip", "install", "Pillow>=10.3.0"]
    else:
        return False, f"Неизвестная зависимость: {name}."

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        return False, str(error)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        return False, details or f"Команда завершилась с кодом {result.returncode}."
    importlib.invalidate_caches()
    return True, "Установка завершена."


class MediaFilterApp:
    """Связывает функции обработки медиа с тёмным интерфейсом Tkinter."""

    BACKGROUND = "#15181d"
    PANEL = "#20242b"
    FIELD = "#292e37"
    FOREGROUND = "#f2f4f8"
    MUTED = "#aeb6c2"
    ACCENT = "#63a4ff"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.mode = tk.StringVar(value="видео")
        self.action = tk.StringVar(value="переместить")
        self.source = tk.StringVar()
        self.destination = tk.StringVar()
        self.max_duration = tk.StringVar(value="3")
        self.progress_text = tk.StringVar(value="0 из 0 — 0%")
        self.summary_text = tk.StringVar(value="Сводка появится после обработки.")

        self._configure_window()
        self._configure_styles()
        self._build_interface()
        self._sync_controls()

    def _configure_window(self) -> None:
        self.root.title("Фильтр медиа")
        self.root.geometry("820x720")
        self.root.minsize(680, 600)
        self.root.configure(background=self.BACKGROUND)
        self.root.option_add("*Font", ("SF Pro Text", 12))

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=self.BACKGROUND, foreground=self.FOREGROUND)
        style.configure("TFrame", background=self.BACKGROUND)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("TLabel", background=self.BACKGROUND, foreground=self.FOREGROUND)
        style.configure("Panel.TLabel", background=self.PANEL, foreground=self.FOREGROUND)
        style.configure("Muted.TLabel", background=self.BACKGROUND, foreground=self.MUTED)
        style.configure(
            "TButton",
            background=self.FIELD,
            foreground=self.FOREGROUND,
            bordercolor=self.FIELD,
            focusthickness=2,
            focuscolor=self.ACCENT,
            padding=(12, 8),
        )
        style.map("TButton", background=[("active", "#39414d"), ("disabled", self.PANEL)])
        style.configure("Accent.TButton", background=self.ACCENT, foreground="#0b1119")
        style.map("Accent.TButton", background=[("active", "#85b8ff"), ("disabled", "#34465f")])
        style.configure(
            "TRadiobutton",
            background=self.BACKGROUND,
            foreground=self.FOREGROUND,
            indicatorcolor=self.FIELD,
            padding=(0, 5),
        )
        style.map(
            "TRadiobutton",
            background=[("active", self.BACKGROUND)],
            indicatorcolor=[("selected", self.ACCENT)],
        )
        style.configure(
            "TEntry",
            fieldbackground=self.FIELD,
            foreground=self.FOREGROUND,
            insertcolor=self.FOREGROUND,
            bordercolor="#414957",
            padding=7,
        )
        style.map(
            "TEntry",
            fieldbackground=[("readonly", self.FIELD)],
            foreground=[("readonly", self.FOREGROUND)],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=self.FIELD,
            foreground=self.FOREGROUND,
            arrowcolor=self.FOREGROUND,
            bordercolor="#414957",
            padding=7,
        )
        style.configure(
            "Horizontal.TProgressbar",
            background=self.ACCENT,
            troughcolor=self.FIELD,
            bordercolor=self.FIELD,
            lightcolor=self.ACCENT,
            darkcolor=self.ACCENT,
        )

    def _build_interface(self) -> None:
        container = ttk.Frame(self.root, padding=24)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(8, weight=1)

        ttk.Label(container, text="Единый фильтр медиа", font=("SF Pro Display", 22, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        ttk.Label(
            container,
            text="Выберите режим, папки и сначала проверьте результат в предпросмотре.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(0, 18))

        mode_frame = ttk.Frame(container)
        mode_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        ttk.Radiobutton(
            mode_frame,
            text="Короткие видео",
            value="видео",
            variable=self.mode,
            command=self._sync_controls,
        ).pack(side="left", padx=(0, 20))
        ttk.Radiobutton(
            mode_frame,
            text="Скриншоты",
            value="скриншоты",
            variable=self.mode,
            command=self._sync_controls,
        ).pack(side="left")

        folders = ttk.Frame(container, style="Panel.TFrame", padding=16)
        folders.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        folders.columnconfigure(1, weight=1)
        ttk.Label(folders, text="Исходная папка", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 10)
        )
        ttk.Entry(folders, textvariable=self.source, state="readonly").grid(
            row=0, column=1, sticky="ew", pady=(0, 10)
        )
        ttk.Button(folders, text="Выбрать…", command=self._choose_source).grid(
            row=0, column=2, padx=(10, 0), pady=(0, 10)
        )
        self.destination_label = ttk.Label(folders, text="Целевая папка", style="Panel.TLabel")
        self.destination_label.grid(row=1, column=0, sticky="w", padx=(0, 12))
        self.destination_entry = ttk.Entry(folders, textvariable=self.destination, state="readonly")
        self.destination_entry.grid(row=1, column=1, sticky="ew")
        self.destination_button = ttk.Button(folders, text="Выбрать…", command=self._choose_destination)
        self.destination_button.grid(row=1, column=2, padx=(10, 0))

        settings = ttk.Frame(container)
        settings.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        settings.columnconfigure(0, weight=1)
        settings.columnconfigure(1, weight=1)

        self.threshold_frame = ttk.Frame(settings)
        self.threshold_frame.grid(row=0, column=0, sticky="w")
        ttk.Label(self.threshold_frame, text="Порог, секунд").pack(side="left", padx=(0, 10))
        self.threshold_spinbox = ttk.Spinbox(
            self.threshold_frame,
            from_=0.0,
            to=86400.0,
            increment=0.1,
            textvariable=self.max_duration,
            width=8,
        )
        self.threshold_spinbox.pack(side="left")

        self.action_frame = ttk.Frame(settings)
        self.action_frame.grid(row=0, column=1, sticky="e")
        ttk.Radiobutton(
            self.action_frame,
            text="Переместить",
            value="переместить",
            variable=self.action,
            command=self._sync_destination,
        ).pack(side="left", padx=(0, 14))
        ttk.Radiobutton(
            self.action_frame,
            text="В Корзину",
            value="удалить",
            variable=self.action,
            command=self._sync_destination,
        ).pack(side="left")

        buttons = ttk.Frame(container)
        buttons.grid(row=5, column=0, sticky="ew", pady=(0, 16))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        self.preview_button = ttk.Button(
            buttons, text="Предпросмотр", command=lambda: self._start(dry_run=True)
        )
        self.preview_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.run_button = ttk.Button(
            buttons,
            text="Запустить обработку",
            style="Accent.TButton",
            command=lambda: self._start(dry_run=False),
        )
        self.run_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        progress_frame = ttk.Frame(container)
        progress_frame.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        progress_frame.columnconfigure(0, weight=1)
        ttk.Label(progress_frame, textvariable=self.progress_text).grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(progress_frame, maximum=100, mode="determinate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        ttk.Label(container, textvariable=self.summary_text, style="Muted.TLabel", wraplength=760).grid(
            row=7, column=0, sticky="ew", pady=(0, 10)
        )
        self.log = scrolledtext.ScrolledText(
            container,
            height=14,
            background="#101217",
            foreground=self.FOREGROUND,
            insertbackground=self.FOREGROUND,
            selectbackground="#355b8c",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
            state="disabled",
            wrap="word",
        )
        self.log.grid(row=8, column=0, sticky="nsew")

    def _choose_source(self) -> None:
        path = filedialog.askdirectory(parent=self.root, title="Выберите исходную папку", mustexist=True)
        if path:
            self.source.set(path)

    def _choose_destination(self) -> None:
        initial = self.destination.get() or self.source.get() or None
        path = filedialog.askdirectory(
            parent=self.root,
            title="Выберите целевую папку",
            initialdir=initial,
            mustexist=True,
        )
        if path:
            self.destination.set(path)

    def _sync_controls(self) -> None:
        if self.mode.get() == "скриншоты":
            self.action.set("переместить")
            self.threshold_frame.grid_remove()
            self.action_frame.grid_remove()
        else:
            self.threshold_frame.grid()
            self.action_frame.grid()
        self._sync_destination()

    def _sync_destination(self) -> None:
        controls = (self.destination_label, self.destination_entry, self.destination_button)
        if self.action.get() == "переместить":
            for control in controls:
                control.grid()
        else:
            for control in controls:
                control.grid_remove()

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.preview_button.configure(state=state)
        self.run_button.configure(state=state)

    def _start(self, dry_run: bool) -> None:
        action = "переместить" if self.mode.get() == "скриншоты" else self.action.get()
        options, error = build_options(
            self.mode.get(),
            self.source.get(),
            self.destination.get(),
            self.max_duration.get(),
            action=action,
            dry_run=dry_run,
        )
        if error or options is None:
            messagebox.showerror("Проверьте параметры", error or "Не удалось подготовить параметры.", parent=self.root)
            return

        dependency = missing_dependency(options.mode)
        if dependency is not None:
            reason = (
                "Для определения длительности видео нужен FFmpeg."
                if dependency == "FFmpeg"
                else "Для чтения метаданных изображений нужен Pillow."
            )
            confirmed = messagebox.askyesno(
                "Необходима зависимость",
                f"{reason}\n\nУстановить {dependency} сейчас?",
                parent=self.root,
            )
            if not confirmed:
                self._append_log(f"Установка {dependency} отменена пользователем.")
                return

        self._set_running(True)
        self.progress.configure(value=0)
        self.progress_text.set("0 из 0 — 0%")
        self.summary_text.set("Обработка выполняется…")
        self._append_log("Предпросмотр запущен." if dry_run else "Обработка запущена.")
        threading.Thread(
            target=self._worker,
            args=(options, dependency),
            name="обработка-медиа",
            daemon=True,
        ).start()

    def _post(self, callback, *args) -> None:
        self.root.after(0, callback, *args)

    def _worker(self, options: Options, dependency: str | None) -> None:
        try:
            if dependency is not None:
                self._post(self._append_log, f"Устанавливается {dependency}…")
                installed, details = install_dependency(dependency)
                if not installed:
                    self._post(self._fail, f"Не удалось установить {dependency}: {details}")
                    return
                if missing_dependency(options.mode) is not None:
                    self._post(self._fail, f"{dependency} установлен, но пока недоступен приложению.")
                    return
                self._post(self._append_log, details)

            files = collect_media(options.source, options.mode)
            total = len(files)
            self._post(self._prepare_progress, total)
            results: list[str] = []
            for index, path in enumerate(files, start=1):
                try:
                    result = process_file(path, options)
                except Exception as error:
                    result = f"ошибка: {error}"
                results.append(result)
                self._post(self._append_log, f"{path}: {result}")
                self._post(self._update_progress, index, total)
            self._post(self._finish, summarize_results(results))
        except Exception as error:
            self._post(self._fail, f"Обработка прервана: {error}")

    def _prepare_progress(self, total: int) -> None:
        self.progress.configure(value=0)
        self.progress_text.set(f"0 из {total} — 0%")
        self._append_log(f"Найдено файлов: {total}.")

    def _update_progress(self, current: int, total: int) -> None:
        percent = round(current * 100 / total) if total else 0
        self.progress.configure(value=percent)
        self.progress_text.set(f"{current} из {total} — {percent}%")

    def _finish(self, summary: dict[str, int]) -> None:
        text = (
            f"Найдено: {summary['найдено']}; перемещено: {summary['перемещено']}; "
            f"отправлено в Корзину: {summary['удалено']}; предпросмотр: {summary['предпросмотр']}; "
            f"пропущено: {summary['пропущено']}; ошибок: {summary['ошибки']}."
        )
        self.summary_text.set(text)
        self._append_log(f"Готово. {text}")
        self._set_running(False)

    def _fail(self, text: str) -> None:
        self.summary_text.set(text)
        self._append_log(text)
        self._set_running(False)
        messagebox.showerror("Ошибка", text, parent=self.root)


def main() -> None:
    """Создаёт окно приложения и запускает цикл Tkinter."""
    if TKINTER_IMPORT_ERROR is not None:
        fallback_python = fallback_python_for_tkinter(Path(sys.executable))
        if fallback_python is not None:
            print("Tkinter недоступен в текущем Python. Запускаю системный Python macOS.")
            os.execv(
                str(fallback_python),
                [str(fallback_python), str(Path(__file__).resolve()), *sys.argv[1:]],
            )
        raise SystemExit(
            "Tkinter недоступен в текущем Python. Установите Python с поддержкой Tk: "
            f"{TKINTER_IMPORT_ERROR}"
        )
    root = tk.Tk()
    MediaFilterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

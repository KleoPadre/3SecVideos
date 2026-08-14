# Единый фильтр коротких видео — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать единый безопасный скрипт для перемещения или удаления видео длительностью до заданного порога.

**Architecture:** `video_filter.py` содержит чистые функции для поиска файлов, измерения длительности и выбора безопасного назначения, а также слой CLI для интерактивного и аргументного запуска. Удаление выполняется отдельной функцией через Корзину macOS, что исключает необратимое удаление.

**Tech Stack:** Python 3, стандартная библиотека (`argparse`, `pathlib`, `subprocess`, `unittest`), FFmpeg (`ffprobe`).

## Global Constraints

- Порог по умолчанию: 3 секунды, сравнение включающее (`<=`).
- Поддерживаются `.mp4`, `.avi`, `.mov`, `.mkv`.
- Удаление направляется в Корзину macOS; прямое удаление не применяется.
- Внешние Python-пакеты и виртуальное окружение не требуются.
- Документация, комментарии и пользовательские сообщения — на русском языке.

---

### Task 1: Ядро отбора и файловых операций

**Files:**
- Create: `video_filter.py`
- Test: `tests/test_video_filter.py`

**Interfaces:**
- Produces: `is_short_video(duration: float, max_duration: float) -> bool`, `unique_destination(source: Path, destination_root: Path, source_root: Path) -> Path`, `get_video_duration(path: Path) -> float | None`.

- [ ] **Step 1: Write the failing test**

```python
def test_ролик_на_границе_порога_подходит():
    assert video_filter.is_short_video(3.0, 3.0)

def test_конфликт_имени_получает_суффикс(tmp_path):
    source = tmp_path / "source" / "nested" / "clip.mov"
    source.parent.mkdir(parents=True)
    source.touch()
    target = tmp_path / "target" / "nested" / "clip.mov"
    target.parent.mkdir(parents=True)
    target.touch()
    assert video_filter.unique_destination(source, tmp_path / "target", tmp_path / "source").name == "clip_1.mov"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_video_filter -v`
Expected: FAIL because module `video_filter` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def is_short_video(duration: float, max_duration: float) -> bool:
    return duration <= max_duration

def unique_destination(source: Path, destination_root: Path, source_root: Path) -> Path:
    candidate = destination_root / source.relative_to(source_root)
    index = 1
    while candidate.exists():
        candidate = candidate.with_name(f"{source.stem}_{index}{source.suffix}")
        index += 1
    return candidate
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_video_filter -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add video_filter.py tests/test_video_filter.py
git commit -m "Добавлен единый фильтр коротких видео"
```

### Task 2: Команды действий и зависимость FFmpeg

**Files:**
- Modify: `video_filter.py`
- Modify: `tests/test_video_filter.py`

**Interfaces:**
- Consumes: `unique_destination(source, destination_root, source_root)`.
- Produces: `check_ffprobe() -> bool`, `send_to_trash(path: Path, runner) -> None`, `process_video(path: Path, options: Options, runner) -> str`.

- [ ] **Step 1: Write the failing test**

```python
def test_предпросмотр_не_вызывает_перемещение_или_корзину(tmp_path):
    path = tmp_path / "clip.mov"
    path.touch()
    options = video_filter.Options(source=tmp_path, action="удалить", destination=None, max_duration=3, dry_run=True)
    result = video_filter.process_video(path, options, duration_getter=lambda _: 2.0)
    assert result == "предпросмотр"
    assert path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_video_filter -v`
Expected: FAIL because `Options` and `process_video` do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def send_to_trash(path: Path, runner=subprocess.run) -> None:
    escaped = str(path).replace('"', '\\\"')
    runner(["osascript", "-e", f'tell application "Finder" to delete POSIX file "{escaped}"'], check=True)

def check_ffprobe() -> bool:
    return shutil.which("ffprobe") is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_video_filter -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add video_filter.py tests/test_video_filter.py
git commit -m "Добавлена безопасная обработка видео"
```

### Task 3: CLI, документация и полная проверка

**Files:**
- Modify: `video_filter.py`
- Modify: `README.md`
- Modify: `tests/test_video_filter.py`

**Interfaces:**
- Consumes: `check_ffprobe()`, `get_video_duration(path)`, `process_video(path, options, runner)`.
- Produces: `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
def test_cli_отклоняет_совпадающие_исходную_и_целевую_папки(tmp_path):
    code = video_filter.main(["--source", str(tmp_path), "--action", "переместить", "--destination", str(tmp_path)])
    assert code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_video_filter -v`
Expected: FAIL because `main` does not validates directories.

- [ ] **Step 3: Write minimal implementation**

```python
parser.add_argument("--action", choices=("переместить", "удалить"))
parser.add_argument("--dry-run", action="store_true")
if options.action == "переместить" and options.source.resolve() == options.destination.resolve():
    print("Исходная и целевая папки должны различаться.", file=sys.stderr)
    return 2
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_video_filter -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add video_filter.py tests/test_video_filter.py README.md
git commit -m "Добавлен интерфейс единого фильтра видео"
```

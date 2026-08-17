# Живой журнал поиска медиафайлов — план реализации

> **Для агентных исполнителей:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Цель:** Показывать в интерфейсе ход поиска файлов до начала их обработки.

**Архитектура:** `collect_media` будет принимать необязательный обратный вызов и сообщать ему количество просмотренных и подходящих файлов. `_worker` передаст эти события в главный поток через `_post`, а журнал покажет начало, ход и завершение поиска. Сортировка и критерии отбора останутся прежними.

**Технологии:** Python 3, Tkinter, `unittest`.

## Общие ограничения

- Все пользовательские сообщения и комментарии — на русском языке.
- Изменение виджетов Tkinter допускается только в главном потоке через `root.after`.
- Поиск не должен выполнять два обхода исходной папки.

---

### Задача 1: Состояние поиска в сборщике файлов

**Файлы:**

- Изменить: `run.py:101-109`
- Тест: `tests/test_run.py`

**Интерфейсы:**

- Потребляет: `source: Path`, `mode: str`.
- Создаёт: `collect_media(source, mode, progress_callback=None) -> list[Path]`, где `progress_callback(checked: int, found: int)` вызывается после каждого файла.

- [ ] **Шаг 1: Написать падающий тест**

```python
def test_сбор_видео_сообщает_ход_поиска(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "clip.mov").touch()
        (root / "audio.mp3").touch()
        progress = []

        run.collect_media(root, "видео", lambda checked, found: progress.append((checked, found)))

    self.assertEqual(progress, [(1, 0), (2, 1)])
```

- [ ] **Шаг 2: Запустить тест и подтвердить падение**

Выполнить: `python3 -m unittest tests.test_run.RunTests.test_сбор_видео_сообщает_ход_поиска`

Ожидается: `TypeError`, потому что третий аргумент ещё не поддерживается.

- [ ] **Шаг 3: Реализовать минимальное изменение**

```python
def collect_media(source: Path, mode: str, progress_callback=None) -> list[Path]:
    found = []
    checked = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        checked += 1
        if is_selected(path, mode):
            found.append(path)
        if progress_callback is not None:
            progress_callback(checked, len(found))
    return found
```

Использовать счётчик только обычных файлов, чтобы текст «просмотрено» не включал каталоги.

- [ ] **Шаг 4: Запустить тест и подтвердить успех**

Выполнить: `python3 -m unittest tests.test_run.RunTests.test_сбор_видео_сообщает_ход_поиска`

Ожидается: `OK`.

### Задача 2: Журнал поиска в рабочем потоке

**Файлы:**

- Изменить: `run.py:624-628`
- Тест: `tests/test_run.py`

**Интерфейсы:**

- Потребляет: `collect_media(..., progress_callback)` из задачи 1 и `_post(callback, *args)`.
- Создаёт: строки журнала «Начат поиск файлов…», «Поиск: просмотрено N, найдено M.» и «Поиск завершён. Найдено файлов: M.».

- [ ] **Шаг 1: Написать падающий тест**

```python
def test_рабочий_поток_публикует_ход_поиска(self):
    scheduled = []
    app = object.__new__(run.MediaFilterApp)
    app.root = SimpleNamespace(after=lambda delay, callback, *args: scheduled.append((callback.__name__, args)))

    def collect(source, mode, callback):
        callback(4, 2)
        return []

    with patch.object(run, "collect_media", side_effect=collect):
        app._worker(options, None)

    self.assertEqual(scheduled[:3], [
        ("_append_log", ("Начат поиск файлов…",)),
        ("_append_log", ("Поиск: просмотрено 4, найдено 2.",)),
        ("_append_log", ("Поиск завершён. Найдено файлов: 0.",)),
    ])
```

- [ ] **Шаг 2: Запустить тест и подтвердить падение**

Выполнить: `python3 -m unittest tests.test_run.RunTests.test_рабочий_поток_публикует_ход_поиска`

Ожидается: проверка не найдёт строки журнала поиска.

- [ ] **Шаг 3: Реализовать минимальное изменение**

Перед вызовом сборщика передать в `_post` начальную строку. Передать `collect_media` функцию, вызывающую `_post(self._append_log, f"Поиск: ...")`. После сборщика опубликовать итог поиска и сохранить текущую подготовку прогресса.

- [ ] **Шаг 4: Запустить тест и подтвердить успех**

Выполнить: `python3 -m unittest tests.test_run.RunTests.test_рабочий_поток_публикует_ход_поиска`

Ожидается: `OK`.

### Задача 3: Полная проверка

**Файлы:**

- Изменить: `run.py`, `tests/test_run.py`

- [ ] **Шаг 1: Проверить синтаксис**

Выполнить: `python3 -m py_compile run.py`

Ожидается: код возврата `0`.

- [ ] **Шаг 2: Запустить весь набор тестов**

Выполнить: `python3 -m unittest`

Ожидается: все тесты проходят.

- [ ] **Шаг 3: Проверить пробелы и diff**

Выполнить: `git diff --check && git diff -- run.py tests/test_run.py`

Ожидается: `git diff --check` завершается без вывода.

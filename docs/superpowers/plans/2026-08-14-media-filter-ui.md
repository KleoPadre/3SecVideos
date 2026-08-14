# План реализации единого приложения медиа

> **Для агентных исполнителей:** выполняйте задачи последовательно с проверкой после каждой из них.

**Цель:** Создать `run.py` — единое тёмное macOS-приложение для обработки коротких видео и скриншотов через выбор папок Finder.

**Архитектура:** Один файл `run.py` содержит изолированные чистые функции поиска и обработки файлов, а класс `MediaFilterApp` связывает их с интерфейсом Tkinter. Обработка запускается в рабочем потоке, а обновления журнала и прогресса безопасно передаются в главный поток окна.

**Стек:** Python 3, Tkinter, Pillow, FFmpeg (`ffprobe`), `unittest`.

## Общие ограничения

- Единственный запуск: `python3 run.py`.
- Интерфейс всегда тёмный; папки выбираются системным диалогом Finder.
- Порог видео включающий и по умолчанию равен 3 секундам.
- Видео: `.mp4`, `.avi`, `.mov`, `.mkv`; удаление идёт только в Корзину macOS.
- Скриншот определяется по `Screenshot` в метаданных Pillow и только перемещается.
- При перемещении сохраняются подпапки и никогда не перезаписываются файлы.
- Все сообщения, документация и комментарии — на русском языке.

---

### Задача 1: Чистые функции обработки медиа

**Файлы:**
- Создать: `run.py`
- Создать: `tests/test_run.py`

**Интерфейсы:**
- Создаёт: `is_short_video(duration: float, maximum: float) -> bool`, `unique_destination(source: Path, destination_root: Path, source_root: Path) -> Path`, `is_screenshot(path: Path) -> bool`, `collect_media(source: Path, mode: str) -> list[Path]`.

- [ ] Написать падающие тесты границы длительности, конфликта имён и EXIF/PNG-метаданных `Screenshot`.

```python
def test_длительность_равная_порогу_подходит(self):
    self.assertTrue(run.is_short_video(4.0, 4.0))

def test_путь_не_перезаписывает_существующий_файл(self):
    self.assertEqual(result.name, "clip_1.mov")
```

- [ ] Выполнить `python3 -m unittest tests.test_run -v`; ожидается ошибка импорта `run`.
- [ ] Реализовать функции на `pathlib`, `shutil` и Pillow; `is_screenshot` возвращает `False` при нечитаемом файле.
- [ ] Повторить `python3 -m unittest tests.test_run -v`; ожидается успешное выполнение.
- [ ] Зафиксировать: `git add run.py tests/test_run.py && git commit -m "Добавлено ядро единого фильтра медиа"`.

### Задача 2: Операции, сводка и зависимости

**Файлы:**
- Изменить: `run.py`
- Изменить: `tests/test_run.py`
- Изменить: `requirements.txt`

**Интерфейсы:**
- Использует: `collect_media(source, mode)`, `unique_destination(source, destination_root, source_root)`.
- Создаёт: `process_file(path: Path, options: Options) -> str`, `validate_options(options: Options) -> str | None`, `dependencies_for(mode: str) -> list[str]`.

- [ ] Написать падающие тесты режима предпросмотра и запрета целевой папки внутри исходной.

```python
def test_предпросмотр_не_изменяет_файл(self):
    result = run.process_file(path, options, duration_getter=lambda _: 2.0)
    self.assertEqual(result, "предпросмотр")
    self.assertTrue(path.exists())
```

- [ ] Выполнить `python3 -m unittest tests.test_run -v`; ожидается отсутствие `process_file`.
- [ ] Реализовать перемещение, отправку видео в Корзину, сводку результатов и предложения установки Pillow/FFmpeg только после нажатия пользователя в UI. Указать `Pillow` в `requirements.txt`.
- [ ] Повторить `python3 -m unittest tests.test_run -v`; ожидается успешное выполнение.
- [ ] Зафиксировать: `git add run.py tests/test_run.py requirements.txt && git commit -m "Добавлена обработка медиа и зависимости"`.

### Задача 3: Тёмный графический интерфейс и миграция

**Файлы:**
- Изменить: `run.py`
- Изменить: `tests/test_run.py`
- Изменить: `README.md`
- Удалить: `video_filter.py`, `mov.py`, `iphone_screens.py`

**Интерфейсы:**
- Использует: `validate_options(options)`, `collect_media(source, mode)`, `process_file(path, options)`.
- Создаёт: `MediaFilterApp`, `main() -> None`.

- [ ] Написать падающий тест подготовки задания: `build_options("видео", source, destination, "4")` должен создавать порог `4.0`, а нестрогое число возвращать ошибку.
- [ ] Выполнить `python3 -m unittest tests.test_run -v`; ожидается отсутствие `build_options`.
- [ ] Реализовать `MediaFilterApp`: тёмные стили, переключатель режима, числовой порог только для видео, Finder-диалоги, кнопки предпросмотра и запуска, журнал, `N из M`, проценты и `ttk.Progressbar`. Запускать обработку в `threading.Thread`, обновляя UI через `after`.
- [ ] Обновить README с единственной командой запуска и удалить три устаревших скрипта после проверки, что `run.py` импортируется и запускается.
- [ ] Выполнить `python3 -m unittest discover -v` и `python3 -m py_compile run.py`; ожидается успешное выполнение.
- [ ] Зафиксировать: `git add -A && git commit -m "Создано единое приложение обработки медиа"`, предварительно убедившись, что случайные пользовательские файлы не попали в индекс.

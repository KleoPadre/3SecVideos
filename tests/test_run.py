"""Проверки чистых функций единого фильтра медиа."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, PngImagePlugin

import run


class RunTests(unittest.TestCase):
    """Проверяет отбор файлов и построение путей назначения."""

    def test_находит_системный_python_для_tkinter_на_macos(self):
        """Ошибка: запуск из Python без Tkinter не переключается на системный Python macOS."""
        system_python = Path("/usr/bin/python3")

        result = run.fallback_python_for_tkinter(
            Path("/Users/test/.pyenv/bin/python3"),
            platform="darwin",
            system_python=system_python,
            system_exists=lambda _: True,
        )

        self.assertEqual(result, system_python)

    def test_подготовка_параметров_преобразует_порог_в_число(self):
        """Ошибка: строковый порог попадает в обработку без преобразования."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "исходные"
            destination = root / "целевые"
            source.mkdir()
            destination.mkdir()

            options, error = run.build_options("видео", source, destination, "4")

            self.assertIsNone(error)
            self.assertIsNotNone(options)
            self.assertEqual(options.max_duration, 4.0)

    def test_подготовка_параметров_отклоняет_некорректный_порог(self):
        """Ошибка: нечисловой порог приводит к исключению из обработчика UI."""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)

            options, error = run.build_options("видео", source, None, "не число")

            self.assertIsNone(options)
            self.assertEqual(error, "Укажите максимальную длительность числом.")

    def test_подготовка_параметров_отклоняет_пустую_исходную_папку(self):
        """Ошибка: пустой путь превращается в текущую папку и допускает удаление."""
        for source in ("", "   "):
            with self.subTest(source=source):
                options, error = run.build_options(
                    "видео", source, None, "3", action="удалить"
                )

                self.assertIsNone(options)
                self.assertEqual(error, "Укажите исходную папку.")

    def test_подготовка_скриншотов_игнорирует_скрытый_порог(self):
        """Ошибка: скрытый порог видео блокирует запуск режима скриншотов."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "исходные"
            destination = root / "целевые"
            source.mkdir()
            destination.mkdir()

            options, error = run.build_options("скриншоты", source, destination, "")

            self.assertIsNone(error)
            self.assertIsNotNone(options)
            self.assertEqual(options.mode, "скриншоты")

    def test_длительность_равная_порогу_подходит(self):
        """Ошибка: строгое сравнение исключает ролик на границе порога."""
        self.assertTrue(run.is_short_video(4.0, 4.0))

    def test_путь_не_перезаписывает_существующий_файл(self):
        """Ошибка: существующий файл назначения может быть перезаписан."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "исходные"
            source = source_root / "вложено" / "clip.mov"
            source.parent.mkdir(parents=True)
            source.touch()
            destination_root = root / "целевые"
            existing = destination_root / "вложено" / "clip.mov"
            existing.parent.mkdir(parents=True)
            existing.touch()

            result = run.unique_destination(source, destination_root, source_root)

            self.assertEqual(result, destination_root / "вложено" / "clip_1.mov")

    def test_png_с_метаданными_screenshot_распознаётся(self):
        """Ошибка: метаданные PNG с признаком скриншота не учитываются."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "screen.png"
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("Description", "iPhone Screenshot")
            Image.new("RGB", (1, 1)).save(path, pnginfo=metadata)

            self.assertTrue(run.is_screenshot(path))

    def test_jpeg_с_exif_screenshot_распознаётся(self):
        """Ошибка: EXIF-метаданные с признаком скриншота не учитываются."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "screen.jpg"
            exif = Image.Exif()
            exif[270] = "Screenshot from iPhone"
            Image.new("RGB", (1, 1)).save(path, exif=exif)

            self.assertTrue(run.is_screenshot(path))

    def test_нечитаемый_файл_не_считается_скриншотом(self):
        """Ошибка: повреждённый файл прерывает поиск вместо безопасного пропуска."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "повреждён.png"
            path.write_text("это не изображение")

            self.assertFalse(run.is_screenshot(path))

    def test_опасно_большое_изображение_безопасно_пропускается(self):
        """Ошибка: защитное исключение Pillow прерывает сбор всех скриншотов."""
        path = Path("слишком-большое.png")
        with patch.object(
            Image,
            "open",
            side_effect=Image.DecompressionBombError("слишком много пикселей"),
        ):
            try:
                result = run.is_screenshot(path)
            except Image.DecompressionBombError:
                self.fail("is_screenshot пробросил DecompressionBombError")

        self.assertFalse(result)

    def test_сбор_видео_рекурсивно_оставляет_только_поддерживаемые_форматы(self):
        """Ошибка: сбор видео может пропустить вложенный файл или взять изображение."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "вложено" / "clip.MOV"
            expected.parent.mkdir()
            expected.touch()
            (root / "audio.mp3").touch()
            (root / "image.png").touch()

            self.assertEqual(run.collect_media(root, "видео"), [expected])

    def test_сбор_скриншотов_рекурсивно_оставляет_только_файлы_с_признаком(self):
        """Ошибка: сбор скриншотов может включить изображение без метаданных."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "вложено" / "screen.png"
            expected.parent.mkdir()
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("Description", "Screenshot")
            Image.new("RGB", (1, 1)).save(expected, pnginfo=metadata)
            Image.new("RGB", (1, 1)).save(root / "photo.png")

            self.assertEqual(run.collect_media(root, "скриншоты"), [expected])

    def test_предпросмотр_не_изменяет_файл(self):
        """Ошибка: предпросмотр удаляет или перемещает короткое видео."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mov"
            path.touch()
            options = SimpleNamespace(
                source=Path(directory),
                mode="видео",
                action="удалить",
                destination=None,
                max_duration=3.0,
                dry_run=True,
            )

            result = run.process_file(path, options, duration_getter=lambda _: 2.0)

            self.assertEqual(result, "предпросмотр")
            self.assertTrue(path.exists())

    def test_целевая_папка_внутри_исходной_отклоняется(self):
        """Ошибка: перемещение может рекурсивно обработать собственный результат."""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "исходные"
            destination = source / "результат"
            destination.mkdir(parents=True)
            options = SimpleNamespace(
                source=source,
                mode="видео",
                action="переместить",
                destination=destination,
                max_duration=3.0,
                dry_run=False,
            )

            self.assertEqual(
                run.validate_options(options),
                "Целевая папка не должна совпадать с исходной или находиться внутри неё.",
            )

    def test_физические_алиасы_исходной_папки_отклоняются(self):
        """Ошибка: иной регистр пути обходит запрет совпадения и вложенности папок."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Источник"
            same_alias = root / "источник"
            parent_alias = root / "ИСТОЧНИК"
            nested_alias = parent_alias / "результат"
            source.mkdir()
            (source / "результат").mkdir()
            if not same_alias.exists():
                same_alias.mkdir()
            if not nested_alias.exists():
                nested_alias.mkdir(parents=True)

            physical_aliases = {
                frozenset((source, same_alias)),
                frozenset((source, parent_alias)),
            }
            real_samefile = Path.samefile

            def samefile(left, right):
                if frozenset((left, right)) in physical_aliases:
                    return True
                return real_samefile(left, right)

            with patch.object(Path, "samefile", autospec=True, side_effect=samefile):
                for destination in (same_alias, nested_alias):
                    with self.subTest(destination=destination):
                        options = run.Options(
                            source=source,
                            mode="видео",
                            action="переместить",
                            destination=destination,
                            max_duration=3.0,
                            dry_run=False,
                        )

                        self.assertEqual(
                            run.validate_options(options),
                            "Целевая папка не должна совпадать с исходной или находиться внутри неё.",
                        )

    def test_ссылка_на_вложенную_целевую_папку_отклоняется(self):
        """Ошибка: ссылка снаружи скрывает физическую вложенность назначения."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "исходные"
            target = source / "вложенная"
            target.mkdir(parents=True)
            destination = root / "ссылка"
            destination.symlink_to(target, target_is_directory=True)
            options = run.Options(
                source=source,
                mode="видео",
                action="переместить",
                destination=destination,
                max_duration=3.0,
                dry_run=False,
            )

            self.assertEqual(
                run.validate_options(options),
                "Целевая папка не должна совпадать с исходной или находиться внутри неё.",
            )

    def test_перемещение_сохраняет_вложенность_файла(self):
        """Ошибка: перемещение теряет подпапку или оставляет файл на прежнем месте."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "исходные"
            path = source / "вложено" / "screen.png"
            path.parent.mkdir(parents=True)
            path.touch()
            destination = root / "целевые"
            destination.mkdir()
            options = run.Options(
                source=source,
                mode="скриншоты",
                action="переместить",
                destination=destination,
                max_duration=3.0,
                dry_run=False,
            )

            result = run.process_file(path, options)

            self.assertEqual(result, "перемещено")
            self.assertFalse(path.exists())
            self.assertTrue((destination / "вложено" / "screen.png").exists())

    def test_удаление_видео_отправляет_файл_в_корзину(self):
        """Ошибка: видео удаляется в обход Корзины или получает неверный статус."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mov"
            path.touch()
            options = run.Options(
                source=Path(directory),
                mode="видео",
                action="удалить",
                destination=None,
                max_duration=3.0,
                dry_run=False,
            )
            sent = []

            with patch.object(run, "send_to_trash", side_effect=sent.append):
                result = run.process_file(path, options, duration_getter=lambda _: 2.0)

            self.assertEqual(result, "удалено")
            self.assertEqual(sent, [path])

    def test_сводка_группирует_результаты_обработки(self):
        """Ошибка: пропуски и ошибки не попадают в итоговую сводку."""
        result = run.summarize_results(
            ["перемещено", "удалено", "предпросмотр", "длинное видео", "ошибка длительности", "ошибка: доступ"]
        )

        self.assertEqual(
            result,
            {
                "найдено": 6,
                "перемещено": 1,
                "удалено": 1,
                "предпросмотр": 1,
                "пропущено": 1,
                "ошибки": 2,
            },
        )

    def test_worker_передаёт_прогресс_в_главный_поток_через_after(self):
        """Ошибка: worker обновляет UI напрямую или теряет шаги прогресса."""
        app = object.__new__(run.MediaFilterApp)
        scheduled = []
        app.root = SimpleNamespace(
            after=lambda delay, callback, *args: scheduled.append(
                (delay, callback.__name__, args)
            )
        )
        options = run.Options(
            source=Path("/медиа"),
            mode="видео",
            action="удалить",
            destination=None,
            max_duration=3.0,
            dry_run=True,
        )
        files = [Path("/медиа/1.mov"), Path("/медиа/2.mov")]

        with (
            patch.object(run, "collect_media", return_value=files),
            patch.object(run, "process_file", side_effect=["предпросмотр", "предпросмотр"]),
        ):
            app._worker(options, None)

        self.assertEqual(
            scheduled,
            [
                (0, "_prepare_progress", (2,)),
                (0, "_append_log", ("/медиа/1.mov: предпросмотр",)),
                (0, "_update_progress", (1, 2)),
                (0, "_append_log", ("/медиа/2.mov: предпросмотр",)),
                (0, "_update_progress", (2, 2)),
                (
                    0,
                    "_finish",
                    (
                        {
                            "найдено": 2,
                            "перемещено": 0,
                            "удалено": 0,
                            "предпросмотр": 2,
                            "пропущено": 0,
                            "ошибки": 0,
                        },
                    ),
                ),
            ],
        )

    def test_отказ_от_установки_зависимости_не_запускает_worker(self):
        """Ошибка: установка или обработка начинается без явного подтверждения."""
        with tempfile.TemporaryDirectory() as directory:
            app = object.__new__(run.MediaFilterApp)
            app.root = object()
            app.mode = SimpleNamespace(get=lambda: "видео")
            app.action = SimpleNamespace(get=lambda: "удалить")
            app.source = SimpleNamespace(get=lambda: directory)
            app.destination = SimpleNamespace(get=lambda: "")
            app.max_duration = SimpleNamespace(get=lambda: "3")
            log = []
            prompts = []
            app._append_log = log.append
            app._set_running = lambda _: self.fail("Обработка была запущена")
            dialog = SimpleNamespace(
                askyesno=lambda title, text, parent: prompts.append((title, text)) or False
            )

            with (
                patch.object(run, "missing_dependency", return_value="FFmpeg"),
                patch.object(run, "messagebox", dialog),
                patch.object(
                    run.threading,
                    "Thread",
                    side_effect=AssertionError("Создан рабочий поток"),
                ),
            ):
                app._start(dry_run=False)

        self.assertEqual(log, ["Установка FFmpeg отменена пользователем."])
        self.assertEqual(prompts[0][0], "Необходима зависимость")

    def test_зависимости_подсказываются_для_выбранного_режима(self):
        """Ошибка: приложению не удаётся подсказать Pillow или FFmpeg для режима."""
        self.assertEqual(run.dependencies_for("видео"), ["FFmpeg"])
        self.assertEqual(run.dependencies_for("скриншоты"), ["Pillow"])

    def test_скриншот_нельзя_направить_в_корзину_прямым_вызовом(self):
        """Ошибка: прямой вызов отправляет скриншот в Корзину в обход проверки UI."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "screen.png"
            path.touch()
            options = run.Options(
                source=Path(directory),
                mode="скриншоты",
                action="удалить",
                destination=None,
                max_duration=3.0,
                dry_run=False,
            )

            with patch.object(run, "send_to_trash", side_effect=AssertionError("Вызвана Корзина")):
                with self.assertRaisesRegex(ValueError, "Скриншоты можно только перемещать"):
                    run.process_file(path, options)

            self.assertTrue(path.exists())

    def test_отсутствующий_ffprobe_возвращает_ошибку_длительности(self):
        """Ошибка: отсутствие ffprobe прерывает обработку исключением."""
        with patch.object(run.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(run.get_video_duration(Path("clip.mov")))


if __name__ == "__main__":
    unittest.main()

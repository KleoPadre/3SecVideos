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
                "пропущено": 2,
                "ошибки": 1,
            },
        )

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

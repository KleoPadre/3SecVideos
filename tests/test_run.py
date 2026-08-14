"""Проверки чистых функций единого фильтра медиа."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image, PngImagePlugin

import run


class RunTests(unittest.TestCase):
    """Проверяет отбор файлов и построение путей назначения."""

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


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

import video_filter


class VideoFilterTests(unittest.TestCase):
    def test_ролик_на_границе_порога_подходит(self):
        """Ошибка: строгое сравнение исключает видео длительностью ровно 3 секунды."""
        self.assertTrue(video_filter.is_short_video(3.0, 3.0))

    def test_конфликт_имени_получает_суффикс(self):
        """Ошибка: перемещение перезаписывает уже существующий файл."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source = source_root / "nested" / "clip.mov"
            source.parent.mkdir(parents=True)
            source.touch()
            destination_root = root / "target"
            existing = destination_root / "nested" / "clip.mov"
            existing.parent.mkdir(parents=True)
            existing.touch()

            result = video_filter.unique_destination(source, destination_root, source_root)

            self.assertEqual(result, destination_root / "nested" / "clip_1.mov")

    def test_предпросмотр_не_изменяет_короткое_видео(self):
        """Ошибка: режим предпросмотра удаляет файл вместо простого вывода плана."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mov"
            path.touch()
            options = video_filter.Options(
                source=Path(directory),
                action="удалить",
                destination=None,
                max_duration=3.0,
                dry_run=True,
            )

            result = video_filter.process_video(path, options, duration_getter=lambda _: 2.0)

            self.assertEqual(result, "предпросмотр")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()

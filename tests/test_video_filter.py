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


if __name__ == "__main__":
    unittest.main()

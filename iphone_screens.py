import os
from PIL import Image
import shutil
from datetime import datetime

LOG_FILE = 'screens.log'


def init_logging():
    """Создаёт лог-файл и добавляет его в .gitignore"""
    # Создание log-файла, если не существует
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            f.write(f"[{datetime.now()}] Лог-файл создан\n")

    # Добавление log-файла в .gitignore
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r+') as f:
            lines = f.read().splitlines()
            if LOG_FILE not in lines:
                f.write(f'\n{LOG_FILE}\n')
    else:
        with open('.gitignore', 'w') as f:
            f.write(f'{LOG_FILE}\n')


def log(message):
    """Запись в лог-файл и вывод в консоль"""
    print(message)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{message}\n")


def move_screenshots(source_folder, destination_folder):
    log(f"Исходная папка: {source_folder}")
    log(f"Целевая папка: {destination_folder}")

    if not os.path.exists(source_folder):
        log(f"Папка {source_folder} не найдена")
        return

    matched_files = []
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            full_path = os.path.join(root, file)
            matched_files.append(full_path)

    total_files = len(matched_files)
    log(f"Найдено {total_files} файлов (включая подпапки)")

    for idx, file_path in enumerate(matched_files, start=1):
        file = os.path.basename(file_path)

        try:
            image = Image.open(file_path)
        except Exception as e:
            log(f"[{idx}/{total_files}] Файл {file} пропущен (не изображение). Ошибка: {e}")
            continue

        metadata = image.info
        log(f"[{idx}/{total_files}] Файл {file} метаданные: {metadata}")

        if any('Screenshot' in str(value) for value in metadata.values()):
            destination_path = os.path.join(destination_folder, file)

            base, ext = os.path.splitext(file)
            counter = 1
            while os.path.exists(destination_path):
                destination_path = os.path.join(destination_folder, f"{base}_{counter}{ext}")
                counter += 1

            shutil.move(file_path, destination_path)
            log(f"[{idx}/{total_files}] Файл {file} перемещен в {destination_path}")
        else:
            log(f"[{idx}/{total_files}] Файл {file} пропущен (не содержит 'Screenshot' в метатегах)")


# === Точка входа ===
source_folder = ''
destination_folder = ''

init_logging()
move_screenshots(source_folder, destination_folder)

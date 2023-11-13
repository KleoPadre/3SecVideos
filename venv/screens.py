import os
from PIL import Image
import shutil

def move_screenshots(source_folder, destination_folder):
    # Получаем список файлов
    files = [f for f in os.listdir(source_folder) if os.path.isfile(os.path.join(source_folder, f))]
    total_files = len(files)

    for idx, file in enumerate(files, start=1):
        file_path = os.path.join(source_folder, file)

        # Проверяем, является ли файл изображением
        try:
            image = Image.open(file_path)
        except Exception as e:
            print(f"[{idx}/{total_files}] Файл {file} пропущен (не изображение)")
            continue

        # Получаем все метаданные изображения
        metadata = image.info

        # Проверяем наличие подстроки "Screenshot" в любом из метатегов
        if any('Screenshot' in str(value) for value in metadata.values()):
            # Перемещаем файл в указанную папку
            destination_path = os.path.join(destination_folder, file)
            shutil.move(file_path, destination_path)
            print(f"[{idx}/{total_files}] Файл {file} перемещен в {destination_path}")
        else:
            print(f"[{idx}/{total_files}] Файл {file} пропущен (не содержит 'Screenshot' в метатегах)")

# Укажите пути к папкам
source_folder = '/Volumes/homes/Elya/Photos/MobileBackup/iPhone Elvira Osipova/2023/11'
destination_folder = '/Users/levon.osipov/Downloads/unt

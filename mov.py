import os
import shutil
import moviepy.editor as mp

source_folder = '...'
destination_folder = '...'

# Функция для перемещения файла с сохранением подпапок
def move_video_file(src, dst):
    # Получаем относительный путь файла от исходной папки
    rel_path = os.path.relpath(src, source_folder)
    dst_path = os.path.join(destination_folder, rel_path)

    # Создаем папку назначения, если она не существует
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    # Перемещаем файл
    shutil.move(src, dst_path)

# Расширения видеофайлов
video_extensions = ['.mp4', '.avi', '.mov', '.mkv']

# Счетчики для общего числа файлов и текущего прогресса
total_files = 0
current_file = 0

# Функция для подсчета общего числа файлов
def count_files(root_folder):
    global total_files
    for root, dirs, files in os.walk(root_folder):
        total_files += len(files)

# Подсчитываем общее количество файлов
count_files(source_folder)

# Пройдемся по всем файлам в исходной папке и её подпапках
for root, dirs, files in os.walk(source_folder):
    for file in files:
        current_file += 1
        file_path = os.path.join(root, file)
        file_extension = os.path.splitext(file_path)[-1].lower()
        try:
            # Проверим длительность видео и расширение файла
            if file_extension in video_extensions:
                video = mp.VideoFileClip(file_path)
                if video.duration < 3:
                    move_video_file(file_path, destination_folder)
                    print(f'[{current_file}/{total_files}] Moved: {file_path}')
                else:
                    print(f'[{current_file}/{total_files}] Skipped (Duration > 3 seconds): {file_path}')
            else:
                print(f'[{current_file}/{total_files}] Skipped (Not a video file): {file_path}')
        except Exception as e:
            # Если произошла ошибка при чтении файла как видео, проигнорируем его
            print(f'[{current_file}/{total_files}] Error: {file_path} - {str(e)}')
            pass

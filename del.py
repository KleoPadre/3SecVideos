import os
import shutil
import moviepy.editor as mp

source_folder = '/Volumes/photo'

# Функция для удаления файла
def delete_video_file(file_path):
    try:
        os.remove(file_path)
        print(f'Deleted: {file_path}')
    except Exception as e:
        print(f'Error: {file_path} - {str(e)}')

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
                    delete_video_file(file_path)
                    print(f'[{current_file}/{total_files}] Deleted: {file_path}')
                else:
                    print(f'[{current_file}/{total_files}] Skipped (Duration > 3 seconds): {file_path}')
            else:
                print(f'[{current_file}/{total_files}] Skipped (Not a video file): {file_path}')
        except Exception as e:
            # Если произошла ошибка при чтении файла как видео, проигнорируем его
            print(f'[{current_file}/{total_files}] Error: {file_path} - {str(e)}')
            pass

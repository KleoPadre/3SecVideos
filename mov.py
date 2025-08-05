import os
import shutil
import subprocess

source_folder = ''
destination_folder = ''

# Расширения видеофайлов
video_extensions = ['.mp4', '.avi', '.mov', '.mkv']

# Счетчики для общего числа файлов и текущего прогресса
total_files = 0
current_file = 0

# Функция для подсчета общего количества файлов
def count_files(root_folder):
    global total_files
    for root, dirs, files in os.walk(root_folder):
        total_files += len(files)

# Функция для получения длительности видео через ffprobe
def get_video_duration(file_path):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())
    except:
        return None

# Функция для перемещения файла с сохранением подпапок
def move_video_file(src, dst):
    rel_path = os.path.relpath(src, source_folder)
    dst_path = os.path.join(destination_folder, rel_path)
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.move(src, dst_path)

# Подсчитываем общее количество файлов
count_files(source_folder)

# Пройдемся по всем файлам
for root, dirs, files in os.walk(source_folder):
    for file in files:
        current_file += 1
        file_path = os.path.join(root, file)
        file_extension = os.path.splitext(file_path)[-1].lower()

        try:
            if file_extension in video_extensions:
                duration = get_video_duration(file_path)
                if duration is None:
                    print(f'[{current_file}/{total_files}] Error: {file_path} - Unable to get duration')
                elif duration < 3:
                    move_video_file(file_path, destination_folder)
                    print(f'[{current_file}/{total_files}] Moved: {file_path}')
                else:
                    print(f'[{current_file}/{total_files}] Skipped (Duration > 3 seconds): {file_path}')
            else:
                print(f'[{current_file}/{total_files}] Skipped (Not a video file): {file_path}')
        except Exception as e:
            print(f'[{current_file}/{total_files}] Error: {file_path} - {str(e)}')

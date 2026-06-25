import os, sys, tempfile
from datetime import datetime
from PIL import Image
import subprocess
from datetime import datetime

def save_image_from_clipboard():
    # Проверяем, есть ли изображение в буфере обмена
    check_image_script = '''
    xclip -selection clipboard -t TARGETS -o | grep -q image/png
    '''
    result = subprocess.run(['bash', '-c', check_image_script])

    if result.returncode != 0:
        print("Изображение не найдено в буфере обмена.")
        return

    # Генерируем имя файла на основе текущей даты и времени
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H-%M-%S")
    file_name_path = f"/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Screenshots/Screenshot {current_time} {current_date}.png"

    # Сохраняем изображение из буфера обмена
    save_image_script = f'''
    xclip -selection clipboard -t image/png -o > "{file_name_path}"
    '''
    subprocess.run(['bash', '-c', save_image_script])
    print(f"Изображение сохранено: {file_name_path}")

if __name__ == "__main__":
    save_image_from_clipboard()
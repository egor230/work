import shutil, subprocess, pyperclip, time, os
from PIL import Image
adress_image = pyperclip.paste()
#adress_image = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Screenshots/разметка.jpg"
# time.sleep(0.1)
# Получаем расширение файла
file_extension = os.path.splitext(adress_image)[1]

# Новый путь с новым именем
new_file_name = "new" + file_extension
output_image_path = os.path.join("/home/egor/Downloads/", new_file_name)

# Копируем файл
shutil.copy(adress_image, output_image_path)

# # Используем ImageMagick для конвертации
# subprocess.run(['convert', adress_image, output_image_path])
while 1:
  time.sleep(1)
  if os.path.exists(output_image_path):
   #print("Файл найден:", output_image_path)
   # pyperclip.copy(output_image_path)
   break


# Формируем bash-команду с использованием правильной подстановки
show_list_id = f'''#!/bin/bash
  copyq write image/png - < "{output_image_path}" # Помещаем изображение в буфер обмена
  sleep 3
  copyq insert 1  
  copyq select 0
'''

# Запуск команды
subprocess.run(['bash', '-c', show_list_id])









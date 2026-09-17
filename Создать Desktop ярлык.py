import os, subprocess, sys, re

def find_best_icon(image_list, search_name):
 """
 Ищет наиболее подходящую иконку по имени с учетом приоритетов.

 Приоритеты:
 1. Точное совпадение имени (без учета регистра и расширения)
 2. Имя + суффикс 'icon', 'logo', 'cover'
 3. Частичное совпадение (подстрока)

 Внутри каждой категории предпочтение отдается форматам: svg > png > jpg > bmp
 """
 if not image_list or not search_name:
  return None
 
 # Приоритеты расширений (чем меньше индекс, тем лучше)
 EXT_PRIORITY = {'.svg': 0, '.png': 1, '.jpg': 2, '.jpeg': 2, '.gif': 3, '.bmp': 4}
 
 search_lower = search_name.lower()
 candidates = []
 
 for image in image_list:
  name_part, ext = os.path.splitext(image)
  name_lower = name_part.lower()
  ext_lower = ext.lower()
  
  if ext_lower not in EXT_PRIORITY:
   continue
  
  score = float('inf')
  
  # Категория 0: Точное совпадение имени файла
  if name_lower == search_lower:
   score = 0
  # Категория 1: Имя + стандартные суффиксы для иконок
  elif re.match(rf'^{re.escape(search_lower)}[-_]?(icon|logo|cover|art)$', name_lower):
   score = 10
  # Категория 2: Имя является началом строки (префикс)
  elif name_lower.startswith(search_lower):
   score = 20 + len(name_lower) - len(search_lower)
  # Категория 3: Подстрока (наименее желательный вариант)
  elif search_lower in name_lower:
   score = 100 + len(name_lower) - len(search_lower)
  else:
   continue
  
  # Добавляем приоритет расширения к общему счету
  total_score = score + EXT_PRIORITY.get(ext_lower, 99) * 0.1
  candidates.append((total_score, image))
 
 if not candidates:
  return None
 
 # Сортируем по счету и берем лучший результат
 candidates.sort(key=lambda x: x[0])
 return candidates[0][1]


def get_files_with_extensions(folder_path):
 """Рекурсивно собирает все изображения в папке."""
 image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'}
 image_files = []
 
 for root, dirs, files in os.walk(folder_path):
  for file in files:
   _, ext = os.path.splitext(file)
   if ext.lower() in image_extensions:
    image_files.append(file)
 
 return image_files


def get_paths_file():
 """Парсит аргументы командной строки и возвращает пути."""
 # Объединяем аргументы (на случай если путь содержит пробелы и передан частями)
 url = " ".join(str(arg) for arg in sys.argv[1:]).strip()
 
 if not url:
  print("Ошибка: Не передан путь к файлу.")
  sys.exit(1)
 
 full_path = url
 directory = os.path.dirname(full_path)
 filename = os.path.basename(full_path)
 
 filename_without_extension = os.path.splitext(filename)[0]
 
 return directory, filename_without_extension, filename, full_path


# === Основная логика ===
directory, filename_without_extension, filename, full_path = get_paths_file()

# Получаем список картинок и ищем лучшую иконку
image_list = get_files_with_extensions(directory)
best_icon_name = find_best_icon(image_list, filename_without_extension)

# Формируем полный путь к иконке или оставляем пустым, если не найдено
if best_icon_name:
 icon_path = os.path.join(directory, best_icon_name)
else:
 icon_path = ""  # Будет использована стандартная иконка системы
 print(f"Предупреждение: Иконка для '{filename_without_extension}' не найдена.")

# Генерация .desktop файла
desktop_content = f"""[Desktop Entry]
Name={filename_without_extension}
Exec=xdg-open "{full_path}"
Icon="{icon_path}"
Terminal=false
Type=Application
"""

output_file = os.path.join(directory, filename_without_extension)
print(f"Создание файла: {output_file}")

with open(output_file, 'w') as f:
 f.write(desktop_content)

# Установка прав на исполнение
chmod_cmd = f'chmod +x "{output_file}"'
subprocess.run(['bash', '-c', chmod_cmd])




# url = url.strip()# os.chdir(url)# Убираем лишний пробел в конце строки
# directory = os.path.dirname(url) # Получение имени файла
# filename = os.path.basename(url)
#
# if '.' in filename:  # Удаление расширения
#  filename_without_extension = filename[:filename.rfind('.')]#  os.remove(os.path.join(url, filename))
# else:
#   filename_without_extension = filename

# file=os.path.join(directory, filename_without_extension).sh

# t = "{0}\n{1}\n{2}\n{3}".format(url, directory, filename, filename_without_extension)
#
#
# file_path = '/home/egor/Рабочий стол/1.txt'
# with open(file_path, 'w') as file:
#   # Записываем текст в файл
#  file.write(t)
#   print("У файла нет расширения")
# script = ("#!/bin/bash\n"
#           "cd \"{0}\";\n"
#           "./{1};\n"
#           "exit;".format(directory,filename))
#
#
# # print(parent_dir)
# # print(script)
# parent_dir=(str(directory+"/"+filename)+".sh")
# # parent_dir = parent_dir.replace(' ', '\ ')  # Замена пробелов на экранированные
# print(parent_dir)
# print(url)
# with open(parent_dir,'w') as f:
#    f.write(script)

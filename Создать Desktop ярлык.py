import os, subprocess, sys, re


def find_most_similar_image(image_list, search_name):
 """
 Ищет наиболее похожую картинку в списке по заданному имени с помощью регулярных выражений.

 Args:
     image_list (list): Список имен файлов картинок.
     search_name (str): Имя для поиска (например, "splintercell3").

 Returns:
     str or None: Имя наиболее подходящего файла или None, если ничего не найдено.
 """
 if not image_list or not search_name:
  return None

 # Экранируем входное имя для безопасного использования в регулярке
 search_pattern = re.escape(search_name.lower())

 best_match = None
 best_score = float('inf')  # Чем меньше "лишнего" текста, тем лучше

 for image in image_list:
  # Ищем совпадение в имени файла (игнорируем регистр)
  image_lower = image.lower()
  match = re.search(search_pattern, image_lower)

  if match:
   # Вычисляем "лишний" текст (до и после совпадения)
   extra_chars = len(image_lower) - len(search_name)

   # Если совпадение точное или с минимальным добавлением, обновляем лучший результат
   if extra_chars < best_score:
    best_score = extra_chars
    best_match = image
 return best_match

def get_files_with_extensions(folder_path):
 image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']  # список расширений изображений
 image_files = []  # список для хранения имен изображений
 for root, dirs, files in os.walk(folder_path):
  for file in files:
   # print(file)
   _, ext = os.path.splitext(file)
   if ext.lower() in image_extensions:
    image_files.append(file)
 return image_files
def get_paths_file():  #  Получаем аргументы командной строки
  num_args = len(sys.argv)# Получаем количество аргументов
  url = ""
  for arg in sys.argv[1:]:
    url += str(arg) + " "# Объединяем аргументы через цикл for
  # url="/mnt/807EB5FA7EB5E954/games/Splinter Cell - Chaos Theory/System/splintercell3.sh"
  full_path = url.strip()
  directory = os.path.dirname(full_path)
  filename = os.path.basename(full_path)
  if '.' in filename:
    filename_without_extension = filename[:filename.rfind('.')]   # extension = filename[filename.rfind('.') + 1:]
  else:
    filename_without_extension = filename    # extension = None
  return directory, filename_without_extension, filename, full_path

directory, filename_without_extension, filename, full_path = get_paths_file()
image_list = get_files_with_extensions(directory)
image = filename_without_extension
image = find_most_similar_image(image_list, image)
image = str(os.path.join(directory, image))
# image="/mnt/807EB5FA7EB5E954/games/Splinter Cell - Chaos Theory/System/splintercell3logo.bmp"
show_list_id = '''
[Desktop Entry]
Name={0}
Exec=xdg-open "{1}"
Icon="{2}"
Terminal=false
Type=Application
exit; '''.format(filename_without_extension,full_path,image)  # показать список устройств в терминале
file=str(os.path.join(directory, filename_without_extension))
print(file)
with open(file, 'w') as f:    # Записываем текст в файл
  f.write(show_list_id)

show_list_id = '''#!/bin/bash\n
chmod +x "{0}"\n'''.format( file)
subprocess.run(['bash', '-c', show_list_id])





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

import os, subprocess, sys

def get_paths_file():  # Получаем аргументы командной строки
  num_args = len(sys.argv)  # Получаем количество аргументов
  url = ""
  for arg in sys.argv[1:]:
    url += str(arg) + " "  # Объединяем аргументы через цикл for
  
  url = url.strip()
  directory = os.path.dirname(url)
  filename = os.path.basename(url)
  if '.' in filename:
    filename_without_extension = filename[:filename.rfind('.')]  # extension = filename[filename.rfind('.') + 1:]
  else:
    filename_without_extension = filename  # extension = None
  return directory, filename_without_extension, filename

# Применяем функцию и сохраняем результаты в соответствующие переменные
directory, filename_without_extension, filename = get_paths_file()

# Формируем полный путь к файлу, соединяя директорию и имя файла, и убираем лишние символы
file1 = str(os.path.join(directory, filename)).replace('\'','')
show_list_id = '''#!/bin/bash
#gnome-terminal -- bash -c ' 
PYTHON_EXECUTABLE="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python" # Путь к скрипту
SCRIPT_PATH=\"{0}\"; # Команда для запуска:
\"$PYTHON_EXECUTABLE\" \"$SCRIPT_PATH\";
exit;
#exec bash'
 '''.format(file1)  #
file=str(os.path.join(directory, filename_without_extension))+".sh"
with open(file, 'w') as file:    # Записываем текст в файл
    file.write(show_list_id)

show_list_id = '''#!/bin/bash\n
cd "{0}";\n
chmod +x "{1}"\n'''.format(directory,file)
subprocess.run(['bash', '-c', show_list_id])

#
# show_list_id = '''
# щл
#  '''.format(directory,file1)  #
# file=str(os.path.join(directory, filename_without_extension))+".txt"
# with open(file, 'w') as file:    # Записываем текст в файл
#     file.write(show_list_id)


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

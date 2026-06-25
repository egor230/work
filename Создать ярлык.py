import os, subprocess, sys
def get_paths_file():  #  Получаем аргументы командной строки
  # num_args = len(sys.argv)# Получаем количество аргументов
  # url = ""
  # for arg in sys.argv[1:]:
  #   url += str(arg) + " "# Объединяем аргументы через цикл for
  url="/home/egor/.wine/drive_c/Program Files/Paint.NET/PaintDotNet.exe"
  url = url.strip()
  directory = os.path.dirname(url)
  filename = os.path.basename(url)
  if '.' in filename:
    filename_without_extension = filename[:filename.rfind('.')]
    extension = filename[filename.rfind('.') + 1:]
  else:
    filename_without_extension = filename
    extension = None
  return directory, filename_without_extension, filename, extension

directory, filename_without_extension, filename, extension = get_paths_file()
# print(directory, filename_without_extension, filename, sep="  ="  )
# print(extension)
if "exe" in extension:
  full_path_file= str("wine \"")+directory+str(".exe\"")
else:
  full_path_file= directory

# print(full_path_file)
show_list_id = '''[Desktop Entry]
Name={0}
Exec={1}
Terminal=false
Type=Application
 '''.format(filename_without_extension, full_path_file)  # показать список устройств в терминале
file=str(directory) +'/'+ str(filename_without_extension)+str(".Desktop")

with open(file, 'w') as f:    # Записываем текст в файл
    f.write(show_list_id)

print(file)
# print(file1)
show_list_id = '''#!/bin/bash\n
cd "{0}";\n
chmod +x "{1}"\n'''.format(directory,file)
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






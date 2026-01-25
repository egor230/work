import os, subprocess, sys
def get_paths_file():  #  Получаем аргументы командной строки
  num_args = len(sys.argv)# Получаем количество аргументов
  url = ""
  for arg in sys.argv[1:]:
    url += str(arg) + " "# Объединяем аргументы через цикл for
  url = url.strip()
  # url="/mnt/807EB5FA7EB5E954/работа/мартагона/книга/Турция/Глава. 147.  Прогуляемся по Анталии и её окрестностям.doc"
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
full_path_file=directory+str("/")+filename

d =str("/mnt/807EB5FA7EB5E954/развития/книги/наша книга/впадина марса/Том 16")
pdf_path_file=d+str("/")+filename_without_extension+(".pdf")

if "doc" in extension:
  script = '''#!/bin/bash\n
  cd \"{0}\"\n
  # Преобразование в pdf
  libreoffice --headless --convert-to pdf \"{1}\" --outdir  \"{0}\"\n
  chmod +x  "{2}";\n
  xdg-open "{2}";
  exit;'''.format(d, full_path_file,  pdf_path_file)
  subprocess.run(['bash', '-c', script])
  # with open("output.sh", "w") as file:
  #   file.write(script)
  # with open("output.sh", "w") as file:
    # file.write(f"Directory: {d}\n")
    # file.write(f"pdf_path_file: {pdf_path_file}\n")
    # file.write(f"full_path_file: {full_path_file}\n")
    # file.write(script)

  # print(show_list_id)

# with open("/mnt/807EB5FA7EB5E954/работа/мартагона/книга/тест.txt", 'w') as f:
#  f.write(url)
# print(full_path_file,  pdf_path_file, sep="  \n"  )
# input()


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






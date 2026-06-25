import time, json, os,  subprocess, psutil, pyperclip, sys, re
script = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''
# Вызываем скрипт
user = subprocess.run(['bash'], input=script, stdout=subprocess.PIPE, text=True).stdout.strip()

# он возвращает имя пользователя (user)
# Создание строки script1 с использованием f-строки и списка
def check_current_active_window(user):# Получаем идентификатор активного окна
 script1 = f'''#!/bin/bash
 sleep 1;
 ps aux;
 sleep 1;
 exit
 '''
 result = str(subprocess.run(['bash'], input=script1, stdout=subprocess.PIPE, text=True).stdout)
 lines = result.split('\n')
 result=[]
 for item in lines:
  item=str(item)
  # print(item)
  if not 'root' or user in item:
   result.append(item)
 script2 = f'''#!/bin/bash
 sleep 1;
 # Получаем идентификатор активного окна
 active_window_id=$(xdotool getactivewindow)

# Получаем идентификатор процесса активного окна
 process_id_active=$(xdotool getwindowpid $active_window_id)

# Выводим результаты
 echo "Active Window ID: $active_window_id"
 echo "Process ID of Active Window: $process_id_active"

 sleep 1;
 exit
 '''
 result1 = subprocess.run(['bash'], input=script2, stdout=subprocess.PIPE, text=True).stdout.strip()

 # Разбиваем вывод по новой строке и извлекаем значения
 lines = result1.split('\n')
 active_window_id = int(lines[0].split(': ')[1])
 process_id_active = int(lines[1].split(': ')[1]) # print(active_window_id)
 a = []
 time.sleep(0.53)
 for line in result:   # print(line)
   user_name = ' '.join(line.split()[:1])# расположение exe
   pid_id = int(line.split()[1])  # id потока
   if user_name==user and pid_id==process_id_active:# Только процессоры запущенны от имени пользователя
    dir_process_name = ' '.join(line.split()[10:])# расположение exe
    filename = str(dir_process_name.split('\\')[-1])# имя процесса.
    if '.exe' in filename:     # print("filename ", filename, sep=" ")
     try:      # a.append({'dir': dir_process_name, 'pid': pid_id, 'exe': filename})# нашли pid активного  окна
      return dir_process_name# активного окна
     except:
       pass
 return dir_process_name
while 1:
 d= check_current_active_window(user)
 print(d)
 time.sleep(6)
    # pass
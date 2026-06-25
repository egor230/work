import subprocess
import time

get_user_name = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''
user = subprocess.run(['bash'], input=get_user_name, stdout=subprocess.PIPE, text=True).stdout.strip()
def get_pid_and_path_window():# Получаем идентификатор активного окна
  result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout) #  # print(result)
  lines = result.split('\n')
  a = [line for line in lines if user in line]  # Убираем 'root' из условия
  data_dict = {}
  for i in a:   # print(i)
   dir_process_name = i.split(maxsplit=10)[10].replace('\\', '/')  # Извлекаем нужную часть строки
   pid_id = int(i.split()[1])  # id потока
   # data_dict[pid_id] = dir_process_name  # Создаем объект для текущего pid_id
   data_dict[dir_process_name] = pid_id  # С
  return  data_dict

get_process_id_active = f'''#!/bin/bash
# Получаем идентификатор активного окна
active_window_id=$(xdotool getactivewindow)
process_id_active=$(xdotool getwindowpid $active_window_id) # Получаем идентификатор процесса активного окна
echo "$process_id_active" # Выводим только идентификатор процесса
exit '''
while 1:
  time.sleep(3)

  res=get_pid_and_path_window()
  for i in res:
   if "/usr/bin/copyq -s"  in i:
    pid_id =res[i]
    result1 = subprocess.run(['bash'], input=get_process_id_active, stdout=subprocess.PIPE, text=True).stdout.strip()
    lines = result1.split('\n')  # Разбиваем вывод по новой строке и извлекаем значения
    process_id_active = int(lines[0].split(': ')[0]) #
    print(process_id_active)
    # if res[i]==process_id_active:
    #  print(pid_id)
    #  print(i)
    #  break
#   f = '''#!/bin/bash
#        kill {}   '''.format(pid_id)
#   subprocess.call(['bash', '-c', f])
# f = '''#!/bin/bash
#      while true; do
#       sleep 2
#       if [ -z "$(copyq clipboard)" ]; then
#          echo "empty"
#          copyq select 0
#          sleep 3
#          break
#         fi
#       done
#       exit; '''
# subprocess.call(['bash', '-c', f])



  #
# if "WINWORD.EXE" in res[90710]:
#   print("ok")
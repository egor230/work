import subprocess

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


res=get_pid_and_path_window()
for i in res:
 if "/mnt/807EB5FA7EB5E954/python_linux/Script.sh"  in i and  "xed" not in i:
  pid_id =res[i]#  print(1)
  f = '''#!/bin/bash
       kill {}   '''.format(pid_id)
  subprocess.call(['bash', '-c', f])
f = '''#!/bin/bash
    cd "/mnt/807EB5FA7EB5E954/python_linux";
    ./"Script.sh"; '''
subprocess.call(['bash', '-c', f])



  #
# if "WINWORD.EXE" in res[90710]:
#   print("ok")
import re
import subprocess, time, json

import psutil

get_user_name = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''
get_main_id = '''#!/bin/bash # Получаем идентификатор активного окна
    active_window_id=$(xdotool getactivewindow 2>/dev/null)
    if [ -n "$active_window_id" ]; then
        process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
        echo "$process_id_active"
    else
        echo "0"  # Или любое значение по умолчанию, если нет активного окна
    fi
    exit'''
def get_process_info():
  process_info = {}
  p=['wine', 'portpoton']
  for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
      pid = proc.info['pid']
      name = proc.info['name']
      cmdline = proc.info['cmdline']      # Проверка, что cmdline не является None
      if cmdline is None:
        continue
      # Проверка, запущен ли процесс через Wine
      for program in p:
       if program in name.lower() or any(program in part.lower() for part in cmdline):
        # Поиск .exe файла в командной строке
        exe_path = next((part for part in cmdline if part.endswith('.exe')), None)
        if exe_path:       # Извлечение части пути, начинающейся с /mnt и включающей .exe
          match = re.search(r'/mnt/.*?\.exe', exe_path)
          if match:
           exe_path = match.group(0)
           # print(pid)
           # print(exe_path)
           process_info[pid]= exe_path
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
      continue
  return process_info

def replace_path_in_dict(d):
		# Определяем новый префикс
		new_prefix = next(('/'.join(value.split('/')[:4]) + '/' for value in d.values() if value.startswith('/mnt/')), None)
		if new_prefix is None:
			raise ValueError("Не удалось определить новый префикс.")

		updated_dict = {}
		for key, value in d.items():
			# Если путь уже начинается с /mnt/, оставляем как есть
			if value.startswith('/mnt/'):
				updated_value = value
			else:
				# Заменяем X:/ на new_prefix
				updated_value = re.sub(r'^[A-Z]:/', new_prefix, value, count=1)
				# Убираем дублирование /games/games/ или других частей
				parts = updated_value.split('/')
				# Удаляем повторяющиеся сегменты после new_prefix
				unique_parts = []
				for part in parts:
					if not unique_parts or part != unique_parts[-1]:
						unique_parts.append(part)
				updated_value = '/'.join(unique_parts)

			# Добавляем .exe, если его нет
			if isinstance(updated_value, str) and not updated_value.lower().endswith('.exe'):
				updated_value += '.exe'

			updated_dict[key] = updated_value

		return updated_dict

user = subprocess.run(['bash'], input=get_user_name, stdout=subprocess.PIPE, text=True).stdout.strip()
def get_pid_and_path_window():# Получаем идентификатор активного окна
  process_id = int(subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip())

  # Получаем имя текущего пользователя
  user = subprocess.run(['whoami'], stdout=subprocess.PIPE, text=True).stdout.strip()

  # Регулярное выражение для поиска путей к .exe файлам
  pattern = re.compile(r'(/mnt/.*?\.exe)|([A-Z]:/.*?\.exe)', re.IGNORECASE)

  data_dict = {}

  # Один проход по всем процессам пользователя
  for proc in psutil.process_iter(['pid', 'username', 'cmdline']):
    if proc.info['username'] == user and proc.info['cmdline']:
      cmdline = ' '.join(proc.info['cmdline']).replace('\\', '/')
      match = pattern.search(cmdline)
      if match:
        file_path = match.group(0)
        # Обработка пути: берём часть после .sh, если есть
        file_path = file_path.split('.sh', 1)[-1].strip() if '.sh' in file_path else file_path
        # Уточняем путь до /mnt/... (если требуется)
        match_mnt = re.search(r'/mnt/[^ ]+', file_path)
        if match_mnt:
          file_path = match_mnt.group(0)
        data_dict[proc.info['pid']] = file_path

  for i in data_dict:
	  print(i, data_dict[i], sep=" = ")
  # Обновляем словарь с помощью внешних функций (если они есть)
  data_dict1 = get_process_info()
  data_dict.update(data_dict1)
  updated_dict = replace_path_in_dict(data_dict)
  # Добавляем .exe, если его нет
  return updated_dict, process_id
  # data_dict = replace_path_in_dict(data_dict)
  # for i in data_dict:
  #   print(i, data_dict[i], sep=" = ")
  # except:
  #   pass

# Вызываем скрипт

while 1:
 time.sleep(5)
 data_dict , process_id=get_pid_and_path_window()
 # print("окно ", process_id, sep=" = ")
 # if process_id in data_dict:
	#  print(data_dict[process_id])
 # print(data_dict)
 for i in data_dict:
  print(i, data_dict[i], sep=" = ")
 input()
    # pass
# if '.exe' in filename and process_id == pid_id:
#   process_name = re.findall(r'"([^"]*)"', process_name)[0]
# print(line)    # print(process_name)     # print(user_name)       # print(process_id)       # print(pid_id)
# a.append({'dir': process_name, 'pid': pid_id, 'exe': filename})# нашли pid активного  окна
# return True# активного окна
'''
  process_id = 550149
541896 = /mnt/807EB5FA7EB5E954/games/Alien Isolation/AI.exe
550149 = /mnt/807EB5FA7EB5E954/games/Alien Isolation/AI.exe
550295 = /mnt/807EB5FA7EB5E954/games/Alien Isolation/AI.exe
551093 = /mnt/807EB5FA7EB5E954/games/Alien Isolation/AI.exe
551392 = /mnt/807EB5FA7EB5E954/games/Alien Isolation/AI.exe
553396 = /mnt/807EB5FA7EB5E954/games/Alien Isolation/AI.exe
'''
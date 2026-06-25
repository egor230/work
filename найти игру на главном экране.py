import re, subprocess, time, psutil

def get_process_info():
  process_info = {}
  for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
      pid = proc.info['pid']
      name = proc.info['name']
      cmdline = proc.info['cmdline']      # Проверка, что cmdline не является None
      if cmdline is None:
        continue      # Проверка, запущен ли процесс через Wine
      exe_path = next((part for part in cmdline if part.endswith('.exe')), None)
      if exe_path:       # Извлечение части пути, начинающейся с /mnt и включающей .exe
       match = re.search(r'/mnt/.*?\.exe', exe_path)
       if match:
        exe_path = match.group(0)      # print(pid)         # print(exe_path)
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
    if value.startswith('/mnt/'):    # Если путь уже начинается с /mnt/, оставляем как есть
      updated_value = value
    else:      # Заменяем X:/ на new_prefix
      updated_value = re.sub(r'^[A-Z]:/', new_prefix, value, count=1)
      # Убираем дублирование /games/games/ или других частей
      parts = updated_value.split('/') # Удаляем повторяющиеся сегменты после new_prefix
      unique_parts = []
      for part in parts:
        if not unique_parts or part != unique_parts[-1]:
          unique_parts.append(part)
      updated_value = '/'.join(unique_parts)
    # Добавляем .exe, если его нет
    if isinstance(updated_value, str) and not updated_value.lower().endswith('.exe'):
      updated_value += '.exe'
    updated_dict[key] = updated_value # Путей обновить значение путей.

  return updated_dict
get_user_name = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''
user = subprocess.run(['bash'], input=get_user_name, stdout=subprocess.PIPE, text=True).stdout.strip()# имя пользователя.
get_main_id = '''#!/bin/bash # Получаем идентификатор активного окна
    active_window_id=$(xdotool getactivewindow 2>/dev/null)
    if [ -n "$active_window_id" ]; then
        process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
        echo "$process_id_active"
    else
        echo "0"  # Или любое значение по умолчанию, если нет активного окна
    fi
    exit'''
def get_pid_and_path_window():# Получаем идентификатор активного окна
 try:   # Регулярное выражение для поиска путей к .exe файлам
   pattern = re.compile(r'(/mnt/.*?\.exe)|([A-Z]:/.*?\.exe)', re.IGNORECASE)
   data_dict = {}   # Один проход по всем процессам пользователя
   for proc in psutil.process_iter(['pid', 'username', 'cmdline']):
    if proc.info['username'] == user and proc.info['cmdline']:
     cmdline = ' '.join(proc.info['cmdline']).replace('\\', '/')
     match = pattern.search(cmdline)
     if match:
      file_path = match.group(0)       # Обработка пути: берём часть после .sh, если есть
      file_path = file_path.split('.sh', 1)[-1].strip() if '.sh' in file_path else file_path       # Уточняем путь до /mnt/... (если требуется)
      match_mnt = re.search(r'/mnt/[^ ]+', file_path)
      if match_mnt:
        file_path = match_mnt.group(0)
      data_dict[proc.info['pid']] = file_path

   # Обновляем словарь с помощью внешних функций (если они есть)
   data_dict1 = get_process_info()
   data_dict.update(data_dict1)
   updated_dict = replace_path_in_dict(data_dict)
   return updated_dict# Обновленный словарь путей.
 except:
   pass
while 1:
  time.sleep(1)
  process_id_active = int(subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip())
  data_dict=get_pid_and_path_window()
  try:
   if data_dict[process_id_active]:
     print(data_dict[process_id_active])
  except:
    pass
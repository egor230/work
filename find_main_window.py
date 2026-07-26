import os
import subprocess
import time

import psutil

import os
import subprocess
import time
import psutil


def Get_pid_and_path_window():
 """
 Собирает информацию о всех процессах и определяет PID активного окна.
 Возвращает: (data_dict, window_pid)
   data_dict: {pid: путь_к_исполняемому_файлу} для всех процессов (расширено на родителей и потомков)
   window_pid: PID активного окна (или None)
 """
 proc_info = {}  # pid -> {'cmdline': [...], 'cwd': str, 'exe': str, 'ppid': int}
 
 print("0")
 my_pid = os.getpid()
 data_dict = {}
 
 # ---- Сбор всех процессов ----
 for proc in psutil.process_iter(["pid", "name", "cmdline"]):
  try:
   info = proc.info
   pid = info["pid"]
   if pid == my_pid:
    continue
   
   cmdline_parts = info["cmdline"] or []
   try:
    cwd = os.readlink(f"/proc/{pid}/cwd")
   except:
    cwd = None
   try:
    exe_link = os.readlink(f"/proc/{pid}/exe")
   except:
    exe_link = None
   
   # Проверка на Wine
   is_wine = False
   if exe_link and ('wine-preloader' in exe_link or 'wine64-preloader' in exe_link):
    is_wine = True
   elif any('.exe' in arg.lower() for arg in cmdline_parts):
    is_wine = True
   elif exe_link and exe_link.lower().endswith('.exe'):
    is_wine = True
   
   resolved_path = None
   
   if is_wine:
    win_exe = None
    for arg in cmdline_parts:
     if arg.lower().endswith('.exe'):
      win_exe = arg
      break
    if win_exe:
     exe_name = os.path.basename(win_exe.replace('\\', '/'))
     found = False
     
     # Попытка получить путь через winepath
     if len(win_exe) >= 2 and win_exe[1] == ':':
      try:
       result = subprocess.run(
        ['winepath', '-u', win_exe],
        capture_output=True, text=True, timeout=3
       )
       if result.returncode == 0:
        linux_path = result.stdout.strip()
        if os.path.isfile(linux_path):
         resolved_path = linux_path
         found = True
      except:
       pass
      if not found and cwd:
       candidate = os.path.join(cwd, exe_name)
       if os.path.isfile(candidate):
        resolved_path = candidate
        found = True
     if not found and cwd:
      rel = win_exe.replace('\\', '/')
      candidate = os.path.normpath(os.path.join(cwd, rel))
      if os.path.isfile(candidate):
       resolved_path = candidate
       found = True
      elif not found:
       candidate = os.path.join(cwd, exe_name)
       if os.path.isfile(candidate):
        resolved_path = candidate
        found = True
     if not found and cwd and exe_name:
      try:
       result = subprocess.run(
        ['find', cwd, '-maxdepth', '4', '-iname', exe_name, '-type', 'f'],
        capture_output=True, text=True, timeout=5
       )
       if result.returncode == 0 and result.stdout.strip():
        resolved_path = result.stdout.strip().split('\n')[0]
        found = True
      except:
       pass
    if resolved_path:
     data_dict[pid] = resolved_path
    else:
     data_dict[pid] = "N/A"
   else:
    # Обычный Linux-процесс
    if not cmdline_parts:
     data_dict[pid] = exe_link if exe_link else "N/A"
     continue
    relative_exe = cmdline_parts[0].replace("\\", "/")
    if relative_exe.startswith('/'):
     full_path = relative_exe
    elif cwd and relative_exe:
     full_path = os.path.normpath(os.path.join(cwd, relative_exe))
    else:
     full_path = None
    if full_path and os.path.isfile(full_path):
     data_dict[pid] = full_path
    elif exe_link:
     data_dict[pid] = exe_link
    else:
     data_dict[pid] = "N/A"
  except:
   pass
 
 # Удаляем N/A
 data_dict = {pid: path for pid, path in data_dict.items() if path != "N/A"}
 
 # Расширяем на родителей и потомков (чтобы все процессы в цепочке имели путь)
 expanded = dict(data_dict)
 for game_pid, game_path in list(data_dict.items()):
  try:
   proc = psutil.Process(game_pid)
   parent = proc.parent()
   while parent and parent.pid > 1:
    expanded[parent.pid] = game_path
    parent = parent.parent()
   for child in proc.children(recursive=True):
    expanded[child.pid] = game_path
  except:
   pass
 data_dict = expanded
 
 # ---- Получаем PID активного окна ----
 window_pid = None
 # xdotool
 try:
  result = subprocess.run(['xdotool', 'getactivewindow'], capture_output=True, text=True, timeout=3)
  window_id = result.stdout.strip()
  if window_id and window_id.isdigit() and int(window_id) > 0:
   result = subprocess.run(['xdotool', 'getwindowpid', window_id], capture_output=True, text=True, timeout=3)
   pid_str = result.stdout.strip()
   if pid_str and pid_str.isdigit():
    window_pid = int(pid_str)
 except:
  pass
 
 # fallback: xprop
 if not window_pid:
  try:
   result = subprocess.run(['xprop', '-root', '_NET_ACTIVE_WINDOW'], capture_output=True, text=True, timeout=3)
   for part in result.stdout.split():
    if part.startswith('0x'):
     window_hex = part.lstrip('#')
     result2 = subprocess.run(['xprop', '-id', window_hex, '_NET_WM_PID'], capture_output=True, text=True, timeout=3)
     for token in result2.stdout.split():
      if token.isdigit() and int(token) > 1:
       window_pid = int(token)
       break
     break
  except:
   pass
 
 # fallback: wmctrl
 if not window_pid:
  try:
   result = subprocess.run(['wmctrl', '-a', ':ACTIVE:', '-p'], capture_output=True, text=True, timeout=3)
   parts = result.stdout.split()
   if len(parts) >= 3 and parts[2].isdigit():
    window_pid = int(parts[2])
  except:
   pass
 
 if not window_pid:
  return None, None
 
 # ---- Поиск игры среди процессов, связанных с окном ----
 # Вспомогательная проверка на игру (не лаунчер) – встроена без отдельной функции
 def is_game(path):
  # Проверяет, является ли процесс игрой (не лаунчером)
  if not path:
   return False
  path_lower = path.lower()
  if 'launcher' in path_lower or 'launcher64' in path_lower:
   return False
  return path_lower.endswith('.exe')
 
 # Сначала смотрим, является ли само окно игрой
 if window_pid in data_dict:
  path = data_dict[window_pid]
  if path and not ('launcher' in path.lower() or 'launcher64' in path.lower()) and path.lower().endswith('.exe'):
   return data_dict, window_pid
 
 # Ищем среди потомков (рекурсивно) — сначала те, которые являются игрой
 try:
  proc = psutil.Process(window_pid)
  for child in proc.children(recursive=True):
   if child.pid in data_dict:
    path = data_dict[child.pid]
    if path and not ('launcher' in path.lower() or 'launcher64' in path.lower()) and path.lower().endswith('.exe'):
     return data_dict, child.pid
 except:
  pass
 
 # Если ничего не нашли — значит, активное окно не принадлежит игре (лаунчер или скрипт)
 return None, None


# ===================== ТЕСТ =====================
if __name__ == "__main__":
 while True:
  time.sleep(3)
  path, pid = Get_pid_and_path_window()
  if path:
   print(f"Игра активна: PID={pid}, путь={path}")
  else:
   print("Игра не активна (окно не принадлежит игровому процессу)")
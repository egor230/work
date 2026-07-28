import os,re
import subprocess
import psutil
import time

import signal

def Get_pid():
   
   # Имя пользователя получаем сами
   user = os.environ.get('USER') or os.environ.get('LOGNAME') or pwd.getpwuid(os.getuid()).pw_name
   if not user:
    user = subprocess.run(['whoami'], capture_output=True, text=True).stdout.strip() or None
   
   _RE_EXE_SH = re.compile(r'.*\.(exe|sh)$', re.IGNORECASE)
   
   _BASH_GET_MAIN_ID = '''#!/bin/bash
active_window_id=$(xdotool getactivewindow 2>/dev/null)
if [[ -n "$active_window_id" && "$active_window_id" =~ ^[0-9]+$ && "$active_window_id" != "0" ]]; then
    process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
    if [[ -n "$process_id_active" && "$process_id_active" != "0" ]]; then
        parent_pid=$(ps -p "$process_id_active" -o ppid= 2>/dev/null | tr -d '[:space:]')
        if [[ -n "$parent_pid" && "$parent_pid" != "0" && "$parent_pid" != "1" ]] && ps -p "$parent_pid" >/dev/null 2>&1; then
            echo "$parent_pid"
        else
            echo "$process_id_active"
        fi
        exit 0
    fi
fi
echo "0"
'''
   
   my_pid = os.getpid()
   data_dict = {}
   
   # === Один проход по всем процессам ===
   for proc in psutil.process_iter(["pid", "username", "cmdline"]):
    try:
     info = proc.info
     pid = info["pid"]
     if pid == my_pid:
      continue
     
     # Фильтр по пользователю
     if user is not None and info.get("username") != user:
      continue
     
     cmdline_parts = info["cmdline"] or []
     
     # cwd / exe через /proc
     try:
      cwd = os.readlink(f"/proc/{pid}/cwd")
     except (FileNotFoundError, PermissionError, OSError):
      cwd = None
     
     try:
      exe_link = os.readlink(f"/proc/{pid}/exe")
     except (FileNotFoundError, PermissionError, OSError):
      exe_link = None
     
     # --- Определяем, Wine ли это ---
     is_wine = False
     if exe_link:
      low_exe = exe_link.lower()
      if 'wine-preloader' in low_exe or 'wine64-preloader' in low_exe or '/wine' in low_exe:
       is_wine = True
     if not is_wine:
      is_wine = any('.exe' in arg.lower() for arg in cmdline_parts)
     
     resolved = None
     
     # ===== WINE-процесс =====
     if is_wine:
      win_exe = None
      for arg in cmdline_parts:
       if arg.lower().endswith('.exe'):
        win_exe = arg
        break
      
      if win_exe:
       exe_name = os.path.basename(win_exe.replace('\\', '/'))
       found = False
       
       # 1. Абсолютный Windows-путь (C:\...)
       if len(win_exe) >= 2 and win_exe[1] == ':':
        try:
         r = subprocess.run(
          ['winepath', '-u', win_exe],
          capture_output=True, text=True, timeout=3
         )
         if r.returncode == 0:
          linux_path = r.stdout.strip()
          if linux_path and os.path.isfile(linux_path):
           resolved = linux_path
           found = True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
         pass
        
        if not found and cwd:
         candidate = os.path.join(cwd, exe_name)
         if os.path.isfile(candidate):
          resolved = candidate
          found = True
       
       # 2. Относительный путь (dx11\Game.exe)
       if not found and cwd:
        rel = win_exe.replace('\\', '/')
        candidate = os.path.normpath(os.path.join(cwd, rel))
        if os.path.isfile(candidate):
         resolved = candidate
         found = True
        
        if not found:
         candidate = os.path.join(cwd, exe_name)
         if os.path.isfile(candidate):
          resolved = candidate
          found = True
       
       # 3. Fallback: find
       if not found and cwd and exe_name:
        try:
         r = subprocess.run(
          ['find', cwd, '-maxdepth', '4', '-iname', exe_name, '-type', 'f'],
          capture_output=True, text=True, timeout=5
         )
         if r.returncode == 0 and r.stdout.strip():
          resolved = r.stdout.strip().split('\n', 1)[0]
          found = True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
         pass
     
     # ===== Обычный Linux-процесс =====
     else:
      if not cmdline_parts:
       resolved = exe_link  # может быть None
      else:
       relative_exe = cmdline_parts[0].replace("\\", "/")
       if relative_exe.startswith('/'):
        full_path = relative_exe
       elif cwd and relative_exe:
        full_path = os.path.normpath(os.path.join(cwd, relative_exe))
       else:
        full_path = None
       
       if full_path and os.path.isfile(full_path):
        resolved = full_path
       else:
        resolved = exe_link  # fallback
     
     # --- Доп. сканирование cmdline на .exe/.sh (бывший второй цикл) ---
     if not resolved:
      for arg in cmdline_parts:
       arg_clean = arg.replace('\\', '/').strip('"')
       if _RE_EXE_SH.search(arg_clean):
        resolved = arg_clean
        break
     
     if resolved:
      data_dict[pid] = resolved
      # ID потоков
      try:
       for thread in proc.threads():
        data_dict[thread.id] = resolved
      except (psutil.NoSuchProcess, psutil.AccessDenied):
       pass
    
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
     continue
    except Exception:
     continue
   
   # === Разворачиваем словарь на родителей/потомков ===
   expanded = dict(data_dict)
   for game_pid, game_path in list(data_dict.items()):
    try:
     proc = psutil.Process(game_pid)
     # Родители
     parent = proc.parent()
     while parent is not None:
      expanded.setdefault(parent.pid, game_path)
      parent = parent.parent()
     # Потомки
     for child in proc.children(recursive=True):
      expanded.setdefault(child.pid, game_path)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
     continue
   
   # === PID активного окна ===
   id_active = 0
   try:
    r = subprocess.run(
     ['bash'],
     input=_BASH_GET_MAIN_ID,
     stdout=subprocess.PIPE,
     stderr=subprocess.DEVNULL,
     text=True,
     timeout=5,
    )
    out = r.stdout.strip()
    if out and out.isdigit():
     id_active = int(out)
   except (subprocess.SubprocessError, ValueError, OSError):
    pass
   
   return expanded, id_active


if __name__ == "__main__":
 while True:
  data_dict, id_active = Get_pid()
  # print(data_dict)
  has_portproton = any('/PortProton/data' in p and '.exe' in p for p in data_dict.values())
  if has_portproton:
   if id_active in data_dict:
    print("PortProton")
    print(f"PID окна={id_active}")
    print(data_dict[id_active])
    break
  else:
   has_exe = any('.exe' in p for p in data_dict.values())
   if id_active in data_dict and has_exe:
    print(data_dict[id_active])
    break  # Оставь break, только если этот код внутри цикла (for/while)
  print("Окно не найдено")
  # time.sleep(4)

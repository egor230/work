import os,re
import subprocess
import psutil
import time

import signal


def Get_pid():
 # Кэш winepath и скомпилированная регулярка через атрибуты функции (ускоряет повторные вызовы)
 if not hasattr(Get_pid, "_winepath_cache"):
  Get_pid._winepath_cache = {}
 if not hasattr(Get_pid, "_RE_EXE_SH"):
  Get_pid._RE_EXE_SH = re.compile(r'.*\.(exe|sh)$', re.IGNORECASE)
 
 winepath_cache = Get_pid._winepath_cache
 _RE_EXE_SH = Get_pid._RE_EXE_SH
 
 # 1. Получение пользователя
 user = (
   os.environ.get('USER')
   or os.environ.get('LOGNAME')
   or (pwd.getpwuid(os.getuid()).pw_name if hasattr(os, 'getuid') else None)
 )
 if not user:
  try:
   user = subprocess.check_output(['whoami'], text=True, timeout=1).strip() or None
  except Exception:
   user = None
 
 my_pid = os.getpid()
 data_dict = {}
 parent_map = {}
 children_map = {}
 
 # === Один быстрый проход по всем процессам ===
 # Запрашиваем нужные атрибуты сразу (работает на C-уровне psutil, быстрее os.readlink)
 for proc in psutil.process_iter(["pid", "username", "cmdline", "ppid", "exe", "cwd"]):
  try:
   info = proc.info
   pid = info["pid"]
   if pid == my_pid:
    continue
   
   # Строим дерево процессов в памяти (O(1) доступ вместо чтения /proc)
   ppid = info.get("ppid")
   parent_map[pid] = ppid
   if ppid:
    children_map.setdefault(ppid, []).append(pid)
   
   if user is not None and info.get("username") != user:
    continue
   
   cmdline_parts = info.get("cmdline") or []
   cwd = info.get("cwd")
   exe_link = info.get("exe")
   
   # --- Определяем, Wine ли это ---
   is_wine = False
   if exe_link:
    low_exe = exe_link.lower()
    if 'wine-preloader' in low_exe or 'wine64-preloader' in low_exe or '/wine' in low_exe:
     is_wine = True
   if not is_wine and cmdline_parts:
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
     
     # 1. Абсолютный Windows-путь
     if len(win_exe) >= 2 and win_exe[1] == ':':
      if win_exe in winepath_cache:
       linux_path = winepath_cache[win_exe]
      else:
       try:
        r = subprocess.run(
         ['winepath', '-u', win_exe],
         capture_output=True, text=True, timeout=1.5
        )
        linux_path = r.stdout.strip() if r.returncode == 0 else None
       except Exception:
        linux_path = None
       winepath_cache[win_exe] = linux_path
      
      if linux_path and os.path.isfile(linux_path):
       resolved = linux_path
       found = True
     
     # 2. cwd + basename
     if not found and cwd and exe_name:
      candidate = os.path.join(cwd, exe_name)
      if os.path.isfile(candidate):
       resolved = candidate
       found = True
     
     # 3. Относительный путь (dx11\Game.exe)
     if not found and cwd:
      rel = win_exe.replace('\\', '/')
      candidate = os.path.normpath(os.path.join(cwd, rel))
      if os.path.isfile(candidate):
       resolved = candidate
       found = True
     
     # 4. Fallback: быстрый поиск на чистом Python (аналог find -maxdepth 2)
     if not found and cwd and exe_name:
      try:
       exe_name_lower = exe_name.lower()
       cwd_clean = cwd if cwd.endswith(os.sep) else cwd + os.sep
       for root, dirs, files in os.walk(cwd):
        if root != cwd:
         if root.startswith(cwd_clean):
          rel_path = root[len(cwd_clean):]
          depth = rel_path.count(os.sep) + 1
         else:
          depth = 3
         if depth >= 3:
          dirs.clear()  # Прерываем спуск (эквивалент -maxdepth 2)
          continue
        for f in files:
         if f.lower() == exe_name_lower:
          resolved = os.path.join(root, f)
          break
        if resolved:
         break
      except (PermissionError, FileNotFoundError, OSError):
       pass
   
   # ===== Обычный Linux-процесс =====
   else:
    if not cmdline_parts:
     resolved = exe_link
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
      resolved = exe_link
   
   # --- Доп. сканирование cmdline ---
   if not resolved:
    for arg in cmdline_parts:
     arg_clean = arg.replace('\\', '/').strip('"')
     if _RE_EXE_SH.search(arg_clean):
      resolved = arg_clean
      break
   
   if resolved:
    data_dict[pid] = resolved
    try:
     for thread in proc.threads():
      data_dict[thread.id] = resolved
    except Exception:
     pass
  
  except Exception:
   continue
 
 # === Разворачиваем словарь на родителей/потомков ===
 # BFS по уже построенным словарям (вместо медленных proc.parent() и proc.children())
 expanded = dict(data_dict)
 for game_pid, game_path in data_dict.items():
  # Родители
  curr = parent_map.get(game_pid)
  while curr and curr != 0:
   if curr not in expanded:
    expanded[curr] = game_path
   curr = parent_map.get(curr)
  
  # Потомки (BFS через список вместо deque, чтобы не требовать лишних импортов)
  queue = [game_pid]
  idx = 0
  while idx < len(queue):
   curr = queue[idx]
   idx += 1
   for child in children_map.get(curr, []):
    if child not in expanded:
     expanded[child] = game_path
     queue.append(child)
 
 # === PID активного окна + консистентный путь ===
 # Множество системных exe Wine — НЕ являются целевыми играми
 WINE_SYSTEM = frozenset({
  'services.exe', 'winedevice.exe', 'plugplay.exe', 'explorer.exe',
  'svchost.exe', 'rpcss.exe', 'wineserver.exe', 'start.exe',
  'winepath.exe', 'conhost.exe', 'csrss.exe', 'lsass.exe',
  'dllhost.exe', 'cmd.exe', 'notepad.exe', 'regedit.exe',
  'taskmgr.exe', 'winemenubuilder.exe', 'wineboot.exe',
  'wineserver', 'services', 'plugplay', 'rpcss',
 })
 def _is_game(path):
  """Путь ведёт к реальной игре, а не к системному exe Wine."""
  if not path:
   return False
  base = os.path.basename(path).lower()
  if not base.endswith('.exe'):
   return False
  return base not in WINE_SYSTEM
 def _is_any_exe(path):
  """Любой .exe (включая системные) — последний fallback."""
  if not path:
   return False
  return os.path.basename(path).lower().endswith('.exe')
 
 def _bfs_down(start, visitor):
  """BFS вниз от start, вызывает visitor(child_pid, child_path) — True = стоп."""
  queue = [start]
  idx = 0
  while idx < len(queue):
   curr = queue[idx]
   idx += 1
   for child in children_map.get(curr, []):
    if visitor(child, expanded.get(child, '')):
     return child
    queue.append(child)
  return 0
 
 def _walk_up(start, visitor):
  """Идём вверх по parent_map, вызывает visitor(pid, path) — True = стоп."""
  curr = parent_map.get(start)
  while curr and curr != 0:
   if visitor(curr, expanded.get(curr, '')):
    return curr
   curr = parent_map.get(curr)
  return 0
 
 id_active = 0
 game_path = None
 try:
  win_id = subprocess.check_output(['xdotool', 'getactivewindow'], stderr=subprocess.DEVNULL, timeout=1).decode().strip()
  if win_id and win_id.isdigit() and win_id != '0':
   win_pid = subprocess.check_output(['xdotool', 'getwindowpid', win_id], stderr=subprocess.DEVNULL, timeout=1).decode().strip()
   if win_pid and win_pid.isdigit() and win_pid != '0':
    win_pid_int = int(win_pid)
    
    # ── Стратегия 1: потомки окна — ищем реальную игру (не system exe) ──
    found = _bfs_down(win_pid_int, lambda p, pth: _is_game(pth))
    if found:
     id_active = found
     game_path = expanded[found]
    
    # ── Стратегия 2: потомки окна — принимаем ЛЮБОЙ .exe (включая system) ──
    if not id_active:
     found = _bfs_down(win_pid_int, lambda p, pth: _is_any_exe(pth))
     if found:
      id_active = found
      game_path = expanded[found]
    
    # ── Стратегия 3: родители окна — ищем игру среди предков ──
    if not id_active:
     found = _walk_up(win_pid_int, lambda p, pth: _is_game(pth))
     if found:
      id_active = found
      game_path = expanded[found]
    
    # ── Стратегия 4: родители окна — любой .exe ──
    if not id_active:
     found = _walk_up(win_pid_int, lambda p, pth: _is_any_exe(pth))
     if found:
      id_active = found
      game_path = expanded[found]
    
    # ── Стратегия 5: само окно ──
    if not id_active:
     self_path = expanded.get(win_pid_int, '')
     if _is_game(self_path) or _is_any_exe(self_path):
      id_active = win_pid_int
      game_path = self_path
    
    # ── Fallback: ppid (старая логика) ──
    if not id_active:
     ppid = parent_map.get(win_pid_int)
     if ppid and ppid not in (0, 1) and ppid in parent_map:
      id_active = ppid
     else:
      try:
       ps_out = subprocess.check_output(
        ['ps', '-p', str(win_pid_int), '-o', 'ppid='],
        stderr=subprocess.DEVNULL, timeout=1
       ).decode().strip()
       ppid_int = int(ps_out) if ps_out.isdigit() else 0
       if ppid_int and ppid_int not in (0, 1):
        subprocess.check_call(['ps', '-p', str(ppid_int)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
        id_active = ppid_int
       else:
        id_active = win_pid_int
      except Exception:
       id_active = win_pid_int
     game_path = expanded.get(id_active)
    
    # === Делаем expanded консистентным: всё дерево активного окна → один путь ===
    if id_active and game_path:
     # Обновляем сам id_active
     expanded[id_active] = game_path
     # Родители
     curr = parent_map.get(id_active)
     while curr and curr != 0:
      expanded[curr] = game_path
      curr = parent_map.get(curr)
     # Потомки
     queue = [id_active]
     idx2 = 0
     while idx2 < len(queue):
      curr = queue[idx2]
      idx2 += 1
      for child in children_map.get(curr, []):
       expanded[child] = game_path
       queue.append(child)
 except Exception:
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
    print(data_dict)
    break
  else:
   has_exe = any('.exe' in p for p in data_dict.values())
   if id_active in data_dict and has_exe:
    print(data_dict[id_active])
    # break  # Оставь break, только если этот код внутри цикла (for/while)
  # print("Окно не найдено")
  # time.sleep(4)

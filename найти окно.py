import psutil, pyautogui, subprocess, time, re, getpass

# Получаем имя текущего пользователя (улучшенная версия)
user = getpass.getuser()

# Инициализируем паттерн для поиска .exe путей
pattern = re.compile(r'/mnt/.*?\.exe')


def get_pid_and_path_window():
 """Получаем PID и путь к exe активного окна (сохранена оригинальная логика)"""
 try:
  # Получаем PID активного окна через xdotool
  result = subprocess.run(
   ['xdotool', 'getactivewindow', 'getwindowpid'],
   stdout=subprocess.PIPE,
   stderr=subprocess.DEVNULL,
   text=True
  )
  if result.returncode != 0 or not result.stdout.strip():
   return None

  process_id_active = int(result.stdout.strip())

  # Ищем процесс с совпадающим PID
  for proc in psutil.process_iter(['pid', 'username', 'cmdline']):
   if proc.info['pid'] != process_id_active or proc.info['username'] != user:
    continue

   cmdline = proc.info['cmdline']
   if not cmdline:
    continue
   # Ищем путь к .exe в командной строке
   joined_cmdline = ' '.join(cmdline).replace('\\', '/')
   # Вариант 1: Просто извлекаем последнюю часть пути
   exe_name = joined_cmdline.split('/')[-1].lower()
   return exe_name

 except (subprocess.SubprocessError, ValueError,
         psutil.NoSuchProcess, psutil.AccessDenied,
         psutil.ZombieProcess) as e:
  pass
 return None


# Нормализуем и подготавливаем список для поиска
lp = ['obsidian', 'obsidian'] #, 'mouse_setting_control_for_buttons_python_for_linux'
def d(file_path):
  know_id = f'''#!/bin/bash
  xte "keydown F3" "keyup F3"
   '''  # Запускаем скрипт нахождения id мыши.
  subprocess.run(['bash', '-c', know_id])  # print(type(res["id"])) print(res["id"])
  lp.remove(file_path)
region = (436, 275, 860, 46)
while lp:
 try:
  time.sleep(1)
  if len(lp)==0:
    break
  file_path = get_pid_and_path_window()  # Проверяем наличие в списке и удаляем
  if file_path in lp:
    d(file_path)
  # location = pyautogui.locateOnScreen("mouse_view.png", confidence=0.9)
  # if location and file_path==None:
  #   region = (location.left, location.top, location.width, location.height)
  #   location = pyautogui.locateOnScreen("mouse_view.png", confidence=0.4, region=region)
  #   file_path="mouse_setting_control_for_buttons_python_for_linux"
  #   if location is not None and  file_path in lp:
  #    d(file_path)
 except:
   pass

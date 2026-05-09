import pyautogui, subprocess, re
def find_nemo():
  get_main_id = '''#!/bin/bash # Получаем идентификатор активного окна
  active_window_id=$(xdotool getactivewindow 2>/dev/null)
  if [ -n "$active_window_id" ]; then
      process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
      echo "$process_id_active"
  else
      echo "0"  # Или любое значение по умолчанию, если нет активного окна
  fi
  exit '''
  result1 = subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip()
  lines = result1.split('\n')  # Разбиваем вывод по новой строке и извлекаем значения
  process_id_active = int(lines[0].split(': ')[0])
  result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # # print(result)
  lines = result.split('\n')
  for line in lines:  #
    if 'nemo' in line:
      parts = line.split()
      pid = int(parts[1])
      cmd = ' '.join(parts[10:]).replace(" ", "")
      if 'nemo' in cmd and process_id_active==pid:

       return True
  return False
while 1:
 try:
  region = (1500, 33, 1600, 300)  # Укажите область # Пример области
  image_path = 'Search button.png'  # Укажите путь к вашему изображению
  # Проверяем, есть ли изображение на экране
  location = pyautogui.locateOnScreen(image_path, confidence=0.6, region=region)  # Уровень
  #res_nemo = find_nemo()
  region1 = (268, 44, 182, 108)  # (left, top, width, height)
  image_path1 = 'Search text.png'  # Укажите путь к вашему изображению
  loc1 = pyautogui.locateOnScreen(image_path1, confidence=0.2, region=region1)
  if location and loc1:# and res_nemo:#
    print("дбль")
    break

 except Exception as ex1:
    print(ex1)

 # print(i)
 # print(line)
 # print(cmd)       # print(cmd)
 #        # print(pid)
 #        # print(process_id_active)
import subprocess
import os
import time


def a():
  try:
    # Получаем список всех окон с их PID и заголовками
    output = subprocess.check_output(['wmctrl', '-lp']).decode().strip().split('\n')
    for line in output:
      parts = line.split(maxsplit=4)  # Разделяем строку на части
      if len(parts) < 5:
        continue

      title = parts[4]  # Заголовок окна
      if title=="Mouse setting control for buttons python":
       window_id = parts[0]  # ID окна
       pid = parts[2]  # PID процесса
       print(f"ID окна: {window_id}, PID: {pid}, Заголовок: {title}")
       print(line)

  except FileNotFoundError:
    print("Установите wmctrl: sudo apt install wmctrl")
  except Exception as e:
    print(f"Ошибка: {e}")


while 1:
  time.sleep(3)
  a()
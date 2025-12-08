#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time
import re
import glob
import subprocess
import threading

backup_script_path = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта'''

# Вызываем скрипт
user = subprocess.run(['bash'], input=backup_script_path, stdout=subprocess.PIPE, text=True).stdout.strip()
list_proccers = ["obsidian", "Mouse_setting_control_for_buttons_python_for_linux", "obsidian"]  # , "nemo""WINWORD","Mouse_setting_control_for_buttons_python_for_linux",


def get_active_window_pid():  # Получает PID активного окна разными способами. Если один способ не работает, пробует следующий.
  try:  # 1. Пробуем через xdotool
    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
    process_id = subprocess.check_output(['xdotool', 'getwindowpid', active_window_id]).decode().strip()
    return int(process_id)
  except Exception:
    pass  # Если xdotool не сработал, пробуем другой способ

  try:  # 2. Пробуем через xprop
    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
    xprop_output = subprocess.check_output(['xprop', '-id', active_window_id]).decode()
    for line in xprop_output.split("\n"):
      if "_NET_WM_PID" in line:
        return int(line.split()[-1])
  except Exception:
    pass
  try:  # 3. Пробуем через wmctrl
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    wmctrl_output = subprocess.check_output(['wmctrl', '-lp']).decode()
    for line in wmctrl_output.split("\n"):
      if active_window_name in line:
        parts = line.split()
        return int(parts[2])  # PID находится в третьем столбце
  except Exception:
    pass
  try:  # 4. Пробуем через pgrep по названию окна
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    process_id = subprocess.check_output(['pgrep', '-f', active_window_name]).decode().strip().split("\n")[0]
    return int(process_id)
  except Exception:
    pass
  try:  # 3. Получаем название активного окна
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    process_list = subprocess.check_output(['ps', 'axf', '-o', 'pid,ppid,cmd']).decode().split("\n")
    for process in process_list:  # 4. Ищем процессы, связанные с этим окном
      parts = process.strip().split(maxsplit=2)
      if len(parts) < 3:
        continue
      pid, ppid, cmd = parts  # Проверяем, содержит ли команда название активного окна
      if active_window_name.lower() in cmd.lower():
        return int(pid)  # Возвращаем PID, если нашли
      return None  # Если ничего не сработало
  except Exception:
    pass


def check_current_active_window(p):  # Получаем идентификатор активного окна
  try:
    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
    process_id = int(get_active_window_pid())  # print(process_id)
    result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # print(result)
    for line in result.split("\n"):
      user_name = ' '.join(line.split()[0]).replace(" ", "")
      if user_name == user:
        process_name = ' '.join(line.split()[10:])
        pid_id = int(line.split()[1])  # или используйте другой индекс, если нужны другие данные
        if process_id == pid_id and p in str(process_name):
          print("ok")
          return True
    return False
  except:
    pass


backup_script_path = f'''#!/bin/bash
 current_user=$(whoami);
 echo $current_user
 exit;# Завершаем выполнение скрипта'''

# Вызываем скрипт
user = subprocess.run(['bash'], input=backup_script_path, stdout=subprocess.PIPE, text=True).stdout.strip()
list_proccers = ["obsidian", "Mouse_setting_control_for_buttons_python_for_linux", "obsidian"]  # , "nemo""WINWORD","Mouse_setting_control_for_buttons_python_for_linux",


def get_active_window_pid():  # Получает PID активного окна разными способами. Если один способ не работает, пробует следующий.
  try:  # 1. Пробуем через xdotool
    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
    process_id = subprocess.check_output(['xdotool', 'getwindowpid', active_window_id]).decode().strip()
    return int(process_id)
  except Exception:
    pass  # Если xdotool не сработал, пробуем другой способ

  try:  # 2. Пробуем через xprop
    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
    xprop_output = subprocess.check_output(['xprop', '-id', active_window_id]).decode()
    for line in xprop_output.split("\n"):
      if "_NET_WM_PID" in line:
        return int(line.split()[-1])
  except Exception:
    pass
  try:  # 3. Пробуем через wmctrl
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    wmctrl_output = subprocess.check_output(['wmctrl', '-lp']).decode()
    for line in wmctrl_output.split("\n"):
      if active_window_name in line:
        parts = line.split()
        return int(parts[2])  # PID находится в третьем столбце
  except Exception:
    pass
  try:  # 4. Пробуем через pgrep по названию окна
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    process_id = subprocess.check_output(['pgrep', '-f', active_window_name]).decode().strip().split("\n")[0]
    return int(process_id)
  except Exception:
    pass
  try:  # 3. Получаем название активного окна
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    process_list = subprocess.check_output(['ps', 'axf', '-o', 'pid,ppid,cmd']).decode().split("\n")
    for process in process_list:  # 4. Ищем процессы, связанные с этим окном
      parts = process.strip().split(maxsplit=2)
      if len(parts) < 3:
        continue
      pid, ppid, cmd = parts  # Проверяем, содержит ли команда название активного окна
      if active_window_name.lower() in cmd.lower():
        return int(pid)  # Возвращаем PID, если нашли
      return None  # Если ничего не сработало
  except Exception:
    pass


def check_current_active_window(p):  # Получаем идентификатор активного окна
  try:
    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
    process_id = int(get_active_window_pid())  # print(process_id)
    result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # print(result)
    for line in result.split("\n"):
      user_name = ' '.join(line.split()[0]).replace(" ", "")
      if user_name == user:
        process_name = ' '.join(line.split()[10:])
        pid_id = int(line.split()[1])  # или используйте другой индекс, если нужны другие данные
        if process_id == pid_id and p in str(process_name):
          return True
    return False
  except:
    pass
def run_wine_command(name):
  # Формируем полный путь к файлу
  word = '''#!/bin/bash
   FILE_PATH="{0}"
   # 1. Запускаем LibreOffice Writer в фоновом режиме
   # libreoffice --writer "$FILE_PATH" &
   wine \"{0}\" &
   # 2. Сохраняем ID процесса Writer
   LO_PID=$!
   # 3. Даем LibreOffice время на загрузку и становление активным окном (очень важно!)
   sleep 4
   # 4. Находим ID окна LibreOffice  Используем команду поиска окна по имени, связанному с файлом
   WINDOW_ID=$(xdotool search --pid "$LO_PID" --name "$(basename "$FILE_PATH")" | head -n 1)
   # 5. Если окно найдено, отправляем команду "Вставить" (Ctrl+V)
   if [ ! -z "$WINDOW_ID" ]; then
     xdotool windowactivate "$WINDOW_ID"
     xte "keydown Control_R" "key V" "keyup Control_R"
     sleep 3
     xte "keydown Shift_L" "key F12" "keyup Shift_L"
     sleep 6   # 6. Завершаем процесс LibreOffice
     # 6. Закрываем окно с помощью команды закрытия (Alt+F4), чтобы Word сам обработал сохранение/закрытие
     xte "keydown Alt_L" "key F4" "keyup Alt_L"
     # Даем Word время на корректное завершение (с диалогом "Сохранить", если необходимо)
     sleep 5
   fi

   # 7. Завершаем процесс Wine, если он еще жив (например, если Alt+F4 не сработало или Word завис)
   if kill -0 "$WINE_PID" 2>/dev/null; then
      # Отправляем SIGTERM для корректного завершения
      kill "$WINE_PID"
      sleep 4

      # Принудительное завершение (SIGKILL), если процесс все еще жив
      if kill -0 "$WINE_PID" 2>/dev/null; then
         kill -9 "$WINE_PID"
      fi
   fii
   exit; '''.format(name)
  # Функция для выполнения команды
  run_command = lambda: subprocess.call(['bash', '-c', word])
  # Создание нового потока и запуск команды в нем
  thread = threading.Thread(target=run_command)
  thread.start()
  thread.join()
  time.sleep(2)
def copy_chapter_number(chapter_number):   # HTML-код с текстом "Глава <chapter_number>", красный, без переноса
  html_content = f"""
    <span style="font-family: 'Times New Roman', Times, serif; font-size: 24pt; color: red; display: inline; font-weight: bold;">
    Глава {chapter_number}
    </span>
  """
  try:
   process = subprocess.Popen( ['xclip', '-selection', 'clipboard', '-t', 'text/html'],
      stdin=subprocess.PIPE,  stderr=subprocess.PIPE,
      text=True  )
   stdout, stderr = process.communicate(input=html_content, timeout=10)
   if process.returncode == 0:
      print(f"Текст 'Глава {chapter_number}' успешно скопирован в буфер обмена.")
      # Используем copyq для записи HTML и активации в буфере
      subprocess.run(['copyq', 'write', '0', 'text/html', '-'], input=html_content, text=True)
      subprocess.run(['copyq', 'select', '0'])
   else:
      print(f"Ошибка при копировании в xclip: {stderr}")
  except subprocess.TimeoutExpired:
    print("Ошибка: превышено время ожидания для xclip")
  except FileNotFoundError:
   print("Ошибка: xclip или copyq не установлены. Убедитесь, что они доступны в системе.")

def create_chapters_dict():
  """Создает словарь глав из DOC файлов"""
  path = "/mnt/807EB5FA7EB5E954/работа/мартагона/книга/новый том/Папка"  # Находим все DOC файлы
  doc_files = glob.glob(os.path.join(path, "*.doc")) + glob.glob(os.path.join(path, "*.DOC"))

  chapters = {}
  pattern = r'Глава\s+(\d+)\.'

  for file_path in doc_files:
    file_name = os.path.basename(file_path)
    match = re.search(pattern, file_name)
    if match:
      chapter_num = int(match.group(1))
      chapters[str(chapter_num)+". "] = file_path
  return chapters


# Использование
if __name__ == "__main__":
  chapter_dict = create_chapters_dict()

  print("Словарь глав (номер -> полный путь):")
  print("=" * 80)

  for num in sorted(chapter_dict.keys()):
    copy_chapter_number(num)
    print(f"{chapter_dict[num]}")
    run_wine_command(chapter_dict[num])
    # break
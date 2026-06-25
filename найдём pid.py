import subprocess
import time


# Получаем ID активного окна
def get_active_window_pid():
    try:
        # Получаем идентификатор активного окна
        active_window_id = subprocess.run(
            ['xdotool', 'getactivewindow'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        ).stdout.strip()

        if active_window_id:
            # Получаем PID процесса, связанного с активным окном
            process_id_active = subprocess.run(
                ['xdotool', 'getwindowpid', active_window_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            ).stdout.strip()
            return int(process_id_active)
        else:
            return 0  # Если нет активного окна
    except Exception as e:
        print(f"Ошибка: {e}")
        return 0

# Получаем командную строку процесса по его PID
def get_process_command_line(pid):
 try:
   with open(f"/proc/{pid}/cmdline", "r") as f:
    cmdline = f.read().replace('\x00', ' ').strip()  # Замена нулевых символов на пробелы
    return cmdline
 except FileNotFoundError:
   return None


while 1:
  time.sleep(6)
  # Пример использования
  pid = get_active_window_pid()
  if pid > 0:
    print(f"PID активного окна: {pid}")
    process_cmd = get_process_command_line(pid)
    if process_cmd:
      print(f"Командная строка процесса: {process_cmd}")
    else:
      print("Процесс не найден.")
  else:
    print("Активное окно не найдено.")
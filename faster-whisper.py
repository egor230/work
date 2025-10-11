from write_text import *
from faster_whisper import WhisperModel
cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/whisper/"# Путь к модели
model_size = "large-v3"
model_dir = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_size}", "snapshots")
if not os.path.exists(model_dir):# Проверка существования папки snapshots
  print(f"Ошибка: Папка snapshots не найдена: {model_dir}. Убедитесь, что модель скачана.")
  sys.exit(1)
snapshot = next((d for d in os.listdir(model_dir) if os.path.isdir(os.path.join(model_dir, d))), None)
if not snapshot:# Поиск первого snapshot
  print("Ошибка: Нет snapshots в кэше. Скачайте модель заново.")
  sys.exit(1)
model_path = os.path.join(model_dir, snapshot)# Путь к модели и проверка model.bin
if not os.path.exists(os.path.join(model_path, "model.bin")):
  print(f"Ошибка: Файл model.bin не найден в {model_path}")
  sys.exit(1)
try: # Загрузка модели
  model = WhisperModel(model_path, device="cpu", compute_type="int8")
  print("Модель загружена успешно.")
except Exception as e:
  print(f"Ошибка загрузки модели: {e}")
  sys.exit(1)
script_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/off mic.py"
script_dir = os.path.dirname(script_path)
script_name = os.path.basename(script_path)

# Команда для поиска PID по имени скрипта
check_cmd = f"pgrep -f '{script_name}'"
result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

# Если процесс найден — убиваем все экземпляры
if result.returncode == 0 and result.stdout.strip():
  pids = result.stdout.strip().split()
  for pid in pids:
    try:
      subprocess.run(["kill", "-9", pid], check=True)
      print(f"Убит запущенный процесс {script_name} с PID {pid}")
    except subprocess.CalledProcessError as e:
      print(f"Не удалось убить PID {pid}: {e}")

# Формируем команду запуска
cmd = f'bash -c "cd \\"{script_dir}\\" && source myenv/bin/activate && python \\"{script_path}\\""'

# Запускаем скрипт в отдельном демонизированном потоке
def run_script():
  subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

threading.Thread(target=run_script, daemon=True).start()
print("Скрипт запущен заново.")

record = threading.Thread(target=record_audio)

def update_label(root, label):
 def record_and_process():
  try:
   # Показ окна с начальной надписью
   root.geometry("100x20+700+1025")
   label.config(text="Говорите...")
   root.deiconify()
   root.update()
   # Новый поток для записи каждый раз!
   t = threading.Thread(target=record_audio)
   t.start()
   t.join()
   label.config(text="Стоп")
   root.update()
   # Проверка звука
   if is_speech():
    message = audio(model)
    if message:
     message = repeat(message)
     # Автоподгонка ширины окна
     win_w = min(len(message)*10+10, 600)
     root.geometry(f"{win_w}x20+700+1025")
     label.config(text=message)
     root.update()
     # Отдельный поток для эмуляции ввода
     threading.Thread(target=press_keys, args=(message,)).start()
     time.sleep(2)
    else:
     label.config(text="Речь не распознана")
     root.update()
     time.sleep(2)
   else:
    label.config(text="Речь не обнаружена")
    root.update()
    time.sleep(3)

   root.withdraw()
   root.after(1000, lambda: update_label(root, label))

  except Exception as e:
   print(f"Ошибка: {e}")
   label.config(text="Ошибка")
   root.update()
   time.sleep(2)
   root.withdraw()
   root.after(1000, lambda: update_label(root, label))

 # Проверка статуса микрофона
 if get_mute_status():
  threading.Thread(target=record_and_process).start()
 else:
  root.withdraw()
  root.after(2000, lambda: update_label(root, label))


# ===== Интерфейс =====
root = tk.Tk()
frame = tk.Frame(root)
label = tk.Label(frame, text="...", font='Times 14', anchor="center")
label.pack(padx=3, fill=tk.X, expand=True)
frame.pack(fill=tk.X)
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)

update_label(root, label)
root.mainloop()

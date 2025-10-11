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

record = threading.Thread(target=record_audio)
def update_label(root, label):
 try:
  mic_on = get_mute_status()
  if mic_on:
   root.deiconify()  # показать панель.
   label.config(text="Говорите...")
   record.start()
   record.join()
   label.config(text="Стоп")
   if is_speech():
    message = audio(model)  # Замените "model" на вашу модель
    if message:
     message = repeat(message)
     print(f" {message}")
     len_len=len(message)*10+10
     # len_len=600
     root.geometry(f"{len_len}x20+700+1025")  #
     label.config(text=message)

     # thread = threading.Thread(target=process_text, args=(message, k))
     # thread.start()
     # thread.join()
     exit(0)
  else:
     root.withdraw()  # свернуть панель подсказок.
   # thread.start()
   # thread.join()  # Ждем завершения записи
 except Exception as ex1:
   print(f"Ошибка: {ex1}")
  # Планируем следующее обновление через 1 секунду
def wt():# Создаем главное окно
 root = tk.Tk()
 frame = tk.Frame(root)
 label = tk.Label(frame, text="...", font='Times 14', anchor="center")
 label.pack(padx=3, fill=tk.X, expand=True)
 frame.pack(fill=tk.X)
 root.overrideredirect(True)
 root.resizable(True, True)
 root.attributes("-topmost", True)
 # Запускаем периодическое обновление метки
 root.after(1000, lambda: update_label(root, label))
 root.mainloop()  # Запускаем главный цикл
 
w1 = threading.Thread(target=wt)
w1.start()

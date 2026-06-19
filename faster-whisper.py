import collections, math
from write_text import *
from faster_whisper import WhisperModel
cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/whisper/"# Путь к модели
model_size = "large-v3"
model_dir = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_size}", "snapshots")
warnings.filterwarnings("ignore", category=DeprecationWarning)
# Настройка директории кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache")
# Отключаем предупреждения ALSA и JACK
os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера
err = os.dup(2)  # Сохраняем оригинальный stderr
os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем вывод ошибок в /dev/null
source_id = get_webcam_source_id()      # ← твоя функция
set_mute("0", source_id)
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
def run_script():# Запускаем скрипт в отдельном демонизированном потоке
  subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

# Загрузка модели
# load_model()
threading.Thread(target=run_script, daemon=True).start()
# print("Скрипт запущен заново.")
try: # Загрузка модели
  model = WhisperModel(model_path, device="cpu", compute_type="int8_float32")
  print("Модель загружена успешно.")
except Exception as e:
  print(f"Ошибка загрузки модели: {e}")
  sys.exit(1)

def update_label(root, label, source_id):
 def record_and_process():
  try:
   if not get_mute_status(source_id):
    root.withdraw()
   else:
    # Показ окна с начальной надписью
    root.geometry("100x20+700+1025")
    label.config(text="Говорите...")
    root.deiconify()
    root.update()
    buffer = collections.deque()  # ИЗМЕНЕНО: используем список вместо Queue
    silence_time = 0
    last_speech_time = time.time()
    min_silence_duration = 1.9
    fs = 48000
    filename = "temp.wav"
    start = False
    with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
     while True:
      audio_chunk, overflowed = stream.read(8096)  # Читаем аудио порциями
      mean_amp = np.mean(np.abs(audio_chunk)) * 100
      mean_amp = math.ceil(mean_amp)      #      print(mean_amp)
      if mean_amp > 2:
       buffer.extend(audio_chunk.flatten())
       last_speech_time = time.time()
       silence_time = 0
       start = True
      if start:
       buffer.extend(audio_chunk.flatten())
       if silence_time > min_silence_duration and start:
        root.withdraw()  # print("0")
        array = np.array(buffer)
        array = enhance_speech_for_recognition(array)
        write(filename, fs, array)
        buffer.clear()  # Сбрасываем буфер
        break
       else:
        silence_time += time.time() - last_speech_time
        last_speech_time = time.time()
    if is_speech(0.073):  # Проверяем, что буфер не пустой
     segment_duration = len(array) / 48000
     print(f" длительность: {segment_duration:.2f} сек ")
     message = audio(model, filename)
     if message != None:
      # if is_model_loaded():
      #  message = fix_text(message)
      threading.Thread(target=process_text, args=(message,), daemon=True).start()

   root.after(1000, lambda: update_label(root, label, source_id))

  except Exception as e:
   print(f"Ошибка: {e}")
   root.after(1000, lambda: update_label(root, label, source_id))
   pass

 # Проверка статуса микрофона
 if get_mute_status(source_id):
  threading.Thread(target=record_and_process).start()
 else:
  root.withdraw()
  root.after(2000, lambda: update_label(root, label, source_id))


# ===== Интерфейс =====
root = tk.Tk()
frame = tk.Frame(root)
label = tk.Label(frame, text="...", font='Times 14', anchor="center")
label.pack(padx=3, fill=tk.X, expand=True)
frame.pack(fill=tk.X)
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)

update_label(root, label, source_id)
root.mainloop()

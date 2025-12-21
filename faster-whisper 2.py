from write_text import *
# Путь к твоей модели Turbo
MODEL_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/podlodka_model"
# Загружаем модель Turbo вместо Whisper
try:
 processor = AutoProcessor.from_pretrained(MODEL_DIR)
 model = AutoModelForSpeechSeq2Seq.from_pretrained(  MODEL_DIR,  dtype=torch.float32,  # CPU
  low_cpu_mem_usage=True )
 model = model.to("cpu")
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
    subprocess.run(["kill", "-9", pid], check=True)    # print(f"Убит запущенный процесс {script_name} с PID {pid}")
   except subprocess.CalledProcessError as e:
    print(f"Не удалось убить PID {pid}: {e}")
# Формируем команду запуска
cmd = f'#!/bin/bash\n"/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python\" \"{script_path}\"'
def run_script():# Запускаем скрипт в отдельном демонизированном потоке
  subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
threading.Thread(target=run_script, daemon=True).start()# print("Скрипт запущен заново.")

# Отключаем предупреждения ALSA и JACK
os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"
os.environ["JACK_NO_START_SERVER"] = "1"
err = os.dup(2)
os.dup2(os.open(os.devnull, os.O_WRONLY), 2)

# --- Настройка и запуск вспомогательного скрипта ---
source_id = get_webcam_source_id()
set_mute("0", source_id)

script_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/off mic.py"
script_dir = os.path.dirname(script_path)
script_name = os.path.basename(script_path)

def transcribe_audio_with_turbo(audio_array, sample_rate=16000):
 try:
  # Если частота дискретизации не 16000 Гц, ресемплируем
  if sample_rate != 16000:
   audio_array = librosa.resample(  audio_array.astype(np.float32),
    orig_sr=sample_rate,   target_sr=16000   )
  inputs = processor(   audio_array,   sampling_rate=16000,   return_tensors="pt"  )
  generated_ids = model.generate(  inputs["input_features"],  max_new_tokens=192,  # Увеличиваем, т.к. речь может быть медленнее
   num_beams=10,  # Увеличиваем beam search для лучшего поиска
   # Ключевые параметры для нечеткой речи
   temperature=0.7,  # Небольшая креативность для интерпретации
   # do_sample=True,  # Включаем сэмплирование
   # top_k=30,  # Рассматриваем больше вариантов
#  top_p=0.9,  # Nucleus sampling
   # Специальные настройки
   # repetition_penalty=1.3,  # Сильнее штрафуем повторения (частая проблема)
  # length_penalty=1.2,  # Поощряем более длинные последовательности
#   no_repeat_ngram_size=3,  # Запрещаем повторения 3-грамм
#   diversity_penalty=0.5,  # Добавляем разнообразие в beam search
   # early_stopping=True,
   # num_return_sequences=1,
  ) # Но можно попробовать 2-3 и выбрать лучшую
  text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
  return text.strip()
 except Exception as e:
  print(f"Ошибка при транскрипции: {e}")
  return ""

# Твой основной модуль обработки
def update_label(root, label, model, processor, source_id):
 def record_and_process():
  try:
   if not get_mute_status(source_id):
    root.withdraw()
   else:
    root.geometry("100x20+700+1025")
    label.config(text="Говорите...")
    root.deiconify()
    root.update()
    buffer = collections.deque()
    silence_time = 0
    last_speech_time = time.time()
    min_silence_duration = 1.4
    fs = 16000
    filename = "temp.wav"
    start = False
    with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
     while True:
      if not get_mute_status(source_id):
       root.withdraw()
      else:
       audio_chunk, overflowed = stream.read(8096)
       mean_amp = np.mean(np.abs(audio_chunk)) * 100
       mean_amp = math.ceil(mean_amp)
       if mean_amp > 5:#        print(mean_amp)
        last_speech_time = time.time()
        silence_time = 0
        start = True
       if start:
        buffer.extend(audio_chunk.flatten())
        if silence_time > min_silence_duration:
         root.withdraw()
         array = np.array(buffer)
         start = False
         break
        else:
         silence_time += time.time() - last_speech_time
         last_speech_time = time.time()

    root.withdraw()
    buffer.clear()
    # Используем Turbo модель для распознавания
    if is_speech(0.030, array):
#     array = enhance_speech_for_recognition(array)
     # Транскрибируем аудио с помощью Turbo модели
     text = transcribe_audio_with_turbo(array)
     if text and text != " " and len(text) > 0:
      threading.Thread(target=process_text, args=(text,), daemon=True).start()
   root.after(1000, lambda: update_label(root, label, model, processor, source_id))
  except Exception as e:
   print(f"Ошибка: {e}")
   try:
    stream.stop()
    stream.close()
   except:
    pass
   root.after(1000, lambda: update_label(root, label, model, processor, source_id))

 if get_mute_status(source_id):
  threading.Thread(target=record_and_process).start()
 else:
  root.withdraw()
  root.after(2000, lambda: update_label(root, label, model, processor, source_id))

# ===== Интерфейс =====
root = tk.Tk()
frame = tk.Frame(root)
label = tk.Label(frame, text="...", font='Times 14', anchor="center")
label.pack(padx=3, fill=tk.X, expand=True)
frame.pack(fill=tk.X)
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)

update_label(root, label, model, processor, source_id)
root.mainloop()
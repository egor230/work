from write_text import *
import torch, gigaam, tempfile, torchaudio
warnings.filterwarnings("ignore", category=DeprecationWarning)
# Настройка директории кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache")
# Отключаем предупреждения ALSA и JACK
os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера
err = os.dup(2)  # Сохраняем оригинальный stderr
os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем вывод ошибок в /dev/null
torch.set_num_threads(8)
subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)  # вкл микрофон.
subprocess.run(['pactl', 'set-source-volume', "54", '65000'])
# Проверка и загрузка модели GigaAM
def check_model():
 models = ["v1_ssl", "v2_ssl", "ssl", "ctc", "v1_ctc", "v2_ctc", "rnnt", "v1_rnnt", "v2_rnnt", "emo"]
 model_name = models[-2]  # v2_rnnt
 model_path = cache_dir / "gigaam" / f"{model_name}"
 if not os.path.exists(f"{model_path}.ckpt"):
  print(f"Ошибка: Файл модели не найден по пути: {model_path}")
  sys.exit(1)  # Завершаем программу с кодом ошибки
 model = gigaam.load_model(model_name)
 return gigaam.load_model(model_name)

def is_speech_audio(audio_data, threshold=0.022, min_duration=4.5, sample_rate=48000):# Проверка наличия речи
  avg_amplitude = np.mean(np.abs(audio_data))
  return avg_amplitude > threshold
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

threading.Thread(target=run_script, daemon=True).start()
print("Скрипт запущен заново.")
sample_rate = 48000
duration = 10.5
block_size = int(sample_rate * duration)
# Обработка аудиопотока
def audio_callback(indata, frames, time, status):
 if status:
  print("Ошибка:", status)
 try:
  model = check_model()
  audio = indata.flatten().astype(np.float32)
  if is_speech_audio(audio):   # Ресэмплирование 48k -> 16k
   audio_16k = torchaudio.functional.resample(torch.tensor(audio).unsqueeze(0), 48000, 16000)[0].numpy()
   # Сохранение во временный файл
   with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_file:
    torchaudio.save(temp_file.name, torch.tensor(audio_16k).unsqueeze(0), 16000)
    result = model.transcribe(temp_file.name)  # Для других моделей получаем текст
    os.unlink(temp_file.name)
    if result != None:
     message = repeat(result) # Автоподгонка ширины окна
     threading.Thread(target=process_text, args=(message,), daemon=True).start()
 except Exception as e:
  print(f"Ошибка распознавания: {e}")

def update_label(root, label):
 def record_and_process():
  try:
   if not get_mute_status():
    root.withdraw()
   else:
    # Показ окна с начальной надписью
    root.geometry("100x20+700+1025")
    label.config(text="Говорите...")
    root.deiconify()
    root.update()
    stream = sd.InputStream(samplerate=sample_rate, channels=1,
                            dtype="float32", callback=audio_callback, blocksize=block_size)
    stream.start()
    time.sleep(duration)
    root.withdraw()
    stream.stop()
    stream.close()
   root.after(1000, lambda: update_label(root, label))

  except Exception as e:
   print(f"Ошибка: {e}")
   root.after(1000, lambda: update_label(root, label))
   pass

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

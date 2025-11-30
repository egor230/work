from transformers import AutoModel
from write_text import *
import torch, gigaam, tempfile, torchaudio, math, scipy.signal
import numpy as np
warnings.filterwarnings("ignore", category=DeprecationWarning)
print("Модель загружена! Если ошибок нет — проверь папку заново.")
source_id = get_webcam_source_id()
# Настройка директории кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache")
# Отключаем предупреждения ALSA и JACK
os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера
err = os.dup(2)  # Сохраняем оригинальный stderr
os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем вывод ошибок в /dev/null
torch.set_num_threads(8)

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
    # print(f"Убит запущенный процесс {script_name} с PID {pid}")
   except subprocess.CalledProcessError as e:
    print(f"Не удалось убить PID {pid}: {e}")
# Формируем команду запуска
cmd = f'bash -c "cd \\"{script_dir}\\" && source myenv/bin/activate && python \\"{script_path}\\""'
def run_script():# Запускаем скрипт в отдельном демонизированном потоке
  subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

threading.Thread(target=run_script, daemon=True).start()
# ← Загружаем только модель (processor НЕ нужен и НЕ существует)
model = AutoModel.from_pretrained(
    "ai-sage/GigaAM-v3",
    revision="e2e_rnnt",        # или "rnnt" — обе работают,
    device_map="cpu",
    trust_remote_code=True,     # ← без этого вообще ничего не будет
)
def update_label(root, label, source_id):
 def update_label(root, label, model, source_id):
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
     min_silence_duration = 1.8
     fs = 48000
     filename = "temp.wav"
     start = False
     with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
      while True:
       audio_chunk, overflowed = stream.read(8096)  # Читаем аудио порциями
       mean_amp = np.mean(np.abs(audio_chunk)) * 100
       mean_amp = math.ceil(mean_amp)  # print(mean_amp)
       if mean_amp > 2:
        last_speech_time = time.time()
        silence_time = 0
        start = True
       if start:
        buffer.extend(audio_chunk.flatten())
        if silence_time > min_silence_duration:
         root.withdraw()
         array = np.array(buffer)
         array = enhance_speech_for_recognition(array)
         start = False
         break
        else:
         silence_time += time.time() - last_speech_time
         last_speech_time = time.time()
     root.withdraw()  #
     if is_speech(0.07, array):
      write(filename, fs, array)
      message = model.transcribe(filename)
      # os.unlink(filename)
      if message != " " and len(message) > 0:
       threading.Thread(target=process_text, args=(message,), daemon=True).start()
     buffer.clear()  # Сбрасываем буфер
    root.after(1000, lambda: update_label(root, label, model, source_id))
    # audio = enhance_speech_for_recognition(audio, 48000)
   except Exception as e:
    print(f"Ошибка: {e}")  # Добавьте остановку потока в случае ошибки
    try:
      stream.stop()
      stream.close()
    except:
      pass
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

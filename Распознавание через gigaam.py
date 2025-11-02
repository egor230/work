from write_text import *
import torch, gigaam, tempfile, torchaudio, scipy.signal
import numpy as np
from scipy import signal
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

def is_speech_audio(audio_data, threshold=0.032, min_duration=4.5, sample_rate=48000):# Проверка наличия речи
  avg_amplitude = np.mean(np.abs(audio_data))
  #print(avg_amplitude)
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
    # print(f"Убит запущенный процесс {script_name} с PID {pid}")
   except subprocess.CalledProcessError as e:
    print(f"Не удалось убить PID {pid}: {e}")
# Формируем команду запуска
cmd = f'bash -c "cd \\"{script_dir}\\" && source myenv/bin/activate && python \\"{script_path}\\""'
def run_script():# Запускаем скрипт в отдельном демонизированном потоке
  subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

threading.Thread(target=run_script, daemon=True).start()
# print("Скрипт запущен заново.")
duration = 10.5
sample_rate = 48000
block_size = int(sample_rate * duration)


def enhance_speech_for_recognition(audio, sample_rate=48000):
  try:
    audio = audio.flatten().astype(np.float32)
    if len(audio) == 0 or np.max(np.abs(audio)) == 0:
      return audio

    # === 1. Мягкое предварительное усиление ===
    audio *= 2.0

    # === 2. Полосовой фильтр для речи ===
    nyquist = sample_rate / 2
    b, a = signal.butter(1, [70 / nyquist, 8000 / nyquist], btype='band')
    audio = signal.filtfilt(b, a, audio)

    # === 3. Усиление тихих фрагментов (адаптивное AGC) ===
    frame_len = int(0.08 * sample_rate)  # 80 мс
    hop = int(frame_len / 2)
    target_rms = 0.15
    out = np.copy(audio)

    for i in range(0, len(audio) - frame_len, hop):
      seg = audio[i:i + frame_len]
      rms = np.sqrt(np.mean(seg ** 2)) + 1e-9
      if rms < target_rms:
        gain = min(target_rms / rms, 8.0)  # сильнее для тихих
        out[i:i + frame_len] = seg * gain

    audio = out

    # === 4. Мягкая нормализация ===
    peak = np.max(np.abs(audio)) + 1e-9
    if peak > 0:
      audio = (audio / peak) * 0.98

    # === 5. Лёгкий лимитер (мягкое сглаживание пиков) ===
    audio = np.tanh(audio * 1.05) * 0.98

    return audio.astype(np.float32)

  except Exception as e:
    print(f"Ошибка улучшения речи: {e}")
    return audio


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
      buffer = []  # ИЗМЕНЕНО: используем список вместо Queue
      silence_time = 0
      last_speech_time = time.time()
      min_silence_duration = 1.8
      fs = 48000
      chunk_duration = 0.03
      queue = Queue()
      def callback(indata, frames, time_info, status):
        if status:
          print(f"Статус потока: {status}")
        queue.put(indata.copy())
      stream = sd.InputStream(samplerate=fs, channels=1, callback=callback, blocksize=int(fs * chunk_duration))
      stream.start()
      while True:
        audio_chunk = queue.get()  # Таймаут, чтобы не блокироваться навсегда
        audio_int16 = (audio_chunk * 32767).astype(np.int16)
        mean_amp = np.mean(np.abs(audio_chunk)) * 1000
        # print(mean_amp)
        if mean_amp > 18:
          buffer.append(audio_chunk)  # Теперь это работает с списком
          last_speech_time = time.time()
          silence_time = 0
        else:
          silence_time += time.time() - last_speech_time
          last_speech_time = time.time()
        if silence_time > min_silence_duration and buffer:
          root.withdraw()#       print("0")
          break
      # ИЗМЕНЕНО: проверяем что буфер не пуст перед конкатенацией
      speech_segment = np.concatenate(buffer).astype(np.float32)  # Теперь это работает
      # segment_duration = len(speech_segment) / 48000
      model = check_model()
      audio = speech_segment.flatten().astype(np.float32)
      if is_speech_audio(audio):  # Ресэмплирование 48k -> 16k
       # audio = enhance_speech_for_recognition(audio, 48000)
       audio_16k = torchaudio.functional.resample(
          torch.tensor(audio).unsqueeze(0), 48000, 16000)[0].numpy()
        # Сохранение во временный файл
       with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_file:
        torchaudio.save(temp_file.name, torch.tensor(audio_16k).unsqueeze(0), 16000)
        message = model.transcribe(temp_file.name)  # Для других моделей получаем текст
        os.unlink(temp_file.name)
        if message !=" " and len(message) >0:
         threading.Thread(target=process_text, args=(message,), daemon=True).start()

      # Очистка буфера
      buffer.clear()
      stream.stop()
      stream.close()

    root.after(1000, lambda: update_label(root, label))

  except Exception as e:
    print(f"Ошибка: {e}")
    # Добавьте остановку потока в случае ошибки
    try:
      stream.stop()
      stream.close()
    except:
      pass
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
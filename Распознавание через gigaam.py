from omegaconf import omegaconf
from omegaconf.base import ContainerMetadata
from omegaconf.dictconfig import DictConfig # <--- ИСПРАВЛЕНИЕ ОШИБКИ #1
from write_text import *
import torch, gigaam, tempfile, torchaudio, math, scipy.signal, typing
# Разрешаем необходимые типы для загрузки чекпоинта
torch.serialization.add_safe_globals([ContainerMetadata, DictConfig, typing.Any])
#pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1

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
source_id = get_webcam_source_id()      # ← твоя функция
set_mute("0", source_id)
# Проверка и загрузка модели GigaAM
def check_model():
 models = ["v1_ssl", "v2_ssl", "ssl", "ctc", "v1_ctc", "v2_ctc", "rnnt", "v1_rnnt", "v2_rnnt", "emo", "v3_e2e_rnnt"]
 model_name = models[-1]  # v2_rnnt
 model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/gigaam/v3_e2e_rnnt"#cache_dir / "gigaam" / f"{model_name}"
 if not os.path.exists(f"{model_path}.ckpt"):
  print(f"Ошибка: Файл модели не найден по пути: {model_path}")
  sys.exit(1)  # Завершаем программу с кодом ошибки
 try:
  model = gigaam.load_model(model_name)
  return model
 except Exception as e:
  print(e)
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
model = check_model()
threading.Thread(target=run_script, daemon=True).start()# print("Скрипт запущен заново.")

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
      start= False
      with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
       while True:
        if not get_mute_status(source_id):
          root.withdraw()
        else:
         audio_chunk, overflowed = stream.read(8096)  # Читаем аудио порциями
         mean_amp = np.mean(np.abs(audio_chunk)) * 100
         mean_amp = math.ceil(mean_amp)#        print(mean_amp)
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
           start= False
           break
          else:
           silence_time += time.time() - last_speech_time
           last_speech_time = time.time()
      root.withdraw()#
      if is_speech(0.087, array):
       write(filename, fs, array)
       message = model.transcribe(filename)
          # os.unlink(filename)
       if message !=" " and len(message) >0:
        threading.Thread(target=process_text, args=(message,), daemon=True).start()
      buffer.clear()  # Сбрасываем буфер
    root.after(1000, lambda: update_label(root, label, model, source_id))
       # audio = enhance_speech_for_recognition(audio, 48000)
  except Exception as e:
    print(f"Ошибка: {e}")
    # Добавьте остановку потока в случае ошибки
    try:
      stream.stop()
      stream.close()
    except:
      pass
    root.after(1000, lambda: update_label(root, label, model, source_id))
    pass
 # Проверка статуса микрофона
 if get_mute_status(source_id):
  threading.Thread(target=record_and_process).start()
 else:
  root.withdraw()
  root.after(2000, lambda: update_label(root, label, model, source_id))

# ===== Интерфейс =====
root = tk.Tk()
frame = tk.Frame(root)
label = tk.Label(frame, text="...", font='Times 14', anchor="center")
label.pack(padx=3, fill=tk.X, expand=True)
frame.pack(fill=tk.X)
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)

update_label(root, label, model, source_id)
root.mainloop()
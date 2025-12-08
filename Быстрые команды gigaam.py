from write_text import *
import torch, gigaam, tempfile, torchaudio, math, scipy.signal
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
if get_mute_status():
 buffer = []  # ИЗМЕНЕНО: используем список вместо Queue
 silence_time, last_speech_time = 0, 0
 min_silence_duration = 0.5
 fs = 48000
 filename = "temp.wav"
 try:
  model = check_model()
  print("star")
  with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
   while True:
     audio_chunk, overflowed = stream.read(8096)  # Читаем аудио порциями
     buffer.extend(audio_chunk.flatten())
     mean_amp = np.mean(np.abs(audio_chunk)) * 100
     mean_amp = math.ceil(mean_amp * 10) / 10
     print(mean_amp)
     if mean_amp > 6:
      last_speech_time = time.time()
      silence_time = 0
     else:
      silence_time += time.time() - last_speech_time
      last_speech_time = time.time()
     if silence_time > min_silence_duration and buffer:
      recording_array = np.array(buffer)
      write(filename, fs, recording_array)
      if buffer:  # ✅ проверка, что буфер не пуст
       buffer.clear()
       message = model.transcribe(filename)
       # os.unlink(filename)
       if message !=" " and len(message) >0:
        print(message)
 except Exception as e:
  print(f"Ошибка: {e}")
  stream.stop()
  stream.close()
  pass
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pathlib import Path
import os, subprocess, torch, shutil, gigaam, tempfile, torchaudio, time

# Настройка директории кэша

cache_dir = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache")
# Отключаем предупреждения ALSA и JACK
os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера

# err = os.dup(2)  # Сохраняем оригинальный stderr
# os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем вывод ошибок в /dev/null
torch.set_num_threads(8)
subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)  # вкл микрофон.

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

def is_speech(audio_data, threshold=0.022, min_duration=4.5, sample_rate=48000):# Проверка наличия речи
  avg_amplitude = np.mean(np.abs(audio_data))
  return avg_amplitude > threshold

# Обработка аудиопотока
def audio_callback(indata, frames, time, status):
 if status:
  print("Ошибка:", status)
 try:
  model = check_model()
  audio = indata.flatten().astype(np.float32)
  if is_speech(audio):   # Ресэмплирование 48k -> 16k
   audio_16k = torchaudio.functional.resample(torch.tensor(audio).unsqueeze(0), 48000, 16000)[0].numpy()
   # Сохранение во временный файл
   with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_file:
    torchaudio.save(temp_file.name, torch.tensor(audio_16k).unsqueeze(0), 16000)
    result = model.transcribe(temp_file.name)  # Для других моделей получаем текст
    os.unlink(temp_file.name)
    text = str(result).strip().lower()
    if text: # Проверяем, что текст не пустой
     print(text)
 except Exception as e:
  print(f"Ошибка распознавания: {e}")

sample_rate = 48000
duration = 8.5
block_size = int(sample_rate * duration)
def gigaam_stream():# Потоковое распознавание
  stream = sd.InputStream( samplerate=sample_rate, channels=1,
  dtype="float32",  callback=audio_callback,  blocksize=block_size  )
  print("Старт")
  stream.start()
  time.sleep(duration)
  stream.stop()
  stream.close()

while 1:
  gigaam_stream()

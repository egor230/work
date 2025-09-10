import sounddevice as sd
import numpy as np
from pynput import keyboard
from pathlib import Path
import os, subprocess, torch, shutil, gigaam, tempfile, torchaudio, time

# Настройка директории кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(cache_dir)

os.environ["OMP_NUM_THREADS"] = "8"# Настройка потоков для PyTorch
os.environ["MKL_NUM_THREADS"] = "8"
torch.set_num_threads(8)
subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)  # вкл микрофон.

# Константа для выбора модели
MODEL_NAME = "v2_rnnt"  # можно заменить на "v2_rnnt" или "emo"

# Проверка и загрузка модели GigaAM
def check_model(model_name=MODEL_NAME):
 models = ["v1_ssl", "v2_ssl", "ssl", "ctc", "v1_ctc", "v2_ctc", "rnnt", "v1_rnnt", "v2_rnnt", "emo"]
 model_name = models[-2]  # v2_rnnt
 model_path = cache_dir / "gigaam" / f"{model_name}"
 if model_path.exists() and model_path.is_dir():
  print(f"⚠️ Обнаружена папка вместо файла: {model_path}, удаляю...")
  shutil.rmtree(model_path)
 if model_path.exists() and model_path.is_file():
  print(f"✅ Использую кэшированную модель: {model_path}")
  return gigaam.load_model(model_name)
 else:
  print(f"⬇️ Скачиваю модель {model_name}...")
  model = gigaam.load_model(model_name)
  print(f"✅ Модель {model_name} загружена и сохранена в кэш.")
  return model

def is_speech(audio_data, threshold=0.022, min_duration=4.5, sample_rate=48000):# Проверка наличия речи
  avg_amplitude = np.mean(np.abs(audio_data))
  return avg_amplitude > threshold

# Обработка аудиопотока
def audio_callback(indata, frames, time, status):
 if status:
  print("Ошибка:", status)
 try:
  model = check_model(MODEL_NAME)
  audio = indata.flatten().astype(np.float32)
  if is_speech(audio):   # Ресэмплирование 48k -> 16k
   audio_16k = torchaudio.functional.resample(
     torch.tensor(audio).unsqueeze(0), 48000, 16000   )[0].numpy()
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

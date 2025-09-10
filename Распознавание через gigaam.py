import sounddevice as sd
import numpy as np
from pynput import keyboard
from pathlib import Path
import os, subprocess, torch
import gigaam, tempfile, torchaudio, time

# Константа для выбора модели
MODEL_NAME = "v2_rnnt"  # можно заменить на "v2_rnnt" или "emo"

# Настройка директории кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(cache_dir)

# Проверка и загрузка модели GigaAM
def check_model(model_name=MODEL_NAME):
  if hasattr(check_model, "model"):
    return check_model.model
  # Список доступных моделей
  models = ["v1_ssl", "v2_ssl", "ssl", "ctc", "v1_ctc", "v2_ctc", "rnnt", "v1_rnnt", "v2_rnnt", "emo"]
  if model_name not in models:
    raise ValueError(f"Модель {model_name} не поддерживается. Выберите из {models}")
  # Путь для кэша модели
  model_path = cache_dir / "gigaam" / f"{model_name}"
  model_path.mkdir(parents=True, exist_ok=True)
  # Настройка потоков
  os.environ["OMP_NUM_THREADS"] = "8"
  os.environ["MKL_NUM_THREADS"] = "8"
  torch.set_num_threads(8)
  # Управление микрофоном
  try:
    subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)
  except Exception as e:
    print(f"Ошибка микрофона: {e}")
  # Загрузка модели
  try:
    check_model.model = gigaam.load_model(model_name)
    print(f"Модель {model_name} загружена")
  except Exception as e:
    print(f"Ошибка загрузки модели {model_name}: {e}")
    raise
  return check_model.model

# Проверка наличия речи
def is_speech(audio_data, threshold=0.022, min_duration=4.5, sample_rate=44100):
  avg_amplitude = np.mean(np.abs(audio_data))
  return avg_amplitude > threshold

# Обработка аудиопотока
def audio_callback(indata, frames, time, status):
 if status:
  print("Ошибка:", status)
 try:
  model = check_model(MODEL_NAME)
  audio = indata.flatten().astype(np.float32)
  if is_speech(audio):
   # Ресэмплирование 48k -> 16k
   audio_16k = torchaudio.functional.resample(
     torch.tensor(audio).unsqueeze(0), 48000, 16000
   )[0].numpy()
   # Сохранение во временный файл
   with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
    torchaudio.save(temp_file.name, torch.tensor(audio_16k).unsqueeze(0), 16000)
   # Проверка типа модели
    if MODEL_NAME == "emo":
     result = model.get_probs(temp_file.name)  # Для emo получаем вероятности эмоций
     os.unlink(temp_file.name)
     if result:
      print("Эмоции:", ", ".join([f"{emo}: {prob:.3f}" for emo, prob in result.items()]))
    else:
     result = model.transcribe(temp_file.name)  # Для других моделей получаем текст
     os.unlink(temp_file.name)
     text = str(result).strip().lower()
     if text:
      print(f"Транскрипция: {text}")
 except Exception as e:
  print(f"Ошибка распознавания: {e}")

# Потоковое распознавание
def gigaam_stream():
  sample_rate = 48000
  duration = 8.5
  block_size = int(sample_rate * duration)
  stream = sd.InputStream( samplerate=sample_rate, channels=1,
  dtype="float32",  callback=audio_callback,  blocksize=block_size  )
  print("Старт")
  stream.start()
  time.sleep(duration)
  stream.stop()
  stream.close()


while 1:
  gigaam_stream()

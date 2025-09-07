import sounddevice as sd
import numpy as np
from pynput import keyboard
from pathlib import Path
import os, subprocess, threading, torch
import whisper, tempfile, queue, torchaudio, time

cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(cache_dir)

def check_model():  # Проверка наличия модели
  if hasattr(check_model, "model"):  # уже загружена
    return check_model.model
  models = ["tiny", "base", "small", "medium", "large", "large-v3"]
  model_name = models[2]
  model_path = cache_dir / "whisper" / f"{model_name}.pt"
  os.environ["OMP_NUM_THREADS"] = "8"
  os.environ["MKL_NUM_THREADS"] = "8"
  torch.set_num_threads(8)
  try:
    subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)
  except Exception:
    pass
  check_model.model = whisper.load_model(model_name, device="cpu")
  return check_model.model

def is_speech(audio_data, threshold=0.022, min_duration=4.5, sample_rate=44100):
  avg_amplitude = np.mean(np.abs(audio_data))
  if avg_amplitude > threshold:
    return True
  else:
    return False

def audio_callback(indata, frames, time, status):
  if status:
    print("Ошибка:", status)
  try:
    model = check_model()
    audio = indata.flatten().astype(np.float32)
    if is_speech(audio):
      audio_16k = audio[::3].astype(np.float32)  # ресэмпл 48k → 16k
      result = model.transcribe( audio_16k, language="ru", fp16=False,
        condition_on_previous_text=False   )
      text = str(result["text"]).strip().lower()
      if text:
        print(text)
  except Exception as e:
    print("Ошибка в распознавании:", e)

def whisper_stream():
  sample_rate = 48000
  duration = 3.5
  block_size = int(sample_rate * duration)
  buffer = queue.Queue()
  stream = sd.InputStream( samplerate=sample_rate,
    channels=1,  dtype="float32",  callback=audio_callback,
    blocksize=block_size )
  print("Старт")
  stream.start()
  time.sleep(duration)
  stream.stop()
  stream.close()

while 1:
  whisper_stream()

import time, os, queue
import sounddevice as sd
import numpy as np
from pathlib import Path
from libs_voice import *
from pynput import keyboard
from faster_whisper import WhisperModel

def on_press(key):  # обработчик клави.
  key = str(key).replace(" ", "")
  if key == "Key.shift_r":    #
    k.set_flag(True)
    return True
  if key == "Key.space" or key =="Key.right" or key =="Key.left" or key =="Key.down" or key =="Key.up":
    k.set_flag(False)
    return True
  if key == "Key.alt":
    driver=k.get_driver()
    k.update_dict()
    return True
  else:
    return True

def on_release(key):
  pass
  return True

def a():
  listener = keyboard.Listener(on_press=on_press, on_release=on_release)
  listener.start()

cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)  # Создаёт или пропускает
os.environ["XDG_CACHE_HOME"] = str(cache_dir)
subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)  # вкл микрофон.
models = ["tiny", "base", "small", "medium", "large", "large-v3"]
model = WhisperModel(models[2], device="cpu", compute_type="int8")  # Убедитесь, что модель скачана через faster-whisper

# Параметры записи
sample_rate = 16000  # Частота дискретизации
duration = 5.5  # Минимальная длительность блока (0.5 секунды)
block_size = int(sample_rate * duration)  # 16000 * 5.5 = 88000 сэмплов
buffer = queue.Queue()  # Оставляем для совместимости, но используем напрямую
# Функция обратного вызова для записи аудио
def audio_callback(indata, frames, time, status):
  if status:
    print("Ошибка:", status)  # Прямое распознавание без буфера
  audio = indata.flatten().astype(np.float32)
  segments, _ = model.transcribe(
    audio, language="ru", beam_size=5, vad_filter=True
  )
  text = "".join(segment.text for segment in segments).strip().lower()
  print(text)
  # thread = threading.Thread(target=process_text, args=(text, k,))
  # thread.start()

# Запуск записи
stream = sd.InputStream(samplerate=sample_rate, channels=1,
  dtype="float32", callback=audio_callback, blocksize=block_size)
stream.start()
print("11")
try:
  while True:
    time.sleep(0.1)  # Минимальная задержка для основного потока
except KeyboardInterrupt:
  print("Завершение записи.")
finally:
  stream.stop()
  stream.close()
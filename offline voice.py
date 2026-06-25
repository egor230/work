import time, whisper, os, queue
import sounddevice as sd
import numpy as np
from pathlib import Path
from libs_voice import *
from pynput import keyboard
def on_press(key):  # обработчик клави.  # print(key )
  key = str(key).replace(" ", "")
  if key == "Key.shift_r":    #
    k.set_flag(True)
    return True
  if key == "Key.space" or key =="Key.right" or key =="Key.left"\
  or key =="Key.down" or key =="Key.up":
    k.set_flag(False)
    return True
  if key == "Key.alt":
    driver=k.get_driver()
    k.update_dict()
    # driver.find_element("id", "mic").click()  # включить запись голоса
    # time.sleep(2.5)
    # driver.find_element("id", "mic").click()  # включить запись голоса
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
models = ["tiny",
    "base", "small",
    "medium","large"]
model = whisper.load_model(models[4])  # Убедитесь, что модель скачана через whisper.load_model()

# # Параметры записи
sample_rate = 16000  # Частота дискретизации
duration = 12  # Длительность записи (10 секунд)
block_size = sample_rate * duration  # 16000 * 10 = 160000 сэмплов
buffer = queue.Queue()
# Функция обратного вызова для записи аудио
def audio_callback(indata, frames, time, status):
    if status:
        print("Ошибка:", status)
    buffer.put(indata.copy())

# Запуск записи
stream = sd.InputStream(
    samplerate=sample_rate,
    channels=1,
    dtype="float32",
    callback=audio_callback,
    blocksize=block_size
)
stream.start()
try:
  print("Говорите! Распознавание начнется...")  # Перемещено сюда
  while True:
   if not buffer.empty():
    print("++++++++\n")
    audio = buffer.get()
    # Преобразование в формат, ожидаемый Whisper
    audio = audio.flatten().astype(np.float32)
    # Распознавание
    result = model.transcribe(
      audio, language="ru",
      fp16=False  # Отключаем FP16 для CPU
    )
    text = str(result["text"])
    thread = threading.Thread(target=process_text, args=(text, k,))  # break  #     #thread.daemon
    thread.start()  #
    thread.join()
    print("Говорите! Распознавание начнется...")  # Перемещено сюда
except KeyboardInterrupt:
    print("Завершение записи.")
finally:
    stream.stop()
    stream.close()
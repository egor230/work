import gigaam, os, time, math, json, threading, subprocess, collections, sys, re, warnings
from scipy.io.wavfile import write
from queue import Queue
import sounddevice as sd
import tkinter as tk
from tkinter import Frame, Label
from scipy.io import wavfile
import soundfile as sf
from scipy import signal
import numpy as np
from pathlib import Path
from pynput.keyboard import Controller, Key, Listener
from pynput import keyboard
model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/meta-llama-3.1-8b-instruct-q4_k_m.gguf"
# Глобальная переменная для модели (чтобы не перезагружать)
# llm = None

class save_key:
 def __init__(self):
  self.text = ""
  self.flag = False
  self.word = []
  self.res = {}
  self.new_res = {}
  self.driver = None

 def save_driver(self, driver):
  self.driver = driver

 def get_driver(self):
  return self.driver

 def save_text(self, text):
  self.text = text

 def get_text(self):
  return self.text

 def get_flag(self):
  return self.flag

 def set_flag(self, value):
  self.flag = value

 def update_dict(self):
  data = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/list for replacements.json"  # файл настроек.
  if os.path.exists(data):  # есть ли этот файл.
   with open(data, encoding="cp1251") as json_file:  # загрузка настроек из файла.
    self.res = json.load(json_file)  # проходимся по каждому элементу словаря
    for key in self.res.keys():  # Если ключ содержит '*', добавляем его в новый словарь
     if '*' in key:
      self.new_res[key] = self.res[key]
    for key in self.new_res.keys():
     del self.res[key]

 def get_dict(self):  # словарь без *
  return self.res

 def get_new_dict(self):  # словарь с *
  return self.new_res

 def save_words(self, w):
  self.word.clear()
  for i in w:
   self.word.append(i)
  self.word = sorted(self.word, key=lambda s: len(s.split()), reverse=True)

 def get_words(self):
  return self.word
k = save_key()
k.update_dict()  # Changed Contr1 to Controller
keyboard = Controller()
def on_press(key):
  key = str(key).replace(" ", "")
  if key == "Key.shift_r":
      k.set_flag(True)
      return True
  if key in ["Key.space", "Key.right", "Key.left", "Key.down", "Key.up"]:
      k.set_flag(False)
      return True
  if key == "Key.alt":
      driver = k.get_driver()
      k.update_dict()
      return True
  return True
def on_release(key):
  pass
  return True

def start_listener():
  global listener
  listener = Listener(on_press=on_press, on_release=on_release)
  listener.start()
start_listener()

def replace(match):
  res = k.get_dict()
  return res[match.group(0)]

def repeat(text1 : str):  # text = "linux менч установить линукс минт помоги мне установить "
  text=text1.replace("?", "").replace(".", "").replace("!", "")
  k.save_text(text)
  text1 = ""
  res = k.get_dict()
  k.save_words(res)
  words = k.get_words()  #print(words)
  try:   # Создаем регулярное выражение для всех слов и словосочетаний из словаря
   words_regex = r'\b(' + r'|'.join(map(re.escape, words)) + r')\b'
   # Выполняем замену с учетом регистра
   text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
   k.save_text(text1)
   # Дополнительная замена для слов из словаря res
   # for word, replacement in res.items():
   #  text1 = re.sub(r'\b' + re.escape(word) + r'\b', replacement, text1, flags=re.IGNORECASE)
  except Exception as ex:
   print(f"Ошибка: {ex}")  # Выводим ошибку для диагностики
  return text1
# llm=load_model(MODEL_PATH)
def press_keys(text):  # xte 'keyup Shift_L'
 try:   #
   text=repeat(text)
   print(text)
   key_s = '''#!/bin/bash
   # xte 'keyup Shift_R'
   # sleep 0.1
   # xte 'keyup Shift_L'
   xkbset -sticky
   xte "key Num_Lock"
   # command = 'xte "key Num_Lock"'
   # subprocess.run(command, shell=True)
   exit     '''
   # text="lunix mint"
   char_to_xdotool = { ",": "comma",
   ":": "shift+semicolon" }
   liters_en=['a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E', 'f', 'F', 'g', 'G', 'h', 'H', 'i', 'I', 'j', 'J', 'k', 'K', 'l', 'L', 'm', 'M',
     'n', 'N', 'o', 'O', 'p', 'P', 'q', 'Q', 'r', 'R', 's', 'S', 't', 'T', 'u', 'U', 'v', 'V', 'w', 'W', 'x', 'X', 'y', 'Y', 'z', 'Z']  # Диапазон от пробела до тильды (ASCII 32-126)#
   for char in text:
    if char in char_to_xdotool:
      subprocess.run(['bash', '-c', key_s])
      subprocess.call(['xdotool', 'key', char_to_xdotool[char]])
      continue
    if char in liters_en:
       subprocess.call(['xdotool', 'type', '--delay', '3', char])
    else:
     if char.isupper():  # Если символ заглавный
      keyboard.press(char.upper())  # Нажимаем строчную версию символа
      keyboard.release(char.upper())
      # keyboard.release(Key.shift)  # Отпустить Shift
      # subprocess.run(['bash', '-c', key_s])
     else:
      keyboard.press(char)
      keyboard.release(char)
    time.sleep(0.03)  # Уменьшение задержки
   # Включить sticky keys
   subprocess.call(['xkbset', 'sticky'])
 except Exception as ex1:
    print(ex1)
    return

def process_text(previous_message1):
  text = previous_message1 + str(" ")
  text=text[0].lower()+ text[1:]
  if k.get_flag() == True:
    k.set_flag(False)
    text0 = text[0].upper() + text[1:]
    press_keys(text0)
  else:
    press_keys(text)


def enhance_speech_for_recognition(audio, sample_rate=48000):
 try:
  audio = audio.astype(np.float32)
  nyquist = sample_rate / 2

  ## 1. Полосовая фильтрация (Оставляем без изменений)
  # Фокусируемся на частотах речи
  b, a = signal.butter(2, [100 / nyquist, 6000 / nyquist], btype='band')
  audio = signal.filtfilt(b, a, audio)

  ## 2. Более агрессивное усиление с нормализацией (AGC)
  # Увеличиваем максимальный коэффициент усиления (с 3.0 до 5.0)
  rms = np.sqrt(np.mean(audio ** 2))
  if rms > 0:
   # Позволяем более сильное усиление для тихих фрагментов
   gain = min(5.0, 0.9 / rms)
   audio *= gain

  ## 3. Улучшенная, более мягкая компрессия
  # Понижаем порог (-18dB вместо -12dB), чтобы захватить более тихие звуки
  threshold_db = -18
  threshold = 10 ** (threshold_db / 20)
  envelope = np.abs(audio)

  # Сглаживание огибающей
  envelope_smooth = np.convolve(envelope, np.ones(100) / 100, mode='same')
  gain = np.ones_like(audio)

  compression_mask = envelope_smooth > threshold
  # Смягчаем коэффициент компрессии (0.15 вместо 0.25),
  # чтобы не сильно "сплющивать" динамику, позволяя модели
  # лучше различать нечеткие звуки.
  gain[compression_mask] = (threshold / envelope_smooth[compression_mask]) ** 0.15

  audio *= gain
  audio = np.clip(audio, -0.9, 0.9)

  return audio

 except Exception as e:
  print(f"Ошибка обработки аудио: {e}")
  return audio

def is_speech(threshold=0.074, audio_source="temp.wav"):
 try:
  # Если передана строка — читаем файл
  if isinstance(audio_source, (str, bytes, os.PathLike)):
   if not os.path.isfile(audio_source):
    print(f"Файл не найден: {audio_source}")
    return False
   data, sr = sf.read(audio_source, dtype='float32')

  # Если уже массив numpy
  elif isinstance(audio_source, np.ndarray):
   data = audio_source.astype('float32')  # на всякий случай приводим тип

  else:
   print("Неподдерживаемый тип данных")
   return False

  if len(data) == 0:
   print("Аудио пустое")
   return False

  # Средняя амплитуда
  amp = np.mean(np.abs(data))
  print(f"amp {amp:.5f}")

  return amp > threshold

 except Exception as ex:
  print(f"Ошибка в is_speech: {ex}")
  return False

def get_webcam_source_id():# Определяет текущий Source ID (например, '53') для HD Webcam C525,
 # Постоянное имя вашего микрофона с веб-камеры (из вашего вывода)
 TARGET_NAME = "alsa_input.usb-046d_HD_Webcam_C525_79588C20-00.mono-fallback"
 try:
  # Самый быстрый способ — использовать pactl list sources в "short" формате
  result = subprocess.run(  ['pactl', 'list', 'sources', 'short'],
   capture_output=True, text=True, check=True  )

  # Формат строки: 53    alsa_input.usb-046d_HD_Webcam_C525_...mono-fallback    PipeWire    s16le 1ch 4800Hz    RUNNING
  for line in result.stdout.splitlines():
   fields = line.split()
   if len(fields) >= 2 and TARGET_NAME in fields[1]:
    return fields[0]  # это и есть ID источника

  print("Webcam C525 не найдена в pactl list sources short", file=sys.stderr)
  return None

 except FileNotFoundError:
  print("pactl не найден. Установлен PipeWire/PulseAudio?", file=sys.stderr)
  return None
 except subprocess.CalledProcessError as e:
  print(f"pactl вернул ошибку: {e}", file=sys.stderr)
  return None


def set_mute(mute: str, source_id: str):
 if source_id is None:
  print("source_id = None → ничего не делаем", file=sys.stderr)
  return # mute = "1" или "0"
 subprocess.run(["pactl", "set-source-mute", source_id, mute], check=True)
 # Опционально — сразу ставим нормальную громкость
 subprocess.run(["pactl", "set-source-volume", source_id, "99%"], check=True)
source_id = get_webcam_source_id()      # ← твоя функция
set_mute("1", source_id)
def get_mute_status(source_id):  # Получает статус Mute для источника '54' с помощью pactl и grep.
 try:
  r = subprocess.run(["pactl", "get-source-mute", source_id],  capture_output=True, text=True, check=True)
  return r.stdout.lower()
 except:
  return False

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
# torch.set_num_threads(8)

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
# ← Загружаем только модель (processor НЕ нужен и НЕ существует)
model_name = "v3_e2e_rnnt"  # Options: any model version with suffix `_ctc` or `_rnnt`
model = gigaam.load_model(model_name)
transcription = model.transcribe("temp.wav")
print(transcription)
threading.Thread(target=run_script, daemon=True).start()
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
      if is_speech(0.077, array):
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
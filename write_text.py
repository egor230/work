import sys, os, subprocess, json, wave, io, threading, re, time, warnings, collections#, webrtcvad
from scipy.io.wavfile import write
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QTimer, QObject, pyqtSignal, Qt, QThread
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import ( QApplication, QWidget, QLabel, QVBoxLayout, QSystemTrayIcon, QMenu,
 QAction, QSlider, QMainWindow, QPushButton, QDialog)
from queue import Queue
import sounddevice as sd
import tkinter as tk
from tkinter import Frame, Label
from scipy.io import wavfile
import soundfile as sf
from scipy import signal
import numpy as np
from pathlib import Path
# from faster_whisper import WhisperModel
from pynput.keyboard import Controller, Key, Listener
from pynput import keyboard
# from llama_cpp import Llama
# Укажите путь к модели Meta-Llama-3.1-8B-Instruct (GGUF q4_K)
model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/meta-llama-3.1-8b-instruct-q4_k_m.gguf"
# Глобальная переменная для модели (чтобы не перезагружать)
# llm = None
#
# def load_model() -> Llama:    #    Загружает модель Llama один раз и возвращает объект.
#     #Если модель уже загружена, возвращает существующий объект.
#
#   global llm
#   if llm is None:
#       print("Загрузка модели... (это может занять 1-2 минуты)")
#       llm = Llama(
#           model_path=model_path,
#           n_ctx=8192,  # Большой контекст для Llama 3.1 — хватит для длинных текстов
#           n_threads=4,  # Кол-во CPU-ядер; увеличь, если нужно
#           n_gpu_layers=35,  # Если GPU: разгружает на GPU (0 для CPU only)
#           verbose=False  # Без лишнего лога
#       )
#       print("Модель загружена успешно!")
#   return llm
#
# def is_model_loaded() -> bool:
#     # Проверяет, загружена ли модель (llm не None).
#     global llm
#     return llm is not None
#
# def fix_text(text: str) -> str:
#     """
#     Исправляет текст от распознавания речи на русском: звуки (р↔л, ш↔с/х, ж↔з/г, з↔с/дз, щ↔ш/сч),
#     грамматику (падежи, склонения, род, число). Возвращает ТОЛЬКО исправленный текст.
#     Адаптировано для Llama 3.1 Instruct.
#
#     Оптимизация токенов: max_tokens динамически по длине текста (минимум 100, максимум 512).
#     """
#     global llm
#     if not is_model_loaded():
#         raise ValueError("Модель не загружена! Вызовите load_model() сначала.")
#
#     # Динамический max_tokens: пропорционально длине + запас
#     max_tokens = min(512, max(100, len(text) * 2 + 100))
#
#     prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
# Ты — эксперт по исправлению текстов, полученных от систем распознавания речи на русском языке. У меня проблемы с дикцией из-за ДЦП: плохо произносятся звуки "р" (часто заменяется на "л" или пропускается), "л" (искажается), "ш" (может звучать как "с" или "х"), "ж" (как "з" или "г"), "з" (как "с" или "дз"), "щ" (как "ш" или "сч"). Из-за этого слова искажаются, например: "работа" может стать "лабода", "школьник" — "скольник", "жизнь" — "зиснь". Также бывают ошибки в грамматике: неправильные падежи (например, "в дом" вместо "в доме"), склонения (окончания слов), роде, числе и предложениях (смешанные слова или фразы).
#
# Твоя задача:
# 1. Прочитай предоставленный текст как "грязный" вывод распознавания речи.
# 2. Исправь орфографию, учитывая типичные замены звуков (р↔л, ш↔с/х, ж↔з/г, з↔с/дз, щ↔ш/сч). Предполагай, что текст близок к реальному смыслу, но искажён произношением.
# 3. Исправь грамматику: подбери правильные падежи, склонения, род, число, времена глаголов. Сделай текст coherentным и естественным на русском.
# 4. Если текст неоднозначен, выбери наиболее логичный вариант (предполагай повседневный контекст: разговор о жизни, работе, семье или хобби).
# 5. Ответь ТОЛЬКО исправленным текстом, без лишних объяснений, кавычек, скобок. Если оригинал слишком искажён, добавь в конце: [Возможная интерпретация].<|eot_id|><|start_header_id|>user<|end_header_id|>
#
# Текст: {text}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
#
#     output = llm(  prompt,  max_tokens=max_tokens,  # Динамический: экономит токены на коротких текстах
#         temperature=0.0,  # Детерминированный вывод
#         top_p=0.9, stop=["<|eot_id|>", "</s>"],  # Стоп-токены для Llama 3.1
#         echo=False  ) # Не повторять промпт в выводе
#
#     # Извлекаем чистый ответ (после assistant)
#     response = output["choices"][0]["text"].strip()
#
#     # Убираем [Возможная интерпретация], если есть, или возвращаем как есть
#     if '[Возможная интерпретация]' in response:
#         response = response.split('[Возможная интерпретация]')[0].strip()
#
#     return response

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

def record_audio(filename = "temp.wav", duration=10, fs=48000):  # Запись аудио с микрофона
 print("star...")
 # Запись аудио
 audio_data = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float64')
 sd.wait()  # Ждем окончания записи
 audio_data = audio_data.flatten().astype(np.float32) # Конвертируем в нужный формат и сохраняем
 wavfile.write(filename, fs, (audio_data * 32767).astype(np.int16))

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
  threshold_db = -28
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
def audio(model, filename = "temp.wav"):  # Путь к аудиофайлу
  try:    # Выполняем транскрипцию аудио
   segments, info = model.transcribe( filename, language="ru",  # Русский язык явно
    beam_size=20,  # Глубокий поиск — повышает точность
    best_of=10,  # Выбирает лучший результат из 10 гипотез
    temperature=0.55,  # Детеминированно, без случайных ошибок
    vad_filter=False,  # Включено — фильтрует шум и паузы
    vad_parameters=dict(  min_silence_duration_ms=800,  # Пауза 0.8 секунды — чтобы не обрывал фразы
     speech_pad_ms=300  ),# 0.3 секунды запаса по краям фразы
    condition_on_previous_text=False,  # Избегает “залипания” на предыдущем тексте
    no_speech_threshold=0.35,  # Позволяет улавливать даже очень тихую речь
    log_prob_threshold=-1.2,  # Терпимее к неуверенным звукам
    compression_ratio_threshold=2.6,  # Разрешает немного "неидеальные" слова
    repetition_penalty=1.05,  # Мягко борется с повторами, не убивая естественность
    patience=4.0,  # Больше терпения при нечетких звуках
    chunk_length=20,  # Короткие отрезки — лучше для неравномерной речи
    suppress_tokens=[-1],  word_timestamps=False   # Новый параметр: отключаем пунктуацию и заглавки
    #initial_prompt="Transcribe the audio in lowercase letters without any punctuation marks, periods, commas, or capitalization. Write everything as plain lowercase text."
    # Или на русском:
    # , initial_prompt="Транскрибируй аудио маленькими буквами без знаков препинания, точек, запятых или заглавных букв. Пиши всё простым текстом в нижнем регистре."
    #                  "Все числа записывай словами (например, 23 → двадцать три). Пиши всё простым текстом в нижнем регистре."
    )

   message_parts = []
   for segment in segments:
    text = segment.text
    if not text:
     continue
    text = str(text).strip().lower()
    if not text:
     continue

    # Разбиваем на слова и гарантируем, что каждое — строка
    words = text.split()
    for word in words:
     # Даже если это число — превратим в строку
     message_parts.append(str(word))

    # Финальная защита: все элементы — строки
   message_parts = [str(part) for part in message_parts if str(part).strip()]
   return ' '.join(message_parts) if message_parts else None

  except Exception as e:
   print(f"Ошибка транскрипции: {e}")
   return None

  except Exception as e:
     print(f"Ошибка транскрипции: {e}")
     return None

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
  if amp > threshold:
   print(f"amp {amp:.5f}")

  return amp > threshold

 except Exception as ex:
  print(f"Ошибка в is_speech: {ex}")
  return False
    # # === 3. Усиление тихих фрагментов (адаптивное AGC) ===
    # frame_len = int(0.08 * sample_rate)  # 80 мс
    # hop = int(frame_len / 2)
    # target_rms = 0.15
    # out = np.copy(audio)
    #
    # for i in range(0, len(audio) - frame_len, hop):
    #   seg = audio[i:i + frame_len]
    #   rms = np.sqrt(np.mean(seg ** 2)) + 1e-9
    #   if rms < target_rms:
    #     gain = min(target_rms / rms, 8.0)  # сильнее для тихих
    #     out[i:i + frame_len] = seg * gain
    #
    # audio = out
    #
    # # === 4. Мягкая нормализация ===
    # peak = np.max(np.abs(audio)) + 1e-9
    # if peak > 0:
    #   audio = (audio / peak) * 0.98
    #
    # # === 5. Лёгкий лимитер (мягкое сглаживание пиков) ===
    # audio = np.tanh(audio * 1.05) * 0.98

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
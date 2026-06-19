import sys, os, subprocess, json, wave, io, threading, re, time, warnings, collections, evdev, glob, time, subprocess, sys#, webrtcvad
from evdev import UInput, ecodes
from scipy.io.wavfile import write
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, Qt, QThread
from PyQt6.QtGui import QIcon, QFont, QAction
from PyQt6.QtWidgets import ( QApplication, QWidget, QLabel, QVBoxLayout, QSystemTrayIcon, QMenu,
 QSlider, QMainWindow, QPushButton, QDialog)
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
from pynput import keyboard, mouse
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
import torch, librosa, math
import logging
warnings.filterwarnings("ignore")
# --- Конфигурация модели ---
warnings.filterwarnings("ignore", category=DeprecationWarning)
# Полное отключение мусора
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["BITSANDBYTES_NOWELCOME"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
logging.getLogger("librosa").setLevel(logging.ERROR)
logging.getLogger("audioread").setLevel(logging.ERROR)
logging.getLogger("paramiko").setLevel(logging.ERROR)


class SmartTyper:
 def __init__(self):
  try:
   subprocess.run(["sudo", "modprobe", "ntsync"], capture_output=True)
  except Exception:
   pass
  
  # 1. Общие символы (одинаково печатаются в обеих раскладках)
  self.COMMON_MAP = {
   ' ': ecodes.KEY_SPACE, '\n': ecodes.KEY_ENTER, '\t': ecodes.KEY_TAB,
   '1': ecodes.KEY_1, '2': ecodes.KEY_2, '3': ecodes.KEY_3, '4': ecodes.KEY_4,
   '5': ecodes.KEY_5, '6': ecodes.KEY_6, '7': ecodes.KEY_7, '8': ecodes.KEY_8,
   '9': ecodes.KEY_9, '0': ecodes.KEY_0, '-': ecodes.KEY_MINUS, '=': ecodes.KEY_EQUAL,
   '\\': ecodes.KEY_BACKSLASH, '!': ecodes.KEY_1, '%': ecodes.KEY_5, '*': ecodes.KEY_8,
   '(': ecodes.KEY_9, ')': ecodes.KEY_0, '_': ecodes.KEY_MINUS, '+': ecodes.KEY_EQUAL, '…': ecodes.KEY_DOT
  }
  self.COMMON_SHIFT = set(['!', '%', '*', '(', ')', '_', '+'])
  
  # 2. Английские буквы
  self.EN_MAP = {
   'q': ecodes.KEY_Q, 'w': ecodes.KEY_W, 'e': ecodes.KEY_E, 'r': ecodes.KEY_R, 't': ecodes.KEY_T,
   'y': ecodes.KEY_Y, 'u': ecodes.KEY_U, 'i': ecodes.KEY_I, 'o': ecodes.KEY_O, 'p': ecodes.KEY_P,
   'a': ecodes.KEY_A, 's': ecodes.KEY_S, 'd': ecodes.KEY_D, 'f': ecodes.KEY_F, 'g': ecodes.KEY_G,
   'h': ecodes.KEY_H, 'j': ecodes.KEY_J, 'k': ecodes.KEY_K, 'l': ecodes.KEY_L, 'z': ecodes.KEY_Z,
   'x': ecodes.KEY_X, 'c': ecodes.KEY_C, 'v': ecodes.KEY_V, 'b': ecodes.KEY_B, 'n': ecodes.KEY_N,
   'm': ecodes.KEY_M
  }
  
  # 3. Русские буквы
  self.RU_MAP = {
   'й': ecodes.KEY_Q, 'ц': ecodes.KEY_W, 'у': ecodes.KEY_E, 'к': ecodes.KEY_R, 'е': ecodes.KEY_T,
   'н': ecodes.KEY_Y, 'г': ecodes.KEY_U, 'ш': ecodes.KEY_I, 'щ': ecodes.KEY_O, 'з': ecodes.KEY_P,
   'х': ecodes.KEY_LEFTBRACE, 'ъ': ecodes.KEY_RIGHTBRACE, 'ф': ecodes.KEY_A, 'ы': ecodes.KEY_S,
   'в': ecodes.KEY_D, 'а': ecodes.KEY_F, 'п': ecodes.KEY_G, 'р': ecodes.KEY_H, 'о': ecodes.KEY_J,
   'л': ecodes.KEY_K, 'д': ecodes.KEY_L, 'ж': ecodes.KEY_SEMICOLON, 'э': ecodes.KEY_APOSTROPHE,
   'я': ecodes.KEY_Z, 'ч': ecodes.KEY_X, 'с': ecodes.KEY_C, 'м': ecodes.KEY_V, 'и': ecodes.KEY_B,
   'т': ecodes.KEY_N, 'ь': ecodes.KEY_M, 'б': ecodes.KEY_COMMA, 'ю': ecodes.KEY_DOT, 'ё': ecodes.KEY_GRAVE
  }
  
  # 4. Строго английская пунктуация (требует английскую раскладку)
  self.EN_ONLY_PUNCT = {
   '@': ecodes.KEY_2, '#': ecodes.KEY_3, '$': ecodes.KEY_4, '^': ecodes.KEY_6, '&': ecodes.KEY_7,
   '{': ecodes.KEY_LEFTBRACE, '}': ecodes.KEY_RIGHTBRACE, '|': ecodes.KEY_BACKSLASH,
   '<': ecodes.KEY_COMMA, '>': ecodes.KEY_DOT, '~': ecodes.KEY_GRAVE,
   '`': ecodes.KEY_GRAVE, '[': ecodes.KEY_LEFTBRACE, ']': ecodes.KEY_RIGHTBRACE
  }
  self.EN_ONLY_PUNCT_SHIFT = set(['@', '#', '$', '^', '&', '{', '}', '|', '<', '>', '~'])
  
  # 5. Строго русская пунктуация (требует русскую раскладку)
  self.RU_ONLY_PUNCT = {
   '№': ecodes.KEY_3
  }
  self.RU_ONLY_PUNCT_SHIFT = set(['№'])
  
  # 6. Универсальная пунктуация (работает в ОБЕИХ раскладках, БЕЗ переключения)
  # Для английской раскладки
  self.PUNCT_EN = {
   ',': ecodes.KEY_COMMA,
   '.': ecodes.KEY_DOT,
   '/': ecodes.KEY_SLASH,
   ';': ecodes.KEY_SEMICOLON,
   "'": ecodes.KEY_APOSTROPHE,
   '?': ecodes.KEY_SLASH,
   ':': ecodes.KEY_SEMICOLON,
   '"': ecodes.KEY_APOSTROPHE
  }
  self.PUNCT_EN_SHIFT = set(['?', ':', '"'])
  
  # Для русской раскладки
  self.PUNCT_RU = {
   ',': ecodes.KEY_SLASH,
   '.': ecodes.KEY_SLASH,
   '/': ecodes.KEY_BACKSLASH,
   ';': ecodes.KEY_4,
   '?': ecodes.KEY_7,
   ':': ecodes.KEY_6,
   '"': ecodes.KEY_2
  }
  self.PUNCT_RU_SHIFT = set([',', '/', ';', '?', ':', '"'])
  
  self.physical_keyboard = self.find_keyboard()
  self.ui = self.create_virtual_keyboard()
  
  # --- ВКЛЮЧЕНИЕ NUMLOCK С ГАРАНТИЕЙ LED ---
  self.ensure_numlock_on()
 
 def find_keyboard(self):
  for path in glob.glob("/dev/input/event*"):
   try:
    dev = evdev.InputDevice(path)
    if "keyboard" in dev.name.lower() or "Keyboard" in dev.name:
     return dev
   except Exception:
    continue
  print("[ERROR] Клавиатура не найдена. Запустите скрипт с sudo.")
  sys.exit(1)
 
 def create_virtual_keyboard(self):
  capabilities = {
   ecodes.EV_KEY: [ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_C, ecodes.KEY_D, ecodes.KEY_E, ecodes.KEY_F,
                   ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_I, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_M,
                   ecodes.KEY_N, ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_Q, ecodes.KEY_R, ecodes.KEY_S, ecodes.KEY_T,
                   ecodes.KEY_U, ecodes.KEY_V, ecodes.KEY_W, ecodes.KEY_X, ecodes.KEY_Y, ecodes.KEY_Z, ecodes.KEY_SPACE,
                   ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT, ecodes.KEY_COMMA, ecodes.KEY_DOT, ecodes.KEY_ENTER, ecodes.KEY_TAB,
                   ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8,
                   ecodes.KEY_9, ecodes.KEY_0, ecodes.KEY_SEMICOLON, ecodes.KEY_APOSTROPHE, ecodes.KEY_GRAVE,
                   ecodes.KEY_LEFTBRACE, ecodes.KEY_RIGHTBRACE, ecodes.KEY_BACKSLASH,
                   ecodes.KEY_MINUS, ecodes.KEY_EQUAL, ecodes.KEY_SLASH,
                   ecodes.KEY_NUMLOCK
                   ],
   ecodes.EV_LED: [ecodes.LED_NUML]
  }
  
  ui = UInput(capabilities, vendor=0x1234, product=0x5678,
              bustype=ecodes.BUS_USB, name="Smart-Virtual-Keyboard"
              )
  
  try:
   self.physical_keyboard.set_led(ecodes.LED_NUML, 1)
  except Exception as e:
   print(f"[WARN] Не удалось установить LED на физической клавиатуре: {e}")
  
  ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
  ui.syn()
  time.sleep(0.06)
  ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 0)
  ui.syn()
  time.sleep(0.1)
  
  ui.write(ecodes.EV_LED, ecodes.LED_NUML, 1)
  ui.syn()
  # time.sleep(0.06)
  
  return ui
 
 def ensure_numlock_on(self):#Надёжно включает NumLock и держит индикатор включённым"""
  print("[INFO] Принудительное включение NumLock...")
 # for _ in range(3):
  try:
    self.physical_keyboard.set_led(ecodes.LED_NUML, 1)
    self.ui.write(ecodes.EV_LED, ecodes.LED_NUML, 1)
    self.ui.syn()
    
    # Эмуляция нажатия NumLock
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
    self.ui.syn()
    time.sleep(0.5)
    # self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 0)
    # self.ui.syn()
  except Exception as e:
   print(f"[WARN] Ошибка при включении NumLock: {e}")
   time.sleep(0.2)
 
 def get_current_layout(self):
  try:
   time.sleep(0.5)
   cmd = "xset -q | grep -A 0 'LED mask' | awk '{print $10}'"
   result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
   mask = result.stdout.strip()
   if mask == "00001002":
    return 'us'
   else:
    return 'ru'
  except Exception:
   return 'us'
 
 def is_capslock_on(self):
  """Улучшенное определение Caps Lock несколькими способами"""
  try:
   # Способ 1: Через xset LED mask (самый надёжный)
   cmd = "xset -q | grep -A 0 'LED mask' | awk '{print $10}'"
   result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
   mask_str = result.stdout.strip()
   
   if mask_str:
    mask = int(mask_str, 16)
    # Caps Lock бит — обычно 3-й байт (0x00000004)
    if mask & 0x00000004:
     return True
    
   #  # Альтернативные биты (на некоторых системах)
   #  if mask & 0x00000001 or mask & 0x00000002:
   #   return True
   #
   # # Способ 2: Через xset q напрямую
   # cmd2 = "xset q | grep -i 'caps lock'"
   # result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=2)
   # if "on" in result2.stdout.lower():
   #  return True
   #
   # # Способ 3: Через evdev (физическая клавиатура)
   # if hasattr(self.physical_keyboard, 'leds'):
   #  return ecodes.LED_CAPSL in self.physical_keyboard.leds()
   #
  except Exception as e:
   print(f"[WARN] Ошибка определения Caps Lock: {e}")
  
  return False
 
 def set_layout(self, lang):
  """Надёжное переключение раскладки"""
  for attempt in range(10):
   current = self.get_current_layout()
   if current == lang:
    return True
   
   try:
    subprocess.run(["xte", "key ISO_Next_Group"], check=True, timeout=1)
    time.sleep(1.8)
    if self.get_current_layout() == lang:
     return True
   except Exception:
    pass
   
   # try:
   #  subprocess.run(["xdotool", "key", "ISO_Next_Group"], check=True, timeout=1)
   #  time.sleep(1.2)
   #  if self.get_current_layout() == lang:
   #   return True
   # except Exception:
   #  pass
   #
   # try:
   #  if lang == 'us':
   #   subprocess.run(["setxkbmap", "-layout", "us"], check=True, timeout=1)
   #  else:
   #   subprocess.run(["setxkbmap", "-layout", "ru"], check=True, timeout=1)
   #  time.sleep(1.15)
   #  if self.get_current_layout() == lang:
   #   return True
   except Exception:
    pass
   
   time.sleep(0.1)
  
  print(f"[ERROR] Не удалось переключить раскладку на {lang} после 10 попыток!")
  return False
 
 def type_text(self, text, delay=0.05):
  shift_delay = 0.1
  original_layout = self.get_current_layout()
  current_layout = original_layout
  
  # print(f"[INFO] Начало печати. Исходная раскладка: {original_layout}")

  caps_on = self.is_capslock_on()
  # print(f"[INFO] Caps Lock: {'ON' if caps_on else 'OFF'}")
  for ch in text:
   needed_layout = current_layout
   lower_ch = ch.lower()
   
   # Учёт Caps Lock
   if caps_on:# учет регистра.
    effective_upper = not ch.isupper()
   else:
    effective_upper = ch.isupper()
   
   if ch in self.COMMON_MAP:
    keycode = self.COMMON_MAP[ch]
    need_shift = ch in self.COMMON_SHIFT
   
   elif lower_ch in self.RU_MAP:
    needed_layout = 'ru'
    keycode = self.RU_MAP[lower_ch]
    need_shift = effective_upper
   
   elif lower_ch in self.EN_MAP:
    needed_layout = 'us'
    keycode = self.EN_MAP[lower_ch]
    need_shift = effective_upper
   
   elif ch in self.EN_ONLY_PUNCT:
    needed_layout = 'us'
    keycode = self.EN_ONLY_PUNCT[ch]
    need_shift = ch in self.EN_ONLY_PUNCT_SHIFT
   
   elif ch in self.RU_ONLY_PUNCT:
    needed_layout = 'ru'
    keycode = self.RU_ONLY_PUNCT[ch]
    need_shift = ch in self.RU_ONLY_PUNCT_SHIFT
   
   elif ch in self.PUNCT_EN or ch in self.PUNCT_RU:
    needed_layout = current_layout
    if current_layout == 'us':
     keycode = self.PUNCT_EN.get(ch)
     need_shift = ch in self.PUNCT_EN_SHIFT
    else:
     keycode = self.PUNCT_RU.get(ch)
     need_shift = ch in self.PUNCT_RU_SHIFT
   else:
    continue
   
   if current_layout != needed_layout:
#    print(f"[SWITCH] {current_layout} -> {needed_layout} для символа '{ch}'")
    success = self.set_layout(needed_layout)
    if success:
     current_layout = needed_layout
    else:
     print(f"[ERROR] НЕ ПЕРЕКЛЮЧИЛОСЬ! Текущая: {self.get_current_layout()}")
     time.sleep(0.3)
     if self.set_layout(needed_layout):
      current_layout = needed_layout
     else:
      continue
   
   if need_shift:
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
    self.ui.syn()
    time.sleep(shift_delay)
   
   # self.ui.write(ecodes.EV_LED, ecodes.LED_NUML, 1)
   # self.ui.syn()
   
   self.ui.write(ecodes.EV_KEY, keycode, 1)
   self.ui.syn()
   time.sleep(delay / 3.5)
   self.ui.write(ecodes.EV_KEY, keycode, 0)
   self.ui.syn()
   
   if need_shift:
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
    self.ui.syn()
   
   # time.sleep(delay)
  
  # Восстановление
  final = self.get_current_layout()
  if final != original_layout: #  print(f"[RESTORE] Восстанавливаю раскладку: {final} -> {original_layout}")
   self.set_layout(original_layout)
  
  # self.ensure_numlock_on()
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

# llm=load_model(MODEL_PATH)
def replace(match):
 res = k.get_dict()
 return res[match.group(0)]

def repeat(text1: str):
 text = text1.replace("!", ".")
 k.save_text(text)
 text1 = ""
 res = k.get_dict()
 # Передаём список ключей (словосочетаний) вместо словаря
 k.save_words(list(res.keys()))
 words = k.get_words()
 try:
  # Регулярное выражение ищет целые слова и фразы (с пробелами)
  # Используем (?<!\w) и (?!\w) для границ, чтобы не заменять части слов
  words_regex = r'(?<!\w)(' + '|'.join(map(re.escape, words)) + r')(?!\w)'
  text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
  k.save_text(text1)
 except Exception as ex:
  print(f"Ошибка: {ex}")
 return text1

typer = SmartTyper()

def press_keys(text):
 try:
  text = repeat(text)
  print(text)
  # Спецсимволы, которые лучше отправлять через key, а не type
  # char_to_xdotool = {",": "comma", ":": "colon"}
  # Сброс sticky-клавиш и NumLock (выполняется один раз)
  reset_keys_script = '''#!/bin/bash
                xte 'keyup Shift_R'
                sleep 0.1
                xte 'keyup Shift_L'
                sleep 0.1
                xkbset -sticky
                xte "key Num_Lock"
                exit '''
  #subprocess.run(['bash', '-c', reset_keys_script])
  #time.sleep(1)
  typer.type_text(text, delay=0.1)
  #subprocess.call(['xkbset', 'sticky']) # Включаем sticky keys обратно
 except Exception as ex1:
  print(ex1)

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

def enhance_speech_for_recognition(audio, sample_rate=16000):
 try:
   x = audio.astype(np.float32).copy()
   eps = 1e-8
   # Параметры компрессии (внутренние)

   threshold_db = -35  # порог, ниже которого считаем фрагмент тихим
   ratio = 4.0  # степень компрессии
   attack = 0.005  # время реакции при уменьшении громкости
   release = 0.03  # время восстановления громкости


   # 1. Считаем RMS (энергетику) в окне 10 мс,
   # чтобы определить громкость в каждый момент времени

   window = int(sample_rate * 0.01)  # 10 мс окно
   rms = np.sqrt(
    np.convolve(x * x, np.ones(window) / window, mode='same') + eps   )

   # 2. RMS → dB (логарифмическая шкала)
   rms_db = 20 * np.log10(rms + eps)

   # 3. Определяем, насколько сигнал превышает порог threshold_db
   # если не превышает — усиливать не нужно
   over_threshold = rms_db - threshold_db

   # 4. Вычисляем коэффициент усиления в dB:
   # чем громче сигнал, тем сильнее его "сжимаем"
   # тихие фрагменты остаются без изменений

   gain_db = np.where(    over_threshold > 0,
    -over_threshold * (1 - 1 / ratio),    0   )

   # 5. Переводим усиление из dB → линейный коэффициент

   gain = 10 ** (gain_db / 20)

   # 6. Сглаживаем коэффициент (attack / release),
   # чтобы не было щелчков и резких переходов

   smoothed_gain = np.zeros_like(gain)

   attack_coeff = np.exp(-1 / (sample_rate * attack))
   release_coeff = np.exp(-1 / (sample_rate * release))

   g = 1.0  # текущее плавное усиление

   for i in range(len(gain)):
    if gain[i] < g:
     # Быстрое уменьшение громкости
     g = attack_coeff * g + (1 - attack_coeff) * gain[i]
    else:
     # Медленное восстановление громкости
     g = release_coeff * g + (1 - release_coeff) * gain[i]
    smoothed_gain[i] = g

   # 7. Применяем сглаженное усиление к аудио
   compressed = x * smoothed_gain

   # 8. Небольшая нормализация, чтобы итоговый сигнал
   # занимал почти весь диапазон, но без клиппинга
   peak = np.max(np.abs(compressed))
   if peak > 0:
    compressed = compressed / peak * 0.98
   # Возвращаем улучшённое аудио
   return compressed.astype(np.float32)

   ## 1. Полосовая фильтрация (Оставляем без изменений)
   # Фокусируемся на частотах речи
   # b, a = signal.butter(2, [100 / nyquist, 6000 / nyquist], btype='band')
   # audio = signal.filtfilt(b, a, audio)

  ## 2. Более агрессивное усиление с нормализацией (AGC)
   # Увеличиваем максимальный коэффициент усиления (с 3.0 до 5.0)
   # rms = np.sqrt(np.mean(audio ** 2))
   # if rms > 0:
   #  # Позволяем более сильное усиление для тихих фрагментов
   #  gain = min(4.0, 0.9 / rms)
   #  audio *= gain

   # 3. Улучшенная, более мягкая компрессия
    # Понижаем порог (-28dB вместо -12dB), чтобы захватить более тихие звуки
   # threshold_db = -28
   # threshold = 10 ** (threshold_db / 20)

   # Сглаживание огибающей
   # gain = np.ones_like(audio)

    # Смягчаем коэффициент компрессии (0.15 вместо 0.25),
    # чтобы не сильно "сплющивать" динамику, позволяя модели
    # лучше различать нечеткие звуки.
   # envelope = np.abs(audio)
   # envelope_smooth = np.convolve(envelope, np.ones(100) / 100, mode='same')
   # compression_mask = envelope_smooth > threshold
   # gain[compression_mask] = (threshold / envelope_smooth[compression_mask]) ** 0.15

   # audio *= gain
   # audio = np.clip(audio, -0.9, 0.9)
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
    vad_filter=False  # Включено — фильтрует шум и паузы
    # ,vad_parameters=dict(  min_silence_duration_ms=800,  # Пауза 0.8 секунды — чтобы не обрывал фразы
    #  speech_pad_ms=300  ),# 0.3 секунды запаса по краям фразы
    # condition_on_previous_text=False,  # Избегает “залипания” на предыдущем тексте
    # no_speech_threshold=0.35,  # Позволяет улавливать даже очень тихую речь
    # log_prob_threshold=-1.2,  # Терпимее к неуверенным звукам
    # compression_ratio_threshold=2.6,  # Разрешает немного "неидеальные" слова
    # repetition_penalty=1.05,  # Мягко борется с повторами, не убивая естественность
    # patience=4.0,  # Больше терпения при нечетких звуках
    # chunk_length=20,  # Короткие отрезки — лучше для неравномерной речи
    # suppress_tokens=[-1],  word_timestamps=False   # Новый параметр: отключаем пунктуацию и заглавки
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
set_mute("0", source_id)
def get_mute_status(source_id):  # Получает статус Mute для источника '54' с помощью pactl и grep.
 try:
  r = subprocess.run(["pactl", "get-source-mute", source_id],  capture_output=True, text=True, check=True)
  return r.stdout.lower()
 except:
  return False
 
 # for char in text:
 #  time.sleep(0.2)
 #  if char in char_to_xdotool:
 #   subprocess.call(['xdotool', 'key', '--delay', '37', char_to_xdotool[char]])
 #  else:
 #   # xdotool type корректно печатает любые символы (русские, английские, заглавные)
 #   subprocess.call(['xdotool', 'type', '--delay', '37', char])
 # from llama_cpp import Llama
 # Укажите путь к модели Meta-Llama-3.1-8B-Instruct (GGUF q4_K)
 # model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/meta-llama-3.1-8b-instruct-q4_k_m.gguf"
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

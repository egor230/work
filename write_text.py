import sys, os, subprocess, json, wave, io, threading, re, time, webrtcvad, warnings
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
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
from pynput.keyboard import Controller, Key, Listener
from pynput import keyboard
from scipy.io import wavfile
import soundfile as sf
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

  self.word = sorted(self.word, key=len, reverse=True)
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
  words = k.get_words()
  k.save_words(res)
  try:
   # Создаем регулярное выражение для всех слов и словосочетаний из словаря
   words_regex = r'\b(' + r'|'.join(map(re.escape, words)) + r')\b'
   # Выполняем замену с учетом регистра
   text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
   k.save_text(text1)
   # Дополнительная замена для слов из словаря res
   # for word, replacement in res.items():
   #  text1 = re.sub(r'\b' + re.escape(word) + r'\b', replacement, text1, flags=re.IGNORECASE)
   k.save_text(text1)
  except Exception as ex:
   print(f"Ошибка: {ex}")  # Выводим ошибку для диагностики
  return text1
def press_keys(text):  # xte 'keyup Shift_L'
  try:   #
   # text=repeat(text)
   key_s = '''#!/bin/bash
   # xte 'keyup Shift_R'
   # sleep 0.1
   # xte 'keyup Shift_L'
   xkbset -sticky
   xte "key Num_Lock"
   # command = 'xte "key Num_Lock"'
   # subprocess.run(command, shell=True)
   exit     '''
   print(text)
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

def audio(model, filename = "temp.wav"):  # Путь к аудиофайлу
  try:    # Выполняем транскрипцию аудио
    segments, info = model.transcribe( filename,  # Основные параметры качества:
      beam_size=10,  # Увеличивает точность, но требует больше ресурсов
      best_of=5,  # Выбирает лучший из нескольких вариантов
      language="ru",  # Явное указание языка
      vad_filter=True,  # Фильтрация тишины - ВКЛЮЧИТЬ
      temperature=0.8,  # Для детерминированного результата
      condition_on_previous_text=False,  # Избегать зацикливания
      no_speech_threshold=0.5,  # Порог определения речи
      log_prob_threshold=-0.8,  # Порог уверенности модели
      compression_ratio_threshold=2.2,  # Фильтрация бессмыслицы    # Параметры для русского языка:
      suppress_tokens=None,  # Не подавлять специальные токены
      word_timestamps=False,  # Выключить для скорости
      repetition_penalty=1.2,  # Бороться с повторениями     # Оптимизация:
      patience=2.0,  # Терпимость в поиске
      chunk_length=30 )  # Длина сегментов# Параллельная обработка
    message_parts = []
    for segment in segments:  # Собираем текст из всех сегментов
      text = segment.text.strip()  # Удаляем лишние пробелы
      if text:  # Проверяем, что текст не пустой
        # Приводим первый символ к нижнему регистру
        text = text[0].lower() + text[1:] if len(text) > 0 else text
        message_parts.append(text)

    if message_parts:  # Формируем итоговое сообщение
      message = ' '.join(message_parts)
      return message
    else:
      return None  # Возвращаем None, если текст не распознан

  except Exception as e:
    print(f"Ошибка транскрипции: {e}")
    return None



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

def is_speech(audio_data="temp.wav", threshold=0.0308):
  try:
    if not os.path.isfile(audio_data):
        print(f"Файл не найден: {audio_data}")
        return False
    data, sr = sf.read(audio_data, dtype='float32')
    if len(data) == 0:
        print("Файл пуст")
        return False
    amp = np.mean(np.abs(data))
    return amp > threshold
  except Exception as ex:
    print(f"Ошибка при обработке аудио: {ex}")
    return False

def get_mute_status():  # Получает статус Mute для источника '54' с помощью pactl и grep.
 try:
  r = subprocess.run(["pactl", "get-source-mute", "54"],  capture_output=True, text=True, check=True)
  return r.stdout.lower()
 except:
  return False
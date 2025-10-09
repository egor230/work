import sys, os, subprocess, json, queue, wave, io, threading
from scipy.io.wavfile import write
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
from PyQt5 import QtCore, QtWidgets, QtGui  # Импорт необходимых модулей из PyQt5
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QAction, QMenu, QWidget, QDialog, QLabel, QSystemTrayIcon, QMenu, QAction, QVBoxLayout, QPushButton, QApplication
import sounddevice as sd
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
from pynput.keyboard import Controller, Listener

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

 def get_words(self):
  return self.word

k = save_key()
k.update_dict()

keyboard_controller = Controller()
keyboard = Controller()  # Changed Contr1 to Controller

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

def repeat(text):  # text = "linux менч установить линукс минт помоги мне установить "
  # print(text)
  k.save_text(text)
  text1 = ""
  res = k.get_dict()
  k.save_words(res)
  words = k.get_words()
  # print(words)
  try:
   # Создаем регулярное выражение для всех слов и словосочетаний из словаря
   words_regex = r'\b(' + r'|'.join(map(re.escape, words)) + r')\b'
   # Выполняем замену с учетом регистра
   text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
   k.save_text(text1)
   # Дополнительная замена для слов из словаря res
   for word, replacement in res.items():
    text1 = re.sub(r'\b' + re.escape(word) + r'\b', replacement, text1, flags=re.IGNORECASE)
   k.save_text(text1)
  except Exception as ex:
   print(f"Ошибка: {ex}")  # Выводим ошибку для диагностики
  return text1
def press_keys(text):  # xte 'keyup Shift_L'
  try:   #
   print(text)
   # text="lunix mint"
   for char in text:
    if char in ['a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E', 'f', 'F', 'g', 'G', 'h', 'H', 'i', 'I', 'j', 'J', 'k', 'K', 'l', 'L', 'm', 'M',
     'n', 'N', 'o', 'O', 'p', 'P', 'q', 'Q', 'r', 'R', 's', 'S', 't', 'T', 'u', 'U', 'v', 'V', 'w', 'W', 'x', 'X', 'y', 'Y', 'z', 'Z',' ']:  # Диапазон от пробела до тильды (ASCII 32-126)#
     subprocess.call(['xdotool', 'type', '--delay', '9', char])
      # pyautogui.write(char, interval=0.01)
    else:  # Русский или смешанный вкладку ак
     if char.isupper():  # Если символ заглавный
      keyboard.press(char.upper())  # Нажимаем строчную версию символа
      keyboard.release(char.upper())
     else:
      keyboard.press(char)
      keyboard.release(char)
      time.sleep(0.03)  # Уменьшение задержки
   #
  except Exception as ex1:
    print(ex1)
    return
  
  
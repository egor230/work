import subprocess, sys, os, json, queue, wave

from scipy.io.wavfile import write
import threading
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
from PyQt5 import QtCore, QtWidgets, QtGui  # Импорт необходимых модулей из PyQt5
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QAction, QMenu, QWidget, QDialog, QLabel, QSystemTrayIcon, QMenu, QAction, QVBoxLayout, QPushButton, QApplication
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key
from pathlib import Path
from faster_whisper import WhisperModel
import io  # Если ещё не импортировано

# Принудительно устанавливаем UTF-8 для вывода
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
# Ваш кастомный путь для кэша
custom_cache = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache/whisper/"

# Размер модели
model_size = "large-v3"
# Базовый путь к модели в кэше HF
expected_model_dir = os.path.join(custom_cache, f"models--Systran--faster-whisper-{model_size}")
# Автоматический поиск snapshots (берём единственную поддиректорию)
snapshots_dir = os.path.join(expected_model_dir, "snapshots")

if not os.path.exists(snapshots_dir):
 print(f"Папка snapshots не найдена: {snapshots_dir}")
 print("Убедитесь, что модель скачана правильно.")
 sys.exit(1)

snapshot_hashes = [d for d in os.listdir(snapshots_dir) if os.path.isdir(os.path.join(snapshots_dir, d))]
if not snapshot_hashes:
 print("Нет snapshots в кэше. Скачайте модель заново.")
 sys.exit(1)

# Берём первый (единственный) хэш
model_path = os.path.join(snapshots_dir, snapshot_hashes[0])
print(f"Используем путь к модели: {model_path}")
# Проверка ключевого файла (model.bin)
if not os.path.exists(os.path.join(model_path, "model.bin")):
 print(f"Файл model.bin не найден в: {model_path}")
 sys.exit(1)
 
# class save_key:
#  def __init__(self):
#   self.text = ""
#   self.flag = False
#   self.word = []
#   self.res = {}
#   self.new_res = {}
#   self.driver = None
#
#  def save_driver(self, driver):
#   self.driver = driver
#
#  def get_driver(self):
#   return self.driver
#
#  def save_text(self, text):
#   self.text = text
#
#  def get_text(self):
#   return self.text
#
#  def get_flag(self):
#   return self.flag
#
#  def set_flag(self, value):
#   self.flag = value
#
#  def update_dict(self):
#   data = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/work/list for replacements.json"  # файл настроек.
#   if os.path.exists(data):  # есть ли этот файл.
#    with open(data, encoding="cp1251") as json_file:  # загрузка настроек из файла.
#     self.res = json.load(json_file)  # проходимся по каждому элементу словаря
#     for key in self.res.keys():  # Если ключ содержит '*', добавляем его в новый словарь
#      if '*' in key:
#       self.new_res[key] = self.res[key]
#     for key in self.new_res.keys():
#      del self.res[key]
#
#  def get_dict(self):  # словарь без *
#   return self.res
#
#  def get_new_dict(self):  # словарь с *
#   return self.new_res
#
#  def save_words(self, w):
#   self.word.clear()
#   for i in w:
#    self.word.append(i)
#
#  def get_words(self):
#   return self.word
#
# keyboard = Contr1()
# k = save_key()
# k.update_dict()
# def on_press(key):  # обработчик клави.  # print(key )
#  key = str(key).replace(" ", "")
#  if key == "Key.shift_r":  #
#   k.set_flag(True)
#   return True
#  if key == "Key.space" or key == "Key.right" or key == "Key.left" \
#   or key == "Key.down" or key == "Key.up":
#   k.set_flag(False)
#   return True
#  if key == "Key.alt":
#   driver = k.get_driver()
#   k.update_dict()
#   return True
#  else:
#   return True
#
# def on_release(key):
#  pass
#  return True
#
# def start_listener():
#  global listener
#  listener = keyboard.Listener(on_press=on_press, on_release=on_release)
#  listener.start()
#
# start_listener()  # Запускаем слушатель# driver.set_window_position(1, 505)
#
# def replace(match):
#   res = k.get_dict()
#   return res[match.group(0)]
#
# def repeat(text):  # text = "linux менч установить линукс минт помоги мне установить "
#   # print(text)
#   k.save_text(text)
#   text1 = ""
#   res = k.get_dict()
#   k.save_words(res)
#   words = k.get_words()
#   # print(words)
#   try:
#    # Создаем регулярное выражение для всех слов и словосочетаний из словаря
#    words_regex = r'\b(' + r'|'.join(map(re.escape, words)) + r')\b'
#    # Выполняем замену с учетом регистра
#    text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
#    k.save_text(text1)
#    # Дополнительная замена для слов из словаря res
#    for word, replacement in res.items():
#     text1 = re.sub(r'\b' + re.escape(word) + r'\b', replacement, text1, flags=re.IGNORECASE)
#    k.save_text(text1)
#   except Exception as ex:
#    print(f"Ошибка: {ex}")  # Выводим ошибку для диагностики
#   return text1
# def press_keys(text):  # xte 'keyup Shift_L'
#   try:   #
#    print(text)
#    # text="lunix mint"
#    for char in text:
#     if char in ['a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E', 'f', 'F', 'g', 'G', 'h', 'H', 'i', 'I', 'j', 'J', 'k', 'K', 'l', 'L', 'm', 'M',
#      'n', 'N', 'o', 'O', 'p', 'P', 'q', 'Q', 'r', 'R', 's', 'S', 't', 'T', 'u', 'U', 'v', 'V', 'w', 'W', 'x', 'X', 'y', 'Y', 'z', 'Z',' ']:  # Диапазон от пробела до тильды (ASCII 32-126)#
#      subprocess.call(['xdotool', 'type', '--delay', '9', char])
#       # pyautogui.write(char, interval=0.01)
#     else:  # Русский или смешанный вкладку ак
#      if char.isupper():  # Если символ заглавный
#       keyboard.press(char.upper())  # Нажимаем строчную версию символа
#       keyboard.release(char.upper())
#      else:
#       keyboard.press(char)
#       keyboard.release(char)
#       time.sleep(0.03)  # Уменьшение задержки
#    #
#   except Exception as ex1:
#     print(ex1)
#     return


# Инициализация модели (для CPU)
try:
 model = WhisperModel(  model_path,
  device="cpu",  compute_type="int8" )
 print("Модель загружена успешно.")
except Exception as e:
 print(f"Ошибка загрузки модели: {e}")
 sys.exit(1)


audio_file = "temp.wav"

def audio(model): # Путь к аудиофайлу
 segments, info = model.transcribe( audio_file, beam_size=4, language="ru" ) # Только русский
 message = ' '.join([segment.text.strip() for segment in segments])
 if isinstance(message, bytes):
  message = message.decode('utf-8', errors='replace')
 return message

def record_audio(filename, duration=8, fs=44100):
# Запись аудио с микрофона
    print("Начинаю запись...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    write(filename, fs, recording)
    print(f"Запись завершена, файл сохранён как {filename}")

class MyThread(QtCore.QThread):  # Определение класса потока
 mysignal = QtCore.pyqtSignal(str)  # Объявление сигнала
 error_signal = QtCore.pyqtSignal(str)  # Добавлено объявление сигнала ошибки
 icon_signal = QtCore.pyqtSignal(str)  # Сигнал для изменения иконки

 def __init__(self, parent=None):  # Конструктор класса потока
  super(MyThread, self).__init__(parent)  # Вызов конструктора базового класса
  self.mic = True  # Добавляем переменную mic в поток

 def run(self):  # Метод, исполняемый потоком
  # Чтение данных из потока
  while True:
   try:
    if self.mic:  # Отправляем путь к первой иконке
     self.icon_signal.emit("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png")
     # Параметры записи

     # Создаём и запускаем поток для записи
     record_thread = threading.Thread(target=record_audio, args=(audio_file, ))
     record_thread.start()
     record_thread.join()
     message = audio(model)
     print(message)
     # if message:
     #   message = repeat(message)
     #   thread = threading.Thread(target=process_text, args=(message, k))
     #   thread.start()
     #   thread.join()

   except Exception as ex2:
    print(ex2)  # Лучше видеть ошибки
    self.error_signal.emit(str(ex2))

def stop(self):
 self._stop = True

class MyWindow(QtWidgets.QWidget):
 def __init__(self, parent=None):
  super(MyWindow, self).__init__(parent)
  self.icon1_path = "stop icon.jpeg"
  self.icon2_path = "голос.png"
  self.mic = True  # состояние микрофона

  self.tray_icon = QSystemTrayIcon(QtGui.QIcon(self.icon2_path), self)
  menu = QMenu()
  quit_action = QAction("Quit", self)
  quit_action.triggered.connect(self.quit_t)
  menu.addAction(quit_action)

  self.mythread = MyThread()
  self.mythread.icon_signal.connect(self.change_icon)
  self.mythread.error_signal.connect(print)  # вывод ошибок в консоль

  self.tray_icon.setContextMenu(menu)
  self.tray_icon.setToolTip("ON")
  self.tray_icon.activated.connect(self.on_tray_icon_activated)
  self.tray_icon.show()

  self.mythread.start()

 def change_icon(self, icon_path):
  self.tray_icon.setIcon(QtGui.QIcon(icon_path))
  self.tray_icon.show()

 def on_tray_icon_activated(self, reason=None):
  try:
   self.mic = not self.mic
   self.mythread.mic_toggle_signal.emit(self.mic)
   self.tray_icon.setToolTip("ON" if self.mic else "OFF")
   set_mute("0" if self.mic else "1")
   self.tray_icon.show()
  except Exception as e:
   print(f"Error in on_tray_icon_activated: {e}")

 def quit_t(self):
  self.mythread.stop()
  self.mythread.wait()
  QApplication.quit()


if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 sys.exit(app.exec_())
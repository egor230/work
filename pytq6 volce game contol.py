import sys, os
import json, threading
import time, math
import numpy as np
import collections, warnings
from pathlib import Path
from typing import Dict, Optional
from PyQt6.QtWidgets import ( QApplication, QMainWindow, QComboBox, QPushButton, QLineEdit,
 QVBoxLayout, QHBoxLayout, QWidget, QScrollArea, QMessageBox)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import QThread, Qt
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ======================= ПУТИ И НАСТРОЙКИ =======================
cache_dir = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/gigaam")
settings_file = "settings_voice_game_control_linux.json"

# Отключаем предупреждения ALSA
os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"
os.environ["JACK_NO_START_SERVER"] = "1"

# ======================= КЛЮЧЕВЫЕ ПЕРЕМЕННЫЕ (загружаются лениво) =======================
source_id = None
pres12 = None
# Глобальная переменная для модели
model = None
model_loading_lock = threading.Lock()

# ======================= ЛЕНИВАЯ ЗАГРУЗКА КЛЮЧЕВЫХ РЕСУРСОВ =======================
def get_source_id():
 """Ленивая загрузка source_id"""
 global source_id
 if source_id is None:
  from libs_voice import get_webcam_source_id, set_mute
  source_id = get_webcam_source_id()
  set_mute("0", source_id)
 return source_id

def get_pres12():
 """Ленивая загрузка pres12"""
 global pres12
 if pres12 is None:
  from libs_voice import work_key
  pres12 = work_key()
 return pres12

def get_gigaam_model():
 """Ленивая загрузка модели GigaAM"""
 from sber_gegaam import load_model
 global model

 print("Начинаю загрузку модели GigaAM...")
 try:
  model = load_model(  "v1_ctc",
   fp16_encoder=False,
   use_flash=False,
   device="cpu",
   download_root=cache_dir   )

  print("Модель GigaAM успешно загружена")
  return model
 except Exception as e:
  print(f"Ошибка загрузки модели GigaAM: {e}")
  return None


# ======================= РЕЖИМ INTERNET (speechtexter.com) =======================
def web():
 """Запускает Chrome с speechtexter.com и включает микрофон"""
 subprocess.call(['bash', '-c', 'pkill -f "chrome"; pkill -f "chromedriver"'])

 options = webdriver.ChromeOptions()
 options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.168 Safari/537.36")
 options.add_experimental_option("excludeSwitches", ['enable-automation'])
 options.add_argument("--use-fake-ui-for-media-stream")
 options.add_argument("--disable-popup-blocking")
 options.add_argument('--disable-web-security')
 options.add_argument('--disable-notifications')
 options.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
 options.binary_location = "/usr/bin/google-chrome"

 try:
  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
  driver.get("https://www.speechtexter.com")
  WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, 'mic')))
  driver.find_element(By.ID, "mic").click()
  return driver
 except Exception as e:
  print(f"Ошибка запуска браузера: {e}")
  return None


def web_press_key(driver, words_dict):
 """Читает текст из speechtexter и отправляет на обработку"""
 try:
  element = WebDriverWait(driver, 1).until(
   EC.presence_of_element_located((By.ID, "speech-text"))
  )

  text = element.get_attribute('value')
  if not text:
   text = element.text

  text = text.strip().lower()

  if text:
   driver.find_element(By.ID, "mic").click()  # выключаем
   threading.Thread(target=press_key_function, args=(text, words_dict), daemon=True).start()

   element.clear()

   time.sleep(1.5)
   driver.find_element(By.ID, "mic").click()  # включаем обратно
   time.sleep(1.5)
   driver.find_element(By.ID, "mic").click()  # включаем обратно
 except Exception as e:
  pass

def press_key_function(text, words_dict):
 """Ищет команду как подстроку в распознанном тексте."""
 text = text.strip().lower()
 pres12_instance = get_pres12()

 for phrase, key in words_dict.items():
  if phrase in text:
   key_name = key.upper().replace("KEY", "")
   pres12_instance.key_press(key_name)
   return

def get_voice_chunks(words_dict):
 """Генератор, выдающий текст после паузы в речи"""

 import sounddevice as sd
 buffer = collections.deque()
 fs = 16 * 1000
 with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
  while True:
    audio_chunk, overflowed = stream.read(2048)  # Читаем аудио порциями
    mean_amp = np.mean(np.abs(audio_chunk)) * 100
    mean_amp = math.ceil(mean_amp)  #
    if mean_amp > 5:  #
     buffer.append(audio_chunk.astype(np.float32).flatten())
     # buffer1.extend(audio_chunk.flatten())
     # if mean_amp<7:
     #  print(mean_amp)
    if mean_amp< 8 and buffer:
     array = np.concatenate(buffer)
     text = model.transcribe(array)
     buffer.clear()
     print(text)
     threading.Thread(target=press_key_function,
                      args=(text, words_dict), daemon=True).start()

class VoiceControlThread(QThread):
 def __init__(self, profile_name, words_dict):
  super().__init__()
  self.profile_name = profile_name
  self.words = words_dict or {}
  self.running = True
  self.driver = None

 def run(self):
  if self.profile_name == "internet":
   self.driver = web()

  if self.profile_name == "Vosk":
   try:
    # Загружаем модель в фоне
    get_gigaam_model()
    get_voice_chunks(self.words)
   except Exception as e:
    print(f"Критическая ошибка в потоке Vosk/GigaAM: {e}")
    self.running = False

  elif self.profile_name == "internet":
   while self.running:
    try:
     if self.driver:
      web_press_key(self.driver, self.words)
     self.msleep(200)
    except Exception as e:
     print(f"Ошибка в потоке Internet: {e}")

 def stop(self):
  self.running = False
  if self.driver:
   try:
    self.driver.quit()
    subprocess.call(['bash', '-c', 'pkill -f "chrome"; pkill -f "chromedriver"'])
   except:
    pass
  self.quit()
  self.wait()


# ======================= ИНТЕРФЕЙС =======================
class CommandWidget(QWidget):
 def __init__(self, parent=None):
  super().__init__(parent)
  layout = QHBoxLayout(self)
  self.command_edit = QLineEdit()
  self.key_combo = QComboBox()
  # Ленивая загрузка KEYS
  try:
   from libs_voice import KEYS
   self.key_combo.addItems(KEYS.keys())
  except ImportError:
   self.key_combo.addItems([])
  layout.addWidget(self.command_edit)
  layout.addWidget(self.key_combo)
  layout.setContentsMargins(0, 0, 0, 0)


class VoiceControlApp(QMainWindow):
 def __init__(self):
  super().__init__()
  self.setWindowTitle("Голосовое управление в играх")
  self.setGeometry(650, 400, 580, 350)

  self.settings_changed = False
  self.original_settings = None

  central = QWidget()
  self.setCentralWidget(central)
  layout = QVBoxLayout(central)

  self.profile_combo = QComboBox()
  self.profile_combo.addItems(["internet", "Vosk"])
  self.profile_combo.currentTextChanged.connect(self.on_settings_changed)
  layout.addWidget(self.profile_combo)

  self.scroll = QScrollArea()
  self.scroll.setWidgetResizable(True)
  self.commands_widget = QWidget()
  self.commands_layout = QVBoxLayout(self.commands_widget)
  self.scroll.setWidget(self.commands_widget)
  layout.addWidget(self.scroll)

  btn_layout = QHBoxLayout()
  self.add_btn = QPushButton("Добавить команду")
  self.del_btn = QPushButton("Удалить команду")
  self.start_btn = QPushButton("Старт")
  btn_layout.addWidget(self.add_btn)
  btn_layout.addWidget(self.del_btn)
  btn_layout.addWidget(self.start_btn)
  layout.addLayout(btn_layout)

  self.add_btn.clicked.connect(self.add_command)
  self.del_btn.clicked.connect(self.del_command)
  self.start_btn.clicked.connect(self.start_control)

  self.command_widgets = []
  self.threads = []
  self.load_settings()

 def add_command(self):
  w = CommandWidget()
  w.command_edit.textChanged.connect(self.on_settings_changed)
  w.key_combo.currentTextChanged.connect(self.on_settings_changed)
  self.commands_layout.addWidget(w)
  self.command_widgets.append(w)
  self.settings_changed = True

 def del_command(self):
  if self.command_widgets:
   w = self.command_widgets.pop()
   self.commands_layout.removeWidget(w)
   w.deleteLater()
   self.settings_changed = True

 def on_settings_changed(self):
  self.settings_changed = True

 def get_current_commands(self):
  commands = {}
  for w in self.command_widgets:
   cmd = w.command_edit.text().strip()
   key = w.key_combo.currentText()
   if cmd and key:
    commands[cmd] = key
  return commands

 def get_full_dict(self):
  commands = self.get_current_commands()
  full_dict = {}
  for phrase, key in commands.items():
   for part in [p.strip() for p in phrase.split(",") if p.strip()]:
    full_dict[part] = key
  return full_dict

 def save_settings(self, commands):
  data = {
   "Gamer": commands,
   "last_pfofile": self.profile_combo.currentText(),
   "start_startup": False
  }

  try:
   # with open(settings_file, "w", encoding="cp1251") as f:
   #  json.dump(data, f, ensure_ascii=False, indent=4)
   self.settings_changed = False
   # Сохраняем копию оригинальных настроек для сравнения
   self.original_settings = data.copy()
  except Exception as e:
   QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось сохранить настройки:\n{e}")

 def start_control(self):
  for t in self.threads:
   t.stop()
  self.threads.clear()

  commands = self.get_current_commands()
  full_dict = self.get_full_dict()

  if not full_dict:
   QMessageBox.critical(self, "Ошибка", "Добавьте хотя бы одну команду!")
   return

  thread = VoiceControlThread(self.profile_combo.currentText(), full_dict)
  thread.start()
  self.threads.append(thread)

  # Сохранение настроек при старте
  self.save_settings(commands)

 def clear_commands(self):
  while self.commands_layout.count():
   item = self.commands_layout.takeAt(0)
   if item.widget():
    item.widget().deleteLater()
  self.command_widgets.clear()

 def load_settings(self):
  if not os.path.exists(settings_file):
   return

  try:
   with open(settings_file, "r", encoding="utf-8") as f:
    data = json.load(f)
  except UnicodeDecodeError:
   with open(settings_file, "r", encoding="cp1251") as f:
    data = json.load(f)
  except Exception as e:
   QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать настройки:\n{e}")
   return

  gamer_cmds = data.get("Gamer", {})
  last_profile = data.get("last_pfofile")
  self.profile_combo.setCurrentIndex(1 if last_profile == "vosk" else 0)
  # Сохраняем оригинальные настройки для сравнения
  self.original_settings = data.copy()

  self.clear_commands()
  for cmd, key in gamer_cmds.items():
   w = CommandWidget()
   w.command_edit.setText(cmd)
   try:
    from libs_voice import KEYS
    if key in KEYS:
     w.key_combo.setCurrentText(key)
   except ImportError:
    pass
   w.command_edit.textChanged.connect(self.on_settings_changed)
   w.key_combo.currentTextChanged.connect(self.on_settings_changed)
   self.commands_layout.addWidget(w)
   self.command_widgets.append(w)

  if data.get("start_startup", False):
   self.start_control()

  self.settings_changed = False

 def closeEvent(self, event):
  # Проверяем, изменились ли настройки
  if self.settings_changed:
   reply = QMessageBox.question(
    self,
    'Сохранение настроек',
    'Настройки были изменены. Сохранить изменения?',
    QMessageBox.StandardButton.Yes |
    QMessageBox.StandardButton.No |
    QMessageBox.StandardButton.Cancel,
    QMessageBox.StandardButton.Yes
   )

   if reply == QMessageBox.StandardButton.Cancel:
    event.ignore()
    return
   elif reply == QMessageBox.StandardButton.Yes:
    commands = self.get_current_commands()
    self.save_settings(commands)

  for t in self.threads:
   t.stop()
  event.accept()


if __name__ == "__main__":
 app = QApplication(sys.argv)

 # Создаем экземпляр приложения
 app_instance = VoiceControlApp()

 # Принудительно светлая тема
 app.setStyle("Fusion")
 palette = QPalette()
 palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
 palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
 palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
 palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
 palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
 palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
 palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
 app.setPalette(palette)

 window = app_instance
 window.show()
 sys.exit(app.exec())
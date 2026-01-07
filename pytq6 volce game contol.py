import sys, os, json, threading, time, math, subprocess, collections, warnings
import numpy as np
from typing import Dict, Optional
from PyQt6.QtWidgets import (QApplication, QMainWindow, QComboBox, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea, QMessageBox)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import QThread, Qt

warnings.filterwarnings("ignore", category=DeprecationWarning)
settings_file = "settings_voice_game_control_linux.json"

os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"
os.environ["JACK_NO_START_SERVER"] = "1"

model = None
model_loading_lock = threading.Lock()
source_id = None
pres12 = None

def get_pres12():
    global pres12
    from libs_voice import work_key
    if pres12 is None:
        pres12 = work_key()
    return pres12

def get_gigaam_model():
    global model
    from sber_gegaam import load_model
    if model is None:
     try:
       cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/gigaam"
       model = load_model("ctc", download_root=cache_dir)
       print("Модель GigaAM успешно загружена")
       return model
     except Exception as e:
       print(f"Ошибка загрузки модели GigaAM: {e}")
       return None
    return model

def web():
  from selenium import webdriver
  from selenium.webdriver.chrome.service import Service
  from selenium.webdriver.common.by import By
  from webdriver_manager.chrome import ChromeDriverManager
  from selenium.webdriver.support.ui import WebDriverWait
  from selenium.webdriver.support import expected_conditions as EC
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
 try:
   element = WebDriverWait(driver, 1).until(
       EC.presence_of_element_located((By.ID, "speech-text")))
   text = element.get_attribute('value')
   if not text:
       text = element.text
   text = text.strip().lower()
   if text:
       driver.find_element(By.ID, "mic").click()
       press_key_function(text, words_dict)
       element.clear()
       time.sleep(1.5)
       driver.find_element(By.ID, "mic").click()
       time.sleep(1.5)
       driver.find_element(By.ID, "mic").click()
 except Exception:
   pass

def press_key_function(text, words_dict):
  print(text)
  # text = text.strip().lower()
  pres12_obj = get_pres12()
  # ✅ Стало — O(1), мгновенный доступ
  key = words_dict.get(text)
  if key:
   key_name = key.upper().replace("KEY", "")
   pres12_obj.key_press(key_name)

def get_voice_chunks(words_dict):
    import sounddevice as sd
    buffer = collections.deque()
    fs = 16 * 1000
    model = get_gigaam_model()
    with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
     while True:
      audio_chunk, overflowed = stream.read(7096)
      mean_amp = np.mean(np.abs(audio_chunk)) * 100
      mean_amp = math.ceil(mean_amp)
      if mean_amp > 5:
       buffer.append(audio_chunk.astype(np.float32).flatten())
      if mean_amp < 6 and buffer:
       array = np.concatenate(buffer)
       text = model.transcribe(array)
       threading.Thread(target=press_key_function, args=(text, words_dict), daemon=True).start()
       buffer.clear()

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
          while self.running:
           try:
             if self.driver:
               web_press_key(self.driver, self.words)
             self.msleep(200)
           except Exception as e:
            print(f"Ошибка в потоке Internet: {e}")
        elif self.profile_name == "Vosk":
            try:
                get_voice_chunks(self.words)
            except Exception as e:
                print(f"Критическая ошибка в потоке Vosk/GigaAM: {e}")
                self.running = False

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

class CommandWidget(QWidget):
  def __init__(self, parent=None):
     super().__init__(parent)
     layout = QHBoxLayout(self)
     self.command_edit = QLineEdit()
     self.key_combo = QComboBox()
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
            self.settings_changed = False
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
     if self.settings_changed:
      try:
        os.kill(os.getpid(), signal.SIGKILL)  # Самоубийство через kill -9
        reply = QMessageBox.question( self, 'Сохранение настроек',
         'Настройки были изменены. Сохранить изменения?',
         QMessageBox.StandardButton.Yes |  QMessageBox.StandardButton.No |
         QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes )
        if reply == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        elif reply == QMessageBox.StandardButton.Yes:
            commands = self.get_current_commands()
            # self.save_settings(commands)
        for t in self.threads:
            t.stop()
        event.accept()
      except:
        sys.exit(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
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
    window = VoiceControlApp()
    window.show()
    sys.exit(app.exec())
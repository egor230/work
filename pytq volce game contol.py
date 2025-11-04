from PyQt5.QtWidgets import ( QApplication, QMainWindow, QComboBox, QPushButton, QLineEdit, QVBoxLayout,
    QHBoxLayout, QWidget, QScrollArea, QInputDialog, QMessageBox)
from PyQt5.QtCore import QThread
from libs_voice import *
from write_text import *
import torch, gigaam, tempfile, torchaudio, math, scipy.signal, collections  # Только для deque, импорт не меняет ничего
import numpy as np
from scipy import signal
warnings.filterwarnings("ignore", category=DeprecationWarning)
# Настройка директории кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache")
# Отключаем предупреждения ALSA и JACK
os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера
err = os.dup(2)  # Сохраняем оригинальный stderr
os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем вывод ошибок в /dev/null
torch.set_num_threads(8)
subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)  # вкл микрофон.
subprocess.run(['pactl', 'set-source-volume', "54", '65000'])
# Проверка и загрузка модели GigaAM
def check_model():
 models = ["v1_ssl", "v2_ssl", "ssl", "ctc", "v1_ctc", "v2_ctc", "rnnt", "v1_rnnt", "v2_rnnt", "emo"]
 model_name = models[5]  # v2_rnnt
 model_path = cache_dir / "gigaam" / f"{model_name}"
 if not os.path.exists(f"{model_path}.ckpt"):
  print(f"Ошибка: Файл модели не найден по пути: {model_path}")
  sys.exit(1)  # Завершаем программу с кодом ошибки
 model = gigaam.load_model(model_name)
 return gigaam.load_model(model_name)
def check(driver):
 url = driver.current_url
 driver.implicitly_wait(3)
 try:
  return 0
 except Exception as ex:
  check(driver)

f = '''#!/bin/bash
     pkill -f "chrome"
     pkill -f "chromedriver" '''
def web():
 subprocess.call(['bash', '-c', f])  #
 # option = get_option()  # Включить настройки.# option.add_argument("--headless")  # Включение headless-режима
 option = webdriver.ChromeOptions()
 option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.168 Safari/537.36")
 option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
 option.add_argument("--use-fake-ui-for-media-stream")  # звук
 option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
 # # option.add_argument("--disable-extensions")  # отключить расширения.
 # option.add_argument('--disable-web-security')
 # option.add_argument('--disable-notifications')
 # # - Отключить загрузку картинок:
 # option.add_argument("--blink-settings=imagesEnabled=false")
 # option.binary_location = "/usr/bin/google-chrome"  # Стандартный путь
 # option.add_argument("--no-sandbox")
 # option.add_argument("--disable-blink-features=AutomationControlled")
 # option.add_argument("--incognito")
 # for dir_path in ["/tmp/chrome-profile", "/tmp/chrome-cache"]:
 #  if os.path.exists(dir_path):
 #   shutil.rmtree(dir_path, ignore_errors=True)
 # option.add_experimental_option("detach", True)
 # 🧹 Создаём **чистый профиль каждый раз**
 # option.add_argument("--user-data-dir=/tmp/chrome-profile")  # временная папка
 # option.add_argument("--disk-cache-dir=/tmp/chrome-cache")
 # option.add_argument("--profile-directory=Default")
 try:
  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)  # # driver.set_window_position(600, 650)
  # driver.set_window_size(624, 368) # optiol
  time.sleep(2)
  # driver.delete_all_cookies()  # Удалить cookies
  driver.get("https://www.speechtexter.com")  # открыть сайт
  #  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),  options=option)
  # check(driver)
  # driver.minimize_window()
  WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'mic')))
  driver.find_element("id", "mic").click()  # включить запись голоса
  
  return driver
 
 except Exception as ex:  #
  print(ex)
  # driver.quit()
  # if "closed connection without response" in ex:
  #     driver.quit()
  pass
  if "code 130" in ex:
   pass
 finally:
  # print(ex)
  # driver.quit()
  pass

os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
pres12 = work_key()

# try:
#
#  element = driver.find_element(By.ID, "speech-text")  # Поиск элемента по ID
#  text = str(element.text).lower()
#  if text:  # Передаем необходимые данные (text и self.words) в функцию потока
#
#   driver.find_element("id", "mic").click()
#   thread = threading.Thread(target=press_key_function, args=(text, self.words), daemon=True)
#   daemon = True  # когда завершится основная программа (главный поток).
#   thread.start()
#   time.sleep(1.5)
#   # driver.find_element("class","p_edit dir_LTR").clear()  # удалить старый текст.
#   driver.find_element("id", "mic").click()
# except Exception as ex:
#  print(f"Ошибка в потоке: {ex}")
#  driver = web()# запуск браузер.
# Пользовательский виджет для команд (голосовая команда + клавиша)
class CommandWidget(QWidget):
  def __init__(self, parent=None):
    super().__init__(parent)
    layout = QHBoxLayout(self)
    self.command_edit = QLineEdit()  # Поле для ввода голосовой команды
    self.key_combo = QComboBox()     # Выпадающий список для выбора клавиши
    self.key_combo.addItems(KEYS.keys())
    layout.addWidget(self.command_edit)
    layout.addWidget(self.key_combo)

def press_key_function(text_to_process, words_dict):
 text = text_to_process.strip().lower()
 print(text)
 if text in words_dict: # Проверяем, есть ли такое слово в словаре
    key_value = words_dict[text]  # получаем клавишу (например, 'C', 'F', 'key1')
    clean_key = key_value.upper().replace("KEY", "") # Убираем "KEY" и делаем в верхнем регистре (если нужно)
    pres12.key_press(clean_key)    # Выполняем нажатие клавиши
# Класс потока для обработки голосовых команд
buffer =  collections.deque() # ИЗМЕНЕНО: используем список вместо Queue
min_silence_duration = 1.5
fs = 16000
filename = "temp.wav"
model = check_model()
def get_liters():
 try:
  silence_time, last_speech_time = 0, 0
  with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
   while True:
     audio_chunk, overflowed = stream.read(8096)  # Читаем аудио порциями
     buffer.extend(audio_chunk.flatten())
     mean_amp = np.mean(np.abs(audio_chunk)) * 100
     mean_amp = math.ceil(mean_amp * 10) / 10
     # print(mean_amp)
     if mean_amp > 6:
      last_speech_time = time.time()
      silence_time = 0
     else:
      silence_time += time.time() - last_speech_time
      last_speech_time = time.time()
     if silence_time > min_silence_duration and buffer:
      recording_array = np.array(buffer)
      write(filename, fs, recording_array)
      if buffer:  # ✅ проверка, что буфер не пуст
       message = model.transcribe(filename)
       buffer.clear()
       silence_time, last_speech_time = 0, 0
   # os.unlink(filename)
       if message != " " and len(message) > 0:
        yield message  # ← Здесь yield вместо return
 except Exception as e:
  print(f"Ошибка: {e}")
  pass
class VoiceControlThread(QThread):
  def __init__(self, profile_name, words):
   super().__init__()
   self.profile_name = profile_name  # <- добавлено
   # ожидаем: words — словарь {фраза: клавиша}
   self.words = words or {}
   self.stopped = False
   check_model()

  def run(self):
   if get_mute_status():
    if self.profile_name == "Vosk":
    # Здесь оставлена минимальная эмуляция работы потока — встраивайте своё распознавание
     while not self.stopped:
      # Пример: печать количества команд (или любую другую диагностическую информацию)
      try:
       if self.profile_name=="Vosk":
        text = next(get_liters())#
        if text:
         thread = threading.Thread(target=press_key_function, args=(text, self.words), daemon=True)
         thread.start()  # когда завершится основная программа (главный пот
      except Exception as e:
       print("Thread error:", e)
      self.msleep(200)

  def stop(self):
   self.stopped = True

 # Основной класс приложения

class VoiceControlApp(QMainWindow):
  def __init__(self):
   super().__init__()
   self.setWindowTitle("Голосовое управление в играх")
   self.setGeometry(650, 400, 580, 250)
   self.settings_file = "settings_voice_game_control_linux.json"

   # Центральный виджет и основной макет
   self.central_widget = QWidget()
   self.setCentralWidget(self.central_widget)
   self.layout = QVBoxLayout(self.central_widget)

   # Выпадающий список профилей (только для выбора интерфейса)
   self.profile_combo = QComboBox()
   self.profile_combo.addItems(["internet", "Vosk"])
   self.layout.addWidget(self.profile_combo)

   # Кнопки управления
   self.add_command_btn = QPushButton("Добавить команду")
   self.del_command_btn = QPushButton("Удалить команду")
   self.start_btn = QPushButton("Старт")

   # Прокручиваемая область для команд
   self.scroll_area = QScrollArea()
   self.scroll_area.setWidgetResizable(True)
   self.commands_widget = QWidget()
   self.commands_layout = QVBoxLayout(self.commands_widget)
   self.scroll_area.setWidget(self.commands_widget)
   self.layout.addWidget(self.scroll_area)

   # Макет для кнопок
   buttons_layout = QHBoxLayout()
   buttons_layout.addWidget(self.add_command_btn)
   buttons_layout.addWidget(self.del_command_btn)
   buttons_layout.addWidget(self.start_btn)
   self.layout.addLayout(buttons_layout)

   # Подключение сигналов к слотам
   self.add_command_btn.clicked.connect(self.add_command)
   self.del_command_btn.clicked.connect(self.del_command)
   self.start_btn.clicked.connect(self.start_voice_control)

   # Один профиль — Gamer
   self.commands = {}  # команды и клавиши
   self.command_widgets = []  # список виджетов команд
   self.threads = []  # активные потоки
   self.current_profile = 0  # индекс выбранного элемента в combo (0=internet,1=wosk)

   # Подключаем обработчик переключения комбо
   self.profile_combo.currentIndexChanged.connect(self.change_combo)

   # Загружаем настройки
   self.load_settings()

  def add_command(self):
   widget = CommandWidget()
   self.commands_layout.addWidget(widget)
   self.command_widgets.append(widget)

  def del_command(self):
   if self.command_widgets:
    widget = self.command_widgets.pop()
    self.commands_layout.removeWidget(widget)
    widget.deleteLater()

  def start_voice_control(self):
   # Остановить потоки
   for thread in self.threads:
    try:
     thread.stop()
     thread.wait(1000)
    except Exception:
     pass
   self.threads.clear()

   # Сохраняем команды
   commands = {}
   for widget in self.command_widgets:
    command = widget.command_edit.text().strip()
    key = widget.key_combo.currentText().strip()
    if command and key:
     commands[command] = key
   self.commands = commands

   # Разворачиваем на отдельные слова
   aggregated = {}
   for cmd_str, key in self.commands.items():
    for part in [p.strip() for p in cmd_str.split(',') if p.strip()]:
     aggregated[part] = key

   if not aggregated:
    QMessageBox.critical(self, "Ошибка", "Нет команд для запуска.")
    return
   profile_name = self.profile_combo.currentText()

   # Передаём имя профиля в поток
   thread = VoiceControlThread(profile_name,aggregated)
   thread.start()
   self.threads.append(thread)

  def change_combo(self, index):
   # просто запоминаем индекс выбранного пункта
   self.current_profile = index

  def clear_commands(self):
   while self.commands_layout.count():
    item = self.commands_layout.takeAt(0)
    widget = item.widget()
    if widget:
     widget.deleteLater()
   self.command_widgets.clear()

  def load_settings(self):
   if os.path.exists(self.settings_file):
    try:
     with open(self.settings_file, "r", encoding="cp1251") as f:
      data = json.load(f)
     # Загружаем команды из Gamer
     self.commands = data.get("Gamer", {})

     # Определяем выбранный пункт выпадающего списка
     last_profile = data.get("last_pfofile", "internet")
     if last_profile == "Vosk":
      self.current_profile = 1
      self.profile_combo.setCurrentIndex(1)
     else:
      self.current_profile = 0
      self.profile_combo.setCurrentIndex(0)

     # Отображаем команды
     self.clear_commands()
     for command, key in self.commands.items():
      widget = CommandWidget()
      widget.command_edit.setText(command)
      try:
       widget.key_combo.setCurrentText(key)
      except Exception:
       pass
      self.commands_layout.addWidget(widget)
      self.command_widgets.append(widget)

     # ✅ если флаг start_startup = True → запустить сразу
     if data.get("start_startup", False):
      print("Автоматический запуск голосового управления при старте...")
      self.start_voice_control()

    except Exception as e:
     print(f"Ошибка загрузки настроек: {e}")
     self.commands = {}
     self.profile_combo.setCurrentIndex(0)
   else:
    print("Файл настроек не найден, создаю пустой набор команд")
    self.commands = {}
    self.profile_combo.setCurrentIndex(0)

  def save_settings(self):
   # сохраняем текущее значение комбо как last_pfofile
   profile_name = "Vosk" if self.current_profile == 1 else "internet"
   # data = {
   #  "last_pfofile": profile_name,
   #  "start_startup": True,
   #  "Gamer": self.commands
   # }
   # try:
   #  with open(self.settings_file, "w", encoding="cp1251") as f:
   #   json.dump(data, f, ensure_ascii=False, indent=2)
   # except Exception as e:
   #  print(f"Ошибка сохранения настроек: {e}")

  def closeEvent(self, event):
   for thread in self.threads:
    try:
     thread.stop()
     thread.wait(1000)
    except Exception:
     pass
 #   self.save_settings()
   event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoiceControlApp()
    window.show()
    sys.exit(app.exec_())
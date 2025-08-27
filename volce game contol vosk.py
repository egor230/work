from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QComboBox, QPushButton, QLineEdit, QVBoxLayout,
    QHBoxLayout, QWidget, QScrollArea, QInputDialog, QMessageBox
)
from PyQt5.QtCore import QThread
from libs_voice import *
import wave, pyaudio, vosk
from queue import Queue
from vosk import Model, KaldiRecognizer
import speech_recognition as sr


def get_steam(model_path):
 # Проверка наличия моделиmodel_path = "
 if not os.path.exists(model_path):
  print("Модель не найдена, скачайте модель и распакуйте ее в текущей директории")
  return
 # Отключаем предупреждения ALSA и JACK
 os.environ["PYAUDIO_ALSA_WARN"] = "0"
 os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
 os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера
 
 # Перенаправляем вывод ошибок в /dev/null
 err = os.dup(2)  # Сохраняем оригинальный stderr
 os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем stderr
 
 # Инициализация после перенаправления
 recognizer = sr.Recognizer()
 microphone = sr.Microphone()
 
 model = vosk.Model(model_path)
 # Инициализация PyAudio
 audio = pyaudio.PyAudio()

 # Параметры
 sample_rate = 16000  # Частота 16 кГц
 block_size = 1000*8 # Чанк 0.5 сек (оптимально для Vosk)
 # Установка параметров потока

 recognizer = vosk.KaldiRecognizer(model, sample_rate)

 # Настраиваем чувствительность
 recognizer.energy_threshold = 35  # Снижаем порог для лучшего распознавания
 recognizer.dynamic_energy_threshold = True  # Включаем динамическую настройку
 stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True,
                     frames_per_buffer=block_size)
 stream.start_stream()
 print("Начало распознавания речи... Говорите в микрофон.")
 return stream, recognizer

def recognize_from_microphone(stream, recognizer):
   # large_chunk = stream.read(16000, exception_on_overflow=False)  # Разбиваем большие данные на чанки по 16000 байт
   # for i in range(0, len(large_chunk), 8000):
   #  chunk = large_chunk[i:i + 8000]
   #  if recognizer.AcceptWaveform(chunk):
   #   result = recognizer.Result()
   #   text = json.loads(result)["text"]
   #   return text
  large_chunk = stream.read(24000, exception_on_overflow=False)
  # Большие шаги для быстрого поиска
  step=8*1000
  for i in range(0, len(large_chunk), step):
     chunk = large_chunk[i:i + step]
     if recognizer.AcceptWaveform(chunk):
      result = recognizer.Result()
      try:
       # Используем get() для избежания исключений
       data = json.loads(result)
       text = data.get("text", "")
       if text.strip():
        return text
      except:
       return ""
  return ""

os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
pres12 = work_key()

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

# Класс потока для обработки голосовых команд
class VoiceControlThread(QThread):
 def __init__(self, words):
  super().__init__()
  self.words = words
  self.stopped = False
 
 def run(self):
  model_path = "vosk-model-ru-0.10"
  stream, recognizer = get_steam(model_path)
  while not self.stopped:
   try:
    text=recognize_from_microphone(stream, recognizer)
    if text:
     print(text)
     text = text.strip().lower()
     # Проверяем, есть ли такое слово в словаре
     if text in self.words:
      key_value = self.words[text]  # получаем клавишу (например, 'C', 'F', 'key1')
      # Убираем "KEY" и делаем в верхнем регистре (если нужно)
      clean_key = key_value.upper().replace("KEY", "")
      pres12.key_press(clean_key)
   except Exception as ex:
    print(f"Ошибка в потоке: {ex}")
  
 
 def stop(self):
  self.stopped = True
# Основной класс приложения
class VoiceControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Голосовое управление в играх")
        self.setGeometry(650, 400, 580, 250)  # Размеры и позиция как в оригинале
        self.settings_file = "settings_voice_game_control_linux.json"
        # Центральный виджет и основной макет
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Выпадающий список профилей
        self.profile_combo = QComboBox()
        self.layout.addWidget(self.profile_combo)

        # Кнопки управления
        self.add_profile_btn = QPushButton("Добавить профиль")
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
        buttons_layout.addWidget(self.add_profile_btn)
        buttons_layout.addWidget(self.add_command_btn)
        buttons_layout.addWidget(self.del_command_btn)
        buttons_layout.addWidget(self.start_btn)
        self.layout.addLayout(buttons_layout)

        # Подключение сигналов к слотам
        self.add_profile_btn.clicked.connect(self.add_profile)
        self.add_command_btn.clicked.connect(self.add_command)
        self.del_command_btn.clicked.connect(self.del_command)
        self.start_btn.clicked.connect(self.start_voice_control)
        self.profile_combo.currentIndexChanged.connect(self.load_profile_commands)

        # Инициализация данных
        self.profiles = {}              # Словарь профилей и их команд
        self.current_profile = None     # Текущий выбранный профиль
        self.command_widgets = []       # Список виджетов команд
        self.threads = []               # Список активных потоков
        self.load_settings()            # Загрузка настроек при запуске

    def add_profile(self):# Добавление нового профиля через диалоговое окно"""
        name, ok = QInputDialog.getText(self, "Добавить профиль", "Введите название профиля:")
        if ok and name:
            if name not in self.profiles:
                self.profiles[name] = {}
                self.profile_combo.addItem(name)
                self.profile_combo.setCurrentText(name)
                self.clear_commands()
                self.current_profile = name
            else:
                QMessageBox.warning(self, "Ошибка", "Профиль уже существует")

    def add_command(self):# "Добавление новой команды в прокручиваемую область"""
        widget = CommandWidget()
        self.commands_layout.addWidget(widget)
        self.command_widgets.append(widget)

    def del_command(self):
        """Удаление последней команды"""
        if self.command_widgets:
            widget = self.command_widgets.pop()
            self.commands_layout.removeWidget(widget)
            widget.deleteLater()

    def start_voice_control(self):# Запуск голосового управления"""
        # Остановка существующих потоков
        for thread in self.threads:
          thread.stop()
          thread.wait()
        self.threads.clear()

        # Сохранение текущих команд профиля
        if self.current_profile:
         commands = {}
         for widget in self.command_widgets:
          command = widget.command_edit.text()
          key = widget.key_combo.currentText()
          if command and key:
           commands[command] = key
         self.profiles[self.current_profile] = commands

        # Запуск новых потоков для каждой команды
        for widget in self.command_widgets:
          words = [word.strip() for word in widget.command_edit.text().split(',') if word.strip()]
          key = widget.key_combo.currentText()
          if words and key:
           if not key:
               QMessageBox.showerror("Ошибка", "Клавиша не выбрана")
               return
           if not words[0]:
               QMessageBox.showerror("Ошибка", "Команда не введена")
               return
        new_dict = {}
        for key, value in commands.items():
         # Разделяем строку по запятым и убираем лишние пробелы
         words = [word.strip() for word in key.split(',')]
         for word in words:
          new_dict[word] = value  # каждое слово → ключ, значение = оригинальное значение (key1, key2 и т.д.)
         
        thread = VoiceControlThread(new_dict)
        thread.start()
        self.threads.append(thread)

    def load_profile_commands(self, index):# Загрузка команд выбранного профиля
        if self.current_profile:
          # Сохранение команд текущего профиля
          commands = {}
          for widget in self.command_widgets:
           command = widget.command_edit.text()
           key = widget.key_combo.currentText()
           if command and key:
            commands[command] = key
          self.profiles[self.current_profile] = commands

        # Установка нового текущего профиля
        self.current_profile = self.profile_combo.itemText(index)

        # Очистка текущих команд
        self.clear_commands()

        # Загрузка команд нового профиля
        if self.current_profile in self.profiles:
         for command, key in self.profiles[self.current_profile].items():
          widget = CommandWidget()
          widget.command_edit.setText(command)
          widget.key_combo.setCurrentText(key)
          self.commands_layout.addWidget(widget)
          self.command_widgets.append(widget)
    def clear_commands(self):
        """Очистка всех команд из прокручиваемой области"""
        while self.commands_layout.count():
            item = self.commands_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.command_widgets.clear()

    def load_settings(self):
      """Загрузка настроек из файла settings.json"""
      if os.path.exists(self.settings_file):
       try:
        with open(self.settings_file, "r", encoding="cp1251") as f:  # Изменено на cp1251
         data = json.load(f)
        last_profile = data.get("last_pfofile")
        self.profiles = data.get("profiles")
        for profile in self.profiles:
         self.profile_combo.addItem(profile)
        if last_profile in self.profiles:
         self.profile_combo.setCurrentText(last_profile)
         self.current_profile = last_profile
         self.load_profile_commands(self.profile_combo.currentIndex())

        self.start_voice_control()
       except Exception as e:
        print(f"Ошибка загрузки настроек: {e}")
      else:
       print("Файл settings volce game contol for linux.json не найден")
       self.profiles = {"default": {}}
       self.profile_combo.addItem("default")
       self.current_profile = "default"

    def save_settings(self):#Сохранение настроек в файл settings.json"""
        data = {
            "last_pfofile": self.current_profile,  # Совместимость с оригинальным ключом
            "profiles": self.profiles
        }
        # try:
        #     with open(self.settings_file, "w", encoding="cp1251") as f:
        #         json.dump(data, f, ensure_ascii=False, indent=2)
        # except Exception as e:
        #     print(f"Ошибка сохранения настроек: {e}")

    def closeEvent(self, event): #Обработка закрытия приложения. Остановка всех потоков
        for thread in self.threads:
            thread.stop()
            thread.wait()
        self.save_settings()
        # Сохранение настроек
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoiceControlApp()
    window.show()
    sys.exit(app.exec_())

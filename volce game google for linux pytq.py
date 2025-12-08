from PyQt5.QtWidgets import ( QApplication, QMainWindow, QComboBox, QPushButton, QLineEdit, QVBoxLayout,
 QHBoxLayout, QWidget, QScrollArea, QInputDialog, QMessageBox)
from PyQt5.QtCore import QThread
from libs_voice import *
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"

# Функция для взаимодействия с сайтом (оставлена без изменений)
def web():
 option = get_option()  # Включить настройки.# option.add_argument("--headless")  # Включение headless-режима
 try:
  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)  # driver.set_window_position(600, 650)
  # driver.set_window_size(624, 368) # optiol
  driver.get("https://www.speechtexter.com")  # открыть сайт
  check(driver)
  driver.minimize_window()
  driver.find_element("id", "mic").click()  # включить запись голоса
  return driver
 except Exception as ex:
   pass

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
 def __init__(self, key, words):
  super().__init__()
  self.key = key
  self.words = words
  self.stopped = False
  self.driver = None  # Объявляем как атрибут класса
  
  try:
   self.driver = web()  # Инициализируем атрибут класса
  except Exception as ex:
   print(f"Ошибка инициализации драйвера: {ex}")
 
 def run(self):
  # if self.driver is None:  # Проверяем инициализацию
  #  print("Драйвер не инициализирован")
  #  return
  t=time.time()
  while not self.stopped:
   try:
    element = driver.find_element(By.ID, "speech-text")  # Поиск элемента по ID
    text = str(element.text).lower()
    if text:
     driver.find_element("id", "mic").click()
     thread = threading.Thread(target=press_key_function, args=(text, self.words), daemon=True)
     thread.start()
     thread.join()
     time.sleep(1.5)       # driver.find_element("class","p_edit dir_LTR").clear()  # удалить старый текст.
     driver.find_element("id", "mic").click()
    if t-time.time()> 10:
     t = time.time()
     driver.find_element("id", "mic").click()
     time.sleep(2.5)       # driver.find_element("class","p_edit dir_LTR").clear()  # удалить старый текст.
     driver.find_element("id", "mic").click()
   except Exception as ex:
    print(f"Ошибка в потоке: {ex}")
  
  if self.driver:
   self.driver.quit()  # Закрываем драйвер
 
 def stop(self):
  self.stopped = True
# Основной класс приложения
class VoiceControlApp(QMainWindow):
 def __init__(self):
   super().__init__()
   self.setWindowTitle("Голосовое управление в играх")
   self.setGeometry(650, 400, 580, 250)  # Размеры и позиция как в оригинале

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
 
 def del_command(self):# Удаление последней команды"""
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
         thread = VoiceControlThread(key, words)
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
 
 def clear_commands(self):# Очистка всех команд из прокручиваемой области"""
      while self.commands_layout.count():
          item = self.commands_layout.takeAt(0)
          widget = item.widget()
          if widget:
              widget.deleteLater()
      self.command_widgets.clear()
 
 def load_settings(self):# Загрузка настроек из файла settings.json"""
    settings_file = "settings volce game contol for linux.json"
    if os.path.exists(settings_file):
     try:
      with open(settings_file, "r", encoding="cp1251") as f:  # Изменено на cp1251
       data = json.load(f)
      last_profile = data.get("last_pfofile")
      self.profiles = data.get("profiles")
      for profile in self.profiles:
       self.profile_combo.addItem(profile)
      if last_profile in self.profiles:
       self.profile_combo.setCurrentText(last_profile)
       self.current_profile = last_profile
       self.load_profile_commands(self.profile_combo.currentIndex())
 
     except Exception as e:
      print(f"Ошибка загрузки настроек: {e}")
    else:
     print("Файл settings volce game contol for linux.json не найден")
     self.profiles = {"default": {}}
     self.profile_combo.addItem("default")
     self.current_profile = "default"
 
 def save_settings(self):#Сохранение настроек в файл settings.json"""
      data = {  "last_pfofile": self.current_profile,  # Совместимость с оригинальным ключом
          "profiles": self.profiles  }
      try:
          with open("settings.json", "w", encoding="cp1251") as f:
           json.dump(data, f, ensure_ascii=False, indent=2)
      except Exception as e:
          print(f"Ошибка сохранения настроек: {e}")
 
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
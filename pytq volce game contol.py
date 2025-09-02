from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QComboBox, QPushButton, QLineEdit, QVBoxLayout,
    QHBoxLayout, QWidget, QScrollArea, QInputDialog, QMessageBox)
from PyQt5.QtCore import QThread
from libs_voice import *


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
subprocess.call(['bash', '-c', f])  #
def web():
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
class VoiceControlThread(QThread):
 def __init__(self, words):
  super().__init__()
  self.words = words
  self.stopped = False
 def run(self):
  driver = web()# запуск браузер.
  while not self.stopped:
   try:
 
    element = driver.find_element(By.ID, "speech-text")  # Поиск элемента по ID
    text = str(element.text).lower()
    if text:  # Передаем необходимые данные (text и self.words) в функцию потока
 
     driver.find_element("id", "mic").click()
     thread = threading.Thread(target=press_key_function, args=(text, self.words), daemon=True)
     daemon=True   # когда завершится основная программа (главный поток).
     thread.start()
     time.sleep(1.5)
       # driver.find_element("class","p_edit dir_LTR").clear()  # удалить старый текст.
     driver.find_element("id", "mic").click()
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
        self.profile_combo.currentIndexChanged.connect(self.load_profile_commands)

        # Инициализация данных
        self.profiles = {}              # Словарь профилей и их команд
        self.current_profile = None     # Текущий выбранный профиль
        self.command_widgets = []       # Список виджетов команд
        self.threads = []               # Список активных потоков
        self.load_settings()            # Загрузка настроек при запуске
     
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
        for thread in self.threads:
          thread.stop()        # Остановка существующих потоков
          thread.wait()
        self.threads.clear()

        if self.current_profile:        # Сохранение текущих команд профиля
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
          commands = {}      # Сохранение команд текущего профиля
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

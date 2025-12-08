from PyQt5.QtWidgets import (QApplication, QMainWindow, QComboBox, QPushButton, QLineEdit, QVBoxLayout,
    QHBoxLayout, QWidget, QScrollArea, QInputDialog, QRadioButton, QMessageBox, QCheckBox) # или PySide6.QtWidgets
from PyQt5.QtCore import QThread
from libs_voice import *
import wave, pyaudio, vosk, copy, gc, psutil, signal
from queue import Queue
from vosk import Model, KaldiRecognizer
import speech_recognition as sr
from deepdiff import DeepDiff
def check(driver):
 url = driver.current_url
 driver.implicitly_wait(3)
 try:
  return 0
 except Exception as ex:
  check(driver)

os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
pres12 = work_key()
subprocess.run( ["pactl", "set-source-mute", "54", "0"], check=True)# вкл микрофон.
def web():
 script = '''#!/bin/bash
 # Аккуратно убиваем процессы chromedriver и chrome
 pkill -f chromedriver || true
 pkill -f chrome || true
 sleep 1
 pkill -9 -f chromedriver || true
 pkill -9 -f chrome || true
 '''

 try:
  subprocess.call(['bash', '-c', script])
  option = webdriver.ChromeOptions()
  option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
  option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36")
  option.add_argument("--use-fake-ui-for-media-stream")  # звук
  option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
  option.add_argument('--disable-web-security')
  option.add_argument("--disable-blink-features=AutomationControlled")
  option.add_experimental_option("useAutomationExtension", True)
  option.add_argument("--disable-dev-shm-usage")  # помогает в Linux с /dev/shm
  option.add_argument("--disable-blink-features=AutomationControlled")  # Скрыть признаки автоматизации
  option.add_argument("--disable-notifications")  # Отключить уведомления
  option.add_argument("--use-fake-ui-for-media-stream")  # Разрешить доступ к микрофону
  option.add_extension('/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/Browsec VPN.crx')  # Загрузка расширения
  option.add_argument("--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/cache/chrome_profile")  # Папка для профиля Chrome
  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                            options=option)
  check(driver)
  driver.get("https://www.speechtexter.com")  # открыть сайт
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

 finally:
  # print(ex)
  # driver.quit()
  pass

def get_steam(model_path): # Проверка наличия моделиmodel_path = "
 if not os.path.exists(model_path):
  print("Модель не найдена, скачайте модель и распакуйте ее в текущей директории")
  return
 # Отключаем предупреждения ALSA и JACK
 os.environ["PYAUDIO_ALSA_WARN"] = "0"
 os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
 os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера
 
 err = os.dup(2)  # Сохраняем оригинальный stderr
 os.dup2(os.open(os.devnull, os.O_WRONLY), 2) # Перенаправляем вывод ошибок в /dev/null
 recognizer = sr.Recognizer() # Инициализация после перенаправления
 microphone = sr.Microphone()
 
 model = vosk.Model(model_path) # Инициализация PyAudio
 audio = pyaudio.PyAudio()
 sample_rate = 16000  # Частота 16 кГц
 recognizer = vosk.KaldiRecognizer(model, sample_rate)
 block_size = 1000*8 # Чанк 0.5 сек (оптимально для Vosk)

 # Настраиваем чувствительность
 recognizer.energy_threshold = 35  # Снижаем порог для лучшего распознавания
 recognizer.dynamic_energy_threshold = True  # Включаем динамическую настройку
 # Установка параметров потока.
 stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True,
                     frames_per_buffer=block_size)
 stream.start_stream()
 print("Начало распознавания речи... Говорите в микрофон.")
 return stream, recognizer

def recognize_from_microphone(stream, recognizer):
 large_chunk = stream.read(48000, exception_on_overflow=False)  # Разбиваем большие данные на чанки по 16000 байт
 step=4*1000
 for i in range(0, len(large_chunk), step):
  chunk = large_chunk[i:i + step]
  if recognizer.AcceptWaveform(chunk):
   result = recognizer.Result()
   text = json.loads(result)["text"]
   return text
 return ""
def press_key_function(text_to_process, words_dict):
 text = text_to_process.strip().lower()
 print(text)
 if text in words_dict: # Проверяем, есть ли такое слово в словаре
    key_value = words_dict[text]  # получаем клавишу (например, 'C', 'F', 'key1')
    clean_key = key_value.upper().replace("KEY", "") # Убираем "KEY" и делаем в верхнем регистре (если нужно)
    pres12.key_press(clean_key)    # Выполняем нажатие клавиши

class CommandWidget(QWidget):
 # Пользовательский виджет для команд (голосовая команда + клавиша)
  def __init__(self, parent=None):
    super().__init__(parent)
    layout = QHBoxLayout(self)
    self.command_edit = QLineEdit()  # Поле для ввода голосовой команды
    self.key_combo = QComboBox()     # Выпадающий список для выбора клавиши
    self.key_combo.addItems(KEYS.keys())
    layout.addWidget(self.command_edit)
    layout.addWidget(self.key_combo)

class VoiceControlThread(QThread):
  def __init__(self, words):
    super().__init__()
    self.words = words
    self.stopped = False
    self.current_profile = None
    self.driver = None

  def voice_vosk(self, stream, recognizer):
    text = recognize_from_microphone(stream, recognizer)
    if text:
      thread = threading.Thread(target=press_key_function, args=(text, self.words), daemon=True)
      thread.start()

  def voice_internet(self, driver):
   t = time.time()
   while not self.stopped:
    try:
     element = driver.find_element(By.ID, "speech-text")  # Поиск элемента по ID
     text = str(element.text).lower()
     if text:
      driver.find_element("id", "mic").click()
      thread = threading.Thread(target=press_key_function, args=(text, self.words), daemon=True)
      thread.start()
      thread.join()
      time.sleep(1.5)  # driver.find_element("class","p_edit dir_LTR").clear()  # удалить старый текст.
      driver.find_element("id", "mic").click()
     if t - time.time() > 15:
      t = time.time()
      driver.find_element("id", "mic").click()
      time.sleep(1.5)  # driver.find_element("class","p_edit dir_LTR").clear()  # удалить старый текст.
      driver.find_element("id", "mic").click()
    except Exception:
     pass
  def run(self):
   if self.current_profile == "vosk":
      model_path = "vosk-model-ru-0.10"
      stream, recognizer = get_steam(model_path)
      while not self.stopped:
        self.voice_vosk(stream, recognizer)
   elif self.current_profile == "internet":
      driver = web()
      self.driver = driver
      while not self.stopped:
        self.voice_internet(driver)

  def stop(self):
    try:
      self.stopped = True
      if self.current_profile == "vosk":
        model = None
        gc.collect()
      elif self.current_profile == "internet" and self.driver:
        self.driver.quit()
    except:
      pass

# Основной класс приложения
class VoiceControlApp(QMainWindow):
  def __init__(self):
     super().__init__()
     self.jnson = {}  # новые настройки.
     self.old_data = {}  # старые настройки.
     self.new_dict = {}  # <-- Добавьте это
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
     self.profile_combo.currentIndexChanged.connect(self.on_profile_changed)

     # Кнопки управления
     self.add_command_btn = QPushButton("Добавить команду")
     self.del_command_btn = QPushButton("Удалить команду")
     self.start_btn = QPushButton("Старт")
     self.start_btn.clicked.connect(self.start_voice_control)
     # Группа радиокнопок для типа команды
     # Заменяем радиокнопку на флажок
     self.radio_voice = QCheckBox("Запуск при старте")  # QCheckBox вместо QRadioButton
     self.radio_voice.toggled.connect(self.on_mode_changed)  # Подключаем сигнал toggled
     # Прокручиваемая область для команд
     self.scroll_area = QScrollArea()
     self.scroll_area.setWidgetResizable(True)
     self.commands_widget = QWidget()
     self.commands_layout = QVBoxLayout(self.commands_widget)
     self.scroll_area.setWidget(self.commands_widget)
     self.layout.addWidget(self.scroll_area)

     # Макет для кнопок и радио-кнопки
     buttons_layout = QHBoxLayout()
     buttons_layout.addWidget(self.add_command_btn)
     buttons_layout.addWidget(self.del_command_btn)
     buttons_layout.addWidget(self.start_btn)
     buttons_layout.addStretch(1)  # Добавляем гибкий отступ
     buttons_layout.addWidget(self.radio_voice)  # Радио-кнопка справа
     self.layout.addLayout(buttons_layout)
     # Инициализация данных
     self.profiles = {}              # Словарь профилей и их команд
     self.command_widgets = []       # Список виджетов команд
     self.threads = []               # Список активных потоков
     self.load_settings()            # Загрузка настроек при запуске
  def save_jnson(self, jn):  # сохранить новые настройки
   self.jnson = jn

  def save_old_data(self, jnson):  # сохранить начальные настройки.
   self.old_data = copy.deepcopy(jnson)
   self.jnson = jnson

  def return_jnson(self):  # Вернуть новые настройки.
   return self.jnson

  def return_old_data(self):
   return self.old_data
  def add_command(self):# "Добавление новой команды в прокручиваемую область"""
     widget = CommandWidget()
     self.commands_layout.addWidget(widget)
     self.command_widgets.append(widget)
  
  def del_command(self):# Удаление последней команды"""
    if self.command_widgets:
      widget = self.command_widgets.pop()
      self.commands_layout.removeWidget(widget)
      widget.deleteLater()
  
  def start_voice_control(self):  # Запуск голосового управления
    for thread in self.threads:
     thread.stop()  # Остановка существующих потоков
     thread.wait()
    self.threads.clear()
  
    # Обновляем self.new_dict из текущих команд
    self.new_dict.clear()
    for widget in self.command_widgets:
     words = [word.strip() for word in widget.command_edit.text().split(',') if word.strip()]
     key = widget.key_combo.currentText()
     if words and key:
      for word in words:
       self.new_dict[word] = key
     else:
      QMessageBox.warning(self, "Ошибка", "Команда или клавиша не введены")
      return
  
    # Создаем и запускаем новый поток
    thread = self.start()
    thread.start()
    self.threads.append(thread)

  def clear_commands(self):# Очистка всех команд из прокручиваемой области"""
    while self.commands_layout.count():
      item = self.commands_layout.takeAt(0)
      widget = item.widget()
      if widget:
       widget.deleteLater()
    self.command_widgets.clear()
  def start(self):# подготовка к запуску
   thread = VoiceControlThread(self.new_dict)  # <-- Добавьте это)  # Передаем self.new_dict
   data = self.return_jnson()  # Получаем текущие данные (словарь)
   thread.current_profile = data["last_pfofile"]  # Устанавливаем текущий профиль
   return thread
  def on_profile_changed(self, index):   # Функция, которая вызывается при изменении выбора
   selected_profile = self.profiles[index]#   print(f"Выбран профиль: {selected_profile} (индекс: {index})")
   data = self.return_jnson()  # Получаем текущие данные (словарь)
   data["last_pfofile"] = selected_profile  # Обновляем нужное поле
   self.save_jnson(data)  # Сохраняем обновленные данные
   for thread in self.threads:
     thread.stop()
     thread.wait()
   self.threads.clear()
   thread = self.start()
   self.threads.append(thread)
   
  def on_mode_changed(self, checked):
   data = self.return_jnson()  # Получаем текущие данные
   data["start_startup"] = checked  # Устанавливаем значение в зависимости от состояния
   self.save_jnson(data)

  def load_profile_commands(self):
   index = self.return_jnson()["last_pfofile"]
   commands = self.return_jnson()["Gamer"]  # Сохранение команд текущего профиля
   # Загрузка команд нового профиля
   for command, key in commands.items():
    widget = CommandWidget()
    widget.command_edit.setText(command)
    widget.key_combo.setCurrentText(key)
    self.commands_layout.addWidget(widget)
    self.command_widgets.append(widget)
 
   sw = self.return_jnson()["start_startup"]
   self.radio_voice.setChecked(sw)  # Устанавливаем состояние флажка
   for key, value in self.return_jnson()["Gamer"].items():
    words = [word.strip() for word in key.split(',')]  # Разделяем строку
    for word in words:
     self.new_dict[word] = value  # Каждое слово → ключ
   thread = self.start()
   if self.return_jnson()["start_startup"]:
    thread.start()
    self.threads.append(thread)
  def load_settings(self):# Загрузка настроек из файла settings.json
    if os.path.exists(self.settings_file):
     try:
      with open(self.settings_file, "r", encoding="cp1251") as f:  # Изменено на cp1251
       data = json.load(f)
       self.save_old_data(data)
      self.profiles = ["vosk", "internet"]
      self.profile_combo.blockSignals(True)  # Блокируем сигналы
      self.profile_combo.addItem(self.profiles[0])
      self.profile_combo.addItem(self.profiles[1])
      self.profile_combo.setCurrentText(data.get("last_pfofile"))
      self.new_dict = {}
      self.profile_combo.blockSignals(False)  # Разблокируем сигналы
      self.load_profile_commands()
     except Exception as e:
      print(f"Ошибка загрузки настроек: {e}")
    else:
     print("Файл settings volce game contol for linux.json не найден")
     self.profile = {"Gamer": {}}
     self.profile_combo.blockSignals(True)  # Блокируем сигналы
     self.profile_combo.addItem("vosk")
     self.profile_combo.blockSignals(False)  # Разблокируем сигналы
     self.current_profile = "vosk"
     self.new_dict = {}  # <-- Добавьте это
  
  def save_settings(self):#Сохранение настроек в файл settings.json"""
     # data = {
     #     "last_pfofile": "vosk",  # Совместимость с оригинальным ключом
     #     "start_startup": true,
     #      "Gamer": {}
     #        }
     old_data = self.return_old_data()  # старые значения настроек.
     new_data = self.return_jnson()  # новые значения настроек.
     diff = DeepDiff(old_data, new_data)
     if diff and (QMessageBox.question(self, 'Quit', "Do you want to save the changes?",
                  QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)):
       try:
         with open(self.settings_file, "w", encoding="cp1251") as f:
             json.dump(new_data, f, ensure_ascii=False, indent=2)
       except Exception as e:
         print(f"Ошибка сохранения настроек: {e}")
  
  def closeEvent(self, event): #Обработка закрытия приложения. Остановка всех потоков
     for thread in self.threads:
         thread.stop()
         thread.wait()
     self.save_settings()
     target = "volce game contol vosk.py"
     for p in psutil.process_iter(['pid', 'cmdline']):
      if p.info['cmdline'] and target in ' '.join(p.info['cmdline']):
       os.kill(p.info['pid'], signal.SIGTERM)  # Используйте сигнал SIGTERM
       break
     root.destroy()
     exit()
     sys.exit()
     event.accept()
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoiceControlApp()
    window.show()
    sys.exit(app.exec_())


'''
Хорошо, давайте разберем ваш код и влияние параметров на качество и скорость распознавания речи.

Вот анализ основных параметров:

**1. `sample_rate` (Частота дискретизации)**

* Количество аудиосэмплов, записываемых за одну секунду. Чем выше, тем точнее передается звук, включая высокие частоты.
 Увеличение (например, с 16000 до 48000 Гц):** Захватывается более широкий диапазон частот (до 24 кГц по теореме Котельникова).
  Это может улучшить качество распознавания, особенно если речь содержит много высокочастотных согласных ("с", "ш", "ц")
   или если фоновый шум находится в высокочастотном диапазоне. Однако Vosk оптимизирован для определенных частот,
  слишком высокая частота может не дать прироста, а только увеличит нагрузку.
  **Уменьшение (например, до 16000 Гц):** Может ухудшить качество, так как часть высокочастотной информации теряется.
    Но часто 16000 Гц вполне достаточно для распознавания человеческой речи.
 Влияние на скорость:** Прямо пропорционально. Удвоение `sample_rate` удваивает объем данных для обработки, замедляя процесс.

**2. `block_size` (Размер буфера аудиопотока)**

  **Что это:** Количество сэмплов, которые обрабатываются за один вызов `stream.read()`.
   **Влияние на качество:** Напрямую не влияет на *качество* звука или распознавания. Это больше технический параметр для буферизации.
**Влияние на скорость:**
    **Увеличение:** Может немного улучшить *эффективность* чтения данных из потока (меньше системных вызовов),
    но увеличивает задержку между захватом звука и началом его обработки. Может увеличить вероятность `exception_on_overflow`,
    если система не справляется.
 Уменьшение:** Уменьшает задержку, но увеличивает количество системных вызов (`stream.read`),
    что может замедлить общую работу, особенно если вызовы происходят слишком часто.

**3. Размер `large_chunk` (`stream.read(32000, ...)`)**

*Что это:** Общее количество сэмплов, считываемых за один раз для последующего анализа.
*   **Влияние на качество:** Напрямую не влияет, если только вы не уменьшите его до очень маленьких значений, где информация о речи будет фрагментарной.
*   **Влияние на скорость:**
     **Увеличение (например, до 64000):** Больше данных для анализа за один проход внешнего цикла.
    Это может быть эффективно, если ваша логика анализа (`range(0, len(large_chunk), step)`) хорошо масштабируется.
    Однако увеличивает объем данных в памяти и время, затрачиваемое на один цикл обработки.
    Уменьшение (например, до 16000):** Меньше данных для анализа за раз. Это может привести к более частому запуску внешнего цикла
    (если вы будете вызывать `stream.read()` чаще), что может увеличить накладные расходы на цикл. Но обработка каждого `large_chunk` будет быстрее.

**4. `step` (Шаг анализа внутри `large_chunk`)**

*   **Что это:** Расстояние в сэмплах между началами анализируемых фрагментов внутри `large_chunk`.
*   **Влияние на качество:**
    *   **Увеличение `step` (например, до 16000):** Вы будете анализировать *меньше* перекрывающихся фрагментов данных.
    Это может пропустить короткие всплески речи или снизить точность определения начала/конца активности, если речь прерывистая. Качество распознавания *внутри* каждого фрагмента не меняется, но *полнота* анализа снижается.
    *   **Уменьшение `step` (например, до 4000):** Более плотный анализ, меньше шансов что-то пропустить. Качество определения активности может улучшиться.
*   **Влияние на скорость:**
    *   **Увеличение `step`:** Меньше итераций цикла `for i in range(...)`, быстрее обрабатывается каждый `large_chunk`.
    *   **Уменьшение `step`:** Больше итераций цикла, медленнее обработка `large_chunk`.

*   `sample_rate = 16000`, `block_size = 16000`, `large_chunk = 32000`, `step = 8000`.
    *   Читается 2 секунды аудио (`32000 / 16000`).
    *   Анализируются фрагменты: `[0:8000]`, `[8000:16000]`, `[16000:24000]`, `[24000:32000]`.
*   Если уменьшить `large_chunk` до `16000`:
    *   Читается 1 секунда аудио.
    *   Анализируются фрагменты: `[0:8000]`, `[8000:16000]`.
    *   Внешний цикл (`while True:`) должен будет запускаться чаще, чтобы обработать тот же объем времени.
*   Если уменьшить `step` до `4000` (при `large_chunk = 32000`):
    *   Анализируются фрагменты: `[0:8000]`, `[4000:12000]`, `[8000:16000]`, `[12000:20000]`, `[16000:24000]`, `[20000:28000]`, `[24000:32000]`.
    *   Больше перекрывающихся фрагментов -> потенциально выше точность определения активности, но больше работы для цикла `for`.

**Вывод:**

 Для **качества** распознавания речи критичен `sample_rate` (в разумных пределах, обычно 16000 или 44100/48000) и плотность анализа
(`step` относительно размера анализируемого фрагмента).
  Для **скорости** обработки критичны `sample_rate` (основной фактор), размер `large_chunk` (влияет на объем данных за цикл) и `step`
  (влияет на количество итераций внутри цикла). `block_size` влияет слабее, но тоже играет роль.
*   Оптимальные значения зависят от конкретной задачи, характеристик системы и используемой модели Vosk. Часто `sample_rate=16000`
и разумные размеры буферов (`block_size`, `large_chunk`) дают хороший баланс. Экспериментируйте!'''

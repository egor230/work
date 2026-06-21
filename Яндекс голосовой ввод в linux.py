from pytq_libs_voice import *
from write_text import *

class VoiceThread(QThread):  # Основной поток для работы с Selenium и голосовым вводом
 icon_signal = pyqtSignal(str)
 status_signal = pyqtSignal(str)
 stop_request = pyqtSignal()
 
 def __init__(self, icon_mic_path, icon_record_path, icon_stop_path, parent=None):  # Инициализация потока
  super().__init__(parent)
  self.icon_mic = icon_mic_path
  self.icon_record = icon_record_path
  self.icon_stop = icon_stop_path
  self._running = True
  self.recording = False  # Флаг: идет ли сейчас запись голоса
  self.driver = None
  self._lock = threading.Lock()  # защита toggle от гонок
  self.stop_request.connect(self.stop_recording)
  self.last_speech_time = time.time()  # Время последнего обнаружения речи (перенесено в self для сброса)
 
 def stop_recording(self):  # Останавливает запись, если она активна (вызывается извне)
  if self.recording:
   self.toggle()
 
 def find_mic_button(self):  # Поиск кнопки микрофона на странице Яндекса
  try:
   wait = WebDriverWait(self.driver, 10)
   svg = wait.until(EC.presence_of_element_located(
    (By.CSS_SELECTOR,
     "button.AliceButton_pin_circle.AliceButton_size_m "
     "svg path[d*='M3.374 10']")
   ))
   mic_btn = svg.find_element(By.XPATH, "./ancestor::button")
   return mic_btn
  except Exception as e:
   logging.warning(f"Микрофон не найден: {e}")
   return None
 
 def find_stop_button(self):  # Поиск кнопки остановки записи
  selectors = [
   (By.CSS_SELECTOR, '.StandaloneRichInput-ControlsPlayer '
                     'button.AliceButton_view_secondary'),
   (By.CSS_SELECTOR, 'button.AliceButton_view_secondary'
                     '.AliceButton_square'),
  ]
  wait = WebDriverWait(self.driver, 10)
  for by, sel in selectors:
   try:
    btn = wait.until(EC.element_to_be_clickable((by, sel)))
    return btn
   except Exception:
    continue
  return None
 
 def get_recognized_text(self):  # Извлечение распознанного текста из поля ввода
  selectors = [
   (By.CSS_SELECTOR,
    "input[role='textbox'], textarea[role='textbox']"),
   (By.CSS_SELECTOR,
    ".StandaloneInput-Field input, .StandaloneInput-Field textarea"),
  ]
  for by, selector in selectors:
   try:
    element = WebDriverWait(self.driver, 3).until(
     EC.presence_of_element_located((by, selector))
    )
    text = (element.get_attribute("value") or element.text or "").strip()
    if len(text) > 2:
     return text
   except Exception:
    continue
  return ""
 
 def clear_input_field(self):  # Очистка поля ввода после получения текста
  try:
   field = WebDriverWait(self.driver, 3).until(
    EC.element_to_be_clickable(
     (By.CSS_SELECTOR, "input[role='textbox'], textarea")
    )
   )
   field.click()
   self.driver.execute_script("arguments[0].value = '';", field)
   self.driver.execute_script("arguments[0].dispatchEvent("
                              "new Event('input', {bubbles: true}));", field)
   time.sleep(0.2)
   if field.get_attribute("value"):
    field.send_keys(Keys.CONTROL + "a")
    field.send_keys(Keys.DELETE)
   remaining = field.get_attribute("value")
   if remaining:
    for _ in range(len(remaining)):
     field.send_keys(Keys.BACKSPACE)
  except Exception as e:
   logging.warning(f"Очистка поля не удалась: {e}")
 
 def click_element(self, button):  # Безопасный клик по элементу с разными методами
  if not button:
   return False
  for method_name, action in [("ActionChains", lambda: ActionChains(self.driver)
    .move_to_element(button).pause(0.1).click().perform()),
                              ("JS",
                               lambda: self.driver.execute_script("arguments[0].click();", button)),
                              ("Native", lambda: button.click()), ]:
   try:
    action()
    return True
   except Exception:
    continue
  return False
 
 def start_selenium(self):  # Запуск браузера и переход на страницу Алисы
  options = get_option()
  options.add_argument("--disable-extensions")
  # Путь к профилю Chrome (измените при необходимости)
  options.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/'
                       'linux must have/python_linux/Project/google-chrome')
  self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                                 options=options)
  self.driver.get("https://alice.yandex.ru/")
  
  original_size = self.driver.get_window_size() # 1. Запоминаем текущие размеры окна
  self.w = original_size['width']
  self.h = original_size['height']
  self.chrome_pid = self.driver.service.process.pid
  
  # Ищем окно по PID и сохраняем в self.window_id
  self.window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
  # subprocess.run(['xdotool', 'windowactivate', '--sync', self.window_id])
  # subprocess.run(['xdotool', 'windowfocus', self.window_id])
  # # Дополнительно через Selenium
  # self.driver.execute_script("window.focus();")
  # subprocess.run(['xdotool', 'windowminimize', self.window_id])
  try:
   WebDriverWait(self.driver, 15).until(
    EC.presence_of_element_located(
     (By.CSS_SELECTOR, "button.AliceButton_pin_circle"))
   )
  except Exception:
   logging.warning("Не дождались кнопки микрофона, но продолжаем")
  time.sleep(1)
 
 def _OFF(self):  # Остановка записи: нажать кнопку стоп, получить текст, очистить поле, отправить текст
  self.icon_signal.emit(self.icon_mic)
  self.status_signal.emit("Обработка...")
  button = self.find_stop_button()
  if button and self.click_element(button):
   text = self.get_recognized_text()
   if text:    # Запускаем эмуляцию ввода в отдельном потоке, чтобы не блокировать GUI
    thread = threading.Thread(target=press_keys, args=(text,))
    thread.start()
    thread.join()
   self.clear_input_field()# Получаем PID браузера от Selenium
 
 def run(self):  # Основной поток: инициализация браузера, запуск записи, прослушивание микрофона
  self.start_selenium()
  # time.sleep(2.3)
  button = self.find_mic_button()
  self.icon_signal.emit(self.icon_record)
  if button and self.click_element(button):
   self.recording = True
  self.icon_signal.emit(self.icon_record)
  # Запускаем глобальные слушатели клавиатуры и мыши (для остановки по End)
  def start_mouse_listener_with_delay():#   time.sleep(10)
   def on_press(key):
    try:
     key_name = (str(key).replace("'", "")
                 .replace(" ", "").replace("Key.", ""))
     if key_name == "end":
      self.toggle()  # Остановить/запустить запись по клавише End
      time.sleep(3)
      return False
    except Exception as e:
     print(f"Ошибка при обработке: {e}")
   
   def start_listener():
    listener = Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    # print("Слушатель клавиатуры запущен...")
   
   start_listener()
  
  listener_thread = threading.Thread(
   target=start_mouse_listener_with_delay, daemon=True
  )
  listener_thread.start()
  fs = 16 * 1000  # Настройка аудиопотока с микрофона
  with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
   while True:
    if not self._running:
     break
    audio_chunk, overflowed = stream.read(16096)
    if self.recording:
     mean_amp = np.mean(np.abs(audio_chunk)) * 100
     mean_amp = math.ceil(mean_amp)
     if mean_amp > 4:  # Порог громкости (речь)
      self.last_speech_time = time.time()  # Обновляем время последней речи
     # Если тишина длится более 3 секунд, останавливаем запись
     if time.time() - self.last_speech_time > 2.3:
      print("Тишина дольше 3 секунд, остановка записи")
      self.toggle()  # Останавливаем запись
    time.sleep(0.5)  # Небольшая пауза для снижения нагрузки
 
 def toggle(self):  # Переключение состояния записи (вкл/выкл)
   if not self.recording:
    print("recod")
    self.driver.set_window_size(self.h, self.w)  # Восстанавливаем до оригинальных размеров
    time.sleep(2)
    button = self.find_mic_button()
    self.icon_signal.emit(self.icon_record)
    if button and self.click_element(button):
     self.recording = True
     self.last_speech_time = time.time()  # Обнуляем счетчик тишины при старте записи
   else:
    # Выключаем запись
    self._OFF()
    self.recording = False
    self.status_signal.emit("Готов")
 
 def stop(self):  # Остановка потока и браузера
  self._running = False
  if self.driver:
   try:
    self.driver.quit()
   except Exception:
    pass

class MyWindow(QWidget):  # Главное окно приложения (трей)
 def __init__(self):  # Инициализация окна и трея
  super().__init__()
  BASE_PATH = os.path.dirname(os.path.abspath(__file__))
  self.icon_mic = os.path.join(BASE_PATH, "voice.png")
  self.icon_record = os.path.join(BASE_PATH, "record.png")
  self.icon_stop = os.path.join(BASE_PATH, "stop.png")
  self.thread = VoiceThread(self.icon_mic, self.icon_record, self.icon_stop)
  self.thread.icon_signal.connect(self.change_icon)
  self.thread.status_signal.connect(self.update_tooltip)
  self.tray = QSystemTrayIcon(QIcon(self.icon_mic), self)
  self.tray.setToolTip("Голосовой ввод Алиса — OFF")
  menu = QMenu()
  quit_act = QAction("Выход", self)
  quit_act.triggered.connect(self.quit_app)
  menu.addAction(quit_act)
  self.tray.setContextMenu(menu)
  self.tray.activated.connect(self.tray_clicked)
  self.tray.show()
  self.thread.start()
 
 def tray_clicked(self, reason):  # Обработка клика по трею (toggle записи)
  if reason == QSystemTrayIcon.ActivationReason.Trigger:
   self.thread.toggle()
 
 def change_icon(self, path):  # Смена иконки в трее
  self.tray.setIcon(QIcon(path))
  QApplication.processEvents()  # Принудительно обновляем иконку в трее
  self.tray.show()
 
 def update_tooltip(self, text):  # Обновление тултипа в трее
  self.tray.setToolTip(f"Голосовой ввод Алиса — {text}")
 
 def quit_app(self):  # Завершение приложения
  self.thread.stop()
  self.thread.wait(3000)
  QApplication.quit()

if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 sys.exit(app.exec())
 
 # self.status_signal.emit("Внимательно вас слушаю")
 # else:
 #  logging.error("Не удалось включить микрофон")

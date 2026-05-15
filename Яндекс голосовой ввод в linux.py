from pytq_libs_voice import *
from write_text import *

# ====================== НАСТРОЙКИ ======================
from pynput import mouse

logging.basicConfig(level=logging.INFO, format=' - %(message)s')

class VoiceThread(QThread):
 icon_signal = pyqtSignal(str)
 status_signal = pyqtSignal(str)
 stop_request = pyqtSignal()  # Сигнал для остановки записи по клику мыши

 def __init__(self, icon_mic_path, icon_stop_path, parent=None):
  super().__init__(parent)
  self.icon_mic = icon_mic_path
  self.icon_stop = icon_stop_path
  self._running = True
  self.recording = False
  self.driver = None
  self.stop_request.connect(self.stop_recording)  # Подключаем сигнал к слоту

 def stop_recording(self):
  """Останавливает запись, если она активна (безопасно из главного потока)"""
  if self.recording:
   self.toggle()

 def find_mic_button(self):
  if not self.driver:
   return None
  try:
   wait = WebDriverWait(self.driver, 10)
   svg = wait.until(EC.presence_of_element_located(
    (By.CSS_SELECTOR, "button.AliceButton_pin_circle.AliceButton_size_m svg path[d*='M3.374 10']")
   ))
   mic_btn = svg.find_element(By.XPATH, "./ancestor::button")
   return mic_btn
  except Exception as e:
   logging.warning(f"Микрофон не найден: {e}")
   return None

 def find_stop_button(self):
  if not self.driver:
   return None
  selectors = [
   (By.CSS_SELECTOR, '.StandaloneRichInput-ControlsPlayer button.AliceButton_view_secondary'),
   (By.CSS_SELECTOR, 'button.AliceButton_view_secondary.AliceButton_square'),
  ]
  wait = WebDriverWait(self.driver, 10)
  for by, sel in selectors:
   try:
    btn = wait.until(EC.element_to_be_clickable((by, sel)))
    return btn
   except:
    continue
  return None

 def get_recognized_text(self):
  """Улучшенное извлечение текста"""
  if not self.driver:
   return ""
  selectors = [
   (By.CSS_SELECTOR, "input[role='textbox'], textarea[role='textbox']"),
   (By.CSS_SELECTOR, ".StandaloneInput-Field input, .StandaloneInput-Field textarea"),
  ]
  for by, selector in selectors:
   try:
    element = WebDriverWait(self.driver, 3).until(
     EC.presence_of_element_located((by, selector))
    )
    text = (element.get_attribute("value") or element.text or "").strip()
    if len(text) > 2:
     return text
   except:
    continue
  return ""

 def clear_input_field(self):
  try:
   field = WebDriverWait(self.driver, 3).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[role='textbox'], textarea"))
   )
   field.click()
   self.driver.execute_script("arguments[0].value = '';", field)
   self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", field)
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

 def click_element(self, button):
  if not button:
   return False
  for method_name, action in [
   ("ActionChains", lambda: ActionChains(self.driver).move_to_element(button).pause(0.1).click().perform()),
   ("JS", lambda: self.driver.execute_script("arguments[0].click();", button)),
   ("Native", lambda: button.click())
  ]:
   try:
    action()
    logging.info(f"Клик выполнен ({method_name})")
    return True
   except:
    continue
  return False

 def start_selenium(self):
  options = get_option()
  options.add_argument("--disable-extensions")
  options.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
  self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
  self.driver.get("https://alice.yandex.ru/")
  try:
   WebDriverWait(self.driver, 15).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "button.AliceButton_pin_circle"))
   )
  except:
   logging.warning("Не дождались кнопки микрофона, но продолжаем")
  time.sleep(1)

 def run(self):
  self.start_selenium()
  time.sleep(1)
  self.toggle()  # автоматический старт записи

  def start_mouse_listener_with_delay():
   """Функция для запуска слушателя мыши через 10 секунд в отдельном потоке"""
   time.sleep(10)

   def on_click(x, y, button, pressed):
    # Нам нужен клик левой кнопкой (нажатие)
    if button == mouse.Button.left and pressed:
     # Сигнал должен быть испущен в потоке слушателя,
     self.stop_request.emit()

   # Запускаем слушатель в демоническом потоке, чтобы он не блокировал завершение
   listener = mouse.Listener(on_click=on_click)
   listener.daemon = True
   listener.start()
   logging.info("Глобальный слушатель мыши активирован через 10 секунд (клик левой кнопкой останавливает запись)")

   # Запускаем функцию в отдельном потоке

  listener_thread = threading.Thread(target=start_mouse_listener_with_delay, daemon=True)
  listener_thread.start()

  while self._running:
   time.sleep(0.5)

 def toggle(self):
  if not self.recording:
   button = self.find_mic_button()
   if button and self.click_element(button):
    self.recording = True
    self.icon_signal.emit(self.icon_stop)
    self.status_signal.emit("Внимательно вас слушаю")
   else:
    logging.error("Не удалось включить микрофон")
  else:
   logging.info("⏹️ Остановка записи...")
   button = self.find_stop_button()
   if button and self.click_element(button):
    time.sleep(2.5)
    text = self.get_recognized_text()
    self.clear_input_field()
    if text:
     thread = threading.Thread(target=process_text, args=(text,))
     thread.start()
     thread.join()
   self.recording = False
   self.icon_signal.emit(self.icon_mic)

 def stop(self):
  self._running = False
  if self.driver:
   try:
    self.driver.quit()
   except:
    pass

class MyWindow(QWidget):
 def __init__(self):
  super().__init__()
  BASE_PATH = os.path.dirname(os.path.abspath(__file__))
  self.icon_mic = os.path.join(BASE_PATH, "voice.png")
  self.icon_stop = os.path.join(BASE_PATH, "stop.png")
  self.thread = VoiceThread(self.icon_mic, self.icon_stop)
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

 def tray_clicked(self, reason):
  if reason == QSystemTrayIcon.ActivationReason.Trigger:
   self.thread.toggle()

 def change_icon(self, path):
  self.tray.setIcon(QIcon(path))

 def update_tooltip(self, text):
  self.tray.setToolTip(f"Голосовой ввод Алиса — {text}")

 def quit_app(self):
  self.thread.stop()
  self.thread.wait(3000)
  QApplication.quit()


if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 sys.exit(app.exec())
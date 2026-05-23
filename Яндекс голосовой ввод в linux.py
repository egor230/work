from pytq_libs_voice import *
from write_text import *
# ====================== НАСТРОЙКИ ======================
# logging.basicConfig(level=logging.INFO, format=' - %(message)s')
def repeat(text1: str):  # text = "linux менч установить линукс минт помоги мне установить "
 text = text1.replace("!", ".")  # .replace(".", "")
 k.save_text(text)
 text1 = ""
 res = k.get_dict()
 k.save_words(res)
 words = k.get_words()  # print(words)
 try:  # Создаем регулярное выражение для всех слов и словосочетаний из словаря
  words_regex = r'\b(' + r'|'.join(map(re.escape, words)) + r')\b'
  # Выполняем замену с учетом регистра
  text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
  k.save_text(text1)
 except Exception as ex:
  print(f"Ошибка: {ex}")  # Выводим ошибку для диагностики
 return text1

def press_keys(text):  # xte 'keyup Shift_L'
 try:  #
  text = repeat(text)
  print(text)
  key_s = '''#!/bin/bash
   xte 'keyup Shift_R'
   sleep 0.1
   xte 'keyup Shift_L'
   xkbset -sticky
   xte "key Num_Lock"
   exit '''  # text="lunix mint"
  # command = 'xte "key Num_Lock"'
  # subprocess.run(command, shell=True)
  char_to_xdotool = {",": "comma", ":": "colon"}  # Без shift, а сам символ
  liters_en = ['a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E', 'f', 'F', 'g', 'G', 'h', 'H', 'i', 'I', 'j', 'J', 'k', 'K', 'l', 'L', 'm', 'M',
               'n', 'N', 'o', 'O', 'p', 'P', 'q', 'Q', 'r', 'R', 's', 'S', 't', 'T', 'u', 'U', 'v', 'V', 'w', 'W', 'x', 'X', 'y', 'Y', 'z', 'Z']  # Диапазон от пробела до тильды (ASCII 32-126)#
  for char in text:
   if char in char_to_xdotool:
    subprocess.run(['bash', '-c', key_s])
    subprocess.call(['xdotool', 'key', char_to_xdotool[char]])
    continue
   if char in liters_en:
    subprocess.call(['xdotool', 'type', '--delay', '3', char])
   else:
    if char.isupper():  # Если символ заглавный
     keyboard.press(char.upper())  # Нажимаем строчную версию символа
     keyboard.release(char.upper())
     # keyboard.release(Key.shift)  # Отпустить Shift
     # subprocess.run(['bash', '-c', key_s])
    else:
     keyboard.press(char)
     keyboard.release(char)
   time.sleep(0.03)  # Уменьшение задержки
  # Включить sticky keys
  subprocess.call(['xkbset', 'sticky'])
 except Exception as ex1:
  print(ex1)
  return

class VoiceThread(QThread):
 icon_signal = pyqtSignal(str)
 status_signal = pyqtSignal(str)
 stop_request = pyqtSignal()
 
 def __init__(self, icon_mic_path, icon_record_path, icon_stop_path, parent=None):
  super().__init__(parent)
  self.icon_mic = icon_mic_path
  self.icon_record = icon_record_path
  self.icon_stop = icon_stop_path
  self._running = True
  self.recording = False
  self.driver = None
  self._lock = threading.Lock()  # защита toggle от гонок
  self.stop_request.connect(self.stop_recording)
 
 def stop_recording(self):
  if self.recording:
   self.toggle()
 
 def find_mic_button(self):
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
 
 def find_stop_button(self):
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
 
 def get_recognized_text(self):
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
 
 def clear_input_field(self):
  try:
   field = WebDriverWait(self.driver, 3).until(
    EC.element_to_be_clickable(
     (By.CSS_SELECTOR, "input[role='textbox'], textarea")
    )
   )
   field.click()
   self.driver.execute_script("arguments[0].value = '';", field)
   self.driver.execute_script("arguments[0].dispatchEvent("
    "new Event('input', {bubbles: true}));", field )
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
  for method_name, action in [ ("ActionChains",  lambda: ActionChains(self.driver)
      .move_to_element(button).pause(0.1).click().perform()),
   ("JS",
    lambda: self.driver.execute_script( "arguments[0].click();", button)),
   ("Native", lambda: button.click()), ]:
   try:
    action()
    return True
   except Exception:
    continue
  return False
 
 def start_selenium(self):
  options = get_option()
  options.add_argument("--disable-extensions")
  options.add_argument( '--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/'
   'linux must have/python_linux/Project/google-chrome' )
  self.driver = webdriver.Chrome(  service=Service(ChromeDriverManager().install()),
   options=options )
  self.driver.get("https://alice.yandex.ru/")
  try:
   WebDriverWait(self.driver, 15).until(
    EC.presence_of_element_located(
     (By.CSS_SELECTOR, "button.AliceButton_pin_circle") )
   )
  except Exception:
   logging.warning("Не дождались кнопки микрофона, но продолжаем")
  time.sleep(1)
 
 def run(self):
  self.start_selenium()
  time.sleep(1)
  self.toggle()
  time.sleep(2.3)  # даём Qt обработать сигнал
  self.icon_signal.emit(self.icon_record)  # принудительно
  
  def start_mouse_listener_with_delay():
   time.sleep(10)
   
   def on_click(x, y, button, pressed):
    if button == mouse.Button.left and pressed:
     self.stop_request.emit()
   
   def on_press(key):
    try:
     key_name = (str(key).replace("'", "")
                 .replace(" ", "").replace("Key.", ""))
     if key_name == "end":
      self.toggle()
    except Exception as e:
     print(f"Ошибка при обработке: {e}")
   
   def start_listener():
    listener = Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    print("Слушатель клавиатуры запущен...")
   
   start_listener()
   m_listener = mouse.Listener(on_click=on_click)
   m_listener.daemon = True
   m_listener.start()
  
  listener_thread = threading.Thread(
   target=start_mouse_listener_with_delay, daemon=True
  )
  listener_thread.start()
  
  while self._running:
   time.sleep(0.5)
 
 def toggle(self):
  # Lock защищает от одновременного вызова из разных потоков
  # with self._lock:
   if not self.recording:
    button = self.find_mic_button()
    self.icon_signal.emit(self.icon_record)
    if button and self.click_element(button):
     self.recording = True
     self.status_signal.emit("Внимательно вас слушаю")
    else:
     logging.error("Не удалось включить микрофон")
   else:
    # === Останавливаем запись ===
    self.icon_signal.emit(self.icon_mic)
    # self.icon_signal.emit(self.icon_stop)   # показываем иконку "стоп"
    self.status_signal.emit("Обработка...")
    button = self.find_stop_button()
    if button and self.click_element(button):
     time.sleep(2.5)
     text = self.get_recognized_text()
     self.clear_input_field()

     if text:
      thread = threading.Thread(target=press_keys, args=(text,))
      thread.start()
      thread.join()
    else:
     logging.warning("Не удалось найти кнопку остановки")

    # === Возвращаем обычную иконку микрофона ===
    self.recording = False
    self.status_signal.emit("Готов")
    # time.sleep(4.5)
    # self.icon_signal.emit(self.icon_mic)
 
 def stop(self):
  self._running = False
  if self.driver:
   try:
    self.driver.quit()
   except Exception:
    pass


class MyWindow(QWidget):
 def __init__(self):
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
 
 def tray_clicked(self, reason):
  if reason == QSystemTrayIcon.ActivationReason.Trigger:
   self.thread.toggle()
 
 def change_icon(self, path):
  self.tray.setIcon(QIcon(path))
  # Самое важное — форсируем обработку событий Qt
  QApplication.processEvents()  # ← это сильно помогает
  # Дополнительный "пинок" для Linux
  # self.tray.hide()
  self.tray.show()
 def update_tooltip(self, text):
  self.tray.setToolTip(f"Голосовой ввод Алиса — {text}")
 
 def quit_app(self):
  self.thread.stop()
  self.thread.wait(3000)
  QApplication.quit()


# ─── Точка входа ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 sys.exit(app.exec())
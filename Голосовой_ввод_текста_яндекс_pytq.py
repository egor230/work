from pytq_libs_voice import *
from write_text import *


class VoiceThread(QThread):
 icon_signal = pyqtSignal(str)
 status_signal = pyqtSignal(str)
 text_signal = pyqtSignal(str, bool)
 mute_signal = pyqtSignal()
 
 def __init__(self, icon_mic_path, icon_record_path, icon_stop_path, parent=None):
  super().__init__(parent)
  self.icon_mic = icon_mic_path
  self.icon_record = icon_record_path
  self.icon_stop = icon_stop_path
  self.mic = True
  self.mode = "auto"
  self.driver = None
  self.OKNYX_CORE_CLASS = "StandaloneOknyxCore"
  self.MIC_BUTTON_CLASS = "StandaloneOknyx"
  self.alisa = "aria-label"
  self.source_id = get_webcam_source_id()
  self.counts = 0
  self._lock = threading.Lock()  # защита toggle от гонок
  self._mode_lock = threading.Lock()  # защита смены режима
  self._stop_recording_flag = False  # флаг для корректной остановки записи
 
 def show_message(self, text, mic):
  self.hint_text = text
  if text:
   self.text_signal.emit(text, mic)
  else:
   self.text_signal.emit(None, mic)
 
 def get_user_message(self, len_c):  # Получение последнего сообщения пользователя из пузырьков.
  try:
   elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='message-bubble-container-from-user']")
   if not elements:
    return "", len_c
   text_selectors = [".MessageBubble-Text"#, ".AliceTextBubble"
    #, ".MessageBubble", ".FuturisTextBubble", ".MarkdownText"
                     ]
   last_user_container = elements[-1]
   message = ""
   for selector in text_selectors:
    try:
     elem = last_user_container.find_element(By.CSS_SELECTOR, selector)
     if elem and elem.text.strip():
      message = elem.text.strip()
      break
    except:
     continue
   if not message:
    try:
     message = last_user_container.text.strip()
    except:
     message = ""
   return (message, len(elements)) if (elements and message) else ("", len_c)
  except:
   return "", len_c
 
 def start_selenium(self):  # Запуск браузера и переход на страницу Алисы."""
  options = get_option()
  options.add_argument("--disable-extensions")
  options.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
  # options.add_argument("--headless=new")
  self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
  # Установить только положительные координаты
  self.driver.set_window_position(0, 378)
  self.driver.set_window_size(532, 467)
  self.driver.get("https://alice.yandex.ru/")  # открыть сайт
  try:
   WebDriverWait(self.driver, 15).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "button.StandaloneOknyx, button.AliceButton_pin_circle"))
   )
  except:
   pass
  self.chrome_pid = self.driver.service.process.pid
  self.window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
  
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
 
 def find_mic_button(self):
  try:
   wait = WebDriverWait(self.driver, 10)
   svg = wait.until(EC.presence_of_element_located(
    (By.CSS_SELECTOR,
     "button.AliceButton_pin_circle.AliceButton_size_m "
     "svg path[d*='M3.374 10']")
   ))
   button = svg.find_element(By.XPATH, "./ancestor::button")
   self.click_element(button)
  except Exception as e:
   # logging.warning(f"Микрофон не найден: {e}")
   pass
   return None
 
 def _OFF(self):
  self.icon_signal.emit(self.icon_mic)
  self.status_signal.emit("Обработка...")
  button = self.find_stop_button()
  if button and self.click_element(button):
   time.sleep(0.3)
   text = self.get_recognized_text()
   if text:
    thread = threading.Thread(target=press_keys, args=(text,))
    thread.start()
    self.clear_input_field()
    thread.join()
 
 def _ON(self):
  if self.mode == "record":
   self.icon_signal.emit(self.icon_record)
   time.sleep(0.82)
   self.find_mic_button()
  
 def talk(self):
  fs = 16 * 1000

  self._ON()
  last_speech_time = time.time()
  try:
   with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
    while not self._stop_recording_flag:
     #time.sleep(2)
     with self._mode_lock:
      if self.mode != "record":
       self._stop_recording_flag = True
       break
     
     audio_chunk, overflowed = stream.read(16096)
     mean_amp = np.mean(np.abs(audio_chunk)) * 100
     mean_amp = math.ceil(mean_amp)
     
     if mean_amp > 4:
      last_speech_time = time.time()
     else:
      if time.time() - last_speech_time > 3.3:
       self._OFF()
       print("Тишина дольше 2.3 сек, остановка записи")
       break

   with self._mode_lock:                 # <-- исправленос
    self._stop_recording_flag = True  # <-- исправлено

   self.icon_signal.emit(self.icon_mic)
   time.sleep(0.82)
  except Exception as e:
   print(f"Ошибка записи: {e}")

 def toggle(self):
  self.first_start = True
  try:
   self.icon_signal.emit(self.icon_record)
   time.sleep(0.82)
   aria_label = self.button.get_attribute(self.alisa) or ""
   oknyx_core = self.button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
   classes = oknyx_core.get_attribute("class") or ""
   print(classes)
   if "li" or "Out" in classes or "сл" in aria_label.lower():
    self.driver.execute_script("arguments[0].click();", self.button)
   self.show_message(None, False)
  except Exception as e:
   pass
  print("0")
  self.talk()
 def run(self):
  self.start_selenium()
  if self.mode == "auto":
   self.button = None
   aria_variants = ["button[data-testid='oknyx']"]  # повторно находим кнопку']
   for selector in aria_variants:
    try:
     self.button = self.driver.find_element(By.CSS_SELECTOR, selector)
     self.button.click()
     break
    except:
     continue
  
  def start_mouse_listener_with_delay():
   def on_press(key):
    try:
     key_name = (str(key).replace("'", "")
                 .replace(" ", "").replace("Key.", ""))
     if key_name == "end":
      with self._mode_lock:  # <-- исправлено
       self._stop_recording_flag = False  # <-- исправлено
      self.toggle()
      time.sleep(0.5)
      return True
    except Exception as e:
     print(f"Ошибка при обработке: {e}")
   
   def start_listener():
    listener = Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
   
   start_listener()
  
  listener_thread = threading.Thread(target=start_mouse_listener_with_delay, daemon=True)
  listener_thread.start()
  self.first_start = True
  
  while True:
   try:
    time.sleep(0.01)
    
    with self._mode_lock:
     current_mode = self.mode
    
    self.mic = get_mute_status(self.source_id)
    if current_mode == "record" and not self._stop_recording_flag:
      print(self._stop_recording_flag)
      print(current_mode)
      self.toggle()
    if current_mode == "auto":
     if not self.button:
      continue
     if self.first_start:
      self.first_start = False #   print("0000")
      self.show_message("Давайте говорите", self.mic)
     if not self.mic:
      self.show_message(None, False)
     else:
      aria_label = self.button.get_attribute(self.alisa) or ""
      oknyx_core = self.button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
      filter_elem = oknyx_core.get_attribute("data-testid") or ""
      classes = oknyx_core.get_attribute("class") or ""
      self.message, counts1 = self.get_user_message(self.counts)
      if "su" in filter_elem or "ex" in classes and "сл" in aria_label.lower():
       # print(classes)
       self.driver.execute_script("arguments[0].click();", self.button)
       # circles = oknyx_core.find_elements(By.CSS_SELECTOR, ".StandaloneOknyxCore-ListeningCircle")
       # is_listening_circles = any(c.value_of_css_property("display") != "none" for c in circles)
       # if "th" in classes and "th" in filter_elem  and "стоп" in aria_label.lower():
       #  print(circles)  is_listening_circles or
      if "lis" in classes and "стоп" in aria_label.lower() and self.message:
       self.show_message(self.message, self.mic)
      if counts1 > self.counts:
       white = oknyx_core.find_element(By.CSS_SELECTOR, ".StandaloneOknyxCore-WhiteCircleWrapper")
       thread = threading.Thread(target=process_text, args=(self.message,))
       if "out" in classes or "col" in classes or "th" in filter_elem or white.value_of_css_property("display") == "none":
        thread.start()
        print(counts1)
        self.counts = counts1
        self.mic = True
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        self.driver.execute_script("arguments[0].click();", self.button)
        time.sleep(2)
        self.driver.execute_script("arguments[0].click();", self.button)
    
   
      # if counts1 > 0:
      #   self.show_message(None, False)
  
   except Exception as e:
    print(f"Ошибка в selenium_worker: {e}")
    pass
 
 def clear_input_field(self):  # Очистка поля ввода."""
  try:
   field = WebDriverWait(self.driver, 3).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "input[role='textbox'], textarea"))
   )
   
   self.driver.execute_script("""
       let el = arguments[0];

       // Если это div-редактор (contenteditable)
       if (el.isContentEditable) {
           el.innerHTML = '';
           el.innerText = '';
           el.dispatchEvent(new Event('input', {bubbles: true}));
       }
       // Если это обычный input или textarea
       else {
           // Фокусируем и выделяем весь текст внутри элемента
           el.focus();
           el.select();

           // Команды на удаление выделенного текста (работает на уровне документа, не ОС)
           document.execCommand('selectAll', false, null);
           document.execCommand('delete', false, null);

           // Физически очищаем свойство value на случай, если фреймворк сопротивляется
           let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set ||
                        Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
           if (setter) setter.call(el, '');
           else el.value = '';

           el.dispatchEvent(new Event('input', {bubbles: true}));
           el.dispatchEvent(new Event('change', {bubbles: true}));
       }
   """, field)
  except Exception as e:
   logging.warning(f"Очистка поля не удалась: {e}")
 
 def get_recognized_text(self):  # Извлечение текущего текста из поля ввода (живое распознавание).
  selectors = [
   (By.CSS_SELECTOR, "input[role='textbox'], textarea[role='textbox']"),
   (By.CSS_SELECTOR, ".StandaloneInput-Field input, .StandaloneInput-Field textarea"),
  ]
  for by, selector in selectors:
   try:
    element = WebDriverWait(self.driver, 2).until(
     EC.presence_of_element_located((by, selector))
    )
    text = (element.get_attribute("value") or element.text or "").strip()
    if len(text) > 0:
     return text
   except Exception:
    continue
  return ""
 
 def click_element(self, button):  # клик по элементу с несколькими способами.
  if not button:
   return False
  for action in [
   lambda: ActionChains(self.driver).move_to_element(button).pause(0.1).click().perform(),
   lambda: self.driver.execute_script("arguments[0].click();", button),
   lambda: button.click()
  ]:
   try:
    action()
    return True
   except Exception:
    continue
  return False

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
  self.thread.text_signal.connect(self._update_label_from_thread)
  self.thread.mute_signal.connect(self.start_mute_timer)
  
  self.tray = QSystemTrayIcon(QIcon(self.icon_mic), self)
  self.tray.setToolTip("Голосовой ввод — Авто")
  menu = QMenu()
  self.action_auto = QAction("Авто", self)
  self.action_auto.setCheckable(True)
  self.action_auto.setChecked(True)
  self.action_auto.triggered.connect(lambda: self.switch_mode("auto"))
  menu.addAction(self.action_auto)
  
  self.action_record = QAction("Запись", self)
  self.action_record.setCheckable(True)
  self.action_record.setChecked(False)
  self.action_record.triggered.connect(lambda: self.switch_mode("record"))
  menu.addAction(self.action_record)
  
  menu.addSeparator()
  quit_act = QAction("Выход", self)
  quit_act.triggered.connect(self.quit_app)
  menu.addAction(quit_act)
  
  self.tray.setContextMenu(menu)
  self.tray.activated.connect(self.tray_clicked)
  self.tray.show()
  
  self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                      Qt.WindowType.WindowStaysOnTopHint |
                      Qt.WindowType.Tool)
  self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
  self.setStyleSheet("background-color: rgba(255, 255, 255, 255); border-radius: 3px;")
  
  layout = QVBoxLayout()
  self.label = QLabel(" ")
  self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  self.label.setFont(QFont("Times", 14))
  self.label.setStyleSheet("color: black;")
  self.label.setWordWrap(False)
  layout.addWidget(self.label)
  self.setLayout(layout)
  
  self.thread.start()
  QTimer.singleShot(0, self.hide)
 
 def switch_mode(self, mode):
  # Блокировка только на время изменения состояния
  with self.thread._mode_lock:
   if self.thread.mode == "record" and mode == "auto":
     self.thread._stop_recording_flag = True
   self.thread.mode = mode

  # ИСПРАВЛЕНО: sleep вынесен из блока блокировки во избежание deadlock-ов
  if mode == "auto" and self.thread._stop_recording_flag:
   time.sleep(0.3)  # даем время завершить запись
  
  set_mute("0", self.thread.source_id)
  
  if mode == "auto":
   self.action_auto.setChecked(True)
   self.action_record.setChecked(False)
   self.tray.setToolTip("Голосовой ввод — Авто")
   self.thread._stop_recording_flag = False
  elif mode == "record":
   self.action_auto.setChecked(False)
   self.action_record.setChecked(True)
   self.tray.setToolTip("Голосовой ввод — Запись")
   self.thread._stop_recording_flag = False
 
 def tray_clicked(self, reason):
  if reason == QSystemTrayIcon.ActivationReason.Trigger:
   if self.thread.mode == "auto":
    if self.thread.mic:
     print("pause")
     self.tray.setToolTip("Голосовой ввод — Пауза")
     set_mute("1", self.thread.source_id)
     self.thread.icon_signal.emit(self.icon_stop)
     self.thread.mic = False
    else:
     print("start")
     set_mute("0", self.thread.source_id)
     self.tray.setToolTip("Запись")
     self.thread.icon_signal.emit(self.icon_mic)
     self.thread.mic = True
   
   # ИСПРАВЛЕНО: для режима record клик по трею переключает запись
   elif self.thread.mode == "record":
    
    with self.thread._mode_lock:
     print("1111111111111111111111")
     self.thread._stop_recording_flag = False
    
 def start_mute_timer(self):
  pass
 
 def _update_label_from_thread(self, text, show):
  try:
   if text and show:
    self.label.setText(text)
    width = max(250, len(text) * 11)
    self.setFixedSize(width, 45)
    self.move(630, 1070)
    self.show()
   else:
    self.hide()
  except Exception as e:
   print(f"UI update error: {e}")
 
 def change_icon(self, path):
  self.tray.setIcon(QIcon(path))
  QApplication.processEvents()
  self.tray.show()
 
 def update_tooltip(self, text):
  self.tray.setToolTip(f"Голосовой ввод — {text}")
 
 def quit_app(self):
  self.thread.stop()
  self.thread.wait(3000)
  QApplication.quit()


if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 sys.exit(app.exec())
 
 # elif not self.recording: # ждем переключения флага или ручного старта
 #  time.sleep(0.6)
 #  # НЕ кликаем кнопку автоматически — ждем toggle() или ручной старт
 #  if not self._stop_recording_flag and self.mode == "record":
 #   # только если явно запустили через toggle
 #   pass
 
 # self.button.click()
 # self.driver.minimize_window() # Окно сворачивается
 # self.button.click()
 # self.driver.minimize_window() # Окно сворачивается
# print("ckick")
# self.button.click()
# self.driver.minimize_window() # Окно сворачивается

# Получить размер окна
# window_size = self.driver.get_window_size()
# print(f"Ширина: {window_size['width']}")
# print(f"Высота: {window_size['height']}")
#
# # Получить позицию окна (координаты левого верхнего угла)
# window_position = self.driver.get_window_position()
# print(f"Позиция X: {window_position['x']}")
# print(f"Позиция Y: {window_position['y']}")
#
# # Или всё вместе в одном словаре
# window_rect = self.driver.get_window_rect()
# print(f"Размер и позиция: {window_rect}")
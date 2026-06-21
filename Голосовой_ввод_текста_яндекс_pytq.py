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
     self._running = True
     self.recording = False  # Флаг: идет ли сейчас запись голоса
     self.mode = "record"#"auto"
     self._prev_mode = "record"#"auto"
     self.driver = None
     self.OKNYX_CORE_CLASS = "StandaloneOknyxCore"
     self.MIC_BUTTON_CLASS = "StandaloneOknyx"
     self.alisa = "aria-label"
     self.source_id = get_webcam_source_id()
     self.counts = 0
     self.driver = None
     self._lock = threading.Lock()  # защита toggle от гонок
     # self.stop_request.connect(self.stop_recording)

 def find_stop_button(self):
     """Поиск кнопки остановки записи (для режима записи)."""
     selectors = [
         (By.CSS_SELECTOR, '.StandaloneRichInput-ControlsPlayer button.AliceButton_view_secondary'),
         (By.CSS_SELECTOR, 'button.AliceButton_view_secondary.AliceButton_square'),
     ]
     wait = WebDriverWait(self.driver, 5)
     for by, sel in selectors:
         try:
             btn = wait.until(EC.element_to_be_clickable((by, sel)))
             return btn
         except Exception:
             continue
     return None

 def get_user_message(self, len_c):
     """Получение последнего сообщения пользователя из пузырьков."""
     try:
         elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='message-bubble-container-from-user']")
         if not elements:
             return "", len_c
         text_selectors = [".MessageBubble-Text", ".AliceTextBubble", ".MessageBubble",
                           ".FuturisTextBubble", ".MarkdownText"]
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

 def clear_input_field(self):
     """Очистка поля ввода."""
     try:
         field = WebDriverWait(self.driver, 3).until(
             EC.element_to_be_clickable((By.CSS_SELECTOR, "input[role='textbox'], textarea"))
         )
         field.click()
         self.driver.execute_script("arguments[0].value = '';", field)
         self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", field)
         # дополнительная очистка на случай, если осталось
         if field.get_attribute("value"):
             field.send_keys(Keys.CONTROL + "a")
             field.send_keys(Keys.DELETE)
     except Exception as e:
         logging.warning(f"Очистка поля не удалась: {e}")

 def get_recognized_text(self):
     """Извлечение текущего текста из поля ввода (живое распознавание)."""
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
 def click_element(self, button):
     """Безопасный клик по элементу с несколькими способами."""
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

 def _is_listening(self, mic_button):
     """Проверяет, слушает ли микрофон (по классам и aria-label)."""
     try:
         aria_label = mic_button.get_attribute(self.alisa) or ""
         try:
             oknyx_core = mic_button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
             classes = oknyx_core.get_attribute("class") or ""
         except:
             classes = mic_button.get_attribute("class") or ""
         return "lis" in classes or "стоп" in aria_label.lower()
     except:
         return False

 def _get_state(self, mic_button):
     """Возвращает (classes, filter_elem) из кнопки микрофона."""
     try:
         oknyx_core = mic_button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
         classes = oknyx_core.get_attribute("class") or ""
         filter_elem = oknyx_core.get_attribute("data-testid") or ""
     except:
         classes = mic_button.get_attribute("class") or ""
         filter_elem = mic_button.get_attribute("data-testid") or ""
     return classes, filter_elem

 def start_selenium(self):
     """Запуск браузера и переход на страницу Алисы."""
     options = get_option()
     options.add_argument("--disable-extensions")
     options.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
     self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
     self.driver.get("https://alice.yandex.ru/")
     try:
         WebDriverWait(self.driver, 15).until(
             EC.presence_of_element_located((By.CSS_SELECTOR, "button.StandaloneOknyx, button.AliceButton_pin_circle"))
         )
     except:
         pass
     # time.sleep(1)
     # try:
     #     elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='message-bubble-container-from-user']")
     #     self.counts = len(elements)
     # except:
     #     self.counts = 0
 
     self.chrome_pid = self.driver.service.process.pid
     
     # Ищем окно по PID и сохраняем в self.window_id
     self.window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
     # subprocess.run(['xdotool', 'windowactivate', '--sync', self.window_id])
     # subprocess.run(['xdotool', 'windowfocus', self.window_id])
     # # Дополнительно через Selenium
     # self.driver.execute_script("window.focus();")
     # subprocess.run(['xdotool', 'windowminimize', self.window_id])
     # try:
     #  WebDriverWait(self.driver, 15).until(
     #   EC.presence_of_element_located(
     #    (By.CSS_SELECTOR, "button.AliceButton_pin_circle"))
     #  )
     # except Exception:
     #  logging.warning("Не дождались кнопки микрофона, но продолжаем")
     # time.sleep(1)
 def stop_recording(self):  # Останавливает запись, если она активна (вызывается извне)
  if self.recording:
   self.toggle()
 
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
 def find_mic_button(self):  # Поиск кнопки микрофона на странице Яндекса
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
    logging.warning(f"Микрофон не найден: {e}")
    return None

 def _OFF(self):  # Остановка записи: нажать кнопку стоп, получить текст, очистить поле, отправить текст
  self.icon_signal.emit(self.icon_mic)
  self.status_signal.emit("Обработка...")
  button = self.find_stop_button()
  if button and self.click_element(button):
   text = self.get_recognized_text()
   if text:  # Запускаем эмуляцию ввода в отдельном потоке, чтобы не блокировать GUI
    thread = threading.Thread(target=press_keys, args=(text,))
    thread.start()
    self.clear_input_field()  # Получаем PID браузера от Selenium
    thread.join()

 def _ON(self):
  if self.mode == "record":
   self.icon_signal.emit(self.icon_record)
   self.find_mic_button()
  
 def toggle(self):  # Переключение состояния записи (вкл/выкл)
  if self.mode == "record":
   if self.recording:
    print("recod")
    self._ON()
   # else:
   #  self._OFF()
 def run(self):
  self.start_selenium()
  set_mute("0", self.source_id)
  self._prev_mode = self.mode
  fs = 16 * 1000  # Настройка аудиопотока с микрофона
  if self.mode == "record":
   self._ON()
  
  # Запускаем глобальные слушатели клавиатуры и мыши (для остановки по End)
  def start_mouse_listener_with_delay():  # time.sleep(10)
   def on_press(key):
    try:
     key_name = (str(key).replace("'", "")
                 .replace(" ", "").replace("Key.", ""))
     if key_name == "end":
      self.toggle()  # Остановить/запустить запись по клавише End
      time.sleep(3)
      return True
    except Exception as e:
     print(f"Ошибка при обработке: {e}")
   
   def start_listener():
    listener = Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    # print("Слушатель клавиатуры запущен...")
   start_listener()
  
  listener_thread = threading.Thread(  target=start_mouse_listener_with_delay, daemon=True
  )
  listener_thread.start()
  try:
   while 1:
    time.sleep(2)
    print(self.mode)
    if self.mode == "record" and not self.recording:       # === РЕЖИМ ЗАПИСЬ ===
      self.recording = True
      last_speech_time = time.time()  # Обновляем время последней речи
      with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
        while self.recording:  # <--- условие
         audio_chunk, overflowed = stream.read(16096)
         mean_amp = np.mean(np.abs(audio_chunk)) * 100
         mean_amp = math.ceil(mean_amp)
         if mean_amp > 4:
          last_speech_time = time.time()
         else:
          if time.time() - last_speech_time > 3.3:
           self._OFF()
           # self.recording = False  # <--- сбрасываем флаг
           print("Тишина дольше 3 секунд, остановка записи")
           break  # выходим из while
           break  # выходим из while
    if self.mode == "auto":
     print("auto")

  except Exception as e:
   print(f"Ошибка в selenium_worker: {e}")

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
     self.action_auto.triggered.connect(lambda: self.switch_mode("record"))
     menu.addAction(self.action_auto)

     self.action_record = QAction("record", self)
     self.action_record.setCheckable(True)
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
        self.action_auto.setChecked(mode == "auto")
        self.action_record.setChecked(mode == "record")
        self.thread.mode = mode
        set_mute("0", self.thread.source_id)
        if mode == "auto":
            self.tray.setToolTip("Голосовой ввод — Авто")
        elif mode == "record":
            self.tray.setToolTip("Голосовой ввод — Запись")

    def start_mute_timer(self):
        # Заглушка (можно реализовать задержку для отключения микрофона)
        pass

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
         if self.thread.mode == "auto":
          print(self.thread.mode)
         #     self.thread.mode = "paused"
         #     self.tray.setToolTip("Голосовой ввод — Пауза")
         #     # set_mute("1", self.thread.source_id)
         # elif self.thread.mode == "paused":
         #     self.thread.mode = "auto"
         #     # set_mute("0", self.thread.source_id)  # раскомментировать при необходимости
        if self.thread.mode == "record":
          print(self.thread.mode)
        if self.thread.mode == "record" and self.thread.recording:
          print(self.thread.recording)
          self.thread._ON()
#             self.switch_mode("auto")

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
    
    

    #  exit(0)
    # def stop(self):
    #  self._running = False
    #  if self.driver:
    #   try:
    #    self.driver.quit()
    #   except:
    #    pass

   # после with поток закрывается автоматически
    # === РЕЖИМ АВТО ===
    # elif self.mode == "auto":
    #
    #  # === Обработка смены режима (пауза) ===
    #  if self._prev_mode == "paused" and self.mode != "paused":
    #   mic_btn = self.find_mic_button()
    #   if mic_btn:
    #    self.click_element(mic_btn)
    #    time.sleep(0.5)
    #   self._prev_mode = self.mode
    #  # === Включение микрофона, если не слушает ===
    #  if not self._is_listening(mic_button):
    #   if self.mode == "paused":
    #    self.text_signal.emit(None, False)
    #    time.sleep(1.0)
    #    continue
    #   self.click_element(mic_button)
    #   time.sleep(0.8)
    #   continue
    #
    #  # === Режим ПАУЗА ===
    #  if self.mode == "paused":
    #   if self._is_listening(mic_button):
    #    self.click_element(mic_button)
    #   self.text_signal.emit(None, False)
    #   time.sleep(1.0)
    #   continue
    #
    #  # === Получение текущего состояния ===
    #  message, counts1 = self.get_user_message(self.counts)
    #  classes, filter_elem = self._get_state(mic_button)
    #  self.text_signal.emit(message if message else "Слушаю...", True)
    #  if counts1 > self.counts:
    #   if "out" in classes or "col" in classes or "th" in filter_elem:
    #    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    #    message, counts1 = self.get_user_message(self.counts)
    #    print(counts1)
    #    self.counts = counts1
    #    threading.Thread(target=process_text, args=(message,)).start()
    #    self.clear_input_field()
    #    self.mute_signal.emit()
    #
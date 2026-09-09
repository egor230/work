# from pytq_libs_voice import *
# from write_text import *
from write_text_fast import *
import threading
import time
from selenium.webdriver.common.by import By

def dom_classes_tracker(driver, interval_sec=0.5, label="classes"):
  """
  Отслеживает ИСКЛЮЧИТЕЛЬНО изменения классов у элементов DOM.
  Запускается в отдельном потоке.
  """
  _prev = None
  _call = 0
  
  def _snap():
   curr = {}
   try:
    all_elems = driver.find_elements(By.CSS_SELECTOR, "*")
    for idx, el in enumerate(all_elems):
     try:
      tag = el.tag_name
      eid = el.get_attribute("id") or ""
      cls = el.get_attribute("class") or ""
      testid = el.get_attribute("data-testid") or ""
      aria = el.get_attribute("aria-label") or ""
      
      if not (eid or cls or testid or aria):
       continue
      
      # Ключ НЕ должен содержать class, иначе смена класса считается за удаление/появление
      key = f"{tag}|id={eid}|testid={testid}|aria={aria[:20]}|idx={idx}"
      curr[key] = {
       "tag": tag,
       "id": eid,
       "classes": cls,
       "testid": testid,
       "aria": aria
      }
     except Exception:
      continue
   except Exception as e:
    print(f"[DOM] Ошибка снимка: {e}")
   return curr
  
  def _print_class_diff(n, prev, curr):
   modified_classes = []
   
   for k in curr:
    if k in prev:
     old_cls = prev[k]["classes"]
     new_cls = curr[k]["classes"]
     
     if old_cls != new_cls:
      old_set = set(old_cls.split())
      new_set = set(new_cls.split())
      added = sorted(list(new_set - old_set))
      removed = sorted(list(old_set - new_set))
      
      if added or removed:
       modified_classes.append((curr[k], added, removed, old_cls, new_cls))
   
   if not modified_classes:
    return False
   
   print(f"\n{'=' * 60}")
   print(f"[DOM #{n} | {label}] ИЗМЕНЕНИЯ КЛАССОВ ({len(modified_classes)}):")
   print(f"{'=' * 60}")
   
   for elem, added, removed, old_c, new_c in modified_classes[:20]:
    info = []
    if elem['id']:
     info.append(f"id='{elem['id']}'")
    if elem['testid']:
     info.append(f"testid='{elem['testid']}'")
    info_str = f" ({' '.join(info)})" if info else ""
    
    print(f"\n  [~] {elem['tag']}{info_str}")
    if added:
     print(f"      + Добавлены: {added}")
    if removed:
     print(f"      - Удалены:   {removed}")
    print(f"      было:  '{old_c[:60]}'")
    print(f"      стало: '{new_c[:60]}'")
   
   if len(modified_classes) > 20:
    print(f"\n  ... и ещё {len(modified_classes) - 20} элементов с изменившимися классами")
   return True
  
  print(f"[DOM] Трекер классов запущен, интервал={interval_sec}сек")
  while True:
   try:
    curr = _snap()
    _call += 1
    if _prev is None:
     _prev = curr
     print(f"[DOM #{_call}] БАЗА КЛАССОВ: {len(curr)} элементов")
    else:
     _print_class_diff(_call, _prev, curr)
     _prev = curr
   except Exception as e:
    print(f"[DOM] Ошибка цикла: {e}")
   
   time.sleep(interval_sec)
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
 
 def _chrome_version(self):
   import subprocess as _sp, re as _re
   for cmd in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
    try:
     out = _sp.run([cmd, "--version"], capture_output=True, text=True, timeout=10).stdout
     m = _re.search(r'(\d+\.\d+\.\d+\.\d+)', out)
     if m:
      return [int(x) for x in m.group(1).split(".")]
    except Exception:
     continue
   return None

 def get_chromedriver_path(self):
   import glob as _glob, re as _re, os as _os
   def _ver(p):
    m = _re.search(r'(\d+\.\d+\.\d+\.\d+)', p)
    return [int(x) for x in m.group(1).split(".")] if m else None
   found = []
   for pat in (
    _os.path.expanduser("~/.wdm/drivers/chromedriver/linux64/*/chromedriver-linux64/chromedriver"),
   ):
    for path in _glob.glob(pat):
     if _os.access(path, _os.X_OK):
      v = _ver(path)
      if v:
       found.append((v, path))
   if not found:
    return None, []
   chrome_ver = self._chrome_version()
   exact = None
   if chrome_ver and len(chrome_ver) >= 3:
    for v, p in found:
     if v[:3] == chrome_ver[:3]:
      exact = p
      break
   if exact:
    return exact, [exact]
   found.sort(key=lambda t: t[0], reverse=True)
   return found[0][1], [p for _, p in found]

 def start_selenium(self):  # Запуск браузера и переход на страницу Алисы."""
   options = get_option()
   options.add_argument("--disable-extensions")
   options.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
   # options.add_argument("--headless=new")

   options.add_argument("--no-proxy-server")
   driver_path, candidates = self.get_chromedriver_path()
   last_err = None
   for path in (candidates or []):
    try:
     self.driver = webdriver.Chrome(service=Service(path), options=options)
     print(f"Chrome запущен с локальным драйвером: {path}")
     break
    except Exception as e:
     last_err = e
     print(f"Не удалось запустить Chrome с драйвером {path}: {e}")
   if self.driver is None:
    if candidates:
     print("Все локальные драйверы не подошли — пытаюсь скачать свежий (нужна сеть)...")
    else:
     print("Локальный chromedriver не найден — пытаюсь скачать (нужна сеть)...")
    try:
     import concurrent.futures as _cf
     with _cf.ThreadPoolExecutor(max_workers=1) as ex:
      path = ex.submit(lambda: ChromeDriverManager().install()).result(timeout=120)
     self.driver = webdriver.Chrome(service=Service(path), options=options)
    except Exception as e:
     print(f"Не удалось получить chromedriver: {e}")
     if last_err:
      raise last_err
     raise
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
  
  def _hotkey_evdev_listener(self):
   """Горячая клавиша End через evdev (БЕЗ pynput/X-захвата!).
   Читает /dev/input/event* напрямую, поэтому не блокирует клавиатуру
   даже при краше скрипта. End запускает toggle()."""
   import evdev as _evdev

   def _find_kbs():
    _list = []
    import glob as _g
    for path in _g.glob("/dev/input/event*"):
     try:
      dev = _evdev.InputDevice(path)
      name = (dev.name or "").lower()
      if ("keyboard" in name or "logitech" in name or "at translate" in name) \
         and "smart" not in name and "mouse setting" not in name:
       _list.append(dev)
     except Exception:
      continue
    return _list

   devs = _find_kbs()
   while True:
    try:
     for dev in devs:
      try:
       for event in dev.read():
        if event.type == _evdev.ecodes.EV_KEY and event.code == _evdev.ecodes.KEY_END \
           and event.value == 1:
         with self._mode_lock:
          self._stop_recording_flag = False
         self.toggle()
         time.sleep(0.5)
      except OSError:
       devs = _find_kbs() or devs
       time.sleep(0.2)
      except Exception:
       pass
    except Exception:
     pass
    time.sleep(0.001)

   listener_thread = threading.Thread(target=self._hotkey_evdev_listener, daemon=True)
   listener_thread.start()
  self.first_start = True
  classes1=""
  # threading.Thread(target=dom_classes_tracker, args=(self.driver, 0.9), daemon=True).start()
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
      oknyx_core = self.button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
      aria_label = self.button.get_attribute(self.alisa) or ""
      filter_elem = oknyx_core.get_attribute("data-testid") or ""
      classes = oknyx_core.get_attribute("class") or ""
      # textarea = textarea_elem.get_attribute("class") or ""
      # print(textarea)
      self.message, counts1 = self.get_user_message(self.counts)
      if classes1 != classes:
       classes1=classes
       # print(classes)
       circles = oknyx_core.find_elements(By.CSS_SELECTOR, ".StandaloneOknyxCore-ListeningCircle")
       circles1 = any(c.value_of_css_property("display") != "none" for c in circles)
       
      if "spe" in filter_elem and "th" in classes  and circles1:# and "стоп" in aria_label and "th" in classes:
       self.driver.execute_script("arguments[0].click();", self.button)
       time.sleep(3)
      if "su" in filter_elem or "ex" in classes and "сл" in aria_label.lower():
       self.driver.execute_script("arguments[0].click();", self.button)
      if "lis" in classes and "стоп" in aria_label.lower() and self.message:
       self.show_message(self.message, self.mic)
      if counts1 > self.counts:
       white = oknyx_core.find_element(By.CSS_SELECTOR, ".StandaloneOknyxCore-WhiteCircleWrapper")
       thread = threading.Thread(target=process_text, args=(self.message,))

       if "out" in classes or "col" in classes or "сл" in aria_label.lower() or "th" in filter_elem or white.value_of_css_property("display") == "none":
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
   # Пример проверки окончательной готовности текста
   # is_listening = "StandaloneOknyxCore_animation_listening" in lottie_elem.get_attribute("class")
   # glow_visible = glow_elem.is_displayed()
   #
   # if not is_listening and not glow_visible:
   #  print(self.message)
   #  pass
   except Exception as e:
    # print(f"Ошибка в selenium_worker: {e}")
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
           // // // el.focus();
           // el.select();

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
 
 # circles = oknyx_core.find_elements(By.CSS_SELECTOR, ".StandaloneOknyxCore-ListeningCircle")
 # is_listening_circles = any(c.value_of_css_property("display") != "none" for c in circles)
 # if "th" in classes and "th" in filter_elem  and "стоп" in aria_label.lower():
 #  print(circles)  is_listening_circles or
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
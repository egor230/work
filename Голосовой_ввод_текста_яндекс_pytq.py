from pytq_libs_voice import *
from write_text import *
# os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
source_id = get_webcam_source_id()      # ← твоя функция
set_mute("0", source_id)
class MyThread(QtCore.QThread):
 text_signal = QtCore.pyqtSignal(str, bool)
 icon_signal = QtCore.pyqtSignal(str)
 init_ui_signal = QtCore.pyqtSignal()
 
 def __init__(self, parent=None):
  super(MyThread, self).__init__(parent)
  self.parent = parent
  self.mic = True
  self._running = True
  self.label = getattr(parent, "label", None)
  self.url = None
  self.driver = None
  self.counts = 0
  self.message = ""
  self.button = None
  self.hint_text = None
  self.DATA_TESTID_ATTR = "data-testid"
  self.OKNYX_CORE_CLASS = "StandaloneOknyxCore"
  self.MIC_BUTTON_CLASS = "StandaloneOknyx"
  self.alisa = "aria-label"
  self.chat_list = ".ChatListGroup-List .ChatListItem"
  self.chat_list_more = ".ChatListItem-Button_more"
  self.stream = ".AliceChat-StreamingPlaceholder"
  self.ready= "AliceChat-Thinking"

 def is_text_stable(self, timeout=8):  # Укоротил таймаут, добавил ретраи
  try:
    print("is_text_stable")
    while 1:
     time.sleep(timeout)
     initial_text = self.driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
     print(initial_text)
     if "Message:" in initial_text:
       break
     time.sleep(timeout)
     final_text = self.driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
     print(final_text)
     if initial_text != final_text:
        continue
     else:
        # print(f"Текст стабилен после {attempt + 1} попытки: {initial_text}")  # Дебаг
      break
    return True
  except:
      # print(f"Попытка {attempt + 1} стабильности failed, продолжаем...")  # Дебаг
      time.sleep(0.5)
   # print("Текст не стабилен после всех ретраев, берём как есть")  # Дебаг
      return False

 def get_user_messages(self):
  try:
    user_m = WebDriverWait(self.driver, 3).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".MessageBubble-Container_from-user")))
    if user_m:
      last_user_container = user_m[-1]
      message = last_user_container.find_element(By.CSS_SELECTOR, ".MessageBubble").text.strip()
      if message:
        counts = len(user_m)
        return message, counts
    return "", 0
  except Exception as ex:
    print(ex)
    return "", 0
  except Exception as ex:
   print(ex)
   return "", 0

 def update_mic_state(self, mic):
  self.mic = mic
 
 def stop(self):
  self._running = False
 
 def show_message(self, text, mic):
  self.hint_text = text
  if text:
   self.text_signal.emit(text, mic)
  else:
   self.text_signal.emit(None, mic)
 def start_selenium(self):
  try:
   option = get_option()
   # service = Service("/usr/local/bin/chromedriver")  # Указываем путь к chromedriver (если не в PATH, укажите явно)
   # self.driver = webdriver.Chrome(service=service, options=option) # Инициализация драйвера
   self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
   self.driver.get("https://alice.yandex.ru/chat/01938823-14ea-4000-bd7a-3cca57830d6a/")
   self.url = self.driver.current_url
   self.driver.refresh()
   # Ожидание полной загрузки DOM
   WebDriverWait(self.driver, 5).until( lambda d: d.execute_script("return document.readyState") == "complete"  )
   html_content = self.driver.page_source
   #time.sleep(2)  # Пауза для JS-обновлений
   # with open('page_source.txt', 'w', encoding='utf-8') as file:
   #   file.write(html_content)
   self.driver.implicitly_wait(1)
   selenium_thread = threading.Thread(target=self.selenium_worker, daemon=True)
   selenium_thread.start()
   self.del_all_chats(self.driver, self.chat_list, self.chat_list_more)  # Находим все чаты
   new_chat_button = WebDriverWait(self.driver, 5).until( EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Новый чат')]")) )
   self.button = self.driver.find_element(By.CSS_SELECTOR, 'button.StandaloneOknyx[aria-label="Алиса, начни слушать"]')
   self.init_ui_signal.emit()
   self.show_message("Давай поговорите", self.mic)
   self.button.click()
   self.driver.minimize_window()
  except Exception as e:
   # print(e)
   pass
 def del_all_chats(self, driver, chat_list, chat_list_more):
  try:
   WebDriverWait(driver, 2).until(  EC.presence_of_element_located((By.CSS_SELECTOR, chat_list))  )
   while True:
    chats = driver.find_elements(By.CSS_SELECTOR, chat_list)#    print(f"Найдено чатов: {len(chats)}")
    if len(chats) <= 1:
     break
    target_chat = chats[0] # Выбираем первый чат (индекс 0)
    more_button = target_chat.find_element(By.CSS_SELECTOR, chat_list_more)
    
    # Прокручиваем кнопку в видимую область
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_button)
    time.sleep(1.3)
    more_button.click()
    
    # Ждём появления кнопки "Удалить" и кликаем
    delete_button = WebDriverWait(driver, 7).until( EC.element_to_be_clickable((
     By.XPATH, "//div[@role='button' and contains(@class, 'ContextMenuItem')]"
     "[.//span[@class='ContextMenuItem-Text' and text()='Удалить']]"  )) )
    driver.execute_script("arguments[0].click();", delete_button)  # Ждём, пока чат исчезнет из DOM
    WebDriverWait(driver, 7).until(EC.staleness_of(target_chat))
    time.sleep(1.3)  # Дополнительная пауза для стабильности
  
  except Exception as e:
   print(f"Неожиданная ошибка: {e}")
   pass

 def get_latest_message(self, len_c=0):
  try:
   self.driver.execute_script( "window.scrollTo(0, document.body.scrollHeight);")  # filter_elem = WebDriverWait(driver, 1).until( EC.presence_of_element_located((By.CSS_SELECTOR, ".yamb-oknyx-lottie.svelte-rdfi3w"))).get_attribute("data-testid")
   # aria_label= mic_button.get_attribute('aria-label')  # Ожидание наличия элемента на странице
   element = WebDriverWait(self.driver, 4).until(
    EC.visibility_of_all_elements_located((By.CLASS_NAME, self.ready)) )
   #element = self.driver.find_element(By.CLASS_NAME, self.ready)
   if element:  # Проверка видимости элемента
    # time.sleep(3)

    message, counts = self.get_user_messages()  # button.click()
    return message, counts
   else:
    self.is_text_stable()
    print("0300")
    message, counts = self.get_user_messages()  # button.click()
    return message, counts
  except Exception as ex:
   # print(ex)
   # self.is_text_stable()
   # message, counts = self.get_user_messages()  # button.click()
   # return message, counts
   return "", len_c  # Возврат по умолчанию, если ни одно условие не выполнилось    # pass       #

 def selenium_worker(self):
  while self._running:
   try:
    if not self.mic:
     self.show_message(None, False)  # скрыт
    else:
      mic_button = self.driver.find_element(By.CSS_SELECTOR, f".{self.MIC_BUTTON_CLASS}")
      oknyx_core = mic_button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
      aria_label = mic_button.get_attribute(f"{self.alisa}")
      user_m = self.driver.find_elements(By.CSS_SELECTOR, ".MessageBubble-Container_from-user")
      if user_m:
       last_user_container = user_m[-1]
       message = last_user_container.find_element(By.CSS_SELECTOR, ".MessageBubble").text.strip()
       filter_elem = oknyx_core.get_attribute(self.DATA_TESTID_ATTR)
       classes = self.driver.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}").get_attribute("class")
       if "lis" in classes and "thinking" not in classes and "стоп" in aria_label and "standby" not in classes:
        self.show_message(message, self.mic)
       else:
        self.show_message(None, False)#скрыт
        if "think" in classes and "стоп" in aria_label:
         # print(aria_label)
         # print(classes)
         time.sleep(3)
         # self.button.click()
         time.sleep(2)
         self.button.click()
    pass
   except Exception as e:#    print(e)
    pass
 
 def run(self):
  self.start_selenium()
  while self._running:
   try:
    time.sleep(1)
    aria_label = self.button.get_attribute(self.alisa)
    oknyx_core = self.button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
    filter_elem = oknyx_core.get_attribute(self.DATA_TESTID_ATTR)
    if self.mic and "слу" in aria_label and ("su" in filter_elem):
     self.button.click()
     time.sleep(1)

    self.message, counts1 = self.get_latest_message(self.counts)
    if counts1 > self.counts and self.mic and self.message and not any(phrase in self.message for phrase in excluded_phrases):
     self.counts =self.counts+1# self.counts1
     self.mic = False
     thread = threading.Thread(target=process_text, args=(self.message, ))
     thread.start()
     thread.join()
     thr = threading.Thread(target=lambda: [time.sleep(3.7), setattr(self, 'mic', True)])
     thr.daemon = True
     thr.start()
     print(counts1)
     time.sleep(3.7)
    if counts1 ==0:
     self.counts = counts1
    pass
   except Exception as ex1:
    pass

class MyWindow(QtWidgets.QWidget):
 def __init__(self, parent=None):
  super(MyWindow, self).__init__(parent)
  self.mic = True
  self.mythread = MyThread(parent=self)

  BASE_PATH = os.path.dirname(os.path.abspath(__file__))
  self.icon1_path = os.path.join(BASE_PATH, "stop.png")
  self.icon2_path = os.path.join(BASE_PATH, "voice.png")
  self.tray_icon = QSystemTrayIcon(QtGui.QIcon(self.icon2_path), self)
  
  menu = QMenu()
  quit_action = QAction("Quit", self)
  quit_action.triggered.connect(self.quit_t)
  menu.addAction(quit_action)
  
  self.mythread.text_signal.connect(self._update_label_from_thread)
  self.mythread.icon_signal.connect(self.change_icon)
  
  self.tray_icon.setContextMenu(menu)
  self.tray_icon.setToolTip("OFF")
  self.tray_icon.activated.connect(self.on_tray_icon_activated)
  self.tray_icon.show()
  self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
  self.setAttribute(Qt.WA_TranslucentBackground)
  self.setStyleSheet("background-color: rgba(255, 255, 255, 255); border-radius: 3px;")
  self.mythread.init_ui_signal.connect(self.QL)
  self.mythread.start()
  QTimer.singleShot(0, self.hide)
 def QL(self):
  layout = QVBoxLayout()
  self.label = QLabel(" ")
  self.label.setAlignment(Qt.AlignCenter)
  self.label.setFont(QFont("Times", 14))
  self.label.setStyleSheet("color: black;")
  self.label.setWordWrap(False)
  layout.addWidget(self.label)
  self.setLayout(layout)
 
 def _update_label_from_thread(self, text, mic):
  try:
   if text and mic:
    self.label.setText(text)
    width = max(250, len(text) * 11)
    height = 45
    self.setFixedSize(width, height)
    self.move(630, 1070)
    self.show()
   else:
    self.hide()
  except Exception as e:
   print(f"UI update error: {e}")
 
 def change_icon(self, icon_path):
  try:
   self.tray_icon.setIcon(QtGui.QIcon(icon_path))
   self.tray_icon.show()
  except Exception as e:
   print(f"change_icon error: {e}")

 def on_tray_icon_activated(self):
  try:
   self.mic = not getattr(self, "mic", True)
   self.tray_icon.setToolTip("ON" if self.mic else "OFF")
   set_mute("0" if self.mic else "1", source_id)
   self.tray_icon.show()
   self.mythread.icon_signal.emit(self.icon2_path if self.mic else self.icon1_path)
   self.mythread.update_mic_state(self.mic)
   if self.mic:
    self.show()
   else:
    self.hide()
  except Exception as e:
   print(f"Error in on_tray_icon_activated: {e}")
 
 def quit_t(self):
  try:
   self.mythread.stop()
   self.mythread.quit()
   self.mythread.wait(2000)
  except Exception:
   pass
  QApplication.quit()

if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 window.show()
 sys.exit(app.exec_())
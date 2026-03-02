from pytq_libs_voice import *
from write_text import *
import json, os, pyautogui, subprocess, sys, time, threading
from datetime import datetime

# PyQt6 импорты
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QMouseEvent, QFont, QIcon, QAction
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QSystemTrayIcon, QMenu

source_id = get_webcam_source_id()
set_mute("0", source_id)


class MyThread(QThread):
 text_signal = pyqtSignal(str, bool)
 icon_signal = pyqtSignal(str)
 init_ui_signal = pyqtSignal()

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
  self.stream = "AliceChat-StreamingPlaceholder"
  self.ready = "AliceChat-Thinking"

 def is_text_stable(self, timeout=4):
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
     break
   return True
  except:
   time.sleep(0.5)
   return False

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
   self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
   self.driver.get("https://alice.yandex.ru/")

   # keyboard = Controller()  # Если не планируешь сам нажимать кнопки кодом, это не нужно

   def get_elements_data():
    try:
     # Получаем исходный код страницы в момент нажатия
     html_content = self.driver.page_source
     print(html_content)
     # Здесь можно добавить логику парсинга html_content
    except Exception as e:
     print(f"Ошибка при чтении страницы: {e}")

   def on_press(key):
    try:
     # Проверка через атрибуты pynput более надежна в Linux
     if key == Key.alt_l:
      print("Нажат левый Alt")
      get_elements_data()
      pass
    except Exception as e:
     print(f"Ошибка в обработчике: {e}")

   def start_listener():
    # Используем демон-поток, чтобы листенер не мешал завершению программы
    listener = Listener(on_press=on_press)
    listener.daemon = True
    listener.start()

   start_listener()

   selenium_thread = threading.Thread(target=self.selenium_worker, daemon=True)
   selenium_thread.start()

   self.del_all_chats(self.driver, self.chat_list, self.chat_list_more)

   try:
    new_chat_button = WebDriverWait(self.driver, 5).until(
     EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Новый чат')]")))
    new_chat_button.click()
    time.sleep(1)
   except Exception as e:
    print(f"Кнопка 'Новый чат' не найдена: {e}")
    self.driver.get("https://alice.yandex.ru/chat/")

   self.button = self.driver.find_element(
    By.CSS_SELECTOR, 'button.StandaloneOknyx[aria-label="Алиса, начни слушать"]')

   self.init_ui_signal.emit()
   self.show_message("Давай поговорите", self.mic)
   self.button.click()
   # self.driver.minimize_window()
  except Exception as e:
   print(f"Ошибка в start_selenium: {e}")
   pass

 def del_all_chats(self, driver, chat_list, chat_list_more):
  """Удаляет все чаты через JavaScript"""
  try:
   WebDriverWait(driver, 2).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, chat_list)))

   while True:
    chats = driver.find_elements(By.CSS_SELECTOR, chat_list)
    if len(chats) <= 1:
     break

    target_chat = chats[0]

    # Показываем ControlsWrapper и кликаем more через JavaScript
    driver.execute_script("""
     var chat = arguments[0];
     var controlsWrapper = chat.querySelector('.ChatListItem-ControlsWrapper');
     if (controlsWrapper) {
      controlsWrapper.style.opacity = '1';
      controlsWrapper.style.pointerEvents = 'auto';
     }
     var moreBtn = chat.querySelector('.ChatListItem-Button_more');
     if (moreBtn) moreBtn.click();
    """, target_chat)
    time.sleep(0.3)

    # Кликаем "Удалить" - ищем по тексту
    delete_button = WebDriverWait(driver, 5).until(
     EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Удалить')]")))

    driver.execute_script("arguments[0].click();", delete_button)
    WebDriverWait(driver, 5).until(EC.staleness_of(target_chat))
    time.sleep(0.3)

  except Exception as e:
   print(f"Ошибка удаления чатов: {e}")

 def selenium_worker(self):
  """Отслеживает состояние и нажимает кнопку когда Алиса думает"""
  while self._running:
   try:
    if not self.mic:
     self.show_message(None, False)
    else:
     mic_button = self.driver.find_element(By.CSS_SELECTOR, f".{self.MIC_BUTTON_CLASS}")
     oknyx_core = mic_button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
     aria_label = mic_button.get_attribute(f"{self.alisa}")
     classes = oknyx_core.get_attribute("class")
     user_m = self.driver.find_elements(By.CSS_SELECTOR, ".MessageBubble-Container_from-user")
     if user_m:
      last_user_container = user_m[-1]
      message = last_user_container.find_element(By.CSS_SELECTOR, ".MessageBubble").text.strip()
      # Показываем сообщение когда слушаем
      if "lis" in classes  and "стоп" in aria_label and "standby" not in classes:
       time.sleep(1)
       self.show_message(message, self.mic)
      else:
       self.show_message(None, False)
       # Когда Алиса думает ("подготавливаю ответ") - ждём и нажимаем кнопку
      # if "think" in classes and "стоп" in aria_label:
      #   self.button.click()
      #   time.sleep(3)
   except Exception as e:
    pass

 def get_user_message(self, len_c):
  try:
   # Проверим, есть ли iframe
   iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
   #print(f"Найдено iframe: {len(iframes)}")
   # Попробуем разные селекторы
   selectors = [
    ".MessageBubble-Container_from-user",
    "[data-testid='message-bubble-container-from-user']",
    ".Message_from_user",
    ".AliceTextBubble_from_user"
   ]

   for selector in selectors:
    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
   # Основной поиск
   user_m = WebDriverWait(self.driver, 10).until(
    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".MessageBubble-Container_from-user"))   )

 #  print(f"Найдено сообщений пользователя: {len(user_m)}")
   last_user_container = user_m[-1]
   message = last_user_container.find_element(By.CSS_SELECTOR, ".AliceTextBubble").text.strip()
  # print(f"Последнее сообщение: '{message}'")

   if user_m and message:
    counts = len(user_m)
    return message, counts
   return "", len_c
  except Exception as ex:
   print(f"Ошибка: {ex}")
   return "", len_c
 def get_latest_message(self, len_c=0):
  try:
   self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
   # Проверяем состояние кнопки Алисы (самый надёжный способ)
   aria_label = self.button.get_attribute("aria-label")
   oknyx_core = self.button.find_element(By.CSS_SELECTOR, ".StandaloneOknyxCore")
   classes = oknyx_core.get_attribute("class").lower()

   message, len_c = self.get_user_message(len_c)
   # Алиса "думает/готовит ответ" если:
   # 1. В классах есть "thinking" ИЛИ
   # 2. aria-label содержит "стоп" И нет "listening"
   is_processing = (
     "thinking" in classes or
     ("стоп" in aria_label and "lis" not in classes)
   )
   if is_processing:
    print("stop")
    return message, len_c
   return message, len_c
  except Exception as ex:
   print(ex)
   return "", len_c

 def run(self):
  self.start_selenium()
  while self._running:
   try:
    time.sleep(2.5)  # Уменьшили с 1 секунды
    aria_label = self.button.get_attribute(self.alisa)
    oknyx_core = self.button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
    filter_elem = oknyx_core.get_attribute(self.DATA_TESTID_ATTR)
    classes = oknyx_core.get_attribute("class")
    # print(classes)
    if "think" in classes and ("начни слушать" in aria_label and "lis" not in classes):
     time.sleep(3)
     self.button.click()
     print("треугольник")
    # ВАРИАНТ 3: Отсутствие standby/listening
    if (
      "стоп" in aria_label
      and "lis" not in classes
      or "think"  in classes
      and "standby" not in classes
    ):
     print("⬜ белый квадратик")
     time.sleep(1)
     self.message, counts1 = self.get_latest_message(self.counts)
     self.button.click()
    # Нажимаем кнопку когда Алиса готова слушать
    if self.mic and "слу" in aria_label and ("su" in filter_elem):
     time.sleep(3)
     self.button.click()
     self.message, counts1 = self.get_latest_message(self.counts)
    if counts1 > self.counts and self.mic and self.message and not any(phrase in self.message for phrase in excluded_phrases):
     print(counts1)
     self.counts = counts1
     self.mic = False

     thread = threading.Thread(target=process_text, args=(self.message,))
     thread.start()
     thread.join()
     thr = threading.Thread(target=lambda: [time.sleep(3.7), setattr(self, 'mic', True)])
     thr.daemon = True
     thr.start()

   except Exception as ex1:
    pass

    # else:
    #  self.is_text_stable()
    #  print("0300")
    #  message, counts = self.get_user_messages()
    # if counts1 == 0:
    #  self.counts = counts1
    # if "стоп" in aria_label and "lis" not in classes and "think" not in classes and "collapse" not in classes and "standby" not in classes:
    #  self.button.click()
    #  time.sleep(2)

class MyWindow(QWidget):
 def __init__(self, parent=None):
  super(MyWindow, self).__init__(parent)
  self.mic = True
  self.mythread = MyThread(parent=self)

  BASE_PATH = os.path.dirname(os.path.abspath(__file__))
  self.icon1_path = os.path.join(BASE_PATH, "stop.png")
  self.icon2_path = os.path.join(BASE_PATH, "voice.png")
  self.tray_icon = QSystemTrayIcon(QIcon(self.icon2_path), self)

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

  self.setWindowFlags(
   Qt.WindowType.FramelessWindowHint |
   Qt.WindowType.WindowStaysOnTopHint |
   Qt.WindowType.Tool
  )
  self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
  self.setStyleSheet("background-color: rgba(255, 255, 255, 255); border-radius: 3px;")

  self.mythread.init_ui_signal.connect(self.QL)
  self.mythread.start()
  QTimer.singleShot(0, self.hide)

 def QL(self):
  layout = QVBoxLayout()
  self.label = QLabel(" ")
  self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
   self.tray_icon.setIcon(QIcon(icon_path))
   self.tray_icon.show()
  except Exception as e:
   print(f"change_icon error: {e}")

 def on_tray_icon_activated(self, reason):
  try:
   if reason == QSystemTrayIcon.ActivationReason.Trigger:
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
 sys.exit(app.exec())
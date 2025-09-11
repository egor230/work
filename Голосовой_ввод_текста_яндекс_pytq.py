from pytq_libs_voice import *
from PyQt5.QtWidgets import QSystemTrayIcon, QAction, QMenu, QDialog, QLabel, QMenu, QAction
from pynput import keyboard
from pynput.keyboard import Controller as Contr1
os.environ[
 "QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
# Глобальные переменные
driver = None
previous_message = ""
message_queue = Queue()
mic_on = True
ICON_PATH_ON = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png"
ICON_PATH_OFF = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/stop icon.jpeg"
SOURCE_ID = "54"
counts = 0

set_mute("0" if mic_on else "1") # вкл микрофон.
class Communicate(QObject):
 update_signal = pyqtSignal(str, bool)

def on_press(key):
 key = str(key).replace(" ", "")
 if key == "Key.shift_r":
  k.set_flag(True)
  return True
 if key in ("Key.space", "Key.right", "Key.left", "Key.down", "Key.up"):
  k.set_flag(False)
  return True
 if key == "Key.alt":
  global driver
  driver = k.get_driver()
  k.update_dict()
  return True
 return True

def on_release(key):
 return True

def start_listener():
 global listener
 listener = keyboard.Listener(on_press=on_press, on_release=on_release)
 listener.start()
start_listener()

### Починенный рабочий вариант
class MyThread(QtCore.QThread):  # Поток
  mysignal = QtCore.pyqtSignal(str, bool, bool)
  error_signal = QtCore.pyqtSignal(str)
  icon_signal = QtCore.pyqtSignal(str)

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
    self.show_hint = False

    self.DATA_TESTID_ATTR = "data-testid"
    self.OKNYX_CORE_CLASS = "StandaloneOknyxCore"
    self.MIC_BUTTON_CLASS = "StandaloneOknyx"
  def update_mic_state(self, mic):
    self.mic = mic

  def stop(self):
    self._running = False

  def show_message(self, text, mic, show):
    self.hint_text = text
    self.show_hint = show
    if show and text:
      self.mysignal.emit(text, mic, show)
    else:
      self.mysignal.emit(None, mic, show)

  def selenium_worker(self):

    mic_button = self.driver.find_element(By.CSS_SELECTOR, f".{self.MIC_BUTTON_CLASS}")
    oknyx_core = mic_button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
    while self._running:
     try:
      user_m = self.driver.find_elements(By.CSS_SELECTOR, ".MessageBubble-Container_from-user")
      if user_m:
       last_user_container = user_m[-1]
       message = last_user_container.find_element(By.CSS_SELECTOR, ".MessageBubble").text.strip()
       filter_elem = oknyx_core.get_attribute(self.DATA_TESTID_ATTR)
       if self.mic and "li" or "su" in filter_elem and len(message)>0:
         self.show_message(message, self.mic, show=True)
       else:
        self.show_message(None, False, show=False)
     except Exception:
       pass

  def run(self):
   try:
    self.show_message(None, False, show=False)
    option = get_option()
    self.driver = webdriver.Chrome(
      service=Service(ChromeDriverManager().install()), options=option
    )
    self.driver.get("https://alice.yandex.ru/chat/01938823-14ea-4000-bd7a-3cca57830d6a/")
    self.url = self.driver.current_url
    self.driver.implicitly_wait(1)
    selenium_thread = threading.Thread(target=self.selenium_worker, daemon=True)
    selenium_thread.start()
    del_all_chats(self.driver)
    new_chat_button = WebDriverWait(self.driver, 1).until(
     EC.element_to_be_clickable((By.XPATH, "//button[.//span[@class='AliceButton-Icon']]"))   )
    new_chat_button.click()
   except Exception as e:
    print(e)
    pass
   self.button = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='oknyx']")
   self.button.click()
   alisa = "aria-label"
   self.show_message("Давай поговорите", self.mic, show=True)
   while self._running:
    try:
     time.sleep(1)
     # Используем переменные в методе
     mic_button = self.driver.find_element(By.CSS_SELECTOR, f".{self.MIC_BUTTON_CLASS}")
     aria_label = mic_button.get_attribute(alisa)
     oknyx_core = mic_button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
     filter_elem = oknyx_core.get_attribute(self.DATA_TESTID_ATTR)
  
     if not self.mic:#    print(filter_elem)
       self.show_message(None, False, show=False)
       print(filter_elem)
       print(aria_label)
       if  "стоп" in aria_label or "li" in filter_elem:
        self.button.click()
       while not self.mic:
        time.sleep(1)
       self.button.click()
  
     if self.mic and not self.message and "слушать" in aria_label and "su" or "th" in filter_elem:
       self.button.click()
  
     self.message, counts1 = get_latest_message(self.driver, self.counts)
  
     if counts1 > self.counts and self.mic and self.message and not any(phrase in self.message for phrase in excluded_phrases):
       self.mic=False
       thread = threading.Thread(target=process_text, args=(self.message, k,))
       thread.start()
       thread.join()
       time.sleep(2.7)
       self.button.click()
       time.sleep(2.1)
       self.button.click()
       time.sleep(2.1)
       self.mic=True
       self.counts = counts1
    except Exception as ex1:
      print(ex1)
      time.sleep(0.1)
      continue
   
   if getattr(self, "driver", None) and hasattr(self.driver, "quit"):
    error_closse(self.driver)

class MyWindow(QtWidgets.QWidget):
  def __init__(self, parent=None):
    super(MyWindow, self).__init__(parent)
    self.mic = True

    self.mythread = MyThread(parent=self)
    self.mythread.start()
    self.icon1_path = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/stop icon.jpeg"
    self.icon2_path = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png"
    self.tray_icon = QSystemTrayIcon(QtGui.QIcon(self.icon2_path), self)

    menu = QMenu()
    quit_action = QAction("Quit", self)
    quit_action.triggered.connect(self.quit_t)
    menu.addAction(quit_action)

    self.mythread.mysignal.connect(self._update_label_from_thread)
    self.mythread.error_signal.connect(self._handle_thread_error)
    self.mythread.icon_signal.connect(self.change_icon)

    self.tray_icon.setContextMenu(menu)
    self.tray_icon.setToolTip("OFF")
    self.tray_icon.activated.connect(self.on_tray_icon_activated)
    self.tray_icon.show()


    self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
    self.setAttribute(Qt.WA_TranslucentBackground)
    self.setStyleSheet("background-color: rgba(255, 255, 255, 255); border-radius: 3px;")

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
        width = max(250, len(text) * 12)
        height = 45
        self.setFixedSize(width, height)
        self.move(610, 1070)
        self.show()
      else:
        self.hide()
    except Exception as e:
      print(f"UI update error: {e}")

  def _handle_thread_error(self, err_text):
    print("Thread error:", err_text)

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
      set_mute("0" if self.mic else "1")
      self.tray_icon.show()
      self.mythread.icon_signal.emit(self.icon2_path if self.mic else self.icon1_path)
      self.mythread.update_mic_state(self.mic)

      if self.mic:
        self.mythread.show_message("Микрофон включен", self.mic)
      else:
        self.mythread.show_message("Микрофон выключен", self.mic)
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
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QIcon
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
from libs_voice import *
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QSystemTrayIcon, QMenu)
from PyQt5.QtGui import QIcon, QFont, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key
from queue import Queue

driver = 0
previous_message = None
message_queue = Queue()
mic_on = True
ICON_PATH = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png"
SOURCE_ID = "54"

def set_mute(mute: str):
    subprocess.run(["pactl", "set-source-mute", SOURCE_ID, mute], check=True)

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

# Инициализация драйвера и настройка Alice
option = get_option()
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
driver.get("https://alice.yandex.ru/chat/01938823-14ea-4000-bd7a-3cca57830d6a/")
excluded_phrases = [...]
button = driver.find_element(By.CSS_SELECTOR, 'div.yamb-oknyx')
button.click()
driver.implicitly_wait(5)


def is_text_stable(driver, timeout=3):
 while True:
  try:  # Ждём 3 секунды перед повторной проверкой
   initial_text = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
   time.sleep(timeout)  # Снова получаем текст и сравниваем
   final_text = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
   if initial_text == final_text:
    break
  #  placeholder_element = driver.find_element(By.CSS_SELECTOR, '.chat__streaming-placeholder.svelte-10qurrr')
  #  if  placeholder_element:
  #   pass
  except:
   break
 return True

class TransparentWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 5px;")
        
        layout = QVBoxLayout()
        self.label = QLabel("...")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Times", 14))
        self.label.setStyleSheet("color: white;")
        layout.addWidget(self.label)
        self.setLayout(layout)
        
    def update_text(self, text, show):
        if show:
            self.label.setText(text)
            width = max(100, len(text) * 10)
            self.setFixedSize(width, 30)
            self.move(600, 1025)
            self.show()
        else:
            self.hide()

def run_app():
    app = QApplication(sys.argv)
    window = TransparentWindow()
    comm = Communicate()
    comm.update_signal.connect(window.update_text)

    # Настройка системного трея
    tray_icon = QSystemTrayIcon(QIcon(ICON_PATH))
    tray_menu = QMenu()
    toggle_action = tray_menu.addAction("ON OFF")
    
    def toggle_mic():
        global mic_on
        mic_on = not mic_on
        set_mute("0" if mic_on else "1")
        tray_icon.setToolTip("ON" if mic_on else "OFF")
    
    toggle_action.triggered.connect(toggle_mic)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.setToolTip("ON" if mic_on else "OFF")
    tray_icon.show()

    # Таймер для обновления интерфейса
    def check_queue():
        while not message_queue.empty():
            text, show = message_queue.get_nowait()
            comm.update_signal.emit(text, show)
    
    timer = QTimer()
    timer.timeout.connect(check_queue)
    timer.start(500)
    
    sys.exit(app.exec_())

def get_latest_message(driver, len_c=0):
 try:
  driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")  # filter_elem = WebDriverWait(driver, 1).until( EC.presence_of_element_located((By.CSS_SELECTOR, ".yamb-oknyx-lottie.svelte-rdfi3w"))).get_attribute("data-testid")
  # aria_label= mic_button.get_attribute('aria-label')  # Ожидание наличия элемента на странице
  element = driver.find_element(By.CSS_SELECTOR, '.AliceChat-StreamingPlaceholder')
  if element.is_displayed():  # Проверка видимости элемента
   message, counts = get_user_messages(driver)   # button.click()
   return message, counts + 1
  else:
   return "", len_c
 except Exception as ex:
  pass
  return "", len_c  # Возврат по умолчанию, если ни одно условие не выполнилось    # pass       #

try:
    counts = 0
    previous_message = ""
    app_thread = threading.Thread(target=run_app, daemon=True)
    app_thread.start()
    url = str(driver.current_url)
    
    while True:
     try:
         mic_button = driver.find_element(By.CSS_SELECTOR, 'div.yamb-oknyx')
         aria_label = mic_button.get_attribute('aria-label')
         if 'слушать' in aria_label:
             button.click()
         message, counts1 = get_latest_message(driver, counts)
         filter_elem = driver.find_element(
             By.CSS_SELECTOR, "div.yamb-oknyx-lottie.svelte-8z6ghg"
         ).get_attribute("data-testid")
         
         if (counts1 > counts and message and
             not any(phrase in message for phrase in excluded_phrases)):
             threading.Thread(
                 target=process_text,
                 args=(message, k),
                 daemon=True
             ).start()
             counts = counts1
             time.sleep(1.7)
             button.click()
             
         # Отправка данных в очередь для GUI
         show_window = mic_on and 'стоп' in aria_label
         message_queue.put((message, show_window))
         
     except Exception as ex1:
         current_url = str(driver.current_url)
         if "/search/" in current_url:
             driver.get(url)
             time.sleep(4)
             counts = 0
             del_all_chats(driver)
             button.click()
except Exception as ex1:
    pass
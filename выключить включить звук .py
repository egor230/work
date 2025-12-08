from libs_voice import *
from PyQt5 import QtCore, QtWidgets, QtGui  # Импорт необходимых модулей из PyQt5
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QAction, QMenu, QWidget,  QDialog,QLabel, QSystemTrayIcon, QMenu, QAction, QVBoxLayout, QPushButton, QApplication

import tempfile
get_user_name = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''

mutex = threading.Lock()# Создаем мьютекс
def mic(driver):
  mutex.acquire()  # Захватываем мьютекс
  primary_button = driver.find_element("id", "mic")
  style_value = primary_button.get_attribute("style")
  pattern = r"--(\w+)"
  result = re.search(pattern, style_value)  # time.sleep(0.75)
  if result:
    res= (result.group(1))
    if res != "secondary-color":     # print("on")
     driver.find_element("id", "mic").click()  # выключить запись голоса
     time.sleep(0.75)
     driver.find_element("id", "mic").click()  # включить запись голоса
     time.sleep(0.75)
  else:
     time.sleep(0.75)
     driver.find_element("id", "mic").click()  # включить запись голоса

  mutex.release()     # Освобождаем мьютекс

def a():
  while 1:
    with keyboard.Listener(on_release=on_release, on_press=on_press) as listener:
      listener.join()
driver=0
try:
   prefs = {'safebrowsing.enabled': True,
           "credentials_enable_service": False,
           "profile.password_manager_enabled": False,
           "credentials_enable_service": False,
           "profile.password_manager_enabled": False,
           "profile.managed_default_content_settings.images": 0,           # - Отключить загрузку CSS:
           # "profile.default_content_setting_values.javascript": 2,           # - Отключить загрузку JavaScript:
           "profile.default_content_setting_values.cache": 0,           # - Включить кэширование:

           }
   option = webdriver.ChromeOptions()
   # option.add_experimental_option("prefs", prefs)
   option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
   option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6367.118 Safari/537.36")
   option.add_argument("--use-fake-ui-for-media-stream")  # звук
   option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
   option.add_argument("--ignore-certificate-errors")  # Игнорировать ошибки сертификатов SSL
   option.add_argument("--allow-running-insecure-content")  # Разрешить запуск небезопасного контента

   option.add_argument("--disable-web-security")  # Отключить веб-безопасность (используйте с осторожностью)
   option.add_argument("--disable-gpu")  # Отключить использование GPU
   option.add_argument('--disable-infobars')
   # option.add_argument("--disable-blink-features=AutomationControlled")
   # option.add_argument("--disk-cache-size=0")
   # option.add_argument("--media-cache-size=0")
   # option.add_argument("--automatic-wait-for-preview")
   # option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
   # option.add_argument("--disable-site-isolation-trials")
   option.add_argument("--disable-session-crashed-bubble")
   option.add_argument("--ignore-certificate-errors")
   option.add_argument("--ignore-ssl-errors")
   option.binary_location = '/usr/bin/google-chrome'
   # option.add_argument("--incognito")  # Включить режим инкогнито
   # Создаем временную директорию для пользовательских данных
   # temp_user_data_dir = tempfile.mkdtemp()
   # option.add_argument(f"--user-data-dir={temp_user_data_dir}")  # Использовать временную директорию для пользовательских данных

   # option.add_argument('--user-data-dir=/home/egor/.config/google-chrome')

   t1 = threading.Thread(target=a)
   t1.start()
except Exception as ex1:  # print(ex1)  # driver.close()  # driver.quit()
  pass
get_user_name = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''# Убивает текущий процесс, запущенный текущим пользователем и соответствующий имени исполняемого скрипта.
script = '''#!/bin/bash
sudo systemd-resolve --flush-caches

'''
def kill_current_script():# Получаем идентификатор активного окна
  result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # print(result)
  name_scrypt =  sys.argv[0]
  user = subprocess.run(['bash'], input=get_user_name, stdout=subprocess.PIPE, text=True).stdout.strip()  # Вызываем скрипт
  for line in result.split("\n"):
   user_name = ' '.join(line.split()[0]).replace(" ", "")
   process_name = ' '.join(line.split()[10:])
   if user_name==user and name_scrypt in process_name:
     pid_id = int(line.split()[1])  # или используйте другой индекс, если нужны другие данные    # print(process_name)
     f = '''#!/bin/bash
          kill {}   '''.format(pid_id)
     subprocess.call(['bash', '-c', f])#

def f1():
  try:
    global driver

    # subprocess.call(['bash', '-c', script])
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                              options=option)
    driver.delete_all_cookies()
    driver.execute_cdp_cmd('Network.clearBrowserCache', {})

    driver.set_window_size(624, 568)  # optiol
    driver.set_window_position(600, 250)  # Открываем новое окно
    driver.get("https://www.speechtexter.com")  # открыть сайт
    k.save_driver(driver)
    time.sleep(1.5)
    driver.find_element("id", "mic").click()  # включить запись голоса    # time.sleep(2.91)
    driver.minimize_window()
  except Exception as ex2:  #
    if 'no such window: target window' in str(ex2):
      print("exit no such window: target window already closed")
      error_closse(driver)  # print(ex2)  # print("error")
    time.sleep(5)
    pass
f1()

class MyThread(QtCore.QThread):  # Определение класса потока
  mysignal = QtCore.pyqtSignal(str)  # Объявление сигнала
  error_signal = QtCore.pyqtSignal(str)  # Добавлено объявление сигнала ошибки
  
  def __init__(self, parent=None):  # Конструктор класса потока
    super(MyThread, self).__init__(parent)  # Вызов конструктора базового класса
  def run(self):  # Метод, исполняемый потоком
    # # Чтение данных из потока
    while 1:
     try:# Чтение данных из потока
      text0 = driver.find_element("id", "textEditor").text
      # while 1:
      #  time.sleep(2.114)
      #  if text0 != driver.find_element("id", "textEditor").text:
      #     text0= driver.find_element("id", "textEditor").text
      #  else:
      #    if text0 !="":
      #     break
      text = str(text0)       # time.sleep(0.3)
      if len(text) != 0 and text != None and text != "None":
        driver.find_element("id", "textEditor").clear()  # удалить старый текст.
        text = str(text.lower())
        thread = threading.Thread(target=process_text, args=(text, k,))  # break
        thread.daemon
        thread.start()         # print("+++++++++++++++")
        mic(driver)
        text = "None"       # break counter = 0  # Обнуляем счетчик, если звук есть
     except Exception as ex2:
       # print(ex2)
       pass
class MyWindow(QtWidgets.QWidget):  # Определение класса главного окна
    def __init__(self, parent=None):  # Конструктор класса окна
      self.mic = True
      super(MyWindow, self).__init__(parent)  # Вызов конструктора базового класса
      self.tray_icon = QSystemTrayIcon(QtGui.QIcon("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png"), self)

      menu = QMenu()      # Создание контекстного меню для иконки в системном трее
      quit_action = QAction("Quit", self)
      quit_action.triggered.connect(self.quit_t)  # Используйте метод quit, определённый ниже
      menu.addAction(quit_action)
      
      self.mythread = MyThread()  # Создание экземпляра потока
      
      # Установка меню в трей
      self.tray_icon.setContextMenu(menu)
      self.tray_icon.setToolTip("OFF")  # Установка начальной подсказки
      self.tray_icon.activated.connect(self.on_tray_icon_activated)  # Привязываем обработчик к сигналу нажатия
      self.tray_icon.show()
      self.mythread.start()

    def on_tray_icon_activated(self):     # Данная функция
     driver.set_window_size(624, 568)  # optiol
     driver.set_window_position(600, 250)  # Открываем
     driver.find_element("id", "mic").click()  # вкл-выкл запись голоса
     time.sleep(0.25)
     if self.mic== True:
      self.mic=False
     else:
      self.mic=True#
     self.tray_icon.setToolTip("ON" if self.mic else "OFF")
     self.tray_icon.show()
     driver.minimize_window()
    
    def quit_t(self):  # Метод обработки события закрытия окна
      QApplication.quit()
      kill_current_script()
app = QApplication(sys.argv)
window = MyWindow()
sys.exit(app.exec_())

# Переопределение стандартных потоков вывода и ошибок, чтобы подавить сообщения ALSA и Jack
sys.stdout = open(os.devnull, 'w')  # Отключаем стандартный вывод
sys.stderr = open(os.devnull, 'w')  # Отключаем ошибки

def sound():  # Переопределение стандартного вывода ошибок
  sys.stderr = open(os.devnull, 'w')

  try:    # Настройки для работы со звуком
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 4096
    p = pyaudio.PyAudio()# Инициализация PyAudio
    # Открытие потока для записи
    stream = p.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,    frames_per_buffer=CHUNK)

    data = stream.read(CHUNK)    # Чтение данных из потока
    audio_data = np.frombuffer(data, dtype=np.int16)
    s=[]
    for i in range(100):
      s.append(np.abs(audio_data).mean())
  # print(np.abs(audio_data).mean())
  except Exception as e:
    print(f"Error: {e}")  # Вывод информации об ошибке (если нужно)
  finally:
    # Восстановление стандартного вывода ошибок
    sys.stderr.close()
    sys.stderr = sys.__stderr__

  return p, stream, audio_data


      # finally:
      #  # Закрытие потока и PyAudio
      #  stream.stop_stream()
      #  stream.close()
      #  p.terminate()

    # start_time = time.time()
       # time.sleep(3.14)
       # p, stream, audio_data = sound()
       # print(np.abs(audio_data).mean())
       #
       # if np.abs(audio_data).mean() > 365:
       #   start_time = time.time()
       # if np.abs(audio_data).mean() < 305:# and (time.time() - start_time) > 3:  # Если прошло 8 секунд
       #  start_time = time.time()  # Сбрасываем время
# Закрытие потока и PyAudio
# stream.stop_stream()
# stream.close()
# p.terminate()

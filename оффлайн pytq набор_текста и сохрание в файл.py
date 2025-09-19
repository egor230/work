from libs_voice import *
from PyQt5 import QtCore, QtWidgets, QtGui  # Импорт необходимых модулей из PyQt5
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QAction, QMenu, QWidget,  QDialog,QLabel, QSystemTrayIcon, QMenu, QAction, QVBoxLayout, QPushButton, QApplication
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key

def on_press(key):  # обработчик клави.  # print(key )
 key = str(key).replace(" ", "")
 if key == "Key.shift_r":  #
  k.set_flag(True)
  return True
 if key == "Key.space" or key == "Key.right" or key == "Key.left" \
  or key == "Key.down" or key == "Key.up":
  k.set_flag(False)
  return True
 if key == "Key.alt":
  driver = k.get_driver()
  k.update_dict()
  return True
 else:
  return True

def on_release(key):
 pass
 return True

def start_listener():
 global listener
 listener = keyboard.Listener(on_press=on_press, on_release=on_release)
 listener.start()

start_listener()  # Запускаем слушатель# driver.set_window_position(1, 505)
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(cache_dir)

#  models = {
#     "tiny": "https://huggingface.co/openai/whisper-tiny/resolve/main/pytorch_model.bin",
#     "base": "https://huggingface.co/openai/whisper-base/resolve/main/pytorch_model.bin",
#     "small": "https://huggingface.co/openai/whisper-small/resolve/main/pytorch_model.bin",
#     "medium": "https://huggingface.co/openai/whisper-medium/resolve/main/pytorch_model.bin",
#     "large": "https://huggingface.co/openai/whisper-large/resolve/main/pytorch_model.bin",
#  }
# Проверка наличия модели
model_name = "large"
model_path = cache_dir / "whisper" / f"{model_name}.pt"

if model_path.exists():  # Загрузка модели (Whisper сам проверит кэш)

    # Установка параметров для оптимизации CPU
    os.environ["OMP_NUM_THREADS"] = "8"
    os.environ["MKL_NUM_THREADS"] = "8"
    model = whisper.load_model(model_name, device="cpu")
else:
    exit(0)
# Запись аудио с микрофона
# duration = 15  # Длительность записи в секундах
# sample_rate = 16000  # Частота дискретизации

class MyThread(QtCore.QThread):  # Определение класса потока
 mysignal = QtCore.pyqtSignal(str)  # Объявление сигнала
 error_signal = QtCore.pyqtSignal(str)  # Добавлено объявление сигнала ошибки
 icon_signal = QtCore.pyqtSignal(str)  # Сигнал для изменения иконки
 
 def __init__(self, parent=None):  # Конструктор класса потока
  super(MyThread, self).__init__(parent)  # Вызов конструктора базового класса
  self.mic = True  # Добавляем переменную mic в поток

 def run(self):  # Метод, исполняемый потоком
  # Чтение данных из потока
  while True:
   try:
    if self.mic:
      # Отправляем путь к первой иконке
      self.icon_signal.emit("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png")
      # Параметры записи
      sample_rate = 16000  # Частота дискретизации
      duration = 5.5  # Минимальная длительность блока (0.5 секунды)
      block_size = int(sample_rate * duration)  # 16000 * 0.5 = 8000 сэмплов
      buffer = queue.Queue()  # Оставляем для совместимости, но используем напрямую

      # Функция обратного вызова для записи аудио
      def audio_callback(indata, frames, time, status):
       if status:
        print("Ошибка:", status)  # Прямое распознавание без буфера
       audio = indata.flatten().astype(np.float32)
       result = model.transcribe(
        audio, language="ru", fp16=False,  # Отключаем FP16 для CPU
        condition_on_previous_text=False)
       text = str(result["text"])
       print(text)
      self.icon_signal.emit("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/stop icon.jpeg")
      audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
      sd.wait()  # Ожидание завершения записи
      
      # Сохранение аудио в файл
      with wave.open("temp.wav", 'wb') as wf:
       wf.setnchannels(1)
       wf.setsampwidth(2)
       wf.setframerate(sample_rate)
       wf.writeframes((audio * 32767).astype(np.int16).tobytes())
      # Распознавание речи
      message = model.transcribe("temp.wav", fp16=False, language="ru", task="transcribe")["text"]
      if message:
       message = repeat(message)
       thread = threading.Thread(target=process_text, args=(message, k))
       thread.daemon = True
       thread.start()
       thread.join()

   except Exception as ex2:
    print(ex2)  # Лучше видеть ошибки
    self.error_signal.emit(str(ex2))

class MyWindow(QtWidgets.QWidget):  # Определение класса главного окна
 def __init__(self, parent=None):  # Конструктор класса окна
  super(MyWindow, self).__init__(parent)  # Вызов конструктора базового класса
  
  # Сохраняем пути к иконкам как атрибуты класса для удобства
  self.icon1_path = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/stop icon.jpeg"
  self.icon2_path = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png"
  
  self.tray_icon = QSystemTrayIcon(QtGui.QIcon(self.icon2_path), self)  # Инициализируем иконку трея
  
  menu = QMenu()  # Создание контекстного меню для иконки в системном трее
  quit_action = QAction("Quit", self)
  quit_action.triggered.connect(self.quit_t)  # Используйте метод quit, определённый ниже
  menu.addAction(quit_action)
  
  self.mythread = MyThread()  # Создание экземпляра потока
  self.mythread.icon_signal.connect(self.change_icon)  # Подключаем сигнал изменения иконки
  self.tray_icon.setContextMenu(menu)  # Установка меню в трей
  self.tray_icon.setToolTip("OFF")  # Установка начальной подсказки
  self.tray_icon.activated.connect(self.on_tray_icon_activated)  # Привязываем обработчик к сигналу нажатия
  self.tray_icon.show()
  self.mythread.start()
 
 def change_icon(self, icon_path): # Метод для изменения иконки в системном трее.
  self.tray_icon.setIcon(QtGui.QIcon(icon_path))
  self.tray_icon.show()
 
 def on_tray_icon_activated(self):  # Данная функция
  try:
   if self.mic == True:
    self.mic = False
   else:
    self.mic = True
   self.tray_icon.setToolTip("ON" if self.mic else "OFF")
   set_mute("0" if  self.mic else "1")
   self.tray_icon.show()
  except Exception as e:
   print(f"Error in on_tray_icon_activated: {e}")
 
 def quit_t(self):  # Метод обработки события закрытия окна
  self.mythread.quit()  # Останавливаем поток
  self.mythread.wait()  # Ждем завершения потока
  QApplication.quit()

if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 sys.exit(app.exec_())

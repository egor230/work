from libs_voice import *
from PyQt5 import QtCore, QtWidgets, QtGui  # Импорт необходимых модулей из PyQt5
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSlider, QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PyQt5.QtWidgets import QSystemTrayIcon, QAction, QMenu, QDialog, QLabel, QMenu, QAction
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller as Contr1
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"

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
def is_speech(audio_data, threshold=0.027, min_duration=3.5, sample_rate=44100):#  Определяет, есть ли звук в аудиопотоке.
 # :param audio_data: Массив аудиоданных (например, indata.flatten())
 # :param threshold: Пороговое значение амплитуды, выше которого считается, что есть звук
 # :param min_duration: Минимальная длительность звука в секундах, чтобы считать его значимым
 # :param sample_rate: Частота дискретизации аудио
 # :return: True, если обнаружен звук, иначе False
 # Вычисляем среднюю амплитуду
 avg_amplitude = np.mean(np.abs(audio_data))
 total_audio_duration = len(audio_data) / sample_rate
 print(total_audio_duration)
 if avg_amplitude > threshold: # total_audio_duration > min_duration  and# print(f"Общая длительность аудио ({total_audio_duration:.2f}с) меньше min_duration ({min_duration}с)")
  # Если аудио длинее min_duration, и превышает ли средняя амплитуда порог
  return True
 else:
  return False

models = ["tiny", "base", "small", "medium", "large", "large-v3"]
model_name = models[5] # Загрузка модели (tiny для скорости, small для качества)
model_path = cache_dir / "whisper" / f"{model_name}.pt"

if model_path.exists():  # Загрузка модели (Whisper сам проверит кэш)
  os.environ["OMP_NUM_THREADS"] = "8"  # Установка параметров для оптимизации CPU
  os.environ["MKL_NUM_THREADS"] = "8"
  torch.set_num_threads(8)  # или количество ядер вашего CPU
  subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)  # вкл микрофон.
  model = whisper.load_model(model_name, device="cpu")
else:
  exit(0)

# Запись аудио с микрофона. Функция обратного вызова для записи аудио
def audio_callback(indata, frames, time, status):
 if status:
  print("Ошибка:", status)
 try:
  audio = indata.flatten().astype(np.float32) # Прямое распознавание без буфера
  if is_speech(audio):
   result = model.transcribe(audio, language="ru", fp16=False, # Отключаем FP16 для CPU
   condition_on_previous_text=False)
   text = str(result["text"]).strip()
   if text: #and text !="Продолжение следует...":  # Проверяем, что текст не пустой
    message = repeat(text)
    thread = threading.Thread(target=process_text, args=(message, k))
    thread.start()
    thread.join()
 except Exception as e:
  print("Ошибка в распознавании:", e)

class MyThread(QtCore.QThread):  # Определение класса потока
 mysignal = QtCore.pyqtSignal(str)  # Объявление сигнала
 icon_signal = QtCore.pyqtSignal(str)  # Сигнал для изменения иконки
 
 def __init__(self, parent=None):  # Конструктор класса потока
  super(MyThread, self).__init__(parent)  # Вызов конструктора базового класса
  self.mic = True  # Добавляем переменную mic в поток
  self.duration = 7.5  # Начальная длительность записи
 
 def run(self):  # Метод, исполняемый потоком
  while True:  # Чтение данных из потока
   try:
    if self.mic: # состояние микрофона.
     sample_rate = 16000  # Частота дискретизации
     duration = self.duration  # Используем self.duration
     block_size = int(sample_rate * duration)  # 16000 * duration
     buffer = queue.Queue()  # Оставляем для совместимости, но используем напрямую
     stream = sd.InputStream(samplerate=sample_rate, channels=1,  # Запуск записи
                             dtype="float32", callback=audio_callback, blocksize=block_size)
     self.icon_signal.emit("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png")
     stream.start()
     time.sleep(duration)  # Ожидание для записи
     stream.stop()  # Останавливаем поток
     stream.close()  # Закрываем поток
   
     self.icon_signal.emit("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/stop icon.jpeg")
     time.sleep(3)
   except Exception as ex2:#    print(ex2)  # Лучше видеть ошибки
    pass

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
  duration_action = QAction("Длина записи", self)  # Новый пункт меню
  duration_action.triggered.connect(self.set_duration)  # Подключаем метод для ползунка
  menu.addAction(duration_action)
  menu.addAction(quit_action)
  
  self.mythread = MyThread()  # Создание экземпляра потока
  self.mythread.icon_signal.connect(self.change_icon)  # Подключаем сигнал изменения иконки
  self.tray_icon.setContextMenu(menu)  # Установка меню в трей
  self.tray_icon.setToolTip("OFF")  # Установка начальной подсказки
  self.tray_icon.activated.connect(self.on_tray_icon_activated)  # Привязываем обработчик к сигналу нажатия
  self.tray_icon.show()
  self.mythread.start()
 
 def change_icon(self, icon_path):  # Метод для изменения иконки в системном трее.
  self.tray_icon.setIcon(QtGui.QIcon(icon_path))
  self.tray_icon.show()
 
 def set_duration(self):  # Метод для установки длительности записи
  dialog = QDialog(self)
  dialog.setWindowTitle("Длина записи")
  layout = QVBoxLayout()
  label = QLabel(str(int(self.mythread.duration)))  # Метка с текущим значением
  slider = QSlider(QtCore.Qt.Horizontal)
  slider.setMinimum(5)  # Минимальное значение 5 секунд
  slider.setMaximum(50)  # Максимальное значение 50 секунд
  slider.setSingleStep(5)  # Шаг 5 секунд
  slider.setValue(int(self.mythread.duration))  # Текущее значение
  slider.valueChanged.connect(lambda value: self.mythread.__setattr__('duration', value))
  slider.valueChanged.connect(lambda value: label.setText(str(value)))  # Обновляем метку
  layout.addWidget(slider)
  layout.addWidget(label)  # Добавляем метку в layout
  dialog.setLayout(layout)
  dialog.exec_()
 def on_tray_icon_activated(self):  # Данная функция
  try:
   if self.mic == True:# Состояние микрофона.
    self.mic = False
   else:
    self.mic = True
   self.tray_icon.setToolTip("ON" if self.mic else "OFF")
   set_mute("0" if self.mic else "1")
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
 

#  models = { "tiny": "https://huggingface.co/openai/whisper-tiny/resolve/main/pytorch_model.bin",
#     "base": "https://huggingface.co/openai/whisper-base/resolve/main/pytorch_model.bin",
#     "small": "https://huggingface.co/openai/whisper-small/resolve/main/pytorch_model.bin",
#     "medium": "https://huggingface.co/openai/whisper-medium/resolve/main/pytorch_model.bin",
#     "large": "https://huggingface.co/openai/whisper-large/resolve/main/pytorch_model.bin", }
# Проверка наличия модели

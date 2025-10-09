from write_text import *
from faster_whisper import WhisperModel
import os, sys
cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/whisper/"# Путь к модели
model_size = "large-v3"
model_dir = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_size}", "snapshots")
if not os.path.exists(model_dir):# Проверка существования папки snapshots
    print(f"Ошибка: Папка snapshots не найдена: {model_dir}. Убедитесь, что модель скачана.")
    sys.exit(1)

# Поиск первого snapshot
snapshot = next((d for d in os.listdir(model_dir) if os.path.isdir(os.path.join(model_dir, d))), None)
if not snapshot:
    print("Ошибка: Нет snapshots в кэше. Скачайте модель заново.")
    sys.exit(1)

# Путь к модели и проверка model.bin
model_path = os.path.join(model_dir, snapshot)
if not os.path.exists(os.path.join(model_path, "model.bin")):
    print(f"Ошибка: Файл model.bin не найден в {model_path}")
    sys.exit(1)

# Загрузка модели
try:
    model = WhisperModel(model_path, device="cpu", compute_type="int8")
    print("Модель загружена успешно.")
except Exception as e:
    print(f"Ошибка загрузки модели: {e}")
    sys.exit(1)

def record_audio(duration=8, fs=44100):# Запись аудио с микрофона
  print("star...")
  recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
  sd.wait()
  audio_file = "temp.wav"
  write(audio_file, fs, recording)
  print(f"Запись завершена, файл сохранён как {audio_file}")

def audio(model): # Путь к аудиофайлу
 try:
   audio_file = "temp.wav"
   segments, info = model.transcribe( audio_file, beam_size=4, language="ru" ) # Только русский
   message_parts = []
   for segment in segments:
    text = segment.text
    message_parts.append(text.strip())
   message = ' '.join(message_parts)
   # На всякий случай принудительно кодируем-раскодируем:
   message = str(message)
   return message
 except Exception as e:
  print(e)
  pass

# Создаём и запускаем поток для записи
record_thread = threading.Thread(target=record_audio, args=( ))
# record_thread.start()
# record_thread.join()

message = audio(model)
print(type(message))
print(message)

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
    if self.mic:  # Отправляем путь к первой иконке
     self.icon_signal.emit("голос.png")
     # Параметры записи

     message = audio(model)
  
     break
     # if message:
     #   message = repeat(message)
     #   thread = threading.Thread(target=process_text, args=(message, k))
     #   thread.start()
     #   thread.join()

   except Exception as ex2:
    print(ex2)  # Лучше видеть ошибки
    self.error_signal.emit(str(ex2))
    exit(1)

def stop(self):
 self._stop = True

class MyWindow(QtWidgets.QWidget):
 def __init__(self, parent=None):
  super(MyWindow, self).__init__(parent)
  self.icon1_path = "stop icon.jpeg"
  self.icon2_path = "голос.png"
  self.mic = True  # состояние микрофона

  self.tray_icon = QSystemTrayIcon(QtGui.QIcon(self.icon2_path), self)
  menu = QMenu()
  quit_action = QAction("Quit", self)
  quit_action.triggered.connect(self.quit_t)
  menu.addAction(quit_action)

  self.mythread = MyThread()
  self.mythread.icon_signal.connect(self.change_icon)
  self.mythread.error_signal.connect(print)  # вывод ошибок в консоль

  self.tray_icon.setContextMenu(menu)
  self.tray_icon.setToolTip("ON")
  self.tray_icon.activated.connect(self.on_tray_icon_activated)
  self.tray_icon.show()

  self.mythread.start()

 def change_icon(self, icon_path):
  self.tray_icon.setIcon(QtGui.QIcon(icon_path))
  self.tray_icon.show()

 def on_tray_icon_activated(self, reason=None):
  try:
   self.mic = not self.mic
   self.mythread.mic_toggle_signal.emit(self.mic)
   self.tray_icon.setToolTip("ON" if self.mic else "OFF")
   set_mute("0" if self.mic else "1")
   self.tray_icon.show()
  except Exception as e:
   print(f"Error in on_tray_icon_activated: {e}")

 def quit_t(self):
  self.mythread.stop()
  self.mythread.wait()
  QApplication.quit()


if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 sys.exit(app.exec_())
from write_text import *
from faster_whisper import WhisperModel
import tkinter as tk
from tkinter import Frame, Label
import numpy as np
cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/whisper/"# Путь к модели
model_size = "large-v3"
model_dir = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_size}", "snapshots")
if not os.path.exists(model_dir):# Проверка существования папки snapshots
    print(f"Ошибка: Папка snapshots не найдена: {model_dir}. Убедитесь, что модель скачана.")
    sys.exit(1)
snapshot = next((d for d in os.listdir(model_dir) if os.path.isdir(os.path.join(model_dir, d))), None)
if not snapshot:# Поиск первого snapshot
  print("Ошибка: Нет snapshots в кэше. Скачайте модель заново.")
  sys.exit(1)
model_path = os.path.join(model_dir, snapshot)# Путь к модели и проверка model.bin
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
    text = segment.text.strip()
    if text:  # Проверяем, что строка не пустая
     message_parts.append(text)
   message = ' '.join(message_parts)
   # На всякий случай принудительно кодируем-раскодируем:
   # message = str(message)
   return message
 except Exception as e:
  print(e)
  pass
 # thread = threading.Thread(target=process_text, args=(message, k))
 # thread.start()
 # thread.join()

thread = threading.Thread(target=record_audio)

import numpy as np
import wave
import os

def is_speech(audio_data="temp.wav", threshold=0.0308, min_duration=4.5, sample_rate=44100):
 try:  # Проверяет, содержит ли аудиофайл речь или звук.
   # Если передано имя файла (строка), загружаем данные
   if isinstance(audio_data, str):
       if not os.path.isfile(audio_data):
           print(f"Ошибка: аудиофайл не найден: {audio_data}")
           return False
       # Чтение WAV-файла
       with wave.open(audio_data, 'rb') as wav_file:
           # Проверка параметров файла
           channels = wav_file.getnchannels()
           samp_width = wav_file.getsampwidth()
           frames = wav_file.getnframes()
           file_sample_rate = wav_file.getframerate()
 
           if frames == 0:
               print("Ошибка: аудиофайл пустой")
               return False
 
           # Чтение всех фреймов
           raw_data = wav_file.readframes(frames)
 
       # Преобразуем в numpy массив
       if samp_width == 2:
           dtype = np.int16
       elif samp_width == 1:
           dtype = np.uint8
       else:
           print(f"Ошибка: неподдерживаемая глубина звука: {samp_width * 8} бит")
           return False
 
       audio_array = np.frombuffer(raw_data, dtype=dtype)
 
       # Преобразуем в моно, если стерео
       if channels == 2:
           audio_array = audio_array.reshape(-1, 2).mean(axis=1)
 
       # Нормализуем в диапазон [-1.0, 1.0] (для 16-bit)
       if dtype == np.int16:
           audio_array = audio_array.astype(np.float32) / 32768.0
       elif dtype == np.uint8:
           audio_array = (audio_array.astype(np.float32) - 128.0) / 128.0
 
       # Используем фактическую частоту дискретизации из файла
       actual_sample_rate = file_sample_rate
   else:
       # Предполагаем, что audio_data — это уже numpy-массив
       audio_array = np.asarray(audio_data)
       if audio_array.size == 0:
           print("Ошибка: аудиоданные пусты")
           return False
       actual_sample_rate = sample_rate
 
   # Проверка, что данные не пустые
   if audio_array.size == 0:
       print("Ошибка: аудиоданные пусты или не загружены")
       return False
 
   # Вычисление длительности аудио в секундах
   duration = len(audio_array) / actual_sample_rate
   if duration < min_duration:
       print(f"Ошибка: длительность аудио ({duration:.2f} сек) меньше минимальной ({min_duration} сек)")
       return False
 
   # Вычисление средней амплитуды
   avg_amplitude = np.mean(np.abs(audio_array))
   print(f"Средняя амплитуда: {avg_amplitude:.6f}")
 
   # Проверка порога амплитуды
   if avg_amplitude > threshold:
       return True
   else:
       print(f"Амплитуда ({avg_amplitude:.6f}) ниже порога ({threshold})")
       return False
 
 except Exception as ex:
   print(f"Ошибка при обработке аудио: {ex}")
   return False

def set_mute(mute: str):
 subprocess.run(["pactl", "set-source-mute", "54", mute], check=True)

def get_mute_status():# Получает статус Mute для источника '54' с помощью pactl и grep.
 
 try:
  r = subprocess.run(  ["pactl", "get-source-mute", "54"],
   capture_output=True, text=True, check=True  )
  return r.stdout.lower()
 except:
  return False
def update_label(root, label):
  try:
    mic_on = get_mute_status()
    if mic_on:
     print("32222222" )
     label.config(text="Говорите...")
     label.config(text="Стоп")
     if is_speech():
      message = audio(model)  # Замените "model" на вашу модель
      if message:
       message = repeat(message)
       print(f" {message}")
       len_len=len(message)*12+10
       # len_len=600
       root.geometry(f"{len_len}x20+700+1025")  #
       label.config(text=message)
     # thread.start()
     # thread.join()  # Ждем завершения записи
  except Exception as ex1:
    print(f"Ошибка: {ex1}")
  # Планируем следующее обновление через 1 секунду
def wt():# Создаем главное окно
 root = tk.Tk()
 frame = tk.Frame(root)
 label = tk.Label(frame, text="...", font='Times 14', anchor="center")
 label.pack(padx=3, fill=tk.X, expand=True)
 frame.pack(fill=tk.X)
 root.overrideredirect(True)
 root.resizable(True, True)
 root.attributes("-topmost", True)
 # Запускаем периодическое обновление метки
 root.after(1000, lambda: update_label(root, label))
 root.mainloop()
  # Запускаем главный цикл
 
w1 = threading.Thread(target=wt)
w1.start()

class MyThread(QtCore.QThread):
 text_signal = QtCore.pyqtSignal(str, bool)
 icon_signal = QtCore.pyqtSignal(str)
 init_ui_signal = QtCore.pyqtSignal()
 
 def __init__(self, parent=None):
  super(MyThread, self).__init__(parent)
  self.parent = parent
  self.mic = True
  self._running = True
 
 def update_mic_state(self, mic):
  self.mic = mic
 
 def run(self):
  while self._running:
   try:
    pass
   except Exception as ex1:
    pass

class MyWindow(QtWidgets.QWidget):
 def __init__(self, parent=None):
  super(MyWindow, self).__init__(parent)
  self.mic = True
  self.mythread = MyThread(parent=self)
  self.icon1_path = "stop icon.jpeg"
  self.icon2_path = "голос.png"
  self.tray_icon = QSystemTrayIcon(QtGui.QIcon(self.icon2_path), self)
  
  menu = QMenu()
  quit_action = QAction("Quit", self)
  quit_action.triggered.connect(self.quit_t)
  menu.addAction(quit_action)
  
  self.mythread.icon_signal.connect(self.change_icon)
  
  self.tray_icon.setContextMenu(menu)
  self.tray_icon.setToolTip("OFF")
  self.tray_icon.activated.connect(self.on_tray_icon_activated)
  self.tray_icon.show()
  self.mythread.start()
  QTimer.singleShot(0, self.hide)
 
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

# if __name__ == "__main__":
#  app = QApplication(sys.argv)
#  window = MyWindow()
#  window.show()
#  sys.exit(app.exec_())
#
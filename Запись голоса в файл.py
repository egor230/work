import sys, os
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt, QTimer, QTime, QDateTime
from PyQt5.QtGui import QFont

class TimerApp(QMainWindow):
 def __init__(self):
  super().__init__()
  
  # Настройки аудио
  self.sample_rate = 44100
  self.channels = 1
  self.save_path = "/mnt/807EB5FA7EB5E954/видео"
  self.recording_frames = []
  self.stream = None
  
  self.init_ui()
  self.init_timer()
 
 def init_ui(self):# Инициализация пользовательского интерфейса.
  self.setWindowTitle("Таймер с записью голоса")
  self.setGeometry(650, 400, 300, 200)
  
  # Создание и настройка метки времени
  self.time_label = QLabel("00:00:00", self)
  self.time_label.setFont(QFont('Arial', 20))
  self.time_label.setAlignment(Qt.AlignCenter)
  
  # Создание и настройка кнопки
  self.button = QPushButton("Пуск", self)
  self.button.setFont(QFont('Arial', 16))
  self.button.clicked.connect(self.toggle_timer)
  
  # Настройка макета
  layout = QVBoxLayout()
  layout.addWidget(self.time_label)
  layout.addSpacerItem(QSpacerItem(15, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
  layout.addWidget(self.button)
  
  container = QWidget()
  container.setLayout(layout)
  self.setCentralWidget(container)
 
 def init_timer(self):
  """Инициализация таймера"""
  self.timer = QTimer(self)
  self.timer.timeout.connect(self.update_time)
  self.elapsed_time = 0
  self.is_running = False
 
 def toggle_timer(self):
  """Переключение состояния таймера и записи"""
  if not self.is_running:
   self.button.setText("Стоп")
   self.timer.start(1000)
   self.is_running = True
   self.start_recording()
  else:
   self.button.setText("Пуск")
   self.timer.stop()
   self.is_running = False
   self.stop_recording()
 
 def update_time(self):
  """Обновление отображения времени"""
  self.elapsed_time += 1
  time = QTime(0, 0, 0).addSecs(self.elapsed_time)
  self.time_label.setText(time.toString("hh:mm:ss"))
 
 def audio_callback(self, indata, frames, time, status):
  """Обратный вызов для записи аудио"""
  if status:
   print(f"Статус обратного вызова аудио: {status}")
  if self.is_running:
   self.recording_frames.append(indata.copy())
 
 def start_recording(self):
  """Начало записи аудио"""
  try:
   # Проверка существования директории
   if not os.path.exists(self.save_path):
    os.makedirs(self.save_path)
   
   self.recording_frames = []
   self.stream = sd.InputStream(
    samplerate=self.sample_rate,
    channels=self.channels,
    callback=self.audio_callback,
    latency='low'
   )
   self.stream.start()
   print("Запись начата")
  except Exception as e:
   print(f"Ошибка при запуске записи: {e}")
   self.is_running = False
   self.button.setText("Пуск")
   self.timer.stop()
 
 def stop_recording(self):#Остановка записи аудио и сохранение файла"""
  try:
   if self.stream:
    self.stream.stop()
    self.stream.close()
    self.stream = None
   
   if self.recording_frames:
    recording_data = np.concatenate(self.recording_frames, axis=0)
    current_time = QDateTime.currentDateTime().toString("hh_mm_ss_dd_MM_yyyy")
    filename = os.path.join(self.save_path, f"{current_time}.wav")
    self.time_label.setText("00:00:00")
    # Проверка прав на запись
    if os.access(self.save_path, os.W_OK):
     write(filename, self.sample_rate, recording_data)
    else:
     print(f"Нет прав на запись в {self.save_path}")
    self.recording_frames = []
  except Exception as e:
   print(f"Ошибка при остановке записи: {e}")

if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = TimerApp()
 window.show()
 sys.exit(app.exec_())
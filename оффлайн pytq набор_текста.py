from PyQt6 import QtCore, QtWidgets, QtGui  # Изменено на PyQt6
from PyQt6.QtGui import QIcon, QAction  # Изменено на PyQt6
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QWidget, QDialog, QLabel, QVBoxLayout, QPushButton, QApplication  # Изменено на PyQt6
from write_text_for_tkinter import *
import whisper  # Добавьте импорт Whisper
from pathlib import Path

# Установка параметров для оптимизации CPU
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"
torch.set_num_threads(8)
source_id = get_webcam_source_id()      # ← твоя функция
set_mute("0", source_id)# Проверка и звука
#  models = {
#     "tiny": "https://huggingface.co/openai/whisper-tiny/resolve/main/pytorch_model.bin",
#     "base": "https://huggingface.co/openai/whisper-base/resolve/main/pytorch_model.bin",
#     "small": "https://huggingface.co/openai/whisper-small/resolve/main/pytorch_model.bin",
#     "medium": "https://huggingface.co/openai/whisper-medium/resolve/main/pytorch_model.bin",
#     "large": "https://huggingface.co/openai/whisper-large/resolve/main/pytorch_model.bin",
#  }
# Проверка наличия модели
models = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "large-v3-turbo"]
model_name = models[-1]

# Пример использования:
t = time.time()
model = whisper.load_model(model_name, download_root="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache", device="cpu")
print(time.time() - t)

class MyThread(QtCore.QThread):
  mysignal = QtCore.pyqtSignal(str)
  error_signal = QtCore.pyqtSignal(str)
  icon_signal = QtCore.pyqtSignal(str)
  mic_toggle_signal = QtCore.pyqtSignal(bool)

  def __init__(self, icon1_path, icon2_path, parent=None):
    super().__init__(parent)
    self.icon1_path = icon1_path
    self.icon2_path = icon2_path
    self.mic = True
    self._stop = False
    self.mic_toggle_signal.connect(self.set_mic_status)

  def set_mic_status(self, status):
    self.mic = status

  def run(self):
    while not self._stop:
      try:
        if self.mic:
         buffer = collections.deque()
         silence_time = 0
         last_speech_time = time.time()
         min_silence_duration = 1.1
         fs = 16 * 1000
         start = False
         self.icon_signal.emit(self.icon1_path)

         with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
          while True:
           audio_chunk, overflowed = stream.read(16096)
           mean_amp = np.mean(np.abs(audio_chunk)) * 100
           mean_amp = math.ceil(mean_amp)
           if mean_amp > 6:
             last_speech_time = time.time()
             silence_time = 0
             start = True
           if start:
             buffer.append(audio_chunk.astype(np.float32).flatten())
             if silence_time > min_silence_duration:
               array = np.concatenate(buffer)
               duration = len(array) / fs
               if duration > 3:
                self.icon_signal.emit(self.icon2_path)
                start = False
                break
             else:
               silence_time += time.time() - last_speech_time
               last_speech_time = time.time()
          if is_speech(0.0730, array):
            message = model.transcribe(array, fp16=False, language="ru", task="transcribe")["text"]
            buffer.clear()
            if message != " " and len(message) > 0:
              threading.Thread(target=process_text, args=(message,), daemon=True).start()
      except Exception as ex2:
        print(ex2)

  def stop(self):
    self._stop = True


class MyWindow(QtWidgets.QWidget):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.icon1_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/voice.png"
    self.icon2_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/stop.png"

    self.mic = True

    self.tray_icon = QSystemTrayIcon(QIcon(self.icon1_path), self)
    menu = QMenu()
    quit_action = QAction("Quit", self)
    quit_action.triggered.connect(self.quit_t)
    menu.addAction(quit_action)

    self.mythread = MyThread(self.icon1_path, self.icon2_path)
    self.mythread.icon_signal.connect(self.change_icon)
    self.mythread.error_signal.connect(print)

    self.tray_icon.setContextMenu(menu)
    self.tray_icon.setToolTip("ON")
    self.tray_icon.activated.connect(self.on_tray_icon_activated)
    self.tray_icon.show()

    self.mythread.start()

  def change_icon(self, icon_path):
    self.tray_icon.setIcon(QIcon(icon_path))
    self.tray_icon.show()

  def on_tray_icon_activated(self, reason):
    try:
      if reason == QSystemTrayIcon.ActivationReason.Trigger:
        self.mic = not self.mic
        self.mythread.mic_toggle_signal.emit(self.mic)
        self.tray_icon.setToolTip("ON" if self.mic else "OFF")
        set_mute("0" if self.mic else "1")
        new_icon = self.icon1_path if self.mic else self.icon2_path
        self.tray_icon.setIcon(QIcon(new_icon))
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
  sys.exit(app.exec())

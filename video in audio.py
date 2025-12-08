import sys, subprocess, os
from PyQt5.QtWidgets import (  QApplication, QWidget, QLabel, QLineEdit,
  QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox)
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"

class AudioExtractor(QWidget):
  def __init__(self):
    super().__init__()
    self.setWindowTitle("Audio Extractor from Video")
    self.setGeometry(650, 300, 550, 250)

    # Виджеты для выбора видеофайла
    self.video_label = QLabel("Video File:")
    self.video_path = QLineEdit()
    self.select_video_btn = QPushButton("Select Video File")
    self.select_video_btn.clicked.connect(self.select_video)

    # Виджеты для выбора выходного MP3
    self.output_label = QLabel("Output MP3 File:")
    self.output_path = QLineEdit()
    self.select_output_btn = QPushButton("Select Output Path")
    self.select_output_btn.clicked.connect(self.select_output)

    # Кнопка извлечения аудио
    self.extract_btn = QPushButton("Ok")
    self.extract_btn.clicked.connect(self.extract_audio)

    # Лэйаут для строки ввода видеофайла
    video_layout = QHBoxLayout()
    video_layout.addWidget(self.video_path)
    video_layout.addWidget(self.select_video_btn)

    # Лэйаут для строки ввода выходного MP3
    output_layout = QHBoxLayout()
    output_layout.addWidget(self.output_path)
    output_layout.addWidget(self.select_output_btn)

    # Основной лэйаут
    layout = QVBoxLayout()
    layout.addWidget(self.video_label)
    layout.addLayout(video_layout)
    layout.addWidget(self.output_label)
    layout.addLayout(output_layout)
    layout.addWidget(self.extract_btn)

    self.setLayout(layout)

  def select_video(self):
    cmd = ['zenity', '--file-selection', '--file-filter=Video files | *.mp4 *.avi *.mkv *.mov *.flv']
    try:
      result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True)
      file_path = result.stdout.strip()
      if file_path:
        self.video_path.setText(file_path)       # Удаляем любое существующее расширение
        if '.' in file_path:
         file_path = file_path.rsplit('.', 1)[0]
        # Добавляем расширение .mp3
        file_path += '.mp3'
        self.output_path.setText(file_path)
    except subprocess.CalledProcessError:
      QMessageBox.warning(self, "Error", "Failed to select video file.")

  def select_output(self):
    cmd = ['zenity', '--file-selection', '--save', '--confirm-overwrite', '--file-filter=MP3 files | *.mp3']
    try:
      result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True)
      file_path = result.stdout.strip()
      if file_path:
       if not file_path.endswith('.mp3'):
         file_path += '.mp3'
       self.output_path.setText(file_path)
    except subprocess.CalledProcessError:
      QMessageBox.warning(self, "Error", "Failed to select output path.")

  def extract_audio(self):
    input_file = self.video_path.text()
    output_file = self.output_path.text()
    if not input_file or not output_file:
      QMessageBox.warning(self, "Error", "Please select both input video and output MP3 paths.")
      return
    try:
      command = ['ffmpeg', '-i', input_file, '-vn', '-acodec', 'libmp3lame', '-q:a', '2', output_file]
      subprocess.run(command, check=True)
      QMessageBox.information(self, "Success", "Audio extracted successfully!")
    except subprocess.CalledProcessError as e:
      QMessageBox.critical(self, "Error", f"Failed to extract audio: {e}")
    except FileNotFoundError:
      QMessageBox.critical(self, "Error", "ffmpeg is not installed or not found in PATH.")

if __name__ == "__main__":
  app = QApplication(sys.argv)
  window = AudioExtractor()
  window.show()
  sys.exit(app.exec_())

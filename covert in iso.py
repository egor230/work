import sys
import subprocess
import os
from pathlib import Path
from PyQt6.QtWidgets import (
 QApplication, QWidget, QVBoxLayout, QPushButton,
 QLabel, QMessageBox, QProgressBar, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class ISOConverterThread(QThread):
 log_signal = pyqtSignal(str)
 finished_signal = pyqtSignal(bool)
 
 def __init__(self, source_dir, output_path):
  super().__init__()
  self.source_dir = source_dir
  self.output_path = output_path
 
 def run(self):
  try:
   self.log_signal.emit("Начинаю создание образа...")
   # Команда для создания ISO
   # -o : выходной файл
   # -R : Rock Ridge (поддержка длинных имен)
   # -J : Joliet (совместимость)
   cmd = ['genisoimage', '-o', self.output_path, '-R', '-J', self.source_dir]
   
   process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
   for line in process.stdout:
    self.log_signal.emit(line.strip())
   
   process.wait()
   if process.returncode == 0:
    self.log_signal.emit("Успешно создано!")
    self.finished_signal.emit(True)
   else:
    self.log_signal.emit("Ошибка при создании образа.")
    self.finished_signal.emit(False)
  except Exception as e:
   self.log_signal.emit(f"Критическая ошибка: {e}")
   self.finished_signal.emit(False)


class SimpleISOConverter(QWidget):
 def __init__(self):
  super().__init__()
  self.init_ui()
 
 def init_ui(self):
  self.setWindowTitle('ISO Creator')
  self.setFixedSize(500, 400)
  layout = QVBoxLayout()
  
  self.btn_select = QPushButton('Выбрать папку с игрой')
  self.btn_select.clicked.connect(self.select_folder)
  layout.addWidget(self.btn_select)
  
  self.status_label = QLabel('Папка не выбрана')
  layout.addWidget(self.status_label)
  
  self.log_output = QTextEdit()
  self.log_output.setReadOnly(True)
  layout.addWidget(self.log_output)
  
  self.btn_start = QPushButton('Создать ISO')
  self.btn_start.setEnabled(False)
  self.btn_start.clicked.connect(self.start_process)
  layout.addWidget(self.btn_start)
  
  self.setLayout(layout)
 
 def select_folder(self):
  # Используем zenity для выбора папки
  cmd = ['zenity', '--file-selection', '--directory', '--title=Выберите папку с игрой']
  result = subprocess.run(cmd, capture_output=True, text=True)
  if result.returncode == 0:
   self.source_dir = result.stdout.strip()
   self.status_label.setText(f'Выбрано: {self.source_dir}')
   self.btn_start.setEnabled(True)
 
 def start_process(self):
  # Выбор места сохранения
  cmd = ['zenity', '--file-selection', '--save', '--confirm-overwrite', '--filename=game.iso']
  result = subprocess.run(cmd, capture_output=True, text=True)
  if result.returncode == 0:
   self.output_path = result.stdout.strip()
   self.btn_start.setEnabled(False)
   self.worker = ISOConverterThread(self.source_dir, self.output_path)
   self.worker.log_signal.connect(self.log_output.append)
   self.worker.finished_signal.connect(lambda: self.btn_start.setEnabled(True))
   self.worker.start()


if __name__ == '__main__':
 app = QApplication(sys.argv)
 win = SimpleISOConverter()
 win.show()
 sys.exit(app.exec())
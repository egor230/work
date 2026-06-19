import sys
import subprocess
import os
import platform

from PyQt5.QtWidgets import (
 QApplication, QWidget, QVBoxLayout, QHBoxLayout,
 QLabel, QLineEdit, QPushButton, QProgressBar,
 QTextEdit, QMessageBox
)
from PyQt5.QtCore import QProcess, QTimer


class NuitkaCompiler(QWidget):
 def __init__(self):
  super().__init__()
  self.setWindowTitle("Nuitka Compiler GUI (Linux + Zenity)")
  self.setGeometry(650, 300, 600, 450)

  # --- Инициализация QProcess и QTimer ---
  self.process = QProcess()
  self.process.readyReadStandardOutput.connect(self.update_log)
  self.process.readyReadStandardError.connect(self.update_log)
  self.process.finished.connect(self.compile_finished)

  self.progress_timer = QTimer()
  self.progress_timer.timeout.connect(self.update_progress)

  self.init_ui()

 def init_ui(self):
  # --- Создание Виджетов ---

  # Виджеты для выбора Python-файла
  self.python_label = QLabel("Python File:")
  self.python_path = QLineEdit()
  self.select_python_btn = QPushButton("Select .py File (Zenity)")
  self.select_python_btn.clicked.connect(self.select_python_file)

  # Виджеты для выбора выходного файла
  self.output_label = QLabel("Output Path (Folder/Binary Name):")
  self.output_path = QLineEdit()
  self.select_output_btn = QPushButton("Select Output (Zenity)")
  self.select_output_btn.clicked.connect(self.select_output_file)

  # Кнопка компиляции
  self.compile_btn = QPushButton("✨ Start Compilation (Nuitka)")
  self.compile_btn.clicked.connect(self.compile)

  # Прогресс-бар
  self.progress_bar = QProgressBar()
  self.progress_bar.setValue(0)
  self.progress_bar.setTextVisible(True)
  self.progress_bar.setFormat("Status: Idle")

  # Текстовое поле для лога
  self.log_text = QTextEdit()
  self.log_text.setReadOnly(True)

  # --- Создание Лэйаутов ---
  python_layout = QHBoxLayout()
  python_layout.addWidget(self.python_path)
  python_layout.addWidget(self.select_python_btn)

  output_layout = QHBoxLayout()
  output_layout.addWidget(self.output_path)
  output_layout.addWidget(self.select_output_btn)

  main_layout = QVBoxLayout()
  main_layout.addWidget(self.python_label)
  main_layout.addLayout(python_layout)
  main_layout.addWidget(self.output_label)
  main_layout.addLayout(output_layout)

  main_layout.addWidget(self.compile_btn)
  main_layout.addWidget(self.progress_bar)
  main_layout.addWidget(QLabel("Compilation Log:"))
  main_layout.addWidget(self.log_text)

  self.setLayout(main_layout)

 def run_zenity_dialog(self, cmd_args):
  """
  Общая функция для выполнения команды Zenity через subprocess.
  Возвращает выбранный путь или None, если пользователь отменил или Zenity не найден.
  """
  # Преобразуем аргументы в список, который начинает с 'zenity'
  cmd = ['zenity'] + cmd_args

  try:
   # Запускаем команду
   result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True, stderr=subprocess.PIPE)
   # Zenity возвращает выбранный путь на stdout
   file_path = result.stdout.strip()
   return file_path

  except subprocess.CalledProcessError as e:
   # Код 1 обычно означает 'Отмена'
   if e.returncode == 1:
    return None

   # Обработка других ошибок Zenity
   QMessageBox.critical(self, "Zenity Error", f"Zenity exited with error code {e.returncode}.\nDetails: {e.stderr.strip()}")
   return None

  except FileNotFoundError:
   QMessageBox.critical(self, "Error", "Zenity command not found. Please ensure Zenity is installed on your system.")
   return None

 def select_python_file(self):
  """
  Использует Zenity для выбора существующего Python-файла.
  Используется --file-selection (без --save).
  """
  # Команда Zenity для выбора файла (открытия)
  cmd_args = [
   '--file-selection',
   '--title=Select Python File',
   '--file-filter=Python Files (*.py)',
   '--file-filter=All Files (*)'
  ]

  file_path = self.run_zenity_dialog(cmd_args)

  if file_path:
   self.python_path.setText(file_path)

   # Автоматически задать выходной путь (без расширения для Linux)
   base_name = os.path.basename(file_path).rsplit('.', 1)[0]
   output_dir = os.path.dirname(file_path)
   output_path = os.path.join(output_dir, base_name)

   self.output_path.setText(output_path)

 def select_output_file(self):
  """
  Использует Zenity для выбора пути сохранения исполняемого файла.
  Используются аргументы Zenity, которые вы указали для сохранения.
  """
  # Команда Zenity для сохранения файла
  # Использование --file-filter для указания типа исполняемого файла (для наглядности)
  cmd_args = [
   '--file-selection',
   '--save',
   '--confirm-overwrite',
   '--title=Save Executable Path',
   '--file-filter=Binary Executable (*)',
   '--file-filter=All Files (*)'
  ]

  file_path = self.run_zenity_dialog(cmd_args)

  if file_path:
   self.output_path.setText(file_path)

 def check_nuitka_installed(self):
  """Проверяет, установлен ли Nuitka."""
  try:
   subprocess.run(
    ["nuitka", "--version"],
    check=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
   )
   return True
  except (subprocess.CalledProcessError, FileNotFoundError):
   return False

 def compile(self):
  """Собирает команду Nuitka и запускает процесс компиляции."""
  input_file = self.python_path.text()
  output_file = self.output_path.text()

  # 1. Проверка путей
  if not input_file or not output_file:
   QMessageBox.warning(self, "Error", "Please select both input and output paths.")
   return

  # 2. Проверка Nuitka
  if not self.check_nuitka_installed():
   QMessageBox.critical(self, "Error", "Nuitka is not installed or not in PATH. Please install it first (pip install nuitka).")
   return

  # 3. Подготовка команды (Linux-стиль)
  output_dir = os.path.dirname(output_file)
  output_filename = os.path.basename(output_file)

  if not output_dir:
   output_dir = "."

  command = [
   "nuitka",
   "--onefile",
   "--output-dir=" + output_dir,
   "--output-filename=" + output_filename,
   "--standalone",
   "--show-progress",
   input_file
  ]

  # 4. Запуск компиляции
  self.log_text.clear()
  self.log_text.append(f"Starting compilation...")
  self.log_text.append(f"Command: {' '.join(command)}\n")

  self.progress_bar.setValue(5)
  self.progress_bar.setFormat("Status: Compiling...")
  self.compile_btn.setEnabled(False)

  # Запуск таймера для эмуляции прогресса
  self.progress_timer.start(750)

  # Запуск внешнего процесса
  self.process.start(command[0], command[1:])

 def update_log(self):
  """Считывает вывод (stdout и stderr) из QProcess и отображает в логе."""
  # Используем 'ignore' для обработки возможных не-UTF-8 символов в выводе
  output_data = self.process.readAllStandardOutput().data().decode("utf-8", errors='ignore')
  if output_data:
   self.log_text.append(output_data.strip())

  error_data = self.process.readAllStandardError().data().decode("utf-8", errors='ignore')
  if error_data:
   self.log_text.append(f"LOG/WARNING: {error_data.strip()}")

 def update_progress(self):
  """Эмуляция прогресса, пока процесс активен."""
  current_value = self.progress_bar.value()
  if current_value < 90:
   self.progress_bar.setValue(current_value + 3)

 def compile_finished(self, exit_code, exit_status):
  """Обрабатывает завершение процесса компиляции."""
  self.progress_timer.stop()
  self.compile_btn.setEnabled(True)
  self.progress_bar.setValue(100)

  if exit_code == 0:
   self.progress_bar.setFormat("Status: Success (Code 0)")
   QMessageBox.information(self, "Success", "Compilation completed successfully!")
   self.log_text.append("\n>>> Compilation finished successfully! <<<")
  else:
   self.progress_bar.setFormat("Status: Failed (Code {})".format(exit_code))
   QMessageBox.critical(self, "Error", "Compilation failed! Check the log for details.")
   self.log_text.append("\n!!! Compilation FAILED with exit code: {} !!!".format(exit_code))
   self.log_text.append("Please check Nuitka/Python installation and file paths.")


# --- Запуск программы ---
if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = NuitkaCompiler()
 window.show()
 sys.exit(app.exec_())
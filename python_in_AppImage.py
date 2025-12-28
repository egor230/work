import sys, os, shutil, subprocess, glob, tempfile;
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QLineEdit, QMessageBox, QTextEdit, QComboBox, QHBoxLayout, QGroupBox, QFrame, QSizePolicy, QCheckBox;
from PyQt6.QtCore import Qt, QSize;
from PyQt6.QtGui import QFont, QIcon, QPixmap


class CompilerApp(QWidget):
 def __init__(self):
  super().__init__()
  self.compiler_methods = {
   "Nuitka": self.compile_with_nuitka,
   "PyInstaller": self.compile_with_pyinstaller,
   "AppImage (Linux)": self.compile_as_appimage
  }

  self.size_info = {
   "Nuitka": "Ожидаемый размер: ~50-150 МБ (высокая оптимизация)",
   "PyInstaller": "Ожидаемый размер: ~100-300 МБ (стандарт)",
   "AppImage (Linux)": "Ожидаемый размер: ~150-400 МБ (полный пакет)"
  }

  self.init_ui()
  self.apply_light_theme()

 def apply_light_theme(self):
  style_sheet = """
      QWidget { background-color: #f5f7fa; color: #2c3e50; font-family: 'Segoe UI', sans-serif; font-size: 10pt; }
      QGroupBox { border: 2px solid #d1d9e6; border-radius: 8px; margin-top: 10px; padding-top: 15px; font-weight: bold; color: #3498db; background-color: #ffffff; }
      QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; }
      QLineEdit { border: 2px solid #d1d9e6; border-radius: 6px; padding: 8px; background-color: #ffffff; }
      QPushButton { border: 2px solid #d1d9e6; border-radius: 6px; padding: 8px 15px; background: #e8ecf1; font-weight: bold; }
      QPushButton#compileButton { background: #2ecc71; color: white; min-height: 40px; }
      QTextEdit { background-color: #ffffff; border: 2px solid #d1d9e6; font-family: 'Monospace'; }
    """
  self.setStyleSheet(style_sheet)
  self.btn_compile.setObjectName("compileButton")

 def init_ui(self):
  self.setWindowTitle('Python Compiler Pro for Linux')
  self.setGeometry(300, 200, 950, 800)
  layout = QVBoxLayout()
  layout.setSpacing(10)

  # Выбор компилятора
  comp_box = QGroupBox("Настройки компиляции")
  comp_layout = QVBoxLayout()
  self.combo_compiler = QComboBox()
  self.combo_compiler.addItems(list(self.compiler_methods.keys()))
  self.combo_compiler.currentTextChanged.connect(self.update_compiler_info)
  self.size_label = QLabel()
  self.size_label.setStyleSheet("color: #27ae60; font-weight: bold;")
  comp_layout.addWidget(QLabel("Инструмент:"))
  comp_layout.addWidget(self.combo_compiler)
  comp_layout.addWidget(self.size_label)
  comp_box.setLayout(comp_layout)
  layout.addWidget(comp_box)

  # Выбор файлов
  file_box = QGroupBox("Исходные данные")
  file_layout = QVBoxLayout()

  # Скрипт
  h_file = QHBoxLayout()
  self.input_file = QLineEdit()
  self.input_file.setPlaceholderText('Выберите .py файл...')
  btn_file = QPushButton('Обзор')
  btn_file.clicked.connect(self.browse_file)
  h_file.addWidget(self.input_file)
  h_file.addWidget(btn_file)
  file_layout.addLayout(h_file)

  # Имя
  self.input_appname = QLineEdit()
  self.input_appname.setPlaceholderText('Название приложения')
  file_layout.addWidget(self.input_appname)

  # Иконка
  h_icon = QHBoxLayout()
  self.input_icon = QLineEdit()
  self.input_icon.setPlaceholderText('Путь к иконке (.png, .ico)...')
  btn_icon = QPushButton('Иконка')
  btn_icon.clicked.connect(self.browse_icon)
  h_icon.addWidget(self.input_icon)
  h_icon.addWidget(btn_icon)
  file_layout.addLayout(h_icon)

  file_box.setLayout(file_layout)
  layout.addWidget(file_box)

  # Лог
  self.log_output = QTextEdit()
  self.log_output.setReadOnly(True)
  layout.addWidget(QLabel("Лог процесса:"))
  layout.addWidget(self.log_output)

  self.btn_compile = QPushButton('Начать процесс сборки')
  self.btn_compile.clicked.connect(self.run_compiler)
  layout.addWidget(self.btn_compile)

  self.setLayout(layout)
  self.update_compiler_info(self.combo_compiler.currentText())

 def update_compiler_info(self, compiler):
  self.size_label.setText(self.size_info.get(compiler, ""))

 def log(self, message):
  self.log_output.append(message)
  QApplication.processEvents()

 def browse_file(self):
  fname, _ = QFileDialog.getOpenFileName(self, 'Скрипт', os.getcwd(), "Python (*.py)")
  if fname:
   self.input_file.setText(fname)
   self.input_appname.setText(os.path.splitext(os.path.basename(fname))[0])

 def browse_icon(self):
  fname, _ = QFileDialog.getOpenFileName(self, 'Иконка', os.getcwd(), "Icons (*.png *.ico)")
  if fname: self.input_icon.setText(fname)

 def get_file_size_mb(self, path):
  return round(os.path.getsize(path) / (1024 * 1024), 2) if os.path.exists(path) else 0

 def run_compiler(self):
  script = self.input_file.text().strip()
  if not script or not os.path.exists(script):
   QMessageBox.warning(self, "Ошибка", "Укажите путь к скрипту!")
   return
  self.log_output.clear()
  self.compiler_methods[self.combo_compiler.currentText()](script)

 def compile_with_nuitka(self, script):
  name = self.input_appname.text() or "app"
  icon = self.input_icon.text().strip()
  cmd = [sys.executable, "-m", "nuitka", "--standalone", "--onefile", "--remove-output", f"--output-filename={name}"]
  if icon: cmd.append(f"--linux-icon={icon}")
  cmd.append(script)
  self.execute_proc(cmd, name)

 def compile_with_pyinstaller(self, script):
  name = self.input_appname.text() or "app"
  icon = self.input_icon.text().strip()
  cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--clean", f"--name={name}"]
  if icon: cmd.extend(["--icon", icon])
  cmd.append(script)
  self.execute_proc(cmd, name)

 def compile_as_appimage(self, script):
  self.log("Для AppImage создается базовый бинарник через PyInstaller...")
  self.compile_with_pyinstaller(script)

 def execute_proc(self, cmd, app_name):
  try:
   self.log(f"Команда: {' '.join(cmd)}")
   process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
   for line in process.stdout: self.log(line.strip())
   process.wait()

   dist_file = os.path.join(os.getcwd(), "dist", app_name)
   final_file = os.path.join(os.getcwd(), app_name)

   if os.path.exists(dist_file):
    if os.path.exists(final_file): os.remove(final_file)
    shutil.move(dist_file, final_file)

    # Полная очистка
    for folder in ["dist", "build"]:
     if os.path.exists(folder): shutil.rmtree(folder)
    for spec in glob.glob("*.spec"): os.remove(spec)

    size = self.get_file_size_mb(final_file)
    self.log(f"Успех! Размер файла: {size} МБ. Путь: {final_file}")
    QMessageBox.information(self, "Готово", f"Сборка завершена!\nРазмер: {size} МБ")
   else:
    self.log("Ошибка: Сборка не удалась, файл в 'dist' не найден.")
  except Exception as e:
   self.log(f"Критическая ошибка: {str(e)}")


if __name__ == '__main__':
 app = QApplication(sys.argv)
 ex = CompilerApp()
 ex.show()
 sys.exit(app.exec())
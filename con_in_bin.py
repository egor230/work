import sys
import os
import time
import shutil
import subprocess
import glob
from PIL import Image
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                             QLabel, QFileDialog, QLineEdit, QMessageBox, QTextEdit)
from PyQt6.QtGui import QPalette, QColor


class CompilerApp(QWidget):
 def __init__(self):
  super().__init__()
  self.init_ui()
  self.apply_light_theme()  # Применяем стили после инициализации UI

 def apply_light_theme(self):
  # Современный и минималистичный стиль (Вариант 1)
  style_sheet = """
      QWidget {
        background-color: #F8F8F8; /* Мягкий светлый фон */
        color: #333333; /* Темный текст для хорошей контрастности */
        font-family: Arial, sans-serif;
        font-size: 10pt;
      }

      QLabel {
        color: #1A1A1A; 
        padding-top: 5px;
      }

      QLineEdit, QTextEdit {
        border: 1px solid #C0C0C0; /* Четкая граница */
        padding: 8px;
        border-radius: 4px;
        background-color: #FFFFFF;
      }

      QPushButton {
        background-color: #EFEFEF;
        border: 1px solid #D0D0D0;
        padding: 10px 15px;
        border-radius: 4px;
        min-height: 30px;
      }

      QPushButton:hover {
        background-color: #E0E0E0;
      }

      /* Специальный стиль для кнопки "Собрать" */
      QPushButton#compileButton { 
        background-color: #007BFF; 
        color: white; 
        font-weight: bold;
        border: none;
      }

      QPushButton#compileButton:hover {
        background-color: #0056B3;
      }
    """
  self.setStyleSheet(style_sheet)
  self.btn_compile.setObjectName("compileButton")

 def init_ui(self):
  self.setWindowTitle('Python to EXE/Bin Compiler')
  self.setGeometry(300, 300, 500, 400)

  layout = QVBoxLayout()

  self.label_file = QLabel('Выберите Python файл (.py):')
  layout.addWidget(self.label_file)

  self.input_file = QLineEdit()
  layout.addWidget(self.input_file)

  self.btn_browse_file = QPushButton('Обзор файла')
  self.btn_browse_file.clicked.connect(self.browse_file)
  layout.addWidget(self.btn_browse_file)

  self.label_icon = QLabel('Выберите иконку (необязательно, .png, .jpg):')
  layout.addWidget(self.label_icon)

  self.input_icon = QLineEdit()
  layout.addWidget(self.input_icon)

  self.btn_browse_icon = QPushButton('Обзор иконки')
  self.btn_browse_icon.clicked.connect(self.browse_icon)
  layout.addWidget(self.btn_browse_icon)

  self.log_output = QTextEdit()
  self.log_output.setReadOnly(True)
  layout.addWidget(self.log_output)

  self.btn_compile = QPushButton('Собрать проект')
  self.btn_compile.clicked.connect(self.run_compiler)
  layout.addWidget(self.btn_compile)

  self.setLayout(layout)

 def log(self, message):
  self.log_output.append(message)
  QApplication.processEvents()

 def browse_file(self):
  fname, _ = QFileDialog.getOpenFileName(self, 'Выбрать скрипт', os.getcwd(), "Python Files (*.py)")
  if fname:
   self.input_file.setText(fname)

 def browse_icon(self):
  fname, _ = QFileDialog.getOpenFileName(self, 'Выбрать иконку', os.getcwd(), "Image Files (*.png *.jpg *.jpeg *.bmp *.ico)")
  if fname:
   self.input_icon.setText(fname)

 def convert_to_ico(self, input_path):
  if input_path and not input_path.lower().endswith('.ico'):
   try:
    img = Image.open(input_path)
    output_path = os.path.splitext(input_path)[0] + '.ico'
    img.save(output_path, format='ICO')
    return output_path
   except Exception as e:
    self.log(f"Ошибка конвертации иконки: {e}")
    return None
  return input_path

 def run_compiler(self):
  py_scrypt = self.input_file.text()
  if not py_scrypt:
   QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите файл скрипта!")
   return

  self.log("Начинаем сборку...")

  icon_path = self.input_icon.text()
  final_icon = None
  if icon_path:
   final_icon = self.convert_to_ico(icon_path)

  home = str(os.getcwd())
  cmd = ['pyinstaller', '--onefile', '--clean', '--distpath', f'{home}/dist', '--workpath', f'{home}/build', py_scrypt]

  if final_icon:
   cmd.insert(2, f'--icon={final_icon}')

  self.log(f"Выполняем команду: {' '.join(cmd)}")

  try:
   subprocess.check_call(cmd)
   self.log("PyInstaller завершил работу.")
  except subprocess.CalledProcessError as e:
   self.log(f"Ошибка сборки: {e}")
   return

  script_name = os.path.basename(py_scrypt)
  name_file = os.path.splitext(script_name)[0]

  compiled_file_path = os.path.join(home, "dist", name_file)
  dest_dir = home

  # Исправлено: используем dest_dir (текущую директорию)
  bash_script_content = (
   "#!/bin/bash\n"
   f"gnome-terminal -- bash -c 'cd \"{dest_dir}\";\n"
   f"./{name_file};\n"
   "exit;\n"
   "exec bash'"
  )

  dest_exe_path = os.path.join(dest_dir, name_file)
  sh_file_path = os.path.join(dest_dir, f"{name_file}.sh")

  try:
   with open(sh_file_path, 'w') as f:
    f.write(bash_script_content)
   os.chmod(sh_file_path, 0o755)
   self.log(f"Создан скрипт запуска: {sh_file_path}")

   if os.path.exists(dest_exe_path):
    os.remove(dest_exe_path)

   shutil.move(compiled_file_path, dest_exe_path)
   self.log(f"Файл перемещен в: {dest_exe_path}")

   if os.path.exists(f'{home}/dist'):
    shutil.rmtree(f'{home}/dist')
   if os.path.exists(f'{home}/build'):
    shutil.rmtree(f'{home}/build')

   spec_file = f"{name_file}.spec"
   if os.path.exists(spec_file):
    os.remove(spec_file)

   self.log("Временные файлы очищены.")
   QMessageBox.information(self, "Успех", f"Сборка завершена!\nИсполняемый файл и скрипт находятся в: {dest_dir}")

  except Exception as e:
   self.log(f"Ошибка при перемещении или очистке: {e}")


if __name__ == '__main__':
 app = QApplication(sys.argv)
 ex = CompilerApp()
 ex.show()
 sys.exit(app.exec())
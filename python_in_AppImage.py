import sys
import os
import time
import shutil
import subprocess
import requests
from PIL import Image
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                             QLabel, QFileDialog, QLineEdit, QMessageBox, QTextEdit)
from PyQt6.QtGui import QPalette, QColor

class CompilerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
        os.makedirs(self.resources_dir, exist_ok=True)
        self.init_ui()
        self.apply_light_theme()

    def apply_light_theme(self):
        style_sheet = """
          QWidget {
            background-color: #F8F8F8;
            color: #333333;
            font-family: Arial, sans-serif;
            font-size: 10pt;
          }
          QLabel {
            color: #1A1A1A;
            padding-top: 5px;
          }
          QLineEdit, QTextEdit {
            border: 1px solid #C0C0C0;
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
          QPushButton#compileButton {
            background-color: #28A745;
            color: white;
            font-weight: bold;
            border: none;
          }
          QPushButton#compileButton:hover {
            background-color: #218838;
          }
        """
        self.setStyleSheet(style_sheet)
        self.btn_compile.setObjectName("compileButton")

    def init_ui(self):
        self.setWindowTitle('Python to AppImage Compiler (Auto-Install Tool)')
        self.setGeometry(300, 300, 550, 500)
        layout = QVBoxLayout()

        self.label_file = QLabel('Выберите Python файл (.py):')
        layout.addWidget(self.label_file)
        self.input_file = QLineEdit()
        layout.addWidget(self.input_file)
        self.btn_browse_file = QPushButton('Обзор файла')
        self.btn_browse_file.clicked.connect(self.browse_file)
        layout.addWidget(self.btn_browse_file)

        self.label_icon = QLabel('Выберите иконку (PNG/JPG/SVG):')
        layout.addWidget(self.label_icon)
        self.input_icon = QLineEdit()
        layout.addWidget(self.input_icon)
        self.btn_browse_icon = QPushButton('Обзор иконки')
        self.btn_browse_icon.clicked.connect(self.browse_icon)
        layout.addWidget(self.btn_browse_icon)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.btn_compile = QPushButton('Собрать AppImage')
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
        fname, _ = QFileDialog.getOpenFileName(self, 'Выбрать иконку', os.getcwd(), "Image Files (*.png *.jpg *.jpeg *.svg)")
        if fname:
            self.input_icon.setText(fname)

    def ensure_pyinstaller(self):
        self.log("Проверка PyInstaller...")
        try:
            import pyinstaller
            self.log("PyInstaller уже установлен.")
            return True
        except ImportError:
            self.log("PyInstaller не найден. Устанавливаю через pip...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
                self.log("PyInstaller успешно установлен.")
                return True
            except Exception as e:
                self.log(f"Ошибка установки PyInstaller: {e}")
                return False

    def ensure_appimagetool(self):
        # Сначала ищем в встроенной папке resources
        local_tool = os.path.join(self.resources_dir, "appimagetool-x86_64.AppImage")
        if os.path.exists(local_tool):
            os.chmod(local_tool, 0o755)  # на всякий случай
            return local_tool

        # Ищем в PATH
        tool = shutil.which("appimagetool")
        if tool:
            return tool

        self.log("appimagetool не найден. Загружаю свежую версию...")
        url = "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(local_tool, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            os.chmod(local_tool, 0o755)
            self.log(f"appimagetool успешно загружен и сохранён в {local_tool}")
            return local_tool
        except Exception as e:
            self.log(f"Ошибка загрузки appimagetool: {e}")
            return None

    def run_compiler(self):
        py_script = self.input_file.text().strip()
        icon_path = self.input_icon.text().strip()

        if not py_script or not os.path.isfile(py_script):
            QMessageBox.warning(self, "Ошибка", "Выберите корректный Python-файл!")
            return
        if not icon_path or not os.path.isfile(icon_path):
            QMessageBox.warning(self, "Ошибка", "Выберите корректную иконку!")
            return

        if not self.ensure_pyinstaller():
            QMessageBox.critical(self, "Ошибка", "Не удалось установить PyInstaller!")
            return

        tool_path = self.ensure_appimagetool()
        if not tool_path:
            QMessageBox.critical(self, "Ошибка", "Не удалось найти или загрузить appimagetool!")
            return

        home = os.getcwd()
        script_name = os.path.basename(py_script)
        name_file = os.path.splitext(script_name)[0]
        app_dir = os.path.join(home, f"{name_file}.AppDir")

        self.log("Этап 1: Сборка исполняемого файла через PyInstaller...")
        cmd = [
            "pyinstaller",
            "--onefile",
            "--clean",
            "--distpath", os.path.join(home, "dist"),
            py_script
        ]

        try:
            subprocess.check_call(cmd)
        except Exception as e:
            self.log(f"Ошибка PyInstaller: {e}")
            QMessageBox.critical(self, "Ошибка", "Сборка PyInstaller провалилась!")
            return

        executable_path = os.path.join(home, "dist", name_file)

        try:
            self.log("Этап 2: Создание AppDir...")
            if os.path.exists(app_dir):
                shutil.rmtree(app_dir)
            os.makedirs(os.path.join(app_dir, "usr/bin"), exist_ok=True)

            shutil.move(executable_path, os.path.join(app_dir, "usr/bin", name_file))

            # Иконка
            icon_dest = os.path.join(app_dir, f"{name_file}.png")
            img = Image.open(icon_path).convert("RGBA")
            img.save(icon_dest, "PNG")

            # .desktop файл
            desktop_path = os.path.join(app_dir, f"{name_file}.desktop")
            with open(desktop_path, "w") as f:
                f.write(f"[Desktop Entry]\n"
                        f"Name={name_file}\n"
                        f"Exec={name_file}\n"
                        f"Icon={name_file}\n"
                        f"Type=Application\n"
                        f"Categories=Utility;")

            # AppRun
            apprun_path = os.path.join(app_dir, "AppRun")
            with open(apprun_path, "w") as f:
                f.write(f'#!/bin/bash\n'
                        f'exec "$APPDIR/usr/bin/{name_file}" "$@"')
            os.chmod(apprun_path, 0o755)

            self.log("Этап 3: Финальная сборка AppImage...")
            env = os.environ.copy()
            env["ARCH"] = "x86_64"

            subprocess.check_call([tool_path, app_dir], env=env)

            final_appimage = f"{name_file}-x86_64.AppImage"
            self.log(f"Готово! Создан файл: {final_appimage}")

            # Очистка временных файлов
            shutil.rmtree(app_dir)
            if os.path.exists(os.path.join(home, "dist")):
                shutil.rmtree(os.path.join(home, "dist"))
            if os.path.exists(os.path.join(home, "build")):
                shutil.rmtree(os.path.join(home, "build"))
            spec_file = f"{name_file}.spec"
            if os.path.exists(spec_file):
                os.remove(spec_file)

            QMessageBox.information(self, "Успех", f"AppImage успешно создан!\n{final_appimage}")

        except Exception as e:
            self.log(f"Ошибка в процессе сборки: {e}")
            QMessageBox.critical(self, "Ошибка", "Произошла ошибка при создании AppImage.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = CompilerApp()
    ex.show()
    sys.exit(app.exec())
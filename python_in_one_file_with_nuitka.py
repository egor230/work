import sys
import os
import subprocess
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                             QLabel, QFileDialog, QLineEdit, QMessageBox, QTextEdit)

class CompilerApp(QWidget):
    def __init__(self):
        super().__init__()
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
        self.setWindowTitle('Python to Executable Compiler (Nuitka)')
        self.setGeometry(300, 300, 600, 400)
        layout = QVBoxLayout()

        self.label_file = QLabel('Выберите Python файл (.py):')
        layout.addWidget(self.label_file)
        self.input_file = QLineEdit()
        layout.addWidget(self.input_file)
        self.btn_browse_file = QPushButton('Обзор файла')
        self.btn_browse_file.clicked.connect(self.browse_file)
        layout.addWidget(self.btn_browse_file)

        self.label_options = QLabel('Дополнительные опции Nuitka (опционально):')
        layout.addWidget(self.label_options)
        self.input_options = QLineEdit()
        self.input_options.setPlaceholderText('Например: --noinclude-qt-plugins=all --remove-output')
        layout.addWidget(self.input_options)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.btn_compile = QPushButton('Скомпилировать в исполняемый файл')
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

    def ensure_nuitka(self):
        self.log("Проверка Nuitka...")
        try:
            import nuitka
            self.log("✓ Nuitka уже установлен")
            return True
        except ImportError:
            self.log("Nuitka не найден. Устанавливаю...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "nuitka"], 
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.log("✓ Nuitka успешно установлен")
                return True
            except Exception as e:
                self.log(f"✗ Ошибка установки Nuitka: {e}")
                return False

    def cleanup_old_files(self, name_file):
        """Очистка старых файлов сборки"""
        home = os.getcwd()
        dirs_to_remove = [
            os.path.join(home, f"{name_file}.build"),
            os.path.join(home, f"{name_file}.dist"),
            os.path.join(home, "build"),
            os.path.join(home, "dist"),
        ]
        
        for dir_path in dirs_to_remove:
            if os.path.exists(dir_path):
                self.log(f"Удаляю старую директорию: {dir_path}")
                try:
                    shutil.rmtree(dir_path, ignore_errors=True)
                except:
                    pass

    def run_compiler(self):
        py_script = self.input_file.text().strip()
        nuitka_options = self.input_options.text().strip()

        if not py_script or not os.path.isfile(py_script):
            QMessageBox.warning(self, "Ошибка", "Выберите корректный Python-файл!")
            return

        if not self.ensure_nuitka():
            QMessageBox.critical(self, "Ошибка", "Не удалось установить Nuitka!")
            return

        home = os.getcwd()
        script_name = os.path.basename(py_script)
        name_file = os.path.splitext(script_name)[0]
        
        # Очищаем старые файлы
        self.cleanup_old_files(name_file)
        
        self.log("=" * 60)
        self.log("Начинаю компиляцию с Nuitka...")
        self.log("=" * 60)

        # Базовые опции Nuitka для одного файла
        base_options = [
            sys.executable, "-m", "nuitka",
            "--standalone",          # Автономное приложение
            "--onefile",             # Один исполняемый файл
            "--follow-imports",      # Включить все импорты
            "--assume-yes-for-downloads",  # Автоподтверждение загрузок
            "--output-dir=dist",     # Папка для вывода
            "--remove-output",       # Удалить промежуточные файлы
            "--lto=yes",             # Оптимизация связывания
        ]
        
        # Автоматическое определение плагинов для PyQt
        if "PyQt6" in open(py_script, 'r').read():
            base_options.append("--plugin-enable=pyqt6")
            base_options.append("--include-qt-plugins=sensible,styles")
            self.log("✓ Обнаружен PyQt6, добавляю плагины")
        
        # Добавляем пользовательские опции
        if nuitka_options:
            user_opts = nuitka_options.split()
            base_options.extend(user_opts)
        
        # Добавляем имя исходного файла
        base_options.append(py_script)
        
        self.log(f"Команда Nuitka: {' '.join(base_options[3:])}")
        
        try:
            # Запускаем компиляцию
            process = subprocess.Popen(
                base_options,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Вывод логов в реальном времени
            for line in process.stdout:
                if line.strip():
                    self.log(line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                # Ищем созданный файл
                dist_dir = os.path.join(home, "dist")
                if os.path.exists(dist_dir):
                    # Ищем исполняемый файл
                    for file in os.listdir(dist_dir):
                        if not file.endswith('.py'):
                            exe_path = os.path.join(dist_dir, file)
                            if os.path.isfile(exe_path):
                                size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                                self.log("=" * 60)
                                self.log(f"✓ Компиляция успешно завершена!")
                                self.log(f"✓ Исполняемый файл: {exe_path}")
                                self.log(f"✓ Размер файла: {size_mb:.2f} MB")
                                self.log("=" * 60)
                                
                                QMessageBox.information(
                                    self, 
                                    "Успех", 
                                    f"Исполняемый файл успешно создан!\n\n"
                                    f"Путь: {exe_path}\n"
                                    f"Размер: {size_mb:.2f} MB\n\n"
                                    f"Файл готов к использованию."
                                )
                                return
                
                # Если не нашли в dist, ищем в текущей директории
                for file in os.listdir(home):
                    if file == name_file and os.access(file, os.X_OK):
                        size_mb = os.path.getsize(file) / (1024 * 1024)
                        self.log(f"✓ Исполняемый файл найден в текущей папке: {file}")
                        self.log(f"✓ Размер: {size_mb:.2f} MB")
                        
                        QMessageBox.information(
                            self, 
                            "Успех", 
                            f"Исполняемый файл создан!\n\n"
                            f"Файл: {file}\n"
                            f"Размер: {size_mb:.2f} MB"
                        )
                        return
                
                self.log("⚠ Исполняемый файл не найден в ожидаемых местах")
                QMessageBox.warning(self, "Внимание", 
                                  "Компиляция завершена, но файл не найден.\n"
                                  "Проверьте папку 'dist' или текущую директорию.")
            else:
                self.log(f"✗ Компиляция завершилась с ошибкой (код: {process.returncode})")
                QMessageBox.critical(self, "Ошибка", 
                                   "Компиляция завершилась с ошибкой.\n"
                                   "Проверьте логи выше.")
                
        except Exception as e:
            self.log(f"✗ Исключение при компиляции: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка при компиляции:\n\n{e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = CompilerApp()
    ex.show()
    sys.exit(app.exec())
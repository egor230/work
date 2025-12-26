import sys
import os
import shutil
import zipfile
import tempfile
import subprocess
import platform
from pathlib import Path
from PyQt6.QtWidgets import (
 QApplication, QWidget, QVBoxLayout, QPushButton,
 QLabel, QFileDialog, QLineEdit, QMessageBox,
 QTextEdit, QComboBox, QProgressBar, QHBoxLayout,
 QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon


class ExtractXISOThread(QThread):
 """Поток для работы с extract-xiso"""
 log_signal = pyqtSignal(str)
 progress_signal = pyqtSignal(int)
 finished_signal = pyqtSignal(bool, str)

 def __init__(self, source_path, output_path, use_extract_iso=True):
  super().__init__()
  self.source_path = source_path
  self.output_path = output_path
  self.use_extract_iso = use_extract_iso
  self.temp_dirs = []

 def log(self, message):
  self.log_signal.emit(message)

 def progress(self, value):
  self.progress_signal.emit(value)

 def cleanup_temp_dirs(self):
  """Очистка временных директорий"""
  for temp_dir in self.temp_dirs:
   if os.path.exists(temp_dir):
    try:
     shutil.rmtree(temp_dir)
     self.log(f"Удалена временная папка: {temp_dir}")
    except Exception as e:
     self.log(f"Ошибка удаления {temp_dir}: {e}")

 def find_extract_iso(self):
  """Поиск extract-xiso в системе"""
  self.log("Ищу extract-xiso в системе...")

  # Проверяем в PATH
  if platform.system() == "Windows":
   tool_name = "extract-xiso.exe"
  else:
   tool_name = "extract-xiso"

  # Ищем в PATH
  tool_path = shutil.which(tool_name)
  if tool_path:
   self.log(f"Найден extract-xiso: {tool_path}")
   return tool_path

  # Проверяем в стандартных местах
  possible_paths = []

  if platform.system() == "Windows":
   possible_paths = [
    r"C:\Program Files\extract-xiso\extract-xiso.exe",
    r"C:\Program Files (x86)\extract-xiso\extract-xiso.exe",
    r"C:\extract-xiso\extract-xiso.exe",
    os.path.join(os.path.dirname(__file__), "tools", "extract-xiso.exe"),
    os.path.join(os.environ.get('USERPROFILE', ''), "Downloads", "extract-xiso.exe"),
   ]
  elif platform.system() == "Linux":
   possible_paths = [
    "/usr/local/bin/extract-xiso",
    "/usr/bin/extract-xiso",
    "/usr/games/extract-xiso",
    os.path.expanduser("~/.local/bin/extract-xiso"),
    os.path.join(os.path.dirname(__file__), "tools", "extract-xiso"),
   ]
  elif platform.system() == "Darwin":  # macOS
   possible_paths = [
    "/usr/local/bin/extract-xiso",
    "/opt/homebrew/bin/extract-xiso",
    os.path.expanduser("~/.local/bin/extract-xiso"),
    os.path.join(os.path.dirname(__file__), "tools", "extract-xiso"),
   ]

  for path in possible_paths:
   if os.path.exists(path):
    self.log(f"Найден extract-xiso: {path}")
    return path

  # Проверяем в текущей директории
  current_dir_tool = os.path.join(os.path.dirname(__file__), tool_name)
  if os.path.exists(current_dir_tool):
   self.log(f"Найден extract-xiso в текущей директории: {current_dir_tool}")
   return current_dir_tool

  self.log("extract-xiso не найден в системе")
  return None

 def check_extract_iso_version(self, tool_path):
  """Проверяем версию extract-xiso"""
  try:
   cmd = [tool_path, "--version"]
   result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
   if result.returncode == 0:
    version_info = result.stdout.strip()
    self.log(f"Версия extract-xiso: {version_info}")
    return True
   else:
    # Пробуем без --version
    cmd = [tool_path, "-h"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
     self.log("extract-xiso работает (версия не определена)")
     return True
  except Exception as e:
   self.log(f"Ошибка проверки версии: {e}")
  return False

 def download_extract_iso(self):
  """Предлагаем скачать extract-xiso"""
  self.log("extract-xiso не найден в системе")
  self.log("Рекомендуется скачать с GitHub:")
  self.log("  https://github.com/XboxDev/extract-xiso/releases")

  if platform.system() == "Windows":
   self.log("Для Windows скачайте extract-xiso-win32.zip")
  elif platform.system() == "Linux":
   self.log("Для Linux соберите из исходников: make")
  elif platform.system() == "Darwin":
   self.log("Для macOS: brew install extract-xiso или соберите из исходников")

  return False

 def extract_zip_archive(self, zip_path, extract_to):
  """Распаковывает ZIP архив"""
  self.log(f"Распаковываю архив: {zip_path}")
  try:
   with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    total_files = len(zip_ref.namelist())
    for i, file_name in enumerate(zip_ref.namelist()):
     zip_ref.extract(file_name, extract_to)
     if i % 100 == 0:  # Обновляем прогресс каждые 100 файлов
      progress = 20 + (i / total_files) * 30
      self.progress(int(progress))

   self.log("Архив успешно распакован")
   return True
  except Exception as e:
   self.log(f"Ошибка распаковки ZIP: {e}")
   return False

 def find_game_files(self, directory):
  """Ищет игровые файлы в директории"""
  self.log("Ищу игровые файлы...")

  # Ищем default.xbe
  xbe_files = list(Path(directory).rglob('default.xbe'))
  if xbe_files:
   game_dir = xbe_files[0].parent
   self.log(f"Найден default.xbe в: {game_dir}")
   return str(game_dir)

  # Ищем другие .xbe файлы
  xbe_files = list(Path(directory).rglob('*.xbe'))
  if xbe_files:
   game_dir = xbe_files[0].parent
   self.log(f"Найден XBE файл: {xbe_files[0].name}")
   return str(game_dir)

  # Ищем .iso файлы
  iso_files = list(Path(directory).rglob('*.iso'))
  if iso_files:
   self.log(f"Найден ISO файл: {iso_files[0].name}")
   return str(iso_files[0])

  # Проверяем структуру папки Xbox
  possible_dirs = ['/', 'Game', 'DATA', 'VIDEO']
  for dir_name in possible_dirs:
   check_dir = os.path.join(directory, dir_name.lstrip('/'))
   if os.path.exists(check_dir):
    files = list(Path(check_dir).rglob('*'))
    if files:
     self.log(f"Найдена игровая структура в: {check_dir}")
     return check_dir

  self.log("Не найдены игровые файлы, использую всю папку")
  return directory

 def create_xiso_with_extract_iso(self, source_dir, output_path, tool_path):
  """Создает XISO с помощью extract-xiso"""
  self.log(f"Создаю XISO из: {source_dir}")

  try:
   # Создаем XISO
   cmd = [tool_path, "-c", source_dir, output_path]
   self.log(f"Команда: {' '.join(cmd)}")

   process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    universal_newlines=True
   )

   # Читаем вывод в реальном времени
   for line in process.stdout:
    if line.strip():
     self.log(f"extract-xiso: {line.strip()}")

   process.wait()

   if process.returncode == 0:
    self.log(f"XISO успешно создан: {output_path}")
    return True
   else:
    self.log(f"Ошибка extract-xiso (код {process.returncode})")
    return False

  except Exception as e:
   self.log(f"Ошибка создания XISO: {e}")
   return False

 def rebuild_iso_to_xiso(self, iso_path, output_path, tool_path):
  """Пересобирает ISO в XISO"""
  self.log(f"Пересобираю ISO в XISO: {iso_path}")

  try:
   # Создаем временную папку для извлечения
   extract_dir = tempfile.mkdtemp(prefix="xemu_extract_")
   self.temp_dirs.append(extract_dir)

   # Извлекаем ISO
   self.log(f"Извлекаю ISO в: {extract_dir}")
   extract_cmd = [tool_path, "-x", iso_path, "-d", extract_dir]

   process = subprocess.run(
    extract_cmd,
    capture_output=True,
    text=True,
    timeout=300  # 5 минут
   )

   if process.returncode != 0:
    self.log(f"Ошибка извлечения ISO: {process.stderr}")
    return False

   self.log("ISO успешно извлечен")

   # Ищем игровые файлы
   game_dir = self.find_game_files(extract_dir)

   # Создаем XISO
   return self.create_xiso_with_extract_iso(game_dir, output_path, tool_path)

  except subprocess.TimeoutExpired:
   self.log("Таймаут при извлечении ISO")
   return False
  except Exception as e:
   self.log(f"Ошибка пересборки ISO: {e}")
   return False

 def process_directory_to_xiso(self, source_dir, output_path, tool_path):
  """Обрабатывает директорию в XISO"""
  # Ищем игровые файлы
  game_dir = self.find_game_files(source_dir)
  return self.create_xiso_with_extract_iso(game_dir, output_path, tool_path)

 def run(self):
  """Основной метод потока"""
  try:
   self.progress(10)

   # Проверяем существование источника
   if not os.path.exists(self.source_path):
    self.log(f"Ошибка: источник не существует: {self.source_path}")
    self.finished_signal.emit(False, "Источник не существует")
    return

   # Проверяем выходной путь
   if not self.output_path:
    self.log("Ошибка: не указан выходной файл")
    self.finished_signal.emit(False, "Не указан выходной файл")
    return

   # Убеждаемся, что выходной файл имеет расширение .xiso
   if not self.output_path.lower().endswith('.xiso'):
    self.output_path = self.output_path + '.xiso'

   # Ищем extract-xiso
   if self.use_extract_iso:
    tool_path = self.find_extract_iso()
    if tool_path and self.check_extract_iso_version(tool_path):
     self.log("Использую extract-xiso для создания XISO")
     extract_iso_available = True
    else:
     self.log("extract-xiso не найден или не работает")
     self.download_extract_iso()
     extract_iso_available = False
   else:
    extract_iso_available = False

   # Обрабатываем в зависимости от типа источника
   source_path = self.source_path

   # Если это ZIP архив - распаковываем
   if zipfile.is_zipfile(source_path):
    self.progress(20)

    # Создаем временную папку для распаковки
    temp_dir = tempfile.mkdtemp(prefix="xemu_zip_")
    self.temp_dirs.append(temp_dir)
    self.log(f"Создана временная папка: {temp_dir}")

    # Распаковываем архив
    if not self.extract_zip_archive(source_path, temp_dir):
     self.finished_signal.emit(False, "Ошибка распаковки архива")
     return

    source_path = temp_dir
    self.progress(50)

   # Проверяем, что источник существует
   if not os.path.exists(source_path):
    self.log(f"Ошибка: источник не найден: {source_path}")
    self.finished_signal.emit(False, "Источник не найден после распаковки")
    return

   # Определяем тип источника
   if os.path.isdir(source_path):
    self.log("Обрабатываю папку с игрой...")
    if extract_iso_available:
     success = self.process_directory_to_xiso(source_path, self.output_path, tool_path)
    else:
     self.log("extract-xiso недоступен, использую альтернативные методы")
     # Здесь можно добавить альтернативные методы
     success = False

   elif source_path.lower().endswith('.iso'):
    self.log("Обрабатываю ISO файл...")
    if extract_iso_available:
     success = self.rebuild_iso_to_xiso(source_path, self.output_path, tool_path)
    else:
     # Просто копируем и переименовываем
     try:
      shutil.copy2(source_path, self.output_path)
      self.log(f"ISO скопирован как: {self.output_path}")
      success = True
     except Exception as e:
      self.log(f"Ошибка копирования ISO: {e}")
      success = False
   else:
    self.log("Неизвестный тип источника")
    success = False

   self.progress(90)

   # Очистка временных файлов
   self.log("Очищаю временные файлы...")
   self.cleanup_temp_dirs()

   self.progress(100)

   if success:
    self.log(f"Готово! XISO создан: {self.output_path}")
    self.finished_signal.emit(True, self.output_path)
   else:
    self.log("Ошибка создания XISO")
    self.finished_signal.emit(False, "Ошибка создания XISO")

  except Exception as e:
   self.log(f"Критическая ошибка: {e}")
   self.cleanup_temp_dirs()
   self.finished_signal.emit(False, f"Критическая ошибка: {e}")


class XISOConverter(QWidget):
 def __init__(self):
  super().__init__()
  self.worker_thread = None
  self.init_ui()

 def init_ui(self):
  self.setWindowTitle('XISO Creator for xemu - Полный цикл')
  self.setGeometry(300, 300, 700, 600)

  layout = QVBoxLayout()

  # Заголовок
  title = QLabel('Конвертер в XISO для Xbox (xemu)')
  title_font = QFont()
  title_font.setPointSize(16)
  title_font.setBold(True)
  title.setFont(title_font)
  title.setAlignment(Qt.AlignmentFlag.AlignCenter)
  layout.addWidget(title)

  # Описание
  desc = QLabel('Автоматическая обработка ZIP, папок, ISO → XISO с очисткой временных файлов')
  desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
  desc.setWordWrap(True)
  layout.addWidget(desc)

  # Группа настроек
  settings_group = QGroupBox("Настройки конвертации")
  settings_layout = QVBoxLayout()

  # Выбор типа источника
  type_layout = QHBoxLayout()
  type_layout.addWidget(QLabel('Тип источника:'))
  self.source_type = QComboBox()
  self.source_type.addItems(['Автоопределение', 'ZIP архив', 'Папка с игрой', 'ISO образ'])
  self.source_type.currentTextChanged.connect(self.on_source_type_changed)
  type_layout.addWidget(self.source_type)
  settings_layout.addLayout(type_layout)

  # Поле для выбора источника
  source_layout = QHBoxLayout()
  source_layout.addWidget(QLabel('Путь к источнику:'))
  self.source_path = QLineEdit()
  source_layout.addWidget(self.source_path)
  self.btn_browse_source = QPushButton('Обзор')
  self.btn_browse_source.clicked.connect(self.browse_source)
  source_layout.addWidget(self.btn_browse_source)
  settings_layout.addLayout(source_layout)

  # Поле для вывода XISO
  output_layout = QHBoxLayout()
  output_layout.addWidget(QLabel('Выходной XISO:'))
  self.output_path = QLineEdit()
  self.output_path.setText('_xbox.xiso')  # Значение по умолчанию
  output_layout.addWidget(self.output_path)
  self.btn_browse_output = QPushButton('Обзор')
  self.btn_browse_output.clicked.connect(self.browse_output)
  output_layout.addWidget(self.btn_browse_output)
  settings_layout.addLayout(output_layout)

  # Опции
  options_layout = QHBoxLayout()
  self.cb_use_extract_iso = QCheckBox('Использовать extract-xiso (рекомендуется)')
  self.cb_use_extract_iso.setChecked(True)
  options_layout.addWidget(self.cb_use_extract_iso)

  self.cb_auto_cleanup = QCheckBox('Автоочистка временных файлов')
  self.cb_auto_cleanup.setChecked(True)
  options_layout.addWidget(self.cb_auto_cleanup)
  settings_layout.addLayout(options_layout)

  settings_group.setLayout(settings_layout)
  layout.addWidget(settings_group)

  # Информация о extract-xiso
  self.extract_info = QLabel('extract-xiso: проверка...')
  self.extract_info.setWordWrap(True)
  layout.addWidget(self.extract_info)

  # Прогресс бар
  self.progress = QProgressBar()
  layout.addWidget(self.progress)

  # Лог
  self.log_output = QTextEdit()
  self.log_output.setReadOnly(True)
  layout.addWidget(self.log_output)

  # Кнопки
  buttons_layout = QHBoxLayout()

  self.btn_check_tools = QPushButton('Проверить инструменты')
  self.btn_check_tools.clicked.connect(self.check_tools)
  buttons_layout.addWidget(self.btn_check_tools)

  self.btn_convert = QPushButton('Создать XISO')
  self.btn_convert.clicked.connect(self.start_conversion)
  self.btn_convert.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
  buttons_layout.addWidget(self.btn_convert)

  self.btn_clean = QPushButton('Очистить лог')
  self.btn_clean.clicked.connect(self.clear_log)
  buttons_layout.addWidget(self.btn_clean)

  layout.addLayout(buttons_layout)

  self.setLayout(layout)

  # Запускаем проверку инструментов при старте
  self.check_tools()

 def on_source_type_changed(self, text):
  """Обновляет расширения файлов при изменении типа"""
  if text == 'ZIP архив':
   self.source_path.setPlaceholderText('Выберите ZIP файл')
  elif text == 'ISO образ':
   self.source_path.setPlaceholderText('Выберите ISO файл')
  else:
   self.source_path.setPlaceholderText('Выберите файл или папку')

 def log(self, message):
  """Добавляет сообщение в лог"""
  self.log_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
  QApplication.processEvents()

 def clear_log(self):
  """Очищает лог"""
  self.log_output.clear()

 def browse_source(self):
  """Выбор исходного файла/папки"""
  source_type = self.source_type.currentText()

  if source_type == 'ZIP архив':
   file_path, _ = QFileDialog.getOpenFileName(
    self, 'Выберите ZIP архив', '',
    'ZIP Files (*.zip *.7z *.rar)'
   )
   if file_path:
    self.source_path.setText(file_path)
    # Автоматически предлагаем имя для выходного файла
    base_name = os.path.basename(file_path).rsplit('.', 1)[0]
    output_dir = os.path.dirname(file_path)
    self.output_path.setText(os.path.join(output_dir, f"{base_name}_xbox.xiso"))

  elif source_type == 'ISO образ':
   file_path, _ = QFileDialog.getOpenFileName(
    self, 'Выберите ISO файл', '',
    'ISO Files (*.iso *.img *.bin)'
   )
   if file_path:
    self.source_path.setText(file_path)
    base_name = os.path.basename(file_path).rsplit('.', 1)[0]
    output_dir = os.path.dirname(file_path)
    self.output_path.setText(os.path.join(output_dir, f"{base_name}_xbox.xiso"))

  else:  # Автоопределение или папка
   # Сначала пробуем выбрать файл
   file_path, _ = QFileDialog.getOpenFileName(
    self, 'Выберите файл или отмена для выбора папки', '',
    'Все поддерживаемые файлы (*.zip *.iso *.xbe *.img *.bin);;'
    'ZIP архивы (*.zip);;'
    'ISO образы (*.iso);;'
    'Все файлы (*.*)'
   )

   if file_path:
    self.source_path.setText(file_path)
    # Определяем тип по расширению
    if file_path.lower().endswith('.zip'):
     self.source_type.setCurrentText('ZIP архив')
    elif file_path.lower().endswith('.iso'):
     self.source_type.setCurrentText('ISO образ')

    base_name = os.path.basename(file_path).rsplit('.', 1)[0]
    output_dir = os.path.dirname(file_path)
    self.output_path.setText(os.path.join(output_dir, f"{base_name}_xbox.xiso"))
   else:
    # Если файл не выбран, выбираем папку
    dir_path = QFileDialog.getExistingDirectory(
     self, 'Выберите папку с игрой'
    )
    if dir_path:
     self.source_path.setText(dir_path)
     self.source_type.setCurrentText('Папка с игрой')
     base_name = os.path.basename(dir_path)
     self.output_path.setText(os.path.join(dir_path, f"{base_name}_xbox.xiso"))

 def browse_output(self):
  """Выбор выходного файла"""
  output_file, _ = QFileDialog.getSaveFileName(
   self, 'Сохранить XISO как', self.output_path.text(),
   'XISO Files (*.xiso);;ISO Files (*.iso)'
  )
  if output_file:
   if not output_file.lower().endswith(('.xiso', '.iso')):
    output_file += '.xiso'
   self.output_path.setText(output_file)

 def check_tools(self):
  """Проверка наличия инструментов"""
  self.log("Проверяю наличие инструментов...")

  # Создаем временный поток для проверки
  check_thread = ExtractXISOThread("", "")

  # Ищем extract-xiso
  tool_path = check_thread.find_extract_iso()

  if tool_path:
   # Проверяем версию
   if check_thread.check_extract_iso_version(tool_path):
    self.extract_info.setText(f"✅ extract-xiso найден: {tool_path}")
    self.log("extract-xiso доступен и работает")
   else:
    self.extract_info.setText(f"⚠️ extract-xiso найден, но не работает: {tool_path}")
    self.log("extract-xiso найден, но не запускается")
  else:
   self.extract_info.setText("❌ extract-xiso не найден. Скачайте с GitHub.")
   self.log("extract-xiso не найден в системе")

  # Проверяем наличие других инструментов
  if platform.system() == "Windows":
   # Проверяем 7-Zip
   sevenzip_paths = [
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
   ]
   for path in sevenzip_paths:
    if os.path.exists(path):
     self.log(f"7-Zip найден: {path}")
     break
   else:
    self.log("7-Zip не найден (полезно для распаковки архивов)")

 def start_conversion(self):
  """Запуск процесса конвертации"""
  if self.worker_thread and self.worker_thread.isRunning():
   QMessageBox.warning(self, "Внимание", "Конвертация уже выполняется!")
   return

  source_path = self.source_path.text().strip()
  output_path = self.output_path.text().strip()

  if not source_path:
   QMessageBox.warning(self, "Ошибка", "Укажите путь к источнику!")
   return

  if not os.path.exists(source_path):
   QMessageBox.warning(self, "Ошибка", "Источник не существует!")
   return

  if not output_path:
   QMessageBox.warning(self, "Ошибка", "Укажите путь для сохранения XISO!")
   return

  # Подтверждение
  reply = QMessageBox.question(
   self, "Подтверждение",
   f"Создать XISO из:\n{source_path}\n\nСохранить как:\n{output_path}\n\nПродолжить?",
   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
  )

  if reply != QMessageBox.StandardButton.Yes:
   return

  # Очищаем лог
  self.clear_log()
  self.log(f"Начинаю обработку: {source_path}")
  self.log(f"Выходной файл: {output_path}")

  # Создаем и настраиваем поток
  self.worker_thread = ExtractXISOThread(
   source_path,
   output_path,
   self.cb_use_extract_iso.isChecked()
  )

  # Подключаем сигналы
  self.worker_thread.log_signal.connect(self.log)
  self.worker_thread.progress_signal.connect(self.progress.setValue)
  self.worker_thread.finished_signal.connect(self.conversion_finished)

  # Блокируем кнопки
  self.btn_convert.setEnabled(False)
  self.btn_convert.setText("Конвертация...")

  # Запускаем поток
  self.worker_thread.start()

 def conversion_finished(self, success, message):
  """Завершение конвертации"""
  self.btn_convert.setEnabled(True)
  self.btn_convert.setText("Создать XISO")

  if success:
   self.log(f"✅ Конвертация успешно завершена!")
   self.log(f"📁 Файл создан: {message}")

   # Показываем диалог успеха
   success_dialog = QMessageBox(self)
   success_dialog.setIcon(QMessageBox.Icon.Information)
   success_dialog.setWindowTitle("Успех")
   success_dialog.setText("XISO успешно создан!")
   success_dialog.setInformativeText(f"Файл: {message}")

   # Добавляем кнопки
   open_button = success_dialog.addButton("Открыть папку", QMessageBox.ButtonRole.ActionRole)
   ok_button = success_dialog.addButton("OK", QMessageBox.ButtonRole.AcceptRole)

   success_dialog.exec()

   # Обработка нажатий
   if success_dialog.clickedButton() == open_button:
    output_dir = os.path.dirname(message)
    if os.path.exists(output_dir):
     if platform.system() == "Windows":
      os.startfile(output_dir)
     elif platform.system() == "Darwin":
      subprocess.run(["open", output_dir])
     else:
      subprocess.run(["xdg-open", output_dir])

  else:
   self.log(f"❌ Ошибка: {message}")
   QMessageBox.critical(self, "Ошибка", f"Не удалось создать XISO:\n{message}")

 def closeEvent(self, event):
  """Очистка при закрытии"""
  if self.worker_thread and self.worker_thread.isRunning():
   reply = QMessageBox.question(
    self, "Конвертация выполняется",
    "Конвертация еще выполняется. Прервать?",
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
   )

   if reply == QMessageBox.StandardButton.Yes:
    self.worker_thread.terminate()
    self.worker_thread.wait(1000)
   else:
    event.ignore()
    return

  event.accept()


if __name__ == '__main__':
 import time

 app = QApplication(sys.argv)
 app.setStyle('Fusion')

 # Устанавливаем иконку приложения
 if platform.system() == "Windows":
  app.setFont(QFont("Segoe UI", 10))

 converter = XISOConverter()
 converter.show()

 sys.exit(app.exec())
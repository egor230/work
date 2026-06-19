import sys, subprocess, os, zipfile
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton,
                             QHBoxLayout, QVBoxLayout, QMessageBox, QComboBox, QStatusBar)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor


class DocumentConverter(QWidget):
 # Класс для конвертации документов (Markdown, pdf, html) с помощью pandoc

 def __init__(self):
  super().__init__()
  self.setWindowTitle("Document Converter (pandoc)")
  self.setGeometry(650, 300, 550, 250)

  # Применяем светлую тему
  self.apply_light_theme()

  # Виджеты для выбора входного файла/папки
  self.input_label = QLabel("Input file or folder:")
  self.input_path = QLineEdit()
  self.select_input_btn = QPushButton("Select Input File/Folder")
  self.select_input_btn.clicked.connect(self.select_input)

  # Виджеты для выбора выходной папки
  self.output_dir_label = QLabel("Output directory:")
  self.output_dir_path = QLineEdit()
  self.select_output_dir_btn = QPushButton("Select Output Directory")
  self.select_output_dir_btn.clicked.connect(self.select_output_dir)

  # Выпадающий список для форматов конвертации
  self.format_label = QLabel("Target format:")
  self.format_combo = QComboBox()
  self.format_combo.addItems(["Markdown", "pdf", "html"])

  # Кнопка запуска конвертации
  self.convert_btn = QPushButton("Convert")
  self.convert_btn.clicked.connect(self.convert_documents)

  # Лэйаут для строки ввода входных данных
  input_layout = QHBoxLayout()
  input_layout.addWidget(self.input_path)
  input_layout.addWidget(self.select_input_btn)

  # Лэйаут для строки выбора выходной папки
  output_layout = QHBoxLayout()
  output_layout.addWidget(self.output_dir_path)
  output_layout.addWidget(self.select_output_dir_btn)

  # Лэйаут для выпадающего списка
  format_layout = QHBoxLayout()
  format_layout.addWidget(self.format_label)
  format_layout.addWidget(self.format_combo)

  # Основной вертикальный лэйаут
  layout = QVBoxLayout()
  layout.addWidget(self.input_label)
  layout.addLayout(input_layout)
  layout.addWidget(self.output_dir_label)
  layout.addLayout(output_layout)
  layout.addLayout(format_layout)
  layout.addWidget(self.convert_btn)

  self.setLayout(layout)

 def apply_light_theme(self):
  # Устанавливаем светлую цветовую схему через QPalette
  app = QApplication.instance()
  app.setStyle('Fusion')

  palette = QPalette()
  palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
  palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
  palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
  palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
  palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
  palette.setColor(QPalette.ColorRole.Button, QColor(220, 220, 220))
  palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
  palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
  palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
  palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

  app.setPalette(palette)
  
 def select_input(self):
  choice = subprocess.run(['zenity', '--question', '--text=What do you want to select?\n\nChoose "Yes" for File, "No" for Directory', '--ok-label=File', '--cancel-label=Directory'], capture_output=True)
  if choice.returncode == 0:
   cmd = subprocess.run(['zenity', '--file-selection', '--file-filter=Document files | *.md *.doc *.docx *.pdf *.html'], capture_output=True, text=True)
   if cmd.returncode == 0:
    path = cmd.stdout.strip()
    self.input_path.setText(path)
    self.output_dir_path.setText(os.path.dirname(path))
  else:
   cmd = subprocess.run(['zenity', '--file-selection', '--directory'], capture_output=True, text=True)
   if cmd.returncode == 0:
    self.input_path.setText(cmd.stdout.strip())
    self.output_dir_path.setText(cmd.stdout.strip())

 def select_output_dir(self):
  # Получаем текущий путь из первого поля, если он есть
  selected_path = self.input_path.text()
  
  # Формируем аргументы для Zenity
  cmd_args = ['zenity', '--file-selection', '--directory']
  if selected_path:
   cmd_args.append(f'--filename={selected_path}')
  
  cmd = subprocess.run(cmd_args, capture_output=True, text=True)
  if cmd.returncode == 0:
   self.output_dir_path.setText(cmd.stdout.strip())
 def convert_documents(self):
  "Основная логика конвертации файлов с отображением прогресса"
  
  "Поиск доступного статус-бара в текущем виджете"
  status_bar = None
  if hasattr(self, 'statusBar'):
   status_bar = self.statusBar()
  elif hasattr(self, 'status_bar'):
   status_bar = self.status_bar
  else:
   status_bar = self.findChild(QStatusBar)
  
  input_path = self.input_path.text()
  output_dir = self.output_dir_path.text()
  selected_format = self.format_combo.currentText()
  
  required_packages = []
  try:
   subprocess.run(['pandoc', '--version'], capture_output=True, check=True)
  except (subprocess.CalledProcessError, FileNotFoundError):
   required_packages.append('pandoc')
  
  try:
   subprocess.run(['libreoffice', '--version'], capture_output=True, check=True)
  except (subprocess.CalledProcessError, FileNotFoundError):
   required_packages.append('libreoffice')
  
  if required_packages:
   try:
    if status_bar:
     status_bar.showMessage("Установка недостающих системных пакетов...")
    QApplication.instance().processEvents()
    subprocess.run(['pkexec', 'apt-get', 'update'], check=True)
    subprocess.run(['pkexec', 'apt-get', 'install', '-y'] + required_packages, check=True)
   except subprocess.CalledProcessError:
    packages_str = " ".join(required_packages)
    QMessageBox.critical(self, "Error", f"Не удалось установить пакеты. Установите вручную: sudo apt install {packages_str}")
    return
  
  if not os.path.exists(input_path):
   QMessageBox.critical(self, "Error", f"Input path does not exist: {input_path}")
   return
  
  if not os.path.isdir(output_dir):
   os.makedirs(output_dir, exist_ok=True)
  
  format_map = {
   "Markdown": (".md", ["-t", "markdown", "--extract-media=" + output_dir, "--resource-path=" + output_dir]),
   "pdf": (".pdf", ["-t", "pdf", "--pdf-engine=pdflatex"]),
   "html": (".html", ["-t", "html"])
  }
  if selected_format not in format_map:
   QMessageBox.critical(self, "Error", f"Unknown format: {selected_format}")
   return
  target_ext, pandoc_args = format_map[selected_format]
  
  if selected_format == "pdf":
   try:
    subprocess.run(['pdflatex', '--version'], capture_output=True, check=True)
   except (subprocess.CalledProcessError, FileNotFoundError):
    pass
  
  source_extensions = [".doc", ".docx", ".pdf", ".html"]
  if target_ext in source_extensions:
   source_extensions.remove(target_ext)
  
  files_to_convert = []
  if os.path.isfile(input_path):
   ext = os.path.splitext(input_path)[1].lower()
   if ext in source_extensions:
    files_to_convert.append(input_path)
  else:
   for filename in os.listdir(input_path):
    filepath = os.path.join(input_path, filename)
    if os.path.isfile(filepath):
     ext = os.path.splitext(filepath)[1].lower()
     if ext in source_extensions:
      files_to_convert.append(filepath)
  
  total_files = len(files_to_convert)
  if total_files == 0:
   if status_bar:
    status_bar.showMessage("Нет файлов для конвертации")
   QMessageBox.information(self, "Done", "Не найдено подходящих файлов для конвертации.")
   return
  
  converted_count = 0
  for index, filepath in enumerate(files_to_convert):
   base_name = os.path.splitext(os.path.basename(filepath))[0]
   
   "Обновление статус-бара в реальном времени"
   progress_text = f"Обработка {index + 1} из {total_files}: {base_name}"
   if status_bar:
    status_bar.showMessage(progress_text)
   QApplication.instance().processEvents()
   
   out_file = os.path.join(output_dir, base_name + target_ext)
   
   is_docx = filepath.lower().endswith('.docx')
   is_doc = filepath.lower().endswith('.doc')
   
   is_broken_docx = is_docx and not zipfile.is_zipfile(filepath)
   
   if is_doc or is_broken_docx:
    if selected_format in ["pdf", "html"]:
     cmd = ['libreoffice', '--headless', '--convert-to', selected_format, filepath, '--outdir', output_dir]
     try:
      subprocess.run(cmd, check=True, capture_output=True)
      converted_count += 1
      continue
     except subprocess.CalledProcessError as e:
      print(f"Error converting {filepath} via libreoffice: {e.stderr.decode()}")
      continue
    elif selected_format == "Markdown":
     import tempfile
     with tempfile.TemporaryDirectory() as tmpdir:
      cmd_repair = ['libreoffice', '--headless', '--convert-to', 'docx', filepath, '--outdir', tmpdir]
      try:
       subprocess.run(cmd_repair, check=True, capture_output=True)
       
       "Получаем точное имя исправленного файла из временной директории"
       repaired_files = os.listdir(tmpdir)
       if repaired_files:
        repaired_docx = os.path.join(tmpdir, repaired_files[0])
        cmd = ['pandoc', repaired_docx, '-o', out_file] + pandoc_args
        subprocess.run(cmd, check=True, capture_output=True)
        converted_count += 1
        
        "=== ИСПРАВЛЕНИЕ ПУТЕЙ К КАРТИНКАМ В MD ==="
        try:
         with open(out_file, 'r', encoding='utf-8') as f:
          content = f.read()
         
         import re
         def replace_image(match):
          alt = match.group(1) or ''
          old_path = match.group(2)
          filename = os.path.basename(old_path)
          new_path = f"media/{filename}"
          return f"![{alt}]({new_path})"
         
         content = re.sub(r'!\[(.*?)\]\((.+?)\)', replace_image, content)
         content = re.sub(r'\{width=.*?\}', '', content)
         content = re.sub(r'\{height=.*?\}', '', content)
         
         with open(out_file, 'w', encoding='utf-8') as f:
          f.write(content)
        except Exception as e:
         print(f"Warning fixing images in {out_file}: {e}")
        continue
      except subprocess.CalledProcessError as e:
       print(f"Error converting {filepath} via fallback pipeline: {e.stderr.decode()}")
       continue
   
   cmd = ['pandoc', filepath, '-o', out_file] + pandoc_args
   try:
    subprocess.run(cmd, check=True, capture_output=True)
    converted_count += 1
    
    if selected_format == "Markdown":
     "=== ИСПРАВЛЕНИЕ ПУТЕЙ К КАРТИНКАМ В MD ==="
     try:
      with open(out_file, 'r', encoding='utf-8') as f:
       content = f.read()
      
      import re
      def replace_image(match):
       alt = match.group(1) or ''
       old_path = match.group(2)
       filename = os.path.basename(old_path)
       new_path = f"media/{filename}"
       return f"![{alt}]({new_path})"
      
      content = re.sub(r'!\[(.*?)\]\((.+?)\)', replace_image, content)
      content = re.sub(r'\{width=.*?\}', '', content)
      content = re.sub(r'\{height=.*?\}', '', content)
      
      with open(out_file, 'w', encoding='utf-8') as f:
       f.write(content)
     except Exception as e:
      print(f"Warning fixing images in {out_file}: {e}")
   
   except subprocess.CalledProcessError as e:
    err_msg = e.stderr.decode()
    if "container" in err_msg or "unpack" in err_msg:
     if selected_format in ["pdf", "html"]:
      cmd_lo = ['libreoffice', '--headless', '--convert-to', selected_format, filepath, '--outdir', output_dir]
      try:
       subprocess.run(cmd_lo, check=True, capture_output=True)
       converted_count += 1
       continue
      except subprocess.CalledProcessError:
       pass
    print(f"Error converting {filepath}: {err_msg}")
  
  if status_bar:
   status_bar.showMessage(f"Успешно сконвертировано {converted_count} файлов.")
  QMessageBox.information(self, "Done", f"Converted {converted_count} file(s) to {selected_format}")
if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = DocumentConverter()
 window.show()
 sys.exit(app.exec())
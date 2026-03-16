import sys, os, subprocess, threading, shlex
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QScrollArea, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor


class SaveDict:
 def __init__(self): self.labels, self.res, self.count = [], [], 0

 def save_labels(self, labels): self.labels = labels

 def return_labels(self): return self.labels

 def cl_res(self): self.res.clear()

 def save_res(self, res): self.res = res

 def return_res(self): return self.res

 def set_count(self, count): self.count = count; return self.count

 def get_count(self): return self.count


class ClickableLabel(QLabel):
 def __init__(self, text, index, parent=None):
  super().__init__(text, parent)
  self.index = index
  # Увеличена высота метки с 30px до 40px
  self.setStyleSheet("""
            background-color: white; 
            padding: 10px; 
            margin: 2px; 
            color: black;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            min-height: 15px;
        """)
  self.setCursor(Qt.CursorShape.PointingHandCursor)

 def mousePressEvent(self, event):
  if event.button() == Qt.MouseButton.LeftButton:
   k.set_count(self.index)
   check_label_changed()


def check_label_changed():
 res = k.return_res()
 count = k.get_count()
 if count < len(res):
  folder_escaped = shlex.quote(folder)
  file_name = shlex.quote(f"{res[count]}.doc")
  command = f'cd {folder_escaped} && wine {file_name}'

  def run_command():
   try:
    subprocess.run(['bash', '-c', command], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
   except subprocess.CalledProcessError as e:
    print(f"Ошибка при запуске файла: {e}")

  thread = threading.Thread(target=run_command, daemon=True)
  thread.start()
  if hasattr(window, 'entry'): window.entry.clear()


def del_labels():
 for label in k.return_labels(): label.deleteLater()
 k.save_labels([])

k = SaveDict()
folder = "/mnt/807EB5FA7EB5E954/работа/база для анализа"
try:
 res = [os.path.splitext(f)[0] for f in os.listdir(folder) if f.lower().endswith('.doc')]
 k.save_res(res)
except FileNotFoundError:
 print(f"Ошибка: папка {folder} не найдена")
 k.save_res([])

class MainWindow(QMainWindow):
 def __init__(self):
  super().__init__()
  self.setWindowTitle("Find text")
  # Увеличена высота окна с 286px до 400px для большей области результатов
  self.setGeometry(580, 500, 700, 400)

  self.central_widget = QWidget()
  self.setCentralWidget(self.central_widget)
  self.layout = QVBoxLayout(self.central_widget)
  self.layout.setContentsMargins(10, 10, 10, 10)
  self.layout.setSpacing(5)  # Уменьшен spacing между виджетами

  # Поле ввода с уменьшенной высотой (35px вместо стандартной)
  self.entry = QLineEdit()
  self.entry.setPlaceholderText("Введите текст для поиска...")
  self.entry.setFixedHeight(25)  # Уменьшена высота
  self.entry.setStyleSheet("""
            QLineEdit {
                padding: 5px 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #0078d7; }
        """)
  self.layout.addWidget(self.entry)

  self.scroll_area = QScrollArea()
  self.scroll_area.setWidgetResizable(True)
  self.scroll_area.setStyleSheet("""
            QScrollArea { border: 1px solid #ddd; border-radius: 4px; background: white; }
            QScrollBar:vertical { background: #f1f1f1; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #c1c1c1; border-radius: 5px; min-height: 10px; }
            QScrollBar::handle:vertical:hover { background: #a8a8a8; }
        """)
  self.scroll_widget = QWidget()
  self.scroll_layout = QVBoxLayout(self.scroll_widget)
  self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
  self.scroll_layout.setSpacing(4)
  self.scroll_area.setWidget(self.scroll_widget)
  self.layout.addWidget(self.scroll_area)
  self.entry.textChanged.connect(self.on_text_changed)

 def on_text_changed(self, text):
  if not text: del_labels(); return
  del_labels()
  search_text = text.lower()
  res_list = k.return_res()
  matching_indices = [i for i, item in enumerate(res_list) if search_text in item.lower()]
  new_labels = []
  for idx in matching_indices:
   label = ClickableLabel(res_list[idx], idx, self.scroll_widget)
   self.scroll_layout.addWidget(label)
   new_labels.append(label)
  k.save_labels(new_labels)

def setup_light_theme(app):
 app.setStyle("Fusion")
 palette = QPalette()
 palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
 palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
 palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
 palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
 palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
 palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
 palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
 palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
 palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
 app.setPalette(palette)


if __name__ == "__main__":
 app = QApplication(sys.argv)
 setup_light_theme(app)
 window = MainWindow()
 window.show()
 sys.exit(app.exec())
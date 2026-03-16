import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class XemuConfigApp(QMainWindow):
 def __init__(self):
  super().__init__()
  self.setWindowTitle("Xemu Master Config Pro")
  self.resize(1050, 750)
  self.setStyleSheet("background-color: #141526;")

  self.colors = {
   "bg": "#141526",
   "frame_bg": "#1c1e3d",
   "border": "#2c2f5a",
   "accent_blue": "#2d5cf7",
   "btn_blue": "#0070d2",
   "btn_orange": "#f39c12",
   "btn_green": "#4cd137",
   "key_bg": "#3d447e",
   "text": "white"
  }

  self.create_widgets()

 def create_widgets(self):
  # --- ВЕРХНЯЯ ПАНЕЛЬ ---
  header = QFrame(self)
  header.setStyleSheet(f"background-color: {self.colors['frame_bg']}; border: 1px solid {self.colors['accent_blue']};")
  header.setGeometry(20, 20, 1010, 80)

  title_label = QLabel("🎮 XEMU ULTIMATE CONFIG", header)
  title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
  title_label.setStyleSheet(f"background-color: {self.colors['frame_bg']}; color: white;")
  title_label.setGeometry(20, 22, 350, 40)

  profile_label = QLabel("ПРОФИЛЬ:", header)
  profile_label.setStyleSheet(f"background-color: {self.colors['frame_bg']}; color: white;")
  profile_label.setGeometry(380, 28, 100, 25)

  profile_entry = QLineEdit("obscure", header)
  profile_entry.setStyleSheet("background-color: #0d0e1a; color: white; border: none;")
  profile_entry.setGeometry(460, 28, 220, 25)

  create_profile_btn = QPushButton("💾 СОЗДАТЬ ПРОФИЛЬ", header)
  create_profile_btn.setStyleSheet(f"background-color: {self.colors['btn_blue']}; color: white; border: none;")
  create_profile_btn.setGeometry(700, 25, 140, 32)

  default_btn = QPushButton("🔄 ПО УМОЛЧАНИЮ", header)
  default_btn.setStyleSheet(f"background-color: {self.colors['btn_orange']}; color: white; border: none;")
  default_btn.setGeometry(850, 25, 140, 32)

  # --- ОСНОВНАЯ ОБЛАСТЬ ---
  main = QWidget(self)
  main.setStyleSheet(f"background-color: {self.colors['bg']};")
  main.setGeometry(20, 110, 1010, 580)

  # --- [ИЗМЕНЕНИЕ 1] БОКОВЫЕ КНОПКИ ПОДНЯТЫ ВВЕРХ (Y=20 и Y=80) ---
  # Левая сторона
  self.create_key(main, 30, 20, "LB\n(W)", "#7f8c8d", w=105, h=50)
  self.create_key(main, 30, 80, "LT\n(KP3)", "#e67e22", w=105, h=50)

  # Правая сторона
  self.create_key(main, 870, 20, "RB\n(PMINUS)", "#7f8c8d", w=105, h=50)
  self.create_key(main, 870, 80, "RT\n(KPDOT)", "#e67e22", w=105, h=50)

  # --- [ИЗМЕНЕНИЕ 2] ЦЕНТРАЛЬНЫЕ КНОПКИ ОПУЩЕНЫ ВНИЗ (Y=330) ---
  self.create_key(main, 390, 330, "Guide\n(BACKSPACE)", "#3498db", w=100, h=50)
  self.create_key(main, 490, 330, "Back\n(PPLU!)", "#9b59b6", w=70, h=50)
  self.create_key(main, 550, 330, "Start\nPMINU", "#9b59b6", w=70, h=50)

  # --- КРЕСТОВИНЫ (Остались на прежних местах для баланса) ---
  self.draw_cross_group(main, 80, 220, "D-PAD", "D-PAD", "I", "J", "L", "K")
  self.draw_cross_group(main, 780, 220, "Right Stick", "RS\n(T)", "KP8", "KP4", "KP6", "KP5")
  self.draw_cross_group(main, 80, 440, "Left Stick", "LS\n(PPLU!)", "UP", "LEFT", "RIGHT", "DOWN")
  self.draw_cross_group(main, 780, 440, "ABXY", "ABXY", "Y\nHTSH", "X\n(KP2)", "B\n(KP3)", "A\n(KPO)", center_color="#57606f")

  # --- НИЖНЯЯ КНОПКА ---
  apply_btn = QPushButton("🚀 ПРИМЕНИТЬ НАСТРОЙКИ В XEMU", self)
  apply_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
  apply_btn.setStyleSheet(f"background-color: {self.colors['btn_green']}; color: white; border: none;")
  apply_btn.setGeometry(20, 700, 1010, 40)

 def create_key(self, parent, x, y, text, color, w=40, h=40):
  lbl = QLabel(text, parent)
  lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
  lbl.setFont(QFont("Arial", 7, QFont.Weight.Bold))
  lbl.setStyleSheet(f"background-color: {color}; color: white; border: none;")
  lbl.setGeometry(x, y, w, h)

 def draw_cross_group(self, parent, x, y, title, center_txt, t, l, r, b, center_color="#2d5cf7"):
  title_lbl = QLabel(title, parent)
  title_lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
  title_lbl.setStyleSheet(f"background-color: {self.colors['bg']}; color: white;")
  title_lbl.setGeometry(x + 40, y - 30, 150, 30)

  btn_size = 42
  self.create_key(parent, x + btn_size, y, t, self.colors["key_bg"], w=btn_size, h=btn_size)
  self.create_key(parent, x, y + btn_size, l, self.colors["key_bg"], w=btn_size, h=btn_size)
  self.create_key(parent, x + btn_size, y + btn_size, center_txt, center_color, w=btn_size + 15, h=btn_size)
  self.create_key(parent, x + (btn_size * 2) + 15, y + btn_size, r, self.colors["key_bg"], w=btn_size, h=btn_size)
  self.create_key(parent, x + btn_size, y + (btn_size * 2), b, self.colors["key_bg"], w=btn_size, h=btn_size)


if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = XemuConfigApp()
 window.setFixedSize(1050, 750)  # Аналог resizable(False, False)
 window.show()
 sys.exit(app.exec())
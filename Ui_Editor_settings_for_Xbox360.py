import sys
from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDialog,
 QFrame, QGraphicsDropShadowEffect, QToolTip, QCheckBox, QLineEdit,
 QComboBox, QApplication
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt6.QtGui import (
 QPixmap, QPainter, QColor, QPen, QBrush, QFont,
 QRadialGradient
)

# =============================================================================
# ОПРЕДЕЛЕНИЕ ЗОН (На основе вашей конфигурации JSON)
# =============================================================================
ZONE_DEFINITIONS = [
 ("LT", "LEFT_TRIGGER", 0.18, 0.01, 0.14, 0.06, "#e67e22", "rect"),
 ("RT", "RIGHT_TRIGGER", 0.68, 0.01, 0.14, 0.06, "#e67e22", "rect"),
 ("LB", "LEFT_SHOULDER", 0.14205128205128206, 0.17369408369408368, 0.16, 0.07, "#95a5a6", "rect"),
 ("RB", "RIGHT_SHOULDER", 0.697948717948718, 0.1708080808080808, 0.16, 0.07, "#95a5a6", "rect"),
 ("Guide", "GUIDE", 0.46, 0.23, 0.08, 0.1, "#3498db", "ellipse"),
 ("Back", "BACK", 0.398974358974359, 0.3728860028860029, 0.05, 0.06, "#9b59b6", "ellipse"),
 ("Start", "START", 0.5546153846153845, 0.3816450216450216, 0.05, 0.06, "#9b59b6", "ellipse"),
 ("L↑", "LEFT_THUMB_UP", 0.18974358974358976, 0.2901010101010101, 0.06, 0.06, "#5b8cff", "rect"),
 ("L↓", "LEFT_THUMB_DOWN", 0.19743589743589746, 0.46741702741702745, 0.06, 0.06, "#5b8cff", "rect"),
 ("L←", "LEFT_THUMB_LEFT", 0.10564102564102565, 0.38597402597402597, 0.06, 0.06, "#5b8cff", "rect"),
 ("L→", "LEFT_THUMB_RIGHT", 0.27, 0.36, 0.06, 0.06, "#5b8cff", "rect"),
 ("LS", "LEFT_THUMB_PRESSED", 0.18102564102564103, 0.35731601731601736, 0.08, 0.1, "#1a47c4", "ellipse"),
 ("Y", "Y", 0.7561538461538462, 0.2815440115440116, 0.06, 0.08, "#f1c40f", "ellipse"),
 ("X", "X", 0.6861538461538461, 0.36865800865800863, 0.06, 0.08, "#3498db", "ellipse"),
 ("B", "B", 0.83, 0.36577200577200575, 0.06, 0.08, "#e74c3c", "ellipse"),
 ("A", "A", 0.7561538461538462, 0.44855699855699854, 0.06, 0.08, "#2ecc71", "ellipse"),
 ("↑", "DPAD_UP", 0.3223076923076923, 0.5032900432900433, 0.06, 0.07, "#7f8c8d", "rect"),
 ("↓", "DPAD_DOWN", 0.321025641025641, 0.6416450216450217, 0.06, 0.07, "#7f8c8d", "rect"),
 ("←", "DPAD_LEFT", 0.2651282051282051, 0.5688600288600288, 0.06, 0.07, "#7f8c8d", "rect"),
 ("→", "DPAD_RIGHT", 0.38333333333333336, 0.5717460317460318, 0.06, 0.07, "#7f8c8d", "rect"),
 ("R↑", "RIGHT_THUMB_UP", 0.6182051282051282, 0.487012987012987, 0.06, 0.06, "#5b8cff", "rect"),
 ("R↓", "RIGHT_THUMB_DOWN", 0.6169230769230769, 0.6412409812409813, 0.06, 0.06, "#5b8cff", "rect"),
 ("R←", "RIGHT_THUMB_LEFT", 0.5392307692307693, 0.5626839826839827, 0.06, 0.06, "#5b8cff", "rect"),
 ("R→", "RIGHT_THUMB_RIGHT", 0.6946153846153846, 0.5597979797979797, 0.06, 0.06, "#5b8cff", "rect"),
 ("RS", "RIGHT_THUMB_PRESSED", 0.6043589743589743, 0.5412409812409813, 0.08, 0.1, "#1a47c4", "ellipse")
]


class InteractiveZone:
 """Класс зоны кнопки геймпада"""
 
 def __init__(self, name, logical_name, rx, ry, rw, rh, color_hex, shape="rect"):
  self.name, self.logical_name = name, logical_name
  self.rx, self.ry, self.rw, self.rh = rx, ry, rw, rh
  self.color = QColor(color_hex)
  self.shape = shape
  self.hovered, self.pressed = False, False
  self.current_binding = ""  # Текущая привязка (пустая, если не назначена)
 
 def abs_rect(self, w, h):
  return QRectF(self.rx * w, self.ry * h, self.rw * w, self.rh * h)
 
 def contains(self, point, w, h):
  rect = self.abs_rect(w, h)
  if self.shape == "ellipse":
   cx, cy = rect.center().x(), rect.center().y()
   rx, ry = rect.width() / 2, rect.height() / 2
   if rx <= 0 or ry <= 0: return False
   return ((point.x() - cx) / rx) ** 2 + ((point.y() - cy) / ry) ** 2 <= 1.0
  return rect.contains(point)


class GamepadWidget(QWidget):
 """Виджет отрисовки геймпада и зон"""
 zone_clicked = pyqtSignal(str)
 mouse_moved_rel = pyqtSignal(float, float)
 
 def __init__(self, image_path, parent=None):
  super().__init__(parent)
  self.bg_pixmap = self._load_and_crop_image(image_path)
  self.setFixedSize(self.bg_pixmap.size())
  self.setMouseTracking(True)
  self.zones = [InteractiveZone(*z) for z in ZONE_DEFINITIONS]
  self._hovered_zone = None
  self._debug = True
  
  self._press_timer = QTimer(self)
  self._press_timer.setSingleShot(True)
  self._press_timer.setInterval(180)
  self._press_timer.timeout.connect(self._release_all)
 
 def _load_and_crop_image(self, path):
  pix = QPixmap(path)
  if pix.isNull():
   pix = QPixmap(900, 500)
   pix.fill(QColor("#1a1a2e"))
   p = QPainter(pix)
   p.setPen(QColor("white"))
   p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "Изображение не найдено")
   p.end()
   return pix
  w, h = pix.width(), pix.height()
  crop_rect = QRectF(w * 0.05, h * 0.02, w * 0.90, h * 0.80).toRect()
  return pix.copy(crop_rect)
 
 def set_debug_mode(self, on):
  self._debug = on
  self.update()
 
 def update_binding(self, logical, key_str):
  for z in self.zones:
   if z.logical_name == logical:
    z.current_binding = key_str
    break
  self.update()
 
 def update_all_bindings(self, mapping):
  # Обновление всех привязок. Если ключа нет в mapping, ставим пустую строку
  for z in self.zones:
   z.current_binding = mapping.get(z.logical_name, "")
  self.update()
 
 def set_image(self, path):
  pix = self._load_and_crop_image(path)
  if not pix.isNull():
   self.bg_pixmap = pix
   self.setFixedSize(pix.size())
   self.update()
 
 def paintEvent(self, event):
  painter = QPainter(self)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)
  w, h = self.width(), self.height()
  painter.drawPixmap(0, 0, self.bg_pixmap)
  
  for z in self.zones:
   rect = z.abs_rect(w, h)
   if self._debug:
    painter.setPen(QPen(QColor(255, 255, 255, 50), 1, Qt.PenStyle.DashLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if z.shape == "ellipse":
     painter.drawEllipse(rect)
    else:
     painter.drawRect(rect)
   
   # Рисуем название зоны
   painter.setPen(QColor(255, 255, 255, 70))
   painter.setFont(QFont("Consolas", 7))
   painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, z.name)
   
   # Подсветка и текст привязки
   if z.hovered and not z.pressed:
    self._paint_highlight(painter, z, rect, 100)
    self._paint_label(painter, z, rect)
   if z.pressed:
    self._paint_highlight(painter, z, rect, 190)
    self._paint_label(painter, z, rect)
  painter.end()
 
 def _paint_highlight(self, painter, z, rect, alpha):
  fill, glow = QColor(z.color), QColor(z.color)
  fill.setAlpha(alpha)
  glow.setAlpha(alpha // 4)
  glow_rect = rect.adjusted(-5, -5, 5, 5)
  
  painter.setPen(Qt.PenStyle.NoPen)
  painter.setBrush(QBrush(glow))
  if z.shape == "ellipse":
   painter.drawEllipse(glow_rect)
   grad = QRadialGradient(rect.center(), max(rect.width(), rect.height()) / 2)
   grad.setColorAt(0.0, QColor(255, 255, 255, alpha // 2))
   grad.setColorAt(0.5, fill)
   grad.setColorAt(1.0, QColor(z.color).darker(160))
   painter.setBrush(QBrush(grad))
  else:
   painter.drawRoundedRect(glow_rect, 5, 5)
   painter.setBrush(QBrush(fill))
   painter.setPen(QPen(QColor(255, 255, 255, alpha), 1.5))
   painter.drawRoundedRect(rect, 4, 4)
 
 def _paint_label(self, painter, z, rect):
  painter.setPen(QColor(255, 255, 255, 230))
  painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
  # Если есть привязка, добавляем её в скобках
  text = z.name + (f"\n[{z.current_binding}]" if z.current_binding else "")
  painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
 
 def _zone_at(self, pos):
  for z in reversed(self.zones):
   if z.contains(pos, self.width(), self.height()): return z
  return None
 
 def mouseMoveEvent(self, event):
  pos, zone = event.position(), self._zone_at(event.position())
  if zone != self._hovered_zone:
   if self._hovered_zone: self._hovered_zone.hovered = False
   if zone: zone.hovered = True
   self._hovered_zone = zone
   self.update()
  
  if zone:
   QToolTip.showText(event.globalPosition().toPoint(), zone.name + (f"{zone.current_binding}" if zone.current_binding else ""), self)
  else:
   QToolTip.hideText()
  
  self.setCursor(Qt.CursorShape.PointingHandCursor if zone else Qt.CursorShape.ArrowCursor)
  self.mouse_moved_rel.emit(pos.x() / self.width(), pos.y() / self.height())
  super().mouseMoveEvent(event)
 
 def mousePressEvent(self, event):
  if event.button() == Qt.MouseButton.LeftButton:
   zone = self._zone_at(event.position())
   if zone:
    zone.pressed = True
    self.update()
    self.zone_clicked.emit(zone.logical_name)
 
 def mouseReleaseEvent(self, event):
  if event.button() == Qt.MouseButton.LeftButton:
   self._press_timer.start()
 
 def _release_all(self):
  for z in self.zones: z.pressed = False
  self.update()
 
 def leaveEvent(self, event):
  if self._hovered_zone:
   self._hovered_zone.hovered = False
   self._hovered_zone = None
  QToolTip.hideText()
  self.update()
  super().leaveEvent(event)


class VirtualKeyboard(QDialog):
 """Виртуальная клавиатура для назначения клавиш"""
 
 def __init__(self, parent, callback_func=None):
  super().__init__(parent)
  self.setWindowTitle("Выбор клавиши")
  self.setFixedSize(1410, 450)
  self.setStyleSheet("QDialog{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1a1a2e,stop:1 #16213e);border-radius:15px;border:2px solid #3949ab;}")
  self.callback_func = callback_func
  self._build_ui()
 
 def _build_ui(self):
  main_layout = QVBoxLayout(self)
  main_layout.setContentsMargins(20, 20, 20, 20)
  
  title = QLabel("ВЫБЕРИТЕ КЛАВИШУ")
  title.setAlignment(Qt.AlignmentFlag.AlignCenter)
  title.setStyleSheet("QLabel{color:#ffffff;font-size:24px;font-weight:bold;padding:10px;background:rgba(57,73,171,0.3);border-radius:10px;border:1px solid #5c6bc0;}")
  main_layout.addWidget(title)
  
  keyboard_widget = QWidget()
  keyboard_widget.setMinimumSize(850, 340)
  keyboard_widget.setStyleSheet(
   "QPushButton{background-color:#3949ab;color:white;border:2px solid #5c6bc0;border-radius:5px;padding:5px;font-weight:bold;font-size:12px;}QPushButton:hover{background-color:#5c6bc0;border:2px solid #7986cb;}QPushButton:pressed{background-color:#283593;color:#bbdefb;}")
  
  BUTTON_WIDTH, BUTTON_HEIGHT = 60, 40
  BASE_X_STEP, BASE_Y_STEP = 70, 50
  X_OFFSET, Y_OFFSET = 6, 6
  
  keyboard_layout = [
   ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'Insert', 'Delete', 'Home', 'End', 'PgUp', 'PgDn'],
   ['~\n`', '!\n1', '@\n2', '#\n3', '$\n4', '%\n5', '^\n6', '&\n7', '\n8', '(\n9', ')\n0', '_\n-', '+\n=', 'Backspace', 'Num Lock', '/', '', '-'],
   ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{\n[', '}\n]', '|\n\\', '7\nHome', '8\n↑', '9\nPgUp', '+'],
   ['Caps Lock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':\n;', '"\n\'', '\nEnter\n', '4\n←', '5\n', '6\n→'],
   ['Shift_L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<\n,', '>\n.', '?\n/', 'Shift_R', '1\nEnd', '2\n↓', '3\nPgDn', 'KEnter'],
   ['Ctrl', 'Windows', 'Alt_L', 'space', 'Alt_r', 'Fn', 'Menu', 'Ctrl_r', 'up', '0\nIns', ' . '],
   ['Left', 'Down', 'Right']
  ]
  
  numpad_shifts = {'first': 69, 'second': 140, 'third': 210}
  first_column_keys = ['7\nHome', '8\n↑', '9\nPgUp', '+']
  second_column_keys = ['4\n←', '5\n', '6\n→']
  third_column_keys = ['1\nEnd', '2\n↓', '3\nPgDn', 'KEnter']
  
  special_keys = {
   '0': 'KP0', '1': 'KP1', '2': 'KP2', '3': 'KP3', '4': 'KP4', '5': 'KP5', '6': 'KP6', '7': 'KP7', '8': 'KP8', '9': 'KP9',
   '/': 'KPSLASH', '*': 'KPMULTIPLY', '-': 'KPMINUS', '+': 'KPPLUS', '.': 'KPDOT',
   'Shift_R': 'RIGHTSHIFT', 'Alt_r': 'RIGHTALT', 'Ctrl_r': 'RIGHTCTRL',
   'Shift_L': 'LEFTSHIFT', 'Alt_L': 'LEFTALT', 'Ctrl': 'LEFTCTRL',
   'up': 'UP', 'down': 'DOWN', 'left': 'LEFT', 'right': 'RIGHT',
  }
  
  for i, row in enumerate(keyboard_layout):
   for j, key in enumerate(row):
    x1 = BASE_X_STEP * j + X_OFFSET
    y1 = BASE_Y_STEP * i + Y_OFFSET
    w, h = BUTTON_WIDTH, BUTTON_HEIGHT
    
    btn = QPushButton(key, keyboard_widget)
    if self.callback_func:
     clean_key = key.split('\n')[0].strip()
     key_for_scancode = special_keys.get(clean_key, clean_key)
     btn.clicked.connect(lambda checked, k=key_for_scancode: (self.callback_func(k), self.accept()))
    
    x_pos, y_pos = x1, y1
    
    if key == 'Backspace':
     w = 120
    elif i == 1 and j > 13:
     x_pos = x1 + 69
    
    if i >= 2:
     if key in first_column_keys:
      x_pos += numpad_shifts['first']
      if key.strip() == '+': btn.setText("+")
     if key in second_column_keys: x_pos += numpad_shifts['second']
     if key in third_column_keys:
      x_pos += numpad_shifts['third']
      if key == 'KEnter': h = BUTTON_HEIGHT * 2 + 5; btn.setText("Enter")
    
    if key == '\nEnter\n': w, h = 140, BUTTON_HEIGHT * 2 + 5
    
    if i == 5:
     if key == 'space':
      w, x_pos = 300, x1
     elif key in ['Alt_r', 'Fn', 'Menu', 'Ctrl_r']:
      x_pos = x1 + 210
     elif key == 'up':
      x_pos = x1 + 330
     elif key == '0\nIns':
      x_pos, w = x1 + 420, 120
     elif key.strip() == '.':
      x_pos = x1 + 490
    
    if i == 6:
     if key in ['Left', 'Down', 'Right']: x_pos, y_pos = x1 + 820, y1 - 9
    
    btn.setGeometry(x_pos, y_pos, w, h)
  main_layout.addWidget(keyboard_widget)


class MainWindow(QWidget):
 """Главное окно приложения (только UI)"""
 closing = pyqtSignal()  # Сигнал для сохранения настроек при закрытии
 
 def __init__(self):
  super().__init__()
  self.setWindowTitle("Xenia Gamepad Config Editor")
  self.setStyleSheet("background-color: #0f1023; color: white;")
  
  main_layout = QVBoxLayout(self)
  main_layout.setContentsMargins(10, 10, 10, 10)
  main_layout.setSpacing(8)
  
  main_layout.addWidget(self._build_header())
  self.gamepad = GamepadWidget("")
  self.gamepad.mouse_moved_rel.connect(self._on_mouse_moved)
  main_layout.addWidget(self.gamepad, alignment=Qt.AlignmentFlag.AlignCenter)
  main_layout.addWidget(self._build_footer())
 
 # Событие закрытия окна
 def closeEvent(self, event):
  self.closing.emit()
  super().closeEvent(event)
 
 def _build_header(self):
  frame = QFrame()
  frame.setFixedHeight(90)
  frame.setStyleSheet("QFrame{background:#1c1e3d;border:1px solid #2d5cf7;border-radius:8px;}")
  lay = QHBoxLayout(frame)
  lay.setContentsMargins(15, 8, 15, 8)
  
  title = QLabel("XENIA GAMEPAD CONFIG")
  title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
  title.setStyleSheet("background:transparent;color:white;")
  lay.addWidget(title)
  
  lay.addStretch()
  lay.addWidget(QLabel("ПРОФИЛЬ:"))
  
  self.profile_combo = QComboBox()
  self.profile_combo.setFixedWidth(180)
  self.profile_combo.setStyleSheet("background:#0d0e1a;color:white;border:1px solid #2c2f5a;border-radius:4px;padding:4px;")
  lay.addWidget(self.profile_combo)
  
  self.btn_create = QPushButton("СОЗДАТЬ")
  self.btn_create.setFixedSize(110, 30)
  self.btn_create.setStyleSheet("background:#0070d2;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_create)
  
  self.btn_delete = QPushButton("УДАЛИТЬ")
  self.btn_delete.setFixedSize(110, 30)
  self.btn_delete.setStyleSheet("background:#e74c3c;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_delete)
  
  self.btn_defaults = QPushButton("ПО УМОЛЧАНИЮ")
  self.btn_defaults.setFixedSize(130, 30)
  self.btn_defaults.setStyleSheet("background:#f39c12;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_defaults)
  
  lay.addStretch()
  lay.addWidget(QLabel("Папка Xenia:"))
  
  self.config_path_edit = QLineEdit()
  self.config_path_edit.setFixedWidth(250)
  self.config_path_edit.setStyleSheet("background:#0d0e1a;color:white;border:1px solid #2c2f5a;border-radius:4px;padding:4px;")
  lay.addWidget(self.config_path_edit)
  
  self.btn_browse = QPushButton("📁")
  self.btn_browse.setFixedSize(30, 30)
  self.btn_browse.setStyleSheet("background:#0070d2;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_browse)
  
  self.btn_img = QPushButton("🖼 Изобр.")
  self.btn_img.setFixedSize(80, 30)
  self.btn_img.setStyleSheet("background:#6c3483;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_img)
  
  return frame
 
 def _build_footer(self):
  frame = QFrame()
  frame.setFixedHeight(40)
  frame.setStyleSheet("QFrame{background:#1c1e3d;border-radius:6px;}")
  lay = QHBoxLayout(frame)
  lay.setContentsMargins(15, 4, 15, 4)
  
  self.debug_cb = QCheckBox("Отладка зон (F3)")
  self.debug_cb.setChecked(True)
  self.debug_cb.setStyleSheet("color:#aaa;background:transparent;")
  lay.addWidget(self.debug_cb)
  self.debug_cb.toggled.connect(lambda v: self.gamepad.set_debug_mode(v))
  
  lay.addStretch()
  self.coord_label = QLabel("Координаты: —")
  self.coord_label.setStyleSheet("color:#888;background:transparent;font-family:Consolas;")
  lay.addWidget(self.coord_label)
  
  lay.addStretch()
  self.btn_apply = QPushButton("💾  ПРИМЕНИТЬ НАСТРОЙКИ В XENIA")
  self.btn_apply.setFixedSize(300, 30)
  self.btn_apply.setFont(QFont("Arial", 10, QFont.Weight.Bold))
  self.btn_apply.setStyleSheet("background:#4cd137;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_apply)
  
  return frame
 
 def _on_mouse_moved(self, rx, ry):
  self.coord_label.setText(f"Координаты: ({rx:.3f}, {ry:.3f})")


if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MainWindow()
 window.resize(1000, 700)
 window.show()
 sys.exit(app.exec())

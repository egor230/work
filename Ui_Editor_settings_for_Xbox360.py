import sys
from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDialog,
 QFrame, QToolTip, QCheckBox, QSlider, QComboBox, QApplication
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt6.QtGui import (
 QPixmap, QPainter, QColor, QPen, QBrush, QFont, QRadialGradient
)

# =====================================================================
# КЛАСС ДЛЯ ПРЕОБРАЗОВАНИЯ КЛАВИШ (адаптирован под evdev)
class KeyMapper:
 """Преобразует нажатия виртуальной клавиатуры в системные имена evdev (KEY_...)"""
 def __init__(self):
  # Маппинг для виртуальной клавиатуры (имя кнопки UI -> системное имя)
  self.virtual_keyboard_map = {
   'Esc': 'KEY_ESC', 'Insert': 'KEY_INSERT', 'Delete': 'KEY_DELETE', 'Home': 'KEY_HOME', 'End': 'KEY_END',
   'PgUp': 'KEY_PAGEUP', 'PgDn': 'KEY_PAGEDOWN', 'Backspace': 'KEY_BACKSPACE', 'Tab': 'KEY_TAB',
   'Caps Lock': 'KEY_CAPSLOCK', 'Num Lock': 'KEY_NUMLOCK', 'Shift_L': 'KEY_LEFTSHIFT', 'Shift_R': 'KEY_RIGHTSHIFT',
   'Ctrl': 'KEY_LEFTCTRL', 'Ctrl_r': 'KEY_RIGHTCTRL', 'Alt_L': 'KEY_LEFTALT', 'Alt_r': 'KEY_RIGHTALT',
   'Windows': 'KEY_LEFTMETA', 'Menu': 'KEY_MENU', 'space': 'KEY_SPACE',
   'up': 'KEY_UP', 'down': 'KEY_DOWN', 'left': 'KEY_LEFT', 'right': 'KEY_RIGHT',
   'KEnter': 'KEY_KPENTER'
  }
  # Словарь для красивого отображения в UI (KEY_LEFTSHIFT -> LShift)
  self.display_names = {
   "KEY_SPACE": "SPACE", "KEY_ENTER": "ENTER", "KEY_BACKSPACE": "BACK", "KEY_TAB": "TAB", "KEY_ESC": "ESC",
   "KEY_UP": "UP", "KEY_DOWN": "DOWN", "KEY_LEFT": "LEFT", "KEY_RIGHT": "RIGHT", "KEY_INSERT": "INS", "KEY_DELETE": "DEL",
   "KEY_HOME": "HOME", "KEY_END": "END", "KEY_PAGEUP": "PGUP", "KEY_PAGEDOWN": "PGDN", "KEY_CAPSLOCK": "CAPS",
   "KEY_NUMLOCK": "NUM", "KEY_LEFTCTRL": "LCTRL", "KEY_RIGHTCTRL": "RCTRL", "KEY_LEFTALT": "LALT", "KEY_RIGHTALT": "RALT",
   "KEY_LEFTSHIFT": "LSHIFT", "KEY_RIGHTSHIFT": "RSHIFT", "KEY_LEFTMETA": "LWIN", "KEY_MENU": "MENU",
   "KEY_KP0": "NUM0", "KEY_KP1": "NUM1", "KEY_KP2": "NUM2", "KEY_KP3": "NUM3", "KEY_KP4": "NUM4",
   "KEY_KP5": "NUM5", "KEY_KP6": "NUM6", "KEY_KP7": "NUM7", "KEY_KP8": "NUM8", "KEY_KP9": "NUM9",
   "KEY_KPPLUS": "NUM+", "KEY_KPMINUS": "NUM-", "KEY_KPASTERISK": "NUM*", "KEY_KPSLASH": "NUM/",
   "KEY_KPENTER": "NUMENT", "KEY_KPDOT": "NUM."
  }

 def _is_numpad_key(self, i, j):
  """Определяет, находится ли клавиша в области NumPad на виртуальной клавиатуре"""
  # Основная область NumPad (цифры 7,8,9, /, *, -, +)
  if i >= 2 and j >= 13:
   return True
  # Средний ряд (4,5,6)
  if i == 3 and j >= 12:
   return True
  # Нижний ряд (1,2,3, Enter)
  if i == 4 and j >= 11:
   return True
  # Строка с 0, Ins, ., стрелки (i=5, j>=8)
  if i == 5 and j >= 8:
   return True
  # Строка стрелок (i=6)
  if i == 6:
   return True
  return False

 def map_virtual_key(self, key_from_ui, i=-1, j=-1):
  """Преобразует ключ из виртуальной клавиатуры в системное имя evdev"""
  base = self.virtual_keyboard_map.get(key_from_ui, f"KEY_{key_from_ui.upper()}")
  if key_from_ui.startswith('F') and key_from_ui[1:].isdigit():
   return f"KEY_{key_from_ui.upper()}"
  if self._is_numpad_key(i, j):
   if key_from_ui.isdigit(): return f"KEY_KP{key_from_ui}"
   if key_from_ui == '/': return 'KEY_KPSLASH'
   if key_from_ui == '*': return 'KEY_KPASTERISK'
   if key_from_ui == '-': return 'KEY_KPMINUS'
   if key_from_ui == '+': return 'KEY_KPPLUS'
   if key_from_ui == '.': return 'KEY_KPDOT'
   if key_from_ui == 'Enter': return 'KEY_KPENTER'
  return base

 def to_display(self, evdev_key):
  """Преобразует код evdev (KEY_A) в короткое имя для отображения (A)"""
  if not evdev_key: return ""
  return self.display_names.get(evdev_key, evdev_key.replace("KEY_", ""))

 def default_mapping(self):
  """Настройки профиля по умолчанию (в формате evdev)"""
  return {
   "A": "KEY_SPACE", "B": "KEY_B", "X": "KEY_X", "Y": "KEY_Y", "LEFT_SHOULDER": "KEY_Q", "RIGHT_SHOULDER": "KEY_E",
   "LEFT_TRIGGER": "KEY_1", "RIGHT_TRIGGER": "KEY_2", "GUIDE": "KEY_F12", "BACK": "KEY_BACKSPACE", "START": "KEY_ENTER",
   "DPAD_UP": "KEY_UP", "DPAD_DOWN": "KEY_DOWN", "DPAD_LEFT": "KEY_LEFT", "DPAD_RIGHT": "KEY_RIGHT",
   "LEFT_THUMB_UP": "KEY_W", "LEFT_THUMB_DOWN": "KEY_S", "LEFT_THUMB_LEFT": "KEY_A", "LEFT_THUMB_RIGHT": "KEY_D",
   "RIGHT_THUMB_UP": "KEY_KP8", "RIGHT_THUMB_DOWN": "KEY_KP2", "RIGHT_THUMB_LEFT": "KEY_KP4", "RIGHT_THUMB_RIGHT": "KEY_KP6",
   "LEFT_THUMB_PRESSED": "KEY_LEFTSHIFT", "RIGHT_THUMB_PRESSED": "KEY_Z"
  }

KEY_MAPPER = KeyMapper()

# =====================================================================
# ОПРЕДЕЛЕНИЕ ЗОН
# =====================================================================
ZONE_DEFINITIONS = [
 ("LT", "LEFT_TRIGGER", 0.13, 0.07, 0.18, 0.06, "#e67e22", "rect"),
 ("RT", "RIGHT_TRIGGER", 0.69, 0.07, 0.18, 0.06, "#e67e22", "rect"),
 ("LB", "LEFT_SHOULDER", 0.14205128205128206, 0.17369408369408368, 0.16, 0.07, "#95a5a6", "rect"),
 ("RB", "RIGHT_SHOULDER", 0.697948717948718, 0.1708080808080808, 0.16, 0.07, "#95a5a6", "rect"),
 ("Guide", "GUIDE", 0.46, 0.23, 0.08, 0.1, "#3498db", "ellipse"),
 ("Back", "BACK", 0.398974358974359, 0.3728860028860029, 0.05, 0.06, "#9b59b6", "ellipse"),
 ("Start", "START", 0.5546153846153845, 0.3816450216450216, 0.05, 0.06, "#9b59b6", "ellipse"),
 ("L↑", "LEFT_THUMB_UP", 0.18974358974358976, 0.2901010101010101, 0.06, 0.06, "#5b8cff", "rect"),
 ("L↓", "LEFT_THUMB_DOWN", 0.19743589743589746, 0.46741702741702745, 0.06, 0.06, "#5b8cff", "rect"),
 ("L←", "LEFT_THUMB_LEFT", 0.10564102564102565, 0.36, 0.06, 0.06, "#5b8cff", "rect"),
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
 def __init__(self, name, logical_name, rx, ry, rw, rh, color_hex, shape="rect"):
  self.name, self.logical_name = name, logical_name
  self.rx, self.ry, self.rw, self.rh = rx, ry, rw, rh
  self.color = QColor(color_hex)
  self.shape = shape
  self.hovered, self.pressed = False, False
  self.current_binding = ""
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
 zone_clicked = pyqtSignal(str)
 zones_changed = pyqtSignal()
 def __init__(self, image_path, parent=None):
  super().__init__(parent)
  self.bg_pixmap = self._load_and_crop_image(image_path)
  self.setFixedSize(self.bg_pixmap.size())
  self.setMouseTracking(True)
  self.zones = [InteractiveZone(*z) for z in ZONE_DEFINITIONS]
  self._hovered_zone = None
  self._edit_enabled = False
  self._edit_mode = False
  self._drag_zone = None
  self._drag_start_pos = None
  self._drag_start_rx = None
  self._drag_start_ry = None
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
   p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "gamepad xbox 360.png не найден")
   p.end()
   return pix
  w, h = pix.width(), pix.height()
  crop_rect = QRectF(w * 0.05, h * 0.02, w * 0.90, h * 0.80).toRect()
  return pix.copy(crop_rect)

 def set_debug_mode(self, on):
  self._edit_enabled = on
  self._edit_mode = False
  self._drag_zone = None
  self.setCursor(Qt.CursorShape.ArrowCursor)
  self.update()

 def update_binding(self, logical, key_str):
  for z in self.zones:
   if z.logical_name == logical:
    z.current_binding = KEY_MAPPER.to_display(key_str) # Показываем красивое имя
    break
  self.update()

 def update_all_bindings(self, mapping):
  for z in self.zones:
   z.current_binding = KEY_MAPPER.to_display(mapping.get(z.logical_name, ""))
  self.update()

 def set_image(self, path):
  pix = self._load_and_crop_image(path)
  if not pix.isNull():
   self.bg_pixmap = pix
   self.setFixedSize(pix.size())
   self.update()

 def get_zones_data(self):
  result = []
  for z in self.zones:
   result.append({"name": z.name, "logical_name": z.logical_name, "rx": z.rx, "ry": z.ry, "rw": z.rw, "rh": z.rh, "color": z.color.name(), "shape": z.shape})
  return result

 def set_zones_data(self, data):
  for item in data:
   for z in self.zones:
    if z.logical_name == item.get("logical_name"):
     z.rx = item.get("rx", z.rx)
     z.ry = item.get("ry", z.ry)
     z.rw = item.get("rw", z.rw)
     z.rh = item.get("rh", z.rh)
     break
  self.update()

 def paintEvent(self, event):
  painter = QPainter(self)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)
  w, h = self.width(), self.height()
  painter.drawPixmap(0, 0, self.bg_pixmap)
  for z in self.zones:
   rect = z.abs_rect(w, h)
   if z.current_binding:
    painter.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.PenStyle.DashLine))
    painter.setBrush(QBrush(QColor(255, 255, 255, 15)))
    if z.shape == "ellipse": painter.drawEllipse(rect)
    else: painter.drawRoundedRect(rect, 4, 4)
    self._paint_label(painter, z, rect)
   else:
    painter.setPen(QColor(255, 255, 255, 30))
    painter.setFont(QFont("Consolas", 7))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, z.name)
   if z.hovered and not z.pressed:
    self._paint_highlight(painter, z, rect, 140, is_hover=True)
    self._paint_label(painter, z, rect)
   if z.pressed:
    self._paint_highlight(painter, z, rect, 200, is_hover=False)
    self._paint_label(painter, z, rect)
   if self._edit_mode and z == self._drag_zone:
    painter.setPen(QPen(QColor("#ffeb3b"), 2, Qt.PenStyle.DashLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if z.shape == "ellipse": painter.drawEllipse(rect.adjusted(-3, -3, 3, 3))
    else: painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 4, 4)
  painter.end()

 def _paint_highlight(self, painter, z, rect, alpha, is_hover=False):
  base_color = QColor("#2d5cf7") if is_hover else QColor(z.color)
  fill, glow = QColor(base_color), QColor(base_color)
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
   grad.setColorAt(1.0, base_color.darker(160))
   painter.setBrush(QBrush(grad))
  else:
   painter.drawRoundedRect(glow_rect, 5, 5)
   painter.setBrush(QBrush(fill))
   painter.setPen(QPen(QColor(255, 255, 255, alpha), 1.5))
   painter.drawRoundedRect(rect, 4, 4)

 def _paint_label(self, painter, z, rect):
  painter.setPen(QColor(255, 255, 255, 240))
  painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
  text = z.name + (f"\n[{z.current_binding}]" if z.current_binding else "")
  painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

 def _zone_at(self, pos):
  for z in reversed(self.zones):
   if z.contains(pos, self.width(), self.height()): return z
  return None

 def mouseMoveEvent(self, event):
  pos = event.position()
  if self._edit_mode and self._drag_zone and self._drag_start_pos:
   dx = (pos.x() - self._drag_start_pos.x()) / self.width()
   dy = (pos.y() - self._drag_start_pos.y()) / self.height()
   self._drag_zone.rx = max(0.0, min(1.0 - self._drag_zone.rw, self._drag_start_rx + dx))
   self._drag_zone.ry = max(0.0, min(1.0 - self._drag_zone.rh, self._drag_start_ry + dy))
   self.update()
   return
  zone = self._zone_at(pos)
  if zone != self._hovered_zone:
   if self._hovered_zone: self._hovered_zone.hovered = False
   if zone: zone.hovered = True
   self._hovered_zone = zone
   self.update()
  if self._edit_mode: self.setCursor(Qt.CursorShape.OpenHandCursor if zone else Qt.CursorShape.ArrowCursor)
  else: self.setCursor(Qt.CursorShape.PointingHandCursor if zone else Qt.CursorShape.ArrowCursor)
  super().mouseMoveEvent(event)

 def mousePressEvent(self, event):
  if event.button() == Qt.MouseButton.LeftButton:
   zone = self._zone_at(event.position())
   if zone:
    if self._edit_enabled:
     self._edit_mode = True
     self._drag_zone = zone
     self._drag_start_pos = event.position()
     self._drag_start_rx = zone.rx
     self._drag_start_ry = zone.ry
     self.setCursor(Qt.CursorShape.ClosedHandCursor)
     self.update()
    else:
     zone.pressed = True
     self.update()
     self.zone_clicked.emit(zone.logical_name)

 def mouseReleaseEvent(self, event):
  if event.button() == Qt.MouseButton.LeftButton:
   if self._edit_mode and self._drag_zone:
    self._drag_zone = None
    self._drag_start_pos = None
    self.setCursor(Qt.CursorShape.OpenHandCursor)
    self.zones_changed.emit()
    self.update()
   else: self._press_timer.start()

 def wheelEvent(self, event):
  if self._edit_enabled:
   pos = event.position()
   zone = self._zone_at(pos)
   if zone:
    delta = event.angleDelta().y()
    scale = 1.05 if delta > 0 else 0.95
    zone.rw = max(0.01, min(0.5, zone.rw * scale))
    zone.rh = max(0.01, min(0.5, zone.rh * scale))
    self.zones_changed.emit()
    self.update()
    return
  super().wheelEvent(event)

 def _release_all(self):
  for z in self.zones: z.pressed = False
  self.update()

 def leaveEvent(self, event):
  if self._hovered_zone:
   self._hovered_zone.hovered = False
   self._hovered_zone = None
  self.update()
  super().leaveEvent(event)

class VirtualKeyboard(QDialog):
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
  keyboard_widget.setStyleSheet("QPushButton{background-color:#3949ab;color:white;border:2px solid #5c6bc0;border-radius:5px;padding:5px;font-weight:bold;font-size:12px;}QPushButton:hover{background-color:#5c6bc0;border:2px solid #7986cb;}QPushButton:pressed{background-color:#283593;color:#bbdefb;}")
  BUTTON_WIDTH, BUTTON_HEIGHT = 60, 40
  BASE_X_STEP, BASE_Y_STEP = 70, 50
  X_OFFSET, Y_OFFSET = 6, 6
  keyboard_layout = [
   ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'Insert', 'Delete', 'Home', 'End', 'PgUp', 'PgDn'],
   ['~\n`', '!\n1', '@\n2', '#\n3', '$\n4', '%\n5', '^\n6', '&\n7', '\n8', '(\n9', ')\n0', '_\n-', '+\n=', 'Backspace', 'Num Lock', '/', '*', '-'],
   ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{\n[', '}\n]', '|\n\\', '7\nHome', '8\n↑', '9\nPgUp', '+'],
   ['Caps Lock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':\n;', '"\n\'', '\nEnter\n', '4\n←', '5\n', '6\n→'],
   ['Shift_L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<\n,', '>\n.', '?\n/', 'Shift_R', '1\nEnd', '2\n↓', '3\nPgDn', 'KEnter'],
   ['Ctrl', 'Windows', 'Alt_L', 'space', 'Alt_r', 'Fn', 'Menu', 'Ctrl_r', 'up', '0\nIns', '.'],
   ['Left', 'Down', 'Right']
  ]
  numpad_shifts = {'first': 69, 'second': 140, 'third': 210}
  first_column_keys = ['7\nHome', '8\n↑', '9\nPgUp', '+']
  second_column_keys = ['4\n←', '5\n', '6\n→']
  third_column_keys = ['1\nEnd', '2\n↓', '3\nPgDn', 'KEnter']
  for i, row in enumerate(keyboard_layout):
   for j, key in enumerate(row):
    x1 = BASE_X_STEP * j + X_OFFSET
    y1 = BASE_Y_STEP * i + Y_OFFSET
    w, h = BUTTON_WIDTH, BUTTON_HEIGHT
    btn = QPushButton(key, keyboard_widget)
    if self.callback_func:
     clean_key = key.split('\n')[0].strip()
     key_for_system = KEY_MAPPER.map_virtual_key(clean_key, i, j)
     if i == 1 and 1 <= j <= 10:
      parts = key.split('\n')
      if len(parts) > 1: key_for_system = f"KEY_{parts[1].strip()}"
     btn.clicked.connect(lambda checked, k=key_for_system: (self.callback_func(k), self.accept()))
    x_pos, y_pos = x1, y1
    if key == 'Backspace': w = 120
    elif i == 1 and j > 13: x_pos = x1 + 69
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
     if key == 'space': w, x_pos = 300, x1
     elif key in ['Alt_r', 'Fn', 'Menu', 'Ctrl_r']: x_pos = x1 + 240
     elif key == 'up': x_pos = x1 + 330
     elif key == '0\nIns': x_pos, w = x1 + 420, 120
     elif key.strip() == '.': x_pos = x1 + 490
    if i == 6:
     if key in ['Left', 'Down', 'Right']: x_pos, y_pos = x1 + 820, y1 - 9
    btn.setGeometry(x_pos, y_pos, w, h)
  main_layout.addWidget(keyboard_widget)

class MainWindow(QWidget):
 closing = pyqtSignal()
 def __init__(self):
  super().__init__()
  self.setWindowTitle("Xbox 360 Virtual Controller")
  self.setStyleSheet("background-color: #0f1023; color: white;")
  main_layout = QVBoxLayout(self)
  main_layout.setContentsMargins(10, 10, 10, 10)
  main_layout.setSpacing(8)
  main_layout.addWidget(self._build_header())
  self.gamepad = GamepadWidget("")
  main_layout.addWidget(self.gamepad, alignment=Qt.AlignmentFlag.AlignCenter)
  main_layout.addWidget(self._build_settings_row()) # Добавлена строка настроек
  main_layout.addWidget(self._build_footer())

 def closeEvent(self, event):
  self.closing.emit()
  super().closeEvent(event)

 def _build_header(self):
  frame = QFrame()
  frame.setFixedHeight(90)
  frame.setStyleSheet("QFrame{background:#1c1e3d;border:1px solid #2d5cf7;border-radius:8px;}")
  lay = QHBoxLayout(frame)
  lay.setContentsMargins(15, 8, 15, 8)
  title = QLabel("XBOX 360 EMULATOR")
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
  self.btn_defaults = QPushButton("СБРОС")
  self.btn_defaults.setFixedSize(110, 30)
  self.btn_defaults.setStyleSheet("background:#f39c12;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_defaults)
  lay.addStretch()
  self.btn_img = QPushButton("🖼 Изобр.")
  self.btn_img.setFixedSize(80, 30)
  self.btn_img.setStyleSheet("background:#6c3483;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_img)
  return frame

 def _build_settings_row(self): # Новая строка для настроек эмуляции
  frame = QFrame()
  frame.setFixedHeight(40)
  frame.setStyleSheet("QFrame{background:#1c1e3d;border-radius:6px;}")
  lay = QHBoxLayout(frame)
  lay.setContentsMargins(15, 4, 15, 4)
  self.sl_sens = QSlider(Qt.Orientation.Horizontal)
  self.sl_sens.setRange(1, 15)
  self.sl_sens.setValue(5)
  self.sl_sens.setFixedWidth(100)
  self.chk_grab = QCheckBox("Захват KB")
  self.chk_grab.setChecked(True)
  self.chk_grab.setStyleSheet("color:#aaa;background:transparent;")
  # lay.addWidget(self.chk_grab)  # [скрыто] Захват KB
  self.chk_mouse = QCheckBox("Мышь → Правый стик")
  self.chk_mouse.setStyleSheet("color:#aaa;background:transparent;")
  # lay.addWidget(self.chk_mouse)  # [скрыто] Мышь → Правый стик
  # lay.addWidget(QLabel("Чувств:"))  # [скрыто] Надпись чувствительности
  self.lbl_sens = QLabel("5")
  self.lbl_sens.setStyleSheet("color:white;")
  # self.sl_sens.valueChanged.connect(lambda v: self.lbl_sens.setText(str(v)))  # [скрыто] Обновление метки
  # lay.addWidget(self.sl_sens)  # [скрыто] Ползунок чувствительности
  # lay.addWidget(self.lbl_sens)  # [скрыто] Значение чувствительности
  self.chk_smooth = QCheckBox("Сглаживание")
  self.chk_smooth.setChecked(True)
  self.chk_smooth.setStyleSheet("color:#aaa;background:transparent;")
  # lay.addWidget(self.chk_smooth)  # [скрыто] Сглаживание
  self.debug_cb = QCheckBox("Двигать зоны (F3)")
  self.debug_cb.setChecked(False)
  self.debug_cb.setStyleSheet("color:#aaa;background:transparent;")
  lay.addWidget(self.debug_cb)  # [скрыто] Двигать зоны (F3)
  self.debug_cb.toggled.connect(lambda v: self.gamepad.set_debug_mode(v))
  return frame

 def _build_footer(self):
  frame = QFrame()
  frame.setFixedHeight(50)
  frame.setStyleSheet("QFrame{background:#1c1e3d;border-radius:6px;}")
  lay = QHBoxLayout(frame)
  lay.setContentsMargins(15, 4, 15, 4)
  self.st_lbl = QLabel("Статус: Остановлен")
  self.st_lbl.setStyleSheet("font-weight: 600; color: #6C757D; font-size: 14px;")
  lay.addWidget(self.st_lbl)
  lay.addStretch()
  self.btn_start = QPushButton("▶  ЗАПУСК  ЭМУЛЯЦИИ")
  self.btn_start.setFixedSize(300, 35)
  self.btn_start.setFont(QFont("Arial", 10, QFont.Weight.Bold))
  self.btn_start.setStyleSheet("background:#198754;color:white;border:none;border-radius:4px;")
  lay.addWidget(self.btn_start)
  return frame
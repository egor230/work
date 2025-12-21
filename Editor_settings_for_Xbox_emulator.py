import sys
import os
import shutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QGridLayout, QComboBox, QPushButton, QLabel, QInputDialog, QDialog,
                            QFrame, QGraphicsDropShadowEffect, QMessageBox, QSizePolicy, QLineEdit)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont
from XemuLogic import XemuConfigManager


class GlowButton(QPushButton):
  def __init__(self, text="", glow_color="#0298ff", parent=None):
    super().__init__(text, parent)
    self._glow_color = QColor(glow_color)
    self.shadow_effect = QGraphicsDropShadowEffect()
    self.shadow_effect.setColor(self._glow_color)
    self.shadow_effect.setBlurRadius(0)
    self.shadow_effect.setOffset(0, 0)
    self.setGraphicsEffect(self.shadow_effect)
    self.glow_animation = QPropertyAnimation(self.shadow_effect, b"blurRadius")
    self.glow_animation.setDuration(300)
    self.glow_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    self.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))

  def enterEvent(self, event):
    self.glow_animation.stop()
    self.glow_animation.setStartValue(self.shadow_effect.blurRadius())
    self.glow_animation.setEndValue(20)
    self.glow_animation.start()
    super().enterEvent(event)

  def leaveEvent(self, event):
    self.glow_animation.stop()
    self.glow_animation.setStartValue(self.shadow_effect.blurRadius())
    self.glow_animation.setEndValue(0)
    self.glow_animation.start()
    super().leaveEvent(event)


class VirtualKeyboard(QDialog):
  def __init__(self, parent, callback_func=None):
    super().__init__(parent)
    self.setWindowTitle("Настройка клавиши")
    self.setFixedSize(1410, 450)
    self.setStyleSheet("""
      QDialog {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a2e, stop:1 #16213e);
        border-radius: 15px;
        border: 2px solid #3949ab;
      }
    """)
    self.callback_func = callback_func
    self.create_keyboard_layout()

  def create_keyboard_layout(self):
    layout = QVBoxLayout(self)
    layout.setContentsMargins(20, 20, 20, 20)

    title = QLabel("ВЫБЕРИТЕ КЛАВИШУ")
    title.setStyleSheet("""
      QLabel {
        color: #ffffff;
        font-size: 24px;
        font-weight: bold;
        padding: 10px;
        background: rgba(57, 73, 171, 0.3);
        border-radius: 10px;
        border: 1px solid #5c6bc0;
      }
    """)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)

    keyboard_widget = QWidget()
    keyboard_widget.setMinimumSize(850, 340)

    BUTTON_WIDTH = 60
    BUTTON_HEIGHT = 40
    BASE_X_STEP = 70
    BASE_Y_STEP = 50
    X_OFFSET = 6
    Y_OFFSET = 6

    keyboard_layout = [
      ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
       'Insert', 'Delete', 'Home', 'End', 'PgUp', 'PgDn'],
      ['~\n`', '!\n1', '@\n2', '#\n3', '$\n4', '%\n5', '^\n6', '&\n7', '*\n8', '(\n9',
       ')\n0', '_\n-', '+\n=', 'Backspace', 'Num Lock', '/', '*', '-'],
      ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{\n[', '}\n]', '|\n\\',
       ' 7\nHome', '8\n↑', '9\nPgUp', '+'],
      ['Caps Lock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':\n;', '"\n\'',
       '\nEnter\n', '4\n←', '5\n', '6\n→'],
      ['Shift_L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<\n,', '>\n.', '?\n/', 'Shift_R',
       '1\nEnd', '2\n↓', '3\nPgDn', 'KEnter'],
      ['Ctrl', 'Windows', 'Alt_L', 'space', 'Alt_r', 'Fn', 'Menu', 'Ctrl_r',
       'up', '0\nIns', ' . '],
      ['Left', 'Down', 'Right']
    ]

    style_sheet = """
      QPushButton {
        background-color: #3949ab;
        color: white;
        border: 2px solid #5c6bc0;
        border-radius: 5px;
        padding: 5px;
        font-weight: bold;
        font-size: 12px;
      }
      QPushButton:hover {
        background-color: #5c6bc0;
        border: 2px solid #7986cb;
      }
      QPushButton:pressed {
        background-color: #283593;
        color: #bbdefb;
      }
    """
    keyboard_widget.setStyleSheet(style_sheet)

    numpad_shifts = {'first': 69, 'second': 140, 'third': 210}
    first_column_keys = [' 7\nHome', '8\n↑', '9\nPgUp', '+']
    second_column_keys = ['4\n←', '5\n', '6\n→']
    third_column_keys = ['1\nEnd', '2\n↓', '3\nPgDn', 'KEnter']

    for i, row in enumerate(keyboard_layout):
      for j, key in enumerate(row):
        x1 = BASE_X_STEP * j + X_OFFSET
        y1 = BASE_Y_STEP * i + Y_OFFSET
        w = BUTTON_WIDTH
        h = BUTTON_HEIGHT

        btn = QPushButton(key, keyboard_widget)

        if self.callback_func:
          clean_key = key.split('\n')[0].strip()
          special_keys = {
            '0': 'KP0', '1': 'KP1', '2': 'KP2', '3': 'KP3', '4': 'KP4',
            '5': 'KP5', '6': 'KP6', '7': 'KP7', '8': 'KP8', '9': 'KP9',
            '/': 'KPSLASH', '*': 'KPMULTIPLY', '-': 'KPMINUS', '+': 'KPPLUS',
            '.': 'KPDOT',
            'Shift_R': 'RIGHTSHIFT', 'Alt_r': 'RIGHTALT', 'Ctrl_r': 'RIGHTCTRL',
            'Shift_L': 'LEFTSHIFT', 'Alt_L': 'LEFTALT', 'Ctrl': 'LEFTCTRL',
            'up': 'UP', 'down': 'DOWN', 'left': 'LEFT', 'right': 'RIGHT',
          }
          key_for_scancode = special_keys.get(clean_key, clean_key)
          btn.clicked.connect(
            lambda checked, k=key_for_scancode: (self.callback_func(k), self.accept())
          )

        x_pos = x1
        y_pos = y1

        if key == 'Backspace':
          w = 120
        elif i == 1 and j > 13:
          x_pos = x1 + 69
        if i >= 2:
          if key in first_column_keys:
            x_pos += numpad_shifts['first']
            if key == "+":
              btn.setText(" + ")
          if key in second_column_keys:
            x_pos += numpad_shifts['second']
          if key in third_column_keys:
            x_pos += numpad_shifts['third']
            if key == "KEnter":
              h = BUTTON_HEIGHT * 2 + 5
              btn.setText(" Enter ")

        if key == '\nEnter\n':
          w = 140
          h = BUTTON_HEIGHT * 2 + 5

        if i == 5:
          if key == "space":
            w = 300
            x_pos = x1
          elif key in ['Alt_r', 'Fn', 'Menu', 'Ctrl_r']:
            x_pos = x1 + 210
          elif key == 'up':
            x_pos = x1 + 280
          elif key == "0\nIns":
            x_pos = x1 + 420
            w = 120
          elif key == ' . ':
            x_pos = x1 + 490

        if i == 6:
          if key in ['Left', 'Down', 'Right']:
            x_pos = x1 + 770
            y_pos = y1 - 9

        btn.setGeometry(x_pos, y_pos, w, h)

    layout.addWidget(keyboard_widget)


class XemuUltimateEditor(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle("Xemu Master Config Pro")
    self.setFixedSize(1050, 750)
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

    self.config_manager = XemuConfigManager()
    self.config_manager.load_profiles()
    last_profile = self.config_manager.profiles.get("last_profile", "obscure")
    if not last_profile or last_profile not in self.config_manager.profiles:
      last_profile = "obscure"
    self.current_profile = last_profile

    self.input_btns = {}
    self.create_widgets()

    # После создания combo заполняем его и выбираем текущий профиль
    self.update_profile_combo()
    self.update_button_labels()

  def create_widgets(self):
    # --- ВЕРХНЯЯ ПАНЕЛЬ ---
    header = QFrame(self)
    header.setStyleSheet(f"""
      background-color: {self.colors['frame_bg']};
      border: 1px solid {self.colors['accent_blue']};
    """)
    header.setGeometry(20, 20, 1010, 80)

    title_label = QLabel("🎮 XEMU ULTIMATE CONFIG", header)
    title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
    title_label.setStyleSheet(f"background-color: {self.colors['frame_bg']}; color: white;")
    title_label.setGeometry(20, 22, 350, 40)

    profile_label = QLabel("ПРОФИЛЬ:", header)
    profile_label.setStyleSheet(f"background-color: {self.colors['frame_bg']}; color: white;")
    profile_label.setGeometry(380, 28, 100, 25)

    # Заменили QLineEdit на QComboBox для выбора профиля
    self.profile_combo = QComboBox(header)
    self.profile_combo.setStyleSheet("background-color: #0d0e1a; color: white; border: none;")
    self.profile_combo.setGeometry(460, 28, 220, 25)
    self.profile_combo.currentTextChanged.connect(self.on_profile_select)  # При смене профиля

    create_profile_btn = QPushButton("💾 СОЗДАТЬ ПРОФИЛЬ", header)
    create_profile_btn.setStyleSheet(f"background-color: {self.colors['btn_blue']}; color: white; border: none;")
    create_profile_btn.setGeometry(700, 25, 140, 32)
    create_profile_btn.clicked.connect(self.new_profile)

    default_btn = QPushButton("🔄 ПО УМОЛЧАНИЮ", header)
    default_btn.setStyleSheet(f"background-color: {self.colors['btn_orange']}; color: white; border: none;")
    default_btn.setGeometry(850, 25, 140, 32)
    default_btn.clicked.connect(self.set_default_values)

    # --- ОСНОВНАЯ ОБЛАСТЬ ---
    main = QWidget(self)
    main.setStyleSheet(f"background-color: {self.colors['bg']};")
    main.setGeometry(20, 110, 1010, 580)

    # Боковые кнопки (подняты вверх)
    self.create_key(main, 30, 20, "LB\n(W)", "#7f8c8d", w=105, h=50)
    self.create_key(main, 30, 80, "LT\n(KP3)", "#e67e22", w=105, h=50)
    self.create_key(main, 870, 20, "RB\n(PMINUS)", "#7f8c8d", w=105, h=50)
    self.create_key(main, 870, 80, "RT\n(KPDOT)", "#e67e22", w=105, h=50)

    # Центральные кнопки (опущены вниз)
    self.create_key(main, 390, 330, "Guide\n(BACKSPACE)", "#3498db", w=100, h=50)
    self.create_key(main, 490, 330, "Back\n(PPLU!)", "#9b59b6", w=70, h=50)
    self.create_key(main, 550, 330, "Start\nPMINU", "#9b59b6", w=70, h=50)

    # Крестовины
    self.draw_cross_group(main, 80, 220, "D-PAD", "D-PAD", "I", "J", "L", "K")
    self.draw_cross_group(main, 780, 220, "Right Stick", "RS\n(T)", "KP8", "KP4", "KP6", "KP5")
    self.draw_cross_group(main, 80, 440, "Left Stick", "LS\n(PPLU!)", "UP", "LEFT", "RIGHT", "DOWN")
    self.draw_cross_group(main, 780, 440, "ABXY", "ABXY", "Y\nHTSH", "X\n(KP2)", "B\n(KP3)", "A\n(KPO)", center_color="#57606f")

    # Нижняя кнопка
    apply_btn = QPushButton("🚀 ПРИМЕНИТЬ НАСТРОЙКИ В XEMU", self)
    apply_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
    apply_btn.setStyleSheet(f"background-color: {self.colors['btn_green']}; color: white; border: none;")
    apply_btn.setGeometry(20, 700, 1010, 40)
    apply_btn.clicked.connect(self.export_xemu_config)

  def create_key(self, parent, x, y, text, color, w=40, h=40):
    lbl = QLabel(text, parent)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setFont(QFont("Arial", 7, QFont.Weight.Bold))
    lbl.setStyleSheet(f"background-color: {color}; color: white; border: none;")
    lbl.setGeometry(x, y, w, h)

    # Сохраняем по первой части текста (например "LB") для возможного обновления
    key_name = text.split('\n')[0]
    self.input_btns[key_name] = lbl

    # Делаем кликабельной (имитация кнопки)
    lbl.setProperty("key_text", text)
    lbl.mousePressEvent = lambda e, k=key_name: self.show_kb(k)

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

  def show_kb(self, key):
    def callback(k):
      scancode = self.config_manager.get_scancode_by_name(k)
      self.config_manager.update_mapping(self.current_profile, key, scancode)
      self.update_button_label(key, k)
    kb = VirtualKeyboard(self, callback)
    kb.exec()

  def update_button_labels(self):
    if self.current_profile not in self.config_manager.profiles:
      return
    mapping = self.config_manager.profiles[self.current_profile]["mapping"]
    for key, widget in self.input_btns.items():
      current_text = widget.text()
      base_name = current_text.split('\n')[0]
      if key in mapping and mapping[key] != 0:
        scancode = mapping[key]
        key_name = next((name for name, code in self.config_manager.key_name_to_scancode.items() if code == scancode), "???")
        widget.setText(f"{base_name}\n({key_name})")
      else:
        widget.setText(base_name)

  def update_button_label(self, key, val):
    if key in self.input_btns:
      widget = self.input_btns[key]
      base_name = widget.text().split('\n')[0]
      if val:
        widget.setText(f"{base_name}\n({val})")
      else:
        widget.setText(base_name)

  # Заполняем выпадающий список профилями и выбираем текущий
  def update_profile_combo(self):
    self.profile_combo.blockSignals(True)  # Отключаем сигналы на время обновления
    self.profile_combo.clear()
    for profile in self.config_manager.profiles:
      if profile != "last_profile":
        self.profile_combo.addItem(profile)
    if self.current_profile in [self.profile_combo.itemText(i) for i in range(self.profile_combo.count())]:
      self.profile_combo.setCurrentText(self.current_profile)
    else:
      self.current_profile = "obscure" if "obscure" in self.config_manager.profiles else self.profile_combo.itemText(0)
      self.profile_combo.setCurrentText(self.current_profile)
    self.profile_combo.blockSignals(False)

  # При выборе другого профиля из списка
  def on_profile_select(self, text):
    if text and text != self.current_profile:
      self.current_profile = text
      self.update_button_labels()

  def new_profile(self):
    name, ok = QInputDialog.getText(self, "Создать профиль", "Имя профиля:")
    if ok and name.strip():
      self.config_manager.new_profile(name.strip())
      self.update_profile_combo()
      self.profile_combo.setCurrentText(name.strip())
      self.current_profile = name.strip()
      self.update_button_labels()

  def set_default_values(self):
    reply = QMessageBox.question(self, "Подтверждение",
                                 f"Установить значения по умолчанию для профиля '{self.current_profile}'?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if reply == QMessageBox.StandardButton.Yes:
      self.config_manager.set_default_mapping(self.current_profile)
      self.update_button_labels()
      QMessageBox.information(self, "Готово", "Значения по умолчанию установлены!")

  def export_xemu_config(self):
    self.config_manager.set_last_profile(self.current_profile)
    is_valid, message = self.config_manager.validate_mapping_complete(self.current_profile)
    if not is_valid:
      QMessageBox.warning(self, "Не настроена кнопка", f"{message}\n\nНастройте кнопку перед сохранением.")
      return

    config_file = "/home/egor/.local/share/xemu/xemu/xemu.toml"
    if not os.path.exists(config_file):
      QMessageBox.warning(self, "Файл не найден", f"Файл настроек XEMU не найден: {config_file}")
      return

    backup_file = config_file + ".backup"
    try:
      shutil.copy2(config_file, backup_file)
    except Exception as e:
      print(f"Ошибка бэкапа: {e}")

    try:
      self.config_manager.export_xemu_config(config_file)
      QMessageBox.information(self, "Успешно", "Конфигурация XEMU обновлена!")
    except ValueError as e:
      QMessageBox.warning(self, "Ошибка", str(e))


if __name__ == "__main__":
  app = QApplication(sys.argv)
  window = XemuUltimateEditor()
  window.setFixedSize(1050, 750)
  window.show()
  sys.exit(app.exec())
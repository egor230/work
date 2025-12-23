import json, os, subprocess, sys, threading
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from evdev import InputDevice, ecodes, list_devices, categorize


class SettingsManager:
 def __init__(self, filename="macros.json"):
  self.filename = filename
  self.data = self.load()
  self.original_data = json.dumps(self.data, sort_keys=True)  # Для отслеживания изменений

 def load(self):
  if os.path.exists(self.filename):
   try:
    with open(self.filename, "r", encoding="utf-8") as f:
     return json.load(f)
   except:
    pass
  return {
   "current_app": "global",
   "keyboard_script": {
    "global": {"keys": {}}
   }
  }

 def save(self):
  with open(self.filename, "w", encoding="utf-8") as f:
   json.dump(self.data, f, indent=4, ensure_ascii=False)
  self.original_data = json.dumps(self.data, sort_keys=True)

 def has_changes(self):
  current_data = json.dumps(self.data, sort_keys=True)
  return current_data != self.original_data

 def get_current_app(self):
  return self.data.get("current_app", "global")

 def get_script(self, key):
  app = self.get_current_app()
  return self.data.get("keyboard_script", {}) \
   .get(app, {}) \
   .get("keys", {}) \
   .get(key, "")

 def set_script(self, key, script):
  app = self.get_current_app()
  if "keyboard_script" not in self.data:
   self.data["keyboard_script"] = {}
  if app not in self.data["keyboard_script"]:
   self.data["keyboard_script"][app] = {"keys": {}}
  if script.strip():
   self.data["keyboard_script"][app]["keys"][key] = script.strip()
  else:
   self.data["keyboard_script"][app]["keys"].pop(key, None)


settings = SettingsManager()

# Расширенная карта для numpad клавиш
simple_key_map = {
 'KEY_KP7': '7\nHome', 'KEY_KP8': '8\n↑', 'KEY_KP9': '9\nPgUp',
 'KEY_KP4': '4\n←', 'KEY_KP5': '5\n', 'KEY_KP6': '6\n→',
 'KEY_KP1': '1\nEnd', 'KEY_KP2': '2\n↓', 'KEY_KP3': '3\nPgDn',
 'KEY_KPDOT': 'Delete', 'KEY_KPDELETE': 'Delete',  # Добавлено для точки на numpad
}

# Карта преобразования evdev кодов в названия UI
evdev_to_ui_key = {
 ecodes.KEY_A: 'A', ecodes.KEY_B: 'B', ecodes.KEY_C: 'C', ecodes.KEY_D: 'D',
 ecodes.KEY_E: 'E', ecodes.KEY_F: 'F', ecodes.KEY_G: 'G', ecodes.KEY_H: 'H',
 ecodes.KEY_I: 'I', ecodes.KEY_J: 'J', ecodes.KEY_K: 'K', ecodes.KEY_L: 'L',
 ecodes.KEY_M: 'M', ecodes.KEY_N: 'N', ecodes.KEY_O: 'O', ecodes.KEY_P: 'P',
 ecodes.KEY_Q: 'Q', ecodes.KEY_R: 'R', ecodes.KEY_S: 'S', ecodes.KEY_T: 'T',
 ecodes.KEY_U: 'U', ecodes.KEY_V: 'V', ecodes.KEY_W: 'W', ecodes.KEY_X: 'X',
 ecodes.KEY_Y: 'Y', ecodes.KEY_Z: 'Z',
 ecodes.KEY_1: '!', ecodes.KEY_2: '@', ecodes.KEY_3: '#', ecodes.KEY_4: '$',
 ecodes.KEY_5: '%', ecodes.KEY_6: '^', ecodes.KEY_7: '&', ecodes.KEY_8: '*',
 ecodes.KEY_9: '(', ecodes.KEY_0: ')',
 ecodes.KEY_SPACE: 'space',
 ecodes.KEY_ENTER: 'Enter',
 ecodes.KEY_BACKSPACE: 'Backspace',
 ecodes.KEY_TAB: 'Tab',
 ecodes.KEY_CAPSLOCK: 'Caps Lock',
 ecodes.KEY_LEFTSHIFT: 'Shift_L',
 ecodes.KEY_RIGHTSHIFT: 'Shift',
 ecodes.KEY_LEFTCTRL: 'Ctrl',
 ecodes.KEY_RIGHTCTRL: 'Ctrl_r',
 ecodes.KEY_LEFTALT: 'Alt_L',
 ecodes.KEY_RIGHTALT: 'Alt_r',
 ecodes.KEY_LEFTMETA: 'Windows',
 ecodes.KEY_RIGHTMETA: 'Menu',
 ecodes.KEY_ESC: 'Esc',
 ecodes.KEY_F1: 'F1', ecodes.KEY_F2: 'F2', ecodes.KEY_F3: 'F3',
 ecodes.KEY_F4: 'F4', ecodes.KEY_F5: 'F5', ecodes.KEY_F6: 'F6',
 ecodes.KEY_F7: 'F7', ecodes.KEY_F8: 'F8', ecodes.KEY_F9: 'F9',
 ecodes.KEY_F10: 'F10', ecodes.KEY_F11: 'F11', ecodes.KEY_F12: 'F12',
 ecodes.KEY_INSERT: 'Insert', ecodes.KEY_DELETE: 'Delete',
 ecodes.KEY_HOME: 'Home', ecodes.KEY_END: 'End',
 ecodes.KEY_PAGEUP: 'PgUp', ecodes.KEY_PAGEDOWN: 'PgDn',
 ecodes.KEY_UP: 'up', ecodes.KEY_DOWN: 'Down', ecodes.KEY_LEFT: 'Left', ecodes.KEY_RIGHT: 'Right',
 ecodes.KEY_KP0: '0\nIns', ecodes.KEY_KPDOT: '.',  # Изменено с ' . ' на '.'
 ecodes.KEY_KP1: '1\nEnd', ecodes.KEY_KP2: '2\n↓', ecodes.KEY_KP3: '3\nPgDn',
 ecodes.KEY_KP4: '4\n←', ecodes.KEY_KP5: '5\n', ecodes.KEY_KP6: '6\n→',
 ecodes.KEY_KP7: '7\nHome', ecodes.KEY_KP8: '8\n↑', ecodes.KEY_KP9: '9\nPgUp',
 ecodes.KEY_KPENTER: 'KEnter',
 ecodes.KEY_COMMA: '<', ecodes.KEY_DOT: '>', ecodes.KEY_SLASH: '?',
 ecodes.KEY_SEMICOLON: ':', ecodes.KEY_APOSTROPHE: '"',
 ecodes.KEY_LEFTBRACE: '{', ecodes.KEY_RIGHTBRACE: '}',
 ecodes.KEY_BACKSLASH: '|', ecodes.KEY_MINUS: '_', ecodes.KEY_EQUAL: '+',
 ecodes.KEY_GRAVE: '~',
}


class KeyboardListener(threading.Thread):
 def __init__(self, update_highlight_callback=None):
  super().__init__(daemon=True)
  self.running = True
  self.board = None
  self.update_highlight_callback = update_highlight_callback
  self.find_keyboard()

 def find_keyboard(self):
   """Поиск физической клавиатуры"""
   devices = [InputDevice(path) for path in list_devices()]
   # print(devices)
   for dev in devices:
    if "Keyboard\"" in str(dev) and ' phys ' in str(dev):
     self.board = dev  #
     # print(dev)
     print(f"Найдена клавиатура: {dev.name}")
     return
   print("Клавиатура не найдена!")

 def run(self):
  if self.board is None:
   self.find_keyboard()
   if self.board is None:
    print("Не удалось найти клавиатуру для прослушки")
    return

  while self.running:
   try:
    for event in self.board.read_loop():
     if not self.running:
      break

     if event.type == ecodes.EV_KEY:
      key_event = categorize(event)

      if key_event.keystate == 1:  # key_down
       key_name = str(key_event.keycode)

       # print(key_name)
       # Преобразуем в формат UI
       ui_key = None

       # Сначала проверяем special_key_map
       if key_name in simple_key_map:
        ui_key = simple_key_map[key_name]
       # Затем проверяем evdev_to_ui_key
       elif event.code in evdev_to_ui_key:
        ui_key = evdev_to_ui_key[event.code]
       else:
        # Пробуем убрать KEY_ префикс
        ui_key = key_name.replace("KEY_", "")
       if ui_key:
        # Получаем текущий скрипт
        current_app = settings.get_current_app()
        script = settings.get_script(ui_key)

        if script and script.strip():
         print(f"Выполняется скрипт для клавиши {ui_key}")
         print(script)
         threading.Thread(
          target=lambda s=script: subprocess.call(['bash', '-c', s]),
          daemon=True
         ).start()

         if self.update_highlight_callback:
          self.update_highlight_callback()

   except Exception as e:
    print(f"Ошибка прослушки: {e}")
    import time
    time.sleep(1)
    # Пробуем переподключиться
    try:
     self.find_keyboard()
    except:
     pass

 def stop(self):
  self.running = False


class KeyboardWidget(QWidget):
 def __init__(self, callback=None, show_profile_bar=True, insert_callback=None):
  super().__init__()
  self.callback = callback
  self.insert_callback = insert_callback
  self.show_profile_bar = show_profile_bar
  self.buttons = {}
  self.create_layout()

 def create_layout(self):
  layout = QVBoxLayout(self)
  layout.setContentsMargins(0, 0, 0, 0)
  layout.setSpacing(5)

  if self.show_profile_bar:
   layout.addWidget(self.create_profile_bar())

  kb = QWidget()
  kb.setMinimumSize(1340, 360)

  kb.setStyleSheet("""
            QPushButton { 
                background-color: lightgray; 
                border: 1px solid gray; 
                padding: 2px; 
                color: black; 
                font-size: 10px; 
            }
            QPushButton:hover { background-color: #CCCCFF; }
            QPushButton:pressed { background-color: blue; color: white; }
        """)

  BUTTON_WIDTH = 60
  BUTTON_HEIGHT = 40
  BASE_X_STEP = 70
  BASE_Y_STEP = 50
  X_OFFSET = 6
  Y_OFFSET = 6

  keyboard_layout = [
   ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'Insert', 'Delete', 'Home',
    'End', 'PgUp', 'PgDn'],
   ['~\n`', '!\n1', '@\n2', '#\n3', '$\n4', '%\n5', '^\n6', '&\n7', '*\n8', '(\n9', ')\n0',
    '_\n-', '+\n=', 'Backspace', 'Num Lock', '/', '*', '-'],
   ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{\n[', '}\n]', '|\n\\', ' 7\nHome', '8\n↑', '9\nPgUp',
    '+'],
   ['Caps Lock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':\n;', '"\n\'', '\nEnter\n', '4\n←', '5\n', '6\n→'],
   ['Shift_L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<\n,', '>\n.', '?\n/', 'Shift', '1\nEnd', '2\n↓', '3\nPgDn', 'KEnter'],
   ['Ctrl', 'Windows', 'Alt_L', 'space', 'Alt_r', 'Fn', 'Menu', 'Ctrl_r', 'up', '0\nIns', '.'],  # Изменено с ' . ' на '.'
   ['Left', 'Down', 'Right']
  ]

  numpad_shifts = {'first': 69, 'second': 140, 'third': 210}
  first_column_keys = [' 7\nHome', '8\n↑', '9\nPgUp', '+']
  second_column_keys = ['4\n←', '5\n', '6\n→']
  third_column_keys = ['1\nEnd', '2\n↓', '3\nPgDn', 'KEnter']

  for i, row in enumerate(keyboard_layout):
   for j, key_text in enumerate(row):
    x1 = BASE_X_STEP * j + X_OFFSET
    y1 = BASE_Y_STEP * i + Y_OFFSET
    w = BUTTON_WIDTH
    h = BUTTON_HEIGHT

    btn = QPushButton(key_text, kb)
    key_name = key_text.strip()

    if self.callback:
     btn.clicked.connect(lambda checked, k=key_name: self.callback(k))
    if self.insert_callback:
     btn.clicked.connect(lambda checked, k=key_name: self.insert_callback(k))

    self.buttons[key_name] = btn

    x_pos = x1
    y_pos = y1

    if key_text == 'Backspace':
     w = 120
    elif i == 1 and j > 13:
     x_pos = x1 + 69

    if i >= 2:
     if key_text in first_column_keys:
      x_pos += numpad_shifts['first']
      if key_text == "+":
       btn.setText(" + ")
     if key_text in second_column_keys:
      x_pos += numpad_shifts['second']
     if key_text in third_column_keys:
      x_pos += numpad_shifts['third']
      if key_text == "KEnter":
       h = BUTTON_HEIGHT * 2 + 5
       btn.setText(" Enter ")
       btn.resize(w, h)
       btn.move(x_pos, y_pos)
       continue

    if key_text == '\nEnter\n':
     w = 140
     h = BUTTON_HEIGHT * 2 + 5
     btn.resize(w, h)
     btn.move(x_pos, y_pos)
     continue

    if i == 5:
     if key_text == "space":
      w = 300
      x_pos = x1
     elif key_text in ['Alt_r', 'Fn', 'Menu', 'Ctrl_r']:
      x_pos = x1 + 210
     elif key_text == 'up':
      x_pos = x1 + 280
     elif key_text == "0\nIns":
      x_pos = x1 + 420
      w = 120
     elif key_text == '.':  # Изменено с ' . '
      x_pos = x1 + 490

    if i == 6:
     if key_text in ['Left', 'Down', 'Right']:
      x_pos = x1 + 770
      y_pos = y1 - 9

    btn.resize(w, h)
    btn.move(x_pos, y_pos)

    btn.setStyleSheet("""
                    QPushButton { 
                        background-color: lightgray; 
                        border: 1px solid gray; 
                        padding: 2px; 
                        color: black; 
                        font-size: 10px; 
                    }
                    QPushButton:hover { background-color: #CCCCFF; }
                    QPushButton:pressed { background-color: blue; color: white; }
                """)

  layout.addWidget(kb)

 def create_profile_bar(self):
  bar = QWidget()
  h = QHBoxLayout(bar)
  h.setContentsMargins(10, 5, 10, 5)

  self.app_combo = QComboBox()
  self.app_combo.setFixedWidth(300)
  self.app_combo.setStyleSheet("background-color: white; color: black;")
  self.app_combo.addItem("global")
  self.app_combo.setCurrentText(settings.get_current_app())
  self.app_combo.currentTextChanged.connect(self.change_app)
  h.addWidget(self.app_combo)
  h.addStretch()
  return bar

 def change_app(self, app):
  settings.data["current_app"] = app
  self.refresh_highlights()

 def update_highlight(self, btn, key):
  has = bool(settings.get_script(key))
  if has:
   btn.setStyleSheet("""
                QPushButton { 
                    background-color: #4169E1; 
                    color: white; 
                    font-weight: bold;
                    border: 1px solid gray; 
                    padding: 2px; 
                    font-size: 10px; 
                }
                QPushButton:hover { background-color: #3559B5; }
                QPushButton:pressed { background-color: blue; color: white; }
            """)
  else:
   btn.setStyleSheet("""
                QPushButton { 
                    background-color: lightgray; 
                    border: 1px solid gray; 
                    padding: 2px; 
                    color: black; 
                    font-size: 10px; 
                }
                QPushButton:hover { background-color: #CCCCFF; }
                QPushButton:pressed { background-color: blue; color: white; }
            """)

 def refresh_highlights(self):
  for key, btn in self.buttons.items():
   self.update_highlight(btn, key)


class EditorWindow(QMainWindow):
 def __init__(self, key, main_kbd):
  super().__init__()
  self.key = key
  self.main_kbd = main_kbd
  self.setWindowTitle(f"Запись макроса для клавиши {key}")
  self.setGeometry(100, 100, 1760, 770)

  central = QWidget()
  self.setCentralWidget(central)
  vbox = QVBoxLayout(central)
  vbox.setContentsMargins(20, 20, 20, 20)

  vbox.addWidget(QLabel("Редактор скрипта:"))
  self.editor = QTextEdit()
  self.editor.setStyleSheet("background-color: white; color: black; font-family: Courier; font-size: 12pt;")
  script = settings.get_script(key)
  if not script.strip():
   script = "#!/bin/bash\n\n"
  self.editor.setPlainText(script)

  cursor = self.editor.textCursor()
  cursor.movePosition(QTextCursor.MoveOperation.Start)
  cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, 2)
  cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
  self.editor.setTextCursor(cursor)

  vbox.addWidget(self.editor)

  self.kbd = KeyboardWidget(insert_callback=self.insert_xte_command, show_profile_bar=False)
  vbox.addWidget(self.kbd)

  self.main_kbd.refresh_highlights()

 keypad_map = {
  "7\nHome": "KP_Home", "8\n↑": "KP_Up", "9\nPgUp": "KP_Prior",
  "4\n←": "KP_Left", "5\n": "KP_Begin", "6\n→": "KP_Right",
  "1\nEnd": "KP_End", "2\n↓": "KP_Down", "3\nPgDn": "KP_Next",
  "0\nIns": "KP_Insert", ".": "Delete",  # Для точки на numpad используем KP_Delete
  "KEnter": "KP_Enter"
 }

 mouse_map = {
  "Левая": ("mousedown 1", "mouseup 1"),
  "Правая": ("mousedown 3", "mouseup 3"),
  "wheel_up": ("mousedown 4", "mouseup 4"),
  "mouse_middie": ("mousedown 2", "mouseup 2"),
  "wheel_down": ("mousedown 5", "mouseup 5")
 }

 def insert_xte_command(self, key):
  if key is None:
   return

  k = key.strip()

  # Специальная обработка для точки на numpad
  if k == '.':
   sc = 'xte "keydown Delete"\nsleep 0.23\nxte "keyup Delete"\n'
  elif k in self.keypad_map:
   key_for_xte = self.keypad_map[k]
   sc = f'xte "keydown {key_for_xte}"\nsleep 0.23\nxte "keyup {key_for_xte}"\n'
  elif k in self.mouse_map:
   down, up = self.mouse_map[k]
   sc = f'xte "{down}"\nsleep 0.23\nxte "{up}"\n'
  else:
   # Экранируем кавычки
   key_for_xte = k.replace('"', '\\"')
   sc = f'xte "keydown {key_for_xte}"\nsleep 0.23\nxte "keyup {key_for_xte}"\n'

  self.editor.insertPlainText(sc)

 def save(self):
  script = self.editor.toPlainText()
  settings.set_script(self.key, script)
  self.main_kbd.refresh_highlights()

 def closeEvent(self, event):
  self.save()
  event.accept()


class MainWindow(QMainWindow):
 def __init__(self):
  super().__init__()
  self.editor = None
  self.listener = None

  self.setWindowTitle("Клавиатура макросов")
  self.setGeometry(100, 100, 1320, 660)

  central = QWidget()
  self.setCentralWidget(central)
  layout = QVBoxLayout(central)

  self.kbd = KeyboardWidget(self.open_editor, show_profile_bar=True)
  layout.addWidget(self.kbd)

  self.setup_keyboard_listener()
  self.setup_ui()

  self.kbd.refresh_highlights()

 def setup_keyboard_listener(self):
  self.listener = KeyboardListener(update_highlight_callback=self.update_highlights)
  self.listener.start()
  print("Прослушка клавиатуры запущена")

 def update_highlights(self):
  QTimer.singleShot(0, self.kbd.refresh_highlights)

 def setup_ui(self):
  pass

 def open_editor(self, key):
  if self.editor:
   self.editor.close()
  self.editor = EditorWindow(key, self.kbd)
  self.editor.show()

 def closeEvent(self, event):
  """Обработка закрытия окна с проверкой изменений"""
  if settings.has_changes():
   reply = QMessageBox.question(
    self,
    'Сохранение настроек',
    'Сохранить новые настройки?',
    QMessageBox.StandardButton.Yes |
    QMessageBox.StandardButton.No |
    QMessageBox.StandardButton.Cancel
   )

   if reply == QMessageBox.StandardButton.Yes:
    settings.save()
    event.accept()
   elif reply == QMessageBox.StandardButton.No:
    event.accept()
   else:
    event.ignore()
    return

  if self.listener:
   self.listener.stop()

  if self.editor:
   self.editor.close()

  event.accept()


if __name__ == "__main__":
 app = QApplication(sys.argv)
 app.setStyle("Windows")

 palette = QPalette()
 palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
 palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
 palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
 palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
 app.setPalette(palette)

 win = MainWindow()
 win.show()
 sys.exit(app.exec())
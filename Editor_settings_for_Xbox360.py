import sys
import os
import re
import json
import tomllib
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QFileDialog
from PyQt6.QtGui import QKeySequence, QPalette, QColor, QAction
from PyQt6.QtCore import Qt
# Импорт UI из отдельного файла
from Ui_Editor_settings_for_Xbox360 import MainWindow, VirtualKeyboard, ZONE_DEFINITIONS

IMAGE_PATH = os.path.join(os.getcwd(), "gamepad xbox 360.png")


class XeniaConfigManager:
 # Логика работы с конфигами Xenia

 def __init__(self, config_dir: str):
  self.config_dir = Path(config_dir)
  self.profiles = {}  # будет хранить словари: { "keys": {...}, "keyboard_mode": int, "keyboard_user_index": int }
  self.key_map = {
   "A": "keybind_a", "B": "keybind_b", "X": "keybind_x", "Y": "keybind_y",
   "LEFT_SHOULDER": "keybind_left_shoulder", "RIGHT_SHOULDER": "keybind_right_shoulder",
   "LEFT_TRIGGER": "keybind_left_trigger", "RIGHT_TRIGGER": "keybind_right_trigger",
   "GUIDE": "keybind_guide", "BACK": "keybind_back", "START": "keybind_start",
   "DPAD_UP": "keybind_dpad_up", "DPAD_DOWN": "keybind_dpad_down",
   "DPAD_LEFT": "keybind_dpad_left", "DPAD_RIGHT": "keybind_dpad_right",
   "LEFT_THUMB_UP": "keybind_left_thumb_up", "LEFT_THUMB_DOWN": "keybind_left_thumb_down",
   "LEFT_THUMB_LEFT": "keybind_left_thumb_left", "LEFT_THUMB_RIGHT": "keybind_left_thumb_right",
   "RIGHT_THUMB_UP": "keybind_right_thumb_up", "RIGHT_THUMB_DOWN": "keybind_right_thumb_down",
   "RIGHT_THUMB_LEFT": "keybind_right_thumb_left", "RIGHT_THUMB_RIGHT": "keybind_right_thumb_right",
   "LEFT_THUMB_PRESSED": "keybind_left_thumb", "RIGHT_THUMB_PRESSED": "keybind_right_thumb"
  }
  self.display_name_map = {
   "SPACE": "SPACE", "ENTER": "ENTER", "BACKSPACE": "BACK", "TAB": "TAB", "ESCAPE": "ESC",
   "UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT", "INSERT": "INS", "DELETE": "DEL",
   "HOME": "HOME", "END": "END", "PAGEUP": "PGUP", "PAGEDOWN": "PGDN", "CAPSLOCK": "CAPS",
   "NUMLOCK": "NUM", "LEFTCTRL": "CTRL", "RIGHTCTRL": "RCTRL", "LEFTALT": "ALT", "RIGHTALT": "RALT",
   "LEFTSHIFT": "SHIFT", "RIGHTSHIFT": "RSHIFT", "LEFTMETA": "WIN", "MENU": "MENU",
   "NUMPAD0": "NUM0", "NUMPAD1": "NUM1", "NUMPAD2": "NUM2", "NUMPAD3": "NUM3", "NUMPAD4": "NUM4",
   "NUMPAD5": "NUM5", "NUMPAD6": "NUM6", "NUMPAD7": "NUM7", "NUMPAD8": "NUM8", "NUMPAD9": "NUM9",
   "NUMPADPLUS": "NUM+", "NUMPADMINUS": "NUM-", "NUMPADMULTIPLY": "NUM*", "NUMPADDIVIDE": "NUM/",
   "NUMPADENTER": "NUMENT", "NUMPADDECIMAL": "NUM."
  }
  self.key_to_xenia = {
   "A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F", "G": "G", "H": "H", "I": "I", "J": "J",
   "K": "K", "L": "L", "M": "M", "N": "N", "O": "O", "P": "P", "Q": "Q", "R": "R", "S": "S", "T": "T",
   "U": "U", "V": "V", "W": "W", "X": "X", "Y": "Y", "Z": "Z", "0": "0", "1": "1", "2": "2", "3": "3",
   "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9", "ESCAPE": "0x1B", "F1": "0x70", "F2": "0x71",
   "F3": "0x72", "F4": "0x73", "F5": "0x74", "F6": "0x75", "F7": "0x76", "F8": "0x77", "F9": "0x78",
   "F10": "0x79", "F11": "0x7A", "F12": "0x7B", "INSERT": "0x2D", "DELETE": "0x2E", "HOME": "0x24",
   "END": "0x23", "PAGEUP": "0x21", "PAGEDOWN": "0x22", "UP": "0x26", "DOWN": "0x28", "LEFT": "0x25",
   "RIGHT": "0x27", "SPACE": "0x20", "BACKSPACE": "0x08", "TAB": "0x09", "ENTER": "0x0D",
   "CAPSLOCK": "0x14", "NUMLOCK": "0x90", "LEFTSHIFT": "0xA0", "RIGHTSHIFT": "0xA1",
   "LEFTCTRL": "0xA2", "RIGHTCTRL": "0xA3", "LEFTALT": "0xA4", "RIGHTALT": "0xA5",
   "LEFTMETA": "0x5B", "MENU": "0x5D", "NUMPAD0": "0x60", "NUMPAD1": "0x61", "NUMPAD2": "0x62",
   "NUMPAD3": "0x63", "NUMPAD4": "0x64", "NUMPAD5": "0x65", "NUMPAD6": "0x66", "NUMPAD7": "0x67",
   "NUMPAD8": "0x68", "NUMPAD9": "0x69", "NUMPADPLUS": "0x6B", "NUMPADMINUS": "0x6D",
   "NUMPADMULTIPLY": "0x6A", "NUMPADDIVIDE": "0x6F", "NUMPADENTER": "0x6C", "NUMPADDECIMAL": "0x6E"
  }
  # Обратный словарь для преобразования Xenia → ключ
  self.xenia_to_key = {}
  for k, v in self.key_to_xenia.items():
   self.xenia_to_key[v.upper()] = k
   self.xenia_to_key[v.lower()] = k
  self.keybind_comments = {v: f"Список клавиш для привязки к {k}, разделённых пробелами" for k, v in self.key_map.items()}

 def _xenia_token_to_display(self, t):
  """Преобразует один токен Xenia в читаемый вид"""
  t = t.strip()
  if not t:
   return ""
  if t.startswith('^') and len(t) > 1:
   return f"Ctrl+{self._xenia_token_to_display(t[1:])}"
  if t.startswith('_') and len(t) > 1:
   return f"Shift+{self._xenia_token_to_display(t[1:])}"
  if t.startswith(('0x', '0X')):
   up = t.upper()
   if up in self.xenia_to_key:
    return self.display_name_map.get(self.xenia_to_key[up], self.xenia_to_key[up])
   return t
  if len(t) == 1:
   return t.upper()
  if t.upper() in self.xenia_to_key:
   kn = self.xenia_to_key[t.upper()]
   return self.display_name_map.get(kn, kn)
  return t

 def _xenia_value_to_display(self, v):
  """Преобразует значение привязки из TOML в отображаемую строку"""
  return " ".join(self._xenia_token_to_display(t) for t in v.strip().split())

 def _single_key_to_xenia(self, d):
  """Преобразует одну клавишу в её Xenia-представление"""
  if len(d) == 1:
   return d.upper()
  for i, dp in self.display_name_map.items():
   if dp == d:
    return self.key_to_xenia.get(i, d)
  return self.key_to_xenia.get(d, d)

 def _display_token_to_xenia(self, t):
  """Преобразует один токен отображаемой строки в Xenia-токен"""
  if t.startswith("Ctrl+") and len(t) > 5:
   return f"^{self._single_key_to_xenia(t[5:])}"
  if t.startswith("Shift+") and len(t) > 6:
   return f"_{self._single_key_to_xenia(t[6:])}"
  return self._single_key_to_xenia(t)

 def _display_to_xenia_value(self, d):
  """Преобразует отображаемую строку (например 'Ctrl+W') в формат Xenia"""
  return " ".join(self._display_token_to_xenia(t) for t in d.strip().split())

 def _default_mapping(self):
  """Возвращает словарь привязок по умолчанию (только клавиши)"""
  return {
   "A": "A", "B": "B", "X": "X", "Y": "Y",
   "LEFT_SHOULDER": "Q", "RIGHT_SHOULDER": "E",
   "LEFT_TRIGGER": "Q I", "RIGHT_TRIGGER": "E O",
   "GUIDE": "ESC", "BACK": "BACK", "START": "SPACE",
   "DPAD_UP": "Ctrl+W", "DPAD_DOWN": "Ctrl+S", "DPAD_LEFT": "Ctrl+A", "DPAD_RIGHT": "Ctrl+D",
   "LEFT_THUMB_UP": "Shift+W", "LEFT_THUMB_DOWN": "Shift+S", "LEFT_THUMB_LEFT": "Shift+A", "LEFT_THUMB_RIGHT": "Shift+D",
   "RIGHT_THUMB_UP": "UP", "RIGHT_THUMB_DOWN": "DOWN", "RIGHT_THUMB_LEFT": "LEFT", "RIGHT_THUMB_RIGHT": "RIGHT",
   "LEFT_THUMB_PRESSED": "F", "RIGHT_THUMB_PRESSED": "K"
  }

 def _read_profile(self, name):
  """Читает профиль из файла, возвращает словарь с ключами 'keys', 'keyboard_mode', 'keyboard_user_index'"""
  fp = self.config_dir / f"{name}.config.toml"
  if not fp.exists():
   return None
  with open(fp, "rb") as f:
   data = tomllib.load(f)
  # Читаем маппинг клавиш из секции [HID.WinKey]
  hid_winkey = data.get("HID", {}).get("WinKey", {})
  mapping = {}
  for logical, config_key in self.key_map.items():
   if config_key in hid_winkey:
    raw = hid_winkey[config_key].strip('"') if isinstance(hid_winkey[config_key], str) else str(hid_winkey[config_key])
    mapping[logical] = self._xenia_value_to_display(raw)
   else:
    mapping[logical] = ""
  # Читаем параметры клавиатуры из секции [HID]
  hid_section = data.get("HID", {})
  keyboard_mode = hid_section.get("keyboard_mode", 1)
  keyboard_user_index = hid_section.get("keyboard_user_index", 0)
  return {
   "keys": mapping,
   "keyboard_mode": keyboard_mode,
   "keyboard_user_index": keyboard_user_index
  }

 def _update_hid_section(self, existing_hid_content, keyboard_mode, keyboard_user_index):
  """Обновляет содержимое секции [HID] (без заголовка) параметрами клавиатуры"""
  lines = existing_hid_content.splitlines()
  new_lines = []
  updated_mode = updated_index = False
  for line in lines:
   if line.strip().startswith("keyboard_mode"):
    new_lines.append(f"keyboard_mode = {keyboard_mode}")
    updated_mode = True
   elif line.strip().startswith("keyboard_user_index"):
    new_lines.append(f"keyboard_user_index = {keyboard_user_index}")
    updated_index = True
   else:
    new_lines.append(line)
  if not updated_mode:
   new_lines.append(f"keyboard_mode = {keyboard_mode}")
  if not updated_index:
   new_lines.append(f"keyboard_user_index = {keyboard_user_index}")
  return "\n" + "\n".join(new_lines)  # добавляем перевод строки после заголовка

 def _generate_hid_section(self, keyboard_mode, keyboard_user_index):
  """Создаёт новую секцию [HID] с минимальными параметрами"""
  return f"""[HID]
keyboard_mode = {keyboard_mode}
keyboard_user_index = {keyboard_user_index}
"""

 def _save_profile(self, name):
  """Сохраняет профиль в файл .config.toml, обновляя секции [HID] и [HID.WinKey]"""
  fp = self.config_dir / f"{name}.config.toml"
  profile_data = self.profiles.get(name)
  if not profile_data:
   profile_data = {"keys": self._default_mapping(), "keyboard_mode": 1, "keyboard_user_index": 0}
  mapping = profile_data["keys"]
  # Генерируем секцию [HID.WinKey]
  winkey_lines = ["[HID.WinKey]"]
  for logical, config_key in self.key_map.items():
   display_value = mapping.get(logical, "")
   if display_value:
    xenia_value = self._display_to_xenia_value(display_value)
    comment = self.keybind_comments.get(config_key, "")
    winkey_lines.append(f'{config_key} = "{xenia_value}"\t\t\t\t#{comment}')
  winkey_section = "\n".join(winkey_lines)
  # Обработка существующего файла
  if fp.exists():
   with open(fp, "r", encoding="utf-8") as f:
    content = f.read()
   # Обновляем секцию [HID]
   hid_pattern = r'(?sm)^\[HID\](.*?)(?=^\[|\Z)'
   hid_block = re.search(hid_pattern, content)
   if hid_block:
    hid_content = hid_block.group(1)
    new_hid_content = self._update_hid_section(hid_content, profile_data["keyboard_mode"], profile_data["keyboard_user_index"])
    new_content = re.sub(hid_pattern, f"[HID]{new_hid_content}", content)
   else:
    new_hid_content = self._generate_hid_section(profile_data["keyboard_mode"], profile_data["keyboard_user_index"])
    new_content = content.rstrip() + "\n\n" + new_hid_content
   # Обновляем секцию [HID.WinKey]
   winkey_pattern = r'(?sm)^\[HID\.WinKey\](.*?)(?=^\[|\Z)'
   if re.search(winkey_pattern, new_content):
    new_content = re.sub(winkey_pattern, winkey_section, new_content)
   else:
    new_content = new_content.rstrip() + "\n\n" + winkey_section
  else:
   # Новый файл – создаём обе секции
   hid_section = self._generate_hid_section(profile_data["keyboard_mode"], profile_data["keyboard_user_index"])
   new_content = hid_section + "\n\n" + winkey_section
  # Запись файла
  with open(fp, "w", encoding="utf-8") as f:
   f.write(new_content)

 def load_profiles(self):
  """Загружает все профили из папки config_dir"""
  self.profiles.clear()
  if not self.config_dir.exists():
   self.config_dir.mkdir(parents=True, exist_ok=True)
   return
  for f in self.config_dir.glob("*.config.toml"):
   profile_name = f.stem.replace(".config", "")
   profile_data = self._read_profile(profile_name)
   if profile_data is not None:
    self.profiles[profile_name] = profile_data
  if not self.profiles:
   self.new_profile("default")

 def new_profile(self, name):
  """Создаёт новый профиль с именем name и привязками по умолчанию"""
  if name in self.profiles:
   return False
  self.profiles[name] = {"keys": self._default_mapping(), "keyboard_mode": 1, "keyboard_user_index": 0}
  self._save_profile(name)
  return True

 def delete_profile(self, name):
  """Удаляет профиль (кроме 'default') и его файл"""
  if name in self.profiles and name != "default":
   fp = self.config_dir / f"{name}.config.toml"
   if fp.exists():
    fp.unlink()
   del self.profiles[name]
   return True
  return False

 def update_mapping(self, profile_name, logical_key, key_string):
  """Обновляет привязку для одной кнопки в указанном профиле"""
  if profile_name in self.profiles:
   # key_string уже в удобочитаемом виде (например, "Ctrl+W" или "A")
   self.profiles[profile_name]["keys"][logical_key] = key_string
   self._save_profile(profile_name)

 def set_default_mapping(self, profile_name):
  """Сбрасывает привязки профиля на значения по умолчанию, оставляя настройки HID без изменений"""
  if profile_name in self.profiles:
   self.profiles[profile_name]["keys"] = self._default_mapping()
   self._save_profile(profile_name)

 def update_hid_settings(self, profile_name, keyboard_mode, keyboard_user_index):
  """Обновляет параметры клавиатуры в профиле (режим и индекс)"""
  if profile_name in self.profiles:
   self.profiles[profile_name]["keyboard_mode"] = keyboard_mode
   self.profiles[profile_name]["keyboard_user_index"] = keyboard_user_index
   self._save_profile(profile_name)

 def get_hid_settings(self, profile_name):
  """Возвращает (keyboard_mode, keyboard_user_index) для профиля"""
  if profile_name in self.profiles:
   return (self.profiles[profile_name]["keyboard_mode"], self.profiles[profile_name]["keyboard_user_index"])
  return (1, 0)


class AppController:
 # Связывает UI (MainWindow) и логику (XeniaConfigManager)

 def __init__(self, window: MainWindow):
  self.window = window
  self.config_manager = None
  self.current_profile = "default"
  self._current_image_path = IMAGE_PATH
  self.settings_file = Path.cwd() / "editor_app_settings.json"

  # Подключаем сигналы UI
  self.window.gamepad.zone_clicked.connect(self._on_zone_clicked)
  self.window.profile_combo.currentTextChanged.connect(self._on_profile_select)
  self.window.btn_create.clicked.connect(self._new_profile)
  self.window.btn_delete.clicked.connect(self._delete_profile)
  self.window.btn_defaults.clicked.connect(self._set_defaults)
  self.window.btn_apply.clicked.connect(self._apply_config)
  self.window.btn_browse.clicked.connect(self._browse_config)
  self.window.btn_img.clicked.connect(self._browse_image)
  self.window.config_path_edit.editingFinished.connect(self._load_config)
  self.window.closing.connect(self._save_app_settings)
  self.window.gamepad.zones_changed.connect(self._on_zones_changed)

  # Горячая клавиша F3 для отладки
  sc = QAction(self.window)
  sc.setShortcut(QKeySequence("F3"))
  sc.triggered.connect(self._toggle_debug)
  self.window.addAction(sc)

  # Загружаем настройки приложения и конфиги
  self._load_app_settings()
  self._load_config()

  # Явно выключаем режим отладки и обновляем привязки
  self.window.debug_cb.setChecked(False)
  self._refresh_bindings()

 def _load_app_settings(self):
  """Загружает сохранённые пути и зоны из JSON"""
  if self.settings_file.exists():
   try:
    with open(self.settings_file, "r", encoding="utf-8") as f:
     data = json.load(f)
    if data.get("config_path"):
     self.window.config_path_edit.setText(data["config_path"])
    if data.get("image_path") and os.path.exists(data["image_path"]):
     self._current_image_path = data["image_path"]
    if data.get("zones"):
     self.window.gamepad.set_zones_data(data["zones"])
   except Exception:
    pass
  self.window.gamepad.set_image(self._current_image_path)

 def _save_app_settings(self):
  """Сохраняет текущие пути и зоны в JSON"""
  data = {
   "config_path": self.window.config_path_edit.text(),
   "image_path": self._current_image_path,
   "zones": self.window.gamepad.get_zones_data()
  }
  try:
   with open(self.settings_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
  except Exception:
   pass

 def _on_zones_changed(self):
  self._save_app_settings()

 def _load_config(self):
  """Загружает конфиг-менеджер из выбранной папки"""
  path = self.window.config_path_edit.text().strip()
  if not path:
   QMessageBox.warning(self.window, "Ошибка", "Укажите папку с конфигами Xenia")
   return
  self.config_manager = XeniaConfigManager(path)
  self.config_manager.load_profiles()
  self.current_profile = "default" if "default" in self.config_manager.profiles else next(iter(self.config_manager.profiles), "default")
  self._refresh_combo()
  self._refresh_bindings()

 def _refresh_combo(self):
  """Обновляет выпадающий список профилей"""
  self.window.profile_combo.blockSignals(True)
  self.window.profile_combo.clear()
  for p in self.config_manager.profiles:
   self.window.profile_combo.addItem(p)
  if self.current_profile in self.config_manager.profiles:
   self.window.profile_combo.setCurrentText(self.current_profile)
  self.window.profile_combo.blockSignals(False)

 def _refresh_bindings(self):
  """Обновляет отображение привязок на геймпаде"""
  if not self.config_manager:
   return
  profile_data = self.config_manager.profiles.get(self.current_profile, {})
  mapping = profile_data.get("keys", {})
  self.window.gamepad.update_all_bindings(mapping)
  # Всегда показываем легенду (привязки)
  if hasattr(self.window.gamepad, "legend_container") and self.window.gamepad.legend_container:
   self.window.gamepad.legend_container.setVisible(True)

 def _on_zone_clicked(self, logical_name):
  """Обработчик клика по зоне геймпада – открывает виртуальную клавиатуру для выбора клавиши"""
  if not self.config_manager:
   return
  def callback(key):
   self.config_manager.update_mapping(self.current_profile, logical_name, key)
   self._refresh_bindings()
  VirtualKeyboard(self.window, callback).exec()

 def _on_profile_select(self, text):
  """Выбор другого профиля из выпадающего списка"""
  if text and text != self.current_profile:
   self.current_profile = text
   self._refresh_bindings()

 def _new_profile(self):
  """Создание нового профиля"""
  n, ok = QInputDialog.getText(self.window, "Создать профиль", "Имя профиля:")
  if ok and n.strip():
   if self.config_manager.new_profile(n.strip()):
    self.current_profile = n.strip()
    self._refresh_combo()
    self.window.profile_combo.setCurrentText(n.strip())
    self._refresh_bindings()
   else:
    QMessageBox.warning(self.window, "Ошибка", "Профиль уже существует")

 def _delete_profile(self):
  """Удаление текущего профиля (кроме default)"""
  if self.current_profile == "default":
   QMessageBox.warning(self.window, "Ошибка", "Нельзя удалить 'default'")
   return
  if QMessageBox.question(self.window, "Подтверждение", f"Удалить '{self.current_profile}'?") == QMessageBox.StandardButton.Yes:
   self.config_manager.delete_profile(self.current_profile)
   self._refresh_combo()
   self.current_profile = self.window.profile_combo.currentText()
   self._refresh_bindings()

 def _set_defaults(self):
  """Сброс привязок текущего профиля на значения по умолчанию"""
  if not self.config_manager:
   return
  if QMessageBox.question(self.window, "Подтверждение", f"Сбросить привязки в '{self.current_profile}'?") == QMessageBox.StandardButton.Yes:
   self.config_manager.set_default_mapping(self.current_profile)
   self._refresh_bindings()

 def _apply_config(self):
  """Принудительное сохранение текущего профиля в файл"""
  if not self.config_manager:
   QMessageBox.warning(self.window, "Ошибка", "Укажите папку с конфигами")
   return
  self.config_manager._save_profile(self.current_profile)
  QMessageBox.information(self.window, "Готово", "Настройки сохранены в .config.toml\nФормат: VK-коды, ^ = Ctrl, _ = Shift")

 def _browse_config(self):
  """Выбор папки с конфигами Xenia через диалог"""
  p = QFileDialog.getExistingDirectory(self.window, "Папка конфигов Xenia")
  if p:
   self.window.config_path_edit.setText(p)
   self._load_config()

 def _browse_image(self):
  """Выбор изображения для геймпада"""
  p, _ = QFileDialog.getOpenFileName(self.window, "Изображение геймпада", "", "Изображения (*.png *.jpg *.bmp *.webp)")
  if p:
   self._current_image_path = p
   self.window.gamepad.set_image(p)
   self._refresh_bindings()

 def _toggle_debug(self):
  """Включение/выключение режима отладки по F3"""
  self.window.debug_cb.setChecked(not self.window.debug_cb.isChecked())


if __name__ == "__main__":
 app = QApplication(sys.argv)
 app.setStyle("Fusion")

 # Тёмная палитра
 palette = QPalette()
 palette.setColor(QPalette.ColorRole.Window, QColor("#0f1023"))
 palette.setColor(QPalette.ColorRole.WindowText, QColor("white"))
 palette.setColor(QPalette.ColorRole.Base, QColor("#0d0e1a"))
 palette.setColor(QPalette.ColorRole.Text, QColor("white"))
 palette.setColor(QPalette.ColorRole.Button, QColor("#1c1e3d"))
 palette.setColor(QPalette.ColorRole.ButtonText, QColor("white"))
 palette.setColor(QPalette.ColorRole.Highlight, QColor("#2d5cf7"))
 app.setPalette(palette)

 window = MainWindow()
 controller = AppController(window)
 window.show()
 sys.exit(app.exec())
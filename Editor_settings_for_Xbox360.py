import sys, os, re, json, tomllib
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QFileDialog
from PyQt6.QtGui import QKeySequence, QPalette, QColor, QAction
from PyQt6.QtCore import Qt
# Импортируем UI из первого файла
from Ui_Editor_settings_for_Xbox360 import MainWindow, VirtualKeyboard, ZONE_DEFINITIONS

IMAGE_PATH = (
 "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/"
 "linux must have/python_linux/Project/gamepad xbox 360.png"
)


class XeniaConfigManager:
 """Логика работы с конфигами Xenia"""
 
 def __init__(self, config_dir: str):
  self.config_dir = Path(config_dir)
  self.profiles = {}
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
  # Обратная карта
  self.xenia_to_key = {}
  for k, v in self.key_to_xenia.items():
   self.xenia_to_key[v.upper()] = k
   self.xenia_to_key[v.lower()] = k
  self.keybind_comments = {v: f"List of keys to bind to {k}, separated by spaces" for k, v in self.key_map.items()}
 
 def _xenia_token_to_display(self, t):
  t = t.strip()
  if not t: return ""
  if t.startswith('^') and len(t) > 1: return f"Ctrl+{self._xenia_token_to_display(t[1:])}"
  if t.startswith('_') and len(t) > 1: return f"Shift+{self._xenia_token_to_display(t[1:])}"
  if t.startswith(('0x', '0X')):
   up = t.upper()
   if up in self.xenia_to_key: return self.display_name_map.get(self.xenia_to_key[up], self.xenia_to_key[up])
   return t
  if len(t) == 1: return t.upper()
  if t.upper() in self.xenia_to_key: kn = self.xenia_to_key[t.upper()]; return self.display_name_map.get(kn, kn)
  return t
 
 def _xenia_value_to_display(self, v):
  return " ".join(self._xenia_token_to_display(t) for t in v.strip().split())
 
 def _single_key_to_xenia(self, d):
  if len(d) == 1: return d.upper()
  for i, dp in self.display_name_map.items():
   if dp == d: return self.key_to_xenia.get(i, d)
  return self.key_to_xenia.get(d, d)
 
 def _display_token_to_xenia(self, t):
  if t.startswith("Ctrl+") and len(t) > 5: return f"^{self._single_key_to_xenia(t[5:])}"
  if t.startswith("Shift+") and len(t) > 6: return f"_{self._single_key_to_xenia(t[6:])}"
  return self._single_key_to_xenia(t)
 
 def _display_to_xenia_value(self, d):
  return " ".join(self._display_token_to_xenia(t) for t in d.strip().split())
 
 def _default_mapping(self):
  return {"A": "A", "B": "B", "X": "X", "Y": "Y", "LEFT_SHOULDER": "Q", "RIGHT_SHOULDER": "E",
          "LEFT_TRIGGER": "Q I", "RIGHT_TRIGGER": "E O", "GUIDE": "ESC", "BACK": "BACK", "START": "SPACE",
          "DPAD_UP": "Ctrl+W", "DPAD_DOWN": "Ctrl+S", "DPAD_LEFT": "Ctrl+A", "DPAD_RIGHT": "Ctrl+D",
          "LEFT_THUMB_UP": "Shift+W", "LEFT_THUMB_DOWN": "Shift+S", "LEFT_THUMB_LEFT": "Shift+A", "LEFT_THUMB_RIGHT": "Shift+D",
          "RIGHT_THUMB_UP": "UP", "RIGHT_THUMB_DOWN": "DOWN", "RIGHT_THUMB_LEFT": "LEFT", "RIGHT_THUMB_RIGHT": "RIGHT",
          "LEFT_THUMB_PRESSED": "F", "RIGHT_THUMB_PRESSED": "K"}
 
 def load_profiles(self):
  self.profiles.clear()
  if not self.config_dir.exists(): self.config_dir.mkdir(parents=True, exist_ok=True); return
  for f in self.config_dir.glob("*.config.toml"): self.profiles[f.stem.replace(".config", "")] = self._read_mapping(f)
  if not self.profiles: self.new_profile("default")
 
 def _read_mapping(self, fp):
  m = {}
  try:
   with open(fp, "rb") as f:
    data = tomllib.load(f)
   hid = data.get("HID", {}).get("WinKey", {})
   for l, ck in self.key_map.items():
    if ck in hid:
     v = hid[ck]
     raw = v.strip('"') if isinstance(v, str) else str(v)
     m[l] = self._xenia_value_to_display(raw)
  except:
   pass
  
  # ИСПРАВЛЕНИЕ БАГА: Если ключа в файле нет, оставляем пустую строку, а не дефолт!
  # Дефолт применяется только при создании профиля или сбросе.
  for k in self.key_map:
   m.setdefault(k, "")
  return m
 
 def _gen_winkey_section(self, m):
  lines = ["[HID.WinKey]"]
  for l, ck in self.key_map.items():
   d = m.get(l, "")
   # Сохраняем только назначенные клавиши
   if d: xv = self._display_to_xenia_value(d); c = self.keybind_comments.get(ck, ""); lines.append(f'{ck} = "{xv}"\t\t\t\t#{c}')
  return "\n".join(lines)
 
 def _save_profile(self, name):
  fp = self.config_dir / f"{name}.config.toml"
  m = self.profiles.get(name, self._default_mapping())
  sec = self._gen_winkey_section(m)
  if fp.exists():
   with open(fp, "r", encoding="utf-8") as f:
    c = f.read()
   pat = r'(\[HID\.WinKey\].*?)(?=\n\[|\Z)'
   c = re.sub(pat, sec, c, flags=re.DOTALL) if re.search(pat, c, re.DOTALL) else c.rstrip() + "\n\n" + sec
  else:
   c = sec
  with open(fp, "w", encoding="utf-8") as f:
   f.write(c)
 
 def new_profile(self, n):
  if n in self.profiles: return False
  self.profiles[n] = self._default_mapping()  # При создании заполняем дефолтом
  self._save_profile(n)
  return True
 
 def delete_profile(self, n):
  if n in self.profiles and n != "default":
   fp = self.config_dir / f"{n}.config.toml"
   if fp.exists(): fp.unlink()
   del self.profiles[n]
   return True
  return False
 
 def update_mapping(self, p, l, ks):
  if p in self.profiles:
   d = self.display_name_map.get(ks, ks)
   self.profiles[p][l] = d if len(ks) != 1 else ks.upper()
   self._save_profile(p)
 
 def set_default_mapping(self, p):
  if p in self.profiles: self.profiles[p] = self._default_mapping(); self._save_profile(p)


class AppController:
 """Связывает UI (MainWindow) и Логику (XeniaConfigManager)"""
 
 def __init__(self, window: MainWindow):
  self.window = window
  self.config_manager = None
  self.current_profile = "default"
  self._current_image_path = IMAGE_PATH
  self.settings_file = Path.cwd() / "editor_app_settings.json"  # Файл настроек в папке запуска
  
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
  self.window.closing.connect(self._save_app_settings)  # Сохранение при закрытии
  
  # Горячая клавиша F3
  sc = QAction(self.window)
  sc.setShortcut(QKeySequence("F3"))
  sc.triggered.connect(self._toggle_debug)
  self.window.addAction(sc)
  
  # Загрузка настроек и конфига
  self._load_app_settings()
  self._load_config()
 
 def _load_app_settings(self):
  """Загрузка путей из JSON при старте"""
  if self.settings_file.exists():
   try:
    with open(self.settings_file, "r", encoding="utf-8") as f:
     data = json.load(f)
    if data.get("config_path"):
     self.window.config_path_edit.setText(data["config_path"])
    if data.get("image_path") and os.path.exists(data["image_path"]):
     self._current_image_path = data["image_path"]
   except:
    pass
  self.window.gamepad.set_image(self._current_image_path)
 
 def _save_app_settings(self):
  """Сохранение путей в JSON при закрытии"""
  data = {
   "config_path": self.window.config_path_edit.text(),
   "image_path": self._current_image_path,
   "zones": ZONE_DEFINITIONS  # Сохраняем расположение кнопок
  }
  try:
   with open(self.settings_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
  except:
   pass
 
 def _load_config(self):
  path = self.window.config_path_edit.text().strip()
  if not path:
   d = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/xbox 360/Emulators/Xenia Canary/config"
   path = d if os.path.exists(d) else os.path.expanduser("~/.xenia/config")
   self.window.config_path_edit.setText(path)
  self.config_manager = XeniaConfigManager(path)
  self.config_manager.load_profiles()
  self.current_profile = "default" if "default" in self.config_manager.profiles else next(iter(self.config_manager.profiles), "default")
  self._refresh_combo()
  self._refresh_bindings()
 
 def _refresh_combo(self):
  self.window.profile_combo.blockSignals(True)
  self.window.profile_combo.clear()
  for p in self.config_manager.profiles: self.window.profile_combo.addItem(p)
  if self.current_profile in self.config_manager.profiles: self.window.profile_combo.setCurrentText(self.current_profile)
  self.window.profile_combo.blockSignals(False)
 
 def _refresh_bindings(self):
  if not self.config_manager: return
  # Получаем словарь назначений для текущего профиля (с пустыми значениями, если нет назначений)
  mapping = self.config_manager.profiles.get(self.current_profile, {})
  self.window.gamepad.update_all_bindings(mapping)
 
 def _on_zone_clicked(self, logical_name):
  if not self.config_manager: return
  
  def callback(key):
   self.config_manager.update_mapping(self.current_profile, logical_name, key)
   self._refresh_bindings()  # Обновляем виджет
  
  VirtualKeyboard(self.window, callback).exec()
 
 def _on_profile_select(self, text):
  if text and text != self.current_profile:
   self.current_profile = text
   self._refresh_bindings()  # Теперь корректно отобразит пустые кнопки
 
 def _new_profile(self):
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
  if self.current_profile == "default": QMessageBox.warning(self.window, "Ошибка", "Нельзя удалить 'default'"); return
  if QMessageBox.question(self.window, "Подтверждение", f"Удалить '{self.current_profile}'?") == QMessageBox.StandardButton.Yes:
   self.config_manager.delete_profile(self.current_profile)
   self._refresh_combo()
   self.current_profile = self.window.profile_combo.currentText()
   self._refresh_bindings()
 
 def _set_defaults(self):
  if not self.config_manager: return
  if QMessageBox.question(self.window, "Подтверждение", f"Сбросить '{self.current_profile}'?") == QMessageBox.StandardButton.Yes:
   self.config_manager.set_default_mapping(self.current_profile)
   self._refresh_bindings()
 
 def _apply_config(self):
  if not self.config_manager: QMessageBox.warning(self.window, "Ошибка", "Укажите папку"); return
  self.config_manager._save_profile(self.current_profile)
  QMessageBox.information(self.window, "Готово", "Настройки сохранены в .config.toml\nФормат: VK-коды, ^ = Ctrl, _ = Shift")
 
 def _browse_config(self):
  p = QFileDialog.getExistingDirectory(self.window, "Папка конфигов Xenia")
  if p: self.window.config_path_edit.setText(p); self._load_config()
 
 def _browse_image(self):
  p, _ = QFileDialog.getOpenFileName(self.window, "Изображение геймпада", "", "Изображения (*.png *.jpg *.bmp *.webp)")
  if p:
   self._current_image_path = p
   self.window.gamepad.set_image(p)
   self._refresh_bindings()
 
 def _toggle_debug(self):
  self.window.debug_cb.setChecked(not self.window.debug_cb.isChecked())


if __name__ == "__main__":
 app = QApplication(sys.argv)
 app.setStyle("Fusion")
 
 # Темная палитра
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
 controller = AppController(window)  # Связываем логику с UI
 window.show()
 sys.exit(app.exec())

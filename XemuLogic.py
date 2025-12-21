import os, json, string

class XemuConfigManager:
 PROFILES_FILE = "xemu_profiles.json"

 def __init__(self):
  self.profiles = {"Default": {"mapping": {}}, "last_profile": "Default"}

  # === Старый словарь (оставлен для совместимости, но больше не основной) ===
  self.scancodes = {
   # === Буквы ===
   "A": 4, "B": 5, "C": 6, "D": 7, "E": 8, "F": 9, "G": 10, "H": 11,
   "I": 12, "J": 13, "K": 14, "L": 15, "M": 16, "N": 17, "O": 18, "P": 19,
   "Q": 20, "R": 21, "S": 22, "T": 23, "U": 24, "V": 25, "W": 26, "X": 27,
   "Y": 28, "Z": 29,

   # === Цифры ===
   "1": 30, "2": 31, "3": 32, "4": 33, "5": 34, "6": 35, "7": 36, "8": 37,
   "9": 38, "0": 39,

   # === Основные клавиши ===
   "ENTER": 40, "ESC": 41, "BACKSPACE": 42, "TAB": 43, "SPACE": 44,

   # === Символы ===
   "MINUS": 45, "EQUAL": 46, "LEFTBRACE": 47, "RIGHTBRACE": 48,
   "BACKSLASH": 49, "SEMICOLON": 51, "APOSTROPHE": 52, "GRAVE": 53,
   "COMMA": 54, "DOT": 55, "SLASH": 56,

   # === Функциональные ===
   "CAPSLOCK": 57, "F1": 58, "F2": 59, "F3": 60, "F4": 61, "F5": 62,
   "F6": 63, "F7": 64, "F8": 65, "F9": 66, "F10": 67, "F11": 68, "F12": 69,
   "PRINTSCREEN": 70, "SCROLLLOCK": 71, "PAUSE": 72,

   # === Навигация ===
   "INSERT": 73, "HOME": 74, "PAGEUP": 75, "DELETE": 76, "END": 77, "PAGEDOWN": 78,

   # === Стрелки ===
   "RIGHT": 79, "LEFT": 80, "DOWN": 81, "UP": 82,

   # === NumPad ===
   "NUMLOCK": 83, "KPSLASH": 84, "KPASTERISK": 85, "KPMINUS": 86,
   "KPPLUS": 87, "KPENTER": 88,
   "KP1": 89, "KP2": 90, "KP3": 91, "KP4": 92, "KP5": 93,
   "KP6": 94, "KP7": 95, "KP8": 96, "KP9": 97, "KP0": 98, "KPDOT": 99,

   # === Модификаторы (ВАЖНО) ===
   "LEFTCTRL": 224, "LEFTSHIFT": 225, "LEFTALT": 226, "LEFTGUI": 227,
   "RIGHTCTRL": 228, "RIGHTSHIFT": 229, "RIGHTALT": 230, "RIGHTGUI": 231,
  }

  # --- Новый полный словарь для поиска по человеко-читаемым именам ---
  self.key_name_to_scancode = {
   # Буквы A-Z
   "A": 4, "B": 5, "C": 6, "D": 7, "E": 8, "F": 9, "G": 10, "H": 11,
   "I": 12, "J": 13, "K": 14, "L": 15, "M": 16, "N": 17, "O": 18,
   "P": 19, "Q": 20, "R": 21, "S": 22, "T": 23, "U": 24, "V": 25,
   "W": 26, "X": 27, "Y": 28, "Z": 29,

   # Цифры сверху
   "1": 30, "2": 31, "3": 32, "4": 33, "5": 34,
   "6": 35, "7": 36, "8": 37, "9": 38, "0": 39,

   # Символы
   "`": 53, "-": 45, "=": 46, "[": 47, "]": 48, "\\": 49,
   ";": 51, "'": 52, ",": 54, ".": 55, "/": 56,

   # Модификаторы и специальные
   "ESC": 41, "TAB": 43, "CAPS LOCK": 57, "SHIFT": 225,  # Left Shift
   "SHIFT_L": 225, "SHIFT_R": 229,  # Right Shift — 229 (важно для Y!)
   "CTRL": 224, "CTRL_L": 224, "CTRL_R": 228,
   "ALT_L": 226, "ALT_R": 230,
   "WINDOWS": 227, "MENU": 231, "FN": 0,  # Fn обычно не имеет scancode
   "SPACE": 44, "ENTER": 40, "BACKSPACE": 42,

   # F-клавиши
   "F1": 58, "F2": 59, "F3": 60, "F4": 61, "F5": 62,
   "F6": 63, "F7": 64, "F8": 65, "F9": 66, "F10": 67,
   "F11": 68, "F12": 69,

   # Стрелки
   "UP": 82, "DOWN": 81, "LEFT": 80, "RIGHT": 79,

   # NumPad (основные)
   "NUM LOCK": 83,
   "0": 98, "1": 89, "2": 90, "3": 91, "4": 92,
   "5": 93, "6": 94, "7": 95, "8": 96, "9": 97,
   "+": 87, "-": 86, "*": 85, "/": 84, ".": 99,
   "ENTER": 88,  # NumPad Enter

   # Дополнительные
   "INSERT": 73, "DELETE": 76, "HOME": 74, "END": 77,
   "PGUP": 75, "PGDN": 78,
  }

  # --- Логическое сопоставление кнопок для Xemu ---
  self.logical_map = {
   # Основные кнопки Xbox (без префикса btn_)
   "btn_a": "a",
   "btn_b": "b",
   "btn_x": "x",
   "btn_y": "y",
   "back": "back",
   "start": "start",
   "white": "white",
   "black": "black",
   "lstick_btn": "lstick_btn",
   "rstick_btn": "rstick_btn",
   "guide": "guide",

   # Крестовина 1 = D-PAD
   "dpad1_up": "dpad_up",
   "dpad1_down": "dpad_down",
   "dpad1_left": "dpad_left",
   "dpad1_right": "dpad_right",

   # Крестовина 2 = LEFT STICK
   "dpad2_up": "lstick_up",
   "dpad2_down": "lstick_down",
   "dpad2_left": "lstick_left",
   "dpad2_right": "lstick_right",

   # Крестовина 3 = RIGHT STICK
   "dpad3_up": "rstick_up",
   "dpad3_down": "rstick_down",
   "dpad3_left": "rstick_left",
   "dpad3_right": "rstick_right",

   # Триггеры
   "ltrigger": "ltrigger",
   "rtrigger": "rtrigger",
  }

  # Дефолтные значения для всех кнопок (в правильной последовательности)
  # Теперь можно использовать любые клавиши из key_name_to_scancode
  self.default_mapping = {
   "btn_a": self.get_scancode_by_name("A"),  # A → кнопка A
   "btn_b": self.get_scancode_by_name("B"),  # B
   "btn_x": self.get_scancode_by_name("X"),  # X
   "btn_y": self.get_scancode_by_name("SHIFT_R"),  # Правый Shift (как на оригинальном Xbox)
   "dpad1_left": self.get_scancode_by_name("LEFT"),  # ←
   "dpad1_up": self.get_scancode_by_name("UP"),  # ↑ (D-PAD)
   "dpad1_right": self.get_scancode_by_name("RIGHT"),  # →
   "dpad1_down": self.get_scancode_by_name("DOWN"),  # ↓
   "back": self.get_scancode_by_name("BACKSPACE"),  # Back
   "start": self.get_scancode_by_name("ENTER"),  # Start
   "white": self.get_scancode_by_name("Q"),  # LB → Q (пример)
   "black": self.get_scancode_by_name("W"),  # RB → W (пример)
   "lstick_btn": self.get_scancode_by_name("L"),  # LS
   "rstick_btn": self.get_scancode_by_name("R"),  # RS
   "guide": self.get_scancode_by_name("WINDOWS"),  # Guide → Windows key
   "dpad2_up": self.get_scancode_by_name("UP"),  # Left stick up (можно переопределить)
   "dpad2_left": self.get_scancode_by_name("LEFT"),
   "dpad2_right": self.get_scancode_by_name("RIGHT"),
   "dpad2_down": self.get_scancode_by_name("DOWN"),
   "ltrigger": self.get_scancode_by_name("Z"),  # LT
   "rtrigger": self.get_scancode_by_name("C"),  # RT
  }

 def get_scancode_by_name(self, key_name: str):
  """
  Возвращает scancode по человеко-читаемому имени клавиши.
  Примеры: "UP", "SHIFT_R", "F12", "NUM LOCK", "A", "1" и т.д.
  Если не найдено — возвращает 0 (безопасное значение).
  """
  return self.key_name_to_scancode.get(key_name.upper().replace(" ", "_"), 0)

 def load_profiles(self):
  if os.path.exists(self.PROFILES_FILE):
   with open(self.PROFILES_FILE, "r", encoding="utf-8") as f:
    self.profiles = json.load(f)

 def save_profiles(self):
  with open(self.PROFILES_FILE, "w", encoding="utf-8") as f:
   json.dump(self.profiles, f, indent=2)

 def new_profile(self, name):
  if name not in self.profiles and name != "last_profile":
   self.profiles[name] = {"mapping": {}}
   self.save_profiles()

 def update_mapping(self, profile, key, scancode):
  if profile in self.profiles and profile != "last_profile":
   self.profiles[profile]["mapping"][key] = scancode
   self.save_profiles()

 def set_last_profile(self, profile_name):
  if profile_name in self.profiles and profile_name != "last_profile":
   self.profiles["last_profile"] = profile_name
   self.save_profiles()

 def set_default_mapping(self, profile_name):
  """Устанавливает дефолтные значения для профиля"""
  if profile_name in self.profiles and profile_name != "last_profile":
   self.profiles[profile_name]["mapping"] = self.default_mapping.copy()
   self.save_profiles()

 def validate_mapping_complete(self, profile_name):
  """Проверяет, что все кнопки имеют значения"""
  if profile_name not in self.profiles or profile_name == "last_profile":
   return False, "Профиль не найден"

  mapping = self.profiles[profile_name]["mapping"]
  missing_buttons = []

  # Словарь красивых имен кнопок для сообщений
  button_display_names = {
   # Основные кнопки
   "btn_a": "A", "btn_b": "B", "btn_x": "X", "btn_y": "Y",
   # D-PAD
   "dpad1_up": "↑ (D-PAD)", "dpad1_down": "↓ (D-PAD)", "dpad1_left": "← (D-PAD)", "dpad1_right": "→ (D-PAD)",
   # Left Stick
   "dpad2_up": "↑ (Left Stick)", "dpad2_down": "↓ (Left Stick)", "dpad2_left": "← (Left Stick)", "dpad2_right": "→ (Left Stick)",
   "lstick_btn": "LS (Left Stick Button)",
   # Right Stick
   "dpad3_up": "↑ (Right Stick)", "dpad3_down": "↓ (Right Stick)", "dpad3_left": "← (Right Stick)", "dpad3_right": "→ (Right Stick)",
   "rstick_btn": "RS (Right Stick Button)",
   # Триггеры
   "ltrigger": "LT (Left Trigger)", "rtrigger": "RT (Right Trigger)",
   # Системные кнопки
   "back": "Back", "start": "Start", "guide": "Guide", "white": "LB", "black": "RB",
   # Специальные
   "center_abxy": "ABXY Center", "center_dpad": "D-PAD Center"
  }

  for button_key in self.default_mapping.keys():
   if button_key not in mapping or mapping[button_key] is None or mapping[button_key] == 0:
    display_name = button_display_names.get(button_key, self.logical_map.get(button_key, button_key))
    missing_buttons.append(display_name)

  if missing_buttons:
   return False, f"Не настроена кнопка: {missing_buttons[0]}"

  return True, "Все кнопки настроены"

 def export_xemu_config(self, filepath):
  current_profile = self.profiles.get("last_profile", "Default")
  if current_profile not in self.profiles:
   current_profile = "Default"

  mapping = self.profiles[current_profile]["mapping"]

  # Проверяем, что все кнопки настроены
  is_valid, message = self.validate_mapping_complete(current_profile)
  if not is_valid:
   raise ValueError(f"Невозможно сохранить конфигурацию: {message}")

  # Формируем новые строки для секции биндингов в правильной последовательности
  new_bindings = []
  for ui_key in self.default_mapping.keys():
   if ui_key in mapping:
    scancode = mapping[ui_key]
    logical = self.logical_map.get(ui_key)
    if logical:
     new_bindings.append(f"{logical} = {scancode}")
    else:
     new_bindings.append(f"{ui_key} = {scancode}")

  # Читаем существующий файл, если он есть
  lines = []
  if os.path.exists(filepath):
   with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

  final_output = []
  skip_section = False
  section_found = False

  for line in lines:
   stripped = line.strip()
   if stripped == "[input.keyboard_controller_scancode_map]":
    section_found = True
    skip_section = True
    final_output.append(line)
    for b_line in new_bindings:
     final_output.append(b_line + "\n")
    continue
   if skip_section and stripped.startswith("["):
    skip_section = False
   if not skip_section:
    final_output.append(line)

  # Если секции не было, добавляем её в конец
  if not section_found:
   if final_output and not final_output[-1].endswith("\n"):
    final_output.append("\n")
   final_output.append("[input.keyboard_controller_scancode_map]\n")
   for b_line in new_bindings:
    final_output.append(b_line + "\n")

  with open(filepath, "w", encoding="utf-8") as f:
   f.writelines(final_output)

  print(f"[OK] Конфигурация обновлена в {filepath}")

'''
key_name_to_scancode = {
    # Буквы A-Z
    "A": 4, "B": 5, "C": 6, "D": 7, "E": 8, "F": 9, "G": 10, "H": 11,
    "I": 12, "J": 13, "K": 14, "L": 15, "M": 16, "N": 17, "O": 18,
    "P": 19, "Q": 20, "R": 21, "S": 22, "T": 23, "U": 24, "V": 25,
    "W": 26, "X": 27, "Y": 28, "Z": 29,

    # Цифры сверху
    "1": 30, "2": 31, "3": 32, "4": 33, "5": 34,
    "6": 35, "7": 36, "8": 37, "9": 38, "0": 39,

    # Символы
    "`": 53, "-": 45, "=": 46, "[": 47, "]": 48, "\\": 49,
    ";": 51, "'": 52, ",": 54, ".": 55, "/": 56,

    # Модификаторы и специальные
    "ESC": 41, "TAB": 43, "CAPS LOCK": 57, "SHIFT": 225,   # Left Shift
    "SHIFT_L": 225, "SHIFT_R": 229,                        # Right Shift — 229 (важно для Y!)
    "CTRL": 224, "CTRL_L": 224, "CTRL_R": 228,
    "ALT_L": 226, "ALT_R": 230,
    "WINDOWS": 227, "MENU": 231, "FN": 0,  # Fn обычно не имеет scancode
    "SPACE": 44, "ENTER": 40, "BACKSPACE": 42,

    # F-клавиши
    "F1": 58, "F2": 59, "F3": 60, "F4": 61, "F5": 62,
    "F6": 63, "F7": 64, "F8": 65, "F9": 66, "F10": 67,
    "F11": 68, "F12": 69,

    # Стрелки
    "UP": 82, "DOWN": 81, "LEFT": 80, "RIGHT": 79,

    # NumPad (основные)
    "NUM LOCK": 83,
    "0": 98, "1": 89, "2": 90, "3": 91, "4": 92,
    "5": 93, "6": 94, "7": 95, "8": 96, "9": 97,
    "+": 87, "-": 86, "*": 85, "/": 84, ".": 99,
    "ENTER": 88,  # NumPad Enter

    # Дополнительные
    "INSERT": 73, "DELETE": 76, "HOME": 74, "END": 77,
    "PGUP": 75, "PGDN": 78,
}

'''

















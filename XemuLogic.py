import os, json, string


class XemuConfigManager:
 PROFILES_FILE = "xemu_profiles.json"

 def __init__(self):
  self.profiles = {"last_profile": "Default"}

  # Полный словарь для поиска по человеко-читаемым именам
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
   "ESC": 41, "TAB": 43, "CAPS LOCK": 57, "SHIFT": 225,
   "SHIFT_L": 225, "SHIFT_R": 229,
   "CTRL": 224, "CTRL_L": 224, "CTRL_R": 228,
   "ALT_L": 226, "ALT_R": 230,
   "WINDOWS": 227, "MENU": 231, "FN": 0,
   "SPACE": 44, "ENTER": 40, "BACKSPACE": 42,

   # F-клавиши
   "F1": 58, "F2": 59, "F3": 60, "F4": 61, "F5": 62,
   "F6": 63, "F7": 64, "F8": 65, "F9": 66, "F10": 67,
   "F11": 68, "F12": 69,

   # Стрелки
   "UP": 82, "DOWN": 81, "LEFT": 80, "RIGHT": 79,

   # NumPad
   "NUM LOCK": 83,
   "NUM0": 98, "NUM1": 89, "NUM2": 90, "NUM3": 91, "NUM4": 92,
   "NUM5": 93, "NUM6": 94, "NUM7": 95, "NUM8": 96, "NUM9": 97,
   "KP+": 87, "KP-": 86, "KP*": 85, "KP/": 84, "KP.": 99,
   "KPENTER": 88,

   # Дополнительные
   "INSERT": 73, "DELETE": 76, "HOME": 74, "END": 77,
   "PGUP": 75, "PGDN": 78,

   # NumPad с префиксом KP
   "KP0": 98, "KP1": 89, "KP2": 90, "KP3": 91, "KP4": 92,
   "KP5": 93, "KP6": 94, "KP7": 95, "KP8": 96, "KP9": 97,
   "KPPLUS": 87, "KPMINUS": 86, "KPMULTIPLY": 85, "KPSLASH": 84, "KPDOT": 99,
   "KPPERIOD": 99,
   "LEFTSHIFT": 225, "RIGHTSHIFT": 229,
   "LEFTCTRL": 224, "RIGHTCTRL": 228,
   "LEFTALT": 226, "RIGHTALT": 230,
  }

  # Обратный словарь для поиска имени по scancode
  self.scancode_to_key_name = {v: k for k, v in self.key_name_to_scancode.items()}

  # Дефолтные значения в формате для xemu - ВСЕ 25 КНОПОК
  self.default_mapping = {
   # Основные кнопки (4)
   "a": 4,  # A -> кнопка A
   "b": 5,  # B -> кнопка B
   "x": 27,  # X -> кнопка X
   "y": 229,  # Y -> кнопка Y (RIGHTSHIFT)

   # D-PAD (4)
   "dpad_left": 80,  # D-PAD Left
   "dpad_up": 82,  # D-PAD Up
   "dpad_right": 79,  # D-PAD Right
   "dpad_down": 81,  # D-PAD Down

   # Системные кнопки (3)
   "back": 42,  # Back (BACKSPACE)
   "start": 88,  # Start (KPENTER)
   "guide": 227,  # Guide (WINDOWS)

   # Верхние кнопки (2)
   "white": 20,  # White (LB) -> Q
   "black": 26,  # Black (RB) -> W

   # Кнопки стиков (2)
   "lstick_btn": 15,  # Left Stick Button -> L
   "rstick_btn": 21,  # Right Stick Button -> R

   # Направления левого стика (4)
   "lstick_up": 82,  # Left Stick Up
   "lstick_left": 80,  # Left Stick Left
   "lstick_right": 79,  # Left Stick Right
   "lstick_down": 81,  # Left Stick Down

   # Направления правого стика (4) - ДОБАВЛЕНО
   "rstick_up": 96,  # Right Stick Up -> KP8
   "rstick_left": 92,  # Right Stick Left -> KP4
   "rstick_right": 94,  # Right Stick Right -> KP6
   "rstick_down": 93,  # Right Stick Down -> KP5

   # Триггеры (2)
   "ltrigger": 29,  # Left Trigger -> Z
   "rtrigger": 6,  # Right Trigger -> C
  }

  # Псевдонимы для совместимости
  self.aliases = {
   "btn_a": "a", "btn_b": "b", "btn_x": "x", "btn_y": "y",
   "dpad1_up": "dpad_up", "dpad1_down": "dpad_down",
   "dpad1_left": "dpad_left", "dpad1_right": "dpad_right",
   "dpad2_up": "lstick_up", "dpad2_down": "lstick_down",
   "dpad2_left": "lstick_left", "dpad2_right": "lstick_right",
   "dpad3_up": "rstick_up", "dpad3_down": "rstick_down",
   "dpad3_left": "rstick_left", "dpad3_right": "rstick_right",
   "lb": "white", "rb": "black",
   "lt": "ltrigger", "rt": "rtrigger",
  }

 def get_scancode_by_name(self, key_name: str):
  """
  Возвращает scancode по человеко-читаемому имени клавиши.
  """
  # Преобразуем имя к стандартному формату
  normalized_name = key_name.upper().replace(" ", "_")
  return self.key_name_to_scancode.get(normalized_name, 0)

 def load_profiles(self):
  if os.path.exists(self.PROFILES_FILE):
   with open(self.PROFILES_FILE, "r", encoding="utf-8") as f:
    loaded_profiles = json.load(f)

    # Копируем загруженные профили
    for profile_name, profile_data in loaded_profiles.items():
     if profile_name == "last_profile":
      self.profiles["last_profile"] = profile_data
      continue

     # Конвертируем старые имена в новые
     converted_mapping = {}
     if isinstance(profile_data, dict):
      for old_key, scancode in profile_data.items():
       # Если ключ есть в алиасах, используем новое имя
       if old_key in self.aliases:
        new_key = self.aliases[old_key]
       else:
        new_key = old_key
       converted_mapping[new_key] = scancode

     # Заполняем недостающие кнопки значениями по умолчанию
     for key in self.default_mapping.keys():
      if key not in converted_mapping:
       converted_mapping[key] = self.default_mapping[key]

     self.profiles[profile_name] = converted_mapping

  # Если нет дефолтного профиля, создаем его
  if "Default" not in self.profiles:
   self.profiles["Default"] = self.default_mapping.copy()

  # Если нет профиля "obscure", создаем его
  if "obscure" not in self.profiles:
   self.profiles["obscure"] = self.default_mapping.copy()

  self.save_profiles()

 def save_profiles(self):
  with open(self.PROFILES_FILE, "w", encoding="utf-8") as f:
   json.dump(self.profiles, f, indent=2)

 def new_profile(self, name):
  if name not in self.profiles and name != "last_profile":
   self.profiles[name] = self.default_mapping.copy()
   self.save_profiles()

 def update_mapping(self, profile, key, scancode):
  """Обновляет маппинг для профиля"""
  if profile in self.profiles and profile != "last_profile":
   # Конвертируем старый ключ в новый если нужно
   if key in self.aliases:
    key = self.aliases[key]

   self.profiles[profile][key] = scancode
   self.save_profiles()

 def set_last_profile(self, profile_name):
  if profile_name in self.profiles and profile_name != "last_profile":
   self.profiles["last_profile"] = profile_name
   self.save_profiles()

 def set_default_mapping(self, profile_name):
  """Устанавливает дефолтные значения для профиля"""
  if profile_name in self.profiles and profile_name != "last_profile":
   self.profiles[profile_name] = self.default_mapping.copy()
   self.save_profiles()

 def validate_mapping_complete(self, profile_name):
  """Проверяет, что все 25 кнопок имеют значения"""
  if profile_name not in self.profiles or profile_name == "last_profile":
   return False, "Профиль не найден"

  mapping = self.profiles[profile_name]

  # Словарь красивых имен кнопок для сообщений
  button_display_names = {
   # Основные кнопки (4)
   "a": "A", "b": "B", "x": "X", "y": "Y",

   # D-PAD (4)
   "dpad_up": "↑", "dpad_down": "↓",
   "dpad_left": "←", "dpad_right": "→",

   # Системные кнопки (3)
   "back": "Back", "start": "Start", "guide": "Guide",

   # Верхние кнопки (2)
   "white": "LB", "black": "RB",

   # Кнопки стиков (2)
   "lstick_btn": "LS", "rstick_btn": "RS",

   # Направления левого стика (4)
   "lstick_up": "↑", "lstick_down": "↓",
   "lstick_left": "←", "lstick_right": "→",

   # Направления правого стика (4)
   "rstick_up": "↑ (Right Stick)", "rstick_down": "↓ (Right Stick)",
   "rstick_left": "← (Right Stick)", "rstick_right": "→ (Right Stick)",

   # Триггеры (2)
   "ltrigger": "LT", "rtrigger": "RT",
  }

  missing_buttons = []

  # Проверяем все 25 кнопок из default_mapping
  for button_key in self.default_mapping.keys():
   if button_key not in mapping or mapping[button_key] is None or mapping[button_key] == 0:
    display_name = button_display_names.get(button_key, button_key)
    missing_buttons.append(display_name)

  if missing_buttons:
   return False, f"Не настроена кнопка: {missing_buttons[0]}"

  return True, "Все 25 кнопок настроены"

 def export_xemu_config(self, filepath):
  current_profile = self.profiles.get("last_profile", "Default")
  if current_profile not in self.profiles:
   current_profile = "Default"

  mapping = self.profiles[current_profile]

  # Проверяем, что все кнопки настроены
  is_valid, message = self.validate_mapping_complete(current_profile)
  if not is_valid:
   raise ValueError(f"Невозможно сохранить конфигурацию: {message}")

  # Формируем строки для секции биндингов - ВСЕ 25 КНОПОК
  new_bindings = []
  for key in [
   "a", "b", "x", "y",  # Основные кнопки (4)
   "dpad_left", "dpad_up", "dpad_right", "dpad_down",  # D-PAD (4)
   "back", "start", "guide",  # Системные (3)
   "white", "black",  # Верхние (2)
   "lstick_btn", "rstick_btn",  # Кнопки стиков (2)
   "lstick_up", "lstick_left", "lstick_right", "lstick_down",  # Левый стик (4)
   "rstick_up", "rstick_left", "rstick_right", "rstick_down",  # Правый стик (4)
   "ltrigger", "rtrigger"  # Триггеры (2)
  ]:
   if key in mapping:
    scancode = mapping[key]
    new_bindings.append(f"{key} = {scancode}")

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
    # Добавляем все 25 биндингов
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
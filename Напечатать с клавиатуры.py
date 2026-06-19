import evdev, glob, time, subprocess, sys
from evdev import UInput, ecodes


class SmartTyper:
 def __init__(self):
  try:
   subprocess.run(["sudo", "modprobe", "ntsync"], capture_output=True)
  except Exception:
   pass
  
  self.find_keyboard()
  self.ui = self.create_virtual_keyboard()
  
  # 1. Общие символы (одинаково печатаются в обеих раскладках)
  self.COMMON_MAP = {
   ' ': ecodes.KEY_SPACE, '\n': ecodes.KEY_ENTER, '\t': ecodes.KEY_TAB,
   '1': ecodes.KEY_1, '2': ecodes.KEY_2, '3': ecodes.KEY_3, '4': ecodes.KEY_4,
   '5': ecodes.KEY_5, '6': ecodes.KEY_6, '7': ecodes.KEY_7, '8': ecodes.KEY_8,
   '9': ecodes.KEY_9, '0': ecodes.KEY_0, '-': ecodes.KEY_MINUS, '=': ecodes.KEY_EQUAL,
   '\\': ecodes.KEY_BACKSLASH, '!': ecodes.KEY_1, '%': ecodes.KEY_5, '*': ecodes.KEY_8,
   '(': ecodes.KEY_9, ')': ecodes.KEY_0, '_': ecodes.KEY_MINUS, '+': ecodes.KEY_EQUAL
  }
  self.COMMON_SHIFT = set(['!', '%', '*', '(', ')', '_', '+'])
  
  # 2. Английские буквы
  self.EN_MAP = {
   'q': ecodes.KEY_Q, 'w': ecodes.KEY_W, 'e': ecodes.KEY_E, 'r': ecodes.KEY_R, 't': ecodes.KEY_T,
   'y': ecodes.KEY_Y, 'u': ecodes.KEY_U, 'i': ecodes.KEY_I, 'o': ecodes.KEY_O, 'p': ecodes.KEY_P,
   'a': ecodes.KEY_A, 's': ecodes.KEY_S, 'd': ecodes.KEY_D, 'f': ecodes.KEY_F, 'g': ecodes.KEY_G,
   'h': ecodes.KEY_H, 'j': ecodes.KEY_J, 'k': ecodes.KEY_K, 'l': ecodes.KEY_L, 'z': ecodes.KEY_Z,
   'x': ecodes.KEY_X, 'c': ecodes.KEY_C, 'v': ecodes.KEY_V, 'b': ecodes.KEY_B, 'n': ecodes.KEY_N,
   'm': ecodes.KEY_M
  }
  
  # 3. Русские буквы
  self.RU_MAP = {
   'й': ecodes.KEY_Q, 'ц': ecodes.KEY_W, 'у': ecodes.KEY_E, 'к': ecodes.KEY_R, 'е': ecodes.KEY_T,
   'н': ecodes.KEY_Y, 'г': ecodes.KEY_U, 'ш': ecodes.KEY_I, 'щ': ecodes.KEY_O, 'з': ecodes.KEY_P,
   'х': ecodes.KEY_LEFTBRACE, 'ъ': ecodes.KEY_RIGHTBRACE, 'ф': ecodes.KEY_A, 'ы': ecodes.KEY_S,
   'в': ecodes.KEY_D, 'а': ecodes.KEY_F, 'п': ecodes.KEY_G, 'р': ecodes.KEY_H, 'о': ecodes.KEY_J,
   'л': ecodes.KEY_K, 'д': ecodes.KEY_L, 'ж': ecodes.KEY_SEMICOLON, 'э': ecodes.KEY_APOSTROPHE,
   'я': ecodes.KEY_Z, 'ч': ecodes.KEY_X, 'с': ecodes.KEY_C, 'м': ecodes.KEY_V, 'и': ecodes.KEY_B,
   'т': ecodes.KEY_N, 'ь': ecodes.KEY_M, 'б': ecodes.KEY_COMMA, 'ю': ecodes.KEY_DOT, 'ё': ecodes.KEY_GRAVE
  }
  
  # 4. Строго английская пунктуация
  self.EN_PUNCT = {
   '@': ecodes.KEY_2, '#': ecodes.KEY_3, '$': ecodes.KEY_4, '^': ecodes.KEY_6, '&': ecodes.KEY_7,
   '{': ecodes.KEY_LEFTBRACE, '}': ecodes.KEY_RIGHTBRACE, '|': ecodes.KEY_BACKSLASH,
   '<': ecodes.KEY_COMMA, '>': ecodes.KEY_DOT, '~': ecodes.KEY_GRAVE,
   '`': ecodes.KEY_GRAVE, '[': ecodes.KEY_LEFTBRACE, ']': ecodes.KEY_RIGHTBRACE,
   "'": ecodes.KEY_APOSTROPHE
  }
  self.EN_PUNCT_SHIFT = set(['@', '#', '$', '^', '&', '{', '}', '|', '<', '>', '~'])
  
  # 5. Строго русская пунктуация
  self.RU_PUNCT = {
   '№': ecodes.KEY_3
  }
  self.RU_PUNCT_SHIFT = set(['№'])
 
 def find_keyboard(self):
  for path in glob.glob("/dev/input/event*"):
   try:
    dev = evdev.InputDevice(path)
    if "keyboard" in dev.name.lower() or "Keyboard" in dev.name:
     return dev
   except Exception:
    continue
  print("[ERROR] Клавиатура не найдена. Запустите скрипт с sudo.")
  sys.exit(1)
 
 def create_virtual_keyboard(self):
  capabilities = {ecodes.EV_KEY: [ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_C, ecodes.KEY_D, ecodes.KEY_E, ecodes.KEY_F,
                                  ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_I, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L,
                                  ecodes.KEY_M, ecodes.KEY_N, ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_Q, ecodes.KEY_R,
                                  ecodes.KEY_S, ecodes.KEY_T, ecodes.KEY_U, ecodes.KEY_V, ecodes.KEY_W, ecodes.KEY_X,
                                  ecodes.KEY_Y, ecodes.KEY_Z, ecodes.KEY_SPACE, ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
                                  ecodes.KEY_COMMA, ecodes.KEY_DOT, ecodes.KEY_ENTER, ecodes.KEY_TAB,
                                  ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5,
                                  ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9, ecodes.KEY_0,
                                  ecodes.KEY_SEMICOLON, ecodes.KEY_APOSTROPHE, ecodes.KEY_GRAVE,
                                  ecodes.KEY_LEFTBRACE, ecodes.KEY_RIGHTBRACE, ecodes.KEY_BACKSLASH,
                                  ecodes.KEY_MINUS, ecodes.KEY_EQUAL, ecodes.KEY_SLASH
                                  ]
                  }
  ui = UInput(capabilities, name="Smart-Virtual-Keyboard")
  return ui
 
 def get_current_layout(self):
  try:
   cmd = "xset -q | grep -A 0 'LED mask' | awk '{print $10}'"
   result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
   mask = result.stdout.strip()
   
   if mask == "00001002":
    return 'us'
   else:
    return 'ru'
  except Exception:
   return 'us'
 
 def set_layout(self, lang):
  current_layout = self.get_current_layout()
  if current_layout == lang:
   return
  
  try:
   subprocess.run(["xte", "key ISO_Next_Group"], check=True)
   time.sleep(0.15)
  except Exception as e:
   print(f"[ERROR] Не удалось переключить раскладку через xte: {e}")
 
 def type_text(self, text, delay=0.05):
  shift_delay = 0.01
  current_layout = self.get_current_layout()
  for ch in text:
   keycode = None
   need_shift = False
   needed_layout = current_layout
   lower_ch = ch.lower()
   
   # 1. Общие символы
   if ch in self.COMMON_MAP:
    keycode = self.COMMON_MAP[ch]
    need_shift = ch in self.COMMON_SHIFT
   
   # 2. Исключительно русский символ (буквы)
   elif lower_ch in self.RU_MAP:
    needed_layout = 'ru'
    keycode = self.RU_MAP[lower_ch]
    need_shift = ch.isupper()
   
   # 3. Исключительно английский символ (буквы)
   elif lower_ch in self.EN_MAP:
    needed_layout = 'us'
    keycode = self.EN_MAP[lower_ch]
    need_shift = ch.isupper()
   
   # 4. Строго английская пунктуация
   elif ch in self.EN_PUNCT:
    needed_layout = 'us'
    keycode = self.EN_PUNCT[ch]
    need_shift = ch in self.EN_PUNCT_SHIFT
   
   # 5. Строго русская пунктуация
   elif ch in self.RU_PUNCT:
    needed_layout = 'ru'
    keycode = self.RU_PUNCT[ch]
    need_shift = ch in self.RU_PUNCT_SHIFT
   
   # 6. Двусмысленные знаки (печатаются разными кнопками, в зависимости от текущей раскладки)
   elif ch in [',', '.', '?', ':', ';', '"', '/']:
    needed_layout = current_layout  # Остаемся в той же раскладке, чтобы не было лишних переключений
    if current_layout == 'us':
     if ch == ',':
      keycode = ecodes.KEY_COMMA
     elif ch == '.':
      keycode = ecodes.KEY_DOT
     elif ch == '?':
      keycode = ecodes.KEY_SLASH; need_shift = True
     elif ch == ':':
      keycode = ecodes.KEY_SEMICOLON; need_shift = True
     elif ch == ';':
      keycode = ecodes.KEY_SEMICOLON
     elif ch == '"':
      keycode = ecodes.KEY_APOSTROPHE; need_shift = True
     elif ch == '/':
      keycode = ecodes.KEY_SLASH
    else:  # ru
     if ch == ',':
      keycode = ecodes.KEY_SLASH; need_shift = True
     elif ch == '.':
      keycode = ecodes.KEY_SLASH
     elif ch == '?':
      keycode = ecodes.KEY_7; need_shift = True
     elif ch == ':':
      keycode = ecodes.KEY_6; need_shift = True
     elif ch == ';':
      keycode = ecodes.KEY_4; need_shift = True
     elif ch == '"':
      keycode = ecodes.KEY_2; need_shift = True
     elif ch == '/':
      keycode = ecodes.KEY_BACKSLASH; need_shift = True
   else:
    print(f"[WARN] Символ '{ch}' не поддерживается, пропускаем.")
    continue
   
   if current_layout != needed_layout:
    self.set_layout(needed_layout)
    current_layout = self.get_current_layout()
   
   if need_shift:
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
    self.ui.syn()
    time.sleep(shift_delay)
   
   self.ui.write(ecodes.EV_KEY, keycode, 1)
   self.ui.syn()
   time.sleep(delay / 2)
   self.ui.write(ecodes.EV_KEY, keycode, 0)
   self.ui.syn()
   
   if need_shift:
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
    self.ui.syn()
   
   time.sleep(delay)
 
 def close(self):
  self.ui.close()


typer = SmartTyper()

print("\nСкрипт начнёт печать через 3 секунды. Переключитесь в текстовый редактор...")
time.sleep(6)

test_text = "Привет, я нахожусь на Linux. Hello World! ? : 123 @ # $ №"
print(f"[INFO] Печатаем: {test_text}")

typer.type_text(test_text, delay=0.06)

print("\n[OK] Печать завершена!")
typer.close()

print("\nСкрипт начнёт печать через 3 секунды. Переключитесь в текстовый редактор...")
time.sleep(6)

test_text = "Привет, я нахожусь на Linux. Hello World! ? : 123"
print(f"[INFO] Печатаем: {test_text}")

typer.type_text(test_text, delay=0.06)

print("\n[OK] Печать завершена!")
typer.close()
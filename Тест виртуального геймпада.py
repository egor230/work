import os, sys, glob, time, json;
from evdev import UInput, ecodes, InputDevice, AbsInfo

# 1. Карта логических имен кнопок геймпада к кодам evdev
logical_to_ecode_btn = {
 "A": ecodes.BTN_A,
 "B": ecodes.BTN_B,
 "X": ecodes.BTN_X,
 "Y": ecodes.BTN_Y,
 "LEFT_SHOULDER": ecodes.BTN_TL,
 "RIGHT_SHOULDER": ecodes.BTN_TR,
 "LEFT_TRIGGER": ecodes.BTN_TL2,
 "RIGHT_TRIGGER": ecodes.BTN_TR2,
 "GUIDE": ecodes.BTN_MODE,
 "BACK": ecodes.BTN_SELECT,
 "START": ecodes.BTN_START,
 "DPAD_UP": ecodes.BTN_DPAD_UP,
 "DPAD_DOWN": ecodes.BTN_DPAD_DOWN,
 "DPAD_LEFT": ecodes.BTN_DPAD_LEFT,
 "DPAD_RIGHT": ecodes.BTN_DPAD_RIGHT,
 "LEFT_THUMB_PRESSED": ecodes.BTN_THUMBL,
 "RIGHT_THUMB_PRESSED": ecodes.BTN_THUMBR,
}
# 2. Карта логических имен осей к кодам evdev и направлению (1 или -1)
logical_to_ecode_axis = {
 "LEFT_THUMB_UP": (ecodes.ABS_Y, -1),
 "LEFT_THUMB_DOWN": (ecodes.ABS_Y, 1),
 "LEFT_THUMB_LEFT": (ecodes.ABS_X, -1),
 "LEFT_THUMB_RIGHT": (ecodes.ABS_X, 1),
 "RIGHT_THUMB_UP": (ecodes.ABS_RY, -1),
 "RIGHT_THUMB_DOWN": (ecodes.ABS_RY, 1),
 "RIGHT_THUMB_LEFT": (ecodes.ABS_RX, -1),
 "RIGHT_THUMB_RIGHT": (ecodes.ABS_RX, 1),
}
# 3. Инициализация пустых карт для динамического заполнения из профиля
key_to_btn = {}
key_to_axis = {}
# 4. Загрузка конфигурации из JSON файла
config_file = "editor_for_Xbox360_app_settings.json"
if os.path.exists(config_file):
 with open(config_file, "r", encoding="utf-8") as f:
  config = json.load(f)
 profile_name = config.get("last_profile", "Default").strip()
 profiles = config.get("profiles", {})
 profile = profiles.get(profile_name, profiles.get("Default", {}))
else:
 # Дефолтный профиль, если файл настроек не найден
 profile = {
  "A": "KEY_SPACE", "B": "KEY_B", "X": "KEY_X", "Y": "KEY_Y",
  "LEFT_SHOULDER": "KEY_Q", "RIGHT_SHOULDER": "KEY_E",
  "LEFT_TRIGGER": "KEY_1", "RIGHT_TRIGGER": "KEY_2",
  "GUIDE": "KEY_F12", "BACK": "KEY_BACKSPACE", "START": "KEY_ENTER",
  "DPAD_UP": "KEY_UP", "DPAD_DOWN": "KEY_DOWN", "DPAD_LEFT": "KEY_LEFT", "DPAD_RIGHT": "KEY_RIGHT",
  "LEFT_THUMB_UP": "KEY_W", "LEFT_THUMB_DOWN": "KEY_S", "LEFT_THUMB_LEFT": "KEY_A", "LEFT_THUMB_RIGHT": "KEY_D",
  "RIGHT_THUMB_UP": "KEY_KP8", "RIGHT_THUMB_DOWN": "KEY_KP2", "RIGHT_THUMB_LEFT": "KEY_KP4", "RIGHT_THUMB_RIGHT": "KEY_KP6",
  "LEFT_THUMB_PRESSED": "KEY_LEFTSHIFT", "RIGHT_THUMB_PRESSED": "KEY_Z"
 }
# 5. Заполнение карт key_to_btn и key_to_axis на основе выбранного профиля
for log_name, key_str in profile.items():
 log_name = log_name.strip()  # Убираем возможные пробелы из ключей JSON
 key_str = key_str.strip()  # Убираем возможные пробелы из значений JSON
 if log_name in logical_to_ecode_btn:
  try:
   key_code = getattr(ecodes, key_str)
   key_to_btn[key_code] = logical_to_ecode_btn[log_name]
  except AttributeError:
   pass  # Игнорируем неизвестные клавиши
 elif log_name in logical_to_ecode_axis:
  try:
   key_code = getattr(ecodes, key_str)
   key_to_axis[key_code] = logical_to_ecode_axis[log_name]
  except AttributeError:
   pass
# 6. Настройки осей (передаются прямо в возможности UInput)
axis_caps = {
 ecodes.ABS_X: AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0),
 ecodes.ABS_Y: AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0),
 ecodes.ABS_RX: AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0),
 ecodes.ABS_RY: AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0),
 ecodes.ABS_RZ: AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0),
}
# 7. Формируем возможности (исправление TypeError: передаем AbsInfo внутри словаря)
gamepad_caps = {
 ecodes.EV_KEY: list(key_to_btn.values()),
 ecodes.EV_ABS: list(axis_caps.items()),
}
# 8. Словарь для хранения текущих состояний осей
axis_states = {ecodes.ABS_X: 0, ecodes.ABS_Y: 0, ecodes.ABS_RX: 0, ecodes.ABS_RY: 0, ecodes.ABS_RZ: 0}


def main():
 kbd_device = None
 # 9. Поиск устройства физической клавиатуры Logitech
 for path in glob.glob("/dev/input/event*"):
  try:
   dev = InputDevice(path)
   if "Logitech" in dev.name and "Keyboard" in dev.name and "Consumer" not in dev.name and "System" not in dev.name:
    kbd_device = dev
    break
  except:
   continue
 
 if not kbd_device:
  print("Ошибка: клавиатура Logitech не найдена!")
  return
 
 print("Создаем виртуальный геймпад...")
 vinput = UInput(gamepad_caps, name="Python-Virtual-Xbox-Gamepad", bustype=ecodes.BUS_USB)
 time.sleep(1)
 
 print("\n--- Список устройств (ищем геймпад) ---")
 os.system("lsinput | grep -A 6 'Python-Virtual-Xbox-Gamepad'")
 print("---------------------------------------\n")
 
 print(f"Перехватываем клавиатуру: {kbd_device.name}")
 kbd_device.grab()
 print("Геймпад активен! Нажимай кнопки. Для выхода Ctrl+C.")
 try:
  for event in kbd_device.read_loop():
   if event.type == ecodes.EV_KEY:
    if event.code in key_to_btn:
     vinput.write(ecodes.EV_KEY, key_to_btn[event.code], event.value)
     vinput.syn()
    elif event.code in key_to_axis:
     abs_code, direction = key_to_axis[event.code]
     if event.value == 1:
      axis_states[abs_code] += direction * 32767 if abs_code != ecodes.ABS_RZ else direction * 255
     elif event.value == 0:
      axis_states[abs_code] -= direction * 32767 if abs_code != ecodes.ABS_RZ else direction * 255
     vinput.write(ecodes.EV_ABS, abs_code, axis_states[abs_code])
     vinput.syn()
 except KeyboardInterrupt:
  print("\nВыход...")
 finally:
  if kbd_device:
   kbd_device.ungrab()
  vinput.close()

if __name__ == "__main__":
 main()
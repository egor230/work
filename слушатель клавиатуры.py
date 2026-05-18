import threading
import time
from evdev import InputDevice, list_devices, ecodes
from pynput.keyboard import Listener

# --- твоя карта (без изменений) ---
simple_key_map = {
 "KEY_SPACE": "Space",
 "KEY_ENTER": "Enter",
 "KEY_BACKSPACE": "Backspace",
 "KEY_TAB": "Tab",
 "KEY_ESC": "Esc",
 "KEY_LEFTSHIFT": "L_Shift",
 "KEY_RIGHTSHIFT": "R_Shift",
 "KEY_LEFTCTRL": "L_Ctrl",
 "KEY_RIGHTCTRL": "R_Ctrl",
 "KEY_LEFTALT": "L_Alt",
 "KEY_RIGHTALT": "R_Alt",
 "KEY_LEFTMETA": "L_Win",
 "KEY_RIGHTMETA": "R_Win",

 "KEY_UP": "UP",
 "KEY_DOWN": "DOWN",
 "KEY_LEFT": "LEFT",
 "KEY_RIGHT": "RIGHT",
 
 "KEY_KP7": "NUM_7",
 "KEY_KP8": "NUM_8",
 "KEY_KP9": "NUM_9",
 "KEY_KP4": "NUM_4",
 "KEY_KP5": "NUM_5",
 "KEY_KP6": "NUM_6",
 "KEY_KP1": "NUM_1",
 "KEY_KP2": "NUM_2",
 "KEY_KP3": "NUM_3",
 "KEY_KP0": "NUM_0",
 "<65437>" : "NUM_5",
 "<65032>" : "L_Ctrl"
}

lock = threading.Lock()
# Для каждого устройства запускаем отдельный поток чтения
def read_device():
 try:
  target_dev = None
  devices = [InputDevice(path) for path in list_devices()]
  for dev in devices:
   caps = dev.capabilities().get(ecodes.EV_KEY, [])
   dev_str_lower = str(dev).lower()
   
   if ecodes.KEY_A in caps and "keyboard" in dev_str_lower and "phys" in dev_str_lower and "rival" not in dev_str_lower:
    target_dev = dev
    break
  
  if target_dev is None:
   print("[-] Подходящее устройство клавиатуры не найдено")
   return
  
  print(f"[+] Запущен слушатель для {target_dev.name}")
  for event in target_dev.read_loop():
   if event.type == ecodes.EV_KEY and event.value == 1:
    with lock:
     key_event = ecodes.KEY.get(event.code, f"UNKNOWN_{event.code}")
     key_name = simple_key_map.get(key_event, key_event).replace("KEY_", "")
     print(key_name)
 
 except OSError as e:
  print(f"[-] Ошибка устройства: {e}")
 except Exception as e:
  print(f"[-] Неожиданная ошибка: {e}")


thread = threading.Thread(target=read_device, args=(), daemon=True)
thread.start()
while True:
 time.sleep(1)
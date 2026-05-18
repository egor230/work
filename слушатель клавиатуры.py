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

# --- глобальные переменные ---
active_devices = {}
lock = threading.Lock()

# --- поиск всех клавиатур ---
def find_keyboards():
    devices = []

    for path in list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities().get(ecodes.EV_KEY, [])

            if ecodes.KEY_A in caps:
                devices.append(dev)

        except Exception:
            continue

    return devices



devices = find_keyboards()
# --- менеджер устройств ---
def device_manager():
 global devices
 
 with lock:
  for dev in devices:
   try:
    # читаем одно событие без блокировки
    event = dev.read_one()
    if event is None:
     continue
    
    if event.type != ecodes.EV_KEY:
     continue
    
    if event.value != 1:
     continue
    
    key_event = ecodes.KEY.get(event.code, f"UNKNOWN_{event.code}")
    key_name = simple_key_map.get(key_event, key_event)
    
    print(key_name)
    return key_name  # сразу выходим после первого найденного
   
   except BlockingIOError:
    continue
   except OSError:
    continue
 
 return None

# --- pynput (второй слушатель) ---
def on_press(key):
    try:
        print(f"[PYNPUT] {key}")
        result = device_manager()
        if result:
            print(f"[EVDEV RESULT] {result}")
    except Exception as e:
        print(f"[PYNPUT ERROR] {e}")


def start_pynput():
    listener = Listener(on_press=on_press)
    listener.daemon = True
    listener.start()


# --- запуск ---
if __name__ == "__main__":
    print("🚀 Ultimate keyboard listener запущен")

    # threading.Thread(target=device_manager, daemon=True).start()
    start_pynput()

    while True:
        time.sleep(1)
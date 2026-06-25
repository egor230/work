from evdev import InputDevice, categorize, ecodes, list_devices
simple_key_map = {
    # Верхний ряд (Row 1)
    'KEY_ESC': 'Esc',
    'KEY_F1': 'F1', 'KEY_F2': 'F2', 'KEY_F3': 'F3', 'KEY_F4': 'F4', 'KEY_F5': 'F5',
    'KEY_F6': 'F6', 'KEY_F7': 'F7', 'KEY_F8': 'F8', 'KEY_F9': 'F9', 'KEY_F10': 'F10',
    'KEY_F11': 'F11', 'KEY_F12': 'F12',
    'KEY_INSERT': 'Insert', 'KEY_DELETE': 'Delete',
    'KEY_HOME': 'Home', 'KEY_END': 'End',
    'KEY_PAGEUP': 'PgUp', 'KEY_PAGEDOWN': 'PgDn',

    # Ряд с цифрами (Row 2)
    'KEY_GRAVE': '~\n`',
    'KEY_1': '!\n1', 'KEY_2': '@\n2', 'KEY_3': '#\n3', 'KEY_4': '$\n4', 'KEY_5': '%\n5',
    'KEY_6': '^\n6', 'KEY_7': '&\n7', 'KEY_8': '*\n8', 'KEY_9': '(\n9', 'KEY_0': ')\n0',
    'KEY_MINUS': '_\n-', 'KEY_EQUAL': '+\n=',
    'KEY_BACKSPACE': 'Backspace',
    'KEY_NUMLOCK': 'Num Lock',
    'KEY_KPSLASH': '/', 'KEY_KPASTERISK': '*', 'KEY_KPMINUS': '-',

    # Ряд с Tab (Row 3)
    'KEY_TAB': 'Tab',
    'KEY_Q': 'Q', 'KEY_W': 'W', 'KEY_E': 'E', 'KEY_R': 'R', 'KEY_T': 'T',
    'KEY_Y': 'Y', 'KEY_U': 'U', 'KEY_I': 'I', 'KEY_O': 'O', 'KEY_P': 'P',
    'KEY_LEFTBRACE': '{\n[', 'KEY_RIGHTBRACE': '}\n]', 'KEY_BACKSLASH': '|\n\\',
    'KEY_KP7': ' 7\nHome', 'KEY_KP8': '8\n↑', 'KEY_KP9': '9\nPgUp',
    'KEY_KPPLUS': '+',

    # Ряд с Caps Lock (Row 4)
    'KEY_CAPSLOCK': 'Caps Lock',
    'KEY_A': 'A', 'KEY_S': 'S', 'KEY_D': 'D', 'KEY_F': 'F', 'KEY_G': 'G',
    'KEY_H': 'H', 'KEY_J': 'J', 'KEY_K': 'K', 'KEY_L': 'L',
    'KEY_SEMICOLON': ':\n;', 'KEY_APOSTROPHE': '"\n\'',
    'KEY_ENTER': '\nEnter\n',
    'KEY_KP4': '4\n←', 'KEY_KP5': '5\n', 'KEY_KP6': '6\n→',

    # Ряд с Shift (Row 5)
    'KEY_LEFTSHIFT': 'Shift_L',
    'KEY_Z': 'Z', 'KEY_X': 'X', 'KEY_C': 'C', 'KEY_V': 'V', 'KEY_B': 'B',
    'KEY_N': 'N', 'KEY_M': 'M',
    'KEY_COMMA': '<\n,', 'KEY_DOT': '>\n.', 'KEY_SLASH': '?\n/',
    'KEY_RIGHTSHIFT': 'Shift_R',
    'KEY_KP1': '1\nEnd', 'KEY_KP2': '2\n↓', 'KEY_KP3': '3\nPgDn',
    'KEY_KPENTER': 'KEnter',

    # Нижний ряд (Row 6)
    'KEY_LEFTCTRL': 'Ctrl',
    'KEY_LEFTMETA': 'Windows',
    'KEY_LEFTALT': 'Alt_L',
    'KEY_SPACE': 'space',
    'KEY_RIGHTALT': 'Alt_r',
    # 'KEY_FN': 'Fn',  # evdev не имеет KEY_FN
    'KEY_COMPOSE': 'Menu',
    'KEY_RIGHTCTRL': 'Ctrl_r',
    'KEY_UP': 'up',
    'KEY_KP0': '0\nIns',
    'KEY_KPDOT': ' . ',

    # Стрелки (Row 7)
    'KEY_LEFT': 'Left',
    'KEY_DOWN': 'Down',
    'KEY_RIGHT': 'Right',
}
keyboard = None
devices = [InputDevice(path) for path in list_devices()]
for dev in devices:
 if "Keyboard\"" in str(dev) and ' phys ' in str(dev):
  keyboard = dev
  break

# Подписываемся на события
for event in keyboard.read_loop():
 if event.type == ecodes.EV_KEY:
   key_event = categorize(event)
   if key_event.keystate == key_event.key_down:
     # Получаем название клавиши и преобразуем его
    key_name = key_event.keycode
    simple_name = simple_key_map.get(key_name, key_name)  # Если клавиша не в словаре, оставляем как есть
    print(simple_name)
    break
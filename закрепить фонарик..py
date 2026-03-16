from pynput import keyboard as pynput_keyboard
import threading
from pynput import keyboard
from pynput.keyboard import Key, Controller

kb = Controller()
holding = False

def toggle_num3():
    global holding
    if not holding:
        kb.press('3')           # Удерживаем '3' на цифровой клавиатуре
        holding = True
        print("Num3 удерживается")
    else:
        kb.release('3')
        holding = False
        print("Num3 отпущена")

def on_press(key):
    print(key)
    try:
        if 'c' in str(key):
         print("1")
         toggle_num3()
    except AttributeError:
        pass

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()
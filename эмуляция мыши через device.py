import evdev
# Для перехвата событий мыши в Linux можно использовать библиотеку evdev. Она позволяет работать с устройствами ввода,
# такими как мыши, клавиатуры, джойстики и другие.

import subprocess
from evdev import InputDevice, ecodes
import select, uinput

events = ( uinput.BTN_LEFT, uinput.BTN_RIGHT, uinput.REL_X, uinput.REL_Y,  uinput.REL_WHEEL
  , uinput.KEY_A, uinput.KEY_B, uinput.KEY_C, uinput.KEY_D, uinput.KEY_E, uinput.KEY_F, uinput.KEY_G, uinput.KEY_H, uinput.KEY_I,
    uinput.KEY_J, uinput.KEY_K, uinput.KEY_L, uinput.KEY_M, uinput.KEY_N, uinput.KEY_O, uinput.KEY_P, uinput.KEY_Q, uinput.KEY_R,
    uinput.KEY_S, uinput.KEY_T, uinput.KEY_U, uinput.KEY_V, uinput.KEY_W, uinput.KEY_X, uinput.KEY_Y, uinput.KEY_Z,
    uinput.KEY_SPACE, uinput.KEY_LEFTCTRL, uinput.KEY_LEFTALT, uinput.KEY_RIGHTALT, uinput.KEY_RIGHTCTRL, uinput.KEY_LEFTSHIFT,
    uinput.KEY_RIGHTSHIFT, uinput.KEY_1, uinput.KEY_2, uinput.KEY_3, uinput.KEY_4, uinput.KEY_5, uinput.KEY_6, uinput.KEY_7,
    uinput.KEY_8, uinput.KEY_9, uinput.KEY_0, uinput.KEY_MINUS, uinput.KEY_EQUAL, uinput.KEY_LEFTBRACE, uinput.KEY_RIGHTBRACE,
    uinput.KEY_SEMICOLON, uinput.KEY_APOSTROPHE, uinput.KEY_GRAVE, uinput.KEY_BACKSLASH, uinput.KEY_COMMA, uinput.KEY_DOT,
    uinput.KEY_SLASH, uinput.KEY_ENTER, uinput.KEY_KPENTER, uinput.KEY_TAB, uinput.KEY_BACKSPACE, uinput.KEY_ESC,
    uinput.KEY_INSERT, uinput.KEY_DELETE, uinput.KEY_PAGEUP, uinput.KEY_PAGEDOWN, uinput.KEY_HOME, uinput.KEY_END,
    uinput.KEY_UP, uinput.KEY_DOWN, uinput.KEY_LEFT, uinput.KEY_RIGHT, uinput.KEY_CAPSLOCK, uinput.KEY_NUMLOCK,
    uinput.KEY_SCROLLLOCK, uinput.KEY_F1, uinput.KEY_F2, uinput.KEY_F3, uinput.KEY_F4, uinput.KEY_F5, uinput.KEY_F6,
    uinput.KEY_F7, uinput.KEY_F8, uinput.KEY_F9, uinput.KEY_F10, uinput.KEY_F11, uinput.KEY_F12, uinput.KEY_KP0,
    uinput.KEY_KP1, uinput.KEY_KP2, uinput.KEY_KP3, uinput.KEY_KP4, uinput.KEY_KP5, uinput.KEY_KP6, uinput.KEY_KP7,
    uinput.KEY_KP8, uinput.KEY_KP9, uinput.KEY_KPMINUS, uinput.KEY_KPPLUS, uinput.KEY_KPDOT, uinput.KEY_KPCOMMA,
    uinput.KEY_KPSLASH, uinput.KEY_KPEQUAL, uinput.KEY_KPASTERISK, uinput.KEY_PAUSE)
script = '''#!/bin/bash
#gnome-terminal -- bash -c 'echo "1" | 
sudo -S chown root:input /dev/uinput;
sudo chmod g+rw /dev/uinput;
sudo usermod -a -G input egor;
sudo chown root:input /dev/uinput;
for i in {0..16}; do
    sudo chmod a+rw /dev/input/event$i
done
exit'''
subprocess.call(['bash', '-c', script])
# Выполнение команды и захват вывода
number =0
for i in range(1,9):
 dev1 = InputDevice('/dev/input/event{}'.format(i))
 s=str(dev1.name)
 if s== "USB OPTICAL MOUSE ":
  number=i
  break
dev = InputDevice('/dev/input/event{0}'.format(number))# открываем устройство мыши
# подписываемся на события # dev.grab()

device = uinput.Device(events)
keys_dict = {
 "a": uinput.KEY_A, "A": uinput.KEY_A, "b": uinput.KEY_B, "B": uinput.KEY_B, "c": uinput.KEY_C, "C": uinput.KEY_C,
    "d": uinput.KEY_D, "D": uinput.KEY_D, "e": uinput.KEY_E, "E": uinput.KEY_E, "f": uinput.KEY_F, "F": uinput.KEY_F, "g": uinput.KEY_G, "G": uinput.KEY_G, "h": uinput.KEY_H, "H": uinput.KEY_H, "i": uinput.KEY_I, "I": uinput.KEY_I, "j": uinput.KEY_J, "J": uinput.KEY_J, "k": uinput.KEY_K, "K": uinput.KEY_K, "l": uinput.KEY_L, "L": uinput.KEY_L, "m": uinput.KEY_M, "M": uinput.KEY_M, "n": uinput.KEY_N, "N": uinput.KEY_N, "o": uinput.KEY_O, "O": uinput.KEY_O, "p": uinput.KEY_P, "P": uinput.KEY_P, "q": uinput.KEY_Q, "Q": uinput.KEY_Q, "r": uinput.KEY_R, "R": uinput.KEY_R, "s": uinput.KEY_S, "S": uinput.KEY_S, "t": uinput.KEY_T, "T": uinput.KEY_T, "u": uinput.KEY_U, "U": uinput.KEY_U, "v": uinput.KEY_V, "V": uinput.KEY_V, "w": uinput.KEY_W, "W": uinput.KEY_W, "x": uinput.KEY_X, "X": uinput.KEY_X, "y": uinput.KEY_Y, "Y": uinput.KEY_Y, "z": uinput.KEY_Z, "Z": uinput.KEY_Z,
 "а": uinput.KEY_F, "А": uinput.KEY_F, "б": uinput.KEY_B, "Б": uinput.KEY_B, "в": uinput.KEY_D, "В": uinput.KEY_D, "г": uinput.KEY_U, "Г": uinput.KEY_U, "д": uinput.KEY_L, "Д": uinput.KEY_L, "е": uinput.KEY_T, "Е": uinput.KEY_T, "ё": uinput.KEY_GRAVE, "Ё": uinput.KEY_GRAVE, "ж": uinput.KEY_SEMICOLON, "Ж": uinput.KEY_SEMICOLON, "з": uinput.KEY_P, "З": uinput.KEY_P, "и": uinput.KEY_B, "И": uinput.KEY_B, "й": uinput.KEY_J, "Й": uinput.KEY_J, "к": uinput.KEY_R, "К": uinput.KEY_R, "л": uinput.KEY_K, "Л": uinput.KEY_K, "м": uinput.KEY_V, "М": uinput.KEY_V, "н": uinput.KEY_Y, "Н": uinput.KEY_Y, "о": uinput.KEY_J, "О": uinput.KEY_J, "п": uinput.KEY_G, "П": uinput.KEY_G, "р": uinput.KEY_H, "Р": uinput.KEY_H, "с": uinput.KEY_C, "С": uinput.KEY_C, "т": uinput.KEY_N, "Т": uinput.KEY_N, "у": uinput.KEY_E, "У": uinput.KEY_E, "ф": uinput.KEY_A,

    "Ф": uinput.KEY_A, "х": uinput.KEY_LEFTBRACE, "Х": uinput.KEY_LEFTBRACE,

    "ц": uinput.KEY_S, "Ц": uinput.KEY_S, "ч": uinput.KEY_M, "Ч": uinput.KEY_M, "ш": uinput.KEY_I, "Ш": uinput.KEY_I, "щ": uinput.KEY_O,

    "Щ": uinput.KEY_O,  "ъ": uinput.KEY_RIGHTBRACE, "Ъ": uinput.KEY_RIGHTBRACE,
    "ы": uinput.KEY_X, "Ы": uinput.KEY_X, "ь": uinput.KEY_APOSTROPHE, "Ь": uinput.KEY_APOSTROPHE, "э": uinput.KEY_BACKSLASH,
    "Э": uinput.KEY_BACKSLASH, "ю": uinput.KEY_DOT, "Ю": uinput.KEY_DOT, "я": uinput.KEY_Z, "Я": uinput.KEY_Z
}
def press_keys(device, text):
  for char in text:
   if char.isalpha():
    print(char)
    device.emit(keys_dict[str(char)], 1)  # эмуляция нажатия клавиши
    device.emit(keys_dict[str(char)], 0)  # эмуляция отпускания клавиши
  # elif char.isspace():    #     device1.emit(uinput.KEY_SPACE, 1)
  #     device1.emit(uinput.KEY_SPACE, 0)
# читаем события мыши без блокировки
# создаем виртуальное устройство ввода
while True:
  r, w, x = select.select([dev], [], [], 0.1)
  if dev in r:
   for event in dev.read():
     if event.code== 276:
      print("button 1")
      dev.grab()

      # эмулируем колесико мыши вверх
      # device.emit(uinput.REL_WHEEL, 2)   # разблокируем оригинальный ввод событий мыши
      press_keys(device, "w")
      dev.ungrab()
     if event.code== 275:
      print("button 2")

 # print(s)#
 # print(i)
# input()
 # print(dev.phys)
# print(number)
'''
Чтобы заблокировать оригинальный ввод событий мыши и эмулировать колесико мыши вверх при нажатии определенной кнопки,
 можно воспользоваться модулем uinput.

Пример кода для блокировки событий мыши и эмуляции колесика мыши вверх при нажатии кнопки 1 (код кнопки 276):

import uinput
from evdev import InputDevice, ecodes

# выбираем устройство ввода мыши
dev = InputDevice('/dev/input/mice')

# создаем виртуальное устройство ввода
events = (
    uinput.BTN_LEFT,
    uinput.BTN_RIGHT,
    uinput.REL_X,
    uinput.REL_Y,
    uinput.REL_WHEEL,
)
device = uinput.Device(events)

# читаем события мыши и эмулируем колесико мыши
for event in dev.read():
    if event.type == ecodes.EV_KEY and event.code == 276:
        # блокируем оригинальный ввод событий мыши
        dev.grab()
        # эмулируем колесико мыши вверх
        device.emit(uinput.REL_WHEEL, 1)
    elif event.type == ecodes.EV_KEY and event.code == 277:
        # разблокируем оригинальный ввод событий мыши
        dev.ungrab()
    else:
        # передаем оригинальные события мыши
        device.emit(event.type, event.code, event.value)
В этом примере мы используем модуль uinput для создания виртуального устройства ввода, 
которое будет эмулировать события мыши. Мы создаем виртуальное устройство, которое будет имитировать левую и правую кнопки мыши, 
перемещение мыши по осям X и Y, а также колесико мыши.

Затем мы читаем события из оригинального устройства ввода мыши (dev.read()) и проверяем, была ли нажата кнопка 1 (код кнопки 276). Если кнопка 1 была нажата, мы блокируем оригинальный ввод событий мыши (dev.grab()) и эмулируем колесико мыши вверх (device.emit(uinput.REL_WHEEL, 1)).

Если кнопка 2 (код кнопки 277) была нажата, мы разблокируем оригинальный ввод событий мыши (dev.ungrab()).
м
Если ни одна из кнопок не была нажата, мы передаем оригинальные события мыши в виртуальное устройство (device.emit(event.type, event.code, event.value)).

Таким образом, мы можем блокировать оригинальный ввод событий мыши и эмулировать колесико мыши вверх при нажатии определенной кнопки.
'''
























            # обрабатываем событие мыши
            # if event.type == ecodes.EV_REL:
            #     if event.code == ecodes.REL_X:
            #         print('Mouse moved X:', event.value)
            #     elif event.code == ecodes.REL_Y:
            #         print('Mouse moved Y:', event.value)
            # elif event.type == ecodes.EV_KEY:
            #     if event.code == ecodes.BTN_LEFT:
                    # if event.value == 1:
                    #     print('Left button pressed')
                    # elif event.value == 0:
                    #     print('Left button released')

#
# В этом примере мы используем функцию `select()` для чтения событий мыши без блокировки. Функция `select()` ожидает, пока появятся данные для чтения в устройстве ввода, и затем возвращает список устройств, готовых для чтения.
#
# Если в списке есть устройство ввода мыши (`dev`), мы читаем события из него и обрабатываем их. В случае событий `EV_REL` мы выводим, насколько переместилась мышь по X и Y. В случае событий `EV_KEY` мы выводим, была ли нажата или отпущена левая кнопка мыши.
#
# Таким образом, мы можем читать события мыши без блокировки и обрабатывать их в реальном времени.
# while True:
#     r, _, _ = select.select([dev.fd], [], [], 10)
#     if r:
#       for event in dev.read():
#        print(event)
       # if event.type == ecodes.code:
       #  print("event")
# читаем события в бесконечном цикле
# for event in dev.read_loop():
#     print(event)
    # обработка событий мыши здесь
    # if event.type == ecodes.EV_REL:
    #     # движение мыши
    #     if event.code == ecodes.REL_X:
    #         # обработка движения по оси X
    #     elif event.code == ecodes.REL_Y:
    #         # обработка движения по оси Y
    # if event.type == ecodes.EV_KEY:   # нажатие клавиши мыши
    #     print("mouse")
        # if event.code == ecodes.BTN_LEFT:
        #     # обработка нажатия левой кнопки мыши
        # elif event.code == ecodes.BTN_RIGHT:
        #     # обработка нажатия правой кнопки мыши


# Здесь мы используем метод `read_loop()`, который блокирует выполнение программы, пока не произойдет
# новое событие на устройстве. Мы обрабатываем движение мыши по осям X и Y, а также нажатия левой и правой кнопок мыши.
#
# Кроме evdev, можно также использовать библиотеку uinput, чтобы эмулировать события мыши и клавиатуры.
# Она позволяет создавать виртуальные устройства ввода, которые затем можно использовать для переназначения действий.
# Но для перехвата событий мыши на низком уровне evdev будет наиболее удобным выбором.


# from pynput.keyboard import Key, Controller
# import time
# import KeyboardLayout
#
#
# layout = KeyboardLayout('ru')# создание объекта клавиатуры с раскладкой "ru"
# keyboard = Controller(layout=layout)
#
# word_text = "у вас есть "# эмуляция ввода текста на русском языке
#
# for i in word_text:
#     i=str(i)
#     keyboard.press(i)
#     keyboard.release(i)
#     time.sleep(1.3)

# import subprocess as sbp
# import pip
# pkgs = eval(str(sbp.run("pip3 list -o --format=json", shell=True,          stdout=sbp.PIPE).stdout, encoding='utf-8'))
# for pkg in pkgs:
#     sbp.run("pip install --upgrade " + pkg['name'], shell=True)



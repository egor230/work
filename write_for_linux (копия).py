import evdev, time, select, uinput, subprocess, glob
from evdev import InputDevice, ecodes


events = ( uinput.KEY_LEFTCTRL,
    uinput.KEY_A)
global device
event_devices = 0
number=0
for device in glob.glob("/dev/input/event*"):
    event_devices += 1
script = '''#!/bin/bash
gnome-terminal -- bash -c 'echo "1" | sudo -S chown root:input /dev/uinput;
sudo chmod g+rw /dev/uinput;
sudo usermod -a -G input egor;
sudo chown root:input /dev/uinput;
for i in {0..event_devices}
do
    sudo chmod a+rw /dev/input/event$i
done
'
'''
subprocess.call(['bash', '-c', script])
devices = []
for i in range(0,event_devices):
 dev1 = InputDevice('/dev/input/event{}'.format(i))
 s=str(dev1.name) # print(i)

 if s== "Logitech Logitech USB Keyboard":
  number=i
  break
dev = InputDevice('/dev/input/event{}'.format(number))# открываем устройство клавиатуры
device = uinput.Device(events)# подписываемся на события # dev.grab()

time.sleep(0.8)
device.emit(uinput.KEY_LEFTCTRL, 1)
device.emit(uinput.KEY_LEFTCTRL, 0)  # создаем виртуальное устройство ввода
time.sleep(0.8)
device.emit(uinput.KEY_LEFTCTRL, 1)
device.emit(uinput.KEY_LEFTCTRL, 0)  # создаем виртуальное устройство ввода




















test = "Вот текст, в котором есть все буквы английского и русского алфавитов и который несёт какой-то смысл текст, в " \
           "A jumbled wizzard slyly used hexing potions. Без забот бродил по полю ёж, щипля травку и пчёл. " \
           "Ёж остановился, и ветер воет во тьме, пока луна светит над ёжом одиноким.Вдруг крик взлетел высоко в небеса! " \
           "Ёж увидел фею, нимфу во сне. Quickly jumped the hedgehog to see the fairy. Она была мала, как звук колокольчика," \
           " но о, так светилась, что озарила всё вокруг. Крохотная фея озарила ёжа своим светом и улыбнулась ему. И" \
           " ёж почувствовал себя счастливым. В этом тексте есть история о еже, который встретил фею. Повествование переходит " \
           "с английского на русский язык, чтобы передать атмосферу. Текст содержит все буквы русского и английского алфавитов."
# input()
# press_keys( test)
# input()




# while True:
#   r, w, x = select.select([dev], [], [], 0.1)
#   if dev in r:
#     for event in dev.read():
#      if event.code== 276:
#       print("button 1")
#       dev.grab()
#
#       # эмулируем колесико мыши вверх
#       device.emit(uinput.REL_WHEEL, 2)   # разблокируем оригинальный ввод событий мыши
#       dev.ungrab()
#       if event.code== 275:
#        print("button 2")












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
# "DELETE": 0x2E  "SEPARATOR": 0x6C,  0x6C на 0x2E
KEYS = {"LBUTTON": 0x01, "RBUTTON": 0x02, "CANCEL": 0x03, "MBUTTON": 0x04, "XBUTTON1": 0x05,
              "XBUTTON2": 0x06, "BACK": 0x08, "TAB": 0x09, "CLEAR": 0x0C, "RETURN": 0x0D,
              "SHIFT": 0x10, "CONTROL": 0x11, "MENU": 0x12, "PAUSE": 0x13, "CAPITAL": 0x14,
              "KANA": 0x15, "JUNJA": 0x17, "FINAL": 0x18, "KANJI": 0x19, "ESCAPE": 0x1B,
              "CONVERT": 0x1C, "NONCONVERT": 0x1D, "ACCEPT": 0x1E, "MODECHANGE": 0x1F, "SPACE": 0x20,
              "PRIOR": 0x21, "NEXT": 0x22, "END": 0x23, "HOME": 0x24, "LEFT": 0x25, "UP": 0x26,
              "RIGHT": 0x27, "DOWN": 0x28, "SELECT": 0x29, "PRINT": 0x2A, "EXECUTE": 0x2B,
              "SNAPSHOT": 0x2C, "INSERT": 0x2D, "DELETE": 0x2E, "HELP": 0x2F, "KEY0": 0x30,
              "KEY1": 0x31, "KEY2": 0x32, "key3": 0x33, "key4": 0x34, "key5": 0x35, "key6": 0x36,
              "key7": 0x37, "key8": 0x38, "key9": 0x39, "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44,
              "E": 0x45, "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49,
              "J": 0x4A, "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F, "P": 0x50, "Q": 0x51, "R": 0x52,
              "S": 0x53, "T": 0x54, "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59,
              "Z": 0x5A, "LWIN": 0x5B, "RWIN": 0x5C, "APPS": 0x5D, "SLEEP": 0x5F, "NUMPAD0": 0x60, "NUMPAD1": 0x61,
              "NUMPAD2": 0x62, "NUMPAD3": 0x63, "NUMPAD4": 0x64, "NUMPAD5": 0x65,
              "NUMPAD6": 0x66, "NUMPAD7": 0x67, "NUMPAD8": 0x68, "NUMPAD9": 0x69, "MULTIPLY": 0x6A, "ADD": 0x6B,
              "SEPARATOR": 0x6C, "SUBTRACT": 0x6D, "DECIMAL": 0x6E, "DIVIDE": 0x6F, "F1": 0x70, "F2": 0x71,
              "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
              "F11": 0x7A, "F12": 0x7B, "F13": 0x7C, "F14": 0x7D,
              "F15": 0x7E, "F16": 0x7F, "F17": 0x80, "F18": 0x81, "F19": 0x82, "F20": 0x83, "F21": 0x84,
              "F22": 0x85, "F23": 0x86, "F24": 0x87, "NUMLOCK": 0x90, "SCROLL": 0x91, "OEM_FJ_JISHO": 0x92, "OEM_FJ_MASSHOU": 0x93,
              "OEM_FJ_TOUROKU": 0x94, "OEM_FJ_LOYA": 0x95, "OEM_FJ_ROYA": 0x96, "LSHIFT": 0xA0, "RSHIFT": 0xA1, "LCONTROL": 0xA2, "RCONTROL": 0xA3, "LMENU": 0xA4, "RMENU": 0xA5, "BROWSER_BACK": 0xA6,
              "BROWSER_FORWARD": 0xA7, "BROWSER_REFRESH": 0xA8, "BROWSER_STOP": 0xA9, "BROWSER_SEARCH": 0xAA, "BROWSER_FAVORITES": 0xAB, "BROWSER_HOME": 0xAC, "VOLUME_MUTE": 0xAD, "VOLUME_DOWN": 0xAE,
              "VOLUME_UP": 0xAF, "MEDIA_NEXT_TRACK": 0xB0, "MEDIA_PREV_TRACK": 0xB1, "MEDIA_STOP": 0xB2, "MEDIA_PLAY_PAUSE": 0xB3, "LAUNCH_MAIL": 0xB4, "LAUNCH_MEDIA_SELECT": 0xB5, "LAUNCH_APP1": 0xB6,
              "LAUNCH_APP2": 0xB7, "OEM_1": 0xBA, "OEM_PLUS": 0xBB, "OEM_COMMA": 0xBC, "OEM_MINUS": 0xBD, "OEM_PERIOD": 0xBE, " OEM_2": 0xBF, "OEM_3": 0xC0, "ABNT_C1": 0xC1, "ABNT_C2": 0xC2, "OEM_4": 0xDB, "OEM_5": 0xDC, "OEM_6": 0xDD, "OEM_7": 0xDE, "OEM_8": 0xDF, "OEM_AX": 0xE1,
              "OEM_102": 0xE2, "ICO_HELP": 0xE3, "PROCESSKEY": 0xE5, "ICO_CLEAR": 0xE6, "PACKET": 0xE7, "OEM_RESET": 0xE9, "OEM_JUMP": 0xEA, "OEM_PA1": 0xEB, "OEM_PA2": 0xEC, "OEM_PA3": 0xED,
              "OEM_WSCTRL": 0xEE, "OEM_CUSEL": 0xEF, "OEM_ATTN": 0xF0, "OEM_FINISH": 0xF1, "OEM_COPY": 0xF2, "OEM_AUTO": 0xF3, "OEM_ENLW": 0xF4, "OEM_BACKTAB": 0xF5, "ATTN": 0xF6, "CRSEL": 0xF7, "EXSEL": 0xF8, " EREOF": 0xF9, "PLAY": 0xFA, "ZOOM": 0xFB, "PA1": 0xFD, " OEM_CLEAR": 0xFE
              }
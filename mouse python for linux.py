import evdev, time, select, uinput, subprocess, Xlib.display, glob
# Для перехвата событий мыши в Linux можно использовать библиотеку evdev. Она позволяет работать с устройствами ввода,
# такими как мыши, клавиатуры, джойстики и другие.
from evdev import InputDevice, ecodes

event_devices = 0
for device in glob.glob("/dev/input/event*"):
    event_devices += 1
number=0

script = '''#!/bin/bash
gnome-terminal -- bash -c 'echo "1" | sudo -S chown root:input /dev/uinput;
sudo chmod g+rw /dev/uinput;
sudo usermod -a -G input egor;
sudo chown root:input /dev/uinput;
for i in {0..event_devices}  
do
    sudo chmod a+rw /dev/input/event$i
done
exit'
'''
subprocess.call(['bash', '-c', script])
for i in range(1,event_devices):
 dev1 = InputDevice('/dev/input/event{}'.format(i))
 s=str(dev1.name)
 # print(dev1.name)
 if s== "USB OPTICAL MOUSE ":  # print(dev1.name)  #
  print(i)
  number=i
  break
dev = InputDevice('/dev/input/event{}'.format(number))# открываем устройство мыши
events = ( uinput.BTN_LEFT,   uinput.BTN_RIGHT,
    uinput.REL_X,    uinput.REL_Y,    uinput.REL_WHEEL,

    uinput.KEY_A, uinput.KEY_B, uinput.KEY_C, uinput.KEY_D, uinput.KEY_E, uinput.KEY_F, uinput.KEY_G, uinput.KEY_H, uinput.KEY_I,
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
    uinput.KEY_KPSLASH, uinput.KEY_KPEQUAL, uinput.KEY_KPASTERISK, uinput.KEY_PAUSE
)# подписываемся на события # dev.grab()
import pyautogui

import threading


class Job(threading.Thread):

  def __init__(self, swit, *args, **kwargs):
    self.swit = swit
    super(Job, self).__init__(*args, **kwargs)
    self.__flag = threading.Event()  # The flag used to pause the thread
    self.__flag.set()  # Set to True
    self.__running = threading.Event()  # Used to stop the thread identification

    self.__running.set()  # Set running to True

  def run(self):
    while self.__running.isSet():
      self.__flag.wait()  # return immediately when it is True, block until the internal flag is True when it is False
      pyautogui.scroll(self.swit)
  def pause(self):
    self.__flag.clear()  # Set to False to block the thread

  def resume(self):
    self.__flag.set()  # Set to True, let the thread stop blocking

  def stop(self):
    self.__flag.set()  # Resume the thread from the suspended state, if it is already suspended
    self.__running.clear()  # Set to False


a1 = Job(1)
a2 = Job(-1)
a1.start()
a1.pause()
a2.start()
a2.pause()
from pynput import *
from pynput import keyboard, mouse
mouse_ = mouse.Controller()
button = mouse.Button
scrol= mouse.Events
def on_click(x, y, button, pressed):
  print(button.name)
  if  pressed== False:
   a1.pause()
   a2.pause()
  if button.name == "button10" and pressed:
    a1.resume()
  if button.name == "button11" and pressed:
    a2.resume()

device = uinput.Device(events)# создаем виртуальное устройство ввода
while True:
  with mouse.Listener(
      on_click=on_click
  ) as listener:
    listener.join()
  # r, w, x = select.select([dev], [], [], 0.5)
  # if dev in r:
  #   for event in dev.read():    #
     # print(event.code)
     # a(event.code)
     # if event.code== 276:
     #  print("button 1")
      # dev.grab()    # эмулируем колесико мыши вверх


      # Эмулируем прокрутку колесика мыши вниз
      # pyautogui.scroll(1)
      # device.emit(uinput.REL_WHEEL, 1)   # разблокируем оригинальный ввод событий мыши
      # dev.ungrab()
     # if event.code== 275:
       # print("button 2")
       # dev.grab()    # эмулируем колесико мыши вниз
       # pyautogui.scroll(-1)
       # device.emit(uinput.REL_WHEEL, -1)   # разблокируем оригинальный ввод событий мыши
       # dev.ungrab()
import time

import pyautogui
from pynput.keyboard import Key, Controller
from pynput import *

t=0
def on_press(key):#обработчик клави.
 key=str(key).replace(" ","").replace("\'","") #  print(key)
 #key=trans(key)
 global t
 try:
   if key=="е":
     # if t==0:
     #   t=1
     print(key)
     pyautogui.mouseDown(button='right')
     #   time.sleep(3)
   if key == "я":
       print("re")
       # Отпускаем правую кнопку мыши
       pyautogui.mouseUp(button='right')
       t=0
   # print(t)
 except Exception as ex:  # clean_label(root)  #
    print(ex)
    return True
def on_release(key):
 pass# Collect events until released

listener = keyboard.Listener(  on_press=on_press,   on_release=on_release)
listener.start()
while 1:
  pass
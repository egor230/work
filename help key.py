from pynput import *
import time, threading, subprocess, os
from pynput.keyboard import Controller

class save_key:

 def __init__(self):
  self.flag = True
  self.swit = False

 def get_swit(self):
  return self.swit

 def set_swit(self, value):
  self.swit = value

 def get_flag(self):
  return self.flag

 def set_flag(self, value):
  self.flag = value
k= save_key()
def show_hints(key):
 k.set_swit(True)
 script = '''#!/bin/bash
 xdotool keyup {0} ; 
 xdotool keydown {0} ;

 '''.format(key)  # Исправлено: передаем key дважды
 subprocess.call(['bash', '-c', script])
    # done;
 #fi;f
 # xdotool keyup {0} ;
 print(key)
 # time.sleep(5)M:::::::::::LLLL
 k.set_flag(False)
 print(key)
def on_press(key):#обработчик клави.
 pass
def on_release(key):
 key=str(key).replace(" ","").replace("\'","").replace("Key.","")
 # print(key)
 try:
  if key=='<65032>' and k.get_flag()==True and k.get_swit() == False :
   key='Shift_L'   # k.set_flag(False)
   thread = threading.Thread(target=show_hints, args=(key,))   # Запускаем поток
   thread.start()
   return True
  else:
   if k.get_flag()==False:
    k.set_flag(True)
    key = 'Shift_L'
    script = '''#!/bin/bash
    xdotool keyup {0} ; 
    xdotool keydown {0} ;

    xdotool keyup {0} ; 
    '''.format(key)  # Исправлено: передаем key дважды
    subprocess.call(['bash', '-c', script])
    k.set_swit(False)
 except Exception as ex:
    return True

listener = keyboard.Listener(  on_press=on_press,   on_release=on_release)
listener.start()

while 1:
    pass
  # if key=='ctrl_r'and k.get_flag()==True :
  #  key='Control_R'
  #  thread = threading.Thread(target=show_hints, args=(key,))   # Запускаем поток
  #  thread.start()
  #  return True
  # if key=='Key.alt_r'and k.get_flag()==True :
  #  key='Alt_R'
  #  thread = threading.Thread(target=show_hints, args=(key,))   # Запускаем поток
  #  thread.start()
  #  return True


  # if key=='shift_r'  :
  #  key='Shift_R'
  #  thread = threading.Thread(target=show_hints, args=(key,))   # Запускаем поток
  #  thread.start()
  #  return True
  #
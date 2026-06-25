import pyautogui, threading, time, subprocess
from pynput import *
from pynput import keyboard, mouse
mouse_ = mouse.Controller()
button = mouse.Button
scrol= mouse.Events
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
      time.sleep(0.1)
  def pause(self):
    self.__flag.clear()  # Set to False to block the thread

  def resume(self):
    self.__flag.set()  # Set to True, let the thread stop blocking

  def stop(self):
    self.__flag.set()  # Resume the thread from the suspended state, if it is already suspended
    self.__running.clear()  # Set to False
script = '''#!/bin/bash
# Ищем идентификаторы процессов, содержащих слово "chrome"
pids=$(pgrep -f "mouse python scrol for linux")
# Перебираем найденные идентификаторы процессов и отправляем им сигнал завершения
for pid in $pids; do
    kill $pid
done
'''
# subprocess.call(['bash', '-c', script])
a1 = Job(1)
a2 = Job(-1)
a1.start()
a1.pause()
a2.start()
a2.pause()
def on_click(x, y, button, pressed):
  if  pressed== False:
   a1.pause()
   a2.pause()
  if button.name == "button10" and pressed:
    a1.resume()
  if button.name == "button11" and pressed:
    a2.resume()

while True:
  with mouse.Listener(
      on_click=on_click
  ) as listener:
    listener.join()
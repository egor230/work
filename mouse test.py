
import threading
from pynput import *
from pynput import keyboard, mouse
class Job(threading.Thread):

  def __init__(self, key, *args, **kwargs):
    self.key = key
    super(Job, self).__init__(*args, **kwargs)
    self.__flag = threading.Event()  # The flag used to pause the thread
    self.__flag.set()  # Set to True
    self.__running = threading.Event()  # Used to stop the thread identification

    self.__running.set()  # Set running to True

  def run(self):
    while self.__running.isSet():
      self.__flag.wait()  # return immediately when it is True, block until the internal flag is True when it is False

      # pyinput.keyDown(str(self.key).lower())

  def pause(self):
    self.__flag.clear()  # Set to False to block the thread

  def resume(self):
    self.__flag.set()  # Set to True, let the thread stop blocking

  def stop(self):
    self.__flag.set()  # Resume the thread from the suspended state, if it is already suspended
    self.__running.clear()  # Set to False


sw1 = False

# def a( key):  # print(key)
#     a1 = Job(key)
#     a1.start()
#     a1.pause()
#
#     global sw1
#     if str(button) == "Button.left" and pres == True and sw1 == False and mouse_button_1_flag == True:
#       a1.resume()
#       sw1 = True
#
#     if str(button) == "Button.left" and pres == True and sw1 == False and mouse_button_1_flag == True:
#       a1.pause()
#
#
mouse_ = mouse.Controller()
button = mouse.Button
scrol= mouse.Events
def on_click(x, y, button, pressed):
  if button.name==10 and pressed== True:
    pass
  # if button.name==10 and pressed== False:
  # if button.name==11 and pressed== True:
  # if button.name==11 and pressed== False:
  #   print(pressed)
  #   print(button.name)

def on_scroll(x, y, dx, dy):
 print(dx)

while 1:
  with mouse.Listener(
      on_click=on_click,on_scroll=on_scroll
  ) as listener:
    listener.join()

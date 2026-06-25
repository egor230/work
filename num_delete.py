import subprocess, threading, time, evdev, select, uinput, subprocess, glob
from evdev import InputDevice, ecodes

command = "xmodmap -e 'keycode 91 = 0x2E '"
subprocess.call(command, shell=True)# Функция, вызываемая при нажатии клавиши

global device
event_devices = 0
for device in glob.glob("/dev/input/event*"):
  event_devices += 1
script = '''#!/bin/bash
gnome-terminal -- bash -c 'echo "1" | sudo -S chown root:input /dev/uinput;
sudo chmod g+rw /dev/uinput;
current_user=$(whoami)
sudo usermod -a -G input $current_user;
sudo chown root:input /dev/uinput;
for i in {0..event_devices}
do
    sudo chmod a+rw /dev/input/event$i
done
'
'''
subprocess.call(['bash', '-c', script])

script = f'''#!/bin/bash
xte 'keydown Delete' 'keyup Delete'
'''
class Job(threading.Thread):

 def __init__(self, *args, **kwargs):
  super(Job, self).__init__(*args, **kwargs)
  self.__flag = threading.Event() # The flag used to pause the thread
  self.__flag.set() # Set to True
  self.__running = threading.Event() # Used to stop the thread identification
  self.__running.set() # Set running to True
 def run(self):
  time.sleep(0.01)
  while self.__running.isSet():
   self.__flag.wait() # return immediately when it is True, block until the internal flag is True when it is False
   subprocess.call(['bash', '-c', script, '_'])
   time.sleep(0.21)
 def pause(self):
  self.__flag.clear() # Set to False to block the thread
 def resume(self):
  self.__flag.set() # Set to True, let the thread stop blocking
a6 = Job()# эмулировать первую боковую кнопку
a6.start()
a6.pause()

devices = []
for i in range(0, event_devices):
  dev1 = InputDevice('/dev/input/event{}'.format(i))
  s = str(dev1.name)
  if 'Keyboard' in s:  # if s== "Logitech Logitech USB Keyboard":
    dev = InputDevice('/dev/input/event{}'.format(i))  # открываем устройство клавиатуры
    devices.append(dev)
    break

while True:
 try:
  for dev in devices:
    r, w, x = select.select([dev], [], [], 0.5)
    if dev in r:
     for event in dev.read():
       # # print(event.code)
         if event.value == 1 and event.code==83:
           # print(event.code)
           a6.resume()
         if event.value == 0 and event.code==83:
           a6.pause()
 except:
     pass


# def on_press(key):
#   key=str(key).replace(" ","") # print(key)
#   # Проверяем, является ли нажатая клавиша той, которую нужно отключить
#   if str(key) == "'.'":
#     a6.resume()    # print("p") # Нажатие клавиши "Delete"
#     # return False# Возвращаем False, чтобы игнорировать нажатие клавиши
#
# def on_release(key):
#     print("re")
#     a6.pause()    # Обработчик отпускания клавиши
#     # print("Клавиша отпущена:", key)
#     return True



# dev.ungrab()  # разблокируем устройство.
# time.sleep(0.01)
# # Создаем объект слушателя клавиатуры
# # Создание экземпляра слушателя клавиатуры
# listener = keyboard.Listener(
#     on_press=on_press,
#     on_release=on_release)
#
# # Запуск прослушивания клавиатуры в отдельном потоке
# listener.start()

# Ожидание завершения прослушивания
# listener.join()










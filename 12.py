# print(32)
import evdev, time, select, uinput, subprocess, Xlib.display, glob

from evdev import InputDevice, ecodes
import Xlib.display
from Xlib import X
# Подключаемся к оконной системе
# Получаем события от мыши
# mouse = disp.screen().root.query_pointer()
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
 if s== "USB OPTICAL MOUSE ":
  # print(dev1.name)
  # print(i)
  number=i
  break
 # print(dev.phys)
mouse = InputDevice('/dev/input/event{}'.format(number))  # Путь до мыши
while True:
 for event in mouse.read_loop():
  try:
   if event.type == evdev.ecodes.EV_KEY:
    print(event.code)

    # if event.code != 276:
    #  mouse.ungrab()
    # if event.code == 276:
    #  if event.value == 1:  # Нажатие
    #   mouse.grab()
    #   print("Заблокировано!")
    #  # pass  # Игнорируем
    #  if event.value == 0:  # Отпускание
    #   mouse.ungrab()
    if event.code != 275:
      mouse.ungrab()
    if event.code == 275:
     if event.value == 1:  # Нажатие
      mouse.grab()
      print("Button")
      # pass  # Игнорируем
     if event.value == 0:  # Отпускание
      mouse.ungrab()
   else:
    mouse.ungrab()
    # Обрабатываем нормально
  except:
   pass
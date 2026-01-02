import time, subprocess
from pynput import keyboard
from pynput.keyboard import Controller, Key
import evdev, time, select, uinput, subprocess, glob
from evdev import InputDevice, ecodes

events = ( uinput.KEY_W,)
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

controller = Controller()
w_pressed = False

def on_press(key):
 global w_pressed
 # ESC отпускает W
 if key == Key.esc and w_pressed:
  # subprocess.run(['xte', 'keyup w'])
  w_pressed = False

  device.emit(uinput.KEY_W, 0)
  return

 # Стрелка вверх нажимает W
 if key == Key.up and not w_pressed:
  # subprocess.run(['xte', 'keydown w'])
  w_pressed = True
  device.emit(uinput.KEY_W, 1)
  return

 # Стрелки влево/вправо/вниз
 if key == Key.down and w_pressed:
  device.emit(uinput.KEY_W, 0)
  # subprocess.run(['xte', 'keyup w'])
  w_pressed = False

def on_release(key):
 global w_pressed # Удаляем отпущенную стрелку
 if key == Key.down and not w_pressed:
  #subprocess.run(['xte', 'keydown w'])
  device.emit(uinput.KEY_W, 1)
  w_pressed = True
  # Если стрелок больше нет и W нажата
 # elif w_pressed:
 #  subprocess.run(['xte', 'keyup w'])
 #  w_pressed = False

print("Скрипт запущен. Логика:")
print("1. Нажатие ВВЕРХ → W нажата")
print("2. Нажатие ВЛЕВО/ВПРАВО/ВНИЗ → W отпущена")
print("3. Отпускание ВЛЕВО/ВПРАВО/ВНИЗ:")
print("   - Если осталась хотя бы одна стрелка → W нажата")
print("   - Если стрелок не осталось → W отпущена")
print("4. ESC → W отпущена")
print("5. Ctrl+C → выход")

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
 try:
  listener.join()
 except KeyboardInterrupt:
  print("\nСкрипт остановлен")
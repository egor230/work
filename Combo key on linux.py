#!/usr/bin/env python3
import subprocess

from pynput import keyboard, mouse
from threading import Event
import time

# Инициализация контроллера мыши
mouse_controller = mouse.Controller()
is_pressed = False
space_pressed = Event()
# s='''#!/bin/bash
# xte "keydown W"
# xte "keydown Shift_L"
# sleep 2.3
# xte "keydown ISO_Next_Group"
# sleep 1.3
# xte "keyup ISO_Next_Group"
# xte "keyup Shift_L"
# xte "keyup W"
# # xte "keydown E"
# # sleep 0.3
# # xte "keyup E"
# # xte "keydown R"
# # sleep 0.3
# # xte "keyup R"
# # xte "keydown F"
# # sleep 0.3
# # xte "keyup F
# "'''
s='''#!/bin/bash
xte "keydown Alt_L"
xte "keydown S"
sleep 9.3
xte "keyup S"
xte "keyup Alt_L"
"'''
def on_press(key):
  key = str(key).replace(" ", "").replace("\'", "").replace("Key.", "")
  print(f"Key pressed: {key}")
  try:
    keyboard_controller = KeyboardController()
    if key == 'i' or key == 'и':
      mouse_controller.press(Button.left)
      mouse_controller.press(Button.right)
      keyboard_controller.press('a')
      time.sleep(9)
      mouse_controller.release(Button.left)
      mouse_controller.release(Button.right)
      keyboard_controller.release('a')
      print("Left and right mouse buttons clicked and 'a' key pressed for 9 seconds.")
  except Exception as e:
    print(f"Error: {e}")
  finally:

      if 'keyboard_controller' in locals():
          del keyboard_controller

      print("Кнопки мыши отпущены")


def on_release(key):
  if key == keyboard.Key.esc:
    # Останавливаем слушатель при нажатии ESC
    if is_pressed:
      mouse_controller.release(mouse.Button.left)
      mouse_controller.release(mouse.Button.right)
    return False


# Настройка слушателя клавиатуры
with keyboard.Listener(
        on_press=on_press,
        on_release=on_release) as listener:
  print("Скрипт активирован. Нажмите SPACE для переключения, ESC для выхода")
  listener.join()

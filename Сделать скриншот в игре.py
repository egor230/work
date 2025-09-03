import subprocess, time, mss, cv2
from io import BytesIO
import cv2, numpy as np
from PIL import Image
from pynput import keyboard, mouse
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
from datetime import datetime
import numpy as np

def take_screenshot(save_path="screenshot.png"):
  try: #Определяем область экрана для захвата (весь экран)
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Основной монитор
        img = sct.grab(monitor) # Захватываем изображение
        img_np = np.array(img) # Преобразуем в массив NumPy для обработки
        # Преобразуем цветовую схему из BGRA в BGR
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        # Сохраняем скриншот на диск
        cv2.imwrite(save_path, img_bgr)
        # Читаем сохранённый файл как байты
  except Exception as e:
        print(f"Ошибка при создании скриншота: {e}")

def on_press(key):
 key = str(key).replace(" ", "").replace("\'", "").replace("Key.", "")
 print(f"Key pressed: {key}")
 try:
   keyboard_controller = KeyboardController()
   if key == 'o' or key == 'щ':
     now = datetime.now()
     current_date = now.strftime("%Y-%m-%d")
     current_time = now.strftime("%H-%M-%S")
     file_name_path = format("Screenshot {0} {1}.png".format( current_time,
       current_date))
     take_screenshot(file_name_path)  # Сделать скриншот игры
 except Exception as e:
   print(f"Error: {e}")
 finally:
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

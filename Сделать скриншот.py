import json, pyautogui, subprocess, time, os, sys
from PIL import ImageGrab
'''
Программа выполняет создание скриншота заданной области экрана, сохраняет его в файл и копирует в буфер обмена. 
Если существует файл настроек, программа использует его для определения области захвата; 
в противном случае использует заранее заданные размеры.
'''
def screenshot(left, top, width, height):
  # print(left, top, width, height, end=' ')
  time.sleep(0.6)
  # Делаем скриншот с заданными размерами и координатами
  screenshot = ImageGrab.grab(bbox=(left, top, left + width, top + height))

  temp_file_path = "/tmp/screenshot.png"  # Сохраняем изображение во временный файл
  screenshot.save(temp_file_path, format="PNG")

  time.sleep(0.1)  # Копируем изображение в буфер обмена с помощью xclip
  subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', temp_file_path])

  time.sleep(0.1)
  os.remove(temp_file_path)

def calculate_coordinates(begin_point, end_point):
    # Рассчитываем координаты top-left угла и размеры для скриншота
    left = min(begin_point.x(), end_point.x())
    top = min(begin_point.y(), end_point.y())
    width = abs(end_point.x() - begin_point.x())
    height = abs(end_point.y() - begin_point.y())
    return left, top,  width, height

def load_coordinates_from_json():
    # Путь к JSON файлу
    json_file_path = 'settings for screenshot.json'

    if os.path.exists(json_file_path):  #  Проверяем существует ли файл
      with open(json_file_path, 'r') as json_file:
        coords = json.load(json_file)

        # Присваиваем значения из словаря переменным
        left = int(coords['left'])
        top = int(coords['top'])
        width = int(coords['width'])
        height = int(coords['height'])
        screenshot(left, top, width, height) # Вызываем функцию скриншота с расчитанными параметрами
    else:
        # Задаем размеры скриншота
        top = int(130)
        left = int(110)
        width = 1530
        height = 910
        screenshot(left, top, width, height)

load_coordinates_from_json()


# Делаем скриншот с заданными размерами и координатами
# screenshot = pyautogui.screenshot(region=(left, top, width, height))
# # Помещаем скриншот в буфер обмена с помощью xclip
# subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png'], input=screenshot.tobytes())

# Выводим координаты в консоль
# print(f"Start point: {self.begin}, End point: {self.end}, Bbox: ({left}, {top}, {width}, {height})")

# Сохраняем скриншот
# screenshot.save("/home/egor/Рабочий стол/screenshot.png")
# script = f'''#!/bin/bash
# if ! dpkg -s xclip >/dev/null 2>&1; then
#     sudo apt-get install -y xclip;
# fi
# current_user=$(whoami);
# xclip -selection clipboard -t image/png -i "/home/$current_user/Рабочий стол/screenshot.png"
#
# '''
# subprocess.call(['bash', '-c', script])# xdg-open "/home/egor/Рабочий стол/screenshot.png"


# Задаем размеры скриншота
# top = int(130)
# left = int(110)
# width = 1530
# height = 910
#
# time.sleep(0.4)
# # Делаем скриншот с заданными размерами и координатами
# screenshot = ImageGrab.grab(bbox=(left, top, left + width, top + height))
#
# # Сохраняем изображение во временный файл
# temp_file_path = "/tmp/screenshot.png"
# screenshot.save(temp_file_path, format="PNG")
#
# time.sleep(0.1)
# # Копируем изображение в буфер обмена с помощью xclip
# subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', temp_file_path])
#
# time.sleep(0.1)
# os.remove(temp_file_path)
#print("Скриншот успешно скопирован в буфер обмена.")

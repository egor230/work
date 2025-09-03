import cv2, os, json
import numpy as np

def find_template(image_path, template_path, left, top, right, bottom, threshold=0.8):

  # Загрузка шаблона
  template = cv2.imread(template_path, cv2.IMREAD_COLOR)
  # Загрузка основного изображения
  screen = cv2.imread(image_path, cv2.IMREAD_COLOR)
  # Проверка, что координаты не выходят за пределы изображения
  height, width = screen.shape[:2]

  # Обрезка изображения по заданным координатам
  cropped = screen[top:bottom, left:right]

  # Проверка размеров шаблона и обрезанной области
  if cropped.shape[0] < template.shape[0] or cropped.shape[1] < template.shape[1]:
    print("Шаблон больше области поиска.")
    return False

  # Поиск шаблона в обрезанной области
  result = cv2.matchTemplate(cropped, template, cv2.TM_CCOEFF_NORMED)
  _, max_val, _, _ = cv2.minMaxLoc(result)

  # Проверка совпадения
  if max_val >= threshold:
    print(f"Эмблема найдена! Максимальное совпадение: {max_val:.2f}")
    return True

  print(f"Эмблема не найдена. Совпадение ниже порога ({max_val:.2f} < {threshold}).")
  return False

# Параметры
image_path = 'result.png'
template_path = 'Target_cropped.png'
json_path = 'Settings target.json'

# Загружаем параметры из JSON
with open(json_path, 'r') as f:
    crop_data = json.load(f)

left = crop_data['left']
top = crop_data['top']
right = crop_data['right']
bottom = crop_data['bottom']

# Цикл поиска
while True:
 if find_template(image_path, template_path, left, top, right, bottom):
  print("ok")
  break
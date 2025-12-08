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

def find_template_position(image_path, template_path, threshold=0.8):

  # Загрузка шаблона
  template = cv2.imread(template_path, cv2.IMREAD_COLOR)
  if template is None:
    print(f"Не удалось загрузить шаблон '{template_path}'")
    return None

  # Загрузка основного изображения
  screen = cv2.imread(image_path, cv2.IMREAD_COLOR)

  # Проверка размеров (шаблон не должен быть больше изображения)
  if screen.shape[0] < template.shape[0] or screen.shape[1] < template.shape[1]:
    print("Шаблон больше изображения.")
    return None

  # Поиск шаблона во всем изображении
  result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
  _, max_val, _, max_loc = cv2.minMaxLoc(result)

  # Проверка совпадения
  if max_val >= threshold:
    print(f"Эмблема найдена! Максимальное совпадение: {max_val:.2f}")

    # Вычисление координат обрезки на основе позиции совпадения
    left = max_loc[0]
    top = max_loc[1]
    right = left + template.shape[1]  # ширина шаблона
    bottom = top + template.shape[0]  # высота шаблона

    # Обрезка изображения по найденным координатам
    cropped = screen[top:bottom, left:right]

    # Сохранение обрезанной картинки
    cropped_path = 'new_cropped.png'
    cv2.imwrite(cropped_path, cropped)
    print(f"Обрезанная картинка сохранена как '{cropped_path}'")

    # Возврат параметров
    return {
      "left": left,
      "top": top,
      "right": right,
      "bottom": bottom
    }
  else:
    print(f"Эмблема не найдена. Совпадение ниже порога ({max_val:.2f} < {threshold}).")
    return None
# Параметры
image_path = 'result.png'
template_path = 'Target_cropped.png'
json_path = 'Settings target.json'

if os.path.exists(image_path):
  print("Параметры найдены, загружаем из JSON...")
  with open(json_path, 'r') as f:  # Загружаем параметры из JSON
    crop_data = json.load(f)
    left = crop_data['left']
    top = crop_data['top']
    right = crop_data['right']
    bottom = crop_data['bottom']
else: # Вызов функции
 crop_data = find_template_position(image_path, template_path)
 if crop_data is not None:
  print("Найденные параметры обрезки:", crop_data)
  left = crop_data['left']
  top = crop_data['top']
  right = crop_data['right']
  bottom = crop_data['bottom']

# Цикл поиска
while True:
 if find_template(image_path, template_path, left, top, right, bottom):
  print("ok")
  break
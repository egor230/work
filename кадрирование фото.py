from PIL import Image
import json

# Путь к JSON-файлу с параметрами
json_path = 'Settings target.json'

# Путь к изображению (оригинал, например, тот же, что использовался в GUI)
image_path = 'result.png'  # Замените на путь к вашему оригинальному изображению

# Загружаем параметры из JSON
with open(json_path, 'r') as f:
    crop_data = json.load(f)

left = crop_data['left']
top = crop_data['top']
right = crop_data['right']
bottom = crop_data['bottom']

# Открываем изображение
img = Image.open(image_path)

# Проверяем валидность координат
if right <= left or bottom <= top:
    raise ValueError("Некорректные параметры обрезки: итоговая ширина или высота <= 0.")

# Кадрируем изображение
cropped_img = img.crop((left, top, right, bottom))

# Сохраняем обрезанное изображение
cropped_img.save('Target_cropped.png')
print("Изображение успешно обрезано и сохранено как 'Target_cropped.png'!")
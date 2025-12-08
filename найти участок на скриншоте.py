import cv2
import os
import json
import sys
import subprocess
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"

def find_template_position(image_path, template_path, threshold=0.26):
 # Загрузка шаблона
 # Загрузка шаблона
 template = cv2.imread(template_path, cv2.IMREAD_COLOR)
 if template is None:
  print(f"Не удалось загрузить шаблон '{template_path}'")
  return None

 # Загрузка основного изображения
 screen = cv2.imread(image_path, cv2.IMREAD_COLOR)
 if screen is None:
  print(f"Не удалось загрузить изображение '{image_path}'")
  return None

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
 
  # Проверка границ изображения
  if right > screen.shape[1] or bottom > screen.shape[0]:
   print(f"Ошибка: Координаты обрезки выходят за пределы изображения: left={left}, top={top}, right={right}, bottom={bottom}")
   return None
 
  # Вычисление ширины и высоты для pyautogui
  width = right - left
  height = bottom - top
 
  # Обрезка изображения по найденным координатам
  cropped = screen[top:bottom, left:right]
 
  # Сохранение обрезанной картинки
  cropped_path = 'new_cropped.png'
  if not cv2.imwrite(cropped_path, cropped):
   print(f"Ошибка: Не удалось сохранить обрезанное изображение '{cropped_path}'")
   return None
  print(f"Обрезанная картинка сохранена как '{cropped_path}'")
 
  # Сохранение координат в JSON, включая width и height
  crop_data = {
   "left": left,
   "top": top,
   "right": right,
   "bottom": bottom,
   "width": width,
   "height": height
  }
  
  json_file_path = "Crode_image_settings.json"
  with open(json_file_path, 'w') as f:
   json.dump(crop_data, f, indent=2)
 else:
  print(f"Эмблема не найдена. Совпадение ниже порога ({max_val:.2f} < {threshold}).")
  return None

class ImageCropper(QWidget):
 def __init__(self):
  super().__init__()
  self.setWindowTitle("Image Cropper")
  self.setGeometry(650, 300, 550, 250)

  # Виджеты для выбора основного изображения
  self.image_label = QLabel("Image File:")
  self.image_path = QLineEdit()
  self.select_image_btn = QPushButton("Select Image File")
  self.select_image_btn.clicked.connect(self.select_image)

  # Виджеты для выбора шаблона
  self.template_label = QLabel("Template File:")
  self.template_path = QLineEdit()
  self.select_template_btn = QPushButton("Select Template File")
  self.select_template_btn.clicked.connect(self.select_template)

  # Кнопка для обработки
  self.process_btn = QPushButton("Process")
  self.process_btn.clicked.connect(self.process_image)

  # Лэйаут для строки ввода изображения
  image_layout = QHBoxLayout()
  image_layout.addWidget(self.image_path)
  image_layout.addWidget(self.select_image_btn)

  # Лэйаут для строки ввода шаблона
  template_layout = QHBoxLayout()
  template_layout.addWidget(self.template_path)
  template_layout.addWidget(self.select_template_btn)

  # Основной лэйаут
  layout = QVBoxLayout()
  layout.addWidget(self.image_label)
  layout.addLayout(image_layout)
  layout.addWidget(self.template_label)
  layout.addLayout(template_layout)
  layout.addWidget(self.process_btn)

  self.setLayout(layout)

 def select_image(self):
  cmd = ['zenity', '--file-selection', '--file-filter=Image files | *.jpg *.jpeg *.png *.gif *.bmp']
  try:
   result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True)
   file_path = result.stdout.strip()
   if file_path:
    self.image_path.setText(file_path)
  except subprocess.CalledProcessError:
   QMessageBox.warning(self, "Error", "Failed to select image file.")

 def select_template(self):
  cmd = ['zenity', '--file-selection', '--file-filter=Image files | *.jpg *.jpeg *.png *.gif *.bmp']
  try:
   result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True)
   file_path = result.stdout.strip()
   if file_path:
    self.template_path.setText(file_path)
  except subprocess.CalledProcessError:
   QMessageBox.warning(self, "Error", "Failed to select template file.")

 def process_image(self):
  image_file = self.image_path.text()
  template_file = self.template_path.text()
  if not image_file or not template_file:
   QMessageBox.warning(self, "Error", "Please select both image and template files.")
   return

  crop_data = find_template_position(image_file, template_file)
  if crop_data is None:
    QMessageBox.warning(self, "Error", "Template not found or processing failed.")

if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = ImageCropper()
 window.show()
 sys.exit(app.exec_())
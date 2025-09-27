import sys, os, subprocess, json
from PyQt5.QtWidgets import ( QApplication, QMainWindow, QLabel, QSlider, QPushButton,
  QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QFrame, QMessageBox)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt

class ImageCropper(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle("Image Cropper")
    self.setGeometry(160, 140, 1500, 750)
    self.central_widget = QWidget()  # Создаём центральный виджет окна
    self.setCentralWidget(self.central_widget)  # Устанавливаем центральный виджет в окно

    # Основной лэйаут (горизонтальный)
    self.main_layout = QHBoxLayout()
    self.main_layout.setSpacing(6)             # небольшое расстояние между панелями
    self.main_layout.setContentsMargins(6, 6, 6, 6)
    self.central_widget.setLayout(self.main_layout)

    # ---------------- Image display ----------------
    self.image_frame = QFrame()                # Рамка для отображения изображения
    self.image_frame_layout = QVBoxLayout()
    self.image_frame_layout.setSpacing(2)      # очень небольшие отступы внутри фрейма
    self.image_frame_layout.setContentsMargins(2, 2, 2, 2)
    self.image_frame.setLayout(self.image_frame_layout)

    self.image_label = QLabel()                # Метка для показа изображения
    self.image_label.setAlignment(Qt.AlignCenter)
    self.image_label.setScaledContents(True)   # изображение заполняет метку (растягивание)
    self.image_label.setSizePolicy(self.image_label.sizePolicy().Expanding, self.image_label.sizePolicy().Expanding)

    self.image_frame_layout.addWidget(self.image_label)
    self.main_layout.addWidget(self.image_frame, stretch=2)

    # ---------------- Sliders (компактно) ----------------
    self.sliders_frame = QFrame()
    self.sliders_layout = QVBoxLayout()
    self.sliders_layout.setSpacing(6)          # компактные вертикальные отступы
    self.sliders_layout.setContentsMargins(2, 2, 2, 2)
    self.sliders_frame.setLayout(self.sliders_layout)

    # Ограничиваем ширину панели слайдеров, чтобы она выглядела компактнее
    self.sliders_frame.setMaximumWidth(380)

    # helper: добавляем подпись и слайдер в одну строку (экономит вертикальное место)
    def add_compact_slider(label_text, slider_widget):
      row = QHBoxLayout()
      row.setSpacing(6)
      lbl = QLabel(label_text)
      lbl.setFixedWidth(90)   # фиксированная ширина подписи, чтобы всё ровно выстраивалось
      lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
      row.addWidget(lbl)
      row.addWidget(slider_widget)
      self.sliders_layout.addLayout(row)

    # Top crop slider
    self.top_slider = QSlider(Qt.Horizontal)
    self.top_slider.setMinimum(0)
    self.top_slider.setValue(0)
    self.top_slider.valueChanged.connect(self.update_crop)
    add_compact_slider("Top Crop:", self.top_slider)

    # Bottom crop slider
    self.bottom_slider = QSlider(Qt.Horizontal)
    self.bottom_slider.setMinimum(0)
    self.bottom_slider.setValue(0)
    self.bottom_slider.valueChanged.connect(self.update_crop)
    add_compact_slider("Bottom Crop:", self.bottom_slider)

    # Left crop slider
    self.left_slider = QSlider(Qt.Horizontal)
    self.left_slider.setMinimum(0)
    self.left_slider.setValue(0)
    self.left_slider.valueChanged.connect(self.update_crop)
    add_compact_slider("Left Crop:", self.left_slider)

    # Right crop slider
    self.right_slider = QSlider(Qt.Horizontal)
    self.right_slider.setMinimum(0)
    self.right_slider.setValue(0)
    self.right_slider.valueChanged.connect(self.update_crop)
    add_compact_slider("Right Crop:", self.right_slider)

    # Save button (оставляем как отдельный элемент, слегка выровнено по центру)
    self.save_button = QPushButton("Save Cropped Image")
    self.save_button.clicked.connect(self.save_image)
    # Обрамляем кнопку горизонтальным лэйаутом, чтобы она центрировалась
    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_row.addWidget(self.save_button)
    btn_row.addStretch(1)
    self.sliders_layout.addLayout(btn_row)

    # Добавляем фрейм слайдеров в основной лэйаут (без изменения логики растяжения)
    self.main_layout.addWidget(self.sliders_frame, stretch=1)

    # Сохранение оригиналов (логика не тронута)
    self.original_pixmap = None
    self.cropped_pixmap = None
    self.select_image()

  # --------- остальной функционал оставлен без изменений ----------
  def select_image(self):
    try:
      # file_path = "screenshot.png"
      cmd = ['zenity', '--file-selection', '--file-filter=Image files | *.jpg *.jpeg *.png *.gif *.bmp']
      result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True)
      file_path = result.stdout.strip()
      if file_path:
       if not self.is_image(file_path):
        QMessageBox.warning(self, "Invalid File", "Selected file is not a valid image.")
        self.select_image()
        return
      self.original_pixmap = QPixmap(file_path)
      if self.original_pixmap.isNull():
        QMessageBox.warning(self, "Error", "Could not load image.")
        return
      # Set max values to full image dimensions
      width = self.original_pixmap.width()
      height = self.original_pixmap.height()
      self.top_slider.setMaximum(height)
      self.bottom_slider.setMaximum(height)
      self.left_slider.setMaximum(width)
      self.right_slider.setMaximum(width)
      self.update_crop()
    except Exception as e:
      QMessageBox.critical(self, "Error", f"Failed to select image: {str(e)}")

  def is_image(self, file_path):
    valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')
    return file_path.lower().endswith(valid_extensions)

  def update_crop(self):
    if not self.original_pixmap:
      return
    left = self.left_slider.value()
    top = self.top_slider.value()
    right = self.right_slider.value()
    bottom = self.bottom_slider.value()
    width = self.original_pixmap.width() - left - right
    height = self.original_pixmap.height() - top - bottom
    if width <= 0 or height <= 0:
      QMessageBox.warning(self, "Invalid Crop", "Crop values would result in empty image. Resetting...")
      self.left_slider.setValue(0)
      self.right_slider.setValue(0)
      self.top_slider.setValue(0)
      self.bottom_slider.setValue(0)
      return
    cropped = self.original_pixmap.copy(left, top, width, height)
    self.cropped_pixmap = cropped
    # режим заполнения (без сохранения пропорций) — оставлен как в оригинале
    self.image_label.setPixmap(cropped.scaled(self.image_label.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

  def save_image(self):
   if not self.cropped_pixmap:
    QMessageBox.warning(self, "No Image", "No cropped image to save.")
    return
 
   file_path = "Target.png"
   if file_path:
    self.cropped_pixmap.save(file_path)
  
    # Получаем текущие значения слайдеров (отступы)
    top = self.top_slider.value()
    bottom = self.bottom_slider.value()
    left = self.left_slider.value()
    right = self.right_slider.value()
  
    # Вычисляем абсолютные координаты для bounding box
    width = self.original_pixmap.width()
    height = self.original_pixmap.height()
    box_left = left
    box_top = top
    box_right = width - right
    box_bottom = height - bottom
  
    # Проверяем, что итоговые размеры валидны
    if box_right <= box_left or box_bottom <= box_top:
     QMessageBox.warning(self, "Invalid Crop", "Crop values would result in empty image.")
     return
  
    # Сохраняем координаты bounding box в JSON
    crop_data = {
     "left": box_left,
     "top": box_top,
     "right": box_right,
     "bottom": box_bottom
    }
  
    base = os.path.splitext(file_path)[0]
    json_file_path = "Settings " + ".json"
    with open(json_file_path, 'w') as f:
     json.dump(crop_data, f, indent=2)
  def resizeEvent(self, event):
    super().resizeEvent(event)
    self.update_crop()

if __name__ == "__main__":
  app = QApplication(sys.argv)
  window = ImageCropper()
  window.show()
  sys.exit(app.exec_())

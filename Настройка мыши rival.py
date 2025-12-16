import json
import subprocess
import threading
import sys
import os
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QComboBox, QSlider, QPushButton


class MouseController(QWidget):
 _mutex = threading.Lock()  # Глобальный мьютекс на уровне класса

 def __init__(self):
  super().__init__()
  self.settings_file = "mouse_settings_for_rival.json"
  self.default_color = 'white'
  self.default_sensitivity = 800
  self.current_color = self.default_color
  self.current_sensitivity = self.default_sensitivity
  self.color_timer = QTimer()  # Таймер для отложенной установки цвета
  self.color_timer.setSingleShot(True)
  self.color_timer.timeout.connect(self.apply_color_change)
  self.pending_color = None

  if os.path.exists(self.settings_file):
   self.load_settings()

  self.initUI()
  self.color_timer.timeout.connect(self.apply_color_change)

 def load_settings(self):
  """Загрузка настроек из JSON файла"""
  try:
   with open(self.settings_file, 'r') as f:
    settings = json.load(f)
    self.current_color = settings.get('color', self.default_color)
    self.current_sensitivity = settings.get('sensitivity', self.default_sensitivity)
    print("Настройки успешно загружены из файла")
  except Exception as e:
   print(f"Ошибка загрузки настроек: {e}")

 def save_settings(self):
  """Сохранение настроек в JSON файл"""
  try:
   settings = {
    'color': self.color_combo.currentText(),
    'sensitivity': self.sensitivity_slider.value()
   }

   # Сохраняем только если значения отличаются от дефолтных
   if (settings['color'] != self.default_color or
     settings['sensitivity'] != self.default_sensitivity):
    with open(self.settings_file, 'w') as f:
     json.dump(settings, f, indent=2)
     print("Настройки успешно сохранены")
  except Exception as e:
   print(f"Ошибка сохранения настроек: {e}")

 def initUI(self):
  """Настройка графического интерфейса"""
  self.setWindowTitle('Mouse Controller')
  layout = QVBoxLayout()

  # Цвет подсветки
  self.color_label = QLabel('Select Color:')
  self.color_combo = QComboBox()
  self.color_combo.addItems(["black", "red", "green", "blue", "yellow", "white"])
  self.color_combo.setCurrentText(self.current_color)
  self.color_combo.currentIndexChanged.connect(self.on_color_change)

  # Подключение сигнала наведения для каждого элемента в выпадающем списке
  self.color_combo.view().entered.connect(self.on_color_hover)

  # Чувствительность
  self.sensitivity_label = QLabel(f'Sensitivity: {self.current_sensitivity}')
  self.sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
  self.sensitivity_slider.setMinimum(500)
  self.sensitivity_slider.setMaximum(1500)
  self.sensitivity_slider.setValue(self.current_sensitivity)
  self.sensitivity_slider.valueChanged.connect(self.on_sensitivity_change)

  # Кнопка сброса настроек
  self.reset_button = QPushButton("Reset to Default")
  self.reset_button.clicked.connect(self.reset_to_default)

  layout.addWidget(self.color_label)
  layout.addWidget(self.color_combo)
  layout.addWidget(self.sensitivity_label)
  layout.addWidget(self.sensitivity_slider)
  layout.addWidget(self.reset_button)

  self.setLayout(layout)
  self.setGeometry(300, 300, 300, 200)
  self.show()

 def set_mouse_color(self, color: str):
  """Установка цвета подсветки мыши с помощью rivalcfg"""
  color_params = ["--strip-top-color", "--strip-middle-color",
                  "--strip-bottom-color", "--logo-color"]
  try:
   with self._mutex:
    for param in color_params:
     # Запускаем команду и игнорируем вывод
     subprocess.run(
      ["rivalcfg", param, color],
      check=True,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL
     )
    print(f"Цвет подсветки мыши установлен на {color}")
  except subprocess.CalledProcessError as e:
   print(f"Ошибка установки цвета: {e}")
  except Exception as e:
   print(f"Непредвиденная ошибка: {e}")

 def on_color_hover(self, index):
  """Обработка наведения на элемент списка"""
  if not index.isValid():
   return

  color = self.color_combo.itemText(index.row())
  self.color_label.setText(f'Preview: {color}')

  # Отменяем предыдущий таймер и устанавливаем новый
  self.color_timer.stop()
  self.pending_color = color
  self.color_timer.start(300)  # 300ms задержка

 def apply_color_change(self):
  """Применение отложенного изменения цвета"""
  if self.pending_color:
   # Используем поток для установки цвета без блокировки UI
   t = threading.Thread(target=self.set_mouse_color, args=(self.pending_color,))
   t.daemon = True  # Демонизируем поток
   t.start()
   self.pending_color = None

 def on_color_change(self):
  """Обработка изменения выбранного цвета"""
  color = self.color_combo.currentText()
  self.color_label.setText(f'Selected: {color}')

  # Отменяем таймер наведения
  self.color_timer.stop()
  self.pending_color = None

  # Немедленная установка цвета
  t = threading.Thread(target=self.set_mouse_color, args=(color,))
  t.daemon = True
  t.start()

 def on_sensitivity_change(self):
  """Обработка изменения значения чувствительности
  sudo /mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux\ must\ have/python_linux/Project/myvenv/bin/rivalcfg --update-udev
  """
  value = self.sensitivity_slider.value()
  self.sensitivity_label.setText(f'Sensitivity: {value}')

  try:
   # Запускаем в отдельном потоке чтобы не блокировать UI
   def set_sensitivity():
    try:
     subprocess.run(
      ['rivalcfg', '--sensitivity', str(value)],
      check=True,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL
     )
     print(f"Чувствительность мыши установлена на {value}")
    except subprocess.CalledProcessError as e:
     print(f"Ошибка установки чувствительности: {e}")

   t = threading.Thread(target=set_sensitivity)
   t.daemon = True
   t.start()
  except Exception as e:
   print(f"Ошибка при изменении чувствительности: {e}")

 def reset_to_default(self):
  """Сброс настроек к значениям по умолчанию"""
  self.color_combo.setCurrentText(self.default_color)
  self.sensitivity_slider.setValue(self.default_sensitivity)
  self.on_color_change()
  self.on_sensitivity_change()

  # Удаляем файл настроек
  if os.path.exists(self.settings_file):
   try:
    os.remove(self.settings_file)
    print("Файл настроек удален")
   except Exception as e:
    print(f"Ошибка удаления файла настроек: {e}")

 def closeEvent(self, event):
  """Обработка события закрытия окна"""
  self.save_settings()
  self.color_timer.stop()  # Останавливаем таймер
  event.accept()


if __name__ == '__main__':
 app = QApplication(sys.argv)
 ex = MouseController()
 sys.exit(app.exec())
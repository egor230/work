import json, subprocess, threading, sys, os
from PyQt5.QtCore import Qt  # Оставлено как было
from PyQt5.QtGui import QCloseEvent  # Оставлено как было
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QComboBox, QSlider, QLineEdit, QPushButton
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"

class MouseController(QWidget):
  _mutex = threading.Lock()  # Глобальный мьютекс на уровне класса
  def __init__(self):
    super().__init__()
    self.settings_file = "mouse_settings_for_rival.json"
    # [Добавлено] Сохраняем исходные значения по умолчанию
    self.default_color = 'white'
    self.default_sensitivity = 800
    if os.path.exists(self.settings_file):  # Проверяем наличие файла
      self.load_settings()  # Загружаем настройки только если файл существует
    else:
      self.current_color = self.default_color  # Используем сохранённые значения по умолчанию
      self.current_sensitivity = self.default_sensitivity
    self.initUI()

  def load_settings(self):# Загрузка настроек из JSON файла
    try:
      with open(self.settings_file, 'r') as f:
        settings = json.load(f)        # [Изменено] Используем сохранённые значения по умолчанию как fallback
        self.current_color = settings.get('color', self.default_color)
        self.current_sensitivity = settings.get('sensitivity', self.default_sensitivity)
        print("Настройки успешно загружены из файла")
    except Exception as ex1:
     pass

  def save_settings(self):# Сохранение настроек в JSON файл
    settings = {
      'color': self.color_combo.currentText(),
      'sensitivity': self.sensitivity_slider.value()
    }
    # [Добавлено] Проверяем, отличаются ли значения от исходных
    if (settings['color'] != self.default_color or
            settings['sensitivity'] != self.default_sensitivity):
      with open(self.settings_file, 'w') as f:
        json.dump(settings, f)

  def initUI(self):# Настройка графического интерфейса
    self.setWindowTitle('Mouse Controller')
    layout = QVBoxLayout()
    self.color_label = QLabel('Select Color:')
    self.color_combo = QComboBox()
    self.color_combo.addItems(["black", "red", "green", "blue", "yellow", "white"])
    self.color_combo.setCurrentText(self.current_color)
    self.color_combo.currentIndexChanged.connect(self.on_color_change)

    # [Изменено] Убрано eventFilter, добавлен сигнал entered
    self.color_combo.view().entered.connect(self.on_color_hover)  # Наведение на элемент

    self.sensitivity_label = QLabel(f'Sensitivity: {self.current_sensitivity}')
    self.sensitivity_slider = QSlider(Qt.Horizontal)
    self.sensitivity_slider.setMinimum(500)
    self.sensitivity_slider.setMaximum(1500)
    self.sensitivity_slider.setValue(self.current_sensitivity)
    self.sensitivity_slider.valueChanged.connect(self.on_sensitivity_change)

    layout.addWidget(self.color_label)
    layout.addWidget(self.color_combo)
    layout.addWidget(self.sensitivity_label)
    layout.addWidget(self.sensitivity_slider)

    self.setLayout(layout)
    self.setGeometry(300, 300, 300, 150)
    self.show()

  def set_mouse_color(self, color: str):  # Установка цвета подсветки мыши с помощью rivalcfg
    color_params = ["--strip-top-color", "--strip-middle-color",
                    "--strip-bottom-color", "--logo-color"]
    try:
     with self._mutex:  # Контекстный менеджер — автоматически захватывает и отпускает мьютекс
      for param in color_params:
        t = threading.Thread(target=subprocess.run, args=(["rivalcfg", param, color],), kwargs={'check': True})
        t.start()
        t.join()  # Ждём завершения каждой команды
        print(f"Цвет подсветки мыши установлен на {color}")
    except Exception as ex1:
      pass
  # [Добавлено] Новый метод для обработки наведения
  def on_color_hover(self, index):# Обработка наведения на элемент списка
    color = self.color_combo.itemText(index.row())
    self.color_label.setText(f'Preview: {color}')  # Лёгкое действие вместо set_mouse_color

    t = threading.Thread(target=self.set_mouse_color, args=(color,))
    t.start()
    # t.join()  # Ждём завершения для предпросмотра
  def on_color_change(self):# Обработка изменения выбранного цвета
    color = self.color_combo.currentText()

    t = threading.Thread(target=self.set_mouse_color, args=(color,))
    t.start()
    t.join()  # Ждём завершения для предпросмотра
  def on_sensitivity_change(self):  # Обработка изменения значения чувствительности
    value = self.sensitivity_slider.value()  # Получение текущего значения ползунка
    self.sensitivity_label.setText(f'Sensitivity: {value}')  # Обновление метки
    try:
      subprocess.run(['rivalcfg', '--sensitivity', str(value)], check=True)
      print(f"Чувствительность мыши установлена на {value}")
    except Exception as ex1:
      pass

  def closeEvent(self, event: QCloseEvent):  # Обработка события закрытия окна
    self.save_settings()  # Сохраняем текущие настройки перед закрытием
    event.accept()  # Подтверждаем закрытие окна

if __name__ == '__main__':
  app = QApplication(sys.argv)  # Создание приложения
  ex = MouseController()  # Создание экземпляра интерфейса
  sys.exit(app.exec_())  # Запуск основного цикла приложения
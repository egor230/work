import json, os, pyautogui, subprocess, sys, time
from datetime import datetime
from PIL import ImageGrab
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QPen, QMouseEvent
from PyQt5.QtWidgets import QApplication, QMainWindow

'''
Эта программа позволяет выбрать область экрана, делает её скриншот, 
копирует в буфер обмена и сохраняет параметры выбора области экрана в JSON-файл.
'''

def screenshot(left, top, width, height):  # print(left, top, width, height, end=' ')
  time.sleep(0.6)
  # Делаем скриншот с заданными размерами и координатами
  screenshot = ImageGrab.grab(bbox=(left, top, left + width, top + height))
  print(left, top, left + width, top + height)
  now = datetime.now()
  current_date = now.strftime("%Y-%m-%d")
  current_time = now.strftime("%H-%M-%S")
  file_name_path = format("{0}Screenshot {1} {2}.png".format(
    "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/Screenshots/",
    current_time,
    current_date))

  # Сохраняем изображение во временный файл
  screenshot.save(file_name_path, format="PNG")

  time.sleep(0.1)
  # # Копируем изображение в буфер обмена с помощью xclip
  # subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', file_name_path])
  # time.sleep(0.6)
  show_list_id = '''#!/bin/bash
    xclip -selection clipboard -t image/png -i $"{0}" # Помещаем изображение в буфер обмена
    sleep 2.9
    copyq select 0  '''.format(file_name_path)
  subprocess.run(['bash', '-c', show_list_id])
  time.sleep(0.1)

def do_screenshot(begin_point, end_point):  # Рассчитываем координаты top-left угла и размеры для скриншота
  left = min(begin_point.x(), end_point.x())
  top = min(begin_point.y(), end_point.y())
  width = abs(end_point.x() - begin_point.x())
  height = abs(end_point.y() - begin_point.y())

  # Получаем текущие координаты мыши
  # current_position = pyautogui.position()
  # # Выводим координаты
  # width = int(current_position.x)
  # height = int(current_position.y)
  # Создаем словарь для сохранения данных
  # Вызываем функцию скриншота с расчитанными параметрами
  screenshot(left, top, width, height)

class TransparentWindow(QMainWindow):
  def __init__(self):
    # Вызываем конструктор класса-предка
    super().__init__()
    # Устанавливаем флаги для окна: без рамки и всегда поверх других окон
    self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    # Делаем фон окна прозрачным
    self.setAttribute(Qt.WA_TranslucentBackground, True)
    # Задаем окну размер экрана
    self.setGeometry(QApplication.primaryScreen().geometry())

    # Флаг, отслеживающий, происходит ли сейчас рисование рамки
    self.drawing = False
    # Начальная точка рамки
    self.begin = QPoint()
    # Конечная точка рамки
    self.end = QPoint()
    # Включаем отслеживание движения мыши по окну
    self.setMouseTracking(True)
    # Отображаем окно
    self.show()

  def paintEvent(self, event):
    # Метод, вызываемый каждый раз, когда необходимо перерисовать содержимое окна
    qp = QPainter(self)
    qp.setPen(QPen(Qt.red, 3))  # Устанавливаем красный цвет пера
    rect = QRect(self.begin, self.end)  # Создаем прямоугольник
    qp.drawRect(rect)  # Рисуем прямоугольник

  def mousePressEvent(self, event: QMouseEvent):  # Проверяем, была ли нажата левая кнопка мыши.
    if event.button() == Qt.LeftButton:
      # Обрабатывает нажатия кнопки мыши
      if self.drawing:
        # Если рисование уже начато, завершаем его
        self.drawing = False
        self.end = event.pos()  # Фиксируем конечную позицию
        self.update()
        self.setMouseTracking(False)  # Выключаем отслеживание мыши
        self.close()  # Закрываем окно
        do_screenshot(self.begin, self.end)  # Делаем скриншот (функция вне класса)
      else:
        # Если рисование не начато, начинаем его
        self.begin = event.pos()  # Фиксируем начальную и конечную позиции
        self.end = event.pos()
        self.drawing = True  # Устанавливаем флаг рисования
        self.update()  # Запрашиваем перерисовку окна

    else:
      self.drawing = False  # Фиксируем конечную позицию
      self.update()
      self.setMouseTracking(False)  # Выключаем отслеживание мыши

      screenshot(0,0,1920, 1080)# Делаем скриншот
      self.close()  # Закрываем окно
  def mouseMoveEvent(self, event: QMouseEvent):
    # Обрабатывает движения мыши
    if self.drawing:
      self.end = event.pos()  # Обновляем конечную точку рамки
      self.update()  # Запрашиваем перерисовку окна


if __name__ == '__main__':
  app = QApplication(sys.argv)
  window = TransparentWindow()
  sys.exit(app.exec_())

import json, os, pyautogui, subprocess, sys, time
from datetime import datetime
from PIL import ImageGrab

# PyQt6 импорты
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPainter, QPen, QMouseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow

'''
Эта программа позволяет выбрать область экрана, делает её скриншот, 
копирует в буфер обмена и сохраняет параметры выбора области экрана в JSON-файл.
'''

def screenshot(left, top, width, height):
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

 # Скрипт для помещения изображения в буфер обмена через copyq
 show_list_id = '''#!/bin/bash
    xclip -selection clipboard -t image/png -i "{0}" # Помещаем изображение в буфер обмена
    sleep 2.9
 '''.format(file_name_path)

 subprocess.run(['bash', '-c', show_list_id])
 time.sleep(0.1)


def do_screenshot(begin_point, end_point):
 # Рассчитываем координаты top-left угла и размеры для скриншота
 left = min(begin_point.x(), end_point.x())
 top = min(begin_point.y(), end_point.y())
 width = abs(end_point.x() - begin_point.x())
 height = abs(end_point.y() - begin_point.y())

 # Вызываем функцию скриншота с расчитанными параметрами
 screenshot(left, top, width, height)


class TransparentWindow(QMainWindow):
 def __init__(self):
  # Вызываем конструктор класса-предка
  super().__init__()

  # Устанавливаем флаги для окна: без рамки и всегда поверх других окон
  self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                      Qt.WindowType.WindowStaysOnTopHint)

  # Делаем фон окна прозрачным
  self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

  # Задаем окну размер экрана
  screen_geometry = QApplication.primaryScreen().geometry()
  self.setGeometry(screen_geometry)

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
  qp.setPen(QPen(Qt.GlobalColor.red, 3))  # Устанавливаем красный цвет пера
  rect = QRect(self.begin, self.end)  # Создаем прямоугольник
  qp.drawRect(rect)  # Рисуем прямоугольник

 def mousePressEvent(self, event: QMouseEvent):
  # Проверяем, была ли нажата левая кнопка мыши
  if event.button() == Qt.MouseButton.LeftButton:
   # Обрабатывает нажатия кнопки мыши
   if self.drawing:
    # Если рисование уже начато, завершаем его
    self.drawing = False
    self.end = event.position().toPoint()  # Фиксируем конечную позицию
    self.update()
    self.setMouseTracking(False)  # Выключаем отслеживание мыши
    self.close()  # Закрываем окно
    do_screenshot(self.begin, self.end)  # Делаем скриншот
   else:
    # Если рисование не начато, начинаем его
    self.begin = event.position().toPoint()  # Фиксируем начальную позицию
    self.end = event.position().toPoint()  # И конечную позицию
    self.drawing = True  # Устанавливаем флаг рисования
    self.update()  # Запрашиваем перерисовку окна
  else:
   # Для других кнопок мыши (например, правой) - делаем скриншот всего экрана
   self.drawing = False
   self.update()
   self.setMouseTracking(False)

   # Делаем скриншот всего экрана
   screenshot(0, 0, 1920, 1080)
   self.close()

 def mouseMoveEvent(self, event: QMouseEvent):
  # Обрабатывает движения мыши
  if self.drawing:
   self.end = event.position().toPoint()  # Обновляем конечную точку рамки
   self.update()  # Запрашиваем перерисовку окна


if __name__ == '__main__':
 app = QApplication(sys.argv)
 window = TransparentWindow()
 sys.exit(app.exec())
import subprocess, sys
import time

import pyautogui
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt
from pynput import mouse

clean = f'''#!/bin/bash       
echo -n "" | xclip -i -selection primary
'''
subprocess.run(['bash', '-c', clean])
get_clipboard = f'''#!/bin/bash
xclip -o -selection primary
'''

class MouseEventThread(QtCore.QThread):
  mouse_event_signal = QtCore.pyqtSignal(str)
  def __init__(self, parent=None):
    super().__init__(parent)
  def on_click(self, x, y, button, pressed):
    if button == mouse.Button.left and not pressed:
      self.mouse_event_signal.emit('self')  # Отправляем сигнал с текстом

  def run(self):
    with mouse.Listener(on_click=self.on_click) as listener:
      listener.join()

class MyWindow(QtWidgets.QWidget):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.previous_text = ""

    self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)

    self.setGeometry(1800, 1010, 45, 20)
    self.mouse_event_thread = MouseEventThread()
    self.mouse_event_thread.mouse_event_signal.connect(self.handle_mouse_event)
    self.mouse_event_thread.start()
    layout = QVBoxLayout()
    # Создаем горизонтальный макет для кнопок
    button_layout = QHBoxLayout()

    cut_button = QPushButton('Вырезать')
    cut_button.clicked.connect(self.cut_text)
    button_layout.addWidget(cut_button)

    copy_button = QPushButton('Копировать')
    copy_button.clicked.connect(self.copy_text)
    button_layout.addWidget(copy_button)

    paste_button = QPushButton('Вставить')
    paste_button.clicked.connect(self.paste_text)
    button_layout.addWidget(paste_button)

    # Добавляем горизонтальный макет с кнопками в основной вертикальный макет
    layout.addLayout(button_layout)

    self.show()
    self.setLayout(layout)
  def handle_mouse_event(self, nj ):
    # Получаем текст из буфера обмена

    self.hide()
    self.lower()  # Окно на задний план
    time.sleep(0.3)
    current_text = subprocess.run(['bash', '-c', get_clipboard], stdout=subprocess.PIPE, text=True).stdout.strip()
    time.sleep(0.3)
    self.raise_()  # Вернуть окно на передний план
    self.show()
    if current_text and current_text != self.previous_text:
      # subprocess.run(['bash', '-c', clean])
      print(current_text)
      self.previous_text = current_text
      # self.show()
    # else:
    #   self.hide()

  def cut_text(self):
    self.hide()
    self.lower()  # Окно на задний план
    # QtWidgets.QApplication.processEvents()  # Обработка событий, чтобы изменения вступили в силу
    time.sleep(2.6)
    script = f'''#!/bin/bash
      xte "keydown Control_R"  "key x" "keyup Control_R"  '''
    subprocess.run(['bash', '-c', script])
    time.sleep(1.7)
    self.raise_()  # Вернуть окно на передний план
    self.show()
  def copy_text(self):
    self.hide()
    self.lower()  # Окно на задний план
    # QtWidgets.QApplication.processEvents()  # Обработка событий, чтобы изменения вступили в силу
    time.sleep(4.3)
    # script = '''#!/bin/bash
    #       xte "keydown Control_R" "key c" "keyup Control_R" '''
    # subprocess.run(['bash', '-c', script])
    pyautogui.hotkey('Control_R', 'c')
    time.sleep(4.3)
    self.raise_()  # Вернуть окно на передний план
    self.show()
  def paste_text(self):
    self.hide()
    self.lower()  # Окно на задний план
    # QtWidgets.QApplication.processEvents()  # Обработка событий, чтобы изменения вступили в силу
    time.sleep(3.3)
    script = '''#!/bin/bash
           copyq paste'''
    subprocess.run(['bash', '-c', script])
    time.sleep(3.3)
    self.raise_()  # Вернуть окно на передний план
    self.show()
app = QtWidgets.QApplication(sys.argv)
window = MyWindow()  # Запуск потока
sys.exit(app.exec_())
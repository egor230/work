import time,json,os,copy,psutil,threading,re,select,glob,subprocess,sys
from PyQt5.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QLineEdit,QScrollArea,QLabel
from PyQt5.QtCore import Qt  # Импортируем необходимые модули в одну строку
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"

class SaveDict:
  def __init__(self):
    self.labels = []  # Инициализируем список для хранения меток
    self.res = []  # Инициализируем список для хранения результатов
    self.count = 0  # Инициализируем индекс текущей записи

  def save_labels(self, labels):
    self.labels = labels  # Сохраняем список меток

  def return_labels(self):
    return self.labels  # Возвращаем список меток

  def cl_res(self):
    self.res.clear()  # Очищаем список результатов

  def save_res(self, res):
    self.res.clear()  # Очищаем текущий список результатов
    self.res = res  # Сохраняем новый список результатов

  def return_res(self):
    return self.res  # Возвращаем список результатов

  def set_count(self, count):
    self.count = count  # Устанавливаем индекс текущей записи
    return self.count  # Возвращаем установленный индекс

  def get_count(self):
    return self.count  # Возвращаем текущий индекс

class ClickableLabel(QLabel):
  def __init__(self, text, index, parent=None):
    super().__init__(text, parent)  # Инициализируем базовый класс QLabel
    self.index = index  # Сохраняем индекс метки
    self.setStyleSheet("background-color: White; padding: 2px; margin: 2px; color: black;")  # Устанавливаем стиль метки
    self.setCursor(Qt.PointingHandCursor)  # Устанавливаем курсор в виде руки для кликабельности

  def mousePressEvent(self, ev):
    if ev.button() == Qt.LeftButton:  # Проверяем, что нажата левая кнопка мыши
      k.set_count(self.index)  # Устанавливаем индекс текущей метки
      check_label_changed()  # Вызываем обработчик клика по метке

def check_label_changed():
  res = k.return_res()  # Получаем список результатов
  count = k.get_count()  # Получаем текущий индекс
  folder1 = str(folder).replace(" ", "\\ ")  # Экранируем пробелы в пути к папке
  if count < len(res):  # Проверяем, что индекс не выходит за пределы списка
    file_path = str(res[count]).replace(" ", "\\ ") + ".doc"  # Формируем путь к файлу
    set_button_map = '''#!/bin/bash
    cd {0};
    wine {1}; exit;'''.format(folder1, file_path)  # Формируем команду для запуска файла через wine
    def run_command():
      subprocess.call(['bash', '-c', set_button_map])  # Выполняем команду в отдельном потоке
    thread = threading.Thread(target=run_command)  # Создаем новый поток
    thread.start()  # Запускаем поток
    window.entry.clear()  # Очищаем поле ввода

def del_labels():
  labels = k.return_labels()  # Получаем список меток
  for label in labels:  # Перебираем все метки
    label.deleteLater()  # Удаляем метку из интерфейса
  labels.clear()  # Очищаем список меток
  k.save_labels(labels)  # Сохраняем пустой список меток

k = SaveDict()  # Создаем экземпляр класса SaveDict
folder = "/mnt/807EB5FA7EB5E954/работа/база для анализа"  # Задаем путь к папке
res = [os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith('.doc')]  # Формируем список имен файлов .doc без расширения
k.save_res(res)  # Сохраняем список результатов

class MainWindow(QMainWindow):
  def __init__(self):
    super().__init__()  # Инициализируем базовый класс QMainWindow
    self.setWindowTitle("Find text")  # Устанавливаем заголовок окна
    self.setGeometry(630, 550, 500, 286)  # Устанавливаем размер (500x236) и позицию (x=630, y=540)
    # self.setStyleSheet("background-color: DimGray;")  # Устанавливаем цвет фона окна DimGray
    self.central_widget = QWidget()  # Создаем центральный виджет
    self.setCentralWidget(self.central_widget)  # Устанавливаем центральный виджет
    self.layout = QVBoxLayout(self.central_widget)  # Создаем вертикальную компоновку
    self.entry = QLineEdit(self)  # Создаем поле ввода
    self.entry.setPlaceholderText("Введите текст для поиска")  # Устанавливаем подсказку для поля ввода
    self.layout.addWidget(self.entry)  # Добавляем поле ввода в компоновку
    self.scroll_area = QScrollArea(self)  # Создаем область прокрутки
    self.scroll_area.setWidgetResizable(True)  # Разрешаем изменение размера виджета
    self.scroll_widget = QWidget()  # Создаем виджет для содержимого области прокрутки
    self.scroll_layout = QVBoxLayout(self.scroll_widget)  # Создаем компоновку для области прокрутки
    self.scroll_area.setWidget(self.scroll_widget)  # Устанавливаем виджет в область прокрутки
    self.layout.addWidget(self.scroll_area)  # Добавляем область прокрутки в основную компоновку
    self.entry.textChanged.connect(self.on_text_changed)  # Подключаем обработчик изменения текста

  def on_text_changed(self, text):
   if text == "":
    return
   del_labels()  # Очищаем предыдущие метки
   search_text = text.lower()  # Приводим введенный текст к нижнему регистру
   matching_indices = [i for i, item in enumerate(k.return_res()) if search_text in item.lower()]  # Ищем совпадения в списке результатов
   new_labels = []  # Создаем список для новых меток
   for idx in matching_indices:  # Перебираем индексы совпадающих результатов
     label_text = k.return_res()[idx]  # Получаем текст результата
     label = ClickableLabel(label_text, idx, self.scroll_widget)  # Создаем кликабельную метку
     self.scroll_layout.addWidget(label)  # Добавляем метку в компоновку области прокрутки
     new_labels.append(label)  # Добавляем метку в список
   k.save_labels(new_labels)  # Сохраняем новый список меток

if __name__ == "__main__":
  app = QApplication(sys.argv)  # Создаем приложение PyQt5
  window = MainWindow()  # Создаем главное окно
  window.show()  # Отображаем окно
  sys.exit(app.exec_())  # Запускаем главный цикл приложения
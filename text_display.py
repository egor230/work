from libs_voice import *
import tkinter as tk
from tkinter import Label, Frame

def get_paths_file():  #  Получаем аргументы командной строки
  num_args = len(sys.argv)# Получаем количество аргументов
  url = ""
  return sys.argv[1:]

driver= get_paths_file()

def close_window():
  # Функция для закрытия окна
  root.destroy()
# Создаем основное окно
root = tk.Tk()

name = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text  # Получаем текст последнего элемента
len_len = len(name) * 12 + 10
# len_len=600
root.geometry(f"{len_len}x20+700+1025")  # Первые 2 определяют ширину высоту. Последние 2 x и y координаты на экране.

# Создаем фрейм
frame = Frame(root)

# Создаем метку с именем файла
label = Label(frame, text=name, font='Times 14')
label.pack(side=tk.LEFT, padx=3, fill=tk.X, expand=False)

# Упаковываем фрейм
frame.pack(fill=tk.X)

# Настраиваем окно
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)

# Планируем закрытие окна через 3 секунды
root.after(3000, close_window)
# Запускаем главный цикл обработки событий
root.mainloop()
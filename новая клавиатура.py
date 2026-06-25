import tkinter as tk
from tkinter import ttk, Text, Toplevel, messagebox
import os, json, copy, subprocess, threading
from deepdiff import DeepDiff
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key
class save_dict:
 def __init__(self):
  self.key_last =""
  self.keyboard_script = {}
  self.old_data = {}
  self.data="setting_keyboard_script.json" # файл настроек. print(data)
  if os.path.exists(self.data):  # есть ли этот файл.
   with open(self.data) as json_file:  # загрузка настроек из файла.
    self.keyboard_script  = json.load(json_file)
    self.old_data= copy.deepcopy(self.keyboard_script)
  else:  # Если нет файла создать настройки.
   self.keyboard_script  = {}
   k.save_jnson(keyboard_script)
 def save_jnson(self, jn):# сохранить настройки
   self.keyboard_script= jn

 def return_jnson(self):# Вернуть новые настройки.
    return self.keyboard_script

 def get_key_last(self):
    return self.key_last
 def set_key_last(self, key_last):
     self.key_last=key_last
     return self.key_last
 def write_to_file(self):
  if self.keyboard_script != self.old_data:
   if (messagebox.askokcancel("Quit", "Do you want to save the changes?")):
    json_string = json.dumps(self.keyboard_script, ensure_ascii=False, indent=2)  # self.data # файл настроек.
    with open(self.data, "w", encoding="UTF-8") as w:
     w.write(json_string)  # сохранить изменения в файле настроек.
  return self
# Создаем словари
en_to_ru = { 'a': 'ф', 'A': 'Ф', 'b': 'и', 'B': 'И', 'c': 'с', 'C': 'С', 'd': 'в', 'D': 'В', 'e': 'у', 'E': 'У', 'f': 'а', 'F': 'А', 'g': 'п', 'G': 'П', 'h': 'р', 'H': 'Р', 'i': 'ш', 'I': 'Ш', 'j': 'о', 'J': 'О', 'k': 'л', 'K': 'Л',
    'l': 'д', 'L': 'Д', 'm': 'ь', 'M': 'Ь', 'n': 'т', 'N': 'Т', 'o': 'щ', 'O': 'Щ', 'p': 'з', 'P': 'З', 'q': 'й', 'Q': 'Й', 'r': 'к', 'R': 'К', 's': 'ы', 'S': 'Ы', 't': 'е', 'T': 'Е', 'u': 'г', 'U': 'Г', 'v': 'м', 'V': 'М',
    'w': 'ц', 'W': 'Ц', 'x': 'ч', 'X': 'Ч', 'y': 'н', 'Y': 'Н', 'z': 'я', 'Z': 'Я', '.': '-', ',': '+', ' ': ' '}

ru_to_en = { 'ф': 'a', 'Ф': 'A', 'и': 'b', 'И': 'B', 'с': 'c', 'С': 'C', 'в': 'd', 'В': 'D', 'у': 'e', 'У': 'E', 'а': 'f', 'А': 'F', 'п': 'g', 'П': 'G', 'р': 'h', 'Р': 'H', 'ш': 'i', 'Ш': 'I', 'о': 'j', 'О': 'J', 'л': 'k', 'Л': 'K',    'д': 'l', 'Д': 'L', 'ь': 'm', 'Ь': 'M', 'т': 'n', 'Т': 'N', 'щ': 'o', 'Щ': 'O', 'з': 'p', 'З': 'P', 'й': 'q',
    'Й': 'Q', 'к': 'r', 'К': 'R', 'ы': 's', 'Ы': 'S', 'е': 't', 'Е': 'T', 'г': 'u', 'Г': 'U', 'м': 'v', 'М': 'V',
    'ц': 'w', 'Ц': 'W', 'ч': 'x', 'Ч': 'X', 'н': 'y', 'Н': 'Y', 'я': 'z', 'Я': 'Z', '-': '.', '+': ',', ' ': ' '}

def on_press(key):  # обработчик клави.  # print(key )
  key = str(key).replace(" ", "").replace('\'','') # Очищаем от ненужного
  for i in list(k.return_jnson().keys()): # Получаем клавиши которые являются макросами.
    i=str(i)
    if key in ru_to_en.keys():# нужно перевести нужно перевести русскую клавишу в английскую.
     key=ru_to_en[key]
    if key == i.lower():# теперь нужно перевести ее в нижней регистр.
     key1 = k.return_jnson()
     script=key1[key.upper()]
     listener.stop()
     t = threading.Thread(target=lambda: subprocess.call(['bash', '-c', script]))
     t.start()
     t.join()
     start_listener()
def on_release(key):
  pass
  return True

def start_listener():
 global listener
 listener = keyboard.Listener(on_press=on_press, on_release=on_release)
 listener.start()

# Запускаем слушатель
start_listener()
k= save_dict()
# Добавляем текст в текстовое поле
def add_text(key, text_widget):

  if key == "Ctrl":
      key = "ISO_Next_Group"
  if key == "Space":
      key = "space"

  if key == "Левая":
      sc = (f'xte "mousedown 1"\n'
            f'sleep 0.23\n'
            f'xte "mouseup 1"\n')
  elif key == "Правая":
      sc = (f'xte "mousedown 3"\n'
            f'sleep 0.23\n'
            f'xte "mouseup 3"\n')
  elif key == "wheel_up":
      sc = (f'xte "mousedown 4"\n'
            f'sleep 0.23\n'
            f'xte "mouseup 4"\n')
  elif key == "mouse_middie":
      sc = (f'xte "mousedown 2"\n'
            f'sleep 0.23\n'
            f'xte "mouseup 2"\n')
  elif key == "wheel_down":
      sc = (f'xte "mousedown 5"\n'
            f'sleep 0.23\n'
            f'xte "mouseup 5"\n')
  else:
      sc = (f'xte "keydown {key}"\n'
            f'sleep 0.23\n'
            f'xte "keyup {key}"\n')

  text_widget.insert(text_widget.index("insert"), sc)
  keyboard_script = k.return_jnson()
  keyboard_script[k.get_key_last()]= text_widget.get("1.0", "end-1c")  # Извлекаем текст из text_widget""
  k.save_jnson(keyboard_script)
# Окно клавиатуры
def create_keyboard(root):
  window = Toplevel(root)  # основа
  window.geometry("1350x340+240+580")  # Используем geometry вместо setGeometry
  keyboard_layout = [
   ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'Insert', 'Delete', 'Home',
    'End', 'PgUp', 'PgDn']
   , ['~\n`', '!\n1', '@\n2', '#\n3', '$\n4', '%\n5', '^\n6', '&\n7', '*\n8', '(\n9', ')\n0', '_\n-', '+\n=',
      'Backspace', 'Num Lock', '/', '*', '-']
   , ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{\n[', '}\n]', '|\n\\', ' 7\nHome', '8\n↑', '9\nPgUp',
      '+']
   , ['Caps Lock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':\n;', '"\n\'', '\nEnter\n', '4\n←', '5\n', '6\n→']
   , ['Shift_L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<\n,', '>\n.', '?\n/', 'Shift', '1\nEnd', '2\n↓', '3\nPgDn', 'KEnter']
   , ['Ctrl', 'Windows', 'Alt_L', 'space', 'Alt_r', 'Fn', 'Menu', 'Ctrl_r', 'up', '0\nIns', ' . ']
   , ['Left', 'Down', 'Right']
  ]
  buttons={}
  style = ttk.Style()  # При нажатии кнопка меняет свой цвет.
  style.configure('TButton', background='lightgray')
  style.map('TButton', background=[('active', 'blue')])
  for i, row in enumerate(keyboard_layout):  # Создаем клавиатуру.
   for j, key in enumerate(row):
    x1 = 70 * j + 6
    y1 = 50 * i + 6
    button = ttk.Button(window, text=key, width=5, style='TButton')
    buttons[button]=key
    if key == 'Backspace':  # Условие только для Backspace
     button = ttk.Button(window, text=key, width=10, style='TButton')
     buttons[button]=key
     button.place(x=x1, y=y1)
    elif i == 1 and j > 13:  # Смещение кнопок NumPad после Backspace
     button.place(x=x1 + 69, y=y1)  # Сдвигаем вправо на 80 пикселей
    else:
     button.place(x=x1, y=y1)
    if key in [' 7\nHome', '8\n↑', '9\nPgUp', '+']:
     x2 = x1 + 69
     button.place(x=x2, y=y1)
     if key == "+":
      button.config(text="\n\n" + key + "\n")
    if key in ['4\n←', '5\n', '6\n→']:
     x2 = x1 + 140
     button.place(x=x2, y=y1)
    if key in ['1\nEnd', '2\n↓', '3\nPgDn', 'KEnter']:
     x2 = x1 + 210
     button.place(x=x2, y=y1)
     if key == "KEnter":
      button.config(text="\n\n" + key + "\n")
    if i == 5:
     if key in ['Ctrl', 'Windows', 'Alt']:
      button.place(x=x1, y=y1)
     if key == "space":
      button = ttk.Button(window, text=key, width=30, style='TButton')
      button.place(x=x1, y=y1)

      buttons[button] = key
     elif key in ['Alt_r', 'Fn', 'Menu', 'Ctrl_r']:
      x2 = x1 + 210
      button.config(width=5)  # Устанавливаем ширину 15 для "0\nIns"
      button.place(x=x2, y=y1)
     elif key == 'up':
      x2 = x1 + 280
      button.config(width=5)
      button.place(x=x2, y=y1)
     elif key == "0\nIns":
      x2 = x1 + 420
      button.config(width=15)  # Устанавливаем ширину 15 для "0\nIns"
      button.place(x=x2, y=y1)
     elif key == ' . ':
      x2 = x1 + 490
      button.config(width=5)
      button.place(x=x2, y=y1)
    if i == 6:
     if key in ['Left', 'Down', 'Right']:
      x2 = x1 + 770
      button.config(width=5)
      button.place(x=x2, y=y1 - 9)

  return window, buttons

root = tk.Tk()
def main_window():
 window, buttons = create_keyboard(root)# создаем окно с клавиатурой. Надо нажать 1 кнопку
 window.title("Выбор клавиш")
 keys_active= k.return_jnson().keys()# Список кнопок из файла которые надо обозначить синим.

 for button, key in buttons.items():# Прикрепляем функцию add_text к каждой кнопке
  button.configure(command=lambda k=key, w=window : close_window(k, w))# при нажатии любой кнопка выходит новая клавиатура с редактором

  if key in keys_active:
   style = ttk.Style()# Меняем цвет тех кнопок которые уже были назначены.
   style.configure("Custom.TButton", background="blue", foreground="white")
   button.configure(style="Custom.TButton")

def kill_notebook(w, n):
 w.destroy()  # Закрываем предыдущую клавиатуру.
 n.destroy()
 main_window()
def kill_keyboard(w, n):
 kill_notebook(w, n)
 k.write_to_file()
def close_window(key,w):
 k.set_key_last(key)
 keys_active = k.return_jnson().keys()
 window, buttons = create_keyboard(root)# создаем новую
 window.title(f"Запись макроса для клавиши {key}")  # Устанавливаем заголовок окна

 window.geometry("1610x340+140+480")  # Используем geometry вместо setGeometry

 mouse_key_left_button = ttk.Button(window, text="\n\nЛевая\n\n", width=6, style='TButton')
 mouse_key_left_button.place(x=1340, y=100)
 buttons[mouse_key_left_button] = "Левая"

 mouse_wheel_up = ttk.Button(window, text="wheel_up", width=11, style='TButton')
 mouse_wheel_up.place(x=1410, y=50)
 buttons[mouse_wheel_up] = "wheel_up"
 #
 mouse_key_middie_button = ttk.Button(window, text="mouse_middie", width=11, style='TButton')
 mouse_key_middie_button.place(x=1410, y=140)
 buttons[mouse_key_middie_button] = "mouse_middie"

 mouse_wheel_down = ttk.Button(window, text="wheel_down", width=11, style='TButton')
 mouse_wheel_down.place(x=1410, y=220)
 buttons[mouse_wheel_down] = "wheel_down"

 mouse_key_right_button = ttk.Button(window, text="\n\nПравая\n\n", width=6, style='TButton')
 mouse_key_right_button.place(x=1530, y=100)
 buttons[mouse_key_right_button] = "Правая"
 note = Toplevel(root)  # основа
 note.title("Скрипт")

 notebook = ttk.Notebook(note)
 notebook.grid(row=0, column=0, sticky="nsew")

 note.protocol("WM_DELETE_WINDOW", lambda: kill_notebook(window, note))
 tab1 = ttk.Frame(notebook)
 notebook.add(tab1, text="Окно редактора скрипта")
 keyboard_script=k.return_jnson()
 text_widget = Text(tab1, wrap='word') # Текстовый редактор
 text_widget.grid(row=0, column=0, sticky="nsew")
 w.destroy()# Закрываем предыдущую клавиатуру.
 if key in keys_active:
  text_content =keyboard_script[key]
  text_widget.insert('end', text_content)
 window.protocol("WM_DELETE_WINDOW", lambda: kill_keyboard(window, note))
 for button, key in buttons.items():# каждой клавише присваиваем свою функци.
  button.configure(command=lambda k=key, t=text_widget: add_text(k, t))

main_window()# Запуск окна.

root.mainloop()



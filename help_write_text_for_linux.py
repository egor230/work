from datetime import datetime
from PIL import ImageGrab
from pynput.keyboard import Key, Controller
from pynput import *
import time, json, os, copy,  subprocess, pyautogui, re, threading
from typing import Optional, Tuple
import keyboard as keybo
from tkinter import *
import tkinter as tk

def check_current_active_window(user):# Получаем идентификатор активного окна
 get_main_id = '''#!/bin/bash # Получаем идентификатор активного окна
 active_window_id=$(xdotool getactivewindow 2>/dev/null)
 if [ -n "$active_window_id" ]; then
     process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
     echo "$process_id_active"
 else
     echo "0"  # Или любое значение по умолчанию, если нет активного окна
 fi
 exit '''
 try:
   process_id = int(subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip())
   a = []
   result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # # print(result)
   lines = result.split('\n')
   a = [line for line in lines if user in line]  # Убираем 'root' из условия
   pattern = [r"(.*.exe)",r"(.*.EXE)"]
   for i in a:
    for p in pattern:      # print(i)
     dir_process_name = i.split(maxsplit=10)[10].replace('\\', '/')  # Извлекаем нужную часть строки
     match = re.search(p, dir_process_name)
     if match:
       file_path = match.group(1)  # Получаем полный путь
       pid_id = int(i.split()[1])  # id потока
       if ".exe" in file_path or ".EXE" in file_path and "WINWORD.EXE" not in file_path:
         if process_id == pid_id:# нашли pid активного  окна
           # print(file_path)
           return True# активного окна
   return False
 except:
      return False

def clean_label(root):
 root.overrideredirect(False)
 root.withdraw()  # свернуть панель подсказок.
 root.overrideredirect(True)
 k.clean()
 for i in range(len(l)):
   l[i].config(text="")   # thread1 = threading.Thread(target=(b, user,))
   # thread1.daemon = True  # Установка атрибута daemon в значение True   # thread1.start()  #
class save_key:
   def __init__(self):
        self.key = ""
        self.text = ""
        self.swith=False
        self.count=0
        self.res=[]
        self.flag=True
        self.replace=True
        self.flag_thread=False
        self.flag_screenshot=False
        self.lock = threading.Lock()

   def get_flag_screenshot(self):
       return self.flag_screenshot

   def set_flag_screenshot(self, value1):
     self.flag_screenshot = value1
     
   def get_replace(self):
       return self.replace

   def set_replace(self, value):
       self.replace = value
   def get_flag(self):
      return self.flag

   def set_flag(self, value):
      self.flag=value

   def save(self, key):# сохранить вводное слово.
       self.key =key
       return self.key
   def clean(self):# обнулить вводное слово.
       self.key =""       # self.replace=False
       self.res.clear()
   def update(self, key1):
      self.key =str(self.key)+str(key1).replace("'","")

   def backspace(self, root):
      if len(self.key)==1:
        clean_label(root)
        self.res.clear()
        root.withdraw()  # свернуть панель подсказок.
        self.key=""
      else:
       self.key = str(self.key[:-1])       # print(self.key)
       return self.key
   def return_key(self):
      return self.key

   def get_swith(self):
     return self.swith

   def set_swith(self, value):
      self.swith = value
   def save_len(self, count):
       self.count = count
   def get_len(self):
      return self.count

   def save_list(self,res1):
       self.res.clear()
       for i in range(len(res1)):
        res1[i]=str(res1[i]).replace(" ","")
       self.res=res1
   def get_list(self):
      return self.res

   def save_text(self, text):
       self.text = text
   def get_text(self):
       return self.text

timestamp = time.time()
script = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''
# Вызываем скрипт
user = subprocess.run(['bash'], input=script, stdout=subprocess.PIPE, text=True).stdout.strip() # он возвращает имя пользователя (user)
k=save_key()
with open("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/words.txt", encoding="cp1251", errors='ignore') as r:
  k.save_text(r.read())
  # print(k.get_text())

root = Tk()
global arg
arg = [StringVar() for _ in range(7)]
global l
l=[]
key1=""
def f(word, text):
    find_liter = r'\b{}\w+\s'.format(word)
    Find_liter = r'\b{}\w+\s'.format(word.capitalize())    # find_liter = r'\b{}+[ ^.!?]+[.!?]+'.format(word)    # Find_liter = r'\b{}+[ ^.!?]+[.!?]+'.format(word.title())
    res = re.findall(find_liter, text)
    res1 = re.findall(Find_liter, text)
    res = res + res1
    for i in range(len(res)):
      res[i]= str(res[i]).replace("\n","").replace(" ","")  # [res1.append(word.lower()) for word in res]

    a = sorted(list(set(res)), key=len)    # res = lensort(res)
    return a
def dela(root):
 clean_label(root)  # удалить подсказки.
 k.backspace(root)# откл блок обработчика
swit1=0
def get_new_key(key, text): # получить новое слово
  res=[]
  k.update(str(key))
  key1= k.return_key()
  res = f(key1, text) # Найти список слов.
  k.save_list(res)  # Сохранить этот список слов.
  return res

def typing_text( char): # Печатает это слово по буквам.
  char = str(char)  # print(char)
  delay = 0.9  # Задайте здесь нужную задержку в секундах
  script = f'''#!/bin/bash
  word="{char}"  # Задайте здесь нужное слово
  delay={delay}  # Задайте здесь нужную задержку в секундах
  if [[ -z "$word" ]]; then
    xte "key space"
  else
    if [[ $word == [:upper:]* ]]; then  
      xdotool key Caps_Lock
      sleep $delay  # Пауза в секундах
      xdotool type  "$word"
      xdotool key Caps_Lock
      else
      xdotool type  "$word"
      sleep $delay  # Пауза в секундах  
    fi
  fi
  '''
  subprocess.call(['bash', '-c', script, '_'])
def update_word(key):# обновить слово
  k.update(str(key))
  key1 = k.return_key()  # Вернуть обновлённое слово.
  return key1

Backspace = f'''#!/bin/bash
xte 'keydown BackSpace' 'keyup BackSpace'
'''
def replacing_words(old_word, new_word, root):
  k.set_flag(False)
  clean_label(root)  #
  root.withdraw()  # свернуть панель подсказок.

  len_word=len(old_word)+1 # длинна написаного слово для удаления.  print(len_word)
  for i in range(len_word):
   subprocess.call(['bash', '-c', Backspace, '_'])
   time.sleep(0.09) # typing_text(new_word)

  dela(root)
  t2 =  threading.Thread(target=typing_text, args=(new_word,))
  t2.start()
  t2.join()
  k.set_flag(True)
  return True  # input()

def filling_in_hints(key1, root):
  text=k.get_text()  # key = from_ghbdtn(key)  # print(key)
  res = f(key1, text)  #  print(key1)  #  # print(res)
  k.save_list(res)
  for i in range(len(l)):
      l[i].config(text="")
  sum_len=[]
  if len(res)>0:
   for i in range(len(res)):
    if i<len(l):
     l[i].config(text=res[i])
     arg[i].set(str(res[i]))
     sum_len.append(len(str(res[i])))
   k.set_replace(True)
   root.deiconify() # показать панель.
   time.sleep(0.001)
  else:
    root.withdraw()# свернуть панель подсказок.
    dela(root)

frame = Frame(root, borderwidth=0)
for i in range(6):
 l.append(Label(frame,  text=arg[i], font='Times 14'))
 l[i].config(text="")

 l[i].pack(side=tk.LEFT, padx=3, fill=tk.X, expand=False)
 # l[i].pack(side=LEFT, padx=3, fill=X)  # Заполняем всю ширину

frame.pack(fill=X)

def show_hints(key, root):
 key= update_word(key)# обновить слово
 filling_in_hints(key, root) # вывести подсказки.
 # Получаем количество букв первых 6 элементов
 res=k.get_list()
 lengths = sum(len(word) for word in res[:6])
 len_len=lengths*12+10
 # len_len=600
 root.geometry(f"{len_len}x20+700+1025")  # Первые 2 определяют ширину высоту. Последние 2 x и y координаты на экране.

def find_nemo():
  get_main_id = '''#!/bin/bash # Получаем идентификатор активного окна
  active_window_id=$(xdotool getactivewindow 2>/dev/null)
  if [ -n "$active_window_id" ]; then
      process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
      echo "$process_id_active"
  else
      echo "0"  # Или любое значение по умолчанию, если нет активного окна
  fi
  exit '''
  result1 = subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip()
  lines = result1.split('\n')  # Разбиваем вывод по новой строке и извлекаем значения
  process_id_active = int(lines[0].split(': ')[0])
  result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # # print(result)
  lines = result.split('\n')
  for line in lines:  #
    if 'nemo' in line:
      parts = line.split()
      pid = int(parts[1])
      cmd = ' '.join(parts[10:]).replace(" ", "")
      if 'nemo' in cmd and process_id_active==pid:

       return True
  return False


def get_nemo_search_regions() -> Optional[Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int]]]:
 """
 Находит окно Nemo, рассчитывает абсолютные координаты двух областей
 поиска для PyAutoGUI и возвращает их.

 Возвращает:
     (region_button, region_text) или None, если Nemo не найден.
     region_button: Абсолютные координаты (left, top, width, height) для кнопки поиска (лупы).
     region_text: Абсолютные координаты (left, top, width, height) для текста поиска ("Поиск файлов:").
 """

 # --- 1. ПОЛУЧЕНИЕ ГЕОМЕТРИИ ОКНА NEMO ---
 try:
  # Найти ID окна Nemo по классу
  window_id_cmd = "wmctrl -l -x | grep 'Nemo' | head -n 1 | awk '{print $1}'"
  window_id = subprocess.check_output(window_id_cmd, shell=True, text=True).strip()

  if not window_id:
   return None

  # Получить геометрию окна
  geometry_cmd = f"xdotool getwindowgeometry --shell {window_id}"
  geometry_output = subprocess.check_output(geometry_cmd, shell=True, text=True)

  # Распарсить вывод
  base_x = int(re.search(r'X=(\d+)', geometry_output).group(1))
  base_y = int(re.search(r'Y=(\d+)', geometry_output).group(1))
  base_width = int(re.search(r'WIDTH=(\d+)', geometry_output).group(1))
  base_height = int(re.search(r'HEIGHT=(\d+)', geometry_output).group(1))

 except Exception:
  # Сюда попадают ошибки subprocess.CalledProcessError и AttributeError
  return None

 # --- 2. НАСТРОЙКИ ОТНОСИТЕЛЬНЫХ СМЕЩЕНИЙ ---

 # Смещения для Кнопки Поиска (привязка к правому верхнему углу)
 REGION_BUTTON_WIDTH = 100
 REGION_BUTTON_HEIGHT = 100

 # Смещения для Текста Поиска (привязка к левому верхнему углу)
 REGION_TEXT_OFFSET_X = 200  # Смещение от левого края Nemo
 REGION_TEXT_OFFSET_Y = 80  # Смещение от верхнего края Nemo
 REGION_TEXT_WIDTH = 300
 REGION_TEXT_HEIGHT = 150

 # --- 3. РАСЧЕТ АБСОЛЮТНЫХ КООРДИНАТ ---

 # Расчет области для Кнопки Поиска (лупы)
 region_button = (
  base_x + base_width - REGION_BUTTON_WIDTH,  # left: привязка к правому краю
  base_y,  # top: привязка к верхнему краю
  REGION_BUTTON_WIDTH,
  REGION_BUTTON_HEIGHT
 )

 # Расчет области для Текста Поиска ("Поиск файлов:")
 region_text = (
  base_x + REGION_TEXT_OFFSET_X,  # left: смещение от левого края
  base_y + REGION_TEXT_OFFSET_Y,  # top: смещение от верхнего края
  REGION_TEXT_WIDTH,
  REGION_TEXT_HEIGHT
 )

 return region_button, region_text

def search_image():
  try:
    s = f'''#!/bin/bash
    xte 'keydown Return' 'keyup Return'
    '''
    region = (1400, 100, 1500, 900)  # Пример области

    region1 = (268, 44, 182, 108)  # (left, top, width, height)
    # 1. Получаем динамические области поиска
    search_regions = get_nemo_search_regions()

    if search_regions:
     # Распаковываем полученные кортежи
     region, region1 = search_regions

    image_path = 'Search button.png'    # Укажите путь к вашему изображению

    loc = pyautogui.locateOnScreen(image_path, confidence=0.25, region=region)  # Проверяем, есть ли изображение на экране

    image_path1 = 'Search text.png'    # Укажите путь к вашему изображению
    loc1 = pyautogui.locateOnScreen(image_path1, confidence=0.2, region=region1)  # Проверяем, есть ли изображение на экране
    if loc and loc1 and find_nemo(): #
      print("22")
      subprocess.call(['bash', '-c', s, '_'])
  except:
    pass

def b(k, user):
  while 1:
    time.sleep(3)
    if check_current_active_window(user):
        k.flag_thread = True
    else:
        k.flag_thread = False  # print("fa")

thread1 = threading.Thread(target=b, args=(k, user,))
thread1.daemon = True
thread1.start()

def replace_word(number, k, old_word, root):
    key1=k.get_list()[number]
    replacing_words(old_word, key1, root)
# Словарь для перевода английских символов в русские
eng_to_rus = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
    'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д',
    'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', 'Q': 'Й', 'W': 'Ц', 'E': 'У',
    'R': 'К', 'T': 'Е', 'Y': 'Н', 'U': 'Г', 'I': 'Ш', 'O': 'Щ', 'P': 'З', 'A': 'Ф', 'S': 'Ы', 'D': 'В',
    'F': 'А', 'G': 'П', 'H': 'Р', 'J': 'О', 'K': 'Л', 'L': 'Д', 'Z': 'Я', 'X': 'Ч', 'C': 'С', 'V': 'М',
    'B': 'И', 'N': 'Т', 'M': 'Ь', '[': 'х', ']': 'ъ', ';': 'ж', "'": 'э', ',': 'б', '.': 'ю'
    # , '{': 'Х', '}': 'Ъ', ':': 'Ж', '"': 'Э', '<': 'Б', '>': 'Ю',  'ф': 'a', 'Ф': 'A', 'и': 'b', 'И': 'B', 'с': 'c', 'С': 'C', 'в': 'd', 'В': 'D', 'у': 'e', 'У': 'E', 'а': 'f', 'А': 'F', 'п': 'g', 'П': 'G', 'р': 'h', 'Р': 'H', 'ш': 'i', 'Ш': 'I', 'о': 'j', 'О': 'J', 'л': 'k', 'Л': 'K',
    #          'д': 'l', 'Д': 'L', 'ь': 'm', 'Ь': 'M', 'т': 'n', 'Т': 'N', 'щ': 'o', 'Щ': 'O', 'з': 'p', 'З': 'P', 'й': 'q',
    # 'Й': 'Q', 'к': 'r', 'К': 'R', 'ы': 's', 'Ы': 'S', 'е': 't', 'Е': 'T', 'г': 'u', 'Г': 'U', 'м': 'v', 'М': 'V',
    # 'ц': 'w', 'Ц': 'W', 'ч': 'x', 'Ч': 'X', 'н': 'y', 'Н': 'Y', 'я': 'z', 'Я': 'Z', '-': '.', '+': ','
}

# Функция для перевода английского символа в русский
def trans(char):
    if char in eng_to_rus:
        return eng_to_rus[char]
    return char  # Если символ не найден в словаре, возвращаем его без изменений

def on_press(key):#обработчик клави.
 key=str(key).replace(" ","").replace("\'","")
 key=trans(key)
 global timestamp # print(time.time()- timestamp )
 try:#  print(key)
  if time.time() - timestamp < 0.3 or  k.flag_thread:  # clean_label(root)# удалить подсказки.
    root.withdraw()  # свернуть панель подсказок.
    dela(root)  # time.sleep(0.3)    print('op[p')
    timestamp = time.time()  # root.withdraw()  # свернуть панель подсказок.
    return True
  timestamp = time.time()
  ignored = {"enter", "Key.right", "Key.left", "Key.down", "Key.up","Key.ctrl_r","Key.ctrl_l","Key.alt_r","Key.alt","<65032>",
             "Key.shift_l", "Key.shift_r"}
  if key not in ignored or k.flag_thread:
   f2 = threading.Thread(target=search_image, args=())
   f2.daemon = True  # Устанавливаем поток как демон
   f2.start()  # Запускаем поток
  if key=='Key.ctrl_l'  or key=='Key.shift_l' or key=='.' or key==',' or key=='Key.shift_r'\
  or  key=='\'\''  or key == "Key.delete" or key =="Key.right" or key =="Key.left"\
  or key =="Key.down" or key =="Key.up" or key == "Key.space" or key == "Key.alt_r"  \
  or key=='\',\'' or key=='\\ 'or key=='/' or key =="Key.caps_lock" or key =="Key.tab" or key == "Key.alt_l"\
  or key =="Key.tab" or key =="Key.cmd"  or key =="Key.enter" or key =="Key.esc" or key =="Key.f1"\
  or key =="Key.f2" or key =="Key.f3" or key =="Key.f4" or key =="Key.f5" or key =="Key.f6" or key =="Key.f7"\
  or key =="Key.f8" or key =="Key.f9" or key =="Key.f10" or key =="Key.f11" or key =="Key.f12" or key =="<65032>"\
  or key =="Key.alt" or key =="Key.shift" or key =="0" :#   print("unkey")
   root.withdraw()  # свернуть панель подсказок.
   dela(root)
   return True
  if key == "Key.backspace" :# and k.get_swith() == False:
    key1 = k.backspace(root)
    if len(key1)>0:#         print(key1)
     filling_in_hints(key1, root)  # вывести подсказки.
     return True
    else:
     dela(root)
     return True
  if key !="<96>" and key !="<97>" and key !="<98>" and key !="<99>" and key !="<100>" and key !="<101>" \
   and key !="<102>" and key !="<103>" and key !="<104>" and key !="<105>" and key !="+" and key !="-" \
   and key !="*" and key !="/" and key != "Key.num_lock" and key !="Key.page_down"and key != "Key.page_up" \
   and key != "Key.end" and key != "Key.home" and key !="Key.insert" and key !='\'/\'' and key !='\'\ \''\
   and key !='\'.\''and key !='1' and key !='2' and key !='3' and key !='4' and key !='5' \
   and key !='6' and key !="<65437>" and key !="Key.backspace":
    if k.get_flag()==True:# подсказки     print(key)
     show_hints(key, root)# вывести подсказки.
     return True

  old_word=k.return_key()
  if key == "1" and k.get_replace()==True and len(k.get_list())>0:
    replace_word(0, k, old_word, root)
    return True
  if key == "2" and k.get_replace()==True and len(k.get_list())>1:
    replace_word(1, k, old_word, root)
    return True
  if key == "3" and k.get_replace()==True and len(k.get_list())>2:
    replace_word(2, k, old_word, root)
    return True
  if key == "4" and k.get_replace()==True and len(k.get_list())>3:
    replace_word(3, k, old_word, root)
    return True
  if key == "<65437>" and k.get_replace()==True and len(k.get_list())>4:
    replace_word(4, k, old_word, root)
    return True
  if key == "6" and k.get_replace()==True and len(k.get_list())>5:
    replace_word(5, k, old_word, root)
    return True

 except Exception as ex:  # clean_label(root)  #
    print(ex)
    return True
def on_release(key):
 pass# Collect events until released
def on_click(x, y, button, pressed):
  root.withdraw()# свернуть панель подсказок.
  dela(root)  # pass
  return True
# root.geometry("600x20+590+1025")  # Первые 2 определяют ширину высоту. Пос 2 x и y координаты на экране.
root.overrideredirect(True)
root.resizable(1, 1)
root.attributes("-topmost",True)
root.withdraw()# свернуть панель подсказок.
listener1 =mouse.Listener(on_click=on_click)
listener1.start()
listener = keyboard.Listener(  on_press=on_press,   on_release=on_release)
listener.start()
root.mainloop()

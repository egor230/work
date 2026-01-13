import json, os, re, subprocess, threading, time, sys, tkinter as tk, pyautogui
from tkinter import Tk, Toplevel, Label, Frame
from pynput import mouse, keyboard
import cv2
import numpy as np
from PIL import ImageGrab  # для скриншота


def find_nemo(): # Проверяет, активно ли окно файлового менеджера Nemo
 get_main_id = '''#!/bin/bash
 active_window_id=$(xdotool getactivewindow 2>/dev/null)
 if [ -n "$active_window_id" ]; then
   process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
   echo "$process_id_active"
 else
   echo "0"
 fi
 exit'''
 try:
  result1 = subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip() # Получаем ID активного окна
  process_id_active = int(result1.splitlines()[0]) # Преобразуем ID в число
  result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout # Получаем список процессов
  for line in result.splitlines():
   if 'nemo' in line: # Ищем процесс nemo
    parts = line.split()
    pid = int(parts[1])
    cmd = ' '.join(parts[10:]).replace(" ", "")
    if 'nemo' in cmd and process_id_active == pid: # Проверяем, совпадает ли PID с активным окном
     return True
  return False
 except:
  return False
def get_nemo_search_regions(image_path, image_path1):
 """
 Проверяет, видны ли на экране два заданных элемента интерфейса Nemo
 (кнопка поиска и текст поиска) с помощью поиска по изображению.

 Аргументы:
     image_path: Путь к изображению Кнопки Поиска.
     image_path1: Путь к изображению Текста Поиска.

 Возвращает:
     True, если оба изображения найдены на экране.
     False, в противном случае.
 """

 # ВАЖНО: Предполагается, что библиотека pyautogui доступна.
 CONFIDENCE = 0.8  # Уровень точности совпадения (можно изменить)

 # 1. Поиск Кнопки Поиска (лупы)
 # Если элемент не найден, loc_button будет None
 loc_button = pyautogui.locateOnScreen(image_path, confidence=CONFIDENCE)

 # 2. Поиск Текста Поиска ("Поиск файлов:")
 loc_text = pyautogui.locateOnScreen(image_path1, confidence=CONFIDENCE)

 # 3. Возврат результата
 # Если оба элемента найдены (то есть loc_button и loc_text не являются None)
 if loc_button is not None and loc_text is not None:
  return True
 else:
  return False
def search_image():
  try:
    s = f'''#!/bin/bash
    xte 'keydown Return' 'keyup Return'
    '''
    # region = (1400, 100, 1500, 900)  # Пример области
    #
    # region1 = (268, 44, 182, 108)  # (left, top, width, height)
    # 1. Получаем динамические области поиска

    image_path = '/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/Search button.png'    # Укажите путь к вашему изображению

    image_path1 = '/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/Search text.png'    # Укажите путь к вашему изображению
    if get_nemo_search_regions(image_path, image_path1) and find_nemo():
   # loc = pyautogui.locateOnScreen(image_path, confidence=0.25, region=region)  # Проверяем, есть ли изображение на экране
    # loc1 = pyautogui.locateOnScreen(image_path1, confidence=0.2, region=region1)  # Проверяем, есть ли изображение на экране
    #if loc :#and loc1     print("22")
     subprocess.call(['bash', '-c', s, '_'])
  except:
    pass

class ToolTip: # Класс для отображения подсказок
 def __init__(self, widget, text):
  self.widget = widget
  self.tipwindow = None
  self.text = text
  self._showtip() # Показываем подсказку при инициализации

 def _showtip(self): # Создает окно подсказки
  if self.tipwindow or not self.text:
   return
  self.tipwindow = tw = Toplevel(self.widget)
  tw.wm_overrideredirect(True) # Убираем рамку окна
  tw.wm_geometry("+0+0")
  label = Label(tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))
  label.pack(ipadx=1)

 def updatetext(self, text): # Обновляет текст подсказки
  self.text = text
  if self.tipwindow:
   for child in self.tipwindow.winfo_children():
    child.destroy()
   label = Label(self.tipwindow, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))
   label.pack(ipadx=1)

 def hidetip(self): # Скрывает подсказку
  if self.tipwindow:
   try:
    self.tipwindow.destroy()
   except tk.TclError:
    pass
   self.tipwindow = None

class SmartTyper: # Основной класс для автозамены и подсказок
 def __init__(self, abbreviations_path, words_path):
  self.abbreviations_path = abbreviations_path
  self.words_path = words_path
  self.abbreviations = {}
  self.normalized_abbrevs = {}
  self.sorted_abbrevs = []
  self.longest_abbreviation_length = 0
  self.word_text_data = ""
  self.ru_to_en_layout = { # Словарь для транслитерации с русской раскладки на английскую
   'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
   'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k',
   'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
   'б': ',', 'ю': '.', '.': '/', 'ё': '`', 'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y',
   'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}', 'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F',
   'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"', 'Я': 'Z', 'Ч': 'X', 'С': 'C',
   'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>', ',': '?', 'Ё': '~'  }
  self.en_to_ru_layout = { # Словарь для транслитерации с английской раскладки на русскую
   'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
   'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', 'z': 'я',
   'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', '[': 'х', ']': 'ъ', ';': 'ж', "'": 'э',
   ',': 'б', '.': 'ю', '`': 'ё', 'Q': 'Й', 'W': 'Ц', 'E': 'У', 'R': 'К', 'T': 'Е', 'Y': 'Н', 'U': 'Г',
   'I': 'Ш', 'O': 'Щ', 'P': 'З', 'A': 'Ф', 'S': 'Ы', 'D': 'В', 'F': 'А', 'G': 'П', 'H': 'Р', 'J': 'О',
   'K': 'Л', 'L': 'Д', 'Z': 'Я', 'X': 'Ч', 'C': 'С', 'V': 'М', 'B': 'И', 'N': 'Т', 'M': 'Ь'  }
  self._load_data() # Загружаем данные из файлов
  self.current_word = ""
  self.matched_abbrev_key = ""
  self.suggestions = []
  self.abbrev_res = ""
  self.tooltip = None
  self.tooltip_root = None
  self.last_key_press_time = time.time()
  self.user = self._get_current_user() # Получаем текущего пользователя
  self.disabled = False
  self.replacing = False
  self._setup_ui() # Настраиваем интерфейс

 def _load_data(self): # Загружает данные из файлов аббревиатур и словаря
  if os.path.exists(self.abbreviations_path):
   with open(self.abbreviations_path, 'r', encoding='utf-8') as json_file:
    self.abbreviations = json.load(json_file)
    if self.abbreviations:
     for k, v in self.abbreviations.items():
      self.normalized_abbrevs[k] = v
     self.longest_abbreviation_length = len(max(self.normalized_abbrevs.keys(), key=len))
     self.sorted_abbrevs = sorted(self.normalized_abbrevs.keys(), key=len, reverse=True)
  if os.path.exists(self.words_path):
   with open(self.words_path, 'r', encoding="cp1251", errors='ignore') as f:
    self.word_text_data = f.read()

 def _get_current_user(self): # Получает имя текущего пользователя
  script = '#!/bin/bash\necho $(whoami)\nexit;'
  return subprocess.run(['bash'], input=script, stdout=subprocess.PIPE, text=True).stdout.strip()

 def _setup_ui(self): # Настраивает интерфейс для подсказок
  self.root = Tk()
  self.root.overrideredirect(True)
  self.root.attributes("-topmost", True)
  self.root.resizable(1, 1)
  self.root.withdraw()
  frame = Frame(self.root, borderwidth=0)
  frame.pack(fill=tk.X)
  self.suggestion_labels = [Label(frame, text="", font='Times 14') for _ in range(6)]
  for label in self.suggestion_labels:
   label.pack(side=tk.LEFT, padx=3, fill=tk.X, expand=False)

 def _get_current_keyboard_layout(self):
   try:
     # Получаем LED mask из вывода xset -q
     result = subprocess.run("xset -q | grep 'LED mask' | awk '{print $10}'",
       shell=True, capture_output=True, text=True )
     led_mask = result.stdout.strip()
     # Если LED mask соответствует анг раскладке
     if led_mask == "00001002":
       return "us"
     else:
       return "ru"
   except Exception:
     return "ru"

 def _get_translated_key(self, key_char): # Возвращает транслитерированный символ
  ch = key_char.lower()
  layout = self._get_current_keyboard_layout()
  if layout == "ru":
   return ch
  else:
   return self.ru_to_en_layout.get(ch, ch)
 def clean(self):
  self.current_word = ""
  self.matched_abbrev_key = ""
  self._hide_suggestions()
  self.root.after(0, self._do_hide_all)
 def _type_text_and_finish(self, text): # Печатает текст и сбрасывает флаг replacing
  try:
   for char in text:
    time.sleep(0.18)
    if char == ' ':
     pyautogui.press('space')
    else:
     subprocess.call(['xdotool', 'type', '--delay', '9', char])

  finally:
   self.replacing = False

 def _replace_word_async(self, new_word, extra_backspace=1): # Асинхронно заменяет слово
  if self.replacing:
   return
  self.replacing = True
  backspace_count = len(self.current_word) + extra_backspace
  for _ in range(backspace_count):
   subprocess.run(['xdotool', 'key', 'BackSpace'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
   time.sleep(0.21)
  t = threading.Thread(target=self._type_text_and_finish, args=(new_word,))
  t.start()
  self.clean()
  t.join()
  self.replacing = False
  # self.root.after(0, do_replace)

 def _do_replace_abbrev_async(self): # Асинхронно заменяет аббревиатуру
  if self.replacing or not self.abbrev_res:
   return
  self.replacing = True
  t = threading.Thread(target=self._type_text_and_finish, args=(self.abbrev_res,))
  backspace_count = len(self.current_word)+1
  for _ in range(backspace_count):
   subprocess.run(['xdotool', 'key', 'BackSpace'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
   time.sleep(0.31)
  self.clean()
  t.start()
  t.join()
  self.replacing = False

 def _find_word_suggestions(self, prefix): # Ищет подсказки для введенного префикса
  if not prefix:
   return []
  try:
   # print(prefix)
   pattern_lower = r'\b' + re.escape(prefix.lower()) + r'[а-яё]*\s'
   pattern_cap = r'\b' + re.escape(prefix.capitalize()) + r'[а-яё]*\s'
   matches = re.findall(pattern_lower, self.word_text_data) + re.findall(pattern_cap, self.word_text_data)
   longer_matches = [m.rstrip() for m in matches if len(m.rstrip()) > len(prefix)]
   if len(longer_matches)>0:
    return sorted(set(longer_matches), key=len)
   else:
    if len(prefix) >0:
     self.current_word =prefix[-1]
     self._hide_suggestions()
     self._find_word_suggestions(prefix[-1])
    else:
     self.clean()
     return []
  except Exception:
   return []

 def _update_suggestions_ui(self): # Обновляет интерфейс подсказок
  if self.tooltip and self.abbrev_res:
   self.tooltip.updatetext(self.abbrev_res)
  for label in self.suggestion_labels:
   label.config(text="")
  if not self.suggestions:
   self.root.withdraw()
   return
  total_width = 60
  for i, word in enumerate(self.suggestions[:6]):
   display_text = f"{word}"
   self.suggestion_labels[i].config(text=display_text)
   total_width += len(display_text) * 12
  self.root.geometry(f"{total_width}x25+700+1010")
  self.root.deiconify()

 def _hide_suggestions(self): # Скрывает подсказки
  self.suggestions = []
  self.matched_abbrev_key = ""
  try:
   self.root.withdraw()
  except tk.TclError:
   pass

 def _show_abbrev_tooltip(self): # Показывает подсказку для аббревиатуры
  try:
   if self.tooltip_root:
    try:
     self.tooltip_root.destroy()
    except tk.TclError:
     pass
  except tk.TclError:
   pass
  self.tooltip_root = Toplevel(self.root)
  self.tooltip_root.withdraw()
  self.tooltip = ToolTip(self.tooltip_root, self.abbrev_res)

 def hide_abbrev_tooltip(self): # Скрывает подсказку для аббревиатуры
  if self.tooltip:
   try:
    self.tooltip.hidetip()
   except tk.TclError:
    pass
   self.tooltip = None
  if self.tooltip_root:
   try:
    self.tooltip_root.destroy()
   except tk.TclError:
    pass
   self.tooltip_root = None

 def _do_update_state(self): # Обновляет состояние подсказок
  if self.replacing:
   return
  match = self.check_for_abbreviation()
  if match:
   self.abbrev_res = match
   self._show_abbrev_tooltip()
  else:
   self.abbrev_res=""
   self.hide_abbrev_tooltip()
   self.suggestions = self._find_word_suggestions(self.current_word)
   self.matched_abbrev_key = ""
   if self.suggestions:
    self._update_suggestions_ui()

 def _do_hide_all(self): # Скрывает все подсказки
  self._hide_suggestions()
  self.hide_abbrev_tooltip()
  self.abbrev_res = ""

 def check_for_abbreviation(self): # Проверяет, совпадает ли ввод с аббревиатурой
  self.matched_abbrev_key = None
  abbre=""
  for key_char in self.current_word:
   trans_key =self._get_translated_key(key_char)
   abbre += trans_key  #  print(abbre)
  for abbrev_key in self.sorted_abbrevs:
   if len(self.current_word) == len(abbrev_key) and abbrev_key == abbre:
    self.matched_abbrev_key = abbrev_key
    return self.normalized_abbrevs[abbrev_key]
  return None

 def _check_active_window_loop(self): # Проверяет активное окно в цикле
  get_main_id = '''#!/bin/bash
  active_window_id=$(xdotool getactivewindow 2>/dev/null)
  if [ -n "$active_window_id" ]; then
   process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
   echo "$process_id_active"
  else
   echo "0"
  fi
  exit'''
  while True:
   try:
    found = False
    time.sleep(1)
    process_id = int(subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip())
    result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout
    lines = [line for line in result.splitlines() if self.user in line]
    pattern = r"(\.exe|\.EXE)"
    for line in lines:
     dir_process_name = line.split(maxsplit=10)[10].replace('\\', '/')
     if re.search(pattern, dir_process_name) and process_id == int(line.split()[1]):
      file_path_lower = dir_process_name.lower()
      if ".exe" or '/PortProton/data/scripts/start.sh' in file_path_lower and "winword.exe" not in file_path_lower:
       self.disabled = True
       self.current_word = ""
       self.suggestions = []
       self.abbrev_res = ""
       self.root.after(0, self._do_hide_all)
       found = True
       # print("game")
       break
    if not found:
     # print("work")
     self.disabled = False
   except Exception as e:
    print(e)
    self.disabled = False
    pass

 def _on_press(self, key): # Обрабатывает нажатия клавиш
  if self.replacing:
   self.clean()
   return True
  if self.disabled:
   return True
  key_str = str(key).replace("'", "").replace(" ", "")#  print(key_str)
  if key_str =="<65437>":
   key_str="5"
  if any(k in key_str for k in ["enter", "down", "right", "up", "left", "Key.tab",
                                "Key.caps_lock", "Key.shift", "<65032>", "<65032>",
                                "<65512>", "Key.ctrl_r"]):
   self.clean()
   return True
  if time.time() - self.last_key_press_time < 0.05:
   self.last_key_press_time = time.time()
   return True
  threading.Thread(target=search_image, daemon=True).start()
  self.last_key_press_time = time.time()
  if key == keyboard.Key.backspace:
   if self.current_word:
    self.current_word = self.current_word[:-1]
    self.root.after(0, self._do_update_state)
   else:
    self.root.after(0, self._do_hide_all)
   return True
  if key == keyboard.Key.space:
   if self.abbrev_res:
    self._do_replace_abbrev_async()
   self.clean()
   return True
  control_keys = { keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.alt_l, keyboard.Key.alt_r,# Набор управляющих клавиш
   keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.tab, keyboard.Key.caps_lock,
   keyboard.Key.left, keyboard.Key.right, keyboard.Key.up, keyboard.Key.down,
   keyboard.Key.home, keyboard.Key.end, keyboard.Key.delete, keyboard.Key.esc,
   keyboard.Key.cmd, keyboard.Key.num_lock, keyboard.Key.page_up, keyboard.Key.page_down,
   keyboard.Key.insert, keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
   keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8, keyboard.Key.f9,
   keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12  }
  if key in control_keys or key_str in {'.', ',', '\\', '/', '\\', '\'', '"', '<', '>', '?', '~', ':', ';', '{', '}', '[', ']', '0'}:
   self.root.after(0, self._do_hide_all)
   self.abbrev_res = ""
   return True
  if self.suggestions and key_str in "123456" :
   index = int(key_str) - 1
   if index < len(self.suggestions):
    self._replace_word_async(self.suggestions[index], extra_backspace=1)
    return True
  if hasattr(key, 'char') and key.char and key.char.isprintable() and key_str not in {"+", "-", "*", "/"}:
   key_char = key.char
   self.current_word += key_char
   if len(self.current_word) > self.longest_abbreviation_length:
    self.current_word = self.current_word[1:]
   self.root.after(0, self._do_update_state)
   return True
  return True

 def _on_click(self, x, y, button, pressed): # Обрабатывает клики мыши
  if pressed:
   self.clean()
  return True

 def start(self): # Запускает основной цикл приложения
  window_checker_thread = threading.Thread(target=self._check_active_window_loop, daemon=True)
  window_checker_thread.start()
  keyboard_listener = keyboard.Listener(on_press=self._on_press)
  mouse_listener = mouse.Listener(on_click=self._on_click)
  keyboard_listener.start()
  mouse_listener.start()
  self.root.mainloop()
  keyboard_listener.stop()
  mouse_listener.stop()
  keyboard_listener.join()
  mouse_listener.join()

if __name__ == "__main__":
 abbreviations_file = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/dictionary of substitutions.json"
 words_file = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/words.txt"
 if not os.path.exists(abbreviations_file):
  print(f"Ошибка: Файл аббревиатур не найден по пути: {abbreviations_file}")
  sys.exit(1)
 if not os.path.exists(words_file):
  print(f"Ошибка: Файл со словарем не найден по пути: {words_file}")
  sys.exit(1)
 app = SmartTyper(abbreviations_path=abbreviations_file, words_path=words_file)
 app.start()


# self.suggestions = []
# self.root.withdraw()
# else:
#  self.root.withdraw()
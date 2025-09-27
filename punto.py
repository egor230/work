import json, os, re, subprocess, threading, time, sys, tkinter as tk, pyautogui
from tkinter import Tk, Toplevel, Label, Frame
from pynput import mouse, keyboard

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
   if 'nemo' in cmd and process_id_active == pid:
    return True
 return False

def search_image():
 try:
  s = f'''#!/bin/bash
    xte 'keydown Return' 'keyup Return'    '''
  region = (1400, 100, 1500, 900)  # Пример области
  image_path = 'Search button.png'  # Укажите путь к вашему изображению
  
  loc = pyautogui.locateOnScreen(image_path, confidence=0.25, region=region)  # Проверяем, есть ли изображение на экране
  '''  "left": 268,
  "top": 44,
  "right": 450,
  "bottom": 152'''
  region1 = (268, 44, 182, 108)  # (left, top, width, height)
  image_path1 = 'Search text.png'  # Укажите путь к вашему изображению
  loc1 = pyautogui.locateOnScreen(image_path1, confidence=0.2, region=region1)  # Проверяем, есть ли изображение на экране
  if loc and loc1 and find_nemo():  #
   # print("22")
   subprocess.call(['bash', '-c', s, '_'])
 except:
  pass


class ToolTip:
 def __init__(self, widget):
  self.widget = widget
  self.tipwindow = None
  self.text = None

 def showtip(self, text):
  self.text = text
  if self.tipwindow or not self.text:
   return
  self.tipwindow = tw = Toplevel(self.widget)
  tw.wm_overrideredirect(True)
  tw.wm_geometry("+0+0")
  label = Label(tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))
  label.pack(ipadx=1)

 def updatetext(self, text):
  if self.tipwindow and self.text:
   self.text = text
   for child in self.tipwindow.winfo_children():
    child.destroy()
   label = Label(self.tipwindow, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))
   label.pack(ipadx=1)

 def hidetip(self):
  if self.tipwindow:
   self.tipwindow.destroy()
   self.tipwindow = None

def CreateToolTip(widget, text):
 toolTip = ToolTip(widget)
 toolTip.showtip(text)
 return toolTip

class SmartTyper:
 def __init__(self, abbreviations_path, words_path):
  # Инициализация путей
  self.abbreviations_path = abbreviations_path
  self.words_path = words_path
  self.abbreviations = {}
  self.normalized_abbrevs = {}
  self.sorted_abbrevs = []
  self.longest_abbreviation_length = 0
  self.word_text_data = ""

  # Словари для раскладки клавиатуры
  self.ru_to_en_layout = { 'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
   'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k',
   'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
   'б': ',', 'ю': '.', '.': '/', 'ё': '`', 'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y',
   'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}', 'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F',
   'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"', 'Я': 'Z', 'Ч': 'X', 'С': 'C',
   'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>', ',': '?', 'Ё': '~'
  }
  self.en_to_ru_layout = {  'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
   'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', 'z': 'я',
   'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', '[': 'х', ']': 'ъ', ';': 'ж', "'": 'э',
   ',': 'б', '.': 'ю', '`': 'ё', 'Q': 'Й', 'W': 'Ц', 'E': 'У', 'R': 'К', 'T': 'Е', 'Y': 'Н', 'U': 'Г',
   'I': 'Ш', 'O': 'Щ', 'P': 'З', 'A': 'Ф', 'S': 'Ы', 'D': 'В', 'F': 'А', 'G': 'П', 'H': 'Р', 'J': 'О',
   'K': 'Л', 'L': 'Д', 'Z': 'Я', 'X': 'Ч', 'C': 'С', 'V': 'М', 'B': 'И', 'N': 'Т', 'M': 'Ь'
  }

  # Загрузка данных после определения словарей
  self._load_data()

  # Инициализация состояния
  self.current_word = ""
  self.key_sequence = ""
  self.matched_abbrev_key = ""
  self.is_abbreviation_suggestion_active = False
  self.is_autocomplete_active = True
  self.is_globally_disabled = False
  self.swit = False
  self.suggestions = []
  self.abbrev_res = ""
  self.tooltip = None
  self.tooltip_root = None
  self.abbrev_listener = None
  self.last_key_press_time = time.time()
  self.user = self._get_current_user()

  # Настройка GUI
  self._setup_ui()

 def _load_data(self):
  # Загружает данные из файлов
  if os.path.exists(self.abbreviations_path):
   with open(self.abbreviations_path, 'r', encoding='utf-8') as json_file:
    self.abbreviations = json.load(json_file)
    if self.abbreviations:
     for k, v in self.abbreviations.items():
      norm_k = ''.join(self.ru_to_en_layout.get(c.lower(), c.lower()) for c in k)
      self.normalized_abbrevs[norm_k] = v
     self.longest_abbreviation_length = len(max(self.normalized_abbrevs.keys(), key=len))
     self.sorted_abbrevs = sorted(self.normalized_abbrevs.keys(), key=len, reverse=True)

  if os.path.exists(self.words_path):
   with open(self.words_path, 'r', encoding="cp1251", errors='ignore') as f:
    self.word_text_data = f.read()

 def _get_current_user(self):
  # Получает имя текущего пользователя Linux
  script = '#!/bin/bash\necho $(whoami)\nexit;'
  return subprocess.run(['bash'], input=script, stdout=subprocess.PIPE, text=True).stdout.strip()

 def _setup_ui(self):
  # Настраивает GUI для подсказок
  self.root = Tk()
  self.root.overrideredirect(True)
  self.root.attributes("-topmost", True)
  self.root.withdraw()

  frame = Frame(self.root, borderwidth=0)
  frame.pack(fill=tk.X)

  self.suggestion_labels = []
  for _ in range(6):
   label = Label(frame, text="", font='Times 14')
   label.pack(side=tk.LEFT, padx=3, fill=tk.X, expand=False)
   self.suggestion_labels.append(label)

 def _get_current_keyboard_layout(self):
  # Определяет текущую раскладку клавиатуры (en/ru)
  try:
   result = subprocess.run(['xset', 'q'], capture_output=True, text=True)
   if result.returncode == 0:
    match = re.search(r"LED mask:\s+(\d+)", result.stdout)
    if match:
     return "en" if '00001002' in match.group(1) else "ru"
  except Exception:
   return "ru"
  return "ru"

 def _get_translated_key(self, key_char):
  # Получает переведенный ключ для сопоставления аббревиатур (всегда нижний en)
  ch = key_char.lower()
  layout = self._get_current_keyboard_layout()
  if layout == "ru":
   return self.ru_to_en_layout.get(ch, ch)
  else:
   return ch

 def _type_text(self, text):
  # Печатает текст посимвольно
  for char in text:
   time.sleep(0.1)
   if char == ' ':
    pyautogui.press('space')
   else:
    subprocess.call(['xdotool', 'type', '--delay', '9', char])

 def _replace_word(self, new_word, extra_backspace=0):
  # Заменяет набранное слово на новое
  self.is_autocomplete_active = False

  # Удаляем старое слово + extra (для пробела или цифры)
  backspace_count = len(self.current_word) + extra_backspace
  for _ in range(backspace_count):
   subprocess.run(['xte', 'key BackSpace'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
   time.sleep(0.35)  # Увеличено время задержки

  # Печатаем новое слово
  threading.Thread(target=self._type_text, args=(new_word,), daemon=True).start()

  self._hide_suggestions()
  self.is_autocomplete_active = True

 def _do_replace_abbrev(self):
  # Выполняет замену аббревиатуры в главном потоке
  self.hide_abbrev_tooltip()
  if self.abbrev_res:
   backspace_count = len(self.current_word)+1
   for _ in range(backspace_count):
    subprocess.run(['xte', 'key BackSpace'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.15)  # Увеличено время задержки
   t = threading.Thread(target=self._type_text, args=(self.abbrev_res,))
   t.start()
   t.join()
   self.current_word = ""
   self.key_sequence = ""
   self.matched_abbrev_key = ""

 def _find_word_suggestions(self, prefix):
  # Ищет слова, начинающиеся с заданного префикса, длиннее префикса
  if not prefix:
   return []
  try:
   pattern_lower = r'\b' + re.escape(prefix.lower()) + r'[а-яё]*\s'
   pattern_cap = r'\b' + re.escape(prefix.capitalize()) + r'[а-яё]*\s'
   matches_lower = re.findall(pattern_lower, self.word_text_data, re.MULTILINE)
   matches_cap = re.findall(pattern_cap, self.word_text_data, re.MULTILINE)
   all_matches = [m.rstrip() for m in matches_lower + matches_cap]
   longer_matches = [m for m in all_matches if len(m) > len(prefix)]
   unique_sorted = sorted(set(longer_matches), key=len)
   return unique_sorted
  except Exception:
   return []

 def _update_suggestions_ui(self): # Обновляет и отображает панель подсказок
  # Очищаем старые подсказки
  for label in self.suggestion_labels:
   label.config(text="")

  if not self.suggestions:
   self.root.withdraw()
   return

  total_width = 60
  for i, word in enumerate(self.suggestions[:len(self.suggestion_labels)]):
   display_text = f"{word}"
   self.suggestion_labels[i].config(text=display_text)
   total_width += len(display_text) * 12

  self.root.geometry(f"{total_width}x25+700+1010")
  self.root.deiconify()

 def _hide_suggestions(self): # Скрывает панель подсказок и сбрасывает состояние
  self.current_word = ''
  self.key_sequence = ''
  self.suggestions = []
  self.is_abbreviation_suggestion_active = False
  self.matched_abbrev_key = ""
  if self.root.winfo_viewable():
   self.root.withdraw()
   for label in self.suggestion_labels:
    label.config(text="")

 def _show_abbrev_tooltip(self):  # Показывает tooltip для аббревиатуры в главном потоке
  try:
   if self.tooltip_root:
    self.tooltip_root.destroy()
  except tk.TclError:
   pass
  self.tooltip_root = Toplevel(self.root)
  self.tooltip_root.withdraw()
  self.tooltip = ToolTip(self.tooltip_root)
  self.tooltip.showtip(self.abbrev_res)

 def _update_abbrev_tooltip(self):
  # Обновляет текст tooltip для аббревиатуры
  if self.tooltip and self.abbrev_res:
   self.tooltip.updatetext(self.abbrev_res)

 def hide_abbrev_tooltip(self):
  # Скрывает tooltip для аббревиатуры в главном потоке
  if self.tooltip:
   self.tooltip.hidetip()
   self.tooltip = None
  if self.tooltip_root:
   self.tooltip_root.destroy()
   self.tooltip_root = None
  if self.abbrev_listener:
   try:
    self.abbrev_listener.stop()
   except:
    pass
   self.abbrev_listener = None
  self.swit = False

 def start_abbrev_listener_thread(self):
  # Запускает поток для слушателя подтверждения аббревиатуры
  def inner():
   def on_press2(key):
    try:
     key_str = str(key).replace(" ", "").replace("'", "")
     if hasattr(key, 'char') and key.char and key.char.isprintable() and key_str not in {"+", "-", "*", "/"}:
      # Letter pressed, update
      key_char = key.char
      trans_key = self._get_translated_key(key_char)
      self.key_sequence += trans_key
      layout = self._get_current_keyboard_layout()
      displayed_char = self.en_to_ru_layout.get(key_char, key_char) if layout == "en" else key_char
      self.current_word += displayed_char
      if len(self.key_sequence) > self.longest_abbreviation_length:
       self.key_sequence = self.key_sequence[1:]
       self.current_word = self.current_word[1:]
      match = self.check_for_abbreviation()
      if match:
       self.abbrev_res = match
       self.root.after(0, self._update_abbrev_tooltip)
      else:
       self.root.after(0, self.hide_abbrev_tooltip)

       def stop_listener():
        if self.abbrev_listener:
         self.abbrev_listener.stop()

       self.root.after(0, stop_listener)
       self.swit = False
       return False
      return True  # Let the key through for typing
     elif key_str == "Key.space":
      self.root.after(0, self._do_replace_abbrev)

      def stop_listener():
       if self.abbrev_listener:
        self.abbrev_listener.stop()

      self.root.after(0, stop_listener)
      return False
     else:
      self.root.after(0, self.hide_abbrev_tooltip)

      def stop_listener():
       if self.abbrev_listener:
        self.abbrev_listener.stop()

      self.root.after(0, stop_listener)
      self.swit = False
      return False
    except Exception:
     return True

   self.abbrev_listener = keyboard.Listener(on_press=on_press2)
   self.abbrev_listener.start()
   self.abbrev_listener.join()

  t = threading.Thread(target=inner, daemon=True)
  t.start()

 def _check_active_window_loop(self):
  # Фоновый процесс для проверки активного окна (отключение в играх)
  while True:
   time.sleep(3)
   try:
    active_pid_cmd = "xdotool getwindowpid $(xdotool getactivewindow 2>/dev/null)"
    active_pid_result = subprocess.run(active_pid_cmd, shell=True, capture_output=True, text=True).stdout.strip()
    if not active_pid_result:
     self.is_globally_disabled = False
     continue

    active_pid = active_pid_result

    ps_cmd = f"ps -u {self.user} -o pid,comm"
    processes = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True).stdout

    is_exe = False
    for line in processes.splitlines():
     if line.strip().startswith(active_pid):
      if ".exe" in line.lower() and "winword.exe" not in line.lower():
       is_exe = True
       break
    self.is_globally_disabled = is_exe
   except Exception:
    self.is_globally_disabled = False

 def _on_press(self, key):  # Основной обработчик нажатий клавиш
  f2 = threading.Thread(target=search_image, args=())
  f2.daemon = True  # Устанавливаем поток как демон
  f2.start()  # Запускаем поток

  if time.time() - self.last_key_press_time < 0.05 or self.is_globally_disabled:
   self.last_key_press_time = time.time()
   return
  self.last_key_press_time = time.time()

  if self.swit:
   return

  try:
   key_str = key.char
  except AttributeError:
   key_str = str(key).replace("'", "").replace(" ", "")

  if key == keyboard.Key.backspace:
   if self.current_word:
    self.current_word = self.current_word[:-1]
    self.key_sequence = self.key_sequence[:-1]
    self.run_suggestion_logic()
   else:
    self._hide_suggestions()
   return

  if key in {keyboard.Key.space, keyboard.Key.enter}:
   if self.is_abbreviation_suggestion_active and self.suggestions:
    self._replace_word(self.suggestions[0], extra_backspace=1)
   else:
    self._hide_suggestions()
   return

  control_keys = {
   keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.alt_l, keyboard.Key.alt_r,
   keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.tab, keyboard.Key.caps_lock,
   keyboard.Key.left, keyboard.Key.right, keyboard.Key.up, keyboard.Key.down,
   keyboard.Key.home, keyboard.Key.end, keyboard.Key.delete, keyboard.Key.esc,
   keyboard.Key.cmd, keyboard.Key.num_lock, keyboard.Key.page_up, keyboard.Key.page_down,
   keyboard.Key.insert, keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
   keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8, keyboard.Key.f9,
   keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12
  }
  if key in control_keys or key_str in {'.', ',', '\\', '/', '\'', '"', '<', '>', '?', '~', ':', ';', '{', '}', '[', ']', '0'}:
   self._hide_suggestions()
   return

  if self.suggestions and key_str in "123456" and self.is_autocomplete_active and not self.is_abbreviation_suggestion_active:
   index = int(key_str) - 1
   if index < len(self.suggestions):
    word_to_insert = self.suggestions[index]
    self._replace_word(word_to_insert, extra_backspace=1)
    return

  if hasattr(key, 'char') and key.char and key.char.isprintable() and key_str not in {"+", "-", "*", "/"}:
   key_char = key.char
   trans_key = self._get_translated_key(key_char)
   self.key_sequence += trans_key
   layout = self._get_current_keyboard_layout()
   displayed_char = self.en_to_ru_layout.get(key_char, key_char) if layout == "en" else key_char
   self.current_word += displayed_char
   if len(self.key_sequence) > self.longest_abbreviation_length:
    self.key_sequence = self.key_sequence[1:]
    self.current_word = self.current_word[1:]
   self.run_suggestion_logic()

 def run_suggestion_logic(self):
  # Запускает логику поиска и отображения подсказок
  abbreviation_match = self.check_for_abbreviation()
  if abbreviation_match:
   self.abbrev_res = abbreviation_match
   self.swit = True
   self.root.after(0, self._show_abbrev_tooltip)
   self.start_abbrev_listener_thread()
   return
  else:
   self.is_abbreviation_suggestion_active = False
   self.suggestions = self._find_word_suggestions(self.current_word)

  if self.suggestions:
   self.root.after(0, self._update_suggestions_ui)
  else:
   self._hide_suggestions()

 def check_for_abbreviation(self):
  # Проверяет, соответствует ли текущее слово аббревиатуре
  normalized = self.key_sequence
  self.matched_abbrev_key = None
  for abbrev_key in self.sorted_abbrevs:
   if len(normalized) >= len(abbrev_key) and normalized[-len(abbrev_key):] == abbrev_key:
    self.matched_abbrev_key = abbrev_key
    return self.normalized_abbrevs[abbrev_key]
  return None

 def _on_click(self, x, y, button, pressed):  # Обработчик кликов мыши для скрытия подсказок
  if pressed:
   self._hide_suggestions()

 def start(self):  # Запускает все слушатели и главный цикл программы
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

 ABS_PATH = os.path.dirname(os.path.abspath(__file__))
 abbreviations_file = os.path.join(ABS_PATH, "dictionary of substitutions.json")
 words_file = os.path.join(ABS_PATH, "words.txt")

 if not os.path.exists(abbreviations_file):
  print(f"Ошибка: Файл аббревиатур не найден по пути: {abbreviations_file}")
  sys.exit(1)
 if not os.path.exists(words_file):
  print(f"Ошибка: Файл со словарем не найден по пути: {words_file}")
  sys.exit(1)

 app = SmartTyper(
  abbreviations_path=abbreviations_file,
  words_path=words_file
 )
 try:
  app.start()
 except KeyboardInterrupt:
  print("SmartTyper остановлен.")

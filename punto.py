import json, os, re, subprocess, threading, time, sys, tkinter as tk, pyautogui
from tkinter import Tk, Toplevel, Label, Frame
from pynput import mouse, keyboard

def find_nemo():  #Checks if the active window is Nemo file manager.#
  get_main_id = '''#!/bin/bash
  active_window_id=$(xdotool getactivewindow 2>/dev/null)
  if [ -n "$active_window_id" ]; then
    process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
    echo "$process_id_active"
  else
    echo "0"
  fi
  exit'''
  result1 = subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip()  #  Получаем ID активного окна
  process_id_active = int(result1.splitlines()[0])  #  Преобразуем результат в целое число
  result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout  #  Получаем список процессов
  for line in result.splitlines():  #  Перебираем строки вывода
    if 'nemo' in line:  #  Ищем процесс nemo
      parts = line.split()  #  Разбиваем строку на части
      pid = int(parts[1])  #  Получаем PID процесса
      cmd = ' '.join(parts[10:]).replace(" ", "")  #  Получаем команду процесса
      if 'nemo' in cmd and process_id_active == pid:  #  Проверяем, совпадает ли PID с активным окном
        return True
  return False

def search_image():  #Searches for specific images on screen and simulates Enter if found in Nemo.#
  try:
    s = f'''#!/bin/bash
    xte 'keydown Return' 'keyup Return'    '''
    region = (1400, 100, 1500, 900)  #  Область поиска изображения
    image_path = 'Search button.png'  #  Путь к изображению кнопки поиска
    loc = pyautogui.locateOnScreen(image_path, confidence=0.25, region=region)  #  Ищем кнопку поиска
    region1 = (268, 44, 182, 108)  #  Область поиска текста
    image_path1 = 'Search text.png'  #  Путь к изображению текста поиска
    loc1 = pyautogui.locateOnScreen(image_path1, confidence=0.2, region=region1)  #  Ищем текст поиска
    if loc and loc1 and find_nemo(): # Если обе картинки найдены и активное окно — Nemo  print("1")
     subprocess.call(['bash', '-c', s, '_'])  #  Симулируем нажатие Enter
  except:
    pass  #  Игнорируем ошибки

class ToolTip:  #Manages tooltip display for abbreviation suggestions.#
  def __init__(self, widget, text):
    self.widget = widget  #  Сохраняем виджет
    self.tipwindow = None  #  Окно подсказки
    self.text = text  #  Текст подсказки
    self._showtip()  #  Показываем подсказку

  def _showtip(self):   #Internal method to show the tooltip window.#
    if self.tipwindow or not self.text:  #  Если окно уже существует или текст пуст
      return
    self.tipwindow = tw = Toplevel(self.widget)  #  Создаем новое окно
    tw.wm_overrideredirect(True)  #  Убираем рамку окна
    tw.wm_geometry("+0+0")  #  Устанавливаем позицию окна
    label = Label(tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))  #  Создаем метку с текстом
    label.pack(ipadx=1)  #  Размещаем метку

  def updatetext(self, text):    #Updates the text in the tooltip.#
    self.text = text  #  Обновляем текст
    if self.tipwindow:  #  Если окно существует
      for child in self.tipwindow.winfo_children():  #  Удаляем все дочерние элементы
        child.destroy()
      label = Label(self.tipwindow, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))  #  Создаем новую метку
      label.pack(ipadx=1)  #  Размещаем метку

  def hidetip(self):
    #Hides and destroys the tooltip.#
    if self.tipwindow:  #  Если окно существует
      self.tipwindow.destroy()  #  Уничтожаем окно
      self.tipwindow = None  #  Сбрасываем ссылку

class SmartTyper:  #Main class for smart typing with abbreviations and word suggestions.#
  def __init__(self, abbreviations_path, words_path):
    #Initializes the SmartTyper with paths to data files and loads resources.#
    self.abbreviations_path = abbreviations_path  #  Путь к файлу аббревиатур
    self.words_path = words_path  #  Путь к файлу слов
    self.abbreviations = {}  #  Словарь аббревиатур
    self.normalized_abbrevs = {}  #  Нормализованные аббревиатуры
    self.sorted_abbrevs = []  #  Отсортированные аббревиатуры
    self.longest_abbreviation_length = 0  #  Длина самой длинной аббревиатуры
    self.word_text_data = ""  #  Текстовые данные словаря
    self.ru_to_en_layout = {  #  Словарь для перевода раскладки с русской на английскую
      'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
      'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k',
      'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
      'б': ',', 'ю': '.', '.': '/', 'ё': '`', 'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y',
      'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}', 'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F',
      'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"', 'Я': 'Z', 'Ч': 'X', 'С': 'C',
      'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>', ',': '?', 'Ё': '~'    }
    self.en_to_ru_layout = {  #  Словарь для перевода раскладки с английской на русскую
      'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
      'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', 'z': 'я',
      'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', '[': 'х', ']': 'ъ', ';': 'ж', "'": 'э',
      ',': 'б', '.': 'ю', '`': 'ё', 'Q': 'Й', 'W': 'Ц', 'E': 'У', 'R': 'К', 'T': 'Е', 'Y': 'Н', 'U': 'Г',
      'I': 'Ш', 'O': 'Щ', 'P': 'З', 'A': 'Ф', 'S': 'Ы', 'D': 'В', 'F': 'А', 'G': 'П', 'H': 'Р', 'J': 'О',
      'K': 'Л', 'L': 'Д', 'Z': 'Я', 'X': 'Ч', 'C': 'С', 'V': 'М', 'B': 'И', 'N': 'Т', 'M': 'Ь'    }
    self._load_data()  #  Загружаем данные
    self.current_word = ""  #  Текущее слово
    self.key_sequence = ""  #  Последовательность нажатых клавиш
    self.matched_abbrev_key = ""  #  Совпавшая аббревиатура
    self.is_abbreviation_active = False  #  Флаг активности аббревиатуры
    self.suggestions = []  #  Список предложений
    self.abbrev_res = ""  #  Результат расширения аббревиатуры
    self.tooltip = None  #  Подсказка
    self.tooltip_root = None  #  Корневое окно подсказки
    self.abbrev_listener = None  #  Слушатель аббревиатур
    self.last_key_press_time = time.time()  #  Время последнего нажатия клавиши
    self.user = self._get_current_user()  #  Текущий пользователь
    self.swit = False  #  Флаг переключения
    self._setup_ui()  #  Настраиваем интерфейс

  def _load_data(self):  #Loads abbreviations from JSON and words from text file.#
    if os.path.exists(self.abbreviations_path):  #  Если файл аббревиатур существует
      with open(self.abbreviations_path, 'r', encoding='utf-8') as json_file:  #  Открываем файл
        self.abbreviations = json.load(json_file)  #  Загружаем аббревиатуры
        if self.abbreviations:  #  Если аббревиатуры есть
          for k, v in self.abbreviations.items():  #  Перебираем их
            norm_k = ''.join(self.ru_to_en_layout.get(c.lower(), c.lower()) for c in k)  #  Нормализуем ключ
            self.normalized_abbrevs[norm_k] = v  #  Сохраняем нормализованную аббревиатуру
          self.longest_abbreviation_length = len(max(self.normalized_abbrevs.keys(), key=len))  #  Находим длину самой длинной аббревиатуры
          self.sorted_abbrevs = sorted(self.normalized_abbrevs.keys(), key=len, reverse=True)  #  Сортируем аббревиатуры по длине
    if os.path.exists(self.words_path):  #  Если файл слов существует
      with open(self.words_path, 'r', encoding="cp1251", errors='ignore') as f:  #  Открываем файл
        self.word_text_data = f.read()  #  Читаем текст

  def _get_current_user(self):    #Retrieves the current Linux user name.#
    script = '#!/bin/bash\necho $(whoami)\nexit;'  #  Скрипт для получения имени пользователя
    return subprocess.run(['bash'], input=script, stdout=subprocess.PIPE, text=True).stdout.strip()  #  Запускаем скрипт и возвращаем результат

  def _setup_ui(self):    #Sets up the Tkinter UI for suggestion display.#
    self.root = Tk()  #  Создаем корневое окно
    self.root.overrideredirect(True)  #  Убираем рамку окна
    self.root.attributes("-topmost", True)  #  Делаем окно поверх всех
    self.root.withdraw()  #  Скрываем окно
    frame = Frame(self.root, borderwidth=0)  #  Создаем фрейм
    frame.pack(fill=tk.X)  #  Размещаем фрейм
    self.suggestion_labels = [Label(frame, text="", font='Times 14') for _ in range(6)]  #  Создаем метки для предложений
    for label in self.suggestion_labels:  #  Размещаем метки
      label.pack(side=tk.LEFT, padx=3, fill=tk.X, expand=False)

  def _get_current_keyboard_layout(self): #Detects current keyboard layout (en or ru) using setxkbmap.#
    try:
      result = subprocess.run(['setxkbmap', '-query'], capture_output=True, text=True)  #  Запрашиваем текущую раскладку
      if result.returncode == 0:  #  Если запрос успешен
        if 'layout:   us' in result.stdout or 'layout:   en' in result.stdout:  #  Если раскладка английская
          return "en"
        elif 'layout:   ru' in result.stdout:  #  Если раскладка русская
          return "ru"
    except Exception:
      pass
    return "ru"  #  По умолчанию русская раскладка

  def _get_translated_key(self, key_char):
    #Translates key to English layout equivalent based on current layout.#
    ch = key_char.lower()  #  Приводим символ к нижнему регистру
    layout = self._get_current_keyboard_layout()  #  Получаем текущую раскладку
    if layout == "ru":  #  Если раскладка русская
      return self.ru_to_en_layout.get(ch, ch)  #  Переводим символ в английскую раскладку
    else:
      return ch  #  Возвращаем символ без изменений

  def _type_text(self, text):   #Types text character by character with delays.#
    for char in text:  #  Перебираем символы текста
      time.sleep(0.1)  #  Задержка перед нажатием
      if char == ' ':  #  Если символ — пробел
        pyautogui.press('space')  #  Нажимаем пробел
      else:
        subprocess.call(['xdotool', 'type', '--delay', '9', char])  #  Печатаем символ

  def _replace_word(self, new_word, extra_backspace=0):   #Replaces current word with new one by backspacing and typing.#
    self.swit=True
    backspace_count = len(self.current_word) + extra_backspace  #  Количество нажатий Backspace
    for _ in range(backspace_count):  #  Нажимаем Backspace
      subprocess.run(['xte', 'key BackSpace'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      time.sleep(0.45)
    t = threading.Thread(target=self._type_text, args=(new_word,))
    t.start()  # Запускаем поток для печати нового слова

    self._hide_suggestions()  #  Скрываем предложения
    self.current_word=""
    t.join()
    self.swit=False

  def _do_replace_abbrev(self):  #Replaces abbreviation with its expansion.#
    self.hide_abbrev_tooltip()  #  Скрываем подсказку
    if self.abbrev_res:  #  Если есть результат расширения аббревиатуры
      backspace_count = len(self.current_word) + 1  #  Количество нажатий Backspace
      for _ in range(backspace_count):  #  Нажимаем Backspace
        subprocess.run(['xte', 'key BackSpace'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.35)
      t = threading.Thread(target=self._type_text, args=(self.abbrev_res,))  #  Запускаем поток для печати расширения
      t.start()
      t.join()
      self.current_word = ""  #  Сбрасываем текущее слово
      self.key_sequence = ""  #  Сбрасываем последовательность клавиш
      self.matched_abbrev_key = ""  #  Сбрасываем совпавшую аббревиатуру

  def _find_word_suggestions(self, prefix):   #Finds word suggestions starting with the given prefix.#
    if not prefix:  #  Если префикс пуст
      self.root.withdraw()  #  Скрываем окно
      return []
    try:
      pattern_lower = r'\b' + re.escape(prefix.lower()) + r'[а-яё]*\s'  #  Шаблон для поиска слов с маленькой буквы
      pattern_cap = r'\b' + re.escape(prefix.capitalize()) + r'[а-яё]*\s'  #  Шаблон для поиска слов с большой буквы
      matches = re.findall(pattern_lower, self.word_text_data) + re.findall(pattern_cap, self.word_text_data)  #  Ищем совпадения
      longer_matches = [m.rstrip() for m in matches if len(m) > len(prefix)+1]  #  Оставляем только те, что длиннее префикса
      return sorted(set(longer_matches), key=len)  #  Возвращаем уникальные и отсортированные по длине совпадения
    except Exception:
      return []

  def _update_suggestions_ui(self):    #Updates and displays the suggestion UI.#
    for label in self.suggestion_labels:  #  Очищаем метки
      label.config(text="")
    if not self.suggestions:  #  Если предложений нет
      self.root.withdraw()  #  Скрываем окно
      return
    total_width = 60  #  Начальная ширина окна
    for i, word in enumerate(self.suggestions[:6]):  #  Перебираем первые 6 предложений
      display_text = f"{word}"  #  Текст для отображения
      self.suggestion_labels[i].config(text=display_text)  #  Устанавливаем текст метки
      total_width += len(display_text) * 12  #  Увеличиваем ширину окна
    self.root.geometry(f"{total_width}x25+700+1010")  #  Устанавливаем геометрию окна
    self.root.deiconify()  #  Показываем окно

  def _hide_suggestions(self):
    #Hides suggestions and resets state.#
    self.current_word = ''  #  Сбрасываем текущее слово
    self.key_sequence = ''  #  Сбрасываем последовательность клавиш
    self.suggestions = []  #  Сбрасываем предложения
    self.is_abbreviation_active = False  #  Сбрасываем флаг активности аббревиатуры
    self.matched_abbrev_key = ""  #  Сбрасываем совпавшую аббревиатуру
    self.root.withdraw()  #  Скрываем окно

  def _show_abbrev_tooltip(self):
    #Shows tooltip for abbreviation expansion.#
    try:
      if self.tooltip_root:  #  Если корневое окно подсказки существует
        self.tooltip_root.destroy()  #  Уничтожаем его
    except tk.TclError:
      pass
    self.tooltip_root = Toplevel(self.root)  #  Создаем новое корневое окно
    self.tooltip_root.withdraw()  #  Скрываем окно
    self.tooltip = ToolTip(self.tooltip_root, self.abbrev_res)  #  Создаем подсказку

  def _update_abbrev_tooltip(self):   #Updates text in abbreviation tooltip.#
    if self.tooltip and self.abbrev_res:  #  Если подсказка и результат расширения существуют
      self.tooltip.updatetext(self.abbrev_res)  #  Обновляем текст подсказки

  def hide_abbrev_tooltip(self):    #Hides abbreviation tooltip and stops listener.#
    if self.tooltip:  #  Если подсказка существует
      self.tooltip.hidetip()  #  Скрываем подсказку
      self.tooltip = None  #  Сбрасываем ссылку
    if self.tooltip_root:  #  Если корневое окно существует
      self.tooltip_root.destroy()  #  Уничтожаем окно
      self.tooltip_root = None  #  Сбрасываем ссылку
    if self.abbrev_listener:  #  Если слушатель существует
      try:
        self.abbrev_listener.stop()  #  Останавливаем слушатель
      except:
        pass
      self.abbrev_listener = None  #  Сбрасываем ссылку
    self.swit = False  #  Сбрасываем флаг

  def start_abbrev_listener_thread(self):   #Starts thread for listening to abbreviation confirmation.#
    def inner():
      def on_press2(key):
        try:
          key_str = str(key).replace(" ", "").replace("'", "")  #  Преобразуем нажатую клавишу в строку
          if hasattr(key, 'char') and key.char and key.char.isprintable() and key_str not in {"+", "-", "*", "/"}:  #  Если это печатный символ
            key_char = key.char  #  Получаем символ
            trans_key = self._get_translated_key(key_char)  #  Переводим символ
            self.key_sequence += trans_key  #  Добавляем в последовательность
            layout = self._get_current_keyboard_layout()  #  Получаем раскладку
            displayed_char = self.en_to_ru_layout.get(key_char, key_char) if layout == "en" else key_char  #  Получаем отображаемый символ
            self.current_word += displayed_char  #  Добавляем в текущее слово
            if len(self.key_sequence) > self.longest_abbreviation_length:  #  Если последовательность слишком длинная
              self.key_sequence = self.key_sequence[1:]  #  Укорачиваем последовательность
              self.current_word = self.current_word[1:]  #  Укорачиваем текущее слово
            match = self.check_for_abbreviation()  #  Ищем совпадение с аббревиатурой
            if match:  #  Если совпадение найдено
              self.abbrev_res = match  #  Сохраняем результат
              self.root.after(0, self._update_abbrev_tooltip)  #  Обновляем подсказку
            else:  #  Если совпадение не найдено
              self.root.after(0, self.hide_abbrev_tooltip)  #  Скрываем подсказку
              self.root.after(0, lambda: self.abbrev_listener.stop() if self.abbrev_listener else None)  #  Останавливаем слушатель
              self.swit = False  #  Сбрасываем флаг
              return False
            return True
          elif key_str == "Key.space":  #  Если нажали пробел
            self.root.after(0, self._do_replace_abbrev)  #  Заменяем аббревиатуру
            self.root.after(0, lambda: self.abbrev_listener.stop() if self.abbrev_listener else None)  #  Останавливаем слушатель
            return False
          else:  #  Если нажали другую клавишу
            self.root.after(0, self.hide_abbrev_tooltip)  #  Скрываем подсказку
            self.root.after(0, lambda: self.abbrev_listener.stop() if self.abbrev_listener else None)  #  Останавливаем слушатель
            self.swit = False  #  Сбрасываем флаг
            return False
        except Exception:
          return True
      self.abbrev_listener = keyboard.Listener(on_press=on_press2)  #  Создаем слушатель
      self.abbrev_listener.start()  #  Запускаем слушатель
      self.abbrev_listener.join()  #  Ожидаем завершения
    t = threading.Thread(target=inner, daemon=True)  #  Создаем поток
    t.start()  #  Запускаем поток

  def _check_active_window_loop(self):
    #Continuously checks active window to enable/disable suggestions.#
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
      while True:  #  Бесконечный цикл
       time.sleep(1)  #  Задержка
       process_id = int(subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip())  #  Получаем ID активного процесса
       result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout  #  Получаем список процессов
       lines = [line for line in result.splitlines() if self.user in line]  #  Фильтруем строки по пользователю
       pattern = r"(\.exe|\.EXE)"  #  Шаблон для поиска .exe файлов
       found = False
       for line in lines:  #  Перебираем строки
        dir_process_name = line.split(maxsplit=10)[10].replace('\\', '/')  #  Получаем имя процесса
        if re.search(pattern, dir_process_name) and process_id == int(line.split()[1]):  #  Если найден .exe файл и PID совпадает
          file_path_lower = dir_process_name.lower()  #  Приводим имя к нижнему регистру
          if ".exe" in file_path_lower and "winword.exe" not in file_path_lower:  #  Если это не WinWord
           self.swit = True  #  Устанавливаем флаг
           found = True  #  Помечаем, что найдено
           break
       if not found:  #  Если не найдено
         self.swit = False  #  Сбрасываем флаг
    except Exception as e:
      print(e)  #  Печатаем ошибку

  def _on_press(self, key):    #Handles key press events for suggestions and replacements.#
    key_str = str(key).replace("'", "").replace(" ", "")  # Преобразуем клавишу в строку
    if key_str =="Key.enter":
     return True
    threading.Thread(target=search_image, daemon=True).start()  #  Запускаем поиск изображения в потоке
    if self.swit or time.time() - self.last_key_press_time < 0.05:  #  Если флаг установлен или нажатие слишком быстрое
      self.last_key_press_time = time.time()  #  Обновляем время последнего нажатия
      return True
    self.last_key_press_time = time.time()  #  Обновляем время последнего нажатия

    if key == keyboard.Key.backspace:  #  Если нажали Backspace
      if self.current_word:  #  Если текущее слово не пустое
        self.current_word = self.current_word[:-1]  #  Удаляем последний символ
        self.key_sequence = self.key_sequence[:-1]  #  Удаляем последний символ из последовательности
        self.run_suggestion_logic()  #  Запускаем логику предложений
      else:
        self._hide_suggestions()  #  Скрываем предложения
      return
    if key == keyboard.Key.space:  #  Если нажали пробел или Enter
      if self.is_abbreviation_active and self.suggestions:  #  Если активна аббревиатура и есть предложения
        self._hide_suggestions()  # Скрываем предложения
        self._replace_word(self.suggestions[0], extra_backspace=1)  # Заменяем слово
        self.run_suggestion_logic()  # Запускаем логику предложений0
      else:
        self._hide_suggestions()  #  Скрываем предложения
      return
    control_keys = { keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.alt_l, keyboard.Key.alt_r, #  Список управляющих клавиш
      keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.tab, keyboard.Key.caps_lock,
      keyboard.Key.left, keyboard.Key.right, keyboard.Key.up, keyboard.Key.down,
      keyboard.Key.home, keyboard.Key.end, keyboard.Key.delete, keyboard.Key.esc,
      keyboard.Key.cmd, keyboard.Key.num_lock, keyboard.Key.page_up, keyboard.Key.page_down,
      keyboard.Key.insert, keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
      keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8, keyboard.Key.f9,
      keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12    }
    if key in control_keys or key_str in {'.', ',', '\\', '/', '\'', '"', '<', '>', '?', '~', ':', ';', '{', '}', '[', ']', '0'}:  #  Если нажали управляющую клавишу или специальный символ
      self._hide_suggestions()  #  Скрываем предложения
      return
    if self.suggestions and key_str in "123456" and not self.is_abbreviation_active:  #  Если есть предложения и нажали цифру
      index = int(key_str) - 1  #  Получаем индекс
      if index < len(self.suggestions):  #  Если индекс корректен
        self._replace_word(self.suggestions[index], extra_backspace=1)  #  Заменяем слово
        return
    if hasattr(key, 'char') and key.char and key.char.isprintable() and key_str not in {"+", "-", "*", "/"}:  #  Если нажали печатный символ
      key_char = key.char  #  Получаем символ
      trans_key = self._get_translated_key(key_char)  #  Переводим символ
      self.key_sequence += trans_key  #  Добавляем в последовательность
      layout = self._get_current_keyboard_layout()  #  Получаем раскладку
      displayed_char = self.en_to_ru_layout.get(key_char, key_char) if layout == "en" else key_char  #  Получаем отображаемый символ
      self.current_word += displayed_char  #  Добавляем в текущее слово
      if len(self.key_sequence) > self.longest_abbreviation_length:  #  Если последовательность слишком длинная
        self.key_sequence = self.key_sequence[1:]  #  Укорачиваем последовательность
        self.current_word = self.current_word[1:]  #  Укорачиваем текущее слово
      self.run_suggestion_logic()  #  Запускаем логику предложений

  def run_suggestion_logic(self):  #Runs logic to check for abbreviations or word suggestions.#
    abbreviation_match = self.check_for_abbreviation()  #  Ищем совпадение с аббревиатурой
    if abbreviation_match:  #  Если совпадение найдено
      self.abbrev_res = abbreviation_match  #  Сохраняем результат
      self.swit = True  #  Устанавливаем флаг
      self.root.after(0, self._show_abbrev_tooltip)  #  Показываем подсказку
      self.start_abbrev_listener_thread()  #  Запускаем слушатель аббревиатур
      return
    self.is_abbreviation_active = False  #  Сбрасываем флаг активности аббревиатуры
    self.suggestions = self._find_word_suggestions(self.current_word)  #  Ищем предложения
    if self.suggestions:  #  Если предложения есть
      self.root.after(0, self._update_suggestions_ui)  #  Обновляем интерфейс предложений
    else:
      self._hide_suggestions()  #  Скрываем предложения

  def check_for_abbreviation(self):#   #Checks if current key sequence matches an abbreviation.#
    normalized = self.key_sequence  #  Нормализованная последовательность
    self.matched_abbrev_key = None  #  Сбрасываем совпавшую аббревиатуру
    for abbrev_key in self.sorted_abbrevs:  #  Перебираем аббревиатуры
      if len(normalized) >= len(abbrev_key) and normalized[-len(abbrev_key):] == abbrev_key:  #  Если последовательность совпадает
        self.matched_abbrev_key = abbrev_key  #  Сохраняем ключ
        return self.normalized_abbrevs[abbrev_key]  #  Возвращаем расширение
    return None  #  Если совпадений нет

  def _on_click(self, x, y, button, pressed):    #Handles mouse clicks to hide suggestions.#
    if pressed:  #  Если нажали кнопку мыши
      self._hide_suggestions()  #  Скрываем предложения

  def start(self):  #Starts the application listeners and main loop.#
    window_checker_thread = threading.Thread(target=self._check_active_window_loop, daemon=True)  #  Создаем поток для проверки активного окна
    window_checker_thread.start()  #  Запускаем поток
    keyboard_listener = keyboard.Listener(on_press=self._on_press)  #  Создаем слушатель клавиатуры
    mouse_listener = mouse.Listener(on_click=self._on_click)  #  Создаем слушатель мыши
    keyboard_listener.start()  #  Запускаем слушатель клавиатуры
    mouse_listener.start()  #  Запускаем слушатель мыши
    self.root.mainloop()  #  Запускаем главный цикл Tkinter
    keyboard_listener.stop()  #  Останавливаем слушатель клавиатуры
    mouse_listener.stop()  #  Останавливаем слушатель мыши
    keyboard_listener.join()  #  Ожидаем завершения слушателя клавиатуры
    mouse_listener.join()  #  Ожидаем завершения слушателя мыши

if __name__ == "__main__":
  ABS_PATH = os.path.dirname(os.path.abspath(__file__))  #  Получаем абсолютный путь к директории скрипта
  abbreviations_file = os.path.join(ABS_PATH, "dictionary of substitutions.json")  #  Путь к файлу аббревиатур
  words_file = os.path.join(ABS_PATH, "words.txt")  #  Путь к файлу слов
  if not os.path.exists(abbreviations_file):  #  Если файл аббревиатур не существует
    print(f"Ошибка: Файл аббревиатур не найден по пути: {abbreviations_file}")  #  Печатаем ошибку
    sys.exit(1)  #  Завершаем программу
  if not os.path.exists(words_file):  #  Если файл слов не существует
    print(f"Ошибка: Файл со словарем не найден по пути: {words_file}")  #  Печатаем ошибку
    sys.exit(1)  #  Завершаем программу
  app = SmartTyper(abbreviations_path=abbreviations_file, words_path=words_file)  #  Создаем экземпляр SmartTyper
  try:
    app.start()  #  Запускаем приложение
  except KeyboardInterrupt:
    print("SmartTyper остановлен.")  #  Печатаем сообщение об остановке

import json, os, re, subprocess, threading, time, sys, bisect, traceback, pyatspi, tkinter as tk, glob
from select import select
from tkinter import Tk, Toplevel, Label, Frame
from pynput import mouse, keyboard
from gi.repository import GLib

HAVE_EVDEV = False
try:
 from evdev import ecodes, UInput, InputDevice, list_devices
 HAVE_EVDEV = True
except Exception:
 pass

ENTRY_NAMES = ("file_search_entry", "content_search_entry")
SEARCH_LABEL_KEYWORDS = ("поиск файлов", "содержит", "search files", "contains", "поиск", "search", "find")
DEBOUNCE_MS = 500  # Уменьшили с 1500 мс для более отзывчивого поиска в Nemo
COOLDOWN_SEC = 0.3  # Уменьшили с 1.0 сек для быстрой реакции

# Сопоставление evdev-кодов клавиш (QWERTY) -> РУССКАЯ буква (раскладка ЙЦУКЕН).
# Значения русские, т.к. словарь подсказок (words.txt) и аббревиатуры — русские:
# current_word обязан собираться кириллицей, иначе подсказки всегда «счёт=0».
# Буквы ж,э,х,ъ,б,ю,ё живут на «пунктуационных» клавишах (; ' [ ] , . `) —
# они тоже включены сюда и перехватываются ДО ветки пунктуации в слушателе.
# При латинской раскладке слушатель сам переведёт букву в латиницу
# через ru_to_en_layout (з -> p), как её раньше отдавал pynput.
_EVDEV_LETTERS = {
 ecodes.KEY_Q:'й', ecodes.KEY_W:'ц', ecodes.KEY_E:'у', ecodes.KEY_R:'к', ecodes.KEY_T:'е',
 ecodes.KEY_Y:'н', ecodes.KEY_U:'г', ecodes.KEY_I:'ш', ecodes.KEY_O:'щ', ecodes.KEY_P:'з',
 ecodes.KEY_A:'ф', ecodes.KEY_S:'ы', ecodes.KEY_D:'в', ecodes.KEY_F:'а', ecodes.KEY_G:'п',
 ecodes.KEY_H:'р', ecodes.KEY_J:'о', ecodes.KEY_K:'л', ecodes.KEY_L:'д', ecodes.KEY_Z:'я',
 ecodes.KEY_X:'ч', ecodes.KEY_C:'с', ecodes.KEY_V:'м', ecodes.KEY_B:'и', ecodes.KEY_N:'т',
 ecodes.KEY_M:'ь', ecodes.KEY_LEFTBRACE:'х', ecodes.KEY_RIGHTBRACE:'ъ',
 ecodes.KEY_SEMICOLON:'ж', ecodes.KEY_APOSTROPHE:'э', ecodes.KEY_COMMA:'б',
 ecodes.KEY_DOT:'ю', ecodes.KEY_GRAVE:'ё', ecodes.KEY_BACKSLASH:'\\', ecodes.KEY_SLASH:'.',
}

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

class EvdevTyper:
 '''Печать текста напрямую через виртуальную клавиатуру (evdev UInput).
    Быстрее и надёжнее, чем xdotool type / pyautogui: нажатия идут в ядро,
    минуя X-специфичные инструменты. Может работать и под Wayland.
    Требует права доступа к /dev/uinput (обычно достаточно группы uinput).'''

 COMMON_MAP = {
  ' ': ecodes.KEY_SPACE, '\n': ecodes.KEY_ENTER, '\t': ecodes.KEY_TAB,
  '1': ecodes.KEY_1, '2': ecodes.KEY_2, '3': ecodes.KEY_3, '4': ecodes.KEY_4,
  '5': ecodes.KEY_5, '6': ecodes.KEY_6, '7': ecodes.KEY_7, '8': ecodes.KEY_8,
  '9': ecodes.KEY_9, '0': ecodes.KEY_0, '-': ecodes.KEY_MINUS, '=': ecodes.KEY_EQUAL,
  '\\': ecodes.KEY_BACKSLASH, '!': ecodes.KEY_1, '%': ecodes.KEY_5, '*': ecodes.KEY_8,
  '(': ecodes.KEY_9, ')': ecodes.KEY_0, '_': ecodes.KEY_MINUS, '+': ecodes.KEY_EQUAL
 }
 COMMON_SHIFT = set(['!', '%', '*', '(', ')', '_', '+'])

 EN_MAP = {
  'q': ecodes.KEY_Q, 'w': ecodes.KEY_W, 'e': ecodes.KEY_E, 'r': ecodes.KEY_R, 't': ecodes.KEY_T,
  'y': ecodes.KEY_Y, 'u': ecodes.KEY_U, 'i': ecodes.KEY_I, 'o': ecodes.KEY_O, 'p': ecodes.KEY_P,
  'a': ecodes.KEY_A, 's': ecodes.KEY_S, 'd': ecodes.KEY_D, 'f': ecodes.KEY_F, 'g': ecodes.KEY_G,
  'h': ecodes.KEY_H, 'j': ecodes.KEY_J, 'k': ecodes.KEY_K, 'l': ecodes.KEY_L, 'z': ecodes.KEY_Z,
  'x': ecodes.KEY_X, 'c': ecodes.KEY_C, 'v': ecodes.KEY_V, 'b': ecodes.KEY_B, 'n': ecodes.KEY_N,
  'm': ecodes.KEY_M
 }

 RU_MAP = {
  'й': ecodes.KEY_Q, 'ц': ecodes.KEY_W, 'у': ecodes.KEY_E, 'к': ecodes.KEY_R, 'е': ecodes.KEY_T,
  'н': ecodes.KEY_Y, 'г': ecodes.KEY_U, 'ш': ecodes.KEY_I, 'щ': ecodes.KEY_O, 'з': ecodes.KEY_P,
  'х': ecodes.KEY_LEFTBRACE, 'ъ': ecodes.KEY_RIGHTBRACE, 'ф': ecodes.KEY_A, 'ы': ecodes.KEY_S,
  'в': ecodes.KEY_D, 'а': ecodes.KEY_F, 'п': ecodes.KEY_G, 'р': ecodes.KEY_H, 'о': ecodes.KEY_J,
  'л': ecodes.KEY_K, 'д': ecodes.KEY_L, 'ж': ecodes.KEY_SEMICOLON, 'э': ecodes.KEY_APOSTROPHE,
  'я': ecodes.KEY_Z, 'ч': ecodes.KEY_X, 'с': ecodes.KEY_C, 'м': ecodes.KEY_V, 'и': ecodes.KEY_B,
  'т': ecodes.KEY_N, 'ь': ecodes.KEY_M, 'б': ecodes.KEY_COMMA, 'ю': ecodes.KEY_DOT, 'ё': ecodes.KEY_GRAVE
 }

 EN_ONLY_PUNCT_SHIFT = set(['@', '#', '$', '^', '&', '{', '}', '|', '<', '>', '~'])
 EN_ONLY_PUNCT = {
  '@': ecodes.KEY_2, '#': ecodes.KEY_3, '$': ecodes.KEY_4, '^': ecodes.KEY_6, '&': ecodes.KEY_7,
  '{': ecodes.KEY_LEFTBRACE, '}': ecodes.KEY_RIGHTBRACE, '|': ecodes.KEY_BACKSLASH,
  '<': ecodes.KEY_COMMA, '>': ecodes.KEY_DOT, '~': ecodes.KEY_GRAVE,
  '`': ecodes.KEY_GRAVE, '[': ecodes.KEY_LEFTBRACE, ']': ecodes.KEY_RIGHTBRACE
 }
 RU_ONLY_PUNCT_SHIFT = set(['№'])
 RU_ONLY_PUNCT = {'№': ecodes.KEY_3}

 PUNCT_EN_SHIFT = set(['?', ':', '"'])
 PUNCT_EN = {
  ',': ecodes.KEY_COMMA, '.': ecodes.KEY_DOT, '/': ecodes.KEY_SLASH,
  ';': ecodes.KEY_SEMICOLON, "'": ecodes.KEY_APOSTROPHE,
  '?': ecodes.KEY_SLASH, ':': ecodes.KEY_SEMICOLON, '"': ecodes.KEY_APOSTROPHE,
  '…': ecodes.KEY_DOT
 }
 PUNCT_RU_SHIFT = set([',', '/', ';', '?', ':', '"'])
 PUNCT_RU = {
  ',': ecodes.KEY_SLASH, '.': ecodes.KEY_SLASH, '/': ecodes.KEY_BACKSLASH,
  ';': ecodes.KEY_4, '?': ecodes.KEY_7, ':': ecodes.KEY_6, '"': ecodes.KEY_2,
  '…': ecodes.KEY_SLASH
 }

 def __init__(self, layout_getter):
  self.layout_getter = layout_getter
  self.ui = None
  self._orig_layout = 'ru'
  self._init_uinput()

 def _init_uinput(self):
  caps_keys = [
   ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_C, ecodes.KEY_D, ecodes.KEY_E,
   ecodes.KEY_F, ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_I, ecodes.KEY_J,
   ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_M, ecodes.KEY_N, ecodes.KEY_O,
   ecodes.KEY_P, ecodes.KEY_Q, ecodes.KEY_R, ecodes.KEY_S, ecodes.KEY_T,
   ecodes.KEY_U, ecodes.KEY_V, ecodes.KEY_W, ecodes.KEY_X, ecodes.KEY_Y,
   ecodes.KEY_Z, ecodes.KEY_SPACE, ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
   ecodes.KEY_COMMA, ecodes.KEY_DOT, ecodes.KEY_ENTER, ecodes.KEY_TAB,
   ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5,
   ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9, ecodes.KEY_0,
   ecodes.KEY_SEMICOLON, ecodes.KEY_APOSTROPHE, ecodes.KEY_GRAVE,
   ecodes.KEY_LEFTBRACE, ecodes.KEY_RIGHTBRACE, ecodes.KEY_BACKSLASH,
    ecodes.KEY_MINUS, ecodes.KEY_EQUAL, ecodes.KEY_SLASH, ecodes.KEY_BACKSPACE,
    ecodes.KEY_NUMLOCK, ecodes.KEY_KP0, ecodes.KEY_KP1, ecodes.KEY_KP2,
    ecodes.KEY_KP3, ecodes.KEY_KP4, ecodes.KEY_KP5, ecodes.KEY_KP6,
    ecodes.KEY_KP7, ecodes.KEY_KP8, ecodes.KEY_KP9, ecodes.KEY_KPDOT,
    ecodes.KEY_KPSLASH, ecodes.KEY_KPASTERISK, ecodes.KEY_KPMINUS,
    ecodes.KEY_KPPLUS, ecodes.KEY_KPENTER
   ]
  try:
   self.ui = UInput(
    {ecodes.EV_KEY: caps_keys},
    vendor=0x1234, product=0x5678,
    bustype=ecodes.BUS_USB,
    name="Smart-Virtual-Keyboard"
   )
   self.ui.syn()
  except Exception as e:
   print(f"[WARN] UInput не доступен ({e}), печать через него невозможна.")
   self.ui = None

 def _detect_us(self):
  try:
   result = subprocess.run("xset -q | grep 'LED mask' | awk '{print $10}'", shell=True, capture_output=True, text=True)
   mask = result.stdout.strip()
   if mask in ("00001002", "00001000", "00001003"):
    return True
  except Exception:
   pass
  try:
   result = subprocess.run("setxkbmap -query | grep layout", shell=True, capture_output=True, text=True)
   if "us" in result.stdout.strip().lower():
    return True
  except Exception:
   pass
  return False

 def _current_layout(self):
  if callable(self.layout_getter):
   try:
    return self.layout_getter()
   except Exception:
    pass
  return 'us' if self._detect_us() else 'ru'

 def _capslock_on(self):
  try:
   result = subprocess.run("xset -q | grep -A0 'LED mask' | awk '{print $10}'", shell=True, capture_output=True, text=True, timeout=2)
   mask_str = result.stdout.strip()
   if mask_str:
    mask = int(mask_str, 16)
    if mask & 0x00000004:
     return True
  except Exception:
   pass
  return False

 def _set_layout(self, lang):
  for _ in range(12):
   if self._current_layout() == lang:
    return True
   try:
    subprocess.run(["xte", "key ISO_Next_Group"], check=True, timeout=1)
   except Exception:
    pass
   time.sleep(0.35)
   if self._current_layout() == lang:
    return True
   time.sleep(0.1)
  return self._current_layout() == lang

 def _press(self, keycode, with_shift=False):
  if not self.ui:
   return False
  if with_shift:
   self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
   self.ui.syn()
  self.ui.write(ecodes.EV_KEY, keycode, 1)
  self.ui.syn()
  time.sleep(0.008)
  self.ui.write(ecodes.EV_KEY, keycode, 0)
  self.ui.syn()
  if with_shift:
   self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
   self.ui.syn()
  return True

 def type_char(self, ch):
  if not self.ui:
   return None
  layout = self._current_layout()
  lower = ch.lower()
  caps_on = self._capslock_on()

  if caps_on and lower in self.EN_MAP or (caps_on and lower in self.RU_MAP):
   effective_upper = not ch.isupper() and ch.isalpha()
  else:
   effective_upper = ch.isupper() and ch.isalpha()

  if ch == '…':
   if layout == 'us':
    return self._press(self.PUNCT_EN['…'], False)
   return self._press(self.PUNCT_RU['…'], True)

  if ch in self.COMMON_MAP:
   return self._press(self.COMMON_MAP[ch], ch in self.COMMON_SHIFT)

  if lower in self.RU_MAP:
   if layout != 'ru' and not self._set_layout('ru'):
    return None
   return self._press(self.RU_MAP[lower], effective_upper)

  if lower in self.EN_MAP:
   if layout != 'us' and not self._set_layout('us'):
    return None
   return self._press(self.EN_MAP[lower], effective_upper)

  if ch in self.EN_ONLY_PUNCT:
   if layout != 'us' and not self._set_layout('us'):
    return None
   return self._press(self.EN_ONLY_PUNCT[ch], ch in self.EN_ONLY_PUNCT_SHIFT)

  if ch in self.RU_ONLY_PUNCT:
   if layout != 'ru' and not self._set_layout('ru'):
    return None
   return self._press(self.RU_ONLY_PUNCT[ch], ch in self.RU_ONLY_PUNCT_SHIFT)

  if ch in self.PUNCT_EN or ch in self.PUNCT_RU:
   if layout == 'us':
    return self._press(self.PUNCT_EN[ch], ch in self.PUNCT_EN_SHIFT)
   return self._press(self.PUNCT_RU[ch], ch in self.PUNCT_RU_SHIFT)
  return None

 def type_text(self, text, delay=0.05):
  if not self.ui:
   return False
  for ch in text:
   self.type_char(ch)
   time.sleep(delay)
  return True

 def type_backspace(self, count=1):
  if not self.ui:
   return False
  for _ in range(count):
   self._press(ecodes.KEY_BACKSPACE, False)
   time.sleep(0.02)
  return True

class SmartTyper: # Основной класс для автозамены и подсказок
 def __init__(self, abbreviations_path, words_path):
  self.abbreviations_path = abbreviations_path
  self.words_path = words_path
  self.abbreviations = {}
  self.normalized_abbrevs = {}
  self.sorted_abbrevs = []
  self.longest_abbreviation_length = 0
  self.word_text_data = ""
  self.suggestion_cache = {}
  self.words_by_first = {}
  self.words_alpha_by_first = {}
  self.max_suggestions = 6
  self._layout_cache = "ru"
  self._layout_cache_time = 0.0

  self.ru_to_en_layout = { # Словарь для транслитерации с русской раскладки на английскую
   'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
   'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k',
   'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
   'б': ',', 'ю': '.', '.': '/', 'ё': '`', 'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P',
   'Х': '{', 'Ъ': '}', 'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"', 'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>', ',': '?', 'Ё': '~'
  }
  self.en_to_ru_layout = { # Словарь для транслитерации с английской раскладки на русскую
   'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
   'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д',
   'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', '[': 'х', ']': 'ъ', ';': 'ж', "'": 'э', ',': 'б', '.': 'ю', '`': 'ё',
   'Q': 'Й', 'W': 'Ц', 'E': 'У', 'R': 'К', 'T': 'Е', 'Y': 'Н', 'U': 'Г', 'I': 'Ш', 'O': 'Щ', 'P': 'З',
   'A': 'Ф', 'S': 'Ы', 'D': 'В', 'F': 'А', 'G': 'П', 'H': 'Р', 'J': 'О', 'K': 'Л', 'L': 'Д', 'Z': 'Я', 'X': 'Ч', 'C': 'С', 'V': 'М', 'B': 'И', 'N': 'Т', 'M': 'Ь'
  }

  # Состояние ATSPI для каждого окна Nemo: key = id(frame), value = [timer_id, last_text, cooldown_until]
  self.nemo_states = {}
  self._load_data() # Загружаем данные из файлов
  self.current_word = ""
  self.matched_abbrev_key = ""
  self.suggestions = []
  self.abbrev_res = ""
  self.tooltip = None
  self.tooltip_root = None
  self.last_key_press_time = time.time()
  self._last_key_id = ""
  self._last_key_time = time.time()
  self.user = self._get_current_user() # Получаем текущего пользователя
  self.disabled = False
  self.replacing = False
  # Виртуальная клавиатура для быстрой/надёжной печати (evdev UInput)
  self.py_typer = None
  if HAVE_EVDEV:
   try:
    self.py_typer = EvdevTyper(layout_getter=self._get_keyboard_layout)
   except Exception as e:
    print(f"[WARN] Не удалось инициализировать EvdevTyper: {e}")
  self._setup_ui() # Настраиваем интерфейс
  # Блокировка для защиты общих переменных от race conditions при быстром вводе
  self.state_lock = threading.Lock()
  # Состояние shift'а из evdev-событий (для передачи регистра буквы)
  self._evdev_shift = False

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
  self._build_word_index()

 def _build_word_index(self): # Строит индекс слов для быстрого поиска подсказок
  self.words_by_first = {}
  self.words_alpha_by_first = {}
  self.suggestion_cache = {}
  if not self.word_text_data:
   return
  words = re.findall(r'[а-яёА-ЯЁ]+', self.word_text_data)
  unique_words = {}
  for w in words:
   lw = w.lower()
   if lw and lw not in unique_words:
    unique_words[lw] = w
  for lw, w in unique_words.items():
   first = lw[0]
   if first not in self.words_by_first:
    self.words_by_first[first] = []
    self.words_alpha_by_first[first] = []
   self.words_by_first[first].append((len(lw), lw, w))
   self.words_alpha_by_first[first].append((lw, w))
  for first in self.words_by_first:
   self.words_by_first[first].sort()
   self.words_alpha_by_first[first].sort()

 def _get_current_user(self): # Получает имя текущего пользователя
  script = '#!/bin/bash\necho $(whoami)\nexit;'
  return subprocess.run(['bash'], input=script, stdout=subprocess.PIPE, text=True).stdout.strip()

 def _active_window_pid(self): # PID активного окна без xdotool (через python-xlib)
  try:
   from Xlib import display, X
   d = display.Display()
   root = d.screen().root
   aw = root.get_full_property(d.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType)
   if aw and aw.value:
    wid = aw.value[0]
    w = d.create_resource_object('window', wid)
    pid = w.get_full_property(d.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
    d.close()
    if pid and pid.value:
     return pid.value[0]
   else:
    d.close()
  except Exception:
   pass
  return None

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

 def _get_keyboard_layout(self):
  # Кэшируем результат на короткое время (0.3 c), чтобы не плодить subprocess на каждый символ
  now = time.time()
  if getattr(self, '_layout_cache_time', 0) and now - self._layout_cache_time < 0.3:
   return self._layout_cache
  layout = self._detect_keyboard_layout()
  self._layout_cache = layout
  self._layout_cache_time = now
  return layout

 def _detect_keyboard_layout(self):
  try:
   result = subprocess.run("xset -q | grep 'LED mask' | awk '{print $10}'", shell=True, capture_output=True, text=True)
   led_mask = result.stdout.strip()
   if led_mask == "00001002" or led_mask == "00001000":
    return "us"
   return "ru"
  except Exception:
   pass
  # Фолбэк: пробуем setxkbmap -query (работает и без xset)
  try:
   result = subprocess.run("setxkbmap -query | grep layout", shell=True, capture_output=True, text=True)
   out = result.stdout.strip().lower()
   if "us" in out:
    return "us"
  except Exception:
   pass
  return "ru"

 def _get_translated_key(self, key_char): # Возвращает транслитерированный символ
  ch = key_char.lower()
  layout = self._get_keyboard_layout()
  if layout == "ru":
   return ch
  else:
   return self.ru_to_en_layout.get(ch, ch)

 def clean(self):
  # Сбрасываем состояние сразу (thread-safe)
  self.current_word = ""
  self.matched_abbrev_key = ""
  self.suggestions = []
  # UI-очистку делегируем в GLib главный поток (исправляет RuntimeError)
  GLib.idle_add(self._do_hide_all)

 def _type_text_and_finish(self, text): # Печатает текст и сбрасывает флаг replacing
  try:
   if getattr(self.py_typer, 'ui', None):
    self.py_typer.type_text(text, delay=0.02)
   else:
    print("[WARN] evdev недоступен — печать замены невозможна.")
  finally:
   self.replacing = False

 def _backspace(self, count): # Удаляет символы BackSpace через evdev
  if self.py_typer and self.py_typer.ui:
   self.py_typer.type_backspace(count)
  else:
   print("[WARN] evdev недоступен — удаление не выполнено.")

 def _replace_word_async(self, new_word, extra_backspace=1): # Асинхронно заменяет слово
  if self.replacing:
   return
  self.replacing = True
  backspace_count = len(self.current_word) + extra_backspace
  self._backspace(backspace_count)
  t = threading.Thread(target=self._type_text_and_finish, args=(new_word,))
  t.start()
  self.clean()
  t.join()
  self.replacing = False

 def _do_replace_abbrev_async(self): # Асинхронно заменяет аббревиатуру
  if self.replacing or not self.abbrev_res:
   return
  self.replacing = True
  backspace_count = len(self.current_word)+1
  self._backspace(backspace_count)
  t = threading.Thread(target=self._type_text_and_finish, args=(self.abbrev_res,))
  self.clean()
  t.start()
  t.join()
  self.replacing = False

 # --- ATSPI Nemo Live Search ---
 def _panel_has_search_label(self, node): # Проверяет, есть ли среди прямых детей label'а подписи поиска
  try:
   for i in range(node.getChildCount()):
    try:
     child = node.getChildAtIndex(i)
     if child.getRole() == pyatspi.ROLE_LABEL:
      text = (child.name or "")
      try:
       q = child.queryText()
       if q:
        text += " " + (q.getText(0, -1) or "")
      except Exception:
       pass
      low = text.lower()
      if any(k in low for k in SEARCH_LABEL_KEYWORDS):
       return True
    except Exception:
     pass
  except Exception:
   pass
  return False

 def _is_nemo_search_entry(self, obj): # Надёжная идентификация поля поиска Nemo (имя может быть пустым)
  name = obj.name or ""
  if name in ENTRY_NAMES:
   return True
  cur = obj
  while cur:
   try:
    role = cur.getRole()
    if role in (pyatspi.ROLE_FRAME, pyatspi.ROLE_WINDOW, pyatspi.ROLE_DIALOG):
     break
    if role in (pyatspi.ROLE_TABLE, pyatspi.ROLE_TREE_TABLE, pyatspi.ROLE_ICON):
     # Поле внутри списка файлов — это переименование (F2), не поиск
     return False
   except Exception:
    pass
   if self._panel_has_search_label(cur):
    return True
   try:
    cur = cur.parent
   except Exception:
    break
  return False

 def on_text_changed(self, event): # Обработчик ATSPI-события text-changed: ловит ввод в поисковое поле Nemo
  obj = event.source
  if not obj:
   return

  # Проверяем, что это поле ввода в Nemo
  try:
   app = obj.getApplication()
   if not app or (app.name or "").lower() != "nemo":
    return
   if obj.getRole() != pyatspi.ROLE_TEXT:
    return

   if not self._is_nemo_search_entry(obj):
    return

   # Находим окно (frame) для per-window состояния
   frame = None
   cur = obj
   while cur:
    try:
     if cur.getRole() in (pyatspi.ROLE_FRAME, pyatspi.ROLE_DIALOG, pyatspi.ROLE_WINDOW):
      frame = cur
      break
    except:
     pass
    cur = cur.parent

   if not frame:
    return

   key = id(frame)

   # Отменяем предыдущий таймер для этого окна
   if key in self.nemo_states and self.nemo_states[key][0]:
    GLib.source_remove(self.nemo_states[key][0])

   # Функция, которая выполнится после паузы (debounce)
   def fire():
    try:
     if not obj:
      return

     # Проверяем, что объект всё ещё в фокусе и видим
     state = obj.getState()
     if not state.contains(pyatspi.STATE_FOCUSED):
      return
     if not state.contains(pyatspi.STATE_VISIBLE):
      return

     # Проверяем, что активное окно всё ещё принадлежит Nemo
     try:
      app_pid = app.get_process_id()
     except Exception:
      app_pid = None
     if app_pid is not None:
      active_pid = self._active_window_pid()
      if active_pid is not None and active_pid != app_pid:
       return

     text = obj.queryText().getText(0, -1) or ""
     if not text.strip():
      return

     # Проверяем cooldown и повтор текста
     now = time.time()
     if now < self.nemo_states.get(key, [None, "", 0.0])[2]:
      return
     last = self.nemo_states.get(key, [None, "", 0.0])[1]
     if text == last:
      return

     self.replacing = True
     # Обновляем состояние
     self.nemo_states[key] = [None, text, now + COOLDOWN_SEC]

     # Эмулируем Enter (evdev, без xte/xdotool)
     if self.py_typer and self.py_typer.ui:
      self.py_typer._press(ecodes.KEY_ENTER, False)
     time.sleep(0.1) # Ждём, чтобы эмулированный Enter успел дойти до _on_press
     self.replacing = False
    except Exception as e:
     print(f"Ошибка в fire: {e}")
     self.replacing = False
    finally:
     # Сбрасываем timer_id в состоянии
     if key in self.nemo_states:
      self.nemo_states[key][0] = None

   timer_id = GLib.timeout_add(DEBOUNCE_MS, fire)

   # Сохраняем состояние: [timer_id, last_text, cooldown_until]
   if key in self.nemo_states:
    self.nemo_states[key][0] = timer_id
   else:
    self.nemo_states[key] = [timer_id, "", 0.0]

  except Exception as e:
   print(f"Ошибка в on_text_changed: {e}")

 def _find_word_suggestions(self, prefix): # Ищет подсказки для введенного префикса
  if not prefix:
   return []
  prefix_lower = prefix.lower()
  if not prefix_lower:
   return []

  if prefix[:1].isupper():
   cache_key = prefix_lower + "|cap"
  else:
   cache_key = prefix_lower + "|low"

  if cache_key in self.suggestion_cache:
   return self.suggestion_cache[cache_key]
  if len(self.suggestion_cache) > 1000:
   self.suggestion_cache.clear()

  first = prefix_lower[0]
  alpha = self.words_alpha_by_first.get(first, [])
  if not alpha:
   self.suggestion_cache[cache_key] = []
   return []

  lo = bisect.bisect_left(alpha, (prefix_lower,))
  hi = bisect.bisect_left(alpha, (prefix_lower + chr(0x10ffff),))
  if lo >= hi:
   self.suggestion_cache[cache_key] = []
   return []

  res = []
  seen = set()
  need_cap = prefix[:1].isupper()
  count = hi - lo

  if count <= 5000:
   temp = []
   for lw, w in alpha[lo:hi]:
    if len(lw) >= len(prefix_lower):
     temp.append((len(lw), lw, w))
   temp.sort()
   for _len, lw, w in temp:
    out = w.capitalize() if need_cap else w.lower()
    if out not in seen:
     seen.add(out)
     res.append(out)
     if len(res) >= self.max_suggestions:
      break
  else:
   for _len, lw, w in self.words_by_first.get(first, []):
    if lw.startswith(prefix_lower) and len(lw) >= len(prefix_lower):
     out = w.capitalize() if need_cap else w.lower()
    if out not in seen:
     seen.add(out)
     res.append(out)
     if len(res) >= self.max_suggestions:
      break

  if prefix_lower and len(prefix_lower) == 1:
   res = [r for r in res if len(r) > 1]

  self.suggestion_cache[cache_key] = res
  return res

 def _update_suggestions_ui(self): # Обновляет интерфейс подсказок
  # Способ 1: принудительная полная обработка событий через update()
  # вместо update_idletasks() — гарантирует применение геометрии
  if self.tooltip and self.abbrev_res:
   self.tooltip.updatetext(self.abbrev_res)
  # ВАЖНО: эта проверка должна быть ВНЕ блока if self.tooltip —
  # раньше она была внутри (баг с отступом), из-за чего при отсутствии
  # tooltip/abbrev_res окно не скрывалось даже когда suggestions пуст.
  if not self.suggestions:
   self._hide_suggestions_window()
   return
  for label in self.suggestion_labels:
   label.config(text="")

  total_width = 60
  for i, word in enumerate(self.suggestions[:self.max_suggestions]):
   display_text = f"{word}"
   self.suggestion_labels[i].config(text=display_text)
   total_width += len(display_text) * 12

  # Сначала задаём геометрию, ПОТОМ делаем окно видимым.
  # deiconify только выводит из withdrawn; геометрию нужно применять
  # до или сразу после — иначе X11 может «потерять» изменение позиции.
  self.root.geometry(f"{total_width}x25+700+1010")
  self.root.deiconify()
  self.root.lift()
  # update() — полная обработка очереди событий X11 (включая ConfigureNotify),
  # update_idletasks() только idle-задачи и НЕ применяет смену позиции окна.
  self.root.update()

 def _hide_suggestions_window(self): # Надёжно скрывает окно подсказок
  try:
   # Очищаем лейблы, чтобы не показывался «старый» текст,
   # если окно мелькнёт перед изменением геометрии.
   for label in self.suggestion_labels:
    label.config(text="")
   # Не двигаем окно за экран (99999), а просто сжимаем до 1x1
   # на той же позиции — так X11 не «зависает» на старой позиции
   # и последующий geometry() применяется корректно.
   self.root.geometry("1x1+700+1010")
   self.root.update()
  except tk.TclError:
   try:
    self.root.withdraw()
   except tk.TclError:
    pass

 def _hide_suggestions(self): # Скрывает подсказки
  self.suggestions = []
  self.matched_abbrev_key = ""
  self._hide_suggestions_window()

 def _show_abbrev_tooltip(self): # Показывает подсказку для аббревиатуры
  if self.tooltip and self.tooltip_root and self.tooltip.tipwindow:
   self.tooltip.updatetext(self.abbrev_res)
   return
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
  try:
   if self.replacing:
    return
   match = self.check_for_abbreviation()
   if match:
    self.abbrev_res = match
    self._show_abbrev_tooltip()
   else:
    self.abbrev_res = ""
    self.hide_abbrev_tooltip()

   self.suggestions = self._find_word_suggestions(self.current_word)
   if self.suggestions:
    print(f"[SUGG] word='{self.current_word}' count={len(self.suggestions)} {self.suggestions}", flush=True)
    self._update_suggestions_ui()
   else:
    print(f"[SUGG-NONE] word='{self.current_word}' счёт=0 -> прячу окно", flush=True)
    for label in self.suggestion_labels:
     label.config(text="")
    self._hide_suggestions_window()
  except Exception:
   print("[EXC] исключение в _do_update_state:", flush=True)
   traceback.print_exc()

 def _do_hide_all(self): # Скрывает все подсказки
  self._hide_suggestions()
  self.hide_abbrev_tooltip()
  self.abbrev_res = ""

 def check_for_abbreviation(self): # Проверяет, совпадает ли ввод с аббревиатурой
  self.matched_abbrev_key = None
  if not self.current_word:
   return None
  if self.longest_abbreviation_length and len(self.current_word) > self.longest_abbreviation_length:
   return None

  abbre = ""
  for key_char in self.current_word:
   trans_key = self._get_translated_key(key_char)
   abbre += trans_key

  for abbrev_key in self.sorted_abbrevs:
   if len(self.current_word) == len(abbrev_key) and abbrev_key == abbre:
    self.matched_abbrev_key = abbrev_key
    return self.normalized_abbrevs[abbrev_key]
  return None

 def _check_active_window_loop(self): # Проверяет активное окно в цикле
  while True:
   try:
    found = False
    time.sleep(1)
    process_id = self._active_window_pid()
    if process_id is None:
     self.disabled = False
     continue
    result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout
    lines = [line for line in result.splitlines() if self.user in line]
    pattern = r"(\.exe|\.EXE)"
    for line in lines:
     dir_process_name = line.split(maxsplit=10)[10].replace('\\', '/')
     if re.search(pattern, dir_process_name) and process_id == int(line.split()[1]):
      file_path_lower = dir_process_name.lower()
      if (".exe" in file_path_lower or '/portproton/data/scripts/start.sh' in file_path_lower) and "winword.exe" not in file_path_lower:
       self.disabled = True
       self.current_word = ""
       self.suggestions = []
       self.abbrev_res = ""
       GLib.idle_add(self._do_hide_all)
       found = True
       break
    if not found:
     self.disabled = False
   except Exception as e:
    print(e)
    self.disabled = False
   pass

 def _evdev_find_keyboards(self):
  """Список физических клавиатур (отсекаем виртуальные, созданные скриптами)."""
  _list = []
  if not HAVE_EVDEV:
   return _list
  try:
   for path in glob.glob("/dev/input/event*"):
    try:
     dev = InputDevice(path)
     name = (dev.name or "").lower()
     if ("keyboard" in name or "logitech" in name or "at translate" in name
         or "корпус" in name) and "smart" not in name \
         and "mouse setting" not in name and "virtual" not in name:
      _list.append(dev)
    except Exception:
     continue
  except Exception:
   pass
  return _list

 def _evdev_find_devices_for_virtual(self):
  """Эмуляция поиска (не используется, оставлено для совместимости)."""
  return []

 def _evdev_key_listener(self):
  """Читает физические клавиатуры через evdev и транслирует нажатия в
  вызовы _on_press() с pynput-совместимыми объектами Key/KeyCode.
  НЕ захватывает клавиатуру X11, поэтому ввод никогда не блокируется."""
  if not HAVE_EVDEV:
   print("[evdev-listener] evdev недоступен — слушатель клавиатуры отключён")
   return
  devs = self._evdev_find_keyboards()
  if not devs:
   print("[evdev-listener] Физическая клавиатура не найдена")
   return
  print(f"[evdev-listener] Читаю: {[d.name for d in devs]}")

  # Код -> объект, похожий на pynput Key (спецклавиши).
  # ВАЖНО: shift'ов здесь НЕТ — они идут в SHIFT_CODES ниже, чтобы
  # слушатель отслеживал регистр букв (верхний/нижний).
  SPECIAL = {
   ecodes.KEY_BACKSPACE: keyboard.Key.backspace,
   ecodes.KEY_SPACE: keyboard.Key.space,
   ecodes.KEY_ENTER: keyboard.Key.enter,
   ecodes.KEY_LEFTCTRL: keyboard.Key.ctrl_l,
   ecodes.KEY_RIGHTCTRL: keyboard.Key.ctrl_r,
   ecodes.KEY_LEFTALT: keyboard.Key.alt_l,
   ecodes.KEY_RIGHTALT: keyboard.Key.alt_r,
   ecodes.KEY_TAB: keyboard.Key.tab,
   ecodes.KEY_CAPSLOCK: keyboard.Key.caps_lock,
   ecodes.KEY_LEFT: keyboard.Key.left,
   ecodes.KEY_RIGHT: keyboard.Key.right,
   ecodes.KEY_UP: keyboard.Key.up,
   ecodes.KEY_DOWN: keyboard.Key.down,
   ecodes.KEY_HOME: keyboard.Key.home,
   ecodes.KEY_END: keyboard.Key.end,
   ecodes.KEY_DELETE: keyboard.Key.delete,
   ecodes.KEY_ESC: keyboard.Key.esc,
   ecodes.KEY_LEFTMETA: keyboard.Key.cmd,
   ecodes.KEY_RIGHTMETA: keyboard.Key.cmd,
   ecodes.KEY_PAGEUP: keyboard.Key.page_up,
   ecodes.KEY_PAGEDOWN: keyboard.Key.page_down,
   ecodes.KEY_INSERT: keyboard.Key.insert,
   ecodes.KEY_NUMLOCK: keyboard.Key.num_lock,
   ecodes.KEY_F1: keyboard.Key.f1,
   ecodes.KEY_F2: keyboard.Key.f2,
   ecodes.KEY_F3: keyboard.Key.f3,
   ecodes.KEY_F4: keyboard.Key.f4,
   ecodes.KEY_F5: keyboard.Key.f5,
   ecodes.KEY_F6: keyboard.Key.f6,
   ecodes.KEY_F7: keyboard.Key.f7,
   ecodes.KEY_F8: keyboard.Key.f8,
   ecodes.KEY_F9: keyboard.Key.f9,
   ecodes.KEY_F10: keyboard.Key.f10,
   ecodes.KEY_F11: keyboard.Key.f11,
   ecodes.KEY_F12: keyboard.Key.f12,
  }

  # Код -> символ для простых клавиш (не зависящих от раскладки в _on_press,
  # т.к. пунктуация/цифры обрабатываются по строковому виду).
  # ВАЖНО: здесь НЕТ клавиш ж/э/х/ъ/б/ю/ё (, . ; ' [ ] ` /) — они занесены
  # в _EVDEV_LETTERS и перехватываются раньше, чтобы русские буквы с
  # «пунктуационных» клавиш не обрезали current_word.
  SIMPLE_CHAR = {
   ecodes.KEY_1:'1', ecodes.KEY_2:'2', ecodes.KEY_3:'3', ecodes.KEY_4:'4',
   ecodes.KEY_5:'5', ecodes.KEY_6:'6', ecodes.KEY_7:'7', ecodes.KEY_8:'8',
   ecodes.KEY_9:'9', ecodes.KEY_0:'0', ecodes.KEY_MINUS:'-', ecodes.KEY_EQUAL:'=',
  }

  # Цифровая клавиатура (numpad). Старый pynput нормализовал KP-цифры
  # в обычные символы — выбор подсказки цифрой 1–6 с numpad работал.
  # evdev отдаёт отдельные коды KEY_KP*, поэтому маппим их так же —
  # ВСЕГДА в цифру (как pynput): NumLock-ветка с dev.leds() оказалась
  # ненадёжной (у UInput и части клавиатур LED недоступен -> KP1
  # превращался в Key.end и стирал слово).
  KP_NUM = {
   ecodes.KEY_KP0:'0', ecodes.KEY_KP1:'1', ecodes.KEY_KP2:'2',
   ecodes.KEY_KP3:'3', ecodes.KEY_KP4:'4', ecodes.KEY_KP5:'5',
   ecodes.KEY_KP6:'6', ecodes.KEY_KP7:'7', ecodes.KEY_KP8:'8',
   ecodes.KEY_KP9:'9', ecodes.KEY_KPDOT:'.', ecodes.KEY_KPSLASH:'/',
   ecodes.KEY_KPASTERISK:'*', ecodes.KEY_KPMINUS:'-', ecodes.KEY_KPPLUS:'+',
  }

  # evdev-коды shift'ов — для передачи реального регистра нажатия в _on_press
  SHIFT_CODES = {ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT}

  while getattr(self, '_kbd_running', True):
   try:
    if not devs:
     devs = self._evdev_find_keyboards()
     if not devs:
      time.sleep(0.5)
      continue
    # select() блокирует до РЕАЛЬНОГО события на любой клавиатуре:
    # без опроса. Раньше пустой dev.read() бросал BlockingIOError
    # (подкласс OSError!) -> except делал sleep(0.2) на КАЖДОМ из 4
    # устройств -> буквы ждали до 0.8 с и приходили пачкой.
    fds = {d.fd: d for d in devs}
    r, _, _ = select(list(fds), [], [], 0.5)
    if r:
     for fd in r:
      dev = fds[fd]
      try:
       for event in dev.read():
        if event.type != ecodes.EV_KEY:
         continue
        code = event.code
        if code in SHIFT_CODES:
         # Запоминаем состояние shift ДО фильтра значений: ловим и
         # отпускание (value=0), иначе флаг регистра «залипнет» в True.
         self._evdev_shift = bool(event.value)
         continue
        if event.value not in (1, 2):
         continue
        # value=2 — АВТОПОВТОР (удержание клавиши, delay 500 мс, период 33 мс).
        # Раньше повторы обрабатывались как нажатия: «зд» при удержании
        # превращалось в «зддд», тултип появлялся и сразу исчезал.
        # Пропускаем повтор для ВСЕХ клавиш, кроме Backspace (удержание
        # для удаления нескольких символов должно работать).
        if event.value == 2 and code != ecodes.KEY_BACKSPACE:
         continue
        if code in SPECIAL:
         self._on_press(SPECIAL[code])
        elif code in KP_NUM:
         # Numpad-цифры: ВСЕГДА цифры, как нормализовал старый pynput.
         # Раньше читали NumLock через dev.leds() — но у части клавиатур
         # (и у всех UInput) LED недоступен -> KP1 превращался в Key.end,
         # что попадал в control_keys и стирал слово вместо выбора подсказки.
         self._on_press(keyboard.KeyCode.from_char(KP_NUM[code]))
        elif code == ecodes.KEY_KPENTER:
         self._on_press(keyboard.Key.enter)
        elif code in SIMPLE_CHAR:
         # Цифры и -= : не зависят от раскладки
         kc = keyboard.KeyCode.from_char(SIMPLE_CHAR[code])
         self._on_press(kc)
        else:
         # Буквы ЙЦУКЕН (см. _EVDEV_LETTERS). Символ всегда русский,
         # при активной латинской раскладке транслируем в латиницу
         # (з -> p) — так же, как символ отдавал старый pynput.
         ch = _EVDEV_LETTERS.get(code)
         if ch:
          if self._get_keyboard_layout() != "ru":
           ch = self.ru_to_en_layout.get(ch, ch)
          if getattr(self, '_evdev_shift', False):
           ch = ch.upper()
          self._on_press(keyboard.KeyCode.from_char(ch))
      except BlockingIOError:
       # норма: событий больше нет — НЕ пересоздаём список и НЕ спим
       pass
      except OSError:
       # устройство реально отвалилось (USB-перетык) — обновляем список
       try:
        dev.close()
       except Exception:
        pass
       devs = self._evdev_find_keyboards() or devs
       time.sleep(0.2)
   except Exception:
    pass
   time.sleep(0.001)

 def _on_press(self, key): # Обрабатывает нажатия клавиш
  if self.replacing:
   return True
  if self.disabled:
   return True

  key_str = str(key).replace("'", "").replace(" ", "")

  if any(k in key_str for k in ["down", "right", "up", "left", "Key.tab", "Key.caps_lock", "Key.shift", "<65032>", "<65512>", "Key.ctrl_r"]):
   self.clean()
   return True

  if key_str == "<65437>":
   key_str = "5"

  # Антидребезг: раньше ЛЮБАЯ клавиша ближе 5 мс «съедалась». При отходе
  # от polling-слушателя буквы могли прийти пачкой (до 0.8 с в буфере
  # ядра) и вторая буква слова терялась («ол» -> «о», тултип не показывался).
  # select() устранил пачки, теперь опасны только истинные повторы
  # железа — держим историю нажатий и игнорируем ТОЛЬКО точный дубликат
  # той же клавиши в течение 5 мс (напр. дребезг контактов клавиатуры).
  key_id = (str(key), time.time())
  if key_id[0] == self._last_key_id and key_id[1] - self._last_key_time < 0.005:
   self._last_key_time = key_id[1]
   return True
  self._last_key_id = key_id[0]
  self._last_key_time = key_id[1]

  if key == keyboard.Key.backspace:
   if self.current_word:
    self.current_word = self.current_word[:-1]
    GLib.idle_add(self._do_update_state)
   else:
    GLib.idle_add(self._do_hide_all)
   return True

  if key == keyboard.Key.space:
   if self.abbrev_res:
    self._do_replace_abbrev_async()
   self.clean()
   return True

  if key == keyboard.Key.enter:
   if self.abbrev_res:
    self._do_replace_abbrev_async()
   else:
    self.clean()
   return True

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

  if key in control_keys or key_str in {'.', ',', '\\', '/', "'", '"', '<', '>', '?', '~', ':', ';', '{', '}', '[', ']', '0'}:
   GLib.idle_add(self._do_hide_all)
   self._do_replace_abbrev_async()
   self.abbrev_res = ""
   return True

  if self.suggestions and key_str in "123456":
   index = int(key_str) - 1
   if index < len(self.suggestions):
    self._replace_word_async(self.suggestions[index], extra_backspace=1)
    return False # "Съедаем" нажатие цифры, чтобы она не напечаталась в текст
   return True

  if hasattr(key, 'char') and key.char and key.char.isprintable() and key_str not in {"+", "-", "*", "/"}:
   key_char = key.char
   self.current_word += key_char
   GLib.idle_add(self._do_update_state)
   return True

  return True

 def _on_click(self, x, y, button, pressed): # Обрабатывает клики мыши
  if pressed:
   self.clean()
  return True

 def start(self): # Запускает основной цикл приложения
  # --- Регистрируем ATSPI-слушатель для Nemo Live Search ---
  pyatspi.Registry.registerEventListener(self.on_text_changed, "object:text-changed")

  # --- Прокачка tkinter для обновления UI подсказок из GLib mainloop ---
  def _pump_tkinter():
   try:
    # update() вместо update_idletasks(): обрабатывает ВСЕ события X11,
    # включая ConfigureNotify — иначе смена геометрии окна подсказок
    # может «зависнуть» после пробела и не примениться повторно.
    self.root.update()
   except tk.TclError:
    return False
   return True

  GLib.timeout_add(50, _pump_tkinter)

  # --- Фоновые потоки ---
  window_checker_thread = threading.Thread(target=self._check_active_window_loop, daemon=True)
  window_checker_thread.start()

  # КЛАВИАТУРА: читаем через evdev (/dev/input/event*) БЕЗ X11-захвата.
  # Раньше pynput.keyboard.Listener захватывал клавиатуру X11 и при краше
  # НЕ отпускал её — вся система переставала печатать. evdev не грабит X.
  self._kbd_running = True
  keyboard_thread = threading.Thread(target=self._evdev_key_listener, daemon=True)
  keyboard_thread.start()

  mouse_listener = mouse.Listener(on_click=self._on_click)
  mouse_listener.start()

  # --- GLib mainloop вместо tkinter mainloop ---
  pyatspi.Registry.start()

  self._kbd_running = False
  mouse_listener.stop()
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

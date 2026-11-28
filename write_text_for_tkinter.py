import torch, sys, os, subprocess, json, wave, io, threading, re, time, warnings, collections, transformers, librosa, math, logging, fcntl #, webrtcvad
from queue import Queue
import sounddevice as sd
import tkinter as tk
from tkinter import Frame, Label
from scipy.io import wavfile
import soundfile as sf
from scipy import signal
import numpy as np
from pathlib import Path
# from faster_whisper import WhisperModel
# Слушатель клавиш — через evdev, как в punto.py и write_text_fast.py.
# pynput.keyboard.Listener захватывал X11 и не отпускал его при краше
# (вся система переставала печатать), а ещё конфликтовал с punto.
import glob
from select import select
from evdev import InputDevice, UInput, ecodes
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

# Сигнал для punto.py: «голосовой ввод сейчас печатает». Punto по этому
# файлу немедленно отпускает свои залипшие Shift/Ctrl/Alt, чтобы они не
# портили регистр и не превращали наши буквы в хоткеи. Живость процесса
# проверяется по PID — после краша voice-скрипта метка не остаётся вечной.
_VOICE_TYPING_FILE = "/tmp/kb_voice_typing.json"


_VOICE_SEQ = 0


def _voice_typing_start():
 global _VOICE_SEQ
 _VOICE_SEQ += 1
 seq = _VOICE_SEQ
 try:
  tmp = _VOICE_TYPING_FILE + ".tmp"
  with open(tmp, "w") as f:
   json.dump({"pid": os.getpid(), "until": time.time() + 3600.0,
              "seq": seq}, f)
  os.replace(tmp, _VOICE_TYPING_FILE)
 except Exception:
  pass
 return seq


def _voice_typing_stop():
  try:
   os.unlink(_VOICE_TYPING_FILE)
  except Exception:
   pass

# ---------------------------------------------------------------------
# КООРДИНАЦИЯ С PUNTO (без отдельного модуля — общие файлы в /tmp)
# ---------------------------------------------------------------------
# punto.py тоже печатает через СВОЮ UInput-клавиатуру и тоже переключает
# раскладку (ISO_Next_Group). Две виртуальные клавиатуры в X сами по себе
# не конфликтуют (X работает с ними как с двумя физическими), мешают две
# вещи:
#   - чужое переключение раскладки посреди печати -> буквы не на том
#     языке;
#   - «залипшие» модификаторы punto (Shift/Ctrl/Alt, липкие клавиши):
#     чужой Shift меняет регистр наших букв, чужой Ctrl превращает букву
#     в хоткей (Ctrl+S вместо 's').
# Согласование — через два файла в /tmp (имена согласованы с punto.py):
#   /tmp/kb_scripts_typing.lock — flock-блокировка печати (flock
#     освобождается ядром при смерти процесса — зависнуть не может);
#   /tmp/kb_sticky_mods.json   — punto публикует свои залипшие
#     модификаторы, мы ждём их отпускания.
# ---------------------------------------------------------------------
_COORD_LOCK = "/tmp/kb_scripts_typing.lock"
_COORD_STICKY = "/tmp/kb_sticky_mods.json"


def _typing_lock_acquire(timeout=5.0):
 """Взять межпроцессную блокировку печати (flock). Возвращает fd;
 по таймауту печатает предупреждение и возвращает fd БЕЗ блокировки
 (печать важнее идеальной сериализации)."""
 fd = open(_COORD_LOCK, "a+")
 deadline = time.time() + timeout
 while True:
  try:
   fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
   break
  except OSError:
   if time.time() >= deadline:
    print(f"[kb-coord] блокировка печати не получена за {timeout:.1f} с "
     "(punto ещё печатает?) — продолжаю без неё")
    break
   time.sleep(0.05)
 try:
  fd.seek(0)
  fd.write(str(os.getpid()))
  fd.truncate()
  fd.flush()
 except Exception:
  pass
 return fd


def _typing_lock_release(fd):
 """Отпустить блокировку печати."""
 try:
  fcntl.flock(fd, fcntl.LOCK_UN)
 except Exception:
  pass
 try:
  fd.close()
 except Exception:
  pass


def _wait_sticky_clear(timeout=0.5, seq=None):
 """Ждём снятия залипших модификаторов punto.

 Если punto подтвердил сброс именно для этой печати (voice_ack/voice_seq
 в /tmp/kb_sticky_mods.json), возвращаемся МГНОВЕННО — так убирается
 задержка между началом диктовки и печатью. Опрос каждые 20 мс.
 """
 mypid = os.getpid()
 end = time.time() + timeout
 while True:
  try:
   with open(_COORD_STICKY) as f:
    st = json.load(f)
   codes = st.get("codes") or []
   if seq is not None:
    if (st.get("voice_ack") == mypid and
        st.get("voice_seq") == seq and not codes):
     return True
   dl = float(st.get("deadline") or 0.0)
   if not codes or dl <= time.time() or dl > time.time() + 30:
    return True
  except Exception:
   return True
  if time.time() >= end:
   return False
  time.sleep(0.02)


# ==============================
# КАРТЫ СИМВОЛОВ (на уровне модуля — константы, не зависят от экземпляра)
# ==============================
# Символ -> (evdev-код клавиши, нужен ли Shift) ОТДЕЛЬНО для каждой
# раскладки.
#
# Раньше здесь лежало семь пересекающихся словарей (COMMON_MAP, EN_MAP,
# RU_MAP, EN_ONLY_PUNCT, RU_ONLY_PUNCT, PUNCT_EN, PUNCT_RU), а нужную
# раскладку для каждого символа выбирала эвристика внутри type_text().
# Из-за этого: часть символов молча терялась ('—', '…', '«', '»'
# вообще не печатались, '…' превращалась в одиночную точку), а для
# общих символов вроде ';' ', ' '/' приходилось угадывать.
#
# Теперь таблицы строятся из ЖИВОЙ карты XKB текущего X-сервера
# (xkbcomp -xkb :0 -) — то есть описывают ровно ту раскладку, которая
# реально загружена у пользователя, и никаких догадок не требуется.
# Если xkbcomp недоступен или данные не распознались, используется
# запасная таблица (проверена на этой системе: xkbcomp -xkb :0 -).

# --- Вспомогательные таблицы для разбора keysym-имён из XKB ---

_CYR_KEYSYMS = {
 'shorti': 'й', 'tse': 'ц', 'u': 'у', 'ka': 'к', 'ie': 'е', 'en': 'н',
 'ghe': 'г', 'sha': 'ш', 'shcha': 'щ', 'ze': 'з', 'ha': 'х',
 'hardsign': 'ъ', 'ef': 'ф', 'yeru': 'ы', 've': 'в', 'a': 'а', 'pe': 'п',
 'er': 'р', 'o': 'о', 'el': 'л', 'de': 'д', 'zhe': 'ж', 'e': 'э',
 'io': 'ё', 'ya': 'я', 'che': 'ч', 'es': 'с', 'em': 'м', 'i': 'и',
 'te': 'т', 'softsign': 'ь', 'be': 'б', 'yu': 'ю',
}

_ASCII_KEYSYMS = {
 'exclam': '!', 'at': '@', 'numbersign': '#', 'dollar': '$', 'percent': '%',
 'asciicircum': '^', 'ampersand': '&', 'asterisk': '*', 'parenleft': '(',
 'parenright': ')', 'underscore': '_', 'plus': '+', 'minus': '-',
 'equal': '=', 'bracketleft': '[', 'braceleft': '{', 'bracketright': ']',
 'braceright': '}', 'semicolon': ';', 'colon': ':', 'apostrophe': "'",
 'quotedbl': '"', 'grave': '`', 'asciitilde': '~', 'backslash': '\\',
 'bar': '|', 'comma': ',', 'less': '<', 'period': '.', 'greater': '>',
 'slash': '/', 'question': '?', 'numerosign': '№', 'space': ' ',
}

# Символы, которых физически нет на клавиатуре ни в одной раскладке
# («—», «…», «ёлочки», «€», эмодзи), печатаются через xdotool — он
# умеет подставлять нужный keysym на лету (см. _type_via_xdotool).
# Отдельного списка для них не нужно: type_text отправляет в xdotool
# любой символ, которого нет в картах раскладок.

_LAYOUT_MAPS = None  # кэш, заполняется функцией build_layout_maps()


def _keysym_to_char(name):
 """Keysym из XKB -> символ. None, если это не печатный символ."""
 if not name:
  return None
 if name in _ASCII_KEYSYMS:
  return _ASCII_KEYSYMS[name]
 if name.startswith('Cyrillic_'):
  base = name[len('Cyrillic_'):]
  low = base.lower()
  if low not in _CYR_KEYSYMS:
   return None
  ch = _CYR_KEYSYMS[low]
  return ch.upper() if base != low else ch
 if len(name) == 1:
  return name
 if re.fullmatch(r'U[0-9A-Fa-f]{4,6}', name):
  try:
   ch = chr(int(name[1:], 16))
   return ch if ch.isprintable() else None
  except ValueError:
   return None
 return None


def _xkb_language(group_name, index, used):
 """По имени группы XKB ('Russian'/'English (US)') определяет язык."""
 n = (group_name or '').lower()
 if 'russian' in n or re.search(r'(^|[^a-z])ru([^a-z]|$)', n):
  return 'ru'
 if 'english' in n or re.search(r'(^|[^a-z])us([^a-z]|$)', n) or 'intl' in n:
  return 'us'
 # Имя не распознано — раскладываем по порядку: ru, us, ru, us...
 return ('ru', 'us')[index % 2]


def _parse_xkb_layout_maps(display=None):
 """Строит {'ru': {символ: (код, shift)}, 'us': {...}} из ЖИВОЙ карты
 XKB. Пустой словарь, если разобрать не удалось."""
 disp = display or os.environ.get('DISPLAY', ':0')
 try:
  proc = subprocess.run(['xkbcomp', '-xkb', disp, '-'],
        capture_output=True, text=True, timeout=3)
 except Exception as e:
  print(f'[WARN] Не удалось прочитать XKB-карту: {e}')
  return {}
 out = proc.stdout or ''
 if 'xkb_symbols' not in out:
  return {}

 # 1. Имена клавиш -> X-номера (берём ПЕРВОЕ определение, дальше идут
 #    псевдонимы с другими номерами).
 codes = {}
 km = re.search(r'xkb_keycodes\s+"[^"]*"\s*\{(.*?)\n\};', out, re.S)
 if km:
  for name, num in re.findall(r'<(\w+)>\s*=\s*(\d+)\s*;', km.group(1)):
   codes.setdefault(name, int(num))
 if not codes:
  return {}

 # 2. Имена групп -> язык.
 names = {int(g): n for g, n in
     re.findall(r'name\[group(\d+)\]\s*=\s*"([^"]*)"', out)}

 # 3. Символы по клавишам и группам (скобки считаем вручную —
 #    регулярка не справляется с блоками в одну строку).
 sm = re.search(r'xkb_symbols\s+"[^"]*"\s*\{(.*)\n\};', out, re.S)
 if not sm:
  return {}
 body = sm.group(1)
 key_pat = re.compile(r'key\s+<(\w+)>\s*\{')
 tables = {}
 langs = {}
 pos = 0
 while True:
  m = key_pat.search(body, pos)
  if not m:
   break
  depth, i = 1, m.end()
  while i < len(body) and depth:
   depth += (body[i] == '{') - (body[i] == '}')
   i += 1
  kbody = body[m.end():i - 1]
  pos = i
  name = m.group(1)
  if name not in codes:
   continue
  # X-номер = evdev-код + 8 (так устроен xkb_keycodes для evdev)
  evdev = codes[name] - 8
  if evdev < 0:
   continue
  # Только ОСНОВНОЙ блок клавиатуры (1..53 и пробел 57). Клавиши
  # цифрового блока, F-клавиши и навигации отбрасываем: в некоторых
  # раскладках на них тоже висят printable-символы (в ru на KPEQ —
  # '#'), и такой «символ» печатался бы вслепую, не появляясь в
  # поле ввода.
  if not (1 <= evdev <= 53 or evdev == 57):
   continue
  found = False
  for gm in re.finditer(r'symbols\[Group(\d+)\]\s*=\s*\[([^\]]*)\]', kbody):
   found = True
   grp = int(gm.group(1))
   chars = [s.strip() for s in gm.group(2).split(',')]
   if grp not in langs:
    langs[grp] = _xkb_language(names.get(grp), len(langs), langs)
   table = tables.setdefault(langs[grp], {})
   for level, sym in enumerate(chars):
    # Уровень 0 — без модификаторов, уровень 1 — с Shift.
    # Уровни 2/3 (AltGr) нам недоступны, их игнорируем.
    if level > 1:
     break
    ch = None if (not sym or sym == 'NoSymbol') else _keysym_to_char(sym)
    if ch and not ch.isspace():
     table.setdefault(ch, (evdev, level == 1))
  if not found:
   plain = re.search(r'\[([^\]]*)\]', kbody)
   if plain:
    chars = [s.strip() for s in plain.group(1).split(',')]
    for grp in (1, 2):
     if grp not in langs:
      langs[grp] = _xkb_language(names.get(grp), len(langs), langs)
     table = tables.setdefault(langs[grp], {})
     for level, sym in enumerate(chars):
      if level > 1:
       break
      ch = None if (not sym or sym == 'NoSymbol') else _keysym_to_char(sym)
      if ch and not ch.isspace():
       table.setdefault(ch, (evdev, level == 1))
 return tables


def _maps_are_valid(maps):
 """Проверка, что в таблицах есть обе раскладки с полным алфавитом."""
 try:
  ru, us = maps['ru'], maps['us']
 except KeyError:
  return False
 alpha_ru = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
 alpha_us = 'abcdefghijklmnopqrstuvwxyz'
 return (all(c in ru for c in alpha_ru) and
         all(c in us for c in alpha_us) and
         all(c in ru for c in alpha_ru.upper()) and
         all(c in us for c in alpha_us.upper()) and
         '1' in ru and '1' in us and ' ' not in ru and ' ' not in us)


def _fallback_maps():
 """Запасные таблицы (сняты с этой системы: pc105, группы 1=ru, 2=us)."""
 def letter_map(pairs):
  out = {}
  for ch, key in pairs:
   out[ch] = (key, False)
   out[ch.upper()] = (key, True)
  return out

 ru = {}
 ru.update({c: (ecodes.KEY_SPACE, False) for c in ' '})
 ru.update({'!': (ecodes.KEY_1, True), '"': (ecodes.KEY_2, True),
    '№': (ecodes.KEY_3, True), ';': (ecodes.KEY_4, True),
    '%': (ecodes.KEY_5, True), ':': (ecodes.KEY_6, True),
    '?': (ecodes.KEY_7, True), '*': (ecodes.KEY_8, True),
    '(': (ecodes.KEY_9, True), ')': (ecodes.KEY_0, True),
    '-': (ecodes.KEY_MINUS, False), '_': (ecodes.KEY_MINUS, True),
    '=': (ecodes.KEY_EQUAL, False), '+': (ecodes.KEY_EQUAL, True),
    'х': (ecodes.KEY_LEFTBRACE, False), 'Х': (ecodes.KEY_LEFTBRACE, True),
    'ъ': (ecodes.KEY_RIGHTBRACE, False), 'Ъ': (ecodes.KEY_RIGHTBRACE, True),
    'ж': (ecodes.KEY_SEMICOLON, False), 'Ж': (ecodes.KEY_SEMICOLON, True),
    'э': (ecodes.KEY_APOSTROPHE, False), 'Э': (ecodes.KEY_APOSTROPHE, True),
    'ё': (ecodes.KEY_GRAVE, False), 'Ё': (ecodes.KEY_GRAVE, True),
    '\\': (ecodes.KEY_BACKSLASH, False), '/': (ecodes.KEY_BACKSLASH, True),
    ',': (ecodes.KEY_SLASH, True), '.': (ecodes.KEY_SLASH, False),
    'б': (ecodes.KEY_COMMA, False), 'Б': (ecodes.KEY_COMMA, True),
    'ю': (ecodes.KEY_DOT, False), 'Ю': (ecodes.KEY_DOT, True)})
 ru.update(letter_map([('й', ecodes.KEY_Q), ('ц', ecodes.KEY_W), ('у', ecodes.KEY_E),
    ('к', ecodes.KEY_R), ('е', ecodes.KEY_T), ('н', ecodes.KEY_Y), ('г', ecodes.KEY_U),
    ('ш', ecodes.KEY_I), ('щ', ecodes.KEY_O), ('з', ecodes.KEY_P), ('ф', ecodes.KEY_A),
    ('ы', ecodes.KEY_S), ('в', ecodes.KEY_D), ('а', ecodes.KEY_F), ('п', ecodes.KEY_G),
    ('р', ecodes.KEY_H), ('о', ecodes.KEY_J), ('л', ecodes.KEY_K), ('д', ecodes.KEY_L),
    ('я', ecodes.KEY_Z), ('ч', ecodes.KEY_X), ('с', ecodes.KEY_C), ('м', ecodes.KEY_V),
    ('и', ecodes.KEY_B), ('т', ecodes.KEY_N), ('ь', ecodes.KEY_M)]))
 for i in range(10):
  ru[str(i)] = ((ecodes.KEY_1 + i) if i < 9 else ecodes.KEY_0, False)

 us = {}
 us.update({c: (ecodes.KEY_SPACE, False) for c in ' '})
 us.update({'!': (ecodes.KEY_1, True), '@': (ecodes.KEY_2, True),
    '#': (ecodes.KEY_3, True), '$': (ecodes.KEY_4, True),
    '%': (ecodes.KEY_5, True), '^': (ecodes.KEY_6, True),
    '&': (ecodes.KEY_7, True), '*': (ecodes.KEY_8, True),
    '(': (ecodes.KEY_9, True), ')': (ecodes.KEY_0, True),
    '-': (ecodes.KEY_MINUS, False), '_': (ecodes.KEY_MINUS, True),
    '=': (ecodes.KEY_EQUAL, False), '+': (ecodes.KEY_EQUAL, True),
    '[': (ecodes.KEY_LEFTBRACE, False), '{': (ecodes.KEY_LEFTBRACE, True),
    ']': (ecodes.KEY_RIGHTBRACE, False), '}': (ecodes.KEY_RIGHTBRACE, True),
    '\\': (ecodes.KEY_BACKSLASH, False), '|': (ecodes.KEY_BACKSLASH, True),
    ';': (ecodes.KEY_SEMICOLON, False), ':': (ecodes.KEY_SEMICOLON, True),
    "'": (ecodes.KEY_APOSTROPHE, False), '"': (ecodes.KEY_APOSTROPHE, True),
    '`': (ecodes.KEY_GRAVE, False), '~': (ecodes.KEY_GRAVE, True),
    ',': (ecodes.KEY_COMMA, False), '<': (ecodes.KEY_COMMA, True),
    '.': (ecodes.KEY_DOT, False), '>': (ecodes.KEY_DOT, True),
    '/': (ecodes.KEY_SLASH, False), '?': (ecodes.KEY_SLASH, True)})
 us.update(letter_map([(c, k) for c, k in zip(
    'qwertyuiopasdfghjklzxcvbnm',
    [ecodes.KEY_Q, ecodes.KEY_W, ecodes.KEY_E, ecodes.KEY_R, ecodes.KEY_T,
     ecodes.KEY_Y, ecodes.KEY_U, ecodes.KEY_I, ecodes.KEY_O, ecodes.KEY_P,
     ecodes.KEY_A, ecodes.KEY_S, ecodes.KEY_D, ecodes.KEY_F, ecodes.KEY_G,
     ecodes.KEY_H, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_Z,
     ecodes.KEY_X, ecodes.KEY_C, ecodes.KEY_V, ecodes.KEY_B, ecodes.KEY_N,
     ecodes.KEY_M])]))
 for i in range(10):
  us[str(i)] = ((ecodes.KEY_1 + i) if i < 9 else ecodes.KEY_0, False)
 return {'ru': ru, 'us': us}


def build_layout_maps():
 """Карты символов для обеих раскладок (из XKB, с запасным вариантом)."""
 global _LAYOUT_MAPS
 if _LAYOUT_MAPS is None:
  maps = _parse_xkb_layout_maps()
  if _maps_are_valid(maps):
   _LAYOUT_MAPS = maps
   print('[INFO] Таблицы символов взяты из живой карты XKB: ' +
    ', '.join(f'{k}={len(v)}' for k, v in sorted(maps.items())))
  else:
   _LAYOUT_MAPS = _fallback_maps()
   print('[INFO] Используется запасная таблица раскладок ' +
    '(XKB-карту прочитать не удалось)')
 return _LAYOUT_MAPS


warnings.filterwarnings("ignore")
# --- Конфигурация модели ---
warnings.filterwarnings("ignore", category=DeprecationWarning)
# Полное отключение мусора
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["BITSANDBYTES_NOWELCOME"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
logging.getLogger("librosa").setLevel(logging.ERROR)
logging.getLogger("audioread").setLevel(logging.ERROR)
logging.getLogger("paramiko").setLevel(logging.ERROR)
# from llama_cpp import Llama
# Укажите путь к модели Meta-Llama-3.1-8B-Instruct (GGUF q4_K)
model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/meta-llama-3.1-8b-instruct-q4_k_m.gguf"
# Глобальная переменная для модели (чтобы не перезагружать)
# llm = None
#
# def load_model() -> Llama:    #    Загружает модель Llama один раз и возвращает объект.
#     #Если модель уже загружена, возвращает существующий объект.
#
#   global llm
#   if llm is None:
#       print("Загрузка модели... (это может занять 1-2 минуты)")
#       llm = Llama(
#           model_path=model_path,
#           n_ctx=8192,  # Большой контекст для Llama 3.1 — хватит для длинных текстов
#           n_threads=4,  # Кол-во CPU-ядер; увеличь, если нужно
#           n_gpu_layers=35,  # Если GPU: разгружает на GPU (0 для CPU only)
#           verbose=False  # Без лишнего лога
#       )
#       print("Модель загружена успешно!")
#   return llm
#
# def is_model_loaded() -> bool:
#     # Проверяет, загружена ли модель (llm не None).
#     global llm
#     return llm is not None
#
# def fix_text(text: str) -> str:
#     """
#     Исправляет текст от распознавания речи на русском: звуки (р↔л, ш↔с/х, ж↔з/г, з↔с/дз, щ↔ш/сч),
#     грамматику (падежи, склонения, род, число). Возвращает ТОЛЬКО исправленный текст.
#     Адаптировано для Llama 3.1 Instruct.
#
#     Оптимизация токенов: max_tokens динамически по длине текста (минимум 100, максимум 512).
#     """
#     global llm
#     if not is_model_loaded():
#         raise ValueError("Модель не загружена! Вызовите load_model() сначала.")
#
#     # Динамический max_tokens: пропорционально длине + запас
#     max_tokens = min(512, max(100, len(text) * 2 + 100))
#
#     prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
# Ты — эксперт по исправлению текстов, полученных от систем распознавания речи на русском языке. У меня проблемы с дикцией из-за ДЦП: плохо произносятся звуки "р" (часто заменяется на "л" или пропускается), "л" (искажается), "ш" (может звучать как "с" или "х"), "ж" (как "з" или "г"), "з" (как "с" или "дз"), "щ" (как "ш" или "сч"). Из-за этого слова искажаются, например: "работа" может стать "лабода", "школьник" — "скольник", "жизнь" — "зиснь". Также бывают ошибки в грамматике: неправильные падежи (например, "в дом" вместо "в доме"), склонения (окончания слов), роде, числе и предложениях (смешанные слова или фразы).
#
# Твоя задача:
# 1. Прочитай предоставленный текст как "грязный" вывод распознавания речи.
# 2. Исправь орфографию, учитывая типичные замены звуков (р↔л, ш↔с/х, ж↔з/г, з↔с/дз, щ↔ш/сч). Предполагай, что текст близок к реальному смыслу, но искажён произношением.
# 3. Исправь грамматику: подбери правильные падежи, склонения, род, число, времена глаголов. Сделай текст coherentным и естественным на русском.
# 4. Если текст неоднозначен, выбери наиболее логичный вариант (предполагай повседневный контекст: разговор о жизни, работе, семье или хобби).
# 5. Ответь ТОЛЬКО исправленным текстом, без лишних объяснений, кавычек, скобок. Если оригинал слишком искажён, добавь в конце: [Возможная интерпретация].<|eot_id|><|start_header_id|>user<|end_header_id|>
#
# Текст: {text}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
#
#     output = llm(  prompt,  max_tokens=max_tokens,  # Динамический: экономит токены на коротких текстах
#         temperature=0.0,  # Детерминированный вывод
#         top_p=0.9, stop=["<|eot_id|>", "</s>"],  # Стоп-токены для Llama 3.1
#         echo=False  ) # Не повторять промпт в выводе
#
#     # Извлекаем чистый ответ (после assistant)
#     response = output["choices"][0]["text"].strip()
#
#     # Убираем [Возможная интерпретация], если есть, или возвращаем как есть
#     if '[Возможная интерпретация]' in response:
#         response = response.split('[Возможная интерпретация]')[0].strip()
#
#     return response

def boost_by_db_range(audio_array, low_db, high_db, boost=3):
 # Переводим в dBFS, избегаем логарифма нуля
 abs_audio = np.abs(audio_array)
 db_vals = 20 * np.log10(abs_audio + 1e-9)
 # Создаем маску для участка, попадающего в диапазон
 mask = (db_vals >= low_db) & (db_vals <= high_db)
 # Коэффициент усиления (например, для 3dB это ~1.41)
 factor = 10 ** (boost / 20)
 # Применяем только к выбранным элементам
 audio_array[mask] *= factor
 return np.clip(audio_array, -1.0, 1.0)
class save_key:
 def __init__(self):
  self.text = ""
  self.flag = False
  self.word = []
  self.res = {}
  self.new_res = {}
  self.driver = None

 def save_driver(self, driver):
  self.driver = driver

 def get_driver(self):
  return self.driver

 def save_text(self, text):
  self.text = text

 def get_text(self):
  return self.text

 def get_flag(self):
  return self.flag

 def set_flag(self, value):
  self.flag = value

 def update_dict(self):
  data = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/list for replacements.json"  # файл настроек.
  if os.path.exists(data):  # есть ли этот файл.
   with open(data, encoding="cp1251") as json_file:  # загрузка настроек из файла.
    self.res = json.load(json_file)  # проходимся по каждому элементу словаря
    for key in self.res.keys():  # Если ключ содержит '*', добавляем его в новый словарь
     if '*' in key:
      self.new_res[key] = self.res[key]
    for key in self.new_res.keys():
     del self.res[key]

 def get_dict(self):  # словарь без *
  return self.res

 def get_new_dict(self):  # словарь с *
  return self.new_res

 def save_words(self, w):
  self.word.clear()
  for i in w:
   self.word.append(i)
  self.word = sorted(self.word, key=lambda s: len(s.split()), reverse=True)

 def get_words(self):
  return self.word
k = save_key()
k.update_dict()  # Changed Contr1 to Controller
class SmartTyper:
 def __init__(self):
  try:
   subprocess.run(["sudo", "modprobe", "ntsync"], capture_output=True)
  except Exception:
   pass

  # Карты символов строятся один раз на весь процесс (см.
  # build_layout_maps): это данные о раскладке, а не состояние
  # экземпляра.
  self.layout_maps = build_layout_maps()

  self._current_layout = None

  self.physical_keyboard = self.find_keyboard()
  self.ui = self.create_virtual_keyboard()

  # Ждём, пока X начнёт обрабатывать смену раскладки с новой
  # клавиатуры (см. warmup_xkb) — иначе первые сообщения печатались бы
  # в неправильной раскладке.
  self.warmup_xkb()

  # --- ВКЛЮЧЕНИЕ NUMLOCK С ГАРАНТИЕЙ LED ---
  # self.ensure_numlock_on()

 def find_keyboard(self):
  # Выбираем НОВУЮ (самую «полную») физическую клавиатуру: из устройств,
  # прошедших фильтр по имени, берём те, у которых реально есть буквы
  # (KEY_A/KEY_ENTER/KEY_SPACE), и сортируем по числу клавиш EV_KEY.
  # Было (баг, исправлено 2026-11-04): «первое совпадение в порядке
  # glob» — на этой системе это «USB OPTICAL MOUSE  Keyboard»
  # (/dev/input/event7, клавиатурный интерфейс МЫШИ без букв и без
  # NumLock-LED): логика NumLock/LED работала не на той клавиатуре.
  candidates = []
  for path in glob.glob("/dev/input/event*"):
   try:
    dev = evdev.InputDevice(path)
    name = (dev.name or "").lower()
    if ("keyboard" in name or "корпус" in name or "logitech" in name
        or "at translate" in name or "virtual core" in name) and "smart" not in name \
        and "mouse" not in name and "virtual" not in name:
     # "mouse" отсекает и "Mouse Setting Control" (наш же UInput), и
     # клавиатурные интерфейсы мышей ("USB OPTICAL MOUSE  Keyboard"),
     # у которых EV_KEY длиннее, чем у настоящей клавиатуры.
     # "virtual" отсекает ЛЮБЫЕ виртуальные клавиатуры: нашу
     # "Smart-Virtual-Keyboard", punto "Punto-Virtual-Keyboard" и
     # мышиного скрипта "Mouse Setting Control Virtual ...". Раньше
     # фильтр опирался только на "smart"/"mouse", и после появления
     # у punto устройства с другим именем оно считалось бы физической
     # клавиатурой: его синтетический Shift ставил бы наш флаг регистра.
     try:
      caps = dev.capabilities().get(ecodes.EV_KEY, [])
     except Exception:
      continue
     if ecodes.KEY_A in caps or ecodes.KEY_ENTER in caps or ecodes.KEY_SPACE in caps:
      candidates.append((len(caps), dev))
   except PermissionError:
    continue
   except Exception:
    continue
  if not candidates:
   print("[WARN] Физическая клавиатура не найдена (keyboard-only режим).")
   return None
  candidates.sort(key=lambda t: t[0], reverse=True)
  dev = candidates[0][1]
  print(f"[INFO] Физическая клавиатура найдена: {dev.name} ({dev.path})")
  return dev

 def create_virtual_keyboard(self):
   capabilities = {
    ecodes.EV_KEY: [ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_C, ecodes.KEY_D, ecodes.KEY_E, ecodes.KEY_F,
                    ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_I, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_M,
                    ecodes.KEY_N, ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_Q, ecodes.KEY_R, ecodes.KEY_S, ecodes.KEY_T,
                    ecodes.KEY_U, ecodes.KEY_V, ecodes.KEY_W, ecodes.KEY_X, ecodes.KEY_Y, ecodes.KEY_Z, ecodes.KEY_SPACE,
                    ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT, ecodes.KEY_COMMA, ecodes.KEY_DOT, ecodes.KEY_ENTER, ecodes.KEY_TAB,
                    ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8,
                    ecodes.KEY_9, ecodes.KEY_0, ecodes.KEY_SEMICOLON, ecodes.KEY_APOSTROPHE, ecodes.KEY_GRAVE,
                    ecodes.KEY_LEFTBRACE, ecodes.KEY_RIGHTBRACE, ecodes.KEY_BACKSLASH,
ecodes.KEY_MINUS, ecodes.KEY_EQUAL, ecodes.KEY_SLASH,
     ecodes.KEY_NUMLOCK, ecodes.KEY_CAPSLOCK
                     ]
    # ВАЖНО: EV_LED сюда НЕ заявлять! X-сервер при регистрации нового
    # устройства с LED-capability пересинхронизирует индикаторы всех
    # клавиатур и ГАСИТ NumLock-LED физической клавиатуры (лампочка
    # NumLock тухнет при запуске скрипта). Печати клавиш EV_LED не нужна.
    # KEY_CAPSLOCK — в отличие от EV_LED — обычная клавиша ввода: она
    # нужна, чтобы на время печати гасить Caps Lock, который ломает
    # цифры и знаки (KEY_1 начинает печатать '!').
   }

   ui = UInput(capabilities, vendor=0x1234, product=0x5678,
               bustype=ecodes.BUS_USB, name="Smart-Virtual-Keyboard"
               )

   # LED-записи больше не нужны: без EV_LED-capability виртуальная
   # клавиатура не трогает индикаторы, и LED физической клавиатуры
   # остаётся как есть (NumLock продолжает гореть).

   # Подстраховка: NumLock должен гореть. Состояние берём из X-сервера
   # (xset), а не из /dev/input — тогда работает и без root. Сам
   # индикатор зажигается честным нажатием KEY_NUMLOCK, XKB
   # пересинхронизирует его у всех клавиатур.
   # ВАЖНО: self.ui должен быть уже присвоен — _ensure_numlock и watchdog
   # пишут KEY_NUMLOCK через self.ui. В исходном write_text_fast.py этого
   # не было, поэтому при выключенном NumLock падал AttributeError и
   # индикатор оставался погасшим.
   self.ui = ui
   self._ensure_numlock()

   return ui

 def _ensure_numlock(self):
  self._start_numlock_watchdog()
  """Гарантирует, что NumLock включён (индикатор горит).

  Проверяем состояние через `xset -q`. Если NumLock выключен —
  отправляем одно нажатие KEY_NUMLOCK и перепроверяем.
  """
  for _ in range(3):
   try:
    result = subprocess.run(["xset", "-q"], capture_output=True,
         text=True, timeout=2)
    on = False
    for line in result.stdout.splitlines():
     if "Num Lock:" in line:
      on = line.split("Num Lock:")[1].split()[0].strip() == "on"
      break
    else:
     # XKB-индикаторов в выводе нет — считаем, что трогать нечего.
     return
    if on:
     return
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
    self.ui.syn()
    time.sleep(0.05)
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 0)
    self.ui.syn()
    time.sleep(0.15)
   except Exception as e:
    print(f"[WARN] Не удалось проверить NumLock: {e}")
    return
  print("[WARN] Не удалось включить NumLock")

 def _start_numlock_watchdog(self):
  """Держим индикатор NumLock горячим постоянно.

  Однократной проверки при старте мало: лампочка может погаснуть и позже
  (другой скрипт, DE, физическая клавиша). Раз в 2 с спрашиваем xset и
  нажимаем KEY_NUMLOCK ТОЛЬКО если он реально выключен — нажатие при
  включённом состоянии как раз погасило бы индикатор. Punto этот ключ
  не трогает, поэтому watchdog с ним не конфликтует.
  """
  if getattr(self, "_numlock_wd_started", False):
   return
  self._numlock_wd_started = True

  def _loop():
   while True:
    time.sleep(2.0)
    try:
     result = subprocess.run(["xset", "-q"], capture_output=True,
          text=True, timeout=2)
     on = None
     for line in result.stdout.splitlines():
      if "Num Lock:" in line:
       on = (line.split("Num Lock:", 1)[1].split()[0].strip().lower()
             == "on")
       break
     if on is False:
      self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
      self.ui.syn()
      time.sleep(0.05)
      self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 0)
      self.ui.syn()
    except Exception:
     pass

  threading.Thread(target=_loop, daemon=True,
       name="numlock-watchdog").start()

 def _toggle_group_once(self):
   """Один щелчок ISO_Next_Group через нашу виртуальную клавиатуру.
   Возвращает номер группы ДО и ПОСЛЕ (None, если X не ответил)."""
   before = self._current_xkb_group()
   self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
   self.ui.syn()
   time.sleep(0.03)
   self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
   self.ui.syn()
   time.sleep(0.12)
   return before, self._current_xkb_group()

 def warmup_xkb(self, timeout=4.0):
  """Обёртка с координацией: не дёргать смену раскладки, пока другой
  скрипт (punto) печатает — иначе его замена уйдёт не на том языке.
  Таймаут: старт скрипта не должен зависнуть."""
  fd = _typing_lock_acquire(timeout=3.0)
  try:
   return self._warmup_xkb_impl(timeout=timeout)
  finally:
   _typing_lock_release(fd)

 def _warmup_xkb_impl(self, timeout=4.0):
   """Ждёт, пока X-сервер начнёт обрабатывать нашу виртуальную клавиатуру.

   Новая uinput-клавиатура подхватывается X'ом не мгновенно: первые
   секунды (на этой машине — примерно до 3 с) нажатия УЖЕ доходят до
   приложений, но действие ISO_Next_Group для нового устройства ещё не
   работает. Из-за этого первые сообщения печатались в неправильной
   раскладке — английские слова выходили кириллицей, и сбой был
   «то есть, то нет» (зависит от того, как быстро после запуска
   началась печать).

   Здесь мы пробуем переключить группу и вернуть её обратно: как только
   переключение сработало — клавиатура готова. Если не сработало за
   timeout, выходим: set_layout всё равно пробует xte/xdotool.
   """
   deadline = time.time() + timeout
   attempts = 0
   while time.time() < deadline:
    attempts += 1
    before = self._current_xkb_group()
    if before is None:
     return False
    # Пробуем ЛЮБОЙ доступный способ переключения (своя клавиатура,
    # xte, xdotool): готовы мы или нет — узнаём по факту смены группы.
    if not self._switch_group():
     time.sleep(0.2)
     continue
    # Переключение сработало — возвращаем группу как была.
    for _ in range(3):
     if self._current_xkb_group() == before:
      break
     self._switch_group()
    print(f"[INFO] Виртуальная клавиатура готова (смена раскладки "
     f"работает, проверок: {attempts})")
    return True
   print("[WARN] X-сервер не отвечает на смену раскладки "
    f"({attempts} проверок за {timeout:.0f} с) — печать может быть "
    "неточной")
   return False

 def _physical_numlock_on(self):
  """Проверяет фактическое состояние NumLock физической клавиатуры через evdev."""
  try:
   leds = self.physical_keyboard.leds()
   return ecodes.LED_NUML in leds
  except Exception:
   return None

 def ensure_numlock_on(self):
   """Принудительно включает NumLock и всегда выставляет LED-индикатор,
   чтобы при старте состояние NumLock было предсказуемым (ВКЛ)."""
   try:
    # ВАЖНО: EV_LED в UInput НЕ заявлен (см. create_virtual_keyboard) —
    # записи LED в виртуальную клавиатуру больше не делаем: без
    # capability evdev падает, а с capability X гасил LED физической
    # клавиатуры. LED физической клавиатуры трогаем только через
    # set_led (ядро), состояние NumLock — только честным нажатием
    # клавиши, которое XKB сам пересинхронизирует везде.
    try:
     self.physical_keyboard.set_led(ecodes.LED_NUML, 1)
    except Exception as e:
     print(f"[WARN] Не удалось установить LED на физической клавиатуре: {e}")

    # Если NumLock физически выключен — эмулируем нажатие клавиши,
    # чтобы реально включить его, а не только погасить индикатор.
    state = self._physical_numlock_on()
    if state is False:
     print("[INFO] NumLock был выключен — включаю...")
     self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
     self.ui.syn()
     time.sleep(0.05)
     self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 0)
     self.ui.syn()

    time.sleep(0.15)
   except Exception as e:
    print(f"[WARN] Ошибка при включении NumLock: {e}")
   
 def get_current_layout(self):
  """
  Определение текущей раскладки RU/US по номеру активной группы XKB.

  Определяем именно номер группы (группа 1, 2, 3...), а не полагаемся на
  бит 0x1000: на системах с раскладкой `ru,us,ru` групп может быть три,
  и слепой детект по одному биту даёт сбои.

  Схема LED mask (типичная):
    0x00000002 — группа 1
    0x00001002 — группа 2
    0x00002002 — группа 3
    ... и так далее (биты 0x1000, 0x2000, 0x4000 ...).

  Номер группы переводим в раскладку через `setxkbmap -query`: список групп
  вида "ru,us,ru" — индекс 0 равен группе 1 и т.д.
  """
  try:
   result = subprocess.run(
    ["xset", "-q"],
    capture_output=True,
    text=True,
    timeout=2
   )

   if result.returncode != 0:
    return getattr(self, "_current_layout", "us")

   mask = None
   for line in result.stdout.splitlines():
    if "LED mask:" in line:
     mask_str = line.split("LED mask:")[-1].strip().split()[0]

     try:
      mask = int(mask_str, 16)
     except ValueError:
      break
     break

   if mask is None:
    return getattr(self, "_current_layout", "us")

   # Номер активной группы (1-based) по битам 0x1000/0x2000/0x4000...
   group = 1
   for g in range(2, 9):
    if mask & (0x1000 << (g - 2)):
     group = g
     break

   # Список групп из конфигурации XKB
   groups = self._get_xkb_groups()

   if 1 <= group <= len(groups):
    layout = "us" if groups[group - 1] == "us" else "ru"
   else:
    layout = "ru"

   self._current_layout = layout
   return layout

  except Exception as e:
   print(f"[WARN] Ошибка определения раскладки: {e}")

  return getattr(self, "_current_layout", "us")

 # Время жизни кэша живой карты XKB (сек). Cinnamon может перекомпилировать
 # карту в любой момент (добавление групп, сменя раскладок в аплете),
 # поэтому кэшируем совсем ненадолго.
 _XKB_LIVE_TTL = 2.0

 def _get_xkb_groups(self):
  """Список раскладок ЖИВОЙ карты X-сервера, например ['ru','us'].

  ВАЖНО: источник — `xkbcomp -xkb :0` (реально загруженная карта),
  а НЕ `setxkbmap -query`. Cinnamon управляет раскладками напрямую
  через xkbcomp и НЕ обновляет конфиг setxkbmap: после смены раскладок
  в аплете query продолжал отдавать старый список (например 'ru,us,ru'
  при реально живых двух группах 'ru','us') — арифметика переключения
  в set_layout шла по ложному числу групп, и буквы уходили не в той
  раскладке.
  """
  now = time.time()
  cached = getattr(self, "_xkb_groups_cache", None)
  if cached is not None and now - cached[0] < self._XKB_LIVE_TTL:
   return list(cached[1])

  groups = None
  try:
   result = subprocess.run(
    ["xkbcomp", "-xkb", ":0", "-"],
    capture_output=True,
    text=True,
    timeout=2
   )
   out = result.stdout or ""
   # Пример строки:
   #   xkb_symbols "pc+ru+us:2+inet(evdev)+group(lctrl_toggle)+..." {
   # Номер после ":N" означает группу, в которую положили раскладку.
   # Нас интересуют только раскладки ru/us (символы "ru", "us" без ":").
   m = re.search(r'xkb_symbols\s+"([^"]+)"', out)
   if m:
    parts = m.group(1).split("+")
    layouts = []
    for part in parts:
     if ":" in part:
      # "us:2" -> раскладка us лежит в группе 2; добиваем список до
      # нужной длины (группы идут по порядку).
      name, idx = part.split(":", 1)
      try:
       idx = int(idx)
      except ValueError:
       continue
      if name not in ("ru", "us"):
       continue
      while len(layouts) < idx:
       layouts.append(None)
      if idx >= 1 and layouts[idx - 1] is None:
       layouts[idx - 1] = name
     elif part in ("ru", "us"):
      # раскладка без явного номера -> следующая группа по порядку
      # (первая незанятая позиция)
      if part not in layouts:
       layouts.append(part)
    # Младшие группы важнее: чистим хвостовые None (пустые группы)
    while layouts and layouts[-1] is None:
     layouts.pop()
    # Если парсинг не смог определить группы — фолбэк на query.
    if not layouts or any(g is None for g in layouts):
     groups = None
    else:
     groups = layouts
  except Exception:
   groups = None

  # Имена ВСЕХ групп из name[groupN]. Разбор xkb_symbols выше видит только
  # явно перечисленные раскладки ('pc+ru+us:2+...'), а в этой системе
  # групп три: ru, us, ru — третью он терял и считал «неизвестной».
  try:
   named = []
   for gn, gname in re.findall(
       r'name\[group(\d+)\]\s*=\s*"([^"]*)"', out):
    idx = int(gn) - 1
    while len(named) <= idx:
     named.append(None)
    low = (gname or "").lower()
    named[idx] = ("us" if ("english" in low or
         re.search(r'(^|[^a-z])us([^a-z]|$)', low)) else "ru")
   if named and all(g is not None for g in named):
    groups = named
  except Exception:
   pass

  if groups is None:
   # Фолбэк: старый способ (кэш setxkbmap может быть устаревшим,
   # но лучше, чем ничего).
   try:
    result = subprocess.run(
     ["setxkbmap", "-query"],
     capture_output=True,
     text=True,
     timeout=2
    )
    if result.returncode == 0:
     for line in result.stdout.splitlines():
      if line.strip().startswith("layout:"):
       q = line.split(":", 1)[-1].strip().split(",")
       q = [g.strip() for g in q if g.strip()]
       if q:
        groups = q
        break
   except Exception:
    pass

  if not groups:
   groups = ["ru", "us"]

  self._xkb_groups_cache = (now, list(groups))
  return list(groups)

 
 def is_capslock_on(self):
  """
  Определение Caps Lock независимо от текущей
  русской/английской раскладки.
  """
  try:
   result = subprocess.run(
    ["xset", "-q"],
    capture_output=True,
    text=True,
    timeout=2
   )
   
   if result.returncode != 0:
    return False
   
   output = result.stdout
   
   # Сначала ищем нормальный текстовый статус.
   for line in output.splitlines():
    if "Caps Lock:" in line:
     status = line.split("Caps Lock:")[-1].strip().split()[0].lower()
     
     if status == "on":
      return True
     
     if status == "off":
      return False
   
   # Если текстового статуса почему-то нет —
   # используем LED mask.
   for line in output.splitlines():
    if "LED mask:" in line:
     mask_str = line.split("LED mask:")[-1].strip().split()[0]
     
     try:
      mask = int(mask_str, 16)
      return bool(mask & 0x04)
     except ValueError:
      pass
  
  except Exception as e:
   print(f"[WARN] Ошибка определения Caps Lock: {e}")
  
  return False
 
 def set_layout(self, lang):
  """
  Переключает раскладку на 'ru' или 'us'.

  Переключение идёт ПО ШАГУ (по одному `ISO_Next_Group` за раз) с
  проверкой реального состояния XKB после каждого шага. Раньше здесь
  число нажатий считалось арифметически и отправлялось пачкой через
  `xte`; когда XTEST-вызов не проходил (а он периодически падает с
  "BadValue ... X_XTestFakeInput"), буквы уходили в чужой раскладке —
  английский текст печатался кириллицей. Теперь каждый щелчок
  подтверждается `xset`, а не сработавший щелчок повторяется другим
  способом (см. _switch_group).
  """
  if lang not in ("ru", "us"):
   return False

  n_groups = max(2, len(self._get_xkb_groups()))

  # Уже стоим на нужной раскладке — ничего не делаем.
  if self.get_current_layout() == lang:
   self._current_layout = lang
   return True

  for _ in range(n_groups + 1):
   self._switch_group()
   time.sleep(0.08)  # даём XKB время переключить группу
   if self.get_current_layout() == lang:
    self._current_layout = lang
    return True

  print(f"[ERROR] Не удалось переключить раскладку на {lang}")
  return False

 def _switch_group(self):
  """Один щелчок по 'следующая раскладка' (ISO_Next_Group).

  Способы пробуются по очереди (xte, xdotool, своя клавиатура), и
  КАЖДЫЙ проверяется по `xset`: группа реально сменилась и осталась
  новой — значит переключение состоялось. Раньше переключение
  отправлялось пачкой без проверки, поэтому единичный неудачный
  XTEST-вызов тихо оставлял английский текст в русской раскладке.
  """
  before = self._current_xkb_group()

  # Перед переключением гасим модификаторы. Пока X считает Shift (или
  # Ctrl) нажатым, ISO_Next_Group срабатывает не как «защёлка» с
  # постоянным переключением, а как LATCH — группа на мгновение
  # меняется и отменяется СЛЕДУЮЩИМ нажатием. Из-за этого проверка
  # через xset попадала в зазор и всегда видела «не переключилось»:
  # английские символы уходили в русскую раскладку (воспроизводилось
  # на строке из одних shift-символов: !"#$%&...).
  self._release_modifiers()

  # Основной путь — XTEST (xte, затем xdotool): он работает всегда,
  # пока доступен. Раньше переключение шло пачкой через xte БЕЗ
  # проверки результата, и когда вызов не проходил, английский текст
  # уходил кириллицей. Теперь каждый щелчок проверяется по `xset`.
  for cmd in (["xte", "key ISO_Next_Group"],
   ["xdotool", "key", "ISO_Next_Group"]):
   try:
    subprocess.run(cmd, check=True, timeout=2, capture_output=True)
   except Exception:
    # Это запасной путь, и следующий способ почти наверняка
    # сработает — молча уходим дальше, ругаться не на что.
    continue
   if self._group_switch_stuck(before):
    return True
   # группа вернулась обратно (тот самый latch) — пробуем ещё раз
   self._release_modifiers()

  # Запасной путь — Left Ctrl на нашей виртуальной клавиатуре
  # (работает, если в раскладке ISO_Next_Group назначен на Ctrl).
  # Используется последним: такое нажатие уходит и в активное окно.
  try:
   self._release_modifiers()
   _, after = self._toggle_group_once()
   if after != before and not self._group_reverted(before):
    return True
  except Exception as e:
   print(f"[WARN] Не удалось переключить группу через UInput: {e}")
  return False

 def _release_modifiers(self):
   """Гасит модификаторы на виртуальной клавиатуре (без нажатий)."""
   for code in (ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
        ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
        ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT):
    try:
     self.ui.write(ecodes.EV_KEY, code, 0)
     self.ui.syn()
    except Exception:
     pass
   time.sleep(0.02)

 def _group_switch_stuck(self, before, settle=0.15):
   """Проверяет, что группа сменилась И осталась в новом состоянии.

   Первая проверка сразу после щелчка, вторая — после задержки: так
   отсекается LATCH-переключение, которое отменяется следующим
   нажатием (иначе символ печатался бы в старой раскладке).
   """
   time.sleep(0.04)
   if self._current_xkb_group() == before:
    return False
   time.sleep(settle)
   return not self._group_reverted(before)

 def _group_reverted(self, before):
   return self._current_xkb_group() == before

 def _set_capslock(self, on):
  """Включает/выключает Caps Lock и проверяет результат через xset."""
  for _ in range(3):
   if self.is_capslock_on() == on:
    return True
   try:
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_CAPSLOCK, 1)
    self.ui.syn()
    time.sleep(0.03)
    self.ui.write(ecodes.EV_KEY, ecodes.KEY_CAPSLOCK, 0)
    self.ui.syn()
    time.sleep(0.1)
   except Exception as e:
    print(f"[WARN] Не удалось переключить Caps Lock: {e}")
    return False
  return self.is_capslock_on() == on
 def _current_xkb_group(self):
  """Номер текущей активной группы XKB (1-based) по LED mask."""
  try:
   result = subprocess.run(
    ["xset", "-q"],
    capture_output=True,
    text=True,
    timeout=2
   )
   if result.returncode != 0:
    return None
   for line in result.stdout.splitlines():
    if "LED mask:" in line:
     mask_str = line.split("LED mask:")[-1].strip().split()[0]
     try:
      mask = int(mask_str, 16)
     except ValueError:
      return None
     for g in range(2, 9):
      if mask & (0x1000 << (g - 2)):
       return g
     return 1
  except Exception:
   return None
  return None
 
 
 def _resolve_char(self, ch, current_layout):
  """Как напечатать символ в ТЕКУЩЕЙ раскладке: (keycode, shift) или None.

  Символ ищется сначала в текущей раскладке — тогда цифры, знаки и
  буквы, одинаковые в обеих раскладках, печатаются без единого
  переключения.
  """
  return self.layout_maps.get(current_layout, {}).get(ch)

 def _other_layout(self, ch, current_layout):
  """В какой раскладке есть этот символ, если не в текущей."""
  other = "us" if current_layout == "ru" else "ru"
  if ch in self.layout_maps.get(other, {}):
   return other
  return None

 def _type_via_xdotool(self, text):
  """Печатает строку через xdotool — работает для ЛЮБОГО символа
  (Unicode, «ёлочки», тире, эмодзи) и НЕ требует переключения
  раскладки. Используется как запасной путь, когда символа нет в
  текущей раскладке или смена раскладки не работает.
  """
  if not text:
   return True
  for cmd in (["xdotool", "type", "--clearmodifiers", "--delay", "12", text],
              ["xdotool", "key", "--clearmodifiers", text]):
   try:
    subprocess.run(cmd, check=True, timeout=10, capture_output=True)
    return True
   except Exception as e:
    last = e
  print(f"[WARN] xdotool не смог напечатать {text!r}: {last}")
  return False

 def type_text(self, text, delay=0.02):
  """Печать с координацией с punto.py (см. шапку файла).

  1. Ждём, пока punto отпустит «залипшие» модификаторы (липкие клавиши):
     чужой Shift меняет регистр наших букв, чужой Ctrl/Alt превращает
     клавиши в хоткеи (Ctrl+S вместо 's').
  2. Берём межпроцессную блокировку печати (flock на
     /tmp/kb_scripts_typing.lock): пока печатаем мы, punto не
     переключает раскладку и не печатает свою замену, и наоборот.
     flock освобождается ядром при смерти процесса, поэтому зависнуть
     навсегда не может (см. Отчет §5).
  """
  seq = _voice_typing_start()
  _wait_sticky_clear(timeout=0.5, seq=seq)
  fd = _typing_lock_acquire(timeout=10.0)
  try:
   return self._type_text_impl(text, delay=delay, seq=seq)
  finally:
   _typing_lock_release(fd)
   _voice_typing_stop()

 def _type_text_impl(self, text, delay=0.02, seq=None):
  """
  Печать текста, где русские и английские слова идут вперемешку.

  Учитывает:
  - обе раскладки и переключение между ними прямо внутри строки;
  - Caps Lock (на время печати гасится, в конце возвращается как было);
  - Shift, знаки препинания и цифры;
  - символы, которых нет на клавиатуре ('—', '…', '«»', '€');
  - РЕАЛЬНОЕ состояние раскладки: перед символом, которому нужна
    другая раскладка, состояние XKB переспрашивается, поэтому если
    пользователь переключил раскладку вручную во время печати,
    скрипт вернёт нужную и продолжит печатать правильно;
  - восстановление исходной раскладки в конце.

  Если смена раскладки не удаётся (X-сервер отвечает на ISO_Next_Group
  через раз — такое бывает на этой системе, особенно в первые секунды
  работы и после символов со Shift), символы печатаются через
  xdotool, а не теряются. Поэтому английские слова не пропадают.
  """

  shift_delay = 0.01

  maps = self.layout_maps

  original_layout = self.get_current_layout()
  current_layout = original_layout

  # Caps Lock ломает цифры и знаки (KEY_1 начинает печатать '!'),
  # поэтому на время печати гасим его, а в конце возвращаем как было.
  # Если погасить не удалось — печатаем с учётом его состояния.
  original_caps = self.is_capslock_on()
  if original_caps and not self._set_capslock(False):
   print("[WARN] Не удалось выключить Caps Lock — цифры и знаки могут "
    "печататься неверно")
  caps_on = self.is_capslock_on()

  # Кэш последней проверки реальной раскладки обнуляем на каждый вызов:
  # иначе начало второго сообщения печаталось бы по устаревшей
  # раскладке (симптом «первые буквы иногда не на своём языке»).
  self._last_layout_check = 0.0
  # Момент последней проверки чужих залипших модификаторов (/tmp/kb_sticky_mods.json).
  self._last_sticky_check = 0.0

  warned = set()
  # Символы, которые нельзя напечатать текущей раскладкой: копятся и
  # уходят одним вызовом xdotool.
  pending = []

  def flush_pending():
   if pending:
    self._type_via_xdotool("".join(pending))
    pending.clear()
    time.sleep(delay)

  # Смена раскладки не сработала — дальше печатаем через xdotool.
  no_switch = False

  for ch in text:

   keycode = None
   need_shift = False

   # ------------------------------------------------
   # Символ -> клавиша текущей раскладки
   # ------------------------------------------------

   if ch == "\n":
    keycode, need_shift = ecodes.KEY_ENTER, False
   elif ch == "\t":
    keycode, need_shift = ecodes.KEY_TAB, False
   elif ch == " ":
    keycode, need_shift = ecodes.KEY_SPACE, False
   elif ch == "\r":
    continue
   else:
    entry = self._resolve_char(ch, current_layout)

    if entry is None:
     # Символа нет в текущей раскладке — пробуем сменить раскладку.
     target = self._other_layout(ch, current_layout)
     if target is not None and not no_switch:
      now = time.time()
      if now - getattr(self, "_last_layout_check", 0) > 0.35:
       real = self.get_current_layout()
       if real != current_layout:
        current_layout = real
       self._last_layout_check = now
      if current_layout != target:
       if self.set_layout(target):
        current_layout = target
       else:
        # set_layout не смог переключить — ПОВТОРЯЕМ попытку: молчаливый
        # continue здесь проглатывал буквы (симптом «не пишет некоторые
        # буквы на английском»).
        ok = False
        for attempt in range(3):
         time.sleep(0.15)
         if self.set_layout(target):
          current_layout = target
          ok = True
          break
        if not ok:
         print(
          f"[ERROR] Не удалось установить "
          f"раскладку {target} для {repr(ch)}"
         )
         no_switch = True
      entry = self._resolve_char(ch, current_layout)

    if entry is None:
     # Напечатать нечем — отдаём символ xdotool: он подставит нужный
     # keysym сам, раскладка при этом не важна. Так символы вроде
     # «—», «…», «» и английские буквы (если раскладка не
     # переключается) не теряются.
     if ch.isprintable():
      pending.append(ch)
     elif ch not in warned:
      warned.add(ch)
      print(f"[WARN] Неизвестный символ: {repr(ch)}")
     continue

    keycode, need_shift = entry

   if keycode is None:
    continue

   # Залипшие модификаторы ДРУГОГО скрипта (punto) могли появиться уже
   # во время нашей печати: чужой Shift портит регистр, чужой Ctrl/Alt
   # превращает клавишу в хоткей. Не чаще раза в 0.3 с переспрашиваем
   # общее состояние (/tmp/kb_sticky_mods.json) и ждём отпускания
   # (макс. ~5.5 с — дедлайн залипания punto всё равно истечёт).
   if time.time() - getattr(self, "_last_sticky_check", 0) > 0.3:
    self._last_sticky_check = time.time()
    _wait_sticky_clear(timeout=0.3, seq=seq)

   # Перед любым нажатием сначала дописываем отложенные символы —
   # иначе они окажутся ПОЗЖЕ пробела/enter'а, который печатается
   # напрямую (к��вычка «50%  —до» вместо «50% — до»).
   flush_pending()

   # Caps Lock инвертирует буквы: при включённом Caps строчная буква
   # требует Shift, а заглавная — нет.
   if caps_on and ch.isalpha():
    need_shift = not need_shift

   # ------------------------------------------------
   # Shift
   # ------------------------------------------------

   if need_shift:
    self.ui.write(
     ecodes.EV_KEY,
     ecodes.KEY_LEFTSHIFT,
     1
    )
    self.ui.syn()

    # Задержка после нажатия Shift: X не всегда успевает зафиксировать
    # модификатор до нажатия буквы — буква выходила без shift.
    time.sleep(max(shift_delay, 0.03))

   # ------------------------------------------------
   # Нажатие клавиши
   # ------------------------------------------------

   try:
    self.ui.write(
     ecodes.EV_KEY,
     keycode,
     1
    )
    self.ui.syn()

    time.sleep(max(delay / 3.5, 0.006))

    self.ui.write(
     ecodes.EV_KEY,
     keycode,
     0
    )
    self.ui.syn()

    # Пауза до отпускания Shift: буква и Shift release в одном такте
    # могут склеиться в одно событие -> буква терялась.
    if need_shift:
     time.sleep(max(delay / 3.5, 0.006))

   finally:

    # Shift обязательно отпускаем.
    # Иначе при исключении он может "залипнуть".
    if need_shift:
     self.ui.write(
      ecodes.EV_KEY,
      ecodes.KEY_LEFTSHIFT,
      0
     )
     self.ui.syn()

   time.sleep(delay)

  # ----------------------------------------------------
  # Хвост, который не удалось напечатать текущей раскладкой
  # ----------------------------------------------------

  flush_pending()

  # ----------------------------------------------------
  # Возвращаем исходную раскладку и состояние Caps Lock
  # ----------------------------------------------------

  if self.get_current_layout() != original_layout:
   self.set_layout(original_layout)

  if caps_on != original_caps:
   self._set_capslock(original_caps)

# Один экземпляр на весь процесс: при создании проверяется NumLock
# (индикатор на нумпаде остаётся горячим) и прогревается смена раскладки.
try:
  typer = SmartTyper()
except Exception as e:
  print(f"[WARN] SmartTyper недоступен: {e}. Печать через xdotool.")
  typer = None
def _find_keyboards():
  """Только физические клавиатуры — виртуальные (наши и punto) отсекаем."""
  _list = []
  for path in glob.glob("/dev/input/event*"):
   try:
    dev = InputDevice(path)
    name = (dev.name or "").lower()
    if ("keyboard" in name or "корпус" in name or "logitech" in name
        or "at translate" in name or "virtual core" in name) and \
        "smart" not in name and "mouse setting" not in name \
        and "virtual" not in name:
     _list.append(dev)
   except Exception:
    pass
  return _list


def _evdev_key_listener():
  """Флаги для process_text и обновление словаря — без захвата X11."""
  devs = _find_keyboards()
  while True:
   try:
    if not devs:
     devs = _find_keyboards()
     time.sleep(0.5)
     continue
    fds = {d.fd: d for d in devs}
    r, _, _ = select(list(fds), [], [], 0.5)
    for fd in r:
     try:
      for event in fds[fd].read():
       if event.type != ecodes.EV_KEY or event.value not in (1, 2):
        continue
       code = event.code
       if code == ecodes.KEY_RIGHTSHIFT:
        k.set_flag(True)
       elif code in (ecodes.KEY_SPACE, ecodes.KEY_LEFT, ecodes.KEY_RIGHT,
                     ecodes.KEY_UP, ecodes.KEY_DOWN):
        k.set_flag(False)
       elif code == ecodes.KEY_LEFTALT:
        k.update_dict()
     except BlockingIOError:
      pass
     except OSError:
      devs = _find_keyboards() or devs
     except Exception:
      pass
   except Exception:
    time.sleep(0.2)

threading.Thread(target=_evdev_key_listener, daemon=True).start()

def replace(match):
  res = k.get_dict()
  return res[match.group(0)]

def repeat(text1 : str):  # text = "linux менч установить линукс минт помоги мне установить "
  text=text1.replace("?", "").replace("!", "")#.replace(".", "")
  k.save_text(text)
  text1 = ""
  res = k.get_dict()
  k.save_words(res)
  words = k.get_words()  #print(words)
  try:   # Создаем регулярное выражение для всех слов и словосочетаний из словаря
   words_regex = r'\b(' + r'|'.join(map(re.escape, words)) + r')\b'
   # Выполняем замену с учетом регистра
   text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
   k.save_text(text1)
   # Дополнительная замена для слов из словаря res
   # for word, replacement in res.items():
   #  text1 = re.sub(r'\b' + re.escape(word) + r'\b', replacement, text1, flags=re.IGNORECASE)
  except Exception as ex:
   print(f"Ошибка: {ex}")  # Выводим ошибку для диагностики
  return text1
# llm=load_model(MODEL_PATH)
def press_keys(text):
  """Печать через SmartTyper из write_text_fast.py.

  NumLock не трогаем: лампочка на нумпаде горит постоянно. Раньше здесь
  для КАЖДОГО символа запускался bash с `xte "key Num_Lock"` — индикатор
  мигал/выключался, русские и английские буквы печатались разными
  механизмами и часть знаков терялась.
  """
  try:
    text = repeat(text)
    print(text)
    if typer is not None:
      typer.type_text(text, delay=0.02)
    else:
      # Резервный путь, если evdev/UInput недоступны.
      subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", text],
                     check=False)
  except Exception as ex1:
    print(ex1)
    return

def process_text(previous_message1):
  text = previous_message1 + str(" ")
  text=text[0].lower()+ text[1:]
  if k.get_flag() == True:
    k.set_flag(False)
    text0 = text[0].upper() + text[1:]
    press_keys(text0)
  else:
    press_keys(text)

def record_audio(filename = "temp.wav", duration=10, fs=48000):  # Запись аудио с микрофона
 print("star...")
 # Запись аудио
 audio_data = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float64')
 sd.wait()  # Ждем окончания записи
 audio_data = audio_data.flatten().astype(np.float32) # Конвертируем в нужный формат и сохраняем
 wavfile.write(filename, fs, (audio_data * 32767).astype(np.int16))

def enhance_speech_for_recognition(audio, sample_rate=16000):
 try:
   x = audio.astype(np.float32).copy()
   eps = 1e-8
   # Параметры компрессии (внутренние)

   threshold_db = -35  # порог, ниже которого считаем фрагмент тихим
   ratio = 4.0  # степень компрессии
   attack = 0.005  # время реакции при уменьшении громкости
   release = 0.03  # время восстановления громкости


   # 1. Считаем RMS (энергетику) в окне 10 мс,
   # чтобы определить громкость в каждый момент времени

   window = int(sample_rate * 0.01)  # 10 мс окно
   rms = np.sqrt(
    np.convolve(x * x, np.ones(window) / window, mode='same') + eps   )

   # 2. RMS → dB (логарифмическая шкала)
   rms_db = 20 * np.log10(rms + eps)

   # 3. Определяем, насколько сигнал превышает порог threshold_db
   # если не превышает — усиливать не нужно
   over_threshold = rms_db - threshold_db

   # 4. Вычисляем коэффициент усиления в dB:
   # чем громче сигнал, тем сильнее его "сжимаем"
   # тихие фрагменты остаются без изменений

   gain_db = np.where(    over_threshold > 0,
    -over_threshold * (1 - 1 / ratio),    0   )

   # 5. Переводим усиление из dB → линейный коэффициент

   gain = 10 ** (gain_db / 20)

   # 6. Сглаживаем коэффициент (attack / release),
   # чтобы не было щелчков и резких переходов

   smoothed_gain = np.zeros_like(gain)

   attack_coeff = np.exp(-1 / (sample_rate * attack))
   release_coeff = np.exp(-1 / (sample_rate * release))

   g = 1.0  # текущее плавное усиление

   for i in range(len(gain)):
    if gain[i] < g:
     # Быстрое уменьшение громкости
     g = attack_coeff * g + (1 - attack_coeff) * gain[i]
    else:
     # Медленное восстановление громкости
     g = release_coeff * g + (1 - release_coeff) * gain[i]
    smoothed_gain[i] = g

   # 7. Применяем сглаженное усиление к аудио
   compressed = x * smoothed_gain

   # 8. Небольшая нормализация, чтобы итоговый сигнал
   # занимал почти весь диапазон, но без клиппинга
   peak = np.max(np.abs(compressed))
   if peak > 0:
    compressed = compressed / peak * 0.98
   # Возвращаем улучшённое аудио
   return compressed.astype(np.float32)

   ## 1. Полосовая фильтрация (Оставляем без изменений)
   # Фокусируемся на частотах речи
   # b, a = signal.butter(2, [100 / nyquist, 6000 / nyquist], btype='band')
   # audio = signal.filtfilt(b, a, audio)

  ## 2. Более агрессивное усиление с нормализацией (AGC)
   # Увеличиваем максимальный коэффициент усиления (с 3.0 до 5.0)
   # rms = np.sqrt(np.mean(audio ** 2))
   # if rms > 0:
   #  # Позволяем более сильное усиление для тихих фрагментов
   #  gain = min(4.0, 0.9 / rms)
   #  audio *= gain

   # 3. Улучшенная, более мягкая компрессия
    # Понижаем порог (-28dB вместо -12dB), чтобы захватить более тихие звуки
   # threshold_db = -28
   # threshold = 10 ** (threshold_db / 20)

   # Сглаживание огибающей
   # gain = np.ones_like(audio)

    # Смягчаем коэффициент компрессии (0.15 вместо 0.25),
    # чтобы не сильно "сплющивать" динамику, позволяя модели
    # лучше различать нечеткие звуки.
   # envelope = np.abs(audio)
   # envelope_smooth = np.convolve(envelope, np.ones(100) / 100, mode='same')
   # compression_mask = envelope_smooth > threshold
   # gain[compression_mask] = (threshold / envelope_smooth[compression_mask]) ** 0.15

   # audio *= gain
   # audio = np.clip(audio, -0.9, 0.9)
   return audio

 except Exception as e:
  print(f"Ошибка обработки аудио: {e}")
  return audio
def audio(model, filename = "temp.wav"):  # Путь к аудиофайлу
  try:    # Выполняем транскрипцию аудио
   segments, info = model.transcribe( filename, language="ru",  # Русский язык явно
    beam_size=20,  # Глубокий поиск — повышает точность
    best_of=10,  # Выбирает лучший результат из 10 гипотез
    temperature=0.55,  # Детеминированно, без случайных ошибок
    vad_filter=False  # Включено — фильтрует шум и паузы
    # ,vad_parameters=dict(  min_silence_duration_ms=800,  # Пауза 0.8 секунды — чтобы не обрывал фразы
    #  speech_pad_ms=300  ),# 0.3 секунды запаса по краям фразы
    # condition_on_previous_text=False,  # Избегает “залипания” на предыдущем тексте
    # no_speech_threshold=0.35,  # Позволяет улавливать даже очень тихую речь
    # log_prob_threshold=-1.2,  # Терпимее к неуверенным звукам
    # compression_ratio_threshold=2.6,  # Разрешает немного "неидеальные" слова
    # repetition_penalty=1.05,  # Мягко борется с повторами, не убивая естественность
    # patience=4.0,  # Больше терпения при нечетких звуках
    # chunk_length=20,  # Короткие отрезки — лучше для неравномерной речи
    # suppress_tokens=[-1],  word_timestamps=False   # Новый параметр: отключаем пунктуацию и заглавки
    #initial_prompt="Transcribe the audio in lowercase letters without any punctuation marks, periods, commas, or capitalization. Write everything as plain lowercase text."
    # Или на русском:
    # , initial_prompt="Транскрибируй аудио маленькими буквами без знаков препинания, точек, запятых или заглавных букв. Пиши всё простым текстом в нижнем регистре."
    #                  "Все числа записывай словами (например, 23 → двадцать три). Пиши всё простым текстом в нижнем регистре."
    )

   message_parts = []
   for segment in segments:
    text = segment.text
    if not text:
     continue
    text = str(text).strip().lower()
    if not text:
     continue

    # Разбиваем на слова и гарантируем, что каждое — строка
    words = text.split()
    for word in words:
     # Даже если это число — превратим в строку
     message_parts.append(str(word))

    # Финальная защита: все элементы — строки
   message_parts = [str(part) for part in message_parts if str(part).strip()]
   return ' '.join(message_parts) if message_parts else None

  except Exception as e:
   print(f"Ошибка транскрипции: {e}")
   return None

  except Exception as e:
     print(f"Ошибка транскрипции: {e}")
     return None

def is_speech(threshold=0.074, audio_source="temp.wav"):
 try:
  # Если передана строка — читаем файл
  if isinstance(audio_source, (str, bytes, os.PathLike)):
   if not os.path.isfile(audio_source):
    print(f"Файл не найден: {audio_source}")
    return False
   data, sr = sf.read(audio_source, dtype='float32')

  # Если уже массив numpy
  elif isinstance(audio_source, np.ndarray):
   data = audio_source.astype('float32')  # на всякий случай приводим тип

  else:
   print("Неподдерживаемый тип данных")
   return False

  if len(data) == 0:
   print("Аудио пустое")
   return False

  # Средняя амплитуда
  amp = np.mean(np.abs(data))
  print(f"amp {amp:.5f}")
#  if amp > threshold:

  return amp > threshold

 except Exception as ex:
  print(f"Ошибка в is_speech: {ex}")
  return False
    # # === 3. Усиление тихих фрагментов (адаптивное AGC) ===
    # frame_len = int(0.08 * sample_rate)  # 80 мс
    # hop = int(frame_len / 2)
    # target_rms = 0.15
    # out = np.copy(audio)
    #
    # for i in range(0, len(audio) - frame_len, hop):
    #   seg = audio[i:i + frame_len]
    #   rms = np.sqrt(np.mean(seg ** 2)) + 1e-9
    #   if rms < target_rms:
    #     gain = min(target_rms / rms, 8.0)  # сильнее для тихих
    #     out[i:i + frame_len] = seg * gain
    #
    # audio = out
    #
    # # === 4. Мягкая нормализация ===
    # peak = np.max(np.abs(audio)) + 1e-9
    # if peak > 0:
    #   audio = (audio / peak) * 0.98
    #
    # # === 5. Лёгкий лимитер (мягкое сглаживание пиков) ===
    # audio = np.tanh(audio * 1.05) * 0.98

def get_webcam_source_id():# Определяет текущий Source ID (например, '53') для HD Webcam C525,
 # Постоянное имя вашего микрофона с веб-камеры (из вашего вывода)
 TARGET_NAME = "alsa_input.usb-046d_HD_Webcam_C525_79588C20-00.mono-fallback"
 try:
  # Самый быстрый способ — использовать pactl list sources в "short" формате
  result = subprocess.run(  ['pactl', 'list', 'sources', 'short'],
   capture_output=True, text=True, check=True  )

  # Формат строки: 53    alsa_input.usb-046d_HD_Webcam_C525_...mono-fallback    PipeWire    s16le 1ch 4800Hz    RUNNING
  for line in result.stdout.splitlines():
   fields = line.split()
   if len(fields) >= 2 and TARGET_NAME in fields[1]:
    return fields[0]  # это и есть ID источника

  print("Webcam C525 не найдена в pactl list sources short", file=sys.stderr)
  return None

 except FileNotFoundError:
  print("pactl не найден. Установлен PipeWire/PulseAudio?", file=sys.stderr)
  return None
 except subprocess.CalledProcessError as e:
  print(f"pactl вернул ошибку: {e}", file=sys.stderr)
  return None

def set_mute(mute: str, source_id: str):
 if source_id is None:
  print("source_id = None → ничего не делаем", file=sys.stderr)
  return # mute = "1" или "0"
 subprocess.run(["pactl", "set-source-mute", source_id, mute], check=True)
 # Опционально — сразу ставим нормальную громкость
 subprocess.run(["pactl", "set-source-volume", source_id, "99%"], check=True)
source_id = get_webcam_source_id()      # ← твоя функция
set_mute("0", source_id)

def get_mute_status(source_id: str) -> bool:  # Получает статус 'Mute' для указанного источника (source) в PulseAudio.
 # Поддерживает английский (yes/no) и русский (да/нет) вывод.
 #
 # Возвращает:
 #     True  — если muted (приглушено),
 #     False — если не muted.
 # Выбрасывает исключение при ошибке pactl или неизвестном формате.

 try:
  # Выполняем команду без смены локали — поддерживаем оба языка
  result = subprocess.run(["pactl", "get-source-mute", source_id],
   capture_output=True, text=True, check=True)
  output = result.stdout.strip()

  # Ищем строку вида "Mute: значение", регистронезависимо
  match = re.search(r'Mute\s*:\s*(\S+)', output, re.IGNORECASE)
  if not match:
   raise ValueError(f"Не удалось найти 'Mute:' в выводе pactl: {output!r}")
   return False
  value = match.group(1).lower()
  # Поддерживаем оба языка:
  if value in ('yes', 'да'):
   return False
  elif value in ('no', 'нет'):
   return True
  else:
   raise ValueError(f"Неизвестное значение mute: {value!r} (ожидалось yes/no/да/нет)")
   return False

 except subprocess.CalledProcessError as e:
  return False
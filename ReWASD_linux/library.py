#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Сгенерировано сборщиком build_3files.py из оригинальных исходников.
# Логика не изменена — убраны только межмодульные импорты и блоки __main__.
# =====================================================================
# ДОПОЛНИТЕЛЬНАЯ БИБЛИОТЕКА: данные, движок эмуляции геймпада (evdev),
# движок мыши/клавиатуры (pynput), менеджеры профилей и окно настроек мыши.
# =====================================================================
import sys, os, json, time, glob, subprocess, threading, copy, re, signal, pwd
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from select import select

import psutil
# deepdiff импортируется лениво — только при закрытии окна настроек мыши
import evdev
from evdev import UInput, AbsInfo, ecodes, InputDevice, categorize, list_devices

# Глобальная библиотека keyboard нужна Editor_settings для hotkey «End».
# pynput-клавиатура импортируется под другим именем, чтобы не было коллизии.
from pynput import mouse, keyboard as pynput_keyboard
from pynput.mouse import Button as Button_Controller, Controller
from pynput.keyboard import Key, Listener
import keyboard  # on_press_key("end", ...) — ловит клавишу даже в fullscreen

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTextEdit, QTabWidget, QScrollArea, QFrame, QCheckBox,
    QLineEdit, QMessageBox, QStyleFactory, QToolTip, QGridLayout, QDialog,
    QPlainTextEdit, QSystemTrayIcon, QMenu, QInputDialog, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QObject, QEvent
from PyQt6.QtGui import (
    QFont, QIcon, QColor, QPalette, QTextCursor, QKeySequence, QAction,
)

# Визуальные классы лежат в отдельном файле «внешнего вида».
from appearance import MainWindow, VirtualKeyboard, ZONE_DEFINITIONS, KEY_MAPPER


# === Pyqt6_libs_data.py (данные и чистые функции) ===

# -*- coding: utf-8 -*-
# ТРЕТИЙ СКРИПТ: модуль ДАННЫХ и чистых функций.
# Здесь собраны все списки, словари и простые функции, с которыми работают
# интерфейс (Pytq6_mouse_setting_control_for_buttons_for_linux.py) и логика
# (Pyqt6_libs_mouse.py). Импортируется обоими:  from Pyqt6_libs_data import *
# Правило отступа: 1 пробел за уровень. Комментарии только через #.
# ==== ДАННЫЕ: списки и словари ====


# Словари транслитерации (en<->ru) для поиска макроса по введённой клавише.
en_to_ru = {'a': 'ф', 'A': 'Ф', 'b': 'и', 'B': 'И', 'c': 'с', 'C': 'С', 'd': 'в', 'D': 'В', 'e': 'у', 'E': 'У', 'f': 'а', 'F': 'А', 'g': 'п', 'G': 'П',
 'h': 'р', 'H': 'Р', 'i': 'ш', 'I': 'Ш', 'j': 'о', 'J': 'О', 'k': 'л', 'K': 'Л',
 'l': 'д', 'L': 'Д', 'm': 'ь', 'M': 'Ь', 'n': 'т', 'N': 'Т', 'o': 'щ', 'O': 'Щ', 'p': 'з', 'P': 'З', 'q': 'й', 'Q': 'Й', 'r': 'к', 'R': 'К', 's': 'ы', 'S': 'Ы',
 't': 'е', 'T': 'Е', 'u': 'г', 'U': 'Г', 'v': 'м', 'V': 'М',
 'w': 'ц', 'W': 'Ц', 'x': 'ч', 'X': 'Ч', 'y': 'н', 'Y': 'Н', 'z': 'я', 'Z': 'Я', '.': '-', ',': '+', ' ': ' '}
ru_to_en = {'ф': 'a', 'Ф': 'A', 'и': 'b', 'И': 'B', 'с': 'c', 'С': 'C', 'в': 'd', 'В': 'D', 'у': 'e', 'У': 'E', 'а': 'f', 'А': 'F',
 'п': 'g', 'П': 'G', 'р': 'h', 'Р': 'H', 'ш': 'i', 'Ш': 'I', 'о': 'j', 'О': 'J', 'л': 'k', 'Л': 'K',
 'д': 'l', 'Д': 'L', 'ь': 'm', 'Ь': 'M', 'т': 'n', 'Т': 'N', 'щ': 'o', 'Щ': 'O', 'з': 'p', 'З': 'P', 'й': 'q',
 'Й': 'Q', 'к': 'r', 'К': 'R', 'ы': 's', 'Ы': 'S', 'е': 't', 'Е': 'T', 'г': 'u', 'Г': 'U', 'м': 'v', 'М': 'V',
 'ц': 'w', 'Ц': 'W', 'ч': 'x', 'Ч': 'X', 'н': 'y', 'Н': 'Y', 'я': 'z', 'Я': 'Z', '-': '.', '+': ',', ' ': ' '}

# Коды/имена клавиш и кнопок мыши.
KEYS = {" ": 0x0, "LBUTTON": 'mouse left', "RBUTTON": 'mouse right', "WHEEL_MOUSE_BUTTON": "mouse middle",
 "WHEEL_MOUSE_UP": "WHEEL_MOUSE_UP", "MBUTTON": 0x04, "SCROLL_UP": "scroll_up",
 "SCROLL_DOWN": "scroll_down", "XBUTTON1": 0x05, "XBUTTON2": 0x06, "BACKSPACE": "BackSpace",
 "TAB": "Tab", "CLEAR": 0x0C, "RETURN": "Return", "KP_Enter": "KP_Enter",
 "Shift_L": "Shift_L", "CONTROL": "CONTROL", "MENU": 0x12, "PAUSE": 0x13, "CAPITAL": 0x14,
 "KANA": 0x15, "JUNJA": 0x17, "FINAL": 0x18, "KANJI": 0x19, "ESCAPE": 0x1B,
 "CONVERT": 0x1C, "NONCONVERT": 0x1D, "ACCEPT": 0x1E, "MODECHANGE": 0x1F, "SPACE": "space",
 "PRIOR": 0x21, "NEXT": 0x22, "END": "0x23", "HOME": "Home", "LEFT": "Left", "UP": "Up",
 "RIGHT": "Right", "DOWN": "Down", "SELECT": 0x29, "PRINT": 0x2A, "EXECUTE": 0x2B, "SNAPSHOT": 0x2C,
 "INSERT": 0x2D, "DELETE": "Delete", "HELP": 0x2F, "LWIN": "Super_L", "RWIN": "Super_R",

 "KEY0": 0, "KEY1": 1, "KEY2": 2, "KEY3": 3, "KEY4": 4, "KEY5": 5, "KEY6": 6,
 "KEY7": 7, "KEY8": 8, "KEY9": 9, "A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F",
 "G": "G", "H": "H", "I": "I", "J": "J", "K": "K", "L": "L", "M": "M", "N": "N", "O": "O",
 "P": "P", "Q": "Q", "R": "R", "S": "S", "T": "T", "U": "U", "V": "V", "W": "W", "X": "X", "Y": "Y",
 "Z": "Z",

 "APPS": 0x5D, "SLEEP": 0x5F, "NUMPAD0": 0x60, "NUMPAD1": 79, "NUMPAD2": 80, "NUMPAD3": 81, "NUMPAD4": 82,
 "NUMPAD5": 83, "NUMPAD6": 84, "NUMPAD7": 85, "NUMPAD8": 86, "NUMPAD9": 87, "MULTIPLY": 0x6A, "ADD": 78,
 "SEPARATOR": 0x6C, "SUBTRACT": 0x6D, "DECIMAL": 0x6E, "DIVIDE": 0x6F, "F1": "F1", "F2": "F2", "F3": "F3",
 "F4": "F4", "F5": "F5", "F6": "F6", "F7": "F7", "F8": "F8", "F9": "F9", "F10": "F10", "F11": "F11", "F12": "F12",

 "F13": 0x7C, "F14": 0x7D, "F15": 0x7E, "F16": 0x7F, "F17": 0x80, "F18": 0x81, "F19": 0x82, "F20": 0x83, "F21": 0x84,
 "F22": 0x85, "F23": 0x86, "F24": 0x87, "NUMLOCK": "Num_Lock", "SCROLL": "Scroll_Lock", "OEM_FJ_JISHO": 0x92, "OEM_FJ_MASSHOU": 0x93,
 "OEM_FJ_TOUROKU": 0x94, "OEM_FJ_LOYA": 0x95, "OEM_FJ_ROYA": 0x96, "RSHIFT": "Shift_R", "LCONTROL": "ISO_Next_Group",
 "RCONTROL": "Control_R", "LMENU": 0xA4, "RMENU": 0xA5, "BROWSER_BACK": 0xA6, "BROWSER_FORWARD": 0xA7, "BROWSER_REFRESH": 0xA8,
 "BROWSER_STOP": 0xA9, "BROWSER_SEARCH": 0xAA, "BROWSER_FAVORITES": 0xAB, "BROWSER_HOME": 0xAC, "VOLUME_MUTE": 0xAD, "VOLUME_DOWN": 0xAE,
 "VOLUME_UP": 0xAF, "MEDIA_NEXT_TRACK": 0xB0, "MEDIA_PREV_TRACK": 0xB1, "MEDIA_STOP": 0xB2, "MEDIA_PLAY_PAUSE": 0xB3, "LAUNCH_MAIL": 0xB4,
 "LAUNCH_MEDIA_SELECT": 0xB5, "LAUNCH_APP1": 0xB6, "LAUNCH_APP2": 0xB7, "OEM_1": 0xBA, "OEM_PLUS": 0xBB, "OEM_COMMA": 0xBC,
 "OEM_MINUS": 0xBD, "OEM_PERIOD": 0xBE, "OEM_2": 0xBF, "OEM_3": 0xC0, "ABNT_C1": 0xC1, "ABNT_C2": 0xC2, "OEM_4": 0xDB,
 "OEM_5": 0xDC, "OEM_6": 0xDD, "OEM_7": 0xDE, "OEM_8": 0xDF, "OEM_AX": 0xE1, "OEM_102": 0xE2, "ICO_HELP": 0xE3, "PROCESSKEY": 0xE5,
 "ICO_CLEAR": 0xE6, "PACKET": 0xE7, "OEM_RESET": 0xE9, "OEM_JUMP": 0xEA, "OEM_PA1": 0xEB, "OEM_PA2": 0xEC, "OEM_PA3": 0xED,
 "OEM_WSCTRL": 0xEE, "OEM_CUSEL": 0xEF, "OEM_ATTN": 0xF0, "OEM_FINISH": 0xF1, "OEM_COPY": 0xF2, "OEM_AUTO": 0xF3, "OEM_ENLW": 0xF4,
 "OEM_BACKTAB": 0xF5, "ATTN": 0xF6, "CRSEL": 0xF7, "EXSEL": 0xF8, " EREOF": 0xF9, "PLAY": 0xFA, "ZOOM": 0xFB, "PA1": 0xFD,
 " OEM_CLEAR": 0xFE}

# Карта нумпада и списки кнопок/клавиш.
simple_key_map = { 'KEY_KP7': ' 7\nHome', 'KEY_KP8': '8\n↑', 'KEY_KP9': '9\nPgUp',
 'KEY_KP4': '4\n←', 'KEY_KP5': '5\n', 'KEY_KP6': '6\n→', 'KEY_KP1': '1\nEnd', 'KEY_KP2': '2\n↓', 'KEY_KP3': '3\nPgDn'}
LIST_MOUSE_BUTTONS = ["Левая кнопка", "Правая кнопка", "Средняя", "Колесико вверх", "Колесико вниз", "1 боковая", "2 боковая"]
LIST_KEYS = list(KEYS.keys())
defaut_list_mouse_buttons = ['LBUTTON', 'RBUTTON', 'WHEEL_MOUSE_BUTTON', 'SCROLL_UP', 'SCROLL_DOWN', 'XBUTTON1', 'XBUTTON2']

# Карты для редактора Xte-скриптов (keypad / mouse).
keypad_map = {"7\nHome": "KP_Home", "8\n↑": "KP_Up",
 "9\nPgUp": "KP_Prior", "4\n←": "KP_Left", "5\n": "KP_Begin", "6\n→": "KP_Right", "1\nEnd": "KP_End",
 "2\n↓": "KP_Down", "3\nPgDn": "KP_Next", "Ctrl": "ISO_Next_Group",
 "KEY_KPPLUS": "KP_Add", "KEY_KPMINUS": "KP_Subtract"}
mouse_map = {  "Левая": ("mousedown 1", "mouseup 1"), "Правая": ("mousedown 3", "mouseup 3"),  "wheel_up": ("mousedown 4", "mouseup 4"),
 "mouse_middie": ("mousedown 2", "mouseup 2"), "wheel_down": ("mousedown 5", "mouseup 5")}

# ==== ЧИСТЫЕ ФУНКЦИИ ====

# Простые проверки путей из настроек.
def _path_key(path):
 # Ключ сравнения путей: без различий регистра и типа слэшей.
 # Linux-ФС регистрозависима, но профиль мог быть сохранён как
 # "games/Entropy Zero 2/hl2.exe", а процесс реально запущен из
 # "games/entropy zero 2/hl2.exe". Раньше сравнение было подстрокой с
 # учётом регистра → профиль не находился, игра «не переключалась».
 text = str(path or '').strip().replace('\\', '/')
 if not text:
  return ''
 return os.path.normpath(text).lower()

def is_path_in_list(path, path_list):  # проверяет, содержится ли путь в списке путей.
 key = _path_key(path)
 if not key:
  return False
 return any(_path_key(item) == key for item in path_list)
def get_index_of_path(path, path_list):
 key = _path_key(path)
 for index, item in enumerate(path_list):
  if _path_key(item) == key:
   return index
 raise ValueError('path not found in list: %r' % (path,))

# Очистка и нормализация настроек (JSON читается через json.load(strict=False)).
def cleanup_empty_script_entries(data):
 """Удалить пустые записи и конфликтующие скрипты из настроек."""
 # ЗАМЕТКА (исправление): раньше здесь безусловно удалялись скрипты боковых
 # кнопок XBUTTON1/XBUTTON2, если в key_value[профиль][5]/[6] было непустое
 # значение. Но слоты 5 и 6 по умолчанию заполнены SCROLL_UP/SCROLL_DOWN, то
 # есть «непустые» почти всегда — из-за этого сохранённый через редактор
 # скрипт боковой кнопки стирался сразу же при сохранении и никогда не
 # работал. Очистка конфликта ключ/скрипт выполняется точечно в update_button
 # (когда пользователь выбирает клавишу для боковой кнопки), поэтому здесь
 # блок не нужен и удалён.

 for section in ("script_mouse", "keyboard_script"):
  container = data.get(section)
  if not isinstance(container, dict):
   continue
  for profile in list(container):
   profile_data = container.get(profile)
   if not isinstance(profile_data, dict):
    container.pop(profile, None)
    continue
   if section == "script_mouse":
    for button in list(profile_data):
     value = profile_data.get(button)
     if not isinstance(value, str) or not value.strip() or value.strip() == "#!/bin/bash":
      profile_data.pop(button, None)
   else:
    keys = profile_data.get("keys")
    if isinstance(keys, dict):
     for key in list(keys):
      value = keys.get(key)
      if not isinstance(value, str) or not value.strip() or value.strip() == "#!/bin/bash":
       keys.pop(key, None)
     if not keys:
      profile_data.pop("keys", None)
    if not profile_data:
     container.pop(profile, None)
   if section == "script_mouse" and not profile_data:
    container.pop(profile, None)
  if not container:
   data.pop(section, None)
 return data
def _format_scripts_in_json(text):
# Преобразуем экранированные переводы строк (\n) внутри bash-скриптов
# (ключи script_mouse / keyboard_script) в НАСТОЯЩИЕ переносы строк,
# чтобы в обычном текстовом редакторе скрипт выглядел как есть — построчно.
# Продолжения выравниваются вертикально по первой строке скрипта (#!/bin/bash).
# Экранированные кавычки \" и слэши \\ оставляем как есть (они корректны для json).
# Такой JSON читается через json.load(..., strict=False).
 json_str_re = re.compile(r'"(?:[^"\\]|\\.)*"')

 def repl(m):
  s = m.group(0)
  if "\\n" not in s:  # содержит ли строка экранированный перевод строки (это bash-скрипт)?
   return s
   # Выравниваем продолжения по первой строке скрипта: отступ = колонке начала
   # содержимого (сразу после открывающей кавычки значения) внутри СТРОКИ.
  line_start = text.rfind("\n", 0, m.start()) + 1
  col = (m.start() - line_start) + 1
  cont = " " * col
  inner = s[1:-1]  # тело без крайних кавычек
  # Заменяем ТОЛЬКО \n, не предварённый другим слэшем (lookbehind), чтобы
  # экранированный \\ (двойной слэш в JSON) не давал «висячий» слэш
  # (JSONDecodeError: Invalid \escape). Обычный перевод строки \n всегда
  # предварён не-слэшем (или началом строки), поэтому заменяется корректно.
  inner = re.sub(r'(?<!\\)\\n', "\n" + cont, inner)
  suffix = "\n" + cont  # убираем хвостовой перенос (от завершающего \n скрипта), чтобы " не уезжала
  if inner.endswith(suffix):
   inner = inner[:-len(suffix)]
  return '"' + inner + '"'

 return json_str_re.sub(repl, text)
def scripts_to_text(data):
# Нормализация после чтения: убираем отступы продолжения строк, которые могли
# попасть внутрь скрипта (от старых версий файла), чтобы строка была «чистой»
# и повторная запись не накапливала лишние отступы.
 for section in ("script_mouse", "keyboard_script"):
  container = data.get(section)
  if not isinstance(container, dict):
   continue
  for app, sub in container.items():
   if section == "keyboard_script":
    keys = sub.get("keys", {}) if isinstance(sub, dict) else {}
    for k, v in list(keys.items()):
     if isinstance(v, str) and "\n" in v:
      lines = v.split("\n")
      keys[k] = "\n".join([lines[0]] + [ln.lstrip() for ln in lines[1:]])
   else:
    if isinstance(sub, dict):
     for k, v in list(sub.items()):
      if isinstance(v, str) and "\n" in v:
       lines = v.split("\n")
       sub[k] = "\n".join([lines[0]] + [ln.lstrip() for ln in lines[1:]])
 return data

# Служебные функции для работы со словарём настроек.
def replace_path_in_dict(d):
# Определяем новый префикс
 new_prefix = next(('/'.join(value.split('/')[:4]) + '/' for value in d.values() if value.startswith('/mnt/')), None)
 if new_prefix is None:
  raise ValueError("Не удалось определить новый префикс.")

 updated_dict = {}
 for key, value in d.items():
  if value.startswith('/mnt/'):  # Если путь уже начинается с /mnt/, оставляем как есть
   updated_value = value
  else:  # Заменяем X:/ на new_prefix
   updated_value = re.sub(r'^[A-Z]:/', new_prefix, value, count=1)
   # Убираем дублирование /games/games/ или других частей
   parts = updated_value.split('/')  # Удаляем повторяющиеся сегменты после new_prefix
   unique_parts = []
   for part in parts:
    if not unique_parts or part != unique_parts[-1]:
     unique_parts.append(part)
   updated_value = '/'.join(unique_parts)
   # Добавляем .exe, если его нет
  if isinstance(updated_value, str) and not updated_value.lower().endswith('.exe'):
   updated_value += '.exe'
  updated_dict[key] = updated_value  # Путей обновить значение путей.
 return updated_dict
def remove_profile_keys(d, profile):  # Создаем глубокую копию словаря
 d_copy = copy.deepcopy(d)
 keys_to_delete = []
 for key, value in d_copy.items():
  if str(key) == str(profile):
   keys_to_delete.append(key)
  elif isinstance(value, dict):
  # Рекурсивно вызываем для вложенного словаря и обновляем значение
   d_copy[key] = remove_profile_keys(value, profile)
  elif isinstance(value, list):
  # Если значение — список, обрабатываем каждый элемент
   new_list = []
   for item in value:
    if isinstance(item, dict):
     new_list.append(remove_profile_keys(item, profile))
    else:
     new_list.append(item)
   d_copy[key] = new_list

   # Удаляем собранные ключи
 for key in keys_to_delete:
  del d_copy[key]
 return d_copy
def reorder_keys_in_dict(res, idx1, idx2):  # ИЗМЕНЕНО: Новая/доработанная функция (self для метода, если нужно; или статичная)
# ИЗМЕНЕНО: Проверки на валидность
 if 'paths' not in res or not isinstance(res['paths'], dict):
  return res
 orig_keys = list(res['paths'].keys())
 n = len(orig_keys)
 if not (0 <= idx1 < n and 0 <= idx2 < n and idx1 != idx2):
  return res

  # ИЗМЕНЕНО: Простой swap по idx1 и idx2 (без direction)
 new_order = orig_keys.copy()
 new_order[idx1], new_order[idx2] = new_order[idx2], new_order[idx1]

 def reorder_recursive(d):
  if not isinstance(d, dict):
   return d
   # Рекурсивно обработаем значения сначала
  processed = {k: reorder_recursive(v) for k, v in d.items()}
  # Если нет ключей из orig_keys — возвращаем как есть
  if not any(k in processed for k in orig_keys):
   return processed
   # Иначе: новый dict с ключами в new_order (только те, что есть)
  new_d = {}
  for k in new_order:
   if k in processed:
    new_d[k] = processed[k]
    # Добавляем оставшиеся ключи (не из paths, если есть)
  for k in processed:
   if k not in new_d:
    new_d[k] = processed[k]
  return new_d

 # ИЗМЕНЕНО: Собираем новый res (рекурсивно по всем top-level dicts)
 new_res = {}
 for top_k, top_v in res.items():
  if isinstance(top_v, dict):
   new_res[top_k] = reorder_recursive(top_v)
  else:
   new_res[top_k] = top_v
 return new_res

def profile_order_changed(old_data, new_data):
 # Проверка: изменился ли ПОРЯДОК ключей профилей (списка игр).
 # DeepDiff порядок ключей словаря изменением НЕ считает (dict сравнивается
 # как множество пар ключ-значение), поэтому перестановка профилей
 # кнопками «Вверх/Вниз» без этой проверки не попадала в диалог сохранения.
 if not isinstance(old_data, dict) or not isinstance(new_data, dict):
  return False
 old_paths = old_data.get('paths')
 new_paths = new_data.get('paths')
 if not isinstance(old_paths, dict) or not isinstance(new_paths, dict):
  return False
 return list(old_paths.keys()) != list(new_paths.keys())

def insert_profile_after(res, new_key, anchor_key):
 # Вставить новый профиль new_key в списке СРАЗУ ПОД активным anchor_key
 # (по требованию пользователя: новый добавленный путь к игре должен стоять
 # ниже того профиля, который был активным в момент добавления).
 # Переставляет ключи во ВСЕХ секциях (paths, games_checkmark, key_value,
 # mouse_press, script_mouse, keyboard_script) — как reorder_keys_in_dict.
 # Если anchor_key отсутствует в paths — новый профиль остаётся в конце.
 if not isinstance(res, dict) or not isinstance(res.get('paths'), dict):
  return res
 paths = res['paths']
 if new_key not in paths or anchor_key not in paths or new_key == anchor_key:
  return res
 orig_keys = list(paths.keys())
 anchor_idx = orig_keys.index(anchor_key)
 new_idx = orig_keys.index(new_key)
 if new_idx < anchor_idx:  # новый уже выше якоря — двигать нечего
  return res
 # порядок: все до якоря + якорь + новый + остальные (в прежнем порядке)
 new_order = [k for k in orig_keys[:anchor_idx + 1] if k != new_key]
 new_order.append(new_key)
 new_order.extend([k for k in orig_keys[anchor_idx + 1:] if k != new_key])

 def reorder_recursive(d):
  if not isinstance(d, dict):
   return d
  processed = {k: reorder_recursive(v) for k, v in d.items()}
  if not any(k in processed for k in orig_keys):
   return processed
  new_d = {}
  for k in new_order:
   if k in processed:
    new_d[k] = processed[k]
  for k in processed:
   if k not in new_d:
    new_d[k] = processed[k]
  return new_d

 new_res = {}
 for top_k, top_v in res.items():
  if isinstance(top_v, dict):
   new_res[top_k] = reorder_recursive(top_v)
  else:
   new_res[top_k] = top_v
 return new_res

# ==== Дополнительные exe профилей (ключа additional_exe) ====
def scan_profile_dir_exes(profile_path):
 # Полные пути всех .exe в верхней папке пути профиля (без подпапок).
 # Профиль сам себя содержит тоже (это .exe своей директории). Для недоступных
 # папок (напр. дефолтный C:/Windows/... который на Linux не смонтирован)
 # возвращаем просто сам путь профиля — «просто тот же путь».
 if not isinstance(profile_path, str) or not profile_path:
  return [profile_path]
 d = os.path.dirname(profile_path)
 if not d:
  return [profile_path]
 try:
  exes = sorted(f for f in os.listdir(d)
   if f.lower().endswith('.exe') and os.path.isfile(os.path.join(d, f)))
 except OSError:
  return [profile_path]
 full = [os.path.join(d, f) for f in exes]
 return full if full else [profile_path]

def ensure_additional_exe(res):
 # Гарантировать, что ключ additional_exe отражает ВСЕ пути из paths: для
 # каждого профиля — список полных путей .exe его директории (заполняется
 # только для отсутствующих ключей; сканирование при добавлении новой игры).
 if not isinstance(res, dict) or not isinstance(res.get('paths'), dict):
  return res
 additional = res.setdefault('additional_exe', {})
 for profile in res['paths']:
  if profile not in additional:
   additional[profile] = scan_profile_dir_exes(profile)
 return res

# evdev-имя клавиши -> нормализованная метка макроса (защищены нумпад +/-).
def evdev_key_to_label(code):
# Преобразует evdev-имя клавиши (напр. 'KEY_EQUAL') в нормализованную метку,
# под которой макросы лежат в keyboard_script.
# Нумпад +/- НАМЕРЕННО оставляем с префиксом 'KEY_', чтобы они НЕ совпадали
# с основными +/- (требование пользователя: различать нумпад и основную клавиатуру).
 if not isinstance(code, str) or not code.startswith("KEY_"):
  return None
 name = code[4:]
 # Нумпад: цифры/навигация -> метки как в simple_key_map (совместимо со старым поведением),
 # но +/- выделяем отдельно.
 if name.startswith("KP"):
  if name in ("KPPLUS", "KPMINUS"):
   return code  # 'KEY_KPPLUS' / 'KEY_KPMINUS' — не совпадают с '+' / '-'
  return simple_key_map.get(code, name)  # напр. 'KEY_KP7' -> ' 7\nHome'
 special = {
  "SPACE": "space", "ENTER": "enter", "KPENTER": "enter", "TAB": "tab",
  "ESC": "esc", "GRAVE": "`", "MINUS": "-", "EQUAL": "+",
  "LEFTBRACE": "[", "RIGHTBRACE": "]", "BACKSLASH": "\\",
  "SEMICOLON": ";", "APOSTROPHE": "'", "COMMA": ",", "DOT": ".",
  "SLASH": "/", "KPASTERISK": "*", "BACKSPACE": "backspace",
  "DELETE": "delete", "HOME": "home", "END": "end",
  "PAGEUP": "page_up", "PAGEDOWN": "page_down", "INSERT": "insert",
  "LEFT": "left", "RIGHT": "right", "UP": "up", "DOWN": "down",
  "LEFTSHIFT": "shift_l", "RIGHTSHIFT": "shift_r",
  "LEFTCTRL": "control_l", "RIGHTCTRL": "control_r",
  "LEFTALT": "alt_l", "RIGHTALT": "alt_r",
  "LEFTMETA": "meta_l", "RIGHTMETA": "meta_r",
  "CAPSLOCK": "caps_lock", "NUMLOCK": "num_lock",
  "SCROLLLOCK": "scroll_lock", "PRINT": "print", "PAUSE": "pause",
  }
 if name in special:
  return special[name]
 if len(name) == 1 and name.isalpha():
  return name.lower()
 if len(name) == 1 and name.isdigit():
  return name
 if name.startswith("F") and name[1:].isdigit():
  return name.lower()
 return name.lower()

# === Pyqt6_libs_mouse.py (движок мыши/клавиатуры) ===

# Подключение модуля данных и чистых функций (3-й скрипт Pyqt6_libs_data.py).
get_user_name = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''
user = subprocess.run(['bash'], input=get_user_name, stdout=subprocess.PIPE, text=True).stdout.strip()  # имя пользователя.
list_threads = []
mouse_controller = mouse.Controller()
# X11-номер кнопки по pynput-объекту: для UInput-эмуляции удержания
# (см. SmartTyper.button_press/button_release, 2026-11-04).
_X11_BY_PYNPUT_BUTTON = {mouse.Button.left: 1, mouse.Button.middle: 2, mouse.Button.right: 3}
# Допустимые длительности повтора (секунды) для галочки «Повторить».
allowed_repeat_durations = (5, 10, 20, 30)

# ==== Защита от запуска второго экземпляра (single-instance) ====
SINGLE_INSTANCE_LOCK = "/tmp/mouse_setting_control.lock"

def acquire_single_instance_lock():
 """Пытаемся занять lock-файл. Если другой живой процесс уже держит его —
 вернуть False (второй экземпляр запускать нельзя)."""
 try:
  with open(SINGLE_INSTANCE_LOCK) as f:
   pid = int(f.read().strip() or "0")
 except Exception:
  pid = 0
 if pid and os.path.exists("/proc/%d" % pid):
  return False  # первый экземпляр ещё работает
 # устаревший lock (процесс умер) или нет вообще — занимаем его
 try:
  with open(SINGLE_INSTANCE_LOCK, "w") as f:
   f.write(str(os.getpid()))
  return True
 except Exception:
  # без прав писать в /tmp не бывает; на всякий случай разрешаем запуск
  return True

def release_single_instance_lock():
 """Снимаем lock-файл при нормальном выходе."""
 try:
  with open(SINGLE_INSTANCE_LOCK) as f:
   pid = int(f.read().strip() or "0")
  if pid == os.getpid():
   os.remove(SINGLE_INSTANCE_LOCK)
 except Exception:
  pass

class save_dict:
 def __init__(self):
  self.jnson = {}  # новые настройки.
  self.old_data = {}  # старые настройки.
  self.name_games = []  # названия игр
  self.labels = []  # надписи.
  self.var_list = []  # галочки
  self.labels_with_checkmark = {}  # словарь надписи с галочками
  self.box_values = []  # Значения боковых кнопок
  self.cur_app = ""  # Текущая игра.
  self.count = 0  # Индекс текущей игры.
  self.id = 0  # id устройство.
  self.mouse_button_press = []  # какие кнопки должны быть удержаны.
  self.dict_id_values = {}
  self.dict_id_names = {}  # id -> имя устройства xinput (стабильный признак мыши между сессиями).
  self.data = "settings.json"  # единый файл всех настроек.
  self.path_current_app = ''  # Текущий путь к игре.
  self.process_id_active = 0  # id активного окна
  self.pid_and_path_window = {}  # Словарь игр и путей к ним.
  self.current_path_game = ""  # Путь к запущенной к игре.
  self.last_key_keyboard_script = ""
  self.thr = 0
  self.thread_exit=False  # это флаг выхода из потоков
  self.prev_game = ""  # Добавляем отсутствующий атрибут
  # Профиль, который пользователь выбрал ВРУЧНУЮ (синяя строка в списке).
  # Авто-переключение по активному окну игры его НЕ перезаписывает: именно к
  # нему нужно возвращаться, когда игра свернута/закрыта (запрос 2026-11-16).
  self.user_profile = ""

 def get_user_profile(self):
  return self.user_profile

 def set_user_profile(self, profile):
  self.user_profile = str(profile or '')

 def get_last_key_keyboard_script(self): #
  return self.last_key_keyboard_script

 def set_last_key_keyboard_script(self, last_key_keyboard_script1):
  self.last_key_keyboard_script = last_key_keyboard_script1

 def get_thread(self):  #
  return self.thr

 def set_thread(self, thr1):
  self.thr = thr1

 def get_current_path_game(self):  # Сохранить текущий путь к игре
  return self.current_path_game

 def set_current_path_game(self, current_path_game):
  self.current_path_game = current_path_game

 def get_prev_game(self):  # Сохранить текущий путь к игре
  return self.prev_game

 def set_prev_game(self, prev_game):
  self.prev_game = prev_game

 def get_pid_and_path_window(self):  #
  return self.pid_and_path_window

 def set_pid_and_path_window(self, pid_and_path_window):  #
  self.pid_and_path_window = pid_and_path_window

 def get_process_id_active(self):
  return self.process_id_active

 def set_process_id_active(self, process_id_active):  #
  self.process_id_active = process_id_active

 def get_current_app_path(self):  # Получить путь текущего окна.
  return self.path_current_app

 def set_current_app_path(self, app):  # Установить путь текущего окна.
  self.path_current_app = app

 def return_name_games(self):  # Вернуть список названия игр.
  return self.name_games

 def return_mouse_button_press(self):
  return self.mouse_button_press

 def save_labels(self, labels):
  self.labels = labels

 def return_labels(self):
  return self.labels

 def save_var_list(self, var_list):
  self.var_list = var_list

 def return_var_list(self):
  return self.var_list

 def return_labels_with_checkmark(self):
  return self.labels_with_checkmark

 def return_box_values(self):
  return self.box_values

 def return_list_mouse_button_press(self):  # какие кнопки должны быть удержаны для текущий игры.
  return list(self.jnson["mouse_press"][self.cur_app])

 def save_mouse_button_press(self, list_mouse_button_press=None, mouse_button_press=None):
  if mouse_button_press is None:
   mouse_button_press = self.mouse_button_press
  self.mouse_button_press = mouse_button_press
  if list_mouse_button_press is None:
   list_mouse_button_press = []  # Сохранить список какие кнопки должны быть удержаны.
   for i in range(len(mouse_button_press)):
    list_mouse_button_press.append(mouse_button_press[i].isChecked())

  self.jnson["mouse_press"][self.cur_app] = list(list_mouse_button_press)

 def save_jnson(self, jn):  # сохранить новые настройки (только в память;
 # запись в файл — при закрытии, через closeEvent, если есть изменения)
  self.jnson = jn

 def save_old_data(self, jnson):  # сохранить начальные настройки.
  self.old_data = copy.deepcopy(jnson)
  self.jnson = jnson

 def return_jnson(self):  # Вернуть новые настройки.
  return self.jnson

 def return_old_data(self):
  return self.old_data

 def set_cur_app(self, cur_app):  # установить текущего игру
  self.cur_app = str(cur_app)
  self.jnson["current_app"] = self.cur_app
  # «Синяя» строка и профиль возврата всегда совпадают с current_app.
  # Авто-переключение по окну игры current_app больше не трогает, поэтому
  # здесь остаётся именно выбор пользователя (2026-11-16).
  self.user_profile = self.cur_app

 def get_cur_app(self):
  return str(self.jnson["current_app"])

 def set_count(self, count):
  self.count = count
  return self.count

 def get_count(self):
  return self.count

 def set_values_box(self):
  box_value = self.jnson["key_value"][self.cur_app]
  for i in range(len(self.box_values)):
   self.box_values[i].setCurrentText(box_value[i])

 def set_box_values(self):  # Установить значение для выпадающего списка.
  self.reset_id_value()
  res = self.jnson
  key_values = res["key_value"]
  d = list(res["paths"].keys())  # получить словарь путей и имен файлов.
  self.set_cur_app(d[self.count])  # установить текущую активную строку.
  self.jnson["current_app"] = d[self.count]  # Сохранить текущую активную строку.
  self.set_values_box()
  return self

 def write_to_file(self, new_data): # Перед записью удаляем пустые записи скриптов, но не трогаем
 # обязательные разделы профилей и пустые значения комбинаций.
  new_data = cleanup_empty_script_entries(copy.deepcopy(new_data))
  # Сериализуем JSON с отступами и прогоняем через _format_scripts_in_json:
  # экранированные \n внутри bash-скриптов (script_mouse / keyboard_script)
  # превращаются в НАСТОЯЩИЕ переводы строк, чтобы в текстовом редакторе
  # скрипт выглядел как есть — построчно (см. REPORT_DOCUMENTATION.md §1.1).
  # Приложение читает файл через json.load(..., strict=False) + scripts_to_text,
  # поэтому такой формат корректен и повторно не портит файл (идемпотентно).
  # Единый JSON: сохраняем данные мыши в раздел mouse_data, не затирая
  # остальные настройки программы.
  root = {}
  if os.path.exists(self.data):
   try:
    with open(self.data, encoding="UTF-8") as r:
     root = json.load(r, strict=False)
   except Exception:
    root = {}
  root["mouse_data"] = new_data
  json_string = json.dumps(root, ensure_ascii=False, indent=2)
  with open(self.data, "w", encoding="UTF-8") as w:
   w.write(json_string)  # сохранить изменения в файле настроек.
  file_relus = '''#!/bin/bash\n
                       chmod a+rw \"{0}\" '''.format(self.data)
  subprocess.call(['bash', '-c', file_relus])  # Дать доступ на чтение и запись любому
  return self

 def get_list_ids(self):  # Получение списка id устройств.
  # Собираем ТОЛЬКО устройства, которые выглядят как МЫШЬ с боковыми кнопками,
  # чтобы повысить точность автоматического определения id игровой мыши.
  # Фильтры (все вместе):
  #  1) ТИП: берём только физические указатели  [slave  pointer ...], исключая
  #     синтетические master/XTEST-устройства и клавиатуры.
  #  2) ИМЯ: отбрасываем виртуальные/системные (XTEST, Virtual core, Power Button,
  #     Video Bus, Smart-Virtual-* и т.п.), которые не являются реальными мышами.
  #  3) КНОПКИ: оставляем устройства с >= 9 кнопками в карте. Боковые кнопки -
  #     это физические 8 и 9, значит у мыши с боковыми кнопками в карте обязано
  #     быть >= 9 позиций. Это отсекает простые 3-7-кнопочные мыши, тачпады и
  #     клавиатуры, случайно зарегистрированные как указатели.
  min_buttons = 9
  excluded_name_markers = (
   'XTEST', 'virtual', 'power button', 'video bus', 'smart-virtual',
   'wacom', 'synaptics', 'realtouch', 'dell wmi', 'apple',
   )
  # Собираем строки «xinput list» и в Python парсим только физические указатели
  # (тип [slave  pointer ...]) — иконки (↳, ➜) юникодные и в sed непостоянны,
  # поэтому разбор названия делаем здесь, а не в bash.
  raw = subprocess.check_output(['bash', '-c', 'xinput list 2>/dev/null']).decode().splitlines()
  button_map = {}  # Словарь id -> актуальная карта кнопок.
  id_names = {}  # id -> имя устройства: xinput-id перенумеруются между сессиями X,
  # имя же у мыши стабильно — по нему обеспечиваем выбор устройства (id_name в JSON).
  for line in raw:
   # Ищем тип устройства: учитывается только «slave  pointer».
   m_type = re.search(r'\[\s*slave\s+pointer\b', line)
   if not m_type:
    continue
   # id из последнего куска «id=N».
   m_id = re.search(r'id=(\d+)', line)
   if not m_id:
    continue
   dev_id = int(m_id.group(1))
   # Имя устройства — всё от начала строки до «id=». Вырезаем юникод-иконки.
   name_raw = line[:m_id.start()]
   words = [p for p in name_raw.split() if any(c.isalnum() for c in p)]
   dev_name = ' '.join(words)
   # Фильтр ИМЯ: пропускаем виртуальные/системные устройства.
   name_low = dev_name.casefold()
   if any(marker in name_low for marker in excluded_name_markers):
    continue
   # Карту кнопок узнаём через xinput get-button-map (как и раньше).
   output = subprocess.check_output(['bash', '-c', 'xinput get-button-map %d 2>&1' % dev_id]).decode()
   if 'device has no buttons' in output or 'X Error of failed request:' in output:
    continue
   buttons = output.strip().split()
   # ЗАМЕТКА (исправление 2026-11-03): если прошлый запуск программы не
   # восстановил карту (crash/kill), здесь кэшировался СЛЕД нашего remap'а
   # (виртуальные кнопки 11-16) как «заводская» карта, и «восстановление
   # по умолчанию» при выходе возвращало его снова. Чистим карту от
   # виртуальных кнопок до кэширования (см. sanitize_button_map).
   buttons = self.sanitize_button_map(buttons)
   # Фильтр КНОПКИ: устройство без боковых кнопок (меньше 9 кнопок в карте)
   # в список не попадает — так повышаем шанс, что вернётся id именно мыши.
   if len(buttons) < min_buttons:
    continue
   button_map[dev_id] = ' '.join(buttons)
   id_names[dev_id] = dev_name
  self.dict_id_values = button_map  # Сохранение карты кнопок в атрибут объекта.
  self.dict_id_names = id_names  # Сохранение имён устройств (для стабильного выбора по имени).
  id_list = sorted(button_map.keys())  # Сохранение списка идентификаторов в переменной id_list.
  return id_list  # Возвращение списка id устройств для дальнейшего использования.

 def get_state_thread(self):
  return self.thread

 def set_default_id_value(self):  # Вернуть значения по умолчанию
  self.thread = True  # Прервать выполнение потока обработчика нажатий.
  for id in self.dict_id_values:
   st = str(self.dict_id_values[id])
   set_button_map = '''#!/bin/bash
             xinput set-button-map {0} {1}
             '''.format(id, st)
   subprocess.call(['bash', '-c', set_button_map])
  # ЗАМЕТКА (исправление 2026-11-03): раньше восстанавливались только карты
  # из кэша dict_id_values. Кэш заполняет get_list_ids, который берёт только
  # устройства с >= 9 кнопками — 7-кнопочная мышь (родная карта 1..7) в кэш
  # не попадала, и при выходе программы наш remap оставался жить в X:
  # правая кнопка была «мёртвой» до следующего запуска или перезагрузки X.
  # Теперь текущее устройство (id из настроек) ГАРАНТИРОВАННО сбрасывается
  # в identity, даже если его карты нет в кэше.
  try:
   current_id = int(self.return_jnson().get('id', 0))
  except (TypeError, ValueError):
   current_id = 0
  if current_id > 0 and current_id not in self.dict_id_values:
   set_button_map = '''#!/bin/bash
             xinput set-button-map {0} 1 2 3 4 5 6 7 8 9
             '''.format(current_id)
   process = subprocess.Popen(['bash', '-c', set_button_map], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   process.communicate()
   if process.returncode != 0:
    try:
     self.write_in_log('set_default_id_value: reset failed for id %s' % current_id)
    except Exception:
     pass

 def sanitize_button_map(self, buttons):
  # ЗАМЕТКА (исправление 2026-11-03): чистит карту кнопок от следа нашего
  # remap'а. INTERCEPTION_RULES remапит физические кнопки в ВИРТУАЛЬНЫЕ
  # 11-16 (Button.button11 … Button.button16). Если прошлый запуск завершился
  # аварийно (crash/kill — closeEvent не отработал), такой remap оставался
  # жить в X, попадал в кэш/в «заводскую» карту и возвращался «восстановлением
  # по умолчанию» — физическая правая кнопка (3) навсегда отображалась в
  # логическую 11 и «умирала» во всех приложениях. Карта, содержащая 11-16,
  # заводской не является: возвращаем identity 1..N (длина сохраняется —
  # устройство заведомо принимает N позиций). Для заводских identity-карт
  # (1..N) замена — no-op.
  virtual = {'11', '12', '13', '14', '15', '16'}
  entries = [str(b) for b in buttons]
  if any(e in virtual for e in entries):
   return [str(i + 1) for i in range(len(entries))]
  return entries

 def reset_id_value(self, device_id=None):  # Сброс карты кнопок устройства в identity.
  # ЗАМЕТКА (исправление 2026-11-03): раньше сброс шёл в цикле по кэшу
  # dict_id_values, но в xinput подставлялся self.id — а это поле всегда 0
  # (никем не синхронизируется с настройками), поэтому «xinput set-button-map
  # 0 …» молча падал и СТАРЫЙ remap нечищенным оставался в X. Теперь
  # сбрасывается устройство, переданное вызывающим кодом (id из настроек);
  # без валидного id (> 0) сброс не выполняется вовсе.
  if device_id is None:
   device_id = self.id
  try:
   device_id = int(device_id)
  except (TypeError, ValueError):
   return
  if device_id <= 0:
   return
  d = '1 2 3 4 5 6 7 8 9'  # identity: физическая кнопка N -> логическая N
  set_button_map = '''#!/bin/bash
            xinput set-button-map {0} {1}
            '''.format(device_id, d)
  process = subprocess.Popen(['bash', '-c', set_button_map], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  process.communicate()
  if process.returncode != 0:
   try:
    self.write_in_log('reset_id_value: failed for id %s' % device_id)
   except Exception:
    pass

 def get_default_id_value(self, id):  #
  # ЗАМЕТКА (исправление 2026-11-03): раньше возвращалась кэшированная карта,
  # а при промахе — жёсткий фолбэк '1 2 3 4 5 6 7 8 9'. Кэш мог содержать
  # ПОРЧЕНУЮ карту (след remap'а после аварийного завершения — см.
  # sanitize_button_map), и «заводская» карта навсегда превращалась в remap.
  # Кроме того, 7-кнопочная мышь (родная карта 1..7) не проходит фильтр
  # get_list_ids (>= 9 кнопок) и в кэш не попадала вовсе. Теперь заводская
  # карта запрашивается у устройства напрямую, чистится от виртуальных
  # кнопок и кэшируется — restore при выходе всегда имеет верные данные.
  try:
   result = subprocess.run(['xinput', 'get-button-map', str(id)],
    capture_output=True, text=True, timeout=5)
   buttons = result.stdout.split() if result.returncode == 0 else []
  except Exception:
   buttons = []
  if buttons:
   clean = self.sanitize_button_map(buttons)
   self.dict_id_values[id] = ' '.join(clean)
   return self.dict_id_values[id]
  try:
   self.write_in_log('get_default_id_value: id %s not readable, using 1..9' % (id,))
  except Exception:
   pass
  return '1 2 3 4 5 6 7 8 9'

 def ensure_valid_mouse_id(self, preferred_id):  # Авто-поиск мыши: сохранённый xinput-id неустойлив между
 # X-сессиями (после перезапуска тот же номер может принадлежать клавиатуре
 # или исчезнуть). Тогда set-button-map молча падает («device has no
 # buttons»), перехват не применяется и назначенные клавиши «не срабатывают».
 # Возвращает (id, was_changed): если preferred_id ещё «мышь с кнопками» —
 # (он, False); иначе — автоматически подобранная мышь и True.
  try:
   preferred = int(preferred_id)
  except (TypeError, ValueError):
   preferred = None
  # get_list_ids() заново обходит устройства и обновляет кэш dict_id_values:
  # в карту попадают только указатели с >=9 кнопками (реальные мыши).
  # (Исправление 2026-11-09: ретраи сканирования) Сразу после запуска
  # X-сессии устройства ещё перечисляются: пустой valid раньше МОЛЧА
  # оставлял устаревший id (remap не применялся — боковые кнопки
  # оставались нативными X11 8/9 = «назад» в браузере, а не прокрутка).
  # Теперь сканируем несколько раз; деградационный путь виден в log.txt.
  valid = []
  for _attempt in range(4):
   try:
    valid = self.get_list_ids()
   except Exception:
    valid = []
   if valid:
    break
   time.sleep(0.5)
  if preferred is not None and preferred in valid:
   return preferred, False
  if not valid:
   try:
    self.write_in_log('ensure_valid_mouse_id: no usable mouse after 4 scans, keeping id %s (degraded mode: remap не применится)' % (preferred,))
   except Exception:
    pass
   return preferred, False  # Подходящей мыши нет — остаётся текущий id.
  # СТАБИЛЬНЫЙ ВЫБОР ПО ИМЕНИ (исправление «сбивания настроек мыши»):
  # xinput-id перенумеруются между сессиями X (6 -> 14 -> 6, см. log.txt),
  # и сохранённый id к следующему запуску оказывается «чужим». Раньше тут
  # сразу шёл legacy-выбор «самая полная карта», который при нескольких
  # мышах/устройствах мог выбрать ДРУГОЕ устройство и перетереть ручной
  # выбор пользователя. Теперь сначала ищем мышь по стабильному имени
  # (ключ id_name в JSON, заполняется ensure_mouse_id_name/startup), и
  # только при отсутствии имени — legacy (поведение прежних запусков).
  wanted = str(self.return_jnson().get('id_name', '') or '').strip()
  if wanted:
   for i in valid:
    if str(self.dict_id_names.get(i, '')).strip().lower() == wanted.lower():
     try:
      self.write_in_log('mouse device id %s stale after X-session renumbering, resolved by name %s -> id %s' % (preferred, wanted, i))
     except Exception:
      pass
     return i, True
  best = max(valid, key=lambda i: len(str(self.dict_id_values.get(i, '')).split()))
  try:
   self.write_in_log('mouse device id %s not usable (absent or has no buttons), reselected id %s' % (preferred, best))
  except Exception:
   pass
  return best, True

 def write_in_log(self, text=" error"):  # Запись ошибок.
  # Лог пишется в папку самой программы (не в текущий каталог запуска):
  # раньше при старте через .sh без cd файл терялся/уезжал в другое место.
  try:
   log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.txt")
   with open(log_path, "a") as f:
    f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(text) + "\n")
  except Exception:
   pass


def ensure_mouse_id_name(res):
 # Стабильный идентификатор мыши: имя устройства xinput (ключ JSON id_name),
 # по которому ensure_valid_mouse_id находит мышь после перенумерации
 # xinput-id в новой X-сессии. Вызывается в __init__ главного скрипта ДО
 # save_old_data (как ensure_additional_exe) — ключ добавляется в старый и
 # новый словари одновременно и НЕ попадает в DeepDiff closeEvent:
 # ложного диалога «Сохранить изменения?» нет.
 # Имя записывается ТОЛЬКО если сохранённый id сейчас валидная мышь
 # (указатель с >=9 кнопками); для устаревшего id (устройство исчезло или
 # стало безкнопочным) старое id_name НЕ трогаем — его всё равно
 # перезапишет ensure_valid_mouse_id/startup для реально подобранной мыши.
 if not isinstance(res, dict):
  return res
 res.setdefault('id_name', '')
 try:
  preferred = int(res.get('id', 0))
 except (TypeError, ValueError):
  preferred = 0
 if preferred <= 0:
  return res
 d = save_dict()
 try:
  d.get_list_ids()
 except Exception:
  return res  # X недоступен — не трогаем id_name, старт не роняем.
 name = str(d.dict_id_names.get(preferred, '')).strip()
 if name:
  res['id_name'] = name
 return res


class SmartTyper:
 """Virtual keyboard for mouse-to-key assignments.

  Keyboard actions selected in the profile UI are emitted through evdev.UInput,
  not through xdotool/xte.  The class owns a single virtual keyboard device and
  is safe to call from the listener's worker threads.  Existing bash macros are
  not modified: a macro remains an explicit user script and may still use xte.
  """

 _ACTION_TO_ECODE = {
  'BACKSPACE': 'KEY_BACKSPACE', 'TAB': 'KEY_TAB', 'RETURN': 'KEY_ENTER',
  'KP_ENTER': 'KEY_KPENTER', 'ESCAPE': 'KEY_ESC', 'SPACE': 'KEY_SPACE',
  'HOME': 'KEY_HOME', 'END': 'KEY_END', 'LEFT': 'KEY_LEFT', 'RIGHT': 'KEY_RIGHT',
  'UP': 'KEY_UP', 'DOWN': 'KEY_DOWN', 'INSERT': 'KEY_INSERT', 'DELETE': 'KEY_DELETE',
  'PRIOR': 'KEY_PAGEUP', 'NEXT': 'KEY_PAGEDOWN', 'PAGE_UP': 'KEY_PAGEUP',
  'PAGE_DOWN': 'KEY_PAGEDOWN', 'SNAPSHOT': 'KEY_SYSRQ', 'PAUSE': 'KEY_PAUSE',
  'CAPITAL': 'KEY_CAPSLOCK', 'CAPS_LOCK': 'KEY_CAPSLOCK', 'NUMLOCK': 'KEY_NUMLOCK',
  'NUM_LOCK': 'KEY_NUMLOCK', 'SCROLL': 'KEY_SCROLLLOCK', 'SCROLL_LOCK': 'KEY_SCROLLLOCK',
  'LWIN': 'KEY_LEFTMETA', 'RWIN': 'KEY_RIGHTMETA', 'SHIFT_L': 'KEY_LEFTSHIFT',
  'SHIFT_R': 'KEY_RIGHTSHIFT', 'LCONTROL': 'KEY_RIGHTALT',
  'RCONTROL': 'KEY_RIGHTCTRL', 'CONTROL': 'KEY_LEFTCTRL',
  'CONTROL_L': 'KEY_LEFTCTRL', 'CONTROL_R': 'KEY_RIGHTCTRL',
  'ALT_L': 'KEY_LEFTALT', 'ALT_R': 'KEY_RIGHTALT', 'LMENU': 'KEY_LEFTALT',
  'RMENU': 'KEY_RIGHTALT', 'MENU': 'KEY_COMPOSE', 'APPS': 'KEY_COMPOSE',
  'ISO_NEXT_GROUP': 'KEY_RIGHTALT', 'ADD': 'KEY_KPPLUS', 'SUBTRACT': 'KEY_KPMINUS',
  'MULTIPLY': 'KEY_KPASTERISK', 'DIVIDE': 'KEY_KPSLASH', 'DECIMAL': 'KEY_KPDOT',
  }

 def __init__(self):
  # Раздельные блокировки: клавиатура и «указатель» (колесо/кнопки мыши)
  # — независимые UInput-устройства, чтобы удержание клавиши (напр. ПКМ->W)
  # и одновременный клик боковой кнопки (напр. боковая->ПКМ) не блокировали
  # друг друга (исправление одновременной работы, 2026-11-15).
  self._kb_lock = threading.RLock()
  self._ptr_lock = threading.RLock()
  self._lock = self._kb_lock  # совместимость со старым именем
  # Счётчики активных нажатий (ref-count), а не просто факт "зажата": это
  # позволяет эмулировать несколько кнопок одновременно. Реальный key-up /
  # button-release отправляется только когда счётчик опускается до 0, поэтому
  # отпускание одной кнопки/слота не прерывает удержание той же клавиши или
  # той же кнопки мыши, инициированное другим слотом.
  self._pressed_codes = {}
  # Зажатые кнопки виртуального указателя (BTN_LEFT/MIDDLE/RIGHT) —
  # ref-count по коду кнопки, чтобы button_release отпускал физически только
  # когда все источники удержания отпущены (безопасен повторный/пустой вызов).
  self._pressed_mouse_buttons = {}
  self._ui = None
  self._ui_scroll = None
  self._physical_keyboard = None
  self._create_device()
  self._create_scroll_device()

 def _find_keyboard(self):
 # Надёжный выбор физической клавиатуры: пропускаем виртуальные
 # устройства и мыши, оставляем те, у которых есть буквы/Enter,
 # и выбираем самую «полную» (больше всего клавиш EV_KEY).
  try:
   devices = list_devices()
  except Exception:
   return None
  candidates = []
  for path in devices:
   try:
    dev = InputDevice(path)
   except Exception:
    continue
   name = (dev.name or "").lower()
   phys = (dev.phys or "").lower()
   if "virtual" in name or "uinput" in phys or "mouse" in name:
    continue
   try:
    caps = dev.capabilities().get(ecodes.EV_KEY, [])
   except Exception:
    continue
   if ecodes.KEY_A in caps or ecodes.KEY_ENTER in caps or ecodes.KEY_SPACE in caps:
    candidates.append(dev)
  if candidates:
   candidates.sort(key=lambda d: len(d.capabilities().get(ecodes.EV_KEY, [])), reverse=True)
   return candidates[0]
  return None

 def _create_device(self):
  try:
   self._physical_keyboard = self._find_keyboard()
  except Exception:
   self._physical_keyboard = None
  try:
   # (Исправление 2026-11-13, §39): EV_LED намеренно НЕ заявляем. X-сервер
   # при регистрации устройства с LED-capability пересинхронизирует
   # индикаторы всех клавиатур и может погасить NumLock-LED физической
   # клавиатуры (конфликт с write_text_fast/punto и другими скриптами,
   # работающими параллельно). Для эмуляции нажатий LED не нужны; NumLock
   # при необходимости выставляется мягко (без переключения, если уже on).
   self._ui = UInput(
    {ecodes.EV_KEY: list(range(1, 256))},
    name='Mouse Setting Control Virtual Keyboard',
    bustype=ecodes.BUS_USB,
    vendor=0x1209,
    product=0x0001,
    )
  except Exception as exc:  # Не останавливаем эмуляцию мыши, если /dev/uinput недоступен.
  # Внешние процессы (xdotool) больше НЕ используются — нажатия
  # просто не эмулируются до появления устройства.
   self._ui = None
   try:
    dict_save.write_in_log('UInput keyboard is unavailable: ' + str(exc))
   except Exception:
    pass
  self._ensure_numlock_on()

 def _create_scroll_device(self):
 # Отдельное ВИРТУАЛЬНОЕ УСТРОЙСТВО-УКАЗАТЕЛЬ для колеса. Клавиатурное
 # устройство (self._ui) в X11 регистрируется как клавиатура, и записанные
 # в него EV_REL/REL_WHEEL сервер игнорирует (событий колеса не возникает).
 # Устройство с capabilities EV_KEY+EV_REL (вкл. REL_WHEEL) Xorg объявляет
 # указателем и превращает REL_WHEEL в настоящий скролл (кнопки 4/5 +
 # XI2 scroll valuator). Имя содержит 'virtual'/'mouse', чтобы фильтр
 # _find_keyboard() не принимал его за физическую клавиатуру.
  try:
   self._ui_scroll = UInput(
    {ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE,
    ecodes.BTN_SIDE, ecodes.BTN_EXTRA],
    ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL, ecodes.REL_HWHEEL]},
    name='Mouse Setting Control Virtual Wheel',
    bustype=ecodes.BUS_USB,
    vendor=0x1209,
    product=0x0002,
    )
  except Exception as exc:
  # Не останавливаем эмуляцию мыши, если /dev/uinput недоступен.
  # Внешние процессы (xdotool) больше НЕ используются — скролл просто
  # не эмулируется до появления устройства.
   self._ui_scroll = None
   try:
    dict_save.write_in_log('UInput wheel device is unavailable: ' + str(exc))
   except Exception:
    pass

 def _read_led_mask(self):
  try:
   result = subprocess.run(["xset", "-q"], capture_output=True, text=True, timeout=2)
   m = re.search(r'LED\s+mask:\s{0,}([0-9a-fA-F]+)', result.stdout)
   if m:
    return int(m.group(1), 16)
  except Exception:
   pass
  return None

 def _is_numlock_on(self):
  mask = self._read_led_mask()
  if mask is not None:
   return bool(mask & 0x00000002)
  try:
   if self._physical_keyboard is not None:
    return bool(self._physical_keyboard.leds() & (1 << ecodes.LED_NUML))
  except Exception:
   pass
  return True

 def _ensure_numlock_on(self):
  # Мягкая, идемпотентная проверка NumLock (§39): не переключаем, если уже
  # включён, не пишем EV_LED в виртуальное устройство (capability убрана),
  # не трогаем LED физической клавиатуры напрямую. Это снижает конфликты с
  # write_text_fast.py / punto.py, которые управляют NumLock/раскладкой
  # параллельно. При необходимости делаем один toggle через виртуальную
  # клавиатуру (XKB сам пересинхронизирует индикаторы).
  try:
   if self._ui is None:
    return
   if self._is_numlock_on():
    return
   with self._kb_lock:
    self._ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
    self._ui.syn()
    time.sleep(0.05)
    self._ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 0)
    self._ui.syn()
  except Exception:
   pass

 def _force_numlock_on(self):
  # Совместимость: старое имя, теперь делегирует в мягкую версию.
  self._ensure_numlock_on()

 @staticmethod
 def _ecodes_value(name):
  value = getattr(ecodes, name, None)
  if isinstance(value, int):
   return value
  value = ecodes.ecodes.get(name)
  return value if isinstance(value, int) else None

 def _resolve(self, action):
  if not isinstance(action, str):
   return None
  action = action.strip()
  if not action or action == ' ':
   return None
  if action.isdigit():
   code = int(action)
   if 0 < code < 256:
    return code
   return None
  normalized = action.upper()
  if len(action) == 1 and action.isalpha():
   key_name = 'KEY_' + normalized
  elif len(action) == 1 and action.isdigit():
   key_name = 'KEY_' + action
  elif normalized.startswith('F') and normalized[1:].isdigit():
   key_name = 'KEY_' + normalized
  elif normalized.startswith('NUMPAD') and normalized[6:].isdigit():
   key_name = 'KEY_KP' + normalized[6:]
  else:
   key_name = self._ACTION_TO_ECODE.get(normalized)
  return self._ecodes_value(key_name) if key_name else None

 def key_down(self, action):
  """Send one key-down event for a mapped mouse action."""
  code = self._resolve(action)
  if code is None:
   return False
  # (Исправление 2026-11-13, §38): одиночные буквы A–Z при активной не-US
  # раскладке XKB. UInput шлёт ФИЗИЧЕСКИЙ keycode (EV_KEY/KEY_W) — X
  # отображает его в символ текущей группы (ru group1: W → «ц»), поэтому
  # «W» в профиле не давало латинскую w в приложениях. xdotool keydown
  # keysym-осознан и выдаёт именно запрошенную букву в любой раскладке
  # (проверено вживую: keydown w → 'w' при ru group1). Для игр/Wine это
  # тоже корректно (X-событие приходит). UInput остаётся для всего
  # остального (F-клавиши, стрелки, модификаторы, спецклавиши, цифры),
  # и как fallback, если xdotool недоступен.
  if isinstance(action, str) and len(action) == 1 and action.isalpha():
   char_key = ('char', action.lower())
   # Блокировку клавиатуры НЕ держим во время subprocess.run, иначе
   # долгое выполнение xdotool блокирует прочие клавиатурные действия и
   # (раньше, при общем _lock) мешало параллельным кликам мыши.
   try:
    with self._kb_lock:
     count = int(self._pressed_codes.get(char_key, 0))
     if count > 0:
      self._pressed_codes[char_key] = count + 1
      return True
     # Если буква уже удерживается через UInput-fallback (evdev code),
     # увеличиваем его счётчик, чтобы не потерять источник удержания.
     if code is not None and int(self._pressed_codes.get(code, 0)) > 0:
      self._pressed_codes[code] = int(self._pressed_codes.get(code, 0)) + 1
      return True
    r = subprocess.run(['xdotool', 'keydown', '--clearmodifiers', action.lower()],
     capture_output=True, timeout=2)
    if r.returncode == 0:
     with self._kb_lock:
      self._pressed_codes[char_key] = int(self._pressed_codes.get(char_key, 0)) + 1
     return True
   except Exception:
    pass
  if self._ui is None:
   self._create_device()
  if self._ui is None:
  # Внешний процесс недоступен и UInput не создан — не эмулируем.
   return False
  try:
   with self._kb_lock:
    count = int(self._pressed_codes.get(code, 0))
    if count <= 0:
     self._ui.write(ecodes.EV_KEY, code, 1)
     self._ui.syn()
    self._pressed_codes[code] = count + 1
   return True
  except Exception as exc:
   try:
    dict_save.write_in_log('UInput key-down failed: ' + str(exc))
   except Exception:
    pass
   return False

 def key_up(self, action):
  """Send one key-up event for a mapped mouse action."""
  code = self._resolve(action)
  if code is None:
   return False
  # Парная ветка к key_down (§38): буквы, зажатые через xdotool keydown,
  # отпускаем тем же путём. Если удержание шло через UInput-fallback (evdev),
  # отпускаем evdev-код, чтобы не оставлять клавишу «залипшей».
  if isinstance(action, str) and len(action) == 1 and action.isalpha():
   char_key = ('char', action.lower())
   with self._kb_lock:
    char_count = int(self._pressed_codes.get(char_key, 0))
    uinput_count = int(self._pressed_codes.get(code, 0))
   if char_count > 0:
    try:
     if char_count == 1:
      subprocess.run(['xdotool', 'keyup', '--clearmodifiers', action.lower()],
       capture_output=True, timeout=2)
    except Exception:
     pass
    with self._kb_lock:
     count = int(self._pressed_codes.get(char_key, 0)) - 1
     if count > 0:
      self._pressed_codes[char_key] = count
     else:
      self._pressed_codes.pop(char_key, None)
    return True
   # Удержание могло быть через UInput-fallback — отпустим его ниже по evdev-коду.
   if uinput_count <= 0:
    with self._kb_lock:
     self._pressed_codes.pop(char_key, None)
    # Нет активного удержания — ничего отпускать не нужно.
    return True
  if self._ui is None:
   self._create_device()
  if self._ui is None:
  # Внешний процесс недоступен и UInput не создан — не эмулируем.
   return False
  try:
   with self._kb_lock:
    count = int(self._pressed_codes.get(code, 0))
    if count > 1:
     self._pressed_codes[code] = count - 1
     return True
    if count <= 0:
     self._pressed_codes.pop(code, None)
     return True
    self._ui.write(ecodes.EV_KEY, code, 0)
    self._ui.syn()
    self._pressed_codes.pop(code, None)
   return True
  except Exception as exc:
   try:
    dict_save.write_in_log('UInput key-up failed: ' + str(exc))
   except Exception:
    pass
   return False

 def scroll(self, direction, amount=1):
  """Emit one or more wheel notches directly through the kernel (UInput).

    `direction`: +1 = scroll up (REL_WHEEL +1), -1 = scroll down (REL_WHEEL -1).
    `amount`: how many notches to send at once (all sent in a single SYN packet —
    effectively an instantaneous step of N lines, faster than N separate ticks).

    The scroll events are written to a dedicated virtual POINTER device
    (EV_KEY + EV_REL with REL_WHEEL), otherwise X11 treats them as a keyboard's
    dead events and no scrolling happens. Faster and lower-latency than
    `xdotool click 4/5` (no process fork per tick), works on Wayland and in
    games. Returns True on success, False if the virtual device is unavailable —
    the caller can then fall back to xdotool.
    """
  if self._ui_scroll is None:
   self._create_scroll_device()
  if self._ui_scroll is None:
   return False
  try:
   with self._ptr_lock:
    self._ui_scroll.write(ecodes.EV_REL, ecodes.REL_WHEEL, direction * int(amount))
    self._ui_scroll.syn()
   return True
  except Exception as exc:
   try:
    dict_save.write_in_log('UInput scroll failed: ' + str(exc))
   except Exception:
    pass
   return False

 def click(self, x11_button):
  """Эмуляция одиночного клика кнопки мыши через виртуальный указатель.

    x11_button: 1=левая, 2=средняя, 3=правая, 4=колесо вверх, 5=колесо вниз
    (нумерация X11). Один вызов = press+release без процессов. Если UInput
    недоступен — возвращаем False, вызывающий код откатывается на xdotool.

    ВАЖНО: клик НЕ должен отпускать кнопки, которые были зажаты через
    button_press (toggle-режим «Держать» / несколько одновременных нажатий).
    Если у кнопки есть активные удержания (ref-count > 0), физический release
    не шлём, чтобы не перебить удержание и не остановить параллельную эмуляцию.
    """
  button_map = {1: ecodes.BTN_LEFT, 2: ecodes.BTN_MIDDLE, 3: ecodes.BTN_RIGHT}
  code = button_map.get(int(x11_button))
  if code is None:
   return False
  if self._ui_scroll is None:
   self._create_scroll_device()
  if self._ui_scroll is None:
   return False
  try:
   with self._ptr_lock:
    held = int(self._pressed_mouse_buttons.get(code, 0)) > 0
    # Press: если кнопка уже удерживается — X уже в состоянии "нажата".
    if not held:
     self._ui_scroll.write(ecodes.EV_KEY, code, 1)
     self._ui_scroll.syn()
    time.sleep(0.01)
    # Release: отпускаем физически только если нет активных удержаний.
    if not held:
     self._ui_scroll.write(ecodes.EV_KEY, code, 0)
     self._ui_scroll.syn()
   return True
  except Exception as exc:
   try:
    dict_save.write_in_log('UInput click failed: ' + str(exc))
   except Exception:
    pass
   return False

 def button_press(self, x11_button):
  """Зажать кнопку мыши (1=ЛКМ, 2=СКМ, 3=ПКМ) БЕЗ отпускания — для режимов
  «держать»/toggle/повтор и для нескольких ОДНОВРЕМЕННЫХ нажатий (например,
  ПКМ->W удерживается, а боковая кнопка эмулирует ПКМ, колёсико крутится).
  Использует ref-count: физический press шлётся один раз при переходе 0->1.

  ВАЖНО (почему UInput, а не pynput XTEST): синтетический X-press
  (XTEST_FakeInput) ЖИВЁТ В X-СЕРВЕРЕ. Если отпускание терялось (краш
  процесса, kill -9, ошибка XTEST, гонка таймера) — X оставался в
  состоянии «кнопка нажата» и физическая правая/средняя кнопка
  «залипала/не работала» во всех приложениях до перезапуска X. UInput-
  устройство принадлежит процессу: при его смерти X автоматически
  отписывает устройство и залипание физически невозможно.
  """
  code = {1: ecodes.BTN_LEFT, 2: ecodes.BTN_MIDDLE, 3: ecodes.BTN_RIGHT}.get(int(x11_button))
  if code is None:
   return False
  if self._ui_scroll is None:
   self._create_scroll_device()
  if self._ui_scroll is None:
   return False
  try:
   with self._ptr_lock:
    count = int(self._pressed_mouse_buttons.get(code, 0))
    if count <= 0:
     self._ui_scroll.write(ecodes.EV_KEY, code, 1)
     self._ui_scroll.syn()
    self._pressed_mouse_buttons[code] = count + 1
   return True
  except Exception as exc:
   try:
    dict_save.write_in_log('UInput button-press failed: ' + str(exc))
   except Exception:
    pass
   return False

 def button_release(self, x11_button):
  """Отпустить кнопку, зажатую button_press(). Ref-count: физический release
  шлётся только при переходе 1->0. Безопасен повторный/пустой вызов.
  """
  code = {1: ecodes.BTN_LEFT, 2: ecodes.BTN_MIDDLE, 3: ecodes.BTN_RIGHT}.get(int(x11_button))
  if code is None:
   return False
  if self._ui_scroll is None:
   return True  # устройства никогда не было — зажатой кнопки тоже нет
  try:
   with self._ptr_lock:
    count = int(self._pressed_mouse_buttons.get(code, 0))
    if count > 1:
     self._pressed_mouse_buttons[code] = count - 1
     return True
    if count <= 0:
     self._pressed_mouse_buttons.pop(code, None)
     return True
    self._ui_scroll.write(ecodes.EV_KEY, code, 0)
    self._ui_scroll.syn()
    self._pressed_mouse_buttons.pop(code, None)
   return True
  except Exception as exc:
   try:
    dict_save.write_in_log('UInput button-release failed: ' + str(exc))
   except Exception:
    pass
   return False

   # Compatibility aliases for code outside this file.
 press = key_down
 release = key_up

smart_typer = SmartTyper()

class Job(threading.Thread):
 def __init__(self, key, *args, **kwargs):
  self.key = key
  # sw=False: воркер стартует в состоянии pause(). Раньше sw=True в паузе
  # давал инвертированный toggle в режиме «держать» (первое нажатие
  # «молчало», прокрутка сдвигалась на одно нажатие).
  self.sw = False
  self.hook_flag_mouse = True  # захват кнопки мыши.
  super(Job, self).__init__(*args, **kwargs)
  self.__flag = threading.Event()  # The flag used to pause the thread
  self.__flag.set()  # Set to True
  self.__running = threading.Event()  # Used to stop the thread identification
  self.__running.set()  # Set running to True

 def run(self): # Событийная эмуляция колеса (В3 evdev/uinput + В4 событийная модель):
 #  - первый клик уходит МГНОВЕННО при resume() (нет задержки старта ~80мс);
 #  - автоповтор идёт по настраиваемому интервалу с компенсацией дрейфа времени;
 #  - при pause()/stop() новых тиков не появляется (нет overscroll после отпускания);
 #  - не создаются потоки на каждый тик и не форкается xdotool/bash (W1/W2/W4/W5/W6/W7/W8/W9).
 # Клавиатурные слоты (key != SCROLL_*) тут не крутят цикл: их обработка
 # выполняется в _handle_keyboard_action напрямую, этот поток лишь ждёт.
  time.sleep(0.00001)
  _active_since = None
  while self.__running.is_set():
   if not self.__flag.is_set():
    self.__flag.wait(0.05)  # paused: ждём resume()/stop() без нагрузки на CPU
    _active_since = None
    continue
   params = self._scroll_params()
   if params is None:
    self.__flag.wait(0.05)  # не-скролл слот — просто не мешаем
    continue
   if _active_since is None:
    _active_since = time.monotonic()
   elif time.monotonic() - _active_since > 300:
    # Страховка: если отпускание кнопки потеряно (реселект устройства,
    # ошибка X-канала), прокрутка не идёт бесконечно — цикл сам стопается.
    dict_save.write_in_log('[safety] цикл прокрутки (%s) сам остановлен по потолку 300 с' % self.key)
    self.pause()
    _active_since = None
    continue
   direction, interval, amount, accel = params
   self._emit(direction, amount)      # первый клик сразу
   self._repeat(direction, interval, amount, accel)

 def _scroll_params(self):
 # Параметры прокрутки берём из профиля (ключ "mouse_scroll"), с
 # безопасными дефолтами — отсутствие ключа в JSON не ломает поведение.
  if self.key == "SCROLL_UP":
   direction = 1
  elif self.key == "SCROLL_DOWN":
   direction = -1
  else:
   return None
  cfg = {}
  try:
   cfg = dict_save.return_jnson().get("mouse_scroll", {}).get(dict_save.get_cur_app(), {}) or {}
  except Exception:
   cfg = {}

  def _bounded(key_name, default, cast, lo, hi):
   try:
    val = cast(cfg.get(key_name, default))
   except (TypeError, ValueError):
    val = default
   if val < lo:
    val = lo
   if val > hi:
    val = hi
   return val

  interval = _bounded("interval", 0.04, float, 0.005, 2.0)
  amount = int(_bounded("amount", 1, float, 1, 20))
  invert = bool(cfg.get("invert", False))
  accel = bool(cfg.get("accel", False))
  if invert:
   direction = -direction
  return direction, interval, amount, accel

 def _emit(self, direction, steps): # Отправка события колеса. Основной путь — evdev/uinput (SmartTyper.scroll),
 # без процессов. Если /dev/uinput недоступен — fallback на xdotool (как раньше).
  if not self.__flag.is_set() or not self.__running.is_set():
   return
  try:
   steps = max(1, int(steps))
  except (TypeError, ValueError):
   steps = 1
  try:
   if not smart_typer.scroll(direction, steps):
    btn = '4' if direction > 0 else '5'
    for _ in range(steps):
     subprocess.call(['xdotool', 'click', btn])
  except Exception as exc:
   try:
    dict_save.write_in_log('scroll emit error: ' + str(exc))
   except Exception:
    pass

 def _repeat(self, direction, interval, amount, accel):
 # Автоповтор: ждём до дедлайна (компенсация дрейфа), реагируя на
 # pause()/stop() почти мгновенно — «лишнего» клика после отпускания нет.
  step = 0
  while self.__running.is_set() and self.__flag.is_set():
   deadline = time.monotonic() + interval
   while time.monotonic() < deadline:
    if not self.__running.is_set() or not self.__flag.is_set():
     return
    time.sleep(0.002)
   if accel:
    step += 1
    steps = amount + (step // 10)  # ускорение при длительном удержании
   else:
    steps = amount
   self._emit(direction, steps)

 def pause(self):
  self.__flag.clear()  # Set to False to block the thread

 def resume(self):
  self.__flag.set()  # Set to True, let the thread stop blocking

 def stop(self):
  self.__flag.set()  # Resume the thread from the suspended state, if it is already suspended
  self.__running.clear()  # Set to False

 def is_active(self):
  # Воркер «активен»: поток жив и не в паузе (идёт прокрутка/повтор).
  # Используется для «сдачи» удержания при смене профиля (см. prepare()).
  return self.__running.is_set() and self.__flag.is_set()

 def set_sw(self, value):
  self.sw = value

 def get_sw(self):
  return self.sw

 def set_hook_flag_mouse(self, value):
  self.hook_flag_mouse = value

 def get_hook_flag_mouse(self):
  return self.hook_flag_mouse

dict_save = save_dict()  # класс


def get_process_info():
 process_info = {}
 pattern = re.compile(r'(/mnt/.*?\.exe)|([A-Z]:/.*?\.exe)', re.IGNORECASE)
 try:
  for proc in psutil.process_iter(['pid', 'username', 'cmdline']):
   if proc.info['username'] == user and proc.info['cmdline']:
    for arg in proc.info['cmdline']:
     arg_clean = arg.replace('\\', '/').strip('"')  # Приводим к нормальному виду
     match = pattern.search(arg_clean)
     if match:
      file_path = match.group(0)
      process_info[proc.info['pid']] = file_path
 except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
  pass
 return process_info


def get_visible_active_pid():
 try:  # Получаем ID активного окна в десятичном формате
  window_id_dec = subprocess.run(['xdotool', 'getactivewindow'],
   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout.strip()
  if not window_id_dec:
   print("Не удалось получить ID активного окна")
   return 0
   # Преобразуем десятичное ID в шестнадцатеричное (например, 1234567 -> 0x01234567)
  window_id_hex = hex(int(window_id_dec))
  # Проверка: окно свернуто?
  xprop_output = subprocess.run(['xprop', '-id', window_id_dec, '_NET_WM_STATE'],
   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout

  if "_NET_WM_STATE_HIDDEN" in xprop_output:
   print("Окно свернуто")
   return 0  # Окно свернуто
   # Получаем список окон с PID
  wmctrl_output = subprocess.run(['wmctrl', '-lp'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
   text=True).stdout
  # Ищем строку с нужным ID окна
  for line in wmctrl_output.splitlines():
   parts = line.split()  # print(parts)
   if len(parts) >= 3 and parts[0] == window_id_hex:
    pid = int(parts[2])  # PID — третий элемент#   print(pid)
    return pid
  return 0  # PID не найден
 except Exception as e:
  print(f"Ошибка: {e}")
  return 0

def is_window_minimized(window_id):
 try:
  xprop_output = subprocess.run(['xprop', '-id', window_id, '_NET_WM_STATE'],
   stdout=subprocess.PIPE, text=True).stdout
  return "_NET_WM_STATE_HIDDEN" in xprop_output
 except Exception:
  return True  # Если ошибка, считаем окно свернутым
  
def get_active_window_exe(user, id_active):
 try:
  result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout
  lines = result.split('\n')
  for line in lines:  # Фильтруем строки по пользователю и PID
   if user in line:  # Проверяем наличие PID и имени пользователя
    parts = line.split(maxsplit=10)  # Разделяем строку, предполагая стандартный формат ps aux
    exe_path = parts[10]
    pid = int(parts[1])
    if id_active == pid:  # "PortProton" in cmdline:# and id_active==pid:
    # print(exe_path)     # print(line)
     return exe_path
  output = subprocess.check_output(['ps', '-eo', 'pid,user,args'], text=True)
  for line in output.strip().split('\n')[1:]:
   parts = line.split(None, 2)
   if len(parts) == 3:
    pid, user, exe_path = parts
    if ".exe" in exe_path and id_active == pid:  # print(exe_path)
     return exe_path
  return None
 except:
  return None

get_main_id = '''#!/bin/bash # Получаем идентификатор активного окна
# Получаем идентификатор активного окна
active_window_id=$(xdotool getactivewindow 2>/dev/null)
if [[ -n "$active_window_id" && "$active_window_id" != "0" && "$active_window_id" =~ ^[0-9]+$ ]]; then
    # Получаем PID процесса, связанного с окном
    process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
    if [[ -n "$process_id_active" && "$process_id_active" != "0" ]]; then
        # Проверяем родительский PID
        parent_pid=$(ps -p "$process_id_active" -o ppid= | tr -d '[:space:]')
        if [[ -n "$parent_pid" && "$parent_pid" != "0" && "$parent_pid" != "1" ]] && ps -p "$parent_pid" >/dev/null 2>&1; then
            echo "$parent_pid"
            exit 0
        else
            echo "$process_id_active"
            exit 0
        fi
         echo "0"
         exit 0
    fi
     echo "0"
     exit 0
fi
exit'''

# ==== БЫСТРОЕ определение игры в активном окне (2026-11-16) ====
# Полный обход psutil по 350+ процессам стоит 140-200 мс, поэтому
# авто-переключение профиля по окну «тормозило» на 1-2 секунды. В типичном
# случае окно принадлежит самому игровому процессу, и достаточно прочитать
# /proc/<pid>/exe|cmdline|cwd — это единицы миллисекунд. Медленный обход
# остаётся страховкой, если быстрый путь ничего не нашёл.
_WINE_SYSTEM_BASES = frozenset({
 'services.exe', 'winedevice.exe', 'plugplay.exe', 'explorer.exe',
 'svchost.exe', 'rpcss.exe', 'wineserver.exe', 'start.exe', 'winepath.exe',
 'conhost.exe', 'csrss.exe', 'lsass.exe', 'dllhost.exe', 'cmd.exe',
 'notepad.exe', 'regedit.exe', 'taskmgr.exe', 'winemenubuilder.exe',
 'wineboot.exe', 'wineserver', 'services', 'plugplay', 'rpcss',
 })


def _proc_readlink(path):
 try:
  return os.readlink(path)
 except OSError:
  return ''


def _proc_cmdline(pid):
 try:
  with open('/proc/%d/cmdline' % int(pid), 'rb') as handle:
   raw = handle.read()
 except (OSError, TypeError, ValueError):
  return []
 return [part.decode('utf-8', 'replace') for part in raw.split(b'\0') if part]


def _proc_ppid(pid):
 try:
  with open('/proc/%d/stat' % int(pid), 'r') as handle:
   stat = handle.read()
  return int(stat[stat.rindex(')') + 2:].split()[1])
 except (OSError, ValueError, TypeError, IndexError):
  return 0


def _proc_children(pid):
 try:
  with open('/proc/%d/task/%d/children' % (int(pid), int(pid)), 'r') as handle:
   return [int(item) for item in handle.read().split() if item.isdigit()]
 except (OSError, ValueError, TypeError):
  return []


def _quick_resolve_exe(pid):
 """Путь exe процесса по /proc. Для Wine — cwd + имя .exe из cmdline."""
 exe = _proc_readlink('/proc/%d/exe' % int(pid))
 cmdline = _proc_cmdline(pid)
 cwd = _proc_readlink('/proc/%d/cwd' % int(pid))
 win_exe = next((arg for arg in cmdline if arg.lower().endswith('.exe')), None)
 if win_exe:
  exe_name = os.path.basename(win_exe.replace('\\', '/'))
  if cwd and exe_name:
   candidates = (os.path.join(cwd, exe_name),
    os.path.normpath(os.path.join(cwd, win_exe.replace('\\', '/'))))
   for candidate in candidates:
    if os.path.isfile(candidate):
     return candidate
 if exe:
  return exe
 if cmdline:
  first = cmdline[0].replace('\\', '/')
  if first.startswith('/') and os.path.isfile(first):
   return first
  if cwd and first:
   candidate = os.path.normpath(os.path.join(cwd, first))
   if os.path.isfile(candidate):
    return candidate
 return ''


def _is_game_exe_path(path):
 base = os.path.basename(str(path or '')).lower()
 return base.endswith('.exe') and base not in _WINE_SYSTEM_BASES


def _quick_window_game_path(win_pid):
 """Быстрый аналог стратегий 1-5 из Get_pid_and_path_window.

 Возвращает (pid_окна, путь) или None, если быстрый путь не дал результата
 (тогда вызывающий делает полный обход). Порядок тот же: потомки окна →
 само окно → предки → любой .exe/.sh."""
 if not win_pid:
  return None
 for child in _proc_children(win_pid):
  path = _quick_resolve_exe(child)
  if _is_game_exe_path(path):
   return win_pid, path
 path = _quick_resolve_exe(win_pid)
 if _is_game_exe_path(path):
  return win_pid, path
 ancestor = _proc_ppid(win_pid)
 for _ in range(4):
  if not ancestor or ancestor <= 1:
   break
  path = _quick_resolve_exe(ancestor)
  if _is_game_exe_path(path):
   return win_pid, path
  ancestor = _proc_ppid(ancestor)
 # Любой .exe/.sh (аналог стратегий 2/4). Профиль всё равно сверяется со
 # списком включённых, поэтому ложного переключения не будет.
 for candidate_pid in [win_pid] + _proc_children(win_pid):
  path = _quick_resolve_exe(candidate_pid)
  if path and path.lower().endswith(('.exe', '.sh')):
   return win_pid, path
 return None


def Get_pid_and_path_window():  # Получаем идентификатор активного окна

# Кэш winepath и скомпилированная регулярка через атрибуты функции (ускоряет повторные вызовы)
 if not hasattr(Get_pid_and_path_window, "_winepath_cache"):
  Get_pid_and_path_window._winepath_cache = {}
 if not hasattr(Get_pid_and_path_window, "_RE_EXE_SH"):
  Get_pid_and_path_window._RE_EXE_SH = re.compile(r'.*\.(exe|sh)$', re.IGNORECASE)
  
 winepath_cache = Get_pid_and_path_window._winepath_cache
 _RE_EXE_SH = Get_pid_and_path_window._RE_EXE_SH
 
 # Кэш результата: полный обход (psutil по ВСЕМ процессам + xdotool + BFS)
 # стоит 50-200 мс и без кэша прогонялся десятки раз в секунду — 50-90% ядра.
 # Быстрый путь: одно окно xdotool (дешёвое, TTL 0.1 с) + результат.
 # (2026-11-16) Активное окно не сменилось — результат валиден до 5 с;
 # сменилось — пересчёт НЕМЕДЛЕННО (раньше был ещё 1 с «залипания» на старом
 # окне: выход из игры/переключение в игру ощущались как задержка).
 _now = time.monotonic()
 _cached = getattr(Get_pid_and_path_window, "_result_cache", None)
 _prev_win = getattr(Get_pid_and_path_window, "_prev_win_id", None)
 try:
  _win_cache = getattr(Get_pid_and_path_window, "_win_cache", None)
  if _win_cache is not None and _now - _win_cache[0] < 0.1:
   _win_id = _win_cache[1]
  else:
   _win_id = subprocess.check_output(
    ['xdotool', 'getactivewindow'], stderr=subprocess.DEVNULL, timeout=1
   ).decode().strip()
   Get_pid_and_path_window._win_cache = (_now, _win_id)
 except Exception:
  _win_id = ''

 # (2026-11-16) Пооконный кэш результата. Раньше результат хранился в ОДНОМ
 # слоте: при смене окна TTL=0 и полный обход psutil (35-260 мс, с GIL) шёл
 # на КАЖДОМ Alt-Tab/меню/всплывашке — приложение «подвисало» (жалоба:
 # «тормозит, как будто грузит процессор»). Теперь результат запоминается
 # по ID окна: вернулись к уже виденному окну — сразу отдаём кэш; новое окно
 # (напр. только что запущенная игра) — считаем немедленно. TTL записи 5 с.
 _bywin = getattr(Get_pid_and_path_window, "_result_by_win", None)
 if _bywin is None:
  _bywin = {}
  Get_pid_and_path_window._result_by_win = _bywin
 if _win_id and _win_id.isdigit() and _win_id != '0':
  _hit = _bywin.get(_win_id)
  if _hit is not None and _now - _hit[0] < 5.0:
   return _hit[1]
 if len(_bywin) > 64:
  for _k in list(_bywin):
   if _now - _bywin[_k][0] >= 30.0:
    _bywin.pop(_k, None)
  if len(_bywin) > 64:
   _bywin.clear()

 if _cached is not None:
  _ttl = 5.0 if (_win_id and _win_id == _prev_win) else 0.0
  if _now - _cached[0] < _ttl:
   return _cached[1]

 # ── БЫСТРЫЙ ПУТЬ (2026-11-16): окно → PID → /proc, единицы миллисекунд ──
 if _win_id and _win_id.isdigit() and _win_id != '0':
  try:
   _win_pid_raw = subprocess.check_output(
    ['xdotool', 'getwindowpid', _win_id], stderr=subprocess.DEVNULL, timeout=1
   ).decode().strip()
  except Exception:
   _win_pid_raw = ''
  if _win_pid_raw and _win_pid_raw.isdigit() and _win_pid_raw != '0':
   _quick = _quick_window_game_path(int(_win_pid_raw))
   if _quick is not None:
    _q_pid, _q_path = _quick
    _result = ({_q_pid: _q_path, int(_win_pid_raw): _q_path}, int(_win_pid_raw))
    Get_pid_and_path_window._result_cache = (_now, _result)
    Get_pid_and_path_window._prev_win_id = _win_id
    if _win_id:
     Get_pid_and_path_window._result_by_win[_win_id] = (_now, _result)
    return _result
 
 # 1. Получение пользователя
 user = (
  os.environ.get('USER')
  or os.environ.get('LOGNAME')
  or (pwd.getpwuid(os.getuid()).pw_name if hasattr(os, 'getuid') else None)
  )
 if not user:
  try:
   user = subprocess.check_output(['whoami'], text=True, timeout=1).strip() or None
  except Exception:
   user = None
  
 my_pid = os.getpid()
 data_dict = {}
 parent_map = {}
 children_map = {}
  
 # === Один быстрый проход по всем процессам ===
 # Запрашиваем нужные атрибуты сразу (работает на C-уровне psutil, быстрее os.readlink)
 for proc in psutil.process_iter(["pid", "username", "cmdline", "ppid", "exe", "cwd"]):
  try:
   info = proc.info
   pid = info["pid"]
   if pid == my_pid:
    continue
    
    # Строим дерево процессов в памяти (O(1) доступ вместо чтения /proc)
   ppid = info.get("ppid")
   parent_map[pid] = ppid
   if ppid:
    children_map.setdefault(ppid, []).append(pid)
    
   if user is not None and info.get("username") != user:
    continue
    
   cmdline_parts = info.get("cmdline") or []
   cwd = info.get("cwd")
   exe_link = info.get("exe")
    
   # --- Определяем, Wine ли это ---
   is_wine = False
   if exe_link:
    low_exe = exe_link.lower()
    if 'wine-preloader' in low_exe or 'wine64-preloader' in low_exe or '/wine' in low_exe:
     is_wine = True
   if not is_wine and cmdline_parts:
    is_wine = any('.exe' in arg.lower() for arg in cmdline_parts)
    
   resolved = None
    
   # ===== WINE-процесс =====
   if is_wine:
    win_exe = None
    for arg in cmdline_parts:
     if arg.lower().endswith('.exe'):
      win_exe = arg
      break
     
    if win_exe:
     exe_name = os.path.basename(win_exe.replace('\\', '/'))
     found = False
      
     # 1. Абсолютный Windows-путь
     if len(win_exe) >= 2 and win_exe[1] == ':':
      if win_exe in winepath_cache:
       linux_path = winepath_cache[win_exe]
      else:
       try:
        r = subprocess.run(
         ['winepath', '-u', win_exe],
         capture_output=True, text=True, timeout=1.5
         )
        linux_path = r.stdout.strip() if r.returncode == 0 else None
       except Exception:
        linux_path = None
       winepath_cache[win_exe] = linux_path
       
      if linux_path and os.path.isfile(linux_path):
       resolved = linux_path
       found = True
      
       # 2. cwd + basename
     if not found and cwd and exe_name:
      candidate = os.path.join(cwd, exe_name)
      if os.path.isfile(candidate):
       resolved = candidate
       found = True
      
       # 3. Относительный путь (dx11\Game.exe)
     if not found and cwd:
      rel = win_exe.replace('\\', '/')
      candidate = os.path.normpath(os.path.join(cwd, rel))
      if os.path.isfile(candidate):
       resolved = candidate
       found = True
      
       # 4. Fallback: быстрый поиск на чистом Python (аналог find -maxdepth 2)
     if not found and cwd and exe_name:
      try:
       exe_name_lower = exe_name.lower()
       cwd_clean = cwd if cwd.endswith(os.sep) else cwd + os.sep
       for root, dirs, files in os.walk(cwd):
        if root != cwd:
         if root.startswith(cwd_clean):
          rel_path = root[len(cwd_clean):]
          depth = rel_path.count(os.sep) + 1
         else:
          depth = 3
         if depth >= 3:
          dirs.clear()  # Прерываем спуск (эквивалент -maxdepth 2)
          continue
        for f in files:
         if f.lower() == exe_name_lower:
          resolved = os.path.join(root, f)
          break
        if resolved:
         break
      except (PermissionError, FileNotFoundError, OSError):
       pass
    
       # ===== Обычный Linux-процесс =====
   else:
    if not cmdline_parts:
     resolved = exe_link
    else:
     relative_exe = cmdline_parts[0].replace("\\", "/")
     if relative_exe.startswith('/'):
      full_path = relative_exe
     elif cwd and relative_exe:
      full_path = os.path.normpath(os.path.join(cwd, relative_exe))
     else:
      full_path = None
      
     if full_path and os.path.isfile(full_path):
      resolved = full_path
     else:
      resolved = exe_link
    
      # --- Доп. сканирование cmdline ---
   if not resolved:
    for arg in cmdline_parts:
     arg_clean = arg.replace('\\', '/').strip('"')
     if _RE_EXE_SH.search(arg_clean):
      resolved = arg_clean
      break
    
   if resolved:
    data_dict[pid] = resolved
    try:
     # Треды мапим ТОЛЬКО для wine/.exe/.sh-процессов: чужое окно может
     # принадлежать не основному TID процесса (getwindowpid отдаёт TID).
     # Для обычных процессов win_pid == TID основного треда — mapping всех
     # ~2000 системных потоков стоил 60-80% времени скана (psutil).
     if is_wine or (resolved.lower().endswith('.exe') or resolved.lower().endswith('.sh')):
      for thread in proc.threads():
       data_dict[thread.id] = resolved
    except Exception:
     pass
   
  except Exception:
   continue
  
   # === Разворачиваем словарь на родителей/потомков ===
   # BFS по уже построенным словарям (вместо медленных proc.parent() и proc.children())
 expanded = dict(data_dict)
 for game_pid, game_path in data_dict.items():
 # Родители
  curr = parent_map.get(game_pid)
  while curr and curr != 0:
   if curr not in expanded:
    expanded[curr] = game_path
   curr = parent_map.get(curr)
   
   # Потомки (BFS через список вместо deque, чтобы не требовать лишних импортов)
  queue = [game_pid]
  idx = 0
  while idx < len(queue):
   curr = queue[idx]
   idx += 1
   for child in children_map.get(curr, []):
    if child not in expanded:
     expanded[child] = game_path
     queue.append(child)
  
     # === PID активного окна + консистентный путь ===
     # Множество системных exe Wine — НЕ являются целевыми играми
 WINE_SYSTEM = frozenset({  'services.exe', 'winedevice.exe', 'plugplay.exe', 'explorer.exe',
  'svchost.exe', 'rpcss.exe', 'wineserver.exe', 'start.exe',
  'winepath.exe', 'conhost.exe', 'csrss.exe', 'lsass.exe',
  'dllhost.exe', 'cmd.exe', 'notepad.exe', 'regedit.exe',
  'taskmgr.exe', 'winemenubuilder.exe', 'wineboot.exe',
  'wineserver', 'services', 'plugplay', 'rpcss',
  })
  
 def _is_game(path):
  """Путь ведёт к реальной игре, а не к системному exe Wine."""
  if not path:
   return False
  base = os.path.basename(path).lower()
  if not base.endswith('.exe'):
   return False
  return base not in WINE_SYSTEM
  
 def _is_any_exe(path):
  """Любой .exe — последний fallback, но БЕЗ системных exe Wine:
  (Исправление 2026-11-09, дооформление §15/§26) фоновые services.exe /
  wine-системные окна не должны тянуть игровой профиль на не-игровое
  активное окно — из-за этого профиль игры «прилипал» к браузеру бота
  (write_text_fast.py) и макросы xte печатали в его поле ввода."""
  if not path:
   return False
  base = os.path.basename(path).lower()
  if not base.endswith('.exe'):
   return False
  return base not in WINE_SYSTEM
 
 def _bfs_down(start, visitor):
  """BFS вниз от start, вызывает visitor(child_pid, child_path) — True = стоп."""
  queue = [start]
  idx = 0
  while idx < len(queue):
   curr = queue[idx]
   idx += 1
   for child in children_map.get(curr, []):
    if visitor(child, expanded.get(child, '')):
     return child
    queue.append(child)
  return 0
  
 def _walk_up(start, visitor):
  """Идём вверх по parent_map, вызывает visitor(pid, path) — True = стоп."""
  curr = parent_map.get(start)
  while curr and curr != 0:
   if visitor(curr, expanded.get(curr, '')):
    return curr
   curr = parent_map.get(curr)
  return 0
  
 id_active = 0
 game_path = None
 try:
  win_id = subprocess.check_output(['xdotool', 'getactivewindow'], stderr=subprocess.DEVNULL, timeout=1).decode().strip()
  if win_id and win_id.isdigit() and win_id != '0':
   win_pid = subprocess.check_output(['xdotool', 'getwindowpid', win_id], stderr=subprocess.DEVNULL, timeout=1).decode().strip()
   if win_pid and win_pid.isdigit() and win_pid != '0':
    win_pid_int = int(win_pid)
     
    # ── Стратегия 1: потомки окна — ищем реальную игру (не system exe) ──
    found = _bfs_down(win_pid_int, lambda p, pth: _is_game(pth))
    if found:
     id_active = found
     game_path = expanded[found]
     
     # ── Стратегия 2: потомки окна — принимаем ЛЮБОЙ .exe (включая system) ──
    if not id_active:
     found = _bfs_down(win_pid_int, lambda p, pth: _is_any_exe(pth))
     if found:
      id_active = found
      game_path = expanded[found]
     
      # ── Стратегия 3: родители окна — ищем игру среди предков ──
    if not id_active:
     found = _walk_up(win_pid_int, lambda p, pth: _is_game(pth))
     if found:
      id_active = found
      game_path = expanded[found]
     
      # ── Стратегия 4: родители окна — любой .exe ──
    if not id_active:
     found = _walk_up(win_pid_int, lambda p, pth: _is_any_exe(pth))
     if found:
      id_active = found
      game_path = expanded[found]
     
      # ── Стратегия 5: само окно ──
    if not id_active:
     self_path = expanded.get(win_pid_int, '')
     if _is_game(self_path) or _is_any_exe(self_path):
      id_active = win_pid_int
      game_path = self_path
     
      # ── Fallback: ppid (старая логика) ──
    if not id_active:
     ppid = parent_map.get(win_pid_int)
     if ppid and ppid not in (0, 1) and ppid in parent_map:
      id_active = ppid
     else:
      try:
       ps_out = subprocess.check_output(
        ['ps', '-p', str(win_pid_int), '-o', 'ppid='],
        stderr=subprocess.DEVNULL, timeout=1
        ).decode().strip()
       ppid_int = int(ps_out) if ps_out.isdigit() else 0
       if ppid_int and ppid_int not in (0, 1):
        subprocess.check_call(['ps', '-p', str(ppid_int)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
        id_active = ppid_int
       else:
        id_active = win_pid_int
      except Exception:
       id_active = win_pid_int
     game_path = expanded.get(id_active)
     
     # === Делаем expanded консистентным: всё дерево активного окна → один путь ===
    if id_active and game_path:
    # Обновляем сам id_active
     expanded[id_active] = game_path
     # Родители
     curr = parent_map.get(id_active)
     while curr and curr != 0:
      expanded[curr] = game_path
      curr = parent_map.get(curr)
      # Потомки
     queue = [id_active]
     idx2 = 0
     while idx2 < len(queue):
      curr = queue[idx2]
      idx2 += 1
      for child in children_map.get(curr, []):
       expanded[child] = game_path
       queue.append(child)
 except Exception:
  pass
  
 _result = (expanded, id_active)
 Get_pid_and_path_window._result_cache = (_now, _result)
 Get_pid_and_path_window._prev_win_id = _win_id
 if _win_id:
  Get_pid_and_path_window._result_by_win[_win_id] = (_now, _result)
 return _result

_profile_running_cache = {'ts': 0.0, 'path': None, 'running': False}


def is_profile_process_running(profile_path):
 """Best-effort check whether a profile's target executable/script is running.

 Used to auto-release a manually-held game profile after the game exits so the
 runtime can return to the default/fallback profile and restore the button map."""
 global _profile_running_cache
 if not profile_path:
  return False
 now = time.monotonic()
 cache = _profile_running_cache or {}
 if cache.get('path') == profile_path and (now - cache.get('ts', 0.0)) < 2.0:
  return bool(cache.get('running'))
 running = False
 try:
  base = os.path.basename(str(profile_path)).lower()
  norm = os.path.normpath(str(profile_path)).lower()
  if not base:
   running = True
  else:
   # (2026-11-16) Быстрый путь: /proc/<pid>/exe — 2-4 мс на 350 процессов
   # вместо 150-200 мс у psutil.process_iter с cmdline. Нужен в цикле
   # авто-переключения профиля (выход из игры), поэтому важен каждый мс.
   for entry in os.scandir('/proc'):
    if not entry.name.isdigit():
     continue
    exe = _proc_readlink('/proc/%s/exe' % entry.name).replace('\\', '/')
    if exe:
     exe_norm = os.path.normpath(exe).lower()
     if exe_norm == norm or os.path.basename(exe_norm) == base:
      running = True
      break
    # Wine: интересующий .exe может быть только в cmdline, а /proc/pid/exe
    # указывать на wine-preloader. Сравниваем ТОЛЬКО полный путь из cmdline:
    # сравнение по имени файла давало ложные срабатывания на обёртках вида
    # `gamescopereaper -- wine hl2.exe` (в их cmdline есть только «hl2.exe»),
    # из-за чего «игра ещё запущена» оставалось навсегда и профиль не
    # возвращался на не-игровой.
    for arg in _proc_cmdline(entry.name):
     a = str(arg).replace('\\', '/').strip('"')
     if not a or '/' not in a:
      continue
     a_norm = os.path.normpath(a).lower()
     if a_norm == norm:
      running = True
      break
    if running:
     break
 except Exception:
  # Fail-open: on scan errors do not drop an active profile unexpectedly.
  running = True
 _profile_running_cache = {'ts': now, 'path': profile_path, 'running': running}
 return running


def default_profile_path(store, enabled_profiles):
 """Return a valid fallback profile; prefer the explicitly named default."""
 settings = store.return_jnson()
 paths = settings.get('paths', {})
 enabled = set(enabled_profiles)
 for path, name in paths.items():
  if path in enabled and (name == 'По умолчанию' or path == 'C:/Windows/explorer.exe'):
   return path
 return next((path for path in paths if path in enabled), '')


def fallback_profile_path(store, enabled_profiles):
 """Return a SAFE non-game profile (the default one).

 (Исправление 2026-11-16, analysis п.22): раньше здесь возвращался
 `prev_game`, который мог оказаться игровым профилем. Из-за этого после
 выхода из игры «безопасный» fallback сам был игрой, и профиль не
 переключался. Возврат к ручному выбору пользователя делает emunator_mouse
 через store.user_profile, а fallback — только страховка."""
 fallback = default_profile_path(store, enabled_profiles)
 if fallback:
  store.set_prev_game(fallback)
 return fallback


def remember_fallback_before_game(store, current_profile, next_profile, enabled_profiles):
 """Keep the non-game/default profile while moving between game windows."""
 saved = fallback_profile_path(store, enabled_profiles)
 if current_profile == saved and current_profile != next_profile:
  store.set_prev_game(current_profile)


# ==== Канонизация путей pid по директориям профилей (§27) ====
# Правило: одна директория из настроек = одна игра. Любой exe из папки профиля
# приравнивается к пути профиля (GTAVLauncher.exe <-> GTA5.exe, portal2.exe <->
# Play Portal 2.exe и т.п.). Кэш пересобирается при смене списка профилей,
# раз в час или при появлении нового exe в папке профиля.

def build_profile_dir_map(games_checkmark_paths, force=False):
 """Собрать {exe (lower) -> путь профиля} и {директории профилей}. Кэшируется."""
 cache = getattr(build_profile_dir_map, "_cache", None)
 key = tuple(games_checkmark_paths)
 now = time.time()
 if not force and cache and cache["key"] == key and (now - cache["ts"]) < 3600:
  return cache["exe_map"], cache["dirs"]
 exe_map = {} # exe из папки профиля (lower) -> путь профиля из настроек
 dirs = set() # директории всех профилей с галочкой
 for profile_path in games_checkmark_paths:
  d = os.path.dirname(profile_path or '')
  if not d:
   continue
  dirs.add(os.path.normpath(d).lower())
  # Папка в настройках может отличаться регистром от реальной
  # ("Entropy Zero 2" vs "entropy zero 2"). Linux-ФС регистрозависима,
  # поэтому ищем реальную папку без учёта регистра (2026-11-16).
  d_actual = d
  if not os.path.isdir(d_actual):
   try:
    _parent = os.path.dirname(d)
    _base = os.path.basename(d).lower()
    for _name in os.listdir(_parent):
     if _name.lower() == _base:
      _cand = os.path.join(_parent, _name)
      if os.path.isdir(_cand):
       d_actual = _cand
       break
   except OSError:
    pass
  try:
   # Собираем exe в самой папке профиля (без под папок)
   exes = [f for f in os.listdir(d_actual)
    if f.lower().endswith('.exe') and os.path.isfile(os.path.join(d_actual, f))]
  except OSError:
   continue # папка недоступна (в т.ч. Windows-пути вида C:/...)
  if len(exes) > 25:
   # «Общая» папка с кучей чужих exe (напр. linux must have) — точечно:
   # маппим только сам exe профиля, иначе любой сосед захватит профиль
   exe_map[os.path.normpath(profile_path).lower()] = profile_path
   continue
  for f in exes:
   full = os.path.normpath(os.path.join(d_actual, f)).lower()
   if full not in exe_map: # два профиля в одной папке: выигрывает первый в списке
    exe_map[full] = profile_path
 build_profile_dir_map._cache = {"key": key, "ts": now, "exe_map": exe_map, "dirs": dirs}
 return exe_map, dirs


def canonicalize_pid_paths(data_dict, games_checkmark_paths):
 """Заменить пути pid на пути профилей: exe в директории профиля = та же игра."""
 exe_map, dirs = build_profile_dir_map(games_checkmark_paths)
 if not exe_map:
  return data_dict # нет доступных папок профилей -> без изменений
 canon = dict(data_dict)
 for pid, p in data_dict.items():
  if not p or not p.lower().endswith('.exe'):
   continue
  norm = os.path.normpath(p).lower()
  if norm in exe_map:
   canon[pid] = exe_map[norm] # exe лежит в папке профиля -> путь профиля
  elif os.path.dirname(norm) in dirs:
   # exe появился в папке профиля ПОЗЖЕ построения карты -> пересобрать
   exe_map, dirs = build_profile_dir_map(games_checkmark_paths, force=True)
   if norm in exe_map:
    canon[pid] = exe_map[norm]
 return canon


def check_current_active_window(dict_save, games_checkmark_paths):
 """Return the game profile for the focused window, or '' if no game is focused.

 ВАЖНО (2026-11-16): раньше при отсутствии игрового окна возвращался fallback-
 профиль, из-за чего вызывающий код не мог отличить «игра в фокусе» от «игры
 нет» (особенно когда fallback сам был игровым). Теперь явный признак «игры
 нет» — пустая строка; решение, какой профиль включить, принимает вызывающий
 код (emunator_mouse → профиль, выбранный пользователем вручную)."""
 try:
  data_dict, id_active = Get_pid_and_path_window()
  # Канонизация: exe из папки профиля приравнивается к пути профиля (§27)
  data_dict = canonicalize_pid_paths(data_dict, games_checkmark_paths)
  file_path = data_dict.get(id_active, '')
  has_exe = any('.exe' in p for p in data_dict.values())
  if has_exe and file_path and is_path_in_list(file_path, games_checkmark_paths):
   result = games_checkmark_paths[get_index_of_path(file_path, games_checkmark_paths)]
   # print(f"[OK] {os.path.basename(file_path)} -> {result}")
   return result

  # ЗАМЕТКА (исправление 2026-11-09): здесь раньше стояла ветка §26
  # («PortProton-gate»), но она была МЁРТВЫМ КОДОМ: недостижима (сразу
  # после `return result` на строке выше) и ссылалась на несуществующие в
  # этой функции переменные (game_path/expanded/win_pid_int — NameError).
  # Гейт перенесён в Get_pid_and_path_window: стратегии 2/4 теперь не
  # принимают WINE_SYSTEM-exe (services.exe и др.), поэтому фоновые
  # wine-процессы больше не затягивают чужой игровой профиль на
  # не-игровое окно (браузер бота, рабочий стол).
  return ''

 except Exception as exc:
  pass
 return ''

def show_list_id_callback():
 show_list_id = f'''#!/bin/bash
   gnome-terminal -- bash -c 'xinput list;
   read;   exec bash' '''  # показать список устройств в терминале
 subprocess.run(['bash', '-c', show_list_id])

class MouseBinding:
 """One intercepted physical mouse control and its runtime state."""

 def __init__(self, listener_button, slot, worker):
  self.listener_button = listener_button
  self.slot = slot
  self.worker = worker
  # Последовательная обработка событий конкретной кнопки в отдельном потоке,
  # чтобы обработчик pynput не блокировался (xdotool/скрипты) и можно было
  # одновременно нажимать/держать несколько разных кнопок.
  self._queue = []
  self._cond = threading.Condition()
  self._dispatch_stop = False
  self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
  self._dispatch_thread.start()

 def enqueue(self, runtime, pressed):
  with self._cond:
   self._queue.append((runtime, pressed))
   self._cond.notify()

 def stop_dispatch(self):
  with self._cond:
   self._dispatch_stop = True
   self._cond.notify_all()

 def join_dispatch(self, timeout=1.0):
  try:
   self._dispatch_thread.join(timeout=timeout)
  except Exception:
   pass

 def _dispatch_loop(self):
  while True:
   with self._cond:
    while not self._queue and not self._dispatch_stop:
     self._cond.wait(timeout=0.2)
    if self._dispatch_stop and not self._queue:
     return
    if not self._queue:
     continue
    runtime, pressed = self._queue.pop(0)
   try:
    if runtime is not None and not runtime.stop_requested.is_set():
     runtime._dispatch_binding(self, pressed)
   except Exception as exc:
    try:
     if runtime is not None:
      runtime.store.write_in_log('binding dispatch error: ' + str(exc))
    except Exception:
     pass
   except BaseException:
    pass


class MouseProfileRuntime:
 """All state required to run one active mouse profile.

    The object is intentionally created once per profile activation.  It replaces
    the former parallel parameters (`key`, `list_buttons`, `press_button`,
    `string_keys`, and `games_checkmark_paths`) with one explicit context.
    """
  # slot, physical X11 button, virtual X11 button, pynput listener button,
  # assignments that retain their normal physical behavior and are not hooked.
 INTERCEPTION_RULES = (
  (1, 3, '11', 'Button.button11', {'RBUTTON'}),
  (2, 2, '12', 'Button.button12', {' ', 'WHEEL_MOUSE_BUTTON'}),
  # Слот 3: ' ' тоже pass-through — раньше пустое назначение всё равно
  # перехватывало физическую кнопку 4 и глухо съедало прокрутку вверх.
  (3, 4, '13', 'Button.button13', {' ', 'SCROLL_UP'}),
  (4, 5, '14', 'Button.button14', {' ', 'SCROLL_DOWN'}),
  # В конфигурации пользователя верхняя боковая кнопка приходит
  # как физическая 9 / Button.button16. Поэтому она соответствует
  # строке «1 боковая», а физическая 8 — строке «2 боковая».
  (5, 9, '16', 'Button.button16', {'XBUTTON1', 'XBUTTON2'}),
  (6, 8, '15', 'Button.button15', {'XBUTTON2', 'XBUTTON1'}),
  )
 MOUSE_ACTIONS = {
  'LBUTTON', 'RBUTTON', 'WHEEL_MOUSE_BUTTON', 'MBUTTON',
  'SCROLL_UP', 'SCROLL_DOWN',
 }
 # Физические (до-ремап) имена кнопок pynput для каждого слота. Нужны как
 # fallback: если xinput set-button-map не применился (устаревший/неверный
 # id устройства, нет доступа к X), кнопки остаются под нативными номерами
 # и без этих алиасов слушатель вообще не «видит» нажатия, поэтому
 # назначенные клавиши не срабатывают.
 PHYSICAL_FALLBACK = {
  1: ('Button.right',),
  2: ('Button.middle',),
  3: ('Button.scroll_up', 'Button.x1'),
  4: ('Button.scroll_down', 'Button.x2'),
  5: ('Button.button9',),
  6: ('Button.button8',),
 }

 def __init__(self, store, start_game=None, force_ui_selection=False):
  self.store = store
  self.settings = store.return_jnson()
  self.enabled_profiles = tuple(
   path for path, enabled in self.settings['games_checkmark'].items() if enabled
   )
  # Цель эмуляции выбирается в порядке приоритета:
  #  0) force_ui_selection=True — явно использовать current_app (ручной клик в
  #     UI). Ручной выбор применяется СРАЗУ и имеет абсолютный приоритет.
  #  1) start_game — явная цель (авто-переключение по активному окну из
  #     emunator_mouse либо только что выбранный вручную профиль);
  #  2) иначе — профиль, выбранный в UI (current_app). Ручной выбор в списке
  #     профилей применяется СРАЗУ, не дожидаясь фокуса окна игры.
  #  3) иначе — фолбэк по активному окну.
  # current_app при этом НИКОГДА не перезаписывается монитором окна.
  selected = str(self.settings.get('current_app', ''))
  if force_ui_selection and selected in self.enabled_profiles:
   self.game = selected
  elif start_game and start_game in self.enabled_profiles:
   self.game = str(start_game)
  elif selected in self.enabled_profiles:
   self.game = selected
  else:
   _active = check_current_active_window(store, self.enabled_profiles)
   self.game = str(_active) if _active else (selected if selected else fallback_profile_path(store, self.enabled_profiles))
  # (Исправление 2026-11-13, §36): «ручной выбор не должен откатываться».
  # force_ui_selection=True ставит флаг manual_ui_pick, и emunator_mouse
  # пропускает откат игрового профиля на fallback, пока пользователь не
  # выберет другой профиль или реальное игровое окно не станет активным.
  self.manual_ui_pick = bool(force_ui_selection and self.game == selected
   and selected in self.enabled_profiles)
  self.device_id = self.settings['id']
  self.assignments = list(self.settings['key_value'][self.game])
  self.hold_flags = list(self.settings.get('mouse_press', {}).get(self.game, [False] * 7))
  self.hold_flags += [False] * (7 - len(self.hold_flags))
  self.hold_flags = self.hold_flags[:7]
  durations = self.settings.get('mouse_hold_repeat_seconds', {}).get(self.game, [None] * 7)
  self.hold_durations = list(durations) if isinstance(durations, list) else [None] * 7
  repeats = self.settings.get('mouse_repeat', {}).get(self.game, [False] * 7)
  self.repeat_flags = list(repeats) if isinstance(repeats, list) else [False] * 7
  self.repeat_flags += [False] * (7 - len(self.repeat_flags))
  self.repeat_flags = self.repeat_flags[:7]
  self.hold_durations += [None] * (7 - len(self.hold_durations))
  self.hold_durations = self.hold_durations[:7]
  self._timed_holds = {}
  self._timed_holds_lock = threading.RLock()
  # Какие физические кнопки сейчас считаются нажатыми (по слотам). Заполняется
  # из событий listener, проверяется сторожевым потоком по РЕАЛЬНОМУ состоянию
  # устройства (xinput query-state). Если событие отпускания потерялось
  # (XRecord/ремap/ошибка X), сторож всё равно снимет эмуляцию — «одно
  # нажатие» никогда не станет бесконечным (2026-11-16).
  self._slot_pressed = {}
  self._slot_pressed_lock = threading.RLock()
  # Слоты, у которых есть активная эмуляция (нужно проверять сторожем).
  self._watch_slots = set()
  self._watch_stop = threading.Event()
  self._watch_thread = None
  # Залипания кнопок — per-runtime: глобальный флаг не сбрасывался при
  # смене профиля и «перетаскивался» между играми (analysis §4).
  # (Исправление 2026-11-15, §40.4): _right/_middle_sticking — это состояния
  # TOGGLE-режима «Держать» (нажать — зажать, нажать снова — отпустить).
  # Их НЕЛЬЗЯ сбрасывать при каждом отпускании физической кнопки, иначе
  # залипание будет отключаться сразу после физического отпускания и
  # удержание (например, ПКМ->W) не «перекрывалось» бы другими кнопками.
  # Физическое отпускание кнопки НЕ сбрасывает toggle; toggle снимается
  # повторным нажатием (toggle), таймером (duration), stop() или
  # _release_sticky_buttons(force=True) при смене профиля/выходе.
  self._right_sticking = False
  self._middle_sticking = False
  # (2026-11-16) Явный toggle-режим галочки «Держать нажатой».
  # галочка ВКЛЮЧЕНА  → первое нажатие+отпускание ФИКСИРУЕТ эмулируемую
  #                     кнопку/клавишу, следующее нажатие+отпускание снимает.
  # галочка ВЫКЛЮЧЕНА → эмуляция живёт ТОЛЬКО пока физическая кнопка нажата.
  # _toggled_slots — источник истины «сейчас зафиксировано»; _toggle_gen
  # защищает от устаревших таймеров duration (снимаем фиксацию только для той
  # генерации, которая её установила).
  self._toggled_slots = set()
  self._toggle_gen = {}
  self._toggle_lock = threading.RLock()
  self.bindings = {}
  self.virtual_by_physical_button = {}
  # Алиасы нативных имён, добавленные register_physical_fallbacks (режим
  # деградации без ремапа). При успешном ремапе они чистятся: нативные
  # имена становятся только эхом собственной эмуляции (см. prepare()).
  self._fallback_aliases = []
  # Нативные алиасы для клавиатурных назначений, добавленные в _build_bindings
  # (чтобы ловить нажатия, если ремап не сработал/XTEST). При УСПЕШНОМ ремапе
  # их нужно убрать: иначе чужие/синтетические события по физическому имени
  # (например, xdotool/UInput клик правой кнопки из другого слота) попадают
  # в биндинг и сбивают удерживаемую эмуляцию (напр. ПКМ->W отпускается).
  self._keyboard_fallback_aliases = []
  self.stop_requested = threading.Event()
  self._build_bindings()

 def _slot_intercepted(self, slot, pass_through):
  # Кнопка перехватывается, если назначение НЕ дефолтное ИЛИ если к слоту
  # привязан bash-скрипт (script_mouse). Раньше скрипт на кнопке, оставленной
  # по умолчанию (XBUTTON1/XBUTTON2), был недостижим: binding не создавался
  # и макрос никогда не выполнялся. Теперь слот со скриптом перехватывается.
  if self.assignments[slot] not in pass_through:
   return True
  return bool(self._mouse_script(slot).strip())

 def _build_bindings(self):
  for slot, physical, virtual, listener_button, pass_through in self.INTERCEPTION_RULES:
   if not self._slot_intercepted(slot, pass_through):
    continue
   worker = Job(self.assignments[slot])
   worker.start()
   worker.pause()
   # В Linux боковые кнопки могут приходить под разными именами.
   listener_names = {listener_button}
   if slot == 5:
    listener_names.update({'Button.x1', 'Button.button9', 'Button.button16'})
   elif slot == 6:
    listener_names.update({'Button.x2', 'Button.button8', 'Button.button15'})
   for listener_name in listener_names:
    self.bindings[listener_name] = MouseBinding(listener_name, slot, worker)
   # (Исправление 2026-11-13, §37): pynput 1.8.1 слушает XRecord
   # (device_events), и какое имя кнопки придёт, зависит от устройства и
   # от того, применился ли xinput-remap:
   #  * реальная мышь при УСПЕШНОМ ремапе → ЛОГИЧЕСКИЕ имена
   #    (правая = Button.button11, колесо = Button.button13/14);
   #  * XTEST (xdotool) идёт через отдельное устройство с identity-картой
   #    → ФИЗИЧЕСКИЕ имена (Button.right и т.п.);
   #  * если ремап НЕ применился (нет доступа к X, сменился id) → тоже
   #    ФИЗИЧЕСКИЕ имена.
   # Раньше при успешном ремапе физические алиасы удалялись, поэтому любое
   # событие с физическим именем (XTEST-эмуляция, сбой ремапа) не
   # перехватывалось — правая кнопка не давала W. Теперь для
   # назначений-клавиш слушаем ОБА набора имён (эхо здесь невозможно:
   # эмулируются только клавиши, а не кнопки мыши). Для мышиных действий
   # (MOUSE_ACTIONS) оставляем прежнюю схему, чтобы не поймать эхо
   # собственной UInput-эмуляции кнопок.
   if self.assignments[slot] not in self.MOUSE_ACTIONS:
    for name in self.PHYSICAL_FALLBACK.get(slot, ()):
     if name not in self.bindings:
      self.bindings[name] = MouseBinding(name, slot, worker)
      self._keyboard_fallback_aliases.append(name)
   self.virtual_by_physical_button[physical] = virtual

 def register_physical_fallbacks(self):
  # Fallback на случай, когда xinput set-button-map НЕ применил карту (нет
  # доступа к X / неверный id устройства / «device has no buttons»). Тогда
  # физические кнопки сохраняют нативные номера и не подпадают под
  # виртуальные имена (Button.button11 и т.д.), поэтому слушатель их просто
  # не видит и назначенные клавиши не срабатывают. Регистрируем алиасы по
  # нативным именам (PHYSICAL_FALLBACK) для тех слотов, для которых уже
  # создан worker. При УСПЕШНОМ ремапе этот метод НЕ вызывается: кнопки
  # приходят под виртуальными номерами, а нативные имена могли бы прийти как
  # эхо нашей эмуляции (XTEST/UInput) и дать ложные срабатывания.
  for slot, physical, virtual, listener_button, pass_through in self.INTERCEPTION_RULES:
   if not self._slot_intercepted(slot, pass_through):
    continue
   worker = None
   for b in self.bindings.values():
    if b.slot == slot:
     worker = b.worker
     break
   if worker is None:
    continue
   for name in self.PHYSICAL_FALLBACK.get(slot, ()):
    if name not in self.bindings:
     self.bindings[name] = MouseBinding(name, slot, worker)
     self._fallback_aliases.append(name)  # чтобы prepare() мог почистить после успешного ремапа

 def apply_button_map(self):
  default_map = self.store.get_default_id_value(self.device_id).split()
  remapped_map = list(default_map)
  for index, button in enumerate(remapped_map):
   try:
    physical_button = int(button)
   except (TypeError, ValueError):
    continue
   virtual_button = self.virtual_by_physical_button.get(physical_button)
   if virtual_button is not None:
    remapped_map[index] = virtual_button

  # (Новый подход, исправление 2026-11-09: атомарное применение без
  # «окна нативности»). Раньше здесь сначала шёл reset_id_value (сброс
  # карты в нативную 1 2 3 4 5 6 7 8 9), а ПОТОМ — remap. Сброс в
  # нативное состояние означал, что боковая кнопка в этот момент — X11
  # 8/9 = «Назад/Вперёд» в браузере; если remap после сброса не
  # применялся (X занят, устаревший id, «device has no buttons», sudo),
  # устройство ОСТАВАЛОСЬ в нативной карте — боковая кнопка «делала
  # назад», а не прокрутку из профиля. Теперь целевая карта (чистая
  # заводская + виртуальные номера профиля, полная) применяется ОДНИМ
  # set-button-map с ретраями: нет промежуточного нативного состояния,
  # и при сбое устройство остаётся в прежней карте (клавиши продолжают
  # работать через physical-fallback, а не «залипают» в «назад»).
  target_map = ' '.join(remapped_map)
  error_text = ''
  applied = False
  for attempt in range(3):
   for use_sudo in (False, True):
    command = (['sudo'] if use_sudo else []) + ['xinput', 'set-button-map', str(self.device_id), *remapped_map]
    try:
     result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    except Exception as exc:
     error_text = str(exc)
     continue
    if result.returncode != 0:
     error_text = (result.stderr or result.stdout or '').strip()
     continue
    # Проверяем фактическое состояние карты: X может вернуть успех, но не применить
    try:
     check = subprocess.run(['xinput', 'get-button-map', str(self.device_id)], capture_output=True, text=True, timeout=5)
     if check.returncode == 0 and check.stdout.split() == [str(b) for b in remapped_map]:
      applied = True
    except Exception as exc:
     error_text = str(exc)
    if applied:
     break
   if applied:
    break
   time.sleep(0.3)  # X временно недоступен/занят — подождём и повторим.
  if not applied:
   message = 'xinput set-button-map failed for id=%s map=%s: %s' % (self.device_id, target_map, error_text)
   try:
    self.store.write_in_log(message)
   except Exception:
    pass

  return applied
 def handle_listener_event(self, button, pressed):
  """Принять событие pynput и передать в очередь нужной привязки (без
  блокировки callback'а слушателя), чтобы разные кнопки обрабатывались
  параллельно и можно было удерживать/нажимать несколько одновременно."""
  if self.stop_requested.is_set():
   return
  binding = self.bindings.get(str(button))
  if binding is None or not binding.worker.get_hook_flag_mouse():
   return
  try:
   binding.enqueue(self, pressed)
  except Exception:
   # Фолбэк: синхронная обработка, если очередь недоступна.
   try:
    self._dispatch_binding(binding, pressed)
   except Exception:
    pass

 def join_event_workers(self):
  # Дождаться обработки уже поставленных в очередь событий кнопок.
  seen = set()
  for binding in list(getattr(self, 'bindings', {}).values()):
   w = getattr(binding, '_dispatch_thread', None)
   if w is None:
    continue
   wid = id(w)
   if wid in seen:
    continue
   seen.add(wid)
   try:
    # Даём время на завершение текущего (в т.ч. скрипта), но не зависаем.
    binding.join_dispatch(timeout=2.0)
   except Exception:
    pass

 def stop_workers(self):
  for binding in list(getattr(self, 'bindings', {}).values()):
   try:
    binding.worker.stop()
   except Exception:
    pass
   try:
    if hasattr(binding, 'stop_dispatch'):
     binding.stop_dispatch()
   except Exception:
    pass

 def stop(self):
  self.stop_requested.set()
  try:
   self._watch_stop.set()
  except Exception:
   pass
  self.stop_workers()
  self.join_event_workers()
  self._release_all_emulated_inputs()

 def _release_all_emulated_inputs(self):
  """Best-effort release of any inputs this runtime may have left pressed.

  On profile switch / game exit / app close we must not leave synthetic key
  downs or mouse holds behind, otherwise buttons appear "stuck" and the mouse
  glitches in other apps. Releases are idempotent/safe to repeat."""
  try:
   with self._timed_holds_lock:
    self._timed_holds.clear()
  except Exception:
   pass
  # (2026-11-16) Снимаем ВСЕ toggle-фиксации при смене профиля/выходе/стопе:
  # иначе после возврата в профиль галочка «Держать» думала бы, что кнопка
  # ещё зафиксирована, и первое же нажатие сняло бы несуществующую фиксацию.
  try:
   with self._toggle_lock:
    self._toggled_slots.clear()
    for _s in list(self._toggle_gen):
     self._toggle_gen[_s] = self._toggle_gen[_s] + 1
  except Exception:
   pass
  # Release keyboard keys assigned to intercepted slots (covers held/toggled
  # states that have no explicit release event during runtime teardown).
  for binding in list(getattr(self, 'bindings', {}).values()):
   try:
    slot = binding.slot
    action = self.assignments[slot]
    if action in self.MOUSE_ACTIONS or str(binding.worker.key).startswith('SCROLL_'):
     continue
    key_value = str(KEYS.get(action, ''))
    if key_value:
     key_work.key_release(key_value, slot)
   except Exception:
    pass
  # Дополнительно отпускаем ВСЕ клавиши, которые SmartTyper считает зажатыми
  # (включая те, что могли остаться из-за гонок key_down/key_up), чтобы при
  # выходе из игры/смене профиля не оставались «залипшие» клавиши.
  try:
   _pc = getattr(smart_typer, '_pressed_codes', {})
   _pressed = list(_pc.keys()) if isinstance(_pc, dict) else list(_pc)
   for code in _pressed:
    if isinstance(code, tuple) and len(code) == 2 and code[0] == 'char':
     try:
      subprocess.run(['xdotool', 'keyup', '--clearmodifiers', code[1]],
       capture_output=True, timeout=2)
     except Exception:
      pass
    else:
     try:
      with smart_typer._kb_lock:
       if smart_typer._ui is not None:
        smart_typer._ui.write(ecodes.EV_KEY, code, 0)
        smart_typer._ui.syn()
     except Exception:
      pass
   with smart_typer._kb_lock:
    smart_typer._pressed_codes.clear()
  except Exception:
   pass
  # Release emulated mouse buttons (sticky/toggle/pulses) as a safety net.
  self._release_sticky_buttons(force=True)
  for x11b in (1, 2, 3):
   try:
    key_work.mouse_button_release(x11b)
   except Exception:
    pass
  # Дополнительно сбрасываем локальное состояние зажатых кнопок виртуального
  # указателя (SmartTyper), чтобы при смене профиля/выходе не оставались
  # «залипшие» BTN_LEFT/MIDDLE/RIGHT (ref-count обнуляется принудительно).
  try:
   _pmb = getattr(smart_typer, '_pressed_mouse_buttons', {})
   _codes = list(_pmb.keys()) if isinstance(_pmb, dict) else list(_pmb)
   for code in _codes:
    try:
     with smart_typer._ptr_lock:
      if smart_typer._ui_scroll is not None:
       smart_typer._ui_scroll.write(ecodes.EV_KEY, code, 0)
       smart_typer._ui_scroll.syn()
    except Exception:
     pass
   with smart_typer._ptr_lock:
    if isinstance(_pmb, dict):
     _pmb.clear()
    else:
     _pmb.clear()
  except Exception:
   pass

 def _release_sticky_buttons(self, force=False):
  # При выходе из игры / смене профиля / выходе из приложения отпускаем
  # залипшие правую/среднюю кнопки: иначе синтетический X-press (XTEST)
  # остаётся «зависшим» в X-сервере, и физическая правая кнопка
  # залипает/перестаёт работать во ВСЕХ приложениях. Циклы «Повторить»
  # (_repeat_*_loop) отключаются тем же stop_requested: они завершаются
  # сами и отпускают клавишу/кнопку в finally. Таймеры _release_sticky_after
  # и _pause_worker_after видят stop_requested и больше ничего не делают.
  #
  # ВАЖНО (исправление 2026-11-15, §40.4): force=False отпускает ТОЛЬКО
  # кнопки, реально зажатые в toggle-режиме (sticky-состояния True). Это
  # НЕ сбрасывает toggle-состояние при физическом отпускании — toggle
  # управляется повторным нажатием / таймером duration / stop(). force=True
  # (стоп рантайма, смена профиля, выход) всегда снимает все удержания.
  if self._right_sticking or force:
   self._right_sticking = False
   try:
    key_work.mouse_button_release(3)  # UInput + сброс legacy-XTEST залипания
   except Exception:
    pass
  if self._middle_sticking or force:
   self._middle_sticking = False
   try:
    key_work.mouse_button_release(2)
   except Exception:
    pass

 def _is_toggle_slot(self, slot):
  """True, если слот работает в режиме TOGGLE (галочка «Держать нажатой»).

  В этом режиме эмуляция фиксируется первым нажатием+отпусканием и снимается
  только следующим нажатием+отпусканием (или сменой профиля/выходом). Поэтому
  исключаем такой слот из сторожевого надзора: watchdog проверяет РЕАЛЬНОЕ
  состояние физической кнопки и снял бы «законное» toggle-удержание сразу
  после физического отпускания."""
  try:
   if not self.hold_flags[slot]:
    return False
   if self.repeat_flags[slot]:
    return False  # «Повторить» имеет приоритет и останавливается отпусканием
   action = self.assignments[slot]
   if action in self.MOUSE_ACTIONS:
    return action in ('RBUTTON', 'WHEEL_MOUSE_BUTTON')
   if action in ('XBUTTON1', 'XBUTTON2', ' '):
    return False
   return True  # клавиатурное назначение с галочкой «Держать»
  except Exception:
   return False

 def dispatch(self, button, pressed):
  if self.stop_requested.is_set():
   return
  binding = self.bindings.get(str(button))
  if binding is None or not binding.worker.get_hook_flag_mouse():
   return
  self._dispatch_binding(binding, pressed)

 def _dispatch_binding(self, binding, pressed):
  if self.stop_requested.is_set():
   return
  action = self.assignments[binding.slot]
  # (2026-11-16) Отслеживаем реальное нажатие по слоту и держим включённым
  # сторожевой поток: он независимо от событий listener проверяет физическое
  # состояние кнопки и снимает эмуляцию, если отпускание потерялось.
  try:
   with self._slot_pressed_lock:
    if pressed:
     self._slot_pressed[binding.slot] = True
     # Toggle (галочка «Держать нажатой») живёт и после физического
     # отпускания — watchdog не должен его снимать (см. _is_toggle_slot).
     if not self._is_toggle_slot(binding.slot):
      self._watch_slots.add(binding.slot)
    else:
     self._slot_pressed[binding.slot] = False
     self._watch_slots.discard(binding.slot)
   if pressed:
    self._ensure_watchdog()
  except Exception:
   pass
  try:
  # Скрипт не заменяет назначение, а выполняется перед ним.
   script = self._mouse_script(binding.slot)
   if action in self.MOUSE_ACTIONS:
    self._handle_mouse_action(binding, pressed, script=script)
   elif action in ('XBUTTON1', 'XBUTTON2') or action == ' ':
    # Боковая кнопка, оставленная «как есть» (XBUTTON1/XBUTTON2) или с
    # назначением «ничего», но с привязанным скриптом: выполняется только
    # скрипт (без клавиши и без нативного клика). Скрипт без назначения
    # кнопки здесь просто не запускается — кнопка остаётся нативной.
    self._handle_side_button_script(binding, pressed, script=script)
   else:
    self._handle_keyboard_action(binding, pressed, script=script)
  except Exception as exc:
   self.store.write_in_log(exc)

 def _mouse_script(self, slot):
  current_game = self.game  # Активный профиль рантайма, а не current_app из UI.
  button_name = defaut_list_mouse_buttons[slot]
  return self.store.return_jnson().get('script_mouse', {}).get(current_game, {}).get(button_name, '')

 def _slot_duration(self, slot):
  # Числовая длительность повтора/удержания для слота (None, если не выбрана
  # или вышла за допустимый диапазон allowed_repeat_durations).
  duration = self.hold_durations[slot] if slot < len(self.hold_durations) else None
  try:
   duration = int(duration) if duration not in (None, '', 0, '0') else None
  except (TypeError, ValueError):
   duration = None
  return duration if duration in allowed_repeat_durations else None

 def _handle_mouse_action(self, binding, pressed, script=None):
  slot = binding.slot
  action = self.assignments[slot]

  # DEBUG: логирование для диагностики (2026-11-15)
  hold = self.hold_flags[slot]
  # (2026-11-16) Боковые кнопки (слоты 5/6) БЕЗ галочки теперь тоже работают
  # как «удержание пока нажата»: зажал — зажата эмулируемая, отпустил —
  # отпущена. Короткое нажатие даёт обычный клик. С галочкой — toggle
  # (фиксация до следующего нажатия). Отдельного принудительного hold для
  # слотов 5/6 больше нет: поведение целиком определяется галочкой.
  duration = self._slot_duration(slot)
  repeat = bool(self.repeat_flags[slot])
  try:
   _st = '_R' if self._right_sticking else ''
   _st += '_M' if self._middle_sticking else ''
   _tg = 'T' if slot in self._toggled_slots else '-'
   dict_save.write_in_log('[DEBUG] mouse_action slot=%s action=%r pressed=%s hold=%s dur=%s repeat=%s sticky=%s toggle=%s' % (slot, action, pressed, hold, duration, repeat, _st, _tg))
  except Exception:
   pass
  # «Повторить» для действий мыши. ВАЖНО (2026-11-16): отпускание физической
  # кнопки ОСТАНАВЛИВАЕТ повтор — раньше цикл продолжался «бесконечно» до
  # повторного нажатия, из-за чего одно нажатие ПКМ давало вечное движение.
  if repeat:
   if not pressed:
    self._stop_slot_emulation(binding)
    return
   # Прокрутка: непрерывно, пока кнопка нажата (или до истечения срока).
   if action in {'SCROLL_UP', 'SCROLL_DOWN'}:
    binding.worker.set_sw(True)
    binding.worker.resume()
    if duration is not None:
     threading.Thread(target=self._pause_worker_after, args=(binding.worker, duration), daemon=True).start()
    return
   if action in ('RBUTTON', 'WHEEL_MOUSE_BUTTON'):
    target_button = mouse.Button.right if action == 'RBUTTON' else mouse.Button.middle
    with self._timed_holds_lock:
     already = bool(self._timed_holds.get(slot, False))
     self._timed_holds[slot] = True
    if not already:
     threading.Thread(
      target=self._repeat_mouse_loop,
      args=(slot, target_button, script, duration),
      daemon=True,
      ).start()
    return
   # Клавиатурное назначение с «Повторить» обрабатывается в
   # _handle_keyboard_action (сюда попадают только действия мыши).
   self._execute_bound_script(script) if script else None
   return

  if pressed and script:
   self._execute_bound_script(script)

  # Прокрутка: нажата — крутим, отпущена — стоп.
  if action in {'SCROLL_UP', 'SCROLL_DOWN'}:
   if pressed:
    binding.worker.set_sw(True)
    binding.worker.resume()
    if duration is not None:
     threading.Thread(target=self._pause_worker_after, args=(binding.worker, duration), daemon=True).start()
   else:
    binding.worker.set_sw(False)
    binding.worker.pause()
   return

  if not pressed:
   # Кнопка отпущена: снимаем удержание/залипание и останавливаем таймеры.
   # (2026-11-16) ИСКЛЮЧЕНИЕ — toggle-режим галочки «Держать нажатой»:
   # физическое отпускание НЕ снимает фиксацию (снимает только следующее
   # нажатие, таймер duration или смена профиля).
   if not self._is_toggle_slot(slot):
    self._stop_slot_emulation(binding)
   return

  if action in ('RBUTTON', 'WHEEL_MOUSE_BUTTON'):
   x11_button = 3 if action == 'RBUTTON' else 2
   if hold:
    # === ГАЛОЧКА «Держать нажатой» ВКЛЮЧЕНА → TOGGLE ===
    # Первое нажатие+отпускание ФИКСИРУЕТ эмулируемую кнопку, второе
    # нажатие+отпускание снимает фиксацию. Физическое ОТПУСКАНИЕ игнорируется:
    # эмуляция живёт до следующего нажатия (или смены профиля/выхода).
    if not pressed:
     return
    toggle_off = False
    with self._toggle_lock:
     if slot in self._toggled_slots:
      self._toggled_slots.discard(slot)
      self._toggle_gen[slot] = self._toggle_gen.get(slot, 0) + 1
      toggle_off = True
     else:
      self._toggled_slots.add(slot)
      gen = self._toggle_gen.get(slot, 0) + 1
      self._toggle_gen[slot] = gen
    # Toggle не состоит под надзором watchdog (иначе он снял бы законную
    # фиксацию сразу после физического отпускания).
    with self._slot_pressed_lock:
     self._watch_slots.discard(slot)
    if toggle_off:
     with self._timed_holds_lock:
      self._timed_holds[slot] = False
     try:
      key_work.mouse_button_release(x11_button)
     except Exception:
      pass
     self._set_sticky(action, False)
     try:
      self.store.write_in_log('[toggle] slot %s %s: фиксация СНЯТА (второе нажатие)' % (slot, action))
     except Exception:
      pass
     return
    with self._timed_holds_lock:
     self._timed_holds[slot] = True
    try:
     key_work.mouse_button_press(x11_button)
    except Exception:
     pass
    self._set_sticky(action, True)
    try:
     self.store.write_in_log('[toggle] slot %s %s: фиксация ВКЛЮЧЕНА (первое нажатие)' % (slot, action))
    except Exception:
     pass
    if duration is not None:
     threading.Thread(target=self._release_toggled_mouse_after,
      args=(slot, action, x11_button, duration, gen), daemon=True).start()
    return
   # === ГАЛОЧКА ВЫКЛЮЧЕНА → удержание ТОЛЬКО пока нажата физическая кнопка ===
   # (включая боковые кнопки 5/6: короткий клик = обычный клик ПКМ/СКМ,
   #  зажатие боковой = зажата эмулируемая кнопка).
   if not pressed:
    self._stop_slot_emulation(binding)
    return
   with self._timed_holds_lock:
    self._timed_holds[slot] = True
   try:
    key_work.mouse_button_press(x11_button)
   except Exception:
    pass
   self._set_sticky(action, True)
   if duration is not None:
    threading.Thread(target=self._release_sticky_after, args=(action, duration), daemon=True).start()
   return

  # Прочие действия мыши (MBUTTON/LBUTTON и т.п.) — одиночный клик.
  if action == 'LBUTTON':
   key_work.mouse_button_press(1)
   key_work.mouse_button_release(1)

 def _stop_slot_emulation(self, binding):
  """Полностью снять эмуляцию слота: остановить повтор, отпустить удержания.

  Вызывается при отпускании физической кнопки (а также при потере фокуса/
  остановке рантайма) — гарантия, что «одно нажатие» никогда не превращается
  в бесконечную эмуляцию."""
  slot = binding.slot
  with self._slot_pressed_lock:
   self._slot_pressed[slot] = False
   self._watch_slots.discard(slot)
  # (2026-11-16) Любая полная остановка слота снимает и toggle-фиксацию.
  try:
   with self._toggle_lock:
    self._toggled_slots.discard(slot)
    self._toggle_gen[slot] = self._toggle_gen.get(slot, 0) + 1
  except Exception:
   pass
  try:
   with self._timed_holds_lock:
    self._timed_holds[slot] = False
  except Exception:
   pass
  try:
   binding.worker.set_sw(False)
   binding.worker.pause()
  except Exception:
   pass
  action = self.assignments[slot]
  if action in ('RBUTTON', 'WHEEL_MOUSE_BUTTON'):
   x11_button = 3 if action == 'RBUTTON' else 2
   try:
    key_work.mouse_button_release(x11_button)
   except Exception:
    pass
   self._set_sticky(action, False)
  elif action == 'LBUTTON':
   try:
    key_work.mouse_button_release(1)
   except Exception:
    pass
  elif action not in self.MOUSE_ACTIONS:
   # Клавиатурное назначение: отпустить клавишу (идемпотентно).
   try:
    key_work.key_release(str(KEYS.get(action, '')), slot)
   except Exception:
    pass

 def _handle_side_button_script(self, binding, pressed, script=None):
  # Боковая кнопка, оставленная «как есть» (XBUTTON1/XBUTTON2) или с
  # назначением «ничего», но с привязанным bash-скриптом. До фикса такой
  # слот не перехватывался (pass-through) и скрипт никогда не выполнялся.
  # Теперь выполняется ТОЛЬКО скрипт: без отправки клавиши (XBUTTON* —
  # не ключи) и без нативного клика (кнопка уже перехвачена xinput-ремапом).
  # «Повторить» повторяет только скрипт (на срок; без срока — пока кнопка нажата).
  if not script:
   return
  slot = binding.slot
  if self.repeat_flags[slot]:
   if not pressed:
    # Отпускание кнопки останавливает повтор скрипта (2026-11-16): раньше
    # цикл шёл «бесконечно» до повторного нажатия.
    self._stop_slot_emulation(binding)
    return
   with self._timed_holds_lock:
    already = bool(self._timed_holds.get(slot, False))
    self._timed_holds[slot] = True
   if not already:
    # Цикл _repeat_mouse_loop со скриптом шлёт ТОЛЬКО скрипт
    # (target_button не используется и отпускание не нужно).
    threading.Thread(target=self._repeat_mouse_loop, args=(slot, None, script, self._slot_duration(slot)), daemon=True).start()
   return
  if pressed:
   self._execute_bound_script(script)

 def _pause_worker_after(self, worker, duration):
  time.sleep(duration)
  if not self.stop_requested.is_set():
   worker.pause()
   worker.set_sw(False)

 def _set_sticky(self, action, value):
  # Залипание правой/средней кнопки — состояние рантайма (не глобальное).
  if action == 'RBUTTON':
   self._right_sticking = value
  elif action == 'WHEEL_MOUSE_BUTTON':
   self._middle_sticking = value

 def _physical_button_state(self):
  """Реальное состояние кнопок мыши по данным X: {X11-номер: bool}.

  Нужно как независимая проверка «кнопка ещё нажата?» — используется
  сторожевым потоком, чтобы гарантированно завершить эмуляцию, даже если
  событие отпускания потерялось (XRecord/remap/ошибка X-канала)."""
  try:
   result = subprocess.run(['xinput', 'query-state', str(self.device_id)],
    capture_output=True, text=True, timeout=2)
  except Exception:
   return None
  if result.returncode != 0 or not result.stdout:
   return None
  state = {}
  for m in re.finditer(r'button\[(\d+)\]=(\w+)', result.stdout):
   try:
    state[int(m.group(1))] = (m.group(2).lower() == 'down')
   except ValueError:
    continue
  return state or None

 def _ensure_watchdog(self):
  """Запустить сторожевой поток (если ещё не запущен)."""
  if self._watch_thread is not None and self._watch_thread.is_alive():
   return
  self._watch_stop.clear()
  self._watch_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
  self._watch_thread.start()

 def _watchdog_loop(self):
  """Сторож: если физическая кнопка уже НЕ нажата, а эмуляция ещё активна —
  принудительно завершить её. Это страховка от потерянного события отпускания
  (из-за remap, XRecord, ошибки X): «одно нажатие» никогда не превращается в
  бесконечное движение (исправление 2026-11-16).

  ВАЖНО: слот «вооружается» только после того, как состояние «нажата» реально
  наблюдалось. Это исключает ложное снятие эмуляции для колёсика (его кнопка
  в X фиксируется мгновенно и может не попасть в выборку)."""
  slot_to_physical = {}
  for slot, physical, virtual, listener_button, pass_through in self.INTERCEPTION_RULES:
   slot_to_physical[slot] = physical
  armed = set()
  # (2026-11-16) Счётчик подряд идущих «up»: одна выборка «не нажата» не
  # должна снимать законное удержание (X может ответить в момент, когда
  # состояние кнопки ещё не обновилось). Снимаем только после 2 подряд.
  up_streak = {}
  while not self._watch_stop.is_set() and not self.stop_requested.is_set():
   with self._slot_pressed_lock:
    watched = set(self._watch_slots)
   if not watched:
    armed.clear()
    up_streak.clear()
    # Нечего сторожить: ждём появления работы, не жгём CPU.
    self._watch_stop.wait(0.25)
    continue
   state = self._physical_button_state()
   if state is not None:
    for slot in list(watched):
     physical = slot_to_physical.get(slot)
     if physical is None:
      continue
     virtual = self.virtual_by_physical_button.get(physical)
     try:
      virt_num = int(virtual) if virtual is not None else None
     except (TypeError, ValueError):
      virt_num = None
     # X может показать кнопку либо под физическим, либо под виртуальным номером.
     down = bool(state.get(physical, False))
     if not down and virt_num is not None:
      down = bool(state.get(virt_num, False))
     if down:
      armed.add(slot)  # кнопка реально нажата — эмуляция законна
      up_streak.pop(slot, None)
      continue
     if slot not in armed:
      continue  # ещё ни разу не видели нажатия (напр. колёсико) — не трогаем
     # Если кнопки вообще нет в ответе устройства — номер/устройство не то,
     # «up» не подтверждён. Не снимаем эмуляцию по отсутствию данных.
     if physical not in state and (virt_num is None or virt_num not in state):
      continue
     up_streak[slot] = up_streak.get(slot, 0) + 1
     if up_streak[slot] < 2:
      continue
     # Кнопка была нажата и уже отпущена (2 выборки подряд), а эмуляция
     # ещё висит — снимаем.
     binding = self._binding_for_slot(slot)
     armed.discard(slot)
     up_streak.pop(slot, None)
     if binding is None:
      with self._slot_pressed_lock:
       self._watch_slots.discard(slot)
      continue
     self.store.write_in_log('[watchdog] slot %s: физическая кнопка отпущена — принудительное завершение эмуляции' % slot)
     try:
      self._stop_slot_emulation(binding)
     except Exception:
      pass
   self._watch_stop.wait(0.25)

 def _binding_for_slot(self, slot):
  for binding in list(getattr(self, 'bindings', {}).values()):
   if binding.slot == slot:
    return binding
  return None

 def _release_sticky_after(self, action, duration):
  # Автоснятие залипания по таймеру (режим «держать» + длительность).
  # Отпускание идёт ВСЕГДА (даже если runtime уже останавливается): release
  # идемпотентен, а пропущенный X-press — это залипшая во всех приложениях
  # правая/средняя кнопка.
  # (Исправление 2026-11-15, §40.4): таймер отпускает ТОЛЬКО физическую
  # кнопку мыши (UInput/XTEST), но НЕ сбрасывает toggle-флаг
  # _right/_middle_sticking. Toggle остаётся активным: повторное нажатие
  # кнопки мыши снова зажимает её (как и в режиме без длительности).
  time.sleep(duration)
  if action == 'RBUTTON':
   key_work.mouse_button_release(3)
  elif action == 'WHEEL_MOUSE_BUTTON':
   key_work.mouse_button_release(2)

 def _release_toggled_mouse_after(self, slot, action, x11_button, duration, gen):
  """Снять toggle-фиксацию мыши по сроку duration, но ТОЛЬКО свою генерацию.

  Если пользователь успел нажать кнопку снова (или профиль сменился) —
  генерация изменилась, и устаревший таймер ничего не трогает."""
  time.sleep(duration)
  if self.stop_requested.is_set():
   return
  with self._toggle_lock:
   if self._toggle_gen.get(slot) != gen or slot not in self._toggled_slots:
    return
   self._toggled_slots.discard(slot)
   self._toggle_gen[slot] = gen + 1
  with self._timed_holds_lock:
   self._timed_holds[slot] = False
  with self._slot_pressed_lock:
   self._watch_slots.discard(slot)
  try:
   key_work.mouse_button_release(x11_button)
  except Exception:
   pass
  self._set_sticky(action, False)

 def _release_toggled_key_after(self, slot, key_value, duration, gen):
  """Снять toggle-фиксацию клавиши по сроку duration (своя генерация)."""
  time.sleep(duration)
  if self.stop_requested.is_set():
   return
  with self._toggle_lock:
   if self._toggle_gen.get(slot) != gen or slot not in self._toggled_slots:
    return
   self._toggled_slots.discard(slot)
   self._toggle_gen[slot] = gen + 1
  with self._timed_holds_lock:
   self._timed_holds[slot] = False
  with self._slot_pressed_lock:
   self._watch_slots.discard(slot)
  try:
   key_work.key_release(key_value, slot)
  except Exception:
   pass

 def _handle_keyboard_action(self, binding, pressed, script=None):
  slot = binding.slot
  key_value = str(KEYS[self.assignments[slot]])
  duration = self._slot_duration(slot)
  # «Повторить» — одно нажатие запускает цикл (на выбранный срок; без срока —
  # пока физическая кнопка нажата). Если на слот привязан скрипт — повторяется
  # ТОЛЬКО скрипт, а не клавиша. (2026-11-16) Отпускание физической кнопки
  # ОСТАНАВЛИВАЕТ цикл — раньше он шёл «бесконечно» до повторного нажатия.
  repeat_mode = bool(self.repeat_flags[slot])
  if script and pressed and not repeat_mode:
  # Для одиночного действия Bash завершается до key-down.
   self._execute_bound_script(script)
  # (2026-11-16) ГАЛОЧКА «Держать нажатой» → TOGGLE: физическое отпускание
  # НЕ снимает фиксацию (как и для кнопок мыши). Без галочки / с «Повторить»
  # эмуляция живёт ТОЛЬКО пока физическая кнопка нажата.
  if not pressed:
   if self._is_toggle_slot(slot):
    return
   with self._timed_holds_lock:
    self._timed_holds[slot] = False
   try:
    binding.worker.set_sw(False)
   except Exception:
    pass
   key_work.key_release(key_value, slot)
   return

  if repeat_mode:
   with self._timed_holds_lock:
    already = bool(self._timed_holds.get(slot, False))
    if not already:
     self._timed_holds[slot] = True
   if not already:
    threading.Thread(
     target=self._repeat_key_loop,
     args=(slot, key_value, script, duration),
     daemon=True,
     ).start()
   return

  if not self.hold_flags[slot]:
   # БЕЗ галочки — клавиша зажата, пока зажата физическая кнопка.
   with self._timed_holds_lock:
    self._timed_holds[slot] = True
   binding.worker.set_sw(True)
   key_work.key_press(key_value, slot)
   return

  # ГАЛОЧКА ВКЛЮЧЕНА → TOGGLE: первое нажатие фиксирует клавишу, второе
  # нажатие снимает фиксацию (физическое отпускание при этом игнорируется).
  toggle_off = False
  with self._toggle_lock:
   if slot in self._toggled_slots:
    self._toggled_slots.discard(slot)
    self._toggle_gen[slot] = self._toggle_gen.get(slot, 0) + 1
    toggle_off = True
   else:
    self._toggled_slots.add(slot)
    gen = self._toggle_gen.get(slot, 0) + 1
    self._toggle_gen[slot] = gen
  with self._slot_pressed_lock:
   self._watch_slots.discard(slot)
  if toggle_off:
   with self._timed_holds_lock:
    self._timed_holds[slot] = False
   try:
    binding.worker.set_sw(False)
   except Exception:
    pass
   key_work.key_release(key_value, slot)
   try:
    self.store.write_in_log('[toggle] slot %s key=%s: фиксация СНЯТА (второе нажатие)' % (slot, key_value))
   except Exception:
    pass
   return
  with self._timed_holds_lock:
   self._timed_holds[slot] = True
  binding.worker.set_sw(True)
  key_work.key_press(key_value, slot)
  try:
   self.store.write_in_log('[toggle] slot %s key=%s: фиксация ВКЛЮЧЕНА (первое нажатие)' % (slot, key_value))
  except Exception:
   pass
  if duration is not None:
   threading.Thread(target=self._release_toggled_key_after,
    args=(slot, key_value, duration, gen), daemon=True).start()

 def _execute_bound_script(self, script):
 # Выполняем Bash синхронно, чтобы следующая клавиша шла после него.
  try:
   execute_script(script)
  except Exception as exc:
   self.store.write_in_log(exc)

 def _repeat_key_loop(self, slot, key_value, script=None, total_duration=None):
  """Repeat pulses for the selected duration, or until toggled off. If a script
     is bound to the slot — repeat ONLY the script, not the key."""
  deadline = time.monotonic() + total_duration if total_duration is not None else None
  try:
   while not self.stop_requested.is_set() and (deadline is None or time.monotonic() < deadline):
    with self._timed_holds_lock:
     if not self._timed_holds.get(slot, False):
      break
    if script:
     self._execute_bound_script(script)
     time.sleep(0.05)
    else:
     key_work.key_press(key_value, slot)
     time.sleep(0.05)
     key_work.key_release(key_value, slot)
     time.sleep(0.05)
  finally:
   with self._timed_holds_lock:
    self._timed_holds[slot] = False
   if not script:
    key_work.key_release(key_value, slot)

 def _repeat_mouse_loop(self, slot, target_button, script=None, total_duration=None):
  """Repeat mouse pulses for the selected duration, or until toggled off. If a
     script is bound to the slot — repeat ONLY the script, not the mouse button."""
  deadline = time.monotonic() + total_duration if total_duration is not None else None
  capped = False
  if deadline is None:
   # Страховка: «повтор без длительности» идёт до повторного нажатия (toggle).
   # Если второе нажатие/отпускание потеряно (реселект устройства, ошибка
   # X-канала), цикл без потолка крутится вечно и жжёт ядро. Потолок — 300 с.
   deadline = time.monotonic() + 300
   capped = True
  x11_button = _X11_BY_PYNPUT_BUTTON.get(target_button) if target_button is not None else None
  try:
   while not self.stop_requested.is_set() and (deadline is None or time.monotonic() < deadline):
    with self._timed_holds_lock:
     if not self._timed_holds.get(slot, False):
      break
    if script:
     self._execute_bound_script(script)
     time.sleep(0.05)
    elif x11_button is not None:
     # Пульсы кнопки через UInput (press+release): залипнуть в X-сервере
     # не могут — устройство умирает вместе с процессом.
      key_work.mouse_button_press(x11_button)
      time.sleep(0.05)
      key_work.mouse_button_release(x11_button)
      time.sleep(0.05)
    if capped and time.monotonic() >= deadline and not self.stop_requested.is_set():
     with self._timed_holds_lock:
      still_on = self._timed_holds.get(slot, False)
     if still_on:
      dict_save.write_in_log('[safety] повтор-цикл слота %s сам остановлен по потолку 300 с (повторное нажатие не дошло)' % slot)
  finally:
   with self._timed_holds_lock:
    self._timed_holds[slot] = False
   if not script and x11_button is not None:
    key_work.mouse_button_release(x11_button)

 def _release_timed_key(self, slot, key_value, duration):
  """Release a non-repeat hold after its selected duration."""
  time.sleep(duration)
  should_release = False
  with self._timed_holds_lock:
   if self._timed_holds.get(slot, False):
    self._timed_holds[slot] = False
    should_release = True
  if should_release:
   try:
    key_work.key_release(key_value, slot)
   except Exception:
    pass


class work_key:
 def __init__(self):
  self.keys_list = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', 'a', 's', 'd', 'f', 'g',
   'h', 'j', 'k', 'l', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ]
  self.keys_list1 = ['BackSpace', 'Tab', 'Return', 'KP_Enter', 'Escape', 'Delete', 'Home', 'End', 'Page_Up',
   'Page_Down', 'F1', 'Up', 'Down', 'Left', 'Right', 'Control_L', 'ISO_Next_Group', 'Control_R',
   'Shift_L', 'Shift_R', 'Alt_L', 'Alt_R', 'Super_L', 'Super_R', 'Caps_Lock', 'Num_Lock', 'Scroll_Lock',
   'space', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12']

 def mouse_wheel_up(self):
  if not smart_typer.click(4):  # колесо вверх через UInput-указатель
   subprocess.call(['xdotool', 'click', '4'])  # fallback, если uinput недоступен

 def mouse_wheel_donw(self):
  if not smart_typer.click(5):
   subprocess.call(['xdotool', 'click', '5'])

 def mouse_right_donw(self):  # Правая кнопка мыши: UInput, fallback xdotool.
  # pyautogui и bash-обёртка больше не используются.
  if not smart_typer.click(3):
   subprocess.call(['xdotool', 'click', '3'])

 def mouse_middle_donw(self):  # Средняя кнопка мыши: UInput, fallback xdotool.
  if not smart_typer.click(2):
   subprocess.call(['xdotool', 'click', '2'])

 # Удержание кнопок мыши (режимы «держать»/toggle/«повторить») через UInput,
 # а не через pynput XTEST. XTEST-press живёт в X-сервере и при потере
 # отпускания (краш, kill -9, ошибка XTEST) оставлял кнопку «залипшей» во
 # всех приложениях. UInput-устройство умирает вместе с процессом — залип
 # невозможно. pynput остался fallback'ом на случай недоступности /dev/uinput
 # (там залипание возможно, но это старый деградированный путь).
 def mouse_button_press(self, x11_button):
  if smart_typer.button_press(x11_button):
   return True
  btn = _X11_BY_PYNPUT_BUTTON.get(int(x11_button))
  if btn is not None:
   try:
    mouse_controller.press(btn)
    return True
   except Exception:
    pass
  return False

 def mouse_button_release(self, x11_button):
  ok = smart_typer.button_release(x11_button)
  btn = _X11_BY_PYNPUT_BUTTON.get(int(x11_button))
  if btn is not None:
   # release-only XTEST: безвреден, если кнопка не зажата; сбрасывает
   # залипшее состояние от старых (pynput-эпохи) синтетических нажатий.
   try:
    mouse_controller.release(btn)
   except Exception:
    pass
  return ok

 def key_press(self, key, number_key):
 # Mouse-to-key assignments always go through SmartTyper/UInput.
  if not smart_typer.key_down(key):
  # print(key)
   dict_save.write_in_log('Mapped key-down was not emitted: ' + str(key))

 def key_release(self, key, number_key):
 # The matching physical-button release goes through the same class.
  if not smart_typer.key_up(key):
   dict_save.write_in_log('Mapped key-up was not emitted: ' + str(key))

 def key_press_release(self, key, number_key):  #
  pass
  # press_release = '''#!/bin/bash
  # xte 'keydown {}' 'keyup {}'
  # '''
  # if key in self.keys_list:
  #   subprocess.call(['bash', '-c', press_release.format(key, key)])
  #
  # else:
  #
  #   keybord_from.press(KEYS[key[number_key]])

key_work = work_key()



def execute_script(script):
 try:  # print(script)
  result = subprocess.call(['bash', '-c', script])
 except subprocess.CalledProcessError as e:
  print(f"Ошибка при выполнении скрипта: {e}")

def get_path_current_active(games_checkmark_paths):  # Получаем идентификатор активного окна
 try:  # Получаем идентификатор процесса, связанного с активным окном
  active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
  process_id = subprocess.check_output(['xdotool', 'getwindowpid', active_window_id]).decode().strip()
  process_list = [p.info for p in psutil.process_iter(attrs=['name', 'pid', 'exe'])]
  for process in process_list:
   if int(process_id) == int(process['pid']):  # нашли pid активного  окна
    if str(process['exe']) in games_checkmark_paths:
     path_game = str(process['exe'])
     return path_game  # путь к игре активного окна

  return games_checkmark_paths[0]
 except:
  pass

def check_star():
 process_list = [p.info for p in psutil.process_iter(attrs=['name'])]
 a = []
 try:
  for process in process_list:  # print(process['name'])
   if 'Mouse_setting_control_for_buttons_python_for_linux' in process['name']:
    a.append(process)
 except psutil.NoSuchProcess:
  pass
  # Сравниваем именно число найденных копий этой программы (a),
  # а не длину списка ВСЕХ процессов системы (process_list).
 return len(a) > 1

def return_file_path(dict_save):
 res = dict_save.return_jnson()  # получаем настройки
 keys_values = res["key_value"][dict_save.get_cur_app()]  # конфигурация кнопок от предыдущего профиля.
 mouse_press_old = res["mouse_press"][dict_save.get_cur_app()]  # какие кнопки имеют залипания.
 # print(dict_save.get_current_app_path())
 cmd = ['zenity', '--file-selection', '--file-filter=EXE files | *.exe | *.EXE']  # Zenity команда для выбора одного exe файла
 # Вызов zenity и получение выбранного пути
 result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True)
 path_to_file = result.stdout.strip()  # новый путь к игре

 name_with_expansion = os.path.basename(path_to_file)  # Получение базового имени файла с расширением из полного пути к файлу
 name = os.path.splitext(name_with_expansion)[0]  # Отделение имени файла без расширения путем разбиения строки.
 li = list(res["paths"].keys())
 if path_to_file in li:
  return None
 active_before_add = dict_save.get_cur_app()  # активный профиль ДО добавления
 res["paths"][str(path_to_file)] = str(name)
 res["games_checkmark"][str(path_to_file)] = True
 res["key_value"][str(path_to_file)] = keys_values  # сохранить пред значения
 res["mouse_press"][str(path_to_file)] = list(mouse_press_old)
 # Новый профиль должен стоять в списке СРАЗУ ПОД активным (не в конце).
 # Переставляем его во всех секциях (paths, games_checkmark, key_value, ...).
 res = insert_profile_after(res, str(path_to_file), active_before_add)
 # Новую игру сопровождаем списком всех .exe её директории (ключ additional_exe).
 res = ensure_additional_exe(res)
 res1 = res["key_value"]

 dict_save.save_jnson(res)
 if path_to_file in res1:
  return path_to_file
 else:
  res["key_value"][path_to_file] = ["LBUTTON", "RBUTTON", "WHEEL_MOUSE_BUTTON",
   "WHEEL_MOUSE_UP", "WHEEL_MOUSE_DOWN", 'XBUTTON1', 'XBUTTON2']
 return path_to_file

def set_list_box(dict_save, index=0):
 if index != 0:
  dict_save.set_count(index)  # Установить  индекс текущей игры.
 dict_save.set_box_values()  # Установить значения выпадающего списка.
 dict_save.set_values_box()


def add_text_pytq5(key, text_widget):
 if key is None:
  return
 k = key.replace('\r', '').strip()
 if k in keypad_map:
  k = keypad_map[k]
 if k in mouse_map:
  down, up = mouse_map[k]
  sc = f'xte "{down}"\n' \
   f'sleep 0.5\n' \
   f'xte "{up}"\n'
 else:
  key_for_xte = k.replace('"', '\\"')
  if "?\n/" in key_for_xte:
   key_for_xte="slash"
  sc = f'xte "keydown {key_for_xte}"\n' \
   f'sleep 0.5\n' \
   f'xte "keyup {key_for_xte}"\n'

 if text_widget is not None:
  cursor = text_widget.textCursor()
  cursor.insertText(sc)
  text_widget.setTextCursor(cursor)
 return sc


class MouseSettingAppMethods:
 def __init__(self):
  self.keyboard_editor = None
  self.current_keyboard_window = None
  self.tray_icon = None
  # Атомарная защита жизненного цикла runtime (prepare / _stop_active_runtime /
  # emunator_mouse). RLock (реентерабельность) нужен, т.к. prepare() держит
  # lock и вызывает _stop_active_runtime(), который тоже берёт lock.
  self._runtime_lock = threading.RLock()
  self._runtime_generation = 0
  self.create_tray_icon()  # Создаем трей-иконку при запуске
  QTimer.singleShot(0, self.hide)  # Это гарантирует, что команда скрытия.

 def create_keyboard_with_editor(self, key):  # Создает клавиатуру с блокнотом для редактирования макросов для конкретной клавиши i
  print("keyboard ")
  # Скрываем основное окно клавиатуры
  if self.current_keyboard_window:
   self.current_keyboard_window.hide()
   # Закрываем предыдущее окно редактора, если оно открыто
  if self.keyboard_editor:
   self.keyboard_editor.close()
   # Создаем окно с блокнотом сверху и клавиатурой снизу
  macro_window = QMainWindow(self)
  macro_window.setWindowTitle(f"Запись макроса для клавиши {key}")
  macro_window.setGeometry(140, 480, 1410, 600)
  central_widget = QWidget()
  macro_window.setCentralWidget(central_widget)
  layout = QVBoxLayout(central_widget)
  # 1. Блокнот (QTextEdit) - сверху
  macro_window.text_widget = QTextEdit()
  layout.addWidget(QLabel("Редактор скрипта:"))
  layout.addWidget(macro_window.text_widget)
  # Загружаем существующий скрипт для этой клавиши, если он есть
  res = dict_save.return_jnson()
  current_app = res["current_app"]
  # print(current_app)
  dict_save.set_last_key_keyboard_script(key)
  content = res.get("keyboard_script", {}).get(current_app, {}).get("keys", {}).get(key, "")
  if content:
  # print(content)
   macro_window.text_widget.setPlainText(content)
  else:
  # Инициализируем структуры если их нет
   keys_dict = res.get("keyboard_script", {}).get(current_app, {}).get("keys", {})
   # Начальный скрипт
   macro_window.text_widget.setPlainText("#!/bin/bash\n")
   # Перемещаем курсор в конец текста
  cursor = macro_window.text_widget.textCursor()
  cursor.movePosition(QTextCursor.MoveOperation.End)
  macro_window.text_widget.setTextCursor(cursor)

  # 2. Клавиатура (KeyboardWidget) - снизу
  def add_key_command_local(key_local):  # """Функция для вставки команд xte при нажатии клавиш"""
   add_text_pytq5(key_local, macro_window.text_widget)

  macro_window.keyboard_widget = KeyboardWidget(add_key_command_local)
  layout.addWidget(macro_window.keyboard_widget)
  # Переопределяем обработчик закрытия окна для сохранения
  macro_window.closeEvent = lambda event: self.kill_notebook(event, macro_window, "keyboard_script")
  macro_window.show()
  self.keyboard_editor = macro_window

 def kill_notebook(self, event, window, section):
  res = dict_save.return_jnson()
  current_app = dict_save.get_cur_app()
  # читаем содержимое
  context = window.text_widget.toPlainText().strip()
  # определяем ключ

  # Закрытие редактора всегда сохраняет скрипт без запроса (запрос о
  # сохранении появляется только в closeEvent при закрытии всей программы).
  # Сохранение идёт в память (save_jnson), а runtime/клавиатурный слушатель
  # читают скрипты живьём из return_jnson(), поэтому изменения вступают в силу
  # немедленно после закрытия редактора — без перезапуска программы.

  # обработка клавиатурных скриптов
  if section == "keyboard_script":
   key = dict_save.get_last_key_keyboard_script()
   if context and context != "#!/bin/bash":
    res.setdefault("keyboard_script", {}).setdefault(current_app, {}).setdefault("keys", {})
    res["keyboard_script"][current_app]["keys"][key] = context
   else:
    if (current_app in res.get("keyboard_script", {}) and
     key in res["keyboard_script"][current_app].get("keys", {})):
     del res["keyboard_script"][current_app]["keys"][key]

     # обработка мышиных скриптов
  else:
   key = section
   if context and context != "#!/bin/bash":
    res.setdefault("script_mouse", {}).setdefault(current_app, {})
    res["script_mouse"][current_app][key] = context
   else:
    if (current_app in res.get("script_mouse", {}) and
     key in res["script_mouse"][current_app]):
     del res["script_mouse"][current_app][key]

  res = cleanup_empty_script_entries(res)
  dict_save.save_jnson(res)  # сохранить json
  # Обновляем подсветку кнопок скриптов: серым — назначенные скрипты.
  self.update_script_button_colors()
  # показываем основную клавиатуру, если нужно
  if section == "keyboard_script" and self.current_keyboard_window:
   self.current_keyboard_window.show()
   self.update_keyboard_display(dict_save)

  if event:
   event.accept()
  else:
   window.close()

 def mouse_scrpt_keyboard_with_editor(self, i):  # Создает клавиатуру с блокнотом для редактирования макросов для кнопки мыши i
 # Скрываем основное окно клавиатуры
  if self.current_keyboard_window:
   self.current_keyboard_window.hide()
   # Закрываем предыдущее окно редактора, если оно открыто
  if self.keyboard_editor:
   self.keyboard_editor.close()  #   print(i)
  key = defaut_list_mouse_buttons[i]
  # Создаем окно с блокнотом сверху и клавиатурой снизу
  macro_window = QMainWindow(self)
  print(key)
  macro_window.setWindowTitle(f"Запись макроса для клавиши мыши {key}")
  macro_window.setGeometry(140, 480, 1410, 600)
  central_widget = QWidget()
  macro_window.setCentralWidget(central_widget)
  layout = QVBoxLayout(central_widget)
  # 1. Блокнот (QTextEdit) - сверху
  macro_window.text_widget = QTextEdit()
  layout.addWidget(QLabel("Редактор скрипта:"))
  layout.addWidget(macro_window.text_widget)
  # Загружаем существующий скрипт для этой клавиши, если он есть
  res = dict_save.return_jnson()
  current_app = res["current_app"]
  # print(current_app) # dict_save.set_last_key_keyboard_script(key)  # Используем тот же метод для простоты, но логика разделена в kill_notebook
  content = res.get("script_mouse", {}).get(current_app, {}).get(key, "")
  if content:
  # print(content)
   macro_window.text_widget.setPlainText(content)
  else:
  # Пустой редактор не создаёт запись в словаре до фактического сохранения.
   macro_window.text_widget.setPlainText("#!/bin/bash\n")
   # Перемещаем курсор в конец текста
  cursor = macro_window.text_widget.textCursor()
  cursor.movePosition(QTextCursor.MoveOperation.End)
  macro_window.text_widget.setTextCursor(cursor)

  # 2. Клавиатура (KeyboardWidget) - снизу
  def add_key_command_local(key_local):  # """Функция для вставки команд xte при нажатии клавиш"""
   add_text_pytq5(key_local, macro_window.text_widget)

  macro_window.keyboard_widget = KeyboardWidget(add_key_command_local)
  layout.addWidget(macro_window.keyboard_widget)
  # Переопределяем обработчик закрытия окна для сохранения
  macro_window.closeEvent = lambda event: self.kill_notebook(event, macro_window, key)
  macro_window.show()
  self.keyboard_editor = macro_window

 def create_virtual_keyboard(self, dict_save, callback_record_macro=None):  # Создает виртуальную клавиатуру без блокнота
 # Закрываем предыдущее окно клавиатуры, если оно открыто
  if self.current_keyboard_window:
   self.current_keyboard_window.close()
  keyboard_window = QMainWindow(self)
  self.current_keyboard_window = keyboard_window
  keyboard_window.dict_save = dict_save
  keyboard_window.setGeometry(240, 580, 1350, 340)
  keyboard_window.setWindowTitle("Выбор клавиш")
  keyboard_window.central = QWidget(keyboard_window)
  keyboard_window.setCentralWidget(keyboard_window.central)
  # Создаем layout для клавиатуры
  layout = QVBoxLayout(keyboard_window.central)
  # Получаем информацию о активных клавишах с макросами
  res = dict_save.return_jnson()
  current_app = dict_save.get_cur_app()
  content = res.get("keyboard_script", {}).get(current_app, {}).get("keys", {})
  keys_active = []
  if content:
   keys_active = list(res["keyboard_script"][current_app]["keys"].keys())
  else:
  # Пустая клавиатура не создаёт запись в словаре до сохранения скрипта.
   pass

   # Создаем клавиатуру с callback для записи макросов
  def record_macro_callback(key):  # Открываем редактор для этой клавиши
   self.create_keyboard_with_editor(key)

  keyboard_widget = KeyboardWidget(record_macro_callback)
  layout.addWidget(keyboard_widget)
  # Подсвечиваем кнопки, которые уже имеют макросы
  self.highlight_buttons_with_macros(keyboard_widget, keys_active)
  keyboard_window.show()
  return keyboard_window

 def highlight_buttons_with_macros(self, keyboard_widget, keys_with_macros):  # Подсвечивает кнопки, для которых уже созданы макросы"""
 # Сначала сбрасываем стиль для всех кнопок
  for button in keyboard_widget.findChildren(QPushButton):
   button.setStyleSheet("")  # Сброс на стиль по умолчанию
   # Теперь подсвечиваем нужные
  for key in keys_with_macros:
  # Ищем кнопку по тексту. Текст может содержать переносы строк, поэтому используем strip()
   key_norm = key.replace('\n', ' ').strip()
   buttons = keyboard_widget.findChildren(QPushButton)
   for button in buttons:
   # Совпадение либо по отображаемому тексту, либо по эффективному ключу
   # (нумпад +/- хранятся как KEY_KPPLUS / KEY_KPMINUS, а на кнопке написано +/-).
    eff = getattr(button, 'effective_key', None)
    if (button.text().replace('\n', ' ').strip() == key_norm) or (eff is not None and eff == key):
     button.setStyleSheet("background-color: #0078d7; color: white;")
     break

 def update_keyboard_display(self, dict_save):  # Обновляет отображение основной клавиатуры после сохранения изменений"""
  if not self.current_keyboard_window:
   self.create_virtual_keyboard(dict_save)
   return
   # Получаем актуальный список клавиш с макросами
  current_app = dict_save.get_cur_app()
  res = dict_save.return_jnson()
  keys_active = []
  if "keyboard_script" in res and current_app in res["keyboard_script"] and "keys" in res["keyboard_script"][current_app]:
   keys_active = list(res["keyboard_script"][current_app]["keys"].keys())
   # Находим виджет клавиатуры и обновляем подсветку
  keyboard_widget = self.current_keyboard_window.findChild(KeyboardWidget)
  if keyboard_widget:
   self.highlight_buttons_with_macros(keyboard_widget, keys_active)
   # Показываем окно, если оно было скрыто
  self.current_keyboard_window.show()

 def create_tray_icon(self):  # создания трей-иконки (немного модифицированный)
  icon = QIcon("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/mouse/tmpovhwj8so.png")
  if icon.isNull():
   icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)

  self.tray_icon = QSystemTrayIcon(icon, self)
  self.tray_icon.setToolTip("Mouse Setting Control")

  tray_menu = QMenu()
  quit_action = tray_menu.addAction("Выход")
  quit_action.triggered.connect(self.close)

  self.tray_icon.setContextMenu(tray_menu)
  self.tray_icon.activated.connect(self.tray_icon_clicked)
  self.tray_icon.show()  # Отображаем иконку в системном трее

 def tray_icon_clicked(self, reason):  # Метод-обработчик кликов по иконке в трее
  if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Проверяем, является ли событие обычным кликом
   if self.isVisible():  # Проверяем, видно ли главное окно
    self.hide()  # Если видно, скрываем его
   else:
    self.show_normal()  # Если скрыто, восстанавливаем и показываем его

 def show_normal(self):  # Метод для восстановления и фокусировки главного окна
  self.showNormal()
  self.activateWindow()

 def close_app(self):   # Закрываем приложение полностью
  self.close()

 def closeEvent(self, event=None):  # Переопределяем закрытие окна - спрашиваем о сохранении изменений
  dict_save.thread_exit=True
  # Возврат ЗАВОДСКОЙ карты кнопок мыши при выходе: раньше после закрытия
  # программы в X оставался жить наш remap (1 2 3 13 5 6 7 15 16) и мышь
  # вела себя «странно» до перезагрузки X.
  try:
   runtime = getattr(self, '_active_runtime', None)
   if runtime is not None:
    # stop() (а не просто stop_requested.set()): отпускает залипшие
    # кнопки и останавливает воркеры до гарантированного выхода.
    runtime.stop()
   dict_save.set_default_id_value()
  except Exception as exc:
   try:
    dict_save.write_in_log('restore button map failed: ' + str(exc))
   except Exception:
    pass
  old_data = dict_save.return_old_data()
  new_data = dict_save.return_jnson()
  # DeepDiff не видит перестановку ключей словаря (порядок профилей),
  # поэтому порядок списка игр сравниваем отдельно.
  import deepdiff  # ленивый импорт: при старте не тормозит запуск
  diff = deepdiff.DeepDiff(old_data, new_data) or profile_order_changed(old_data, new_data)
  if diff:
   reply = QMessageBox.question(self, "Выход", "Вы хотите сохранить изменения перед выходом?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
   if reply == QMessageBox.StandardButton.Cancel:
    if event is not None:
     event.ignore()
    return
   if new_data["current_app"] == "":
    new_data["current_app"] = "C:/Windows/explorer.exe"
   if reply == QMessageBox.StandardButton.Save:
    dict_save.write_to_file(new_data)
  release_single_instance_lock()
  event.accept()
  os._exit(0)   # гарантированный выход (фоновые потоки уже остановлены через thread_exit)

 def _resolve_profile_target(self, runtime, active_game):
  """Решение, какой профиль должен быть активен прямо сейчас.

  Вынесено из emunator_mouse, чтобы правило возврата («вышли из игры —
  вернулись на синюю строку/профиль возврата, а не остались в игровом»)
  было в одном месте и проверялось тестами. Возвращает путь профиля."""
  if active_game and active_game in runtime.enabled_profiles:
   # В фокусе реальное игровое окно: его профиль всегда главнее.
   if active_game == runtime.game and getattr(runtime, 'manual_ui_pick', False):
    # Профиль, выбранный вручную, подтверждён живым игровым окном: режим
    # «настройка профиля» закончен. При выходе из игры/Alt-Tab вернёмся на
    # профиль возврата, а не останемся в игровом (жалоба 2026-11-16).
    runtime.manual_ui_pick = False
   return active_game
  if getattr(runtime, 'manual_ui_pick', False):
   # Пользователь только что выбрал профиль вручную, а игра ещё не в фокусе
   # (например, настраивает кнопки до запуска) — не выдёргиваем его из
   # выбранного профиля.
   return runtime.game
  # Игрового окна в фокусе нет (свернуто, закрыто, другое окно).
  #
  # (Запрос 2026-11-16): возвращаемся к профилю, который пользователь выбрал
  # ВРУЧНУЮ («синяя» строка, store.user_profile), либо к последнему профилю
  # возврата. current_app/user_profile авто-переключением не перезаписываются,
  # поэтому после сворачивания/выхода из игры снова активен именно тот
  # профиль, который был выбран пользователем.
  fallback = fallback_profile_path(runtime.store, runtime.enabled_profiles)
  selected = str(runtime.store.get_user_profile() or runtime.store.get_cur_app() or '')
  return_profile = str(getattr(self, '_return_profile', '') or '')
  target = runtime.game
  for candidate in (selected, return_profile, fallback):
   if not candidate or candidate not in runtime.enabled_profiles:
    continue
   if candidate == runtime.game:
    continue
   # Игровой профиль, чей процесс уже не запущен, возвратом быть не может:
   # иначе после выхода из игры мы «возвращались» в мёртвую игру и
   # застревали в игровом профиле (или прыгали между профилями).
   if candidate != fallback and not is_profile_process_running(candidate):
    continue
   target = candidate
   break
  self._return_profile = target
  return target

 def emunator_mouse(self, runtime, generation):
  """Run one listener until its profile is changed, stopped, or the app exits."""
  def on_click(_x, _y, button, pressed):
   with self._runtime_lock:
    current = getattr(self, '_active_runtime', None)
   if current is runtime and not runtime.stop_requested.is_set():
    runtime.handle_listener_event(button, pressed)
   return True

  restart_game = None
  listener = mouse.Listener(on_click=on_click)
  listener.start()
  try:
   while not runtime.store.thread_exit and not runtime.stop_requested.is_set():
    with self._runtime_lock:
     # Этот runtime уже устарел (UI или авто-переключение создали новый) —
     # тихо выходим, чтобы не перетирать актуальный профиль.
     if getattr(self, '_active_runtime', None) is not runtime or self._runtime_generation != generation:
      return
    active_game = check_current_active_window(runtime.store, runtime.enabled_profiles)
    target = self._resolve_profile_target(runtime, active_game)
    if target != runtime.game:
     # (2026-11-16) current_app / user_profile здесь НЕ перезаписываем:
     # это выбор пользователя (синяя строка), и именно к нему мы вернёмся,
     # когда игровое окно потеряет фокус. Раньше здесь current_app
     # принудительно менялся на fallback, из-за чего «синий» профиль
     # терялся и возврат шёл не туда.
     try:
      runtime.store.write_in_log('[profile] switch %r -> %r (active_game=%r)' % (runtime.game, target, active_game))
     except Exception:
      pass
     # (2026-11-16) НЕ вызывать здесь runtime.join_event_workers(): dispatch-
     # потоки ещё не получили stop (он будет в finally → runtime.stop()), поэтому
     # join ждёт полный timeout на КАЖДЫЙ из ~8 биндингов (~16 с). Всё это время
     # цикл опроса окна стоит и НЕ видит смену фокуса (Win+D/Alt-Tab) — профиль
     # «не возвращается» на рабочий стол. Корректный join — в runtime.stop().
     restart_game = target
     break
    time.sleep(0.15)  # тело цикла: быстрый путь по /proc (единицы мс),
                     # поэтому опрос 6-7 раз/с дешёвый и реакция на смену
                     # окна ~0.2-0.3 с (раньше 0.5 с + кэш 5 с = до 1.5 с)
  finally:
  # Determine whether we were externally replaced BEFORE any cleanup below.
   with self._runtime_lock:
    is_current = getattr(self, '_active_runtime', None) is runtime
    is_same_generation = self._runtime_generation == generation
   was_stopped_externally = runtime.stop_requested.is_set()
   # pynput/Xlib может закрыть Display раньше, чем старый listener
   # успеет выполнить stop(). В этом случае record_disable_context()
   # падает с AttributeError: request_queue is None. Остановка
   # listener не должна ронять emunator_mouse или мешать новому runtime.
   try:
    listener.stop()
   except (AttributeError, RuntimeError, OSError) as exc:
    try:
     runtime.store.write_in_log('pynput listener stop ignored: ' + str(exc))
    except Exception:
     pass
   try:
    listener.join(timeout=1.0)
   except (AttributeError, RuntimeError, OSError):
    pass
   # Полная остановка рантайма: снимаем залипшие/эмулированные кнопки и клавиши
   # (иначе при смене профиля или выходе из игры ввод остаётся «зажатым»).
   try:
    runtime.stop()
   except Exception:
    try:
     runtime.stop_workers()
    except Exception:
     pass
    try:
     runtime._release_all_emulated_inputs()
    except Exception:
     pass
   if is_current and is_same_generation:
    self._active_runtime = None
    runtime.store.set_thread(0)

  # Перезапуск с явной целью (окно игры или выбранный профиль) только если
  # мы всё ещё актуальны и не были остановлены извне.
  # ВАЖНО: НЕ использовать здесь QTimer.singleShot. Этот код выполняется в
  # фоновом потоке emunator_mouse, у которого НЕТ Qt event loop — таймер с
  # timeout=0 создаётся в этом потоке и никогда не сработает, поэтому
  # авто-переключение профиля по активному окну игры не происходило.
  # self.prepare() атомарен под _runtime_lock, thread-safe (GUI-вызовов нет) и
  # сам запускает новый listener-поток, поэтому вызываем его напрямую.
  if not runtime.store.thread_exit and not was_stopped_externally and restart_game and is_same_generation:
   self.prepare(runtime.store, restart_game)

 def _stop_active_runtime(self, store):
  """Request old runtime shutdown without waiting for window detection."""
  with self._runtime_lock:
   runtime = getattr(self, '_active_runtime', None)
   if runtime is not None:
    runtime.stop()
    # The old listener exits on its next loop iteration.  Do not join it:
    # a slow process/window scan must never delay the new profile map.
   if getattr(self, '_active_runtime', None) is runtime:
    self._active_runtime = None
  store.set_thread(0)

 def prepare(self, store=None, start_game=None, force_ui_selection=False):
  """Replace the old profile runtime atomically, apply its map, start listener."""
  store = store or dict_save
  with self._runtime_lock:
   # (Исправление 2026-11-09: «сдача» физического удержания) Если в старом
   # рантайме идёт прокрутка (боковая кнопка физически удерживается), то после
   # смены профиля событие «отпускание» уйдёт в остановленный старый рантайм,
   # а новый останется на паузе — кнопка «перестанет делать колёсико» до
   # нового нажатия. Запоминаем активные слоты ДО остановки старого рантайма
   # и resume-им те же слоты в новом (только режим «удержание», а не
   # «повторить»/«держать» — у них своё toggle-состояние, его не наследуем).
   # (Исправление 2026-11-15, §42: «сдача» toggle-состояний «Держать»)
   # Если в старом рантайме активно toggle-залипание ПКМ/СКМ (режим «Держать»
   # без длительности, т.е. 1-е нажатие зажимает, 2-е отпускает), то после
   # смены профиля (выход из игры) новое рантайм НЕ наследует это состояние —
   # и кнопки остаются «залипшими» (X-состояние «нажата» сохраняется в
   # виртуальном указателе, а новое рантайм не знает, что их нужно отпустить).
   # Запоминаем toggle-состояния ДО остановки старого рантайма и сбрасываем
   # их в новом (полный release, а не «сдача» — т.к. после выхода из игры
   # пользователь ожидает «чистое» состояние, а не продолжение залипания).
   _handover_scroll_slots = set()
   _old_runtime = getattr(self, '_active_runtime', None)
   _old_right_sticking = False
   _old_middle_sticking = False
   if _old_runtime is not None:
    for _b in _old_runtime.bindings.values():
     if _b.worker.is_active() and str(_b.worker.key).startswith('SCROLL_'):
      _s = _b.slot
      try:
       if _old_runtime.hold_flags[_s] or _old_runtime.repeat_flags[_s]:
        continue
      except IndexError:
       continue
      _handover_scroll_slots.add(_s)
    # Запоминаем toggle-состояния «Держать» (они будут сброшены в новом
    # рантайме, т.к. после выхода из игры/смены профиля пользователь
    # ожидает «чистое» состояние, а не продолжение залипания).
    _old_right_sticking = bool(getattr(_old_runtime, '_right_sticking', False))
    _old_middle_sticking = bool(getattr(_old_runtime, '_middle_sticking', False))
   self._stop_active_runtime(store)
   self._runtime_generation += 1
   my_generation = self._runtime_generation
   runtime = MouseProfileRuntime(store, start_game, force_ui_selection)
   print(f"[PREPARE] gen={my_generation} game={runtime.game!r}")
   # (2026-11-16) Профиль возврата: куда вернуться, когда игровое окно
   # потеряет фокус. Ручной выбор в UI сразу становится профилем возврата;
   # иначе — безопасный не-игровой профиль (fallback).
   if force_ui_selection:
    self._return_profile = runtime.game
   elif not getattr(self, '_return_profile', ''):
    self._return_profile = fallback_profile_path(store, runtime.enabled_profiles) or runtime.game
   # (Исправление 2026-11-09: «боковая кнопка = назад, а не прокрутка»)
   # Хранимый xinput-id устаревает после каждого перезапуска X-сессии
   # (устройства нумеруются заново: мышь может быть 6 в одной сессии и
   # 14 в другой). Раньше авто-поиск мыши (ensure_valid_mouse_id) шёл
   # ТОЛЬКО в start_startup_now; при авто-смене профиля (emunator_mouse)
   # рантайм работал со «чужим» id → remap не применялся → боковые
   # кнопки оставались нативными X11 8/9 = «Назад/Вперёд» в браузере,
   # а не прокруткой из профиля. Теперь перед применением карты id
   # перепроверяем (по стабильному имени id_name / по полноте карты),
   # и при смене устройства применяем карту повторно.
   try:
    _new_id, _id_changed = store.ensure_valid_mouse_id(runtime.device_id)
    if _id_changed and _new_id and _new_id != runtime.device_id:
     runtime.device_id = _new_id
     _settings_now = store.return_jnson()
     _settings_now['id'] = _new_id
     store.save_jnson(_settings_now)
   except Exception:
    _id_changed = False  # X недоступен — применяем карту на текущем id как раньше
   applied = runtime.apply_button_map()
   if not applied and _id_changed:
    # Первая попытка могла не успеть (X занято) — повтор один раз.
    applied = runtime.apply_button_map()
   if not applied:
    runtime.register_physical_fallbacks()
   else:
    # Ремап применён: нативные имена (Button.button8/9/left/right/...) 
    # становятся эхом (в т.ч. от xdotool/UInput эмуляции других слотов),
    # поэтому убираем все физические fallback-алиасы. Они нужны только когда
    # xinput-remap не сработал; иначе события уже приходят под виртуальными
    # именами (Button.button11..16) и дополнительные физические имена дают
    # ложные срабатывания, сбивая удержание других кнопок.
    for _alias in getattr(runtime, '_fallback_aliases', ()):
     runtime.bindings.pop(_alias, None)
    runtime._fallback_aliases = []
    for _alias in getattr(runtime, '_keyboard_fallback_aliases', ()):
     runtime.bindings.pop(_alias, None)
    runtime._keyboard_fallback_aliases = []
   runtime.store.set_current_path_game(runtime.game)
   self._active_runtime = runtime
   # Сдача удержания: возобновляем прокрутку в тех же слотах, где она шла в
   # старом рантайме (кнопка физически не отпущена — user всё ещё держит её).
   for _slot in _handover_scroll_slots:
    try:
     if runtime.hold_flags[_slot] or runtime.repeat_flags[_slot]:
      continue
    except IndexError:
     continue
    for _b in runtime.bindings.values():
     if _b.slot == _slot:
      _b.worker.resume()
      break
    # (Исправление 2026-11-15, §42: полный сброс toggle-залипания при смене
    # профиля / выходе из игры). Если в старом рантайме было активно
    # toggle-залипание ПКМ/СКМ (режим «Держать» без длительности), то после
    # смены профиля (например, выход из игры) новое рантайм НЕ наследует это
    # состояние — кнопки остаются «залипшими» в виртуальном указателе.
    # _stop_active_runtime() → runtime.stop() → _release_all_emulated_inputs()
    # уже отпустил зажатые кнопки (EV_KEY=0) в X, но toggle-флаги нового
    # рантайма (_right_sticking/_middle_sticking) по умолчанию False — что
    # корректно: после выхода из игры пользователь ожидает «чистое» состояние,
    # а не продолжение залипания. Дополнительный safety-net: принудительно
    # отпускаем 1/2/3 ещё раз (идемпотентно) и логируем, если залипание было.
    if _old_right_sticking or _old_middle_sticking:
     try:
      store.write_in_log('[profile-switch] old runtime had sticking RMB=%s MMB=%s — full release on new runtime' % (_old_right_sticking, _old_middle_sticking))
     except Exception:
      pass
     try:
      for _x11b in (1, 2, 3):
       key_work.mouse_button_release(_x11b)
     except Exception:
      pass

  listener_thread = threading.Thread(target=self.emunator_mouse, args=(runtime, my_generation))
  runtime.store.set_thread(listener_thread)
  listener_thread.start()

 def start_startup_now(self, store=None, force_ui_selection=False):
  store = store or dict_save
  settings = store.return_jnson()
  # Сброс залипших синтетических кнопок мыши (исправление 2026-11-04):
  # старый режим «держать» работал через pynput XTEST — после краша/kill
  # X-сервер мог остаться в состоянии «правая кнопка нажата», и физическая
  # правая кнопка «не работала» во всех приложениях. Release-only XTEST-
  # событие: если кнопка НЕ зажата — ничего не происходит; если залипла —
  # сбрасывает. UInput-вариант (новый режим) залипать в принципе не может.
  for _btn in (mouse.Button.left, mouse.Button.middle, mouse.Button.right):
   try:
    mouse_controller.release(_btn)
   except Exception:
    pass
  current_game = str(settings['current_app'])
  if not current_game:
   return
  # АВТО-ПОИСК МЫШИ: сохранённый xinput-id может устареть после перезапуска
  # X-сессии (номера устройств выдаются заново в порядке эnumerации USB и тот
  # же id может оказаться у клавиатуры БЕЗ кнопок). Тогда set-button-map
  # молча падает, перехват кнопок не применяется и «назначение клавиши не
  # срабатывает». Переопределяем устройство автоматически и сохраняем.
  valid_id, id_changed = store.ensure_valid_mouse_id(settings.get('id', 0))
  if id_changed:
   # Без всплывающего окна: исправление делаем тихо (id уже сохранён в
   # настройках), лишь синхронизируем выпадающий список. Следующий запуск
   # будет «чистым», т.к. валидный id теперь записан в JSON.
   settings['id'] = valid_id
   # Стабильное ИМЯ устройства: в следующей X-сессии xinput-id снова
   # перенумеруются, и мышь будет найдена по имени, а не по «слетевшему» id.
   settings['id_name'] = str(store.dict_id_names.get(valid_id, '')).strip()
   store.save_jnson(settings)
   if hasattr(self, 'id_combo'):
    try:
     self.id_combo.setCurrentText(str(valid_id))
    except Exception:
     pass
  if settings['id'] == 0:
   self._show_missing_device_message()
   return

  enabled_profiles = [path for path, enabled in settings['games_checkmark'].items() if enabled]
  if current_game in enabled_profiles:
   # force_ui_selection=True при ручном клике: применение выбранного профиля
   # сейчас (приоритет №0 в MouseProfileRuntime).
   self.prepare(store, force_ui_selection=force_ui_selection)
  else:
   self._stop_active_runtime(store)
   QMessageBox.information(self, 'Ошибка', 'Нужно выбрать приложение')

 def _show_missing_device_message(self):
  message = QMessageBox(self)
  message.setWindowTitle('Ошибка')
  message.setText('Вы не выбрали устройство')
  show_button = message.addButton('Ок', QMessageBox.ButtonRole.AcceptRole)
  message.buttonClicked.connect(lambda button: show_list_id_callback() if button == show_button else None)
  message.exec()

 def update_script_button_colors(self):
  """Подсветить кнопки скриптов для текущего профиля:
   серым — если на кнопку мыши назначен скрипт, обычным цветом — если нет.
   Позволяет сразу видеть, на какие кнопки уже есть назначение скрипта."""
  res = dict_save.return_jnson()
  game = res.get("current_app", "")
  buttons = getattr(self, "buttons_script", None)
  if not buttons:
   return
  for button in buttons:
   button.setStyleSheet("")
  script = res.get("script_mouse", {}).get(game, {})
  if script:
   for key, value in script.items():
    if value and key in defaut_list_mouse_buttons:  # Проверяем, что значение не пустое
     i = defaut_list_mouse_buttons.index(key)
     self.buttons_script[i].setStyleSheet(""" QPushButton { border: 1px solid gray; padding: 5px;
                                    color: black;  background-color: gray; } """)
     self.buttons_script[i].update()

 def check_label_changed(self, count):  # установить текущую активную игру
  _sb = self.scroll_area.verticalScrollBar()
  _scroll_pos = _sb.value()
  res = dict_save.return_jnson()
  labels = dict_save.return_labels()
  # Сброс ВСЕХ label в белый (как в Tkinter-версии, см. set_colol_white_label_changed).
  # Раньше сбрасывался только label по current_app; если фоновый монитор активного
  # окна (emunator_mouse) уже сменил current_app без обновления UI, старый синий
  # label оставался и синих накапливалось несколько.
  for label in labels:
   label.setStyleSheet("background-color: white; border: 1px solid gray; padding: 5px;")
  game = list(res["paths"].keys())[count]
  # Selecting a row updates the UI, but must not overwrite the saved
  # non-game fallback used after a game process exits.
  res["current_app"] = game
  labels[count].setStyleSheet("background-color: #06c; color: white; border: 1px solid gray; padding: 5px;")
  list_check_buttons = res.get("mouse_press", {}).get(game, [])
  # print("ch")
  res["current_app"] = game
  for idx, check in enumerate(self.mouse_check_buttons):
   if idx < len(list_check_buttons):
    check.setChecked(list_check_buttons[idx])
   else:
    check.setChecked(False)
  script = res.get("script_mouse", {}).get(game, {})
  self.update_script_button_colors()
  script = res.get("keyboard_script", {}).get(game, {}).get("keys", {})
  self.Keyboard_button.setStyleSheet("")
  if script:
   self.Keyboard_button.setStyleSheet(""" QPushButton { border: 1px solid gray; padding: 5px;
                                    color: black;  background-color: gray; } """)
   self.Keyboard_button.update()

  repeats = res.get("mouse_repeat", {}).get(game, [False] * 7)
  for idx, repeat_checkbox in enumerate(getattr(self, "mouse_repeat_check_buttons", [])):
   repeat_checkbox.blockSignals(True)
   repeat_checkbox.setChecked(bool(repeats[idx]) if idx < len(repeats) else False)
   repeat_checkbox.blockSignals(False)

  durations = res.get("mouse_hold_repeat_seconds", {}).get(game, [None] * 7)
  for idx, duration_combo in enumerate(getattr(self, "mouse_hold_duration_combos", [])):
   value = durations[idx] if idx < len(durations) else None
   duration_combo.blockSignals(True)
   duration_combo.setCurrentText("" if value in (None, "", 0, "0") else str(value))
   duration_combo.blockSignals(False)

  values = res["key_value"][game]
  for button, value in zip(self.combo_box, values):
   button.blockSignals(True)
   button.setCurrentText(value)
   button.blockSignals(False)
  dict_save.set_cur_app(game)
  # Запоминаем ручной выбор («синюю» строку): к нему вернёмся после
  # сворачивания/выхода из игры (см. emunator_mouse, 2026-11-16).
  dict_save.set_user_profile(game)
  dict_save.save_jnson(res)
  # The blue profile must also become the active emulation context.
  # КЛЮЧЕВОЕ: force_ui_selection=True гарантирует, что ручной выбор применится
  # немедленно (приоритет №0), даже если current_app ещё указывает на игру.
  self.start_startup_now(dict_save, force_ui_selection=True)
  # Сохраняем позицию прокрутки: клик не должен «скакать» список профилей.
  QTimer.singleShot(0, lambda: self.scroll_area.verticalScrollBar().setValue(_scroll_pos))

 def filling_in_fields(self, dict_save):
  while self.games_layout.count():
   child = self.games_layout.takeAt(0)
   if child.widget():
    child.widget().deleteLater()
  res = dict_save.return_jnson()
  labels = dict_save.return_labels()
  name_games = dict_save.return_name_games()
  var_list = dict_save.return_var_list()
  labels.clear()
  name_games.clear()
  var_list.clear()
  check_mark = res["games_checkmark"]
  paths = res["paths"]
  for count, (path, game_name) in enumerate(paths.items()):
   game_container = QWidget()
   game_container.setFocusPolicy(Qt.FocusPolicy.NoFocus)
   game_layout = QHBoxLayout(game_container)
   game_layout.setContentsMargins(0, 0, 0, 0)
   var = QCheckBox()
   var.setFocusPolicy(Qt.FocusPolicy.NoFocus)
   var.setChecked(check_mark[path])
   var_list.append(var)
   var.stateChanged.connect(lambda state, c=count: self.checkbutton_changed(c))
   label = QLabel(game_name)
   label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
   label.setFixedWidth(200)
   label.setStyleSheet("background-color: white; border: 1px solid gray; padding: 5px;")
   label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

   label.mousePressEvent = lambda event, c=count: self.label_clicked(event, c)
   label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
   label.customContextMenuRequested.connect(lambda pos, c=count: self.show_change_name_menu(c))
   name_games.append(game_name)
   labels.append(label)
   game_layout.addWidget(var)
   game_layout.addWidget(label)
   self.games_layout.addWidget(game_container)
  if res['current_app'] in paths:
   index = list(paths.keys()).index(res['current_app'])
   if index < len(labels):
    labels[index].setStyleSheet("background-color: #06c; color: white; border: 1px solid gray; padding: 5px;")

 def change_app(self, game=None):
  # Установить текущий профиль. game=None (смена ID мыши в update_profile)
  # означает «перезапустить эмуляцию на уже выбранном профиле» — раньше
  # вызов без аргументов ЗАТИРАЛ current_app пустой строкой (game=""
  # записывался в JSON), из-за чего выбранный профиль слетал.
  if game is None:
   game = dict_save.get_cur_app() or str(dict_save.return_jnson().get('current_app', ''))
  if not game:
   return
  if game != dict_save.get_cur_app():
   dict_save.set_cur_app(game)
   dict_save.set_user_profile(game)
   res = dict_save.return_jnson()
   res['current_app'] = game
   dict_save.save_jnson(res)

 def checkbutton_changed(self, count):  # снять и убрать галочку.
  res = dict_save.return_jnson()
  keys_list = list(res["games_checkmark"].keys())
  curr_app = str(keys_list[count])
  var_list = dict_save.return_var_list()
  res["games_checkmark"][curr_app] = var_list[count].isChecked()
  dict_save.save_jnson(res)

 def update_labels_bindings(self):  # Обновление списка игр
  labels = dict_save.return_labels()
  var_list = dict_save.return_var_list()
  for count, label in enumerate(labels):    # ИЗМЕНЕНО: Более надёжная перепривязка (lambda с default c=count захватывается правильно)
   label.mousePressEvent = lambda event, c=count: self.label_clicked(event, c)
   if count < len(var_list):
    try:    # ИЗМЕНЕНО: disconnect с try-except для безопасности (если уже отключено)
     var_list[count].stateChanged.disconnect()
    except TypeError:
     pass  # Нет соединений — OK
    var_list[count].stateChanged.connect(lambda state, c=count: self.checkbutton_changed(c))

 def move_element(self, dict_save, direction):  # Двигать названия игр по списку
  try:
   res = dict_save.return_jnson()
   labels = dict_save.return_labels()
   curr_app_path = res["current_app"]

   # ИЗМЕНЕНО: Используем paths для consistency (как в filling_in_fields)
   keys_list = list(res["paths"].keys())
   index_curr = keys_list.index(curr_app_path)

   new_index = -1
   if direction == 'up' and index_curr > 0:
    new_index = index_curr - 1
   elif direction == 'down' and index_curr < len(labels) - 1:
    new_index = index_curr + 1
   else:
    return

   container_curr = labels[index_curr].parentWidget()
   container_new = labels[new_index].parentWidget()
   main_layout = container_curr.parentWidget().layout()

   main_layout.removeWidget(container_curr)
   main_layout.removeWidget(container_new)

   # Перемещаем в labels (визуальный порядок)
   labels.insert(new_index, labels.pop(index_curr))

   if direction == 'up':
    main_layout.insertWidget(new_index, container_curr)
    main_layout.insertWidget(index_curr, container_new)
   else:
    main_layout.insertWidget(index_curr, container_new)
    main_layout.insertWidget(new_index, container_curr)

    # ИЗМЕНЕНО: Стили по временным индексам (после move: curr теперь на new_index, former new на index_curr)
   labels[index_curr].setStyleSheet("background-color: white; color: black; border: 1px solid gray; padding: 5px;")
   labels[new_index].setStyleSheet("background-color: #06c; color: white; border: 1px solid gray; padding: 5px;")

   # ИЗМЕНЕНО: reorder JSON по старым индексам (swap idx1=index_curr, idx2=new_index)
   res = reorder_keys_in_dict(res, index_curr, new_index)

   self.update_labels_bindings()
   dict_save.save_labels(labels)
   dict_save.save_jnson(res)

   # ИЗМЕНЕНО: Опционально — sync layout с новым JSON (перестроит, но в правильном порядке)
   # Если не нужно (чтобы не мигать), закомментируйте
   self.filling_in_fields(dict_save)

   return 0
  except Exception as e:
   print(f"Ошибка при перемещении элемента: {e}")
   return -1

 def apply_settings_now(self):
  """Перезапустить активный runtime без ожидания смены профиля."""
  QTimer.singleShot(0, lambda: self.start_startup_now(dict_save))

 def update_button(self, index):  # обновить, когда выбираем другое значение для кнопки мыши
  res = dict_save.return_jnson()
  game = res["current_app"]
  current_value = self.combo_box[index].currentText()
  res["key_value"][game][index] = current_value
  # Выпадающее назначение и скрипт одной и той же кнопки не должны
  # конкурировать. Если пользователь выбрал R/W/другую клавишу,
  # удаляем старый script_mouse для этого слота, иначе dispatch
  # запускал бы старый bash-скрипт и до R никогда не доходил.
  button_name = defaut_list_mouse_buttons[index]
  script_profiles = res.get("script_mouse", {})
  profile_scripts = script_profiles.get(game)
  if index in (5, 6):
   button_names = {"XBUTTON1", "XBUTTON2"}
  else:
   button_names = {button_name}
  if isinstance(profile_scripts, dict) and current_value.strip() != "":
   for stale_button_name in button_names:
    profile_scripts.pop(stale_button_name, None)
   if not profile_scripts:
    script_profiles.pop(game, None)
   if not script_profiles:
    res.pop("script_mouse", None)
  dict_save.save_jnson(res)  # Сохранить новое значение для выпадающего списка
  # Назначение клавиши снимает скрипт — сбрасываем подсветку кнопки.
  self.update_script_button_colors()
  self.apply_settings_now()

 def update_profile(self):  # обновить профиль (смена ID устройства мыши)
  res = dict_save.return_jnson()
  text = self.id_combo.currentText()
  try:
   current_value = int(text)
  except (TypeError, ValueError):
   return
  if res["id"] != current_value:
   res["id"] = current_value
   # Стабильное ИМЯ выбранного устройства: после перенумерации xinput-id
   # в новой X-сессии ручной выбор будет восстановлен по имени, а не
   # перезаписан авто-выбором (ensure_valid_mouse_id).
   nm = str(dict_save.dict_id_names.get(current_value, '')).strip()
   res["id_name"] = nm if nm else res.get("id_name", "")
   dict_save.save_jnson(res)  # Сохранить новое значение для выпадающего списка
   # Раньше: change_app() без аргументов затирал current_app пустой строкой.
   # Теперь перезапускаем эмуляцию на выбранном профиле с новым устройством.
   self.change_app()
   self.apply_settings_now()

 def change(self, window, new_name, old_name, res, count, labels):  # Окно изменение названия игры
  new_name_text = new_name.text()  # print(new_name_text, old_name, end=" , ")
  if new_name_text != "" and new_name_text != old_name:
   res["paths"][list(res["paths"])[count]] = new_name_text
   labels[count].setText(new_name_text)  # res["paths"][dict_save.get_cur_app()] = new_name.get()
   dict_save.save_jnson(res)
  window.close()  # Закрытие окна после сохранения изменений

  # Обновляем привязки событий
  self.update_labels_bindings()

 def change_name_label(self, count):  # Изменить название игры
  window = QDialog()  # основа
  window.setWindowTitle("change_name")  # заголовок
  window.resize(350, 150)  # Ширина и высота
  window.move(750, 400)  # x и y координаты на экране

  labels = dict_save.return_labels()
  res = dict_save.return_jnson()
  old_name = res["paths"][list(res["paths"])[count]]  # Получить прежнее название игры

  layout = QVBoxLayout()

  new_name = QLineEdit()
  new_name.setFixedWidth(250)  # Аналог width=25 в Tkinter (примерно)
  new_name.setText(old_name)
  new_name.setFocus()  # Фокусируемся на текстовом поле
  layout.addWidget(new_name)

  # Кнопка теперь является частью нового диалогового окна `window`
  ok_button = QPushButton("Ok")
  ok_button.clicked.connect(lambda: self.change(window, new_name, old_name, res, count, labels))
  layout.addWidget(ok_button)

  # Bind Enter key to change function
  new_name.returnPressed.connect(lambda: self.change(window, new_name, old_name, res, count, labels))

  window.setLayout(layout)
  window.exec()  # Показать модальное окно (аналог grid placement)

 def label_clicked(self, event, count):
  if event.button() == Qt.MouseButton.LeftButton:
   self.check_label_changed(count)
  if event.type() == QEvent.Type.MouseButtonDblClick:  #    print(11111)
   self.change_name_label(count)  # изменить название игры

 def check_mouse_press_button(self, count, state):
  res = dict_save.return_jnson()
  curr_name = dict_save.get_cur_app()

  if curr_name not in res.get("mouse_press", {}):
   res["mouse_press"][curr_name] = [False] * 7
  res["mouse_press"][curr_name][count] = bool(state)
  # «Удерживать» и «Повторить» взаимоисключающие: включая hold, снимаем repeat.
  if bool(state):
   repeat_widgets = getattr(self, "mouse_repeat_check_buttons", [])
   if count < len(repeat_widgets):
    repeat_widgets[count].blockSignals(True)
    repeat_widgets[count].setChecked(False)
    repeat_widgets[count].blockSignals(False)
   repeats = res.setdefault("mouse_repeat", {}).setdefault(curr_name, [False] * 7)
   repeats += [False] * (7 - len(repeats))
   repeats[count] = False
   if not any(repeats):
    res["mouse_repeat"].pop(curr_name, None)
    if not res["mouse_repeat"]:
     res.pop("mouse_repeat", None)
  dict_save.save_jnson(res)
  self.apply_settings_now()

 def update_mouse_repeat(self, count, state):
  res = dict_save.return_jnson()
  curr_name = dict_save.get_cur_app()
  repeats = res.setdefault("mouse_repeat", {}).setdefault(curr_name, [False] * 7)
  repeats += [False] * (7 - len(repeats))
  repeats[count] = bool(state)
  # «Повторить» и «Удерживать» взаимоисключающие: включая repeat, снимаем hold.
  if bool(state):
   hold_widgets = getattr(self, "mouse_check_buttons", [])
   if count < len(hold_widgets):
    hold_widgets[count].blockSignals(True)
    hold_widgets[count].setChecked(False)
    hold_widgets[count].blockSignals(False)
   if curr_name not in res.get("mouse_press", {}):
    res["mouse_press"][curr_name] = [False] * 7
   res["mouse_press"][curr_name][count] = False
  if not any(repeats):
   res["mouse_repeat"].pop(curr_name, None)
   if not res["mouse_repeat"]:
    res.pop("mouse_repeat", None)
  dict_save.save_jnson(res)
  self.apply_settings_now()

 def update_mouse_hold_duration(self, count):
  res = dict_save.return_jnson()
  curr_name = dict_save.get_cur_app()
  durations = res.setdefault("mouse_hold_repeat_seconds", {}).setdefault(curr_name, [None] * 7)
  durations += [None] * (7 - len(durations))
  selected = self.mouse_hold_duration_combos[count].currentText().strip()
  durations[count] = int(selected) if selected in {str(v) for v in allowed_repeat_durations} else None
  if all(value is None for value in durations):
   res["mouse_hold_repeat_seconds"].pop(curr_name, None)
   if not res["mouse_hold_repeat_seconds"]:
    res.pop("mouse_hold_repeat_seconds", None)
  dict_save.save_jnson(res)
  self.apply_settings_now()

 def add_file(self):  # Добавить новые игры
  path_to_file = return_file_path(dict_save)
  if path_to_file is None:
   return 0
  res = dict_save.return_jnson()  # получаем настройки

  while self.games_layout.count():    # Очистка layout (аналог destroy и clear)
   child = self.games_layout.takeAt(0)
   if child.widget():
    child.widget().deleteLater()

  labels = dict_save.return_labels()
  name_games = dict_save.return_name_games()
  var_list = dict_save.return_var_list()
  labels_with_checkmark = dict_save.return_labels_with_checkmark()

  # Очистка списков
  labels.clear()
  name_games.clear()
  var_list.clear()
  labels_with_checkmark.clear()
  dict_save.count += 1  # Увеличиваем счётчик (исправлена опечатка)

  res['current_app'] = path_to_file  # Выбранная игра.
  dict_save.set_cur_app(path_to_file)
  dict_save.set_user_profile(path_to_file)
  dict_save.set_current_path_game(path_to_file)
  dict_save.save_jnson(res)

  # Установить белый цвет для всех label (аналог set_colol_white_label_changed)
  for label in labels:
   if isinstance(label, QLabel):
    label.setStyleSheet("background-color: white; border: 1px solid gray; padding: 5px;")

  self.filling_in_fields(dict_save)  # Перезаполнение полей (аналог filling_in_fields(res))

  # Копирование значений из box_values (QComboBox использует currentText())
  keys_values = dict_save.return_box_values()
  old_keys_values = []
  for i in range(len(keys_values)):
   old_keys_values.append(keys_values[i].currentText())

   # Выделяем НОВЫЙ профиль синим (он теперь стоит под активным, а не в конце —
   # ищем его индекс по current_app, а не labels[-1]).
   labels = dict_save.return_labels()  # Обновляем список после filling_in_fields
   res_now = dict_save.return_jnson()
   new_keys = list(res_now["paths"].keys())
   if res_now.get('current_app') in new_keys:
    new_index = new_keys.index(res_now['current_app'])
    if 0 <= new_index < len(labels):
     labels[new_index].setStyleSheet("background-color: #06c; color: white; border: 1px solid gray; padding: 5px;")

   # Обновление привязок (аналог update_buttons и bindings)
  self.update_labels_bindings()
  self.set_list_box(dict_save)  # Установка значений в combo_box, если нужно

 def delete(self):  # Удалить профиль.
  if dict_save.get_cur_app() == "C:/Windows/explorer.exe":  # Получить id устройства. Если id устройство не выбрали.
   msg_box = QMessageBox(self)
   msg_box.setWindowTitle("Ошибка")
   msg_box.setText("Вы выбрали профиль по умолчанию")
   ok_button = msg_box.addButton("Ок", QMessageBox.ButtonRole.AcceptRole)
   msg_box.exec()
   return
  profile = dict_save.get_cur_app()  # Текущая директория активной игры.
  res = dict_save.return_jnson()  # print(profile)
  list_paths = list(res["paths"].keys())
  del_index = list_paths.index(profile)
  res = remove_profile_keys(res, profile)  # Удаляем из JSON
  dict_save.save_jnson(res)  # Сохранить новые настройки.

  # Перестраиваем UI (удаление и сдвиг через перезаполнение)
  self.filling_in_fields(dict_save)

  # Выделяем новый активный label (первый после удаления, аналог check_label_changed(0, ...))
  labels = dict_save.return_labels()
  if labels and len(labels) > 0:
   self.check_label_changed(0)  # Выделяем индекс 0 (первый)

   # Обновляем привязки событий
  self.update_labels_bindings()

 def button_keyboard(self, index):
  pass

 def create_scrypt_buttons(self):
  pass

 def show_change_name_menu(self, count):
  pass




  # if isinstance(data_dict, dict) and data_dict and id_active != 0:
  #     key_paths = get_active_window_exe(user, id_active)  # print(key_paths)
  #     if key_paths == None or ".exe" and ".sh" not in key_paths.lower():
  #         return dict_save.get_prev_game()  # то есть мы возвышаемся директорию из get_prev_game
  #     if ".sh" in key_paths.lower():
  #         key_paths1 = os.path.basename(key_paths.split()[-1])[:-3]  # Берём всё после последнего '/'
  #         file_path2 = next((p for p in games_checkmark_paths if key_paths1.lower() in p.lower()), None)  #
  #         if file_path2 and ".exe" in file_path2.lower():  # print(file_path2)
  #             return games_checkmark_paths[get_index_of_path(file_path2, games_checkmark_paths)]
    
    
    
    

# === Editor_settings_for_Xbox360.py (эмуляция геймпада) ===

IMAGE_PATH = os.path.join(os.getcwd(), "gamepad xbox 360.png")
SETTINGS_FILE = Path.cwd() / "editor_for_Xbox360_app_settings.json"  # Файл настроек

# Маппинг логических имен кнопок геймпада в коды ecodes
GAMEPAD_EC = { "A": ecodes.BTN_A, "B": ecodes.BTN_B, "X": ecodes.BTN_X, "Y": ecodes.BTN_Y,
 "LEFT_SHOULDER": ecodes.BTN_TL, "RIGHT_SHOULDER": ecodes.BTN_TR, "LEFT_TRIGGER": ecodes.ABS_Z,
 "RIGHT_TRIGGER": ecodes.ABS_RZ, "GUIDE": ecodes.BTN_MODE, "BACK": ecodes.BTN_SELECT, "START": ecodes.BTN_START,
 "DPAD_UP": ecodes.ABS_HAT0Y, "DPAD_DOWN": ecodes.ABS_HAT0Y, "DPAD_LEFT": ecodes.ABS_HAT0X,
 "DPAD_RIGHT": ecodes.ABS_HAT0X, "LEFT_THUMB_UP": ecodes.ABS_Y, "LEFT_THUMB_DOWN": ecodes.ABS_Y,
 "LEFT_THUMB_LEFT": ecodes.ABS_X, "LEFT_THUMB_RIGHT": ecodes.ABS_X, "RIGHT_THUMB_UP": ecodes.ABS_RY,
 "RIGHT_THUMB_DOWN": ecodes.ABS_RY, "RIGHT_THUMB_LEFT": ecodes.ABS_RX, "RIGHT_THUMB_RIGHT": ecodes.ABS_RX,
 "LEFT_THUMB_PRESSED": ecodes.BTN_THUMBL, "RIGHT_THUMB_PRESSED": ecodes.BTN_THUMBR}

# Кнопки, для которых применим комбинированный режим (hold/repeat + обычное нажатие)
# D-pad и стики обрабатываются немедленно (несколько логических кнопок на одну ось)
SIMPLE_BUTTONS = {"A", "B", "X", "Y", "LEFT_SHOULDER", "RIGHT_SHOULDER",
                  "LEFT_TRIGGER", "RIGHT_TRIGGER", "GUIDE", "BACK", "START",
                  "LEFT_THUMB_PRESSED", "RIGHT_THUMB_PRESSED"}

# ======================================================================
# ПОТОК ЭМУЛЯЦИИ ГЕЙМПАДА
# Принцип: обычные маппинги и триггерные режимы (hold/repeat) хранятся
# раздельно. Для кнопок с триггерным режимом вычисляется комбинированное
# состояние: hold ИЛИ repeat_импульс ИЛИ обычное_нажатие.
# Это позволяет одной клавише делать обычное нажатие, а другой —
# удержание той же кнопки геймпада без конфликтов.
# ======================================================================
class Worker(QThread):
 status_sig = pyqtSignal(str)
 error_sig = pyqtSignal(str)

 def __init__(self, keymap, trigger_modes, mouse_on, sens_x, sens_y, smooth, grab):
  # keymap — словарь обычных маппингов (строки: "RIGHT_TRIGGER" -> "KEY_N")
  # trigger_modes — словарь триггерных режимов ("RIGHT_TRIGGER" -> {"key":"KEY_H","mode":"hold"})
  super().__init__()
  self.km = keymap
  self.tm = trigger_modes
  self.mouse_on = bool(mouse_on)
  self.sens_x = max(1, min(15, int(sens_x)))
  self.sens_y = max(1, min(15, int(sens_y)))
  self.smooth, self.grab = smooth, grab
  self.running = False
  self.ui = None
  self.kb_dev, self.m_dev = None, None
  self.kb_grabbed = False
  self.hat = {"x": 0, "y": 0}
  self.m_rx, self.m_ry = 0.0, 0.0
  self.kb_rx, self.kb_ry = 0, 0
  self.smoother = deque(maxlen=20)
  # Состояния триггерных режимов
  self.hold_states = {}        # logical_name -> bool (включено ли удержание)
  self.repeat_active = {}      # logical_name -> bool (активен ли повтор)
  self.repeat_start_time = {}  # logical_name -> float (время начала повтора)
  self.REPEAT_PERIOD = 0.1    # Полный цикл повтора: 50мс вкл + 50мс выкл
  # Отслеживание физически нажатых клавиш (key_code)
  self.physically_pressed = set()
  # Последнее отправленное значение для каждой кнопки (чтобы не слать дубли)
  self.last_output = {}
  # Набор кнопок, для которых применяется комбинированная логика
  self.combined_set = set()
  # Обратный маппинг: logical_name -> [key_codes] для обычных нажатий
  self.normal_logical_to_keys = {}

 def run(self):  # Поиск клавиатуры Logitech (исключая Consumer и System)
  self.kb_dev = None
  for path in glob.glob("/dev/input/event*"):
   try:
    dev = evdev.InputDevice(path)
    if "Logitech" in dev.name and "Keyboard" in dev.name and "Consumer" not in dev.name and "System" not in dev.name:
     self.kb_dev = dev
     break
   except:
    continue

  if not self.kb_dev:  # Резервный поиск любой подходящей клавиатуры
   skip = ("xbox", "x-box", "gamepad", "pad", "virtual", "uinput", "microsoft", "xenia", "360", "consumer", "system")
   self.kb_dev = next((evdev.InputDevice(p) for p in evdev.list_devices()
                       if not any(w in evdev.InputDevice(p).name.lower() for w in skip)
                       and ecodes.EV_KEY in evdev.InputDevice(p).capabilities()
                       and ecodes.KEY_A in evdev.InputDevice(p).capabilities()[ecodes.EV_KEY]), None)

  if not self.kb_dev:
   self.error_sig.emit("Клавиатура не найдена!")
   return

  # ------------------------------------------------------------
  # Определение текущего состояния NumLock и установка LED
  # ------------------------------------------------------------
  self.numlock_state = 0
  try:
   import subprocess
   result = subprocess.run(['xset', 'q'], capture_output=True, text=True, timeout=1)
   for line in result.stdout.split('\n'):
    if 'Num Lock' in line:
     self.numlock_state = 1 if 'on' in line.lower() else 0
     break
  except Exception:
   try:
    import glob as glob2
    led_files = glob2.glob("/sys/class/leds/input*::numlock/brightness")
    if led_files:
     with open(led_files[0], 'r') as f:
      val = f.read().strip()
      self.numlock_state = 1 if int(val) > 0 else 0
   except Exception:
    pass

  # Устанавливаем LED NumLock на устройстве
  self.kb_dev.write(ecodes.EV_LED, ecodes.LED_NUML, self.numlock_state)
  self.kb_dev.syn()

  try:
   if self.grab:  # Захват клавиатуры (перехват всех событий)
    self.kb_dev.grab()
    self.kb_grabbed = True
  except Exception as e:
   self.error_sig.emit(f"Ошибка захвата: {e}")
   return

  # Поиск мыши
  self.m_dev = None
  if self.mouse_on:
   self.m_dev = next((evdev.InputDevice(p) for p in evdev.list_devices()
                      if ecodes.EV_REL in evdev.InputDevice(p).capabilities()
                      and ecodes.EV_KEY in evdev.InputDevice(p).capabilities()
                      and ecodes.REL_X in evdev.InputDevice(p).capabilities()[ecodes.EV_REL]), None)
   if not self.m_dev:
    # Без устройства мыши режим нельзя включить. Важно освободить уже
    # захваченную клавиатуру, иначе она могла бы остаться заблокированной.
    self._clean()
    self.error_sig.emit("Мышь не найдена!")
    return

  # Создание виртуального геймпада Xbox 360
  try:
   cap = {ecodes.EV_KEY: [ecodes.BTN_A, ecodes.BTN_B, ecodes.BTN_X, ecodes.BTN_Y, ecodes.BTN_TL, ecodes.BTN_TR, ecodes.BTN_START, ecodes.BTN_SELECT, ecodes.BTN_MODE, ecodes.BTN_THUMBL, ecodes.BTN_THUMBR],
          ecodes.EV_ABS: [(ecodes.ABS_X, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_Y, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)),
                          (ecodes.ABS_RX, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_RY, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),
                          (ecodes.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)), (ecodes.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0))]}
   self.ui = UInput(cap, name="Microsoft X-Box 360 pad", vendor=0x045e, product=0x028e, version=0x0114, bustype=ecodes.BUS_USB)
   time.sleep(0.3)
   self._neutral()
  except Exception as e:
   self.error_sig.emit(f"UInput ошибка: {e}")
   self._clean()
   return

  self.running = True
  msg = f"Активно | KB: {self.kb_dev.name}"
  self.status_sig.emit(msg)

  # ------------------------------------------------------------
  # Построение инвертированных маппингов
  # normal_inv: key_code -> [logical_names] — для обычных нажатий
  # trigger_inv: key_code -> [(logical_name, mode)] — для hold/repeat
  # ------------------------------------------------------------
  normal_inv = {}
  trigger_inv = {}
  for logical, val in self.km.items():
   # Пропускаем пустые строки и не-строки (на случай старого формата)
   if not isinstance(val, str) or not val:
    continue
   if hasattr(ecodes, val):
    k_code = getattr(ecodes, val)
    normal_inv.setdefault(k_code, []).append(logical)

  for logical, info in self.tm.items():
   if not isinstance(info, dict):
    continue
   key_str = info.get("key", "")
   mode = info.get("mode", "")
   if key_str and hasattr(ecodes, key_str):
    k_code = getattr(ecodes, key_str)
    trigger_inv.setdefault(k_code, []).append((logical, mode))

  # Обратный маппинг: logical -> [key_codes] для обычных нажатий
  self.normal_logical_to_keys = {}
  for k_code, logicals in normal_inv.items():
   for logical in logicals:
    self.normal_logical_to_keys.setdefault(logical, []).append(k_code)

  # Набор кнопок с триггерным режимом (только SIMPLE_BUTTONS — не стики/DPAD)
  self.combined_set = set()
  for logical, info in self.tm.items():
   if logical in SIMPLE_BUTTONS and isinstance(info, dict):
    self.combined_set.add(logical)

  fds = [self.kb_dev] + ([self.m_dev] if self.m_dev else [])

  # ===================== ГЛАВНЫЙ ЦИКЛ =====================
  while self.running:
   r, _, _ = select(fds, [], [], 0.02)
   for d in r:
    try:
     for ev in d.read():
      if d is self.kb_dev and ev.type == ecodes.EV_KEY:
       p = ev.value in (1, 2)  # True при нажатии или автоповторе ядра

       # ESC — остановка эмуляции
       if ev.code == ecodes.KEY_ESC and p:
        self.running = False
        break

       # Обновляем множество физически нажатых клавиш
       if ev.value == 1 or ev.value == 2:
        self.physically_pressed.add(ev.code)
       elif ev.value == 0:
        self.physically_pressed.discard(ev.code)

       # === Триггерные режимы (hold/repeat) — приоритет ===
       if ev.code in trigger_inv:
        for logical, mode in trigger_inv[ev.code]:
         self._handle_trigger_key(logical, mode, ev.value)

       # === Обычные маппинги ===
       elif ev.code in normal_inv:
        for logical in normal_inv[ev.code]:
         if logical in self.combined_set:
          # Кнопка с триггерным режимом — НЕ отправляем сразу,
          # состояние будет вычислено ниже в комбинированной логике
          pass
         else:
          # Обычная кнопка без триггерного режима — немедленная отправка
          self._dispatch(logical, p)

      elif d is self.m_dev:
       self._mouse_ev(ev)
    except:
     self.running = False
     self.error_sig.emit("Устройство отключилось!")
     break

   # --------------------------------------------------------
   # Комбинированная логика для кнопок с триггерными режимами
   # Вычисляем итоговое состояние: hold OR repeat_пульс OR обычное_нажатие
   # --------------------------------------------------------
   now = time.time()
   for logical in self.combined_set:
    # Проверяем удержание (hold) — переключается по нажатию
    hold_active = self.hold_states.get(logical, False)

    # Проверяем повтор (repeat) — пульсация: 50мс вкл, 50мс выкл
    repeat_on = False
    if self.repeat_active.get(logical, False):
     start = self.repeat_start_time.get(logical, now)
     elapsed = now - start
     phase = elapsed % self.REPEAT_PERIOD
     repeat_on = phase < (self.REPEAT_PERIOD / 2)  # Первая половина цикла — включено

    # Проверяем, нажата ли обычная клавиша для этой кнопки
    normal_on = False
    if logical in self.normal_logical_to_keys:
     for k in self.normal_logical_to_keys[logical]:
      if k in self.physically_pressed:
       normal_on = True
       break

    # Итоговое состояние: включено, если ХОТЯ БЫ ОДИН источник активен
    desired = hold_active or repeat_on or normal_on

    # Определяем выходное значение (аналоговый триггер: 0/255, кнопка: 0/1)
    if logical in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
     output_val = 255 if desired else 0
    else:
     output_val = 1 if desired else 0

    # Отправляем только если значение изменилось (избегаем лишних событий)
    last_val = self.last_output.get(logical, 0)
    if output_val != last_val:
     ec = GAMEPAD_EC.get(logical)
     if ec is not None:
      if logical in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
       self.ui.write(ecodes.EV_ABS, ec, output_val)
      else:
       self.ui.write(ecodes.EV_KEY, ec, output_val)
      self.ui.syn()
      self.last_output[logical] = output_val

   # Затухание мыши (右 стик эмуляция)
   self.m_rx *= 0.85
   self.m_ry *= 0.85
   if abs(self.m_rx) < 200: self.m_rx = 0
   if abs(self.m_ry) < 200: self.m_ry = 0
   rx = self.kb_rx if self.kb_rx != 0 else int(self.m_rx)
   ry = self.kb_ry if self.kb_ry != 0 else int(self.m_ry)
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RX, rx)
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RY, ry)
   self.ui.syn()

  self._clean()

 def _handle_trigger_key(self, logical, mode, ev_value):
  """Обрабатывает нажатие клавиши для триггерного режима (hold/repeat).
     НЕ отправляет события напрямую — это делает комбинированная логика."""
  if mode == "hold":
   # Переключение при нажатии (value=1), игнорируем автоповтор (value=2)
   if ev_value == 1:
    current = self.hold_states.get(logical, False)
    self.hold_states[logical] = not current
  elif mode == "repeat":
   if ev_value == 1:  # Начало повтора
    self.repeat_active[logical] = True
    self.repeat_start_time[logical] = time.time()
   elif ev_value == 0:  # Остановка повтора
    self.repeat_active[logical] = False
    self.repeat_start_time.pop(logical, None)

 def _mouse_ev(self, ev):
  """Преобразует движение мыши в оси правого стика и её кнопки в действия геймпада."""
  if ev.type == ecodes.EV_REL:
   # Игнорируем колесо и прочие относительные события: иначе они добавляли
   # нулевые значения в сглаживание и временно ухудшали отклик стика.
   if ev.code not in (ecodes.REL_X, ecodes.REL_Y):
    return
   dx = ev.value * self.sens_x if ev.code == ecodes.REL_X else 0
   dy = ev.value * self.sens_y if ev.code == ecodes.REL_Y else 0
   self.smoother.append((dx, dy))
   if self.smooth:
    dx = sum(item[0] for item in self.smoother) / len(self.smoother)
    dy = sum(item[1] for item in self.smoother) / len(self.smoother)
   self.m_rx = max(-32767, min(32767, self.m_rx + dx * 40))
   self.m_ry = max(-32767, min(32767, self.m_ry + dy * 40))
  elif ev.type == ecodes.EV_KEY:
   pressed = 1 if ev.value else 0
   if ev.code == ecodes.BTN_LEFT:
    self.ui.write(ecodes.EV_ABS, ecodes.ABS_RZ, 255 if pressed else 0)
   elif ev.code == ecodes.BTN_RIGHT:
    self.ui.write(ecodes.EV_ABS, ecodes.ABS_Z, 255 if pressed else 0)
   elif ev.code == ecodes.BTN_MIDDLE:
    self.ui.write(ecodes.EV_KEY, ecodes.BTN_THUMBR, pressed)
   else:
    return
   self.ui.syn()

 def _dispatch(self, t, p):
  """Немедленная отправка события для кнопок БЕЗ триггерного режима
     (D-pad, стики, и обычные кнопки без hold/repeat)"""
  if t in GAMEPAD_EC:
   ec = GAMEPAD_EC[t]
   if t.startswith("DPAD"):
    # D-pad: несколько направлений на одну ось
    if "LEFT" in t:   ax, v = ecodes.ABS_HAT0X, -1 if p else 0
    elif "RIGHT" in t: ax, v = ecodes.ABS_HAT0X, 1 if p else 0
    elif "UP" in t:   ax, v = ecodes.ABS_HAT0Y, -1 if p else 0
    else:             ax, v = ecodes.ABS_HAT0Y, 1 if p else 0  # DOWN
    self.ui.write(ecodes.EV_ABS, ax, v)
   elif t in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
    # Аналоговые триггеры: 0 или 255
    self.ui.write(ecodes.EV_ABS, ec, 255 if p else 0)
   elif "THUMB" in t and "PRESSED" not in t:
    # Стики: направление берём ТОЛЬКО из последней части имени (UP/DOWN/LEFT/RIGHT).
    # Иначе "LEFT_THUMB_RIGHT" ошибочно совпадает с подстрокой "LEFT".
    # Стандарт Xbox: вверх/влево = отрицательное, вниз/вправо = положительное.
    direction = t.rsplit("_", 1)[-1]
    F = 32767
    if direction == "UP":
     val = -F if p else 0
    elif direction == "DOWN":
     val = F if p else 0
    elif direction == "LEFT":
     val = -F if p else 0
    elif direction == "RIGHT":
     val = F if p else 0
    else:
     val = 0
    if "RIGHT_THUMB" in t:
     # Правый стик: пишем через kb_rx/kb_ry (комбинируется с мышью)
     if direction in ("LEFT", "RIGHT"):
      self.kb_rx = val
     elif direction in ("UP", "DOWN"):
      self.kb_ry = val
    else:
     self.ui.write(ecodes.EV_ABS, ec, val)
   else:
    # Обычные цифровые кнопки (A, B, X, Y, плечи, и т.д.)
    self.ui.write(ecodes.EV_KEY, ec, int(p))
   self.ui.syn()

 def _neutral(self):
  """Установка всех осей и триггеров в нейтральное положение"""
  for a in [ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_RX, ecodes.ABS_RY, ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y]:
   self.ui.write(ecodes.EV_ABS, a, 0)
  for a in [ecodes.ABS_Z, ecodes.ABS_RZ]:
   self.ui.write(ecodes.EV_ABS, a, 0)
  self.ui.syn()

 def _clean(self):
  """Освобождение ресурсов: отжим кнопок, закрытие устройств"""
  if self.kb_dev and self.kb_grabbed:
   try:
    self.kb_dev.ungrab()
   except:
    pass
   self.kb_grabbed = False
  if self.ui:
   try:
    self._neutral()
    self.ui.close()
   except:
    pass
   self.ui = None

 def stop(self):
  self.running = False
  self.wait(2000)


# ======================================================================
# МЕНЕДЖЕР ПРОФИЛЕЙ
# Хранит обычные маппинги (profiles) и триггерные режимы (trigger_modes)
# РАЗДЕЛЬНО, чтобы одна кнопка геймпада могла иметь одновременно
# и обычное нажатие, и hold/repeat от разных клавиш клавиатуры.
# ======================================================================
class ProfileManager:
 def __init__(self):
  self.profiles = {}           # Имя профиля -> {логическая_кнопка: "KEY_X"}
  self.trigger_modes = {}      # Имя профиля -> {логическая_кнопка: {"key":"KEY_X","mode":"hold"}}
  self.current_profile = "Default"

 def load_profiles(self, data):
  """Загрузка профилей и триггерных режимов из JSON с миграцией старого формата"""
  self.profiles = data.get("profiles", {})
  if not self.profiles:
   self.profiles["Default"] = KEY_MAPPER.default_mapping()
  self.current_profile = data.get("last_profile", "Default")
  if self.current_profile not in self.profiles:
   self.current_profile = "Default"

  # Загрузка триггерных режимов (новый формат)
  self.trigger_modes = data.get("trigger_modes", {})

  # Миграция: если в старом профиле есть dict-значения, переносим в trigger_modes
  for profile_name, mapping in self.profiles.items():
   migrated = False
   for logical, val in list(mapping.items()):
    if isinstance(val, dict):
     # Старый формат: {"key":"KEY_H","mode":"hold"} прямо в маппинге
     key = val.get("key", "")
     mode = val.get("mode", "hold")
     if profile_name not in self.trigger_modes:
      self.trigger_modes[profile_name] = {}
     self.trigger_modes[profile_name][logical] = {"key": key, "mode": mode}
     mapping[logical] = ""  # Очищаем обычный маппинг (пользователь назначит заново)
     migrated = True
   if migrated:
    # Убеждаемся что ключ профиля есть в trigger_modes
    if profile_name not in self.trigger_modes:
     self.trigger_modes[profile_name] = {}

 def get_mapping(self):
  """Возвращает обычные маппинги текущего профиля (только строки)"""
  return self.profiles.get(self.current_profile, KEY_MAPPER.default_mapping())

 def get_trigger_modes(self):
  """Возвращает триггерные режимы текущего профиля"""
  return self.trigger_modes.get(self.current_profile, {})

 def update_mapping(self, logical, key_str):
  """Обновляет обычный маппинг для кнопки (строковое значение клавиши)"""
  if self.current_profile in self.profiles:
   if isinstance(key_str, dict):
    # На случай старого формата — переносим в trigger_modes
    if self.current_profile not in self.trigger_modes:
     self.trigger_modes[self.current_profile] = {}
    self.trigger_modes[self.current_profile][logical] = key_str
    self.profiles[self.current_profile][logical] = ""
   else:
    self.profiles[self.current_profile][logical] = key_str

 def set_trigger_mode(self, logical, mode, key):
  """Устанавливает триггерный режим (hold/repeat) для кнопки.
     Сохраняется ОТДЕЛЬНО от обычного маппинга."""
  if self.current_profile not in self.trigger_modes:
   self.trigger_modes[self.current_profile] = {}
  self.trigger_modes[self.current_profile][logical] = {"key": key, "mode": mode}

 def clear_trigger_mode(self, logical):
  """Удаляет триггерный режим для кнопки. Обычный маппинг НЕ затрагивается."""
  if self.current_profile in self.trigger_modes:
   if logical in self.trigger_modes[self.current_profile]:
    del self.trigger_modes[self.current_profile][logical]

 def new_profile(self, name, template_name=None):
  """Создаёт новый профиль (копируя маппинги из шаблона)"""
  if name in self.profiles:
   return False
  if template_name and template_name in self.profiles:
   self.profiles[name] = self.profiles[template_name].copy()
  else:
   self.profiles[name] = KEY_MAPPER.default_mapping()
  # Копируем триггерные режимы из шаблона
  if template_name and template_name in self.trigger_modes:
   self.trigger_modes[name] = {}
   for k, v in self.trigger_modes[template_name].items():
    self.trigger_modes[name][k] = v.copy()
  return True

 def delete_profile(self, name):
  """Удаляет профиль (кроме 'Default')"""
  if name in self.profiles and name != "Default":
   del self.profiles[name]
   if name in self.trigger_modes:
    del self.trigger_modes[name]
   return True
  return False


# ======================================================================
# КОНТРОЛЛЕР ПРИЛОЖЕНИЯ — связывает UI с логикой профилей и воркером
# ======================================================================
class AppController:
 def __init__(self, window: MainWindow):
  self.window = window
  self.pm = ProfileManager()
  self.worker = None
  self._current_image_path = IMAGE_PATH

  # Привязка сигналов UI
  self.window.gamepad.zone_clicked.connect(self._on_zone_clicked)
  self.window.profile_combo.currentTextChanged.connect(self._on_profile_select)
  self.window.btn_create.clicked.connect(self._new_profile)
  self.window.btn_delete.clicked.connect(self._delete_profile)
  self.window.btn_defaults.clicked.connect(self._set_defaults)
  self.window.btn_img.clicked.connect(self._browse_image)
  self.window.btn_start.clicked.connect(self._toggle_emulation)
  self.window.mouse_mode_toggled.connect(self._on_mouse_mode_changed)
  self.window.closing.connect(self._save_app_settings)
  self.window.gamepad.zones_changed.connect(self._save_app_settings)

  # Горячая клавиша F3 для отладки
  sc = QAction(self.window)
  sc.setShortcut(QKeySequence("F3"))
  sc.triggered.connect(lambda: self.window.debug_cb.setChecked(not self.window.debug_cb.isChecked()))
  self.window.addAction(sc)

  # Глобальная горячая клавиша End: остановить эмуляцию геймпада.
  # Используем библиотеку keyboard (ловит клавишу даже когда окно не в фокусе,
  # например когда Condemned 2 запущен через gamescope на весь экран).
  # respect_all=False не нужен: End не является модификатором.
  keyboard.on_press_key("end", lambda _e: self._stop_emulation_hotkey())

  # Сигналы панели триггерных режимов
  self.window.trigger_button_combo.currentIndexChanged.connect(self._on_trigger_button_changed)
  self.window.trigger_mode_combo.currentIndexChanged.connect(self._on_trigger_mode_changed)
  self.window.trigger_key_btn.clicked.connect(self._on_trigger_key_clicked)
  self.window.trigger_clear_btn.clicked.connect(self._on_trigger_clear)

  # Инициализация
  self._load_app_settings()
  self._refresh_combo()
  self._refresh_bindings()
  self._sync_trigger_ui()       # Восстановление UI из загруженных настроек
  self._update_trigger_status()
  self._start_emulation()       # Автоматический запуск эмуляции

 def _load_app_settings(self):
  """Загрузка всех настроек из JSON файла"""
  if SETTINGS_FILE.exists():
   try:
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
     data = json.load(f)
    if data.get("image_path") and os.path.exists(data["image_path"]):
     self._current_image_path = data["image_path"]
    self.window.gamepad.set_image(self._current_image_path)
    if data.get("zones"):
     self.window.gamepad.set_zones_data(data["zones"])
    self.pm.load_profiles(data)  # Загружает профили + триггерные режимы + миграция
    # Поддержка старого формата: единая sens применяется к обеим осям,
    # если отдельных значений sens_x/sens_y ещё нет.
    legacy_sens = data.get("sens", 5)
    self.window.set_mouse_enabled(data.get("mouse_on", False))
    self.window.set_mouse_settings(data.get("sens_x", legacy_sens), data.get("sens_y", legacy_sens))
    self.window.chk_smooth.setChecked(data.get("smooth", True))
    self.window.chk_grab.setChecked(data.get("grab", True))
   except:
    self.pm.load_profiles({})
  else:
   self.pm.load_profiles({})
  self.window.gamepad.set_image(self._current_image_path)

 def _save_app_settings(self):
  """Сохранение ВСЕХ настроек в JSON (профили + триггерные режимы раздельно)"""
  data = {
   "image_path": self._current_image_path,
   "zones": self.window.gamepad.get_zones_data(),
   "last_profile": self.pm.current_profile,
   "profiles": self.pm.profiles,
   "trigger_modes": self.pm.trigger_modes,  # Триггерные режимы отдельно от маппингов
   "mouse_on": self.window.mouse_enabled(),
   # sens оставлен для совместимости со старыми версиями приложения.
   "sens": self.window.mouse_sens_x,
   "sens_x": self.window.mouse_sens_x,
   "sens_y": self.window.mouse_sens_y,
   "smooth": self.window.chk_smooth.isChecked(),
   "grab": self.window.chk_grab.isChecked()
  }
  try:
   with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
  except:
   pass

 def _refresh_combo(self):
  """Обновление выпадающего списка профилей"""
  self.window.profile_combo.blockSignals(True)
  self.window.profile_combo.clear()
  for p in self.pm.profiles:
   display = p.capitalize() if p != "Default" else "Default"
   self.window.profile_combo.addItem(display, p)
  idx = self.window.profile_combo.findData(self.pm.current_profile)
  if idx >= 0:
   self.window.profile_combo.setCurrentIndex(idx)
  self.window.profile_combo.blockSignals(False)

 def _refresh_bindings(self):
  """Обновление отображения привязок на изображении геймпада и перезапуск эмуляции"""
  mapping = self.pm.get_mapping()
  self.window.gamepad.update_all_bindings(mapping)
  if self.worker and self.worker.isRunning():
   self._start_emulation()  # Перезапуск для применения изменений

 def _on_zone_clicked(self, logical_name):
  """Клик по зоне геймпада — назначение обычной клавиши"""
  def callback(key):
   self.pm.update_mapping(logical_name, key)
   self._refresh_bindings()
   self._save_app_settings()
   self._update_trigger_status()
  VirtualKeyboard(self.window, callback).exec()

 def _on_profile_select(self, text):
  """Смена текущего профиля"""
  raw = self.window.profile_combo.currentData()
  if raw and raw != self.pm.current_profile:
   self.pm.current_profile = raw
   self._refresh_bindings()
   self._save_app_settings()
   self._sync_trigger_ui()       # Обновляем панель триггеров
   self._update_trigger_status()

 def _new_profile(self):
  """Создание нового профиля"""
  n, ok = QInputDialog.getText(self.window, "Создать профиль", "Имя профиля:")
  if ok and n.strip():
   if self.pm.new_profile(n.strip(), template_name=self.pm.current_profile):
    self.pm.current_profile = n.strip()
    self._refresh_combo()
    idx = self.window.profile_combo.findData(n.strip())
    if idx >= 0:
     self.window.profile_combo.setCurrentIndex(idx)
    self._refresh_bindings()
    self._save_app_settings()
    self._sync_trigger_ui()
    self._update_trigger_status()
   else:
    QMessageBox.warning(self.window, "Ошибка", "Профиль уже существует")

 def _delete_profile(self):
  """Удаление текущего профиля (кроме Default)"""
  if self.pm.current_profile == "Default":
   QMessageBox.warning(self.window, "Ошибка", "Нельзя удалить 'Default'")
   return
  if QMessageBox.question(self.window, "Подтверждение", f"Удалить '{self.pm.current_profile}'?") == QMessageBox.StandardButton.Yes:
   self.pm.delete_profile(self.pm.current_profile)
   self.pm.current_profile = "Default"
   self._refresh_combo()
   self._refresh_bindings()
   self._save_app_settings()
   self._sync_trigger_ui()
   self._update_trigger_status()

 def _set_defaults(self):
  """Сброс всех привязок текущего профиля к значениям по умолчанию"""
  if QMessageBox.question(self.window, "Подтверждение", "Сбросить привязки?") == QMessageBox.StandardButton.Yes:
   self.pm.profiles[self.pm.current_profile] = KEY_MAPPER.default_mapping()
   # Также очищаем триггерные режимы
   if self.pm.current_profile in self.pm.trigger_modes:
    self.pm.trigger_modes[self.pm.current_profile] = {}
   self._refresh_bindings()
   self._save_app_settings()
   self._sync_trigger_ui()
   self._update_trigger_status()

 def _browse_image(self):
  """Выбор изображения геймпада"""
  p, _ = QFileDialog.getOpenFileName(self.window, "Изображение геймпада", "", "Изображения (*.png *.jpg *.bmp *.webp)")
  if p:
   self._current_image_path = p
   self.window.gamepad.set_image(p)
   self._refresh_bindings()
   self._save_app_settings()

 def _toggle_emulation(self):
  """Переключение эмуляции: запуск/остановка"""
  if self.worker and self.worker.isRunning():
   self._stop_emulation()
  else:
   self._start_emulation()

 def _on_mouse_mode_changed(self, enabled):
  """Сохраняет переключение режима и применяет его без запуска, если он остановлен."""
  self._save_app_settings()
  if self.worker and self.worker.isRunning():
   self._start_emulation()

 def _start_emulation(self):
  """Запуск потока эмуляции геймпада"""
  self._stop_emulation()
  mapping = self.pm.get_mapping()           # Обычные маппинги (строки)
  trigger_modes = self.pm.get_trigger_modes()  # Триггерные режимы (dict)
  worker = Worker(mapping, trigger_modes,
                  self.window.mouse_enabled(), self.window.mouse_sens_x, self.window.mouse_sens_y,
                  self.window.chk_smooth.isChecked(), self.window.chk_grab.isChecked())
  # Сигналы привязаны к конкретному экземпляру. Это предотвращает ситуацию,
  # когда отложенный сигнал завершения старого потока останавливает уже новый.
  worker.status_sig.connect(self._update_status)
  worker.error_sig.connect(lambda error, source=worker: self._on_worker_error(source, error))
  worker.finished.connect(lambda source=worker: self._on_worker_finished(source))
  self.worker = worker
  worker.start()

 def _on_worker_error(self, source, error):
  """Показывает ошибку только активного потока эмуляции."""
  if self.worker is source:
   QMessageBox.critical(self.window, "Ошибка", error)
   self._stop_emulation()

 def _on_worker_finished(self, source):
  """Обрабатывает завершение только текущего, а не уже заменённого потока."""
  if self.worker is source:
   self.worker = None
   self.window.st_lbl.setText("Статус: Остановлен")
   self.window.st_lbl.setStyleSheet("font-weight: 600; color: #6C757D; font-size: 14px;")
   self.window.btn_start.setText("▶  ЗАПУСК  ЭМУЛЯЦИИ")
   self.window.btn_start.setStyleSheet("background:#198754;color:white;border:none;border-radius:4px;")

 def _update_status(self, msg):
  """Обновление строки статуса при успешном запуске"""
  self.window.st_lbl.setText(f"Статус: {msg}")
  self.window.st_lbl.setStyleSheet("font-weight: 600; color: #198754; font-size: 14px;")
  self.window.btn_start.setText("■  ОСТАНОВИТЬ")
  self.window.btn_start.setStyleSheet("background:#DC3545;color:white;border:none;border-radius:4px;")

 def _stop_emulation_hotkey(self):
  """Глобальный hotkey End -> остановка эмуляции.
  Библиотека keyboard вызывает это из своего потока, поэтому переключаем
  выполнение в GUI-поток через QTimer (безопасно для Qt-виджетов)."""
  QTimer.singleShot(0, self._stop_emulation)

 def _stop_emulation(self):
  """Остановка потока эмуляции"""
  if self.worker:
   self.worker.stop()
   self.worker = None
  self.window.st_lbl.setText("Статус: Остановлен")
  self.window.st_lbl.setStyleSheet("font-weight: 600; color: #6C757D; font-size: 14px;")
  self.window.btn_start.setText("▶  ЗАПУСК  ЭМУЛЯЦИИ")
  self.window.btn_start.setStyleSheet("background:#198754;color:white;border:none;border-radius:4px;")

 # -------------------- Панель триггерных режимов --------------------

 def _on_trigger_button_changed(self):
  """Смена выбранной кнопки в выпадающем списке триггеров"""
  self._update_trigger_status()

 def _on_trigger_mode_changed(self):
  """Смена режима (hold/repeat) в выпадающем списке"""
  self._update_trigger_status()

 def _on_trigger_key_clicked(self):
  """Назначение клавиши для триггерного режима выбранной кнопки"""
  logical = self.window.trigger_button_combo.currentText()
  mode_index = self.window.trigger_mode_combo.currentIndex()
  mode = "hold" if mode_index == 0 else "repeat"

  def callback(key):
   self.pm.set_trigger_mode(logical, mode, key)  # Сохраняем ОТДЕЛЬНО от обычного маппинга
   self._refresh_bindings()
   self._save_app_settings()
   self._sync_trigger_ui()
   self._update_trigger_status()
   # Перезапуск эмуляции для применения
   if self.worker and self.worker.isRunning():
    self._start_emulation()

  VirtualKeyboard(self.window, callback).exec()

 def _on_trigger_clear(self):
  """Очистка триггерного режима для выбранной кнопки (обычный маппинг НЕ затрагивается)"""
  logical = self.window.trigger_button_combo.currentText()
  self.pm.clear_trigger_mode(logical)
  self._refresh_bindings()
  self._save_app_settings()
  self._sync_trigger_ui()
  self._update_trigger_status()
  if self.worker and self.worker.isRunning():
   self._start_emulation()

 def _update_trigger_status(self):
  """Обновление метки статуса для выбранной кнопки триггера"""
  logical = self.window.trigger_button_combo.currentText()
  trigger_modes = self.pm.get_trigger_modes()
  val = trigger_modes.get(logical)
  if isinstance(val, dict):
   key_display = KEY_MAPPER.to_display(val.get("key", ""))
   mode = val.get("mode", "")
   mode_display = "Удержание" if mode == "hold" else "Повтор"
   self.window.trigger_status_label.setText(f"{logical}: {key_display} ({mode_display})")
  else:
   self.window.trigger_status_label.setText(f"{logical}: обычный")

 def _sync_trigger_ui(self):
  """Синхронизация панели триггеров с загруженными настройками.
     Восстанавливает и кнопку, и режим (hold/repeat) в выпадающих списках."""
  trigger_modes = self.pm.get_trigger_modes()
  target_logical = None
  target_mode = None
  # Ищем первую кнопку с назначенным триггерным режимом
  for logical, val in trigger_modes.items():
   if isinstance(val, dict):
    target_logical = logical
    target_mode = val.get("mode", "hold")
    break
  if target_logical:
   # Устанавливаем выбранную кнопку в выпадающем списке
   idx = self.window.trigger_button_combo.findText(target_logical)
   if idx >= 0:
    self.window.trigger_button_combo.setCurrentIndex(idx)
   # Восстанавливаем режим (hold/repeat) в выпадающем списке
   if target_mode:
    mode_idx = 0 if target_mode == "hold" else 1
    self.window.trigger_mode_combo.setCurrentIndex(mode_idx)

# === mouse_app.py (окно настроек мыши) ===

class MouseSettingApp(QMainWindow, MouseSettingAppMethods):
 def __init__(self):
  super().__init__()
  self.keyboard_editor = None
  self.a_scrypt = []
  self.combo_box = []
  self.creat = 0
  self.mouse_button_labels = []
  self.mouse_button_combos = []
  self.mouse_check_buttons = []
  self.mouse_repeat_check_buttons = []
  self.mouse_hold_duration_combos = []
  self.buttons_script = []
  self.board = None
  data = dict_save.data
  if os.path.exists(data):
   with open(data) as json_file:
   # strict=False: разрешаем реальные переносы строк внутри bash-скриптов (script_mouse / keyboard_script)
    root = json.load(json_file, strict=False)
    res = root.get("mouse_data", root)  # единый settings.json или старый формат
    res = scripts_to_text(res)  # убрать отступы продолжения строк из скриптов (нормализация)
    res = ensure_additional_exe(res)  # дозаполнить ключ additional_exe (все .exe директорий путей)
    res = ensure_mouse_id_name(res)  # дозаполнить ключ id_name (стабильное имя мыши — выдерживает перенумерацию xinput-id)
    dict_save.save_old_data(res)
   dict_save.save_jnson(res)
  else:
   res = {'games_checkmark': {'C:/Windows/explorer.exe': True},
    'paths': {'C:/Windows/explorer.exe': 'По умолчанию'},
    'key_value': {'C:/Windows/explorer.exe': ['LBUTTON', 'RBUTTON', 'WHEEL_MOUSE_BUTTON', 'SCROLL_UP',
    'SCROLL_DOWN', 'SCROLL_UP', 'SCROLL_DOWN']},
    "mouse_press": {"C:/Windows/explorer.exe": [False, False, False, False, False, False, False]},
    "id": 0,
    "current_app": 'C:/Windows/explorer.exe'}
   res = ensure_additional_exe(res)
   res = ensure_mouse_id_name(res)  # дозаполнить ключ id_name (стабильное имя мыши)
   know_id = '''#!/bin/bash
               input_list=$(xinput list)
               mouse_line=$(echo "$input_list" | head -n 1)
               if [ -n "$mouse_line" ]; then
                   mouse_id=$(echo "$mouse_line" | grep -o "id=[0-9]*" | cut -d "=" -f 2)
                   echo "$mouse_id"
               fi       '''
   # result = subprocess.run(['bash', '-c', know_id], capture_output=True, text=True)
   # res["id"] = int(result.stdout.strip())
  dict_save.save_jnson(res)
  dict_save.set_cur_app(res["current_app"])
  dict_save.set_prev_game(res["current_app"])
  # Ручной/сохранённый выбор профиля (синяя строка) — к нему будем
  # возвращаться после сворачивания/выхода из игры (2026-11-16).
  dict_save.set_user_profile(res["current_app"])
  dict_save.set_current_app_path(res['current_app'])
  devices = [InputDevice(path) for path in list_devices()]
  # Надёжный выбор физической клавиатуры: старый фильтр ("Keyboard\"" + ' phys ')
  # первым ловил виртуальное uinput-устройство (Smart-Virtual-Keyboard), и
  # реальные нажатия терялись. Теперь берём настоящую клавиатуру: пропускаем
  # виртуальные устройства и мыши, оставляем те, у которых есть буквы/Enter,
  # и выбираем самую «полную» (больше всего клавиш EV_KEY).
  try:
   candidates = []
   for dev in devices:
    try:
     caps = dev.capabilities().get(ecodes.EV_KEY, [])
    except Exception:
     continue
    name = (dev.name or "").lower()
    phys = (dev.phys or "").lower()
    if "virtual" in name or "uinput" in phys or "mouse" in name:
     continue
    if ecodes.KEY_A in caps or ecodes.KEY_ENTER in caps or ecodes.KEY_SPACE in caps:
     candidates.append(dev)
   if candidates:
    candidates.sort(key=lambda d: len(d.capabilities().get(ecodes.EV_KEY, [])), reverse=True)
    self.board = candidates[0]
    print("Клавиатура найдена:", self.board.name)
   if self.board is None:
    print("Клавиатура не найдена!")
  except Exception as e:
   print("Ошибка поиска клавиатуры:", e)
   # Вариант B: evdev — единственный источник событий клавиатуры. Корректно
   # различает нумпад (+/-) и основную клавиатуру, не падает при отсутствии устройства.
  self.start_keyboard_listener()  # Запускаем evdev-слушатель
  self.setup_ui()

 def start_keyboard_listener(self):
 # Запуск evdev-слушателя клавиатуры в отдельном потоке (Вариант B:
 # evdev — единственный источник событий, корректно различает нумпад и основную клавиатуру).
  self.keyboard_thread_exit = True
  old = getattr(self, "keyboard_thread", None)
  if old is not None and old.is_alive():
   try:
    old.join(timeout=1)
   except Exception:
    pass
  self.keyboard_thread_exit = False
  self.keyboard_thread = threading.Thread(target=self.keyboard_evdev_loop, daemon=True)
  self.keyboard_thread.start()

 def keyboard_evdev_loop(self):
  board = self.board
  if board is None:
   print("Клавиатура (evdev) не найдена — макросы клавиатуры отключены.")
   return
  pressed = set()
  while not self.keyboard_thread_exit:
   try:
    events = board.read()
    for event in events:
     if event.type != ecodes.EV_KEY:
      continue
     ke = categorize(event)
     if ke.keystate != ke.key_down:
      pressed.discard(ke.keycode)
      continue
     code = ke.keycode
     if isinstance(code, tuple):
      code = code[0]
     if code in pressed:
      continue  # защита от автоповтора (key_hold)
     pressed.add(code)
     label = evdev_key_to_label(code)
     if label is not None:
      self.handle_keyboard_macro(label)
   except BlockingIOError:
    time.sleep(0.01)  # буфер evdev пуст — не блокируем поток/GUI
    continue
   except Exception:
    time.sleep(0.05)
    continue

 def handle_keyboard_macro(self, key_label): # Та же логика сопоставления, что была в старом on_press: ищем макрос в keyboard_script
 # для текущего приложения и запускаем bash-скрипт. Без остановки/рестарта слушателя
 # (цикл непрерывный, поэтому повторные нажатия не теряются).
 # Макросы клавиатуры должны совпадать с целью эмуляции (активное окно),
 # а не с выбранным в UI профилем — иначе они расходятся после разделения
 # current_app (выбор) и live-цели эмуляции.
  try:
   current_app = None
   _rt = getattr(self, "_active_runtime", None)
   if _rt is not None and getattr(_rt, "game", None):
    current_app = _rt.game
   res = dict_save.return_jnson()
   if not current_app:
    _enabled = [p for p, e in res.get("games_checkmark", {}).items() if e]
    try:
     current_app = check_current_active_window(dict_save, _enabled) or dict_save.get_cur_app()
    except Exception:
     # При сбое определения окна/профиля — безопасный откат на профиль по умолчанию.
     _enabled = [p for p, e in res.get("games_checkmark", {}).items() if e]
     current_app = fallback_profile_path(dict_save, _enabled) or dict_save.get_cur_app()

   keys_map = res.get("keyboard_script", {}).get(current_app, {}).get("keys", {})
   if not keys_map:
    # Если у целевого профиля нет макросов (или профиль битый) — пробуем дефолтный.
    _enabled = [p for p, e in res.get("games_checkmark", {}).items() if e]
    fb = fallback_profile_path(dict_save, _enabled)
    if fb and fb != current_app:
     keys_map = res.get("keyboard_script", {}).get(fb, {}).get("keys", {})
     if keys_map:
      current_app = fb
   if not keys_map:
    return

   def _norm_key_name(name):
    # Нормализация имён клавиш: убираем мусорные пробелы/переносы,
    # приводим к нижнему регистру и выравниваем распространённые алиасы.
    s = str(name).replace("\r", " ").replace("\n", " ").strip().lower()
    s = "_".join(s.split())
    aliases = {
     "ctrl_r": "control_r", "ctrl_l": "control_l",
     "rctrl": "control_r", "lctrl": "control_l",
     "rshift": "shift_r", "lshift": "shift_l",
     "ralt": "alt_r", "lalt": "alt_l",
     "esc": "esc", "escape": "esc",
     "return": "enter", "kp_enter": "enter", "kpenter": "enter",
     "capslock": "caps_lock", "numlock": "num_lock",
     "pageup": "page_up", "pagedown": "page_down",
     "printscreen": "print", "prt_sc": "print",
    }
    return aliases.get(s, s)

   key = _norm_key_name(key_label)
   # Перевод русской БУКВЫ в английскую. Символы (+, -, ,, . и т.п.) НЕ трогаем:
   # в ru_to_en есть '+' -> ',' и '-' -> '.', что ломало сопоставление с макросами
   # "+"/"-" (физическая клавиша уже дана в нейтральном виде).
   if key.isalpha() and key in ru_to_en.keys():
    key = ru_to_en[key]

   # Предвычисляем нормализованные имена сохранённых макросов один раз.
   for raw_name, script in list(keys_map.items()):
    if _norm_key_name(raw_name) == key:
     if not isinstance(script, str) or not script.strip():
      return

     def _run_macro(s):
      # Межпроцессная координация с punto.py / write_text_fast.py:
      # берём тот же flock, чтобы xte-макросы не вклинивались в их печать
      # (best-effort: если lock недоступен, макрос всё равно выполняется).
      lock_fd = None
      try:
       try:
        import fcntl as _fcntl
        lock_fd = open("/tmp/kb_scripts_typing.lock", "a+")
        deadline = time.time() + 1.0
        while True:
         try:
          _fcntl.flock(lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
          break
         except OSError:
          if time.time() >= deadline:
           break
          time.sleep(0.02)
       except Exception:
        lock_fd = None
       subprocess.call(["bash", "-c", s])
      except Exception as e:
       try:
        dict_save.write_in_log('keyboard macro error: ' + str(e))
       except Exception:
        pass
      finally:
       if lock_fd is not None:
        try:
         import fcntl as _fcntl
         _fcntl.flock(lock_fd, _fcntl.LOCK_UN)
        except Exception:
         pass
        try:
         lock_fd.close()
        except Exception:
         pass

     t = threading.Thread(target=_run_macro, args=(script,), daemon=True)
     t.start()
     t.join()
     break
  except Exception as e:
   try:
    dict_save.write_in_log('handle_keyboard_macro error: ' + str(e))
   except Exception:
    pass
  
  def eventFilter(self, watched, event):
   if watched is self.scroll_area.viewport():
    # Блокировка прокрутки списка при клике. ВАЖНО: press по QLabel (строке
    # профиля) НЕ доходит до этого фильтра (label потребляет нажатие), а
    # release — доходит. Поэтому позицию запоминаем на КАЖДОМ press и release
    # (актуальное значение скроллбара), а «возврат» на release не делаем —
    # раньше filter возвращал УСТАРЕВШЕЕ _scroll_lock_val (от прошлого press),
    # из-за чего список «убегал» вниз и вверх при двойном клике (переименование).
    if event.type() == QEvent.Type.MouseButtonPress:
     self._scroll_locked = True
     self._scroll_lock_val = self.scroll_area.verticalScrollBar().value()
    elif event.type() == QEvent.Type.MouseButtonRelease:
     self._scroll_locked = True
     self._scroll_lock_val = self.scroll_area.verticalScrollBar().value()
     QTimer.singleShot(180, lambda: self._clear_scroll_lock())
    elif event.type() == QEvent.Type.MouseButtonDblClick:
     self._scroll_locked = True
     self._scroll_lock_val = self.scroll_area.verticalScrollBar().value()
     QTimer.singleShot(180, lambda: self._clear_scroll_lock())
   return super().eventFilter(watched, event)

 def _block_scroll_during_click(self, _val): # Жёстко подавляем любую прокрутку списка профилей во время/сразу после клика
 # (QScrollArea сам «подскролливает» кликнутый элемент в зону видимости по фокусу).
  if getattr(self, "_scroll_locked", False):
   sb = self.scroll_area.verticalScrollBar()
   sb.blockSignals(True)
   sb.setValue(self._scroll_lock_val)
   sb.blockSignals(False)

 def _clear_scroll_lock(self):
  self._scroll_locked = False

 def setup_ui(self):
  self.setWindowTitle("Mouse setting control for buttons python")
  self.setGeometry(400, 340, 1037, 386)
  self.setFixedSize(1042, 346)
  central_widget = QWidget()
  self.setCentralWidget(central_widget)
  
  main_layout = QVBoxLayout(central_widget)
  main_layout.setContentsMargins(10, 10, 10, 10)
  main_layout.setSpacing(10)
  
  top_layout = QHBoxLayout()
  top_layout.setSpacing(10)
  
  left_widget = QWidget()
  left_widget.setFixedWidth(260)
  left_layout = QVBoxLayout(left_widget)
  left_layout.setContentsMargins(0, 0, 0, 0)
  
  self.scroll_area = QScrollArea()
  self.scroll_area.setWidgetResizable(True)
  self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
  self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
  self.scroll_area.setFixedHeight(280)
  
  self.scroll_widget = QWidget()
  self.games_layout = QVBoxLayout(self.scroll_widget)
  self.games_layout.setSpacing(5)
  self.games_layout.setContentsMargins(5, 5, 5, 5)
  
  self.scroll_area.setWidget(self.scroll_widget)
  self._scroll_locked = False
  self._scroll_lock_val = 0
  self.scroll_area.verticalScrollBar().valueChanged.connect(self._block_scroll_during_click)
  self.scroll_area.viewport().installEventFilter(self)
  left_layout.addWidget(self.scroll_area)
  top_layout.addWidget(left_widget, 1)
  
  right_widget = QWidget()
  right_layout = QVBoxLayout(right_widget)
  right_layout.setContentsMargins(10, 10, 10, 10)
  right_layout.setSpacing(10)
  
  rows_and_buttons_layout = QHBoxLayout()
  rows_and_buttons_layout.setSpacing(10)
  
  rows_layout = QVBoxLayout()
  rows_layout.setSpacing(5)
  res = dict_save.return_jnson()
  game = res['current_app']
  box_button = list(res["key_value"][game])
  lab=[]
  for i in range(7):
   row_layout = QHBoxLayout()
   row_layout.setSpacing(10)
   label = QLabel(LIST_MOUSE_BUTTONS[i])
   label.setStyleSheet("padding: 4px; font-weight: bold;")
   label.setFixedWidth(150)
   lab.append(label)
   combo = QComboBox()# Установить все значения выпадающего списка
   combo.addItems(LIST_KEYS)
   current_value = box_button[i]
   self.combo_box.append(combo)
 
   if current_value in LIST_KEYS:
    i2 = LIST_KEYS.index(current_value)
    combo.setCurrentIndex(i2)
   else:
    combo.setCurrentIndex(0)
   combo.currentIndexChanged.connect(lambda idx, i=i: self.update_button(i))
   
   checkbox = QCheckBox()
   checkbox.setToolTip("Держать нажатой")
   checkbox.stateChanged.connect(lambda state, i=i: self.check_mouse_press_button(i, state))
   self.mouse_button_labels.append(label)
   self.mouse_button_combos.append(combo)
   self.mouse_check_buttons.append(checkbox)
   row_layout.addWidget(label)
   row_layout.addWidget(combo, 1)
   row_layout.addWidget(checkbox)
   
   repeat_checkbox = QCheckBox()
   repeat_checkbox.setToolTip("Повторить")
   repeat_checkbox.stateChanged.connect(lambda state, i=i: self.update_mouse_repeat(i, state))
   self.mouse_repeat_check_buttons.append(repeat_checkbox)
   duration_combo = QComboBox()
   duration_combo.addItems(["", "5", "10", "20", "30"])
   duration_combo.setToolTip("Секунды повтора")
   duration_combo.currentIndexChanged.connect(lambda _=0, i=i: self.update_mouse_hold_duration(i))
   self.mouse_hold_duration_combos.append(duration_combo)
   row_layout.addWidget(repeat_checkbox)
   row_layout.addWidget(duration_combo)
   
   rows_layout.addLayout(row_layout)
  
  button_column_layout = QVBoxLayout()
  button_column_layout.setSpacing(5)

  dict_save.save_labels(lab)
  for idx, name in enumerate(LIST_MOUSE_BUTTONS):# Кнопки для скриптов
   button = QPushButton(name)
   button.setFixedWidth(150)
   button.setStyleSheet("padding: 4px;")
   button_column_layout.addWidget(button)
   button.clicked.connect(lambda _, i=idx: self.mouse_scrpt_keyboard_with_editor(i))
   self.buttons_script.append(button)
  
  control_widget = QWidget()
  control_layout = QVBoxLayout(control_widget)
  control_layout.setContentsMargins(10, 10, 10, 10)
  control_layout.setSpacing(12)
  
  self.add_button_add = QPushButton("Добавить")
  self.add_button_add.clicked.connect(lambda: self.add_file())
  control_layout.addWidget(self.add_button_add)
  
  self.del_button = QPushButton("Удалить")
  self.del_button.clicked.connect(lambda: self.delete())
  control_layout.addWidget(self.del_button)
  
  self.move_element_up = QPushButton("Вверх")
  self.move_element_up.clicked.connect(lambda: self.move_element(dict_save, "up"))
  control_layout.addWidget(self.move_element_up)
  self.move_element_down = QPushButton("Вниз")
  self.move_element_down.clicked.connect(lambda: self.move_element(dict_save, "down"))
  control_layout.addWidget(self.move_element_down)
  
  self.Keyboard_button = QPushButton("Клавиатура")
  self.Keyboard_button.clicked.connect(lambda: self.create_virtual_keyboard(dict_save))
  control_layout.addWidget(self.Keyboard_button)
  self.show_devices_button = QPushButton("Показать список устройств")
  self.show_devices_button.clicked.connect(lambda: show_list_id_callback())

  control_layout.addWidget(self.show_devices_button)
  
  if os.getgid() != 0:
   id_layout = QHBoxLayout()
   id_layout.setSpacing(10)
   
   id_label = QLabel("ID устройства:")
   id_label.setStyleSheet("padding: 2px;")
   
   self.id_combo = QComboBox()# выпадающий список профиля
   id_list = dict_save.get_list_ids() if dict_save else []
   self.id_combo.addItems([str(id) for id in id_list])
   self.id_combo.setToolTip('Выбор id устройства')
   self.id_combo.currentIndexChanged.connect(lambda: self.update_profile()) # Используем сигнал currentIndexChanged или activated
   id_layout.addWidget(id_label)
   id_layout.addWidget(self.id_combo)
   control_layout.addLayout(id_layout)
  
  rows_and_buttons_layout.addLayout(rows_layout, 3)
  rows_and_buttons_layout.addLayout(button_column_layout, 1)
  rows_and_buttons_layout.addWidget(control_widget, 1)
  
  right_layout.addLayout(rows_and_buttons_layout)
  top_layout.addWidget(right_widget, 2)
  main_layout.addLayout(top_layout)
  
  QTimer.singleShot(0, self.start_app)
 
 def start_app(self):# Функция старта.
  res = dict_save.return_jnson()
  if os.getgid() != 0 and hasattr(self, 'id_combo'):
   self.id_combo.setCurrentText(str(res["id"]))# установить ввыпадающий список ID устройства.
  curr_name = dict_save.get_cur_app()
  key_values = res["key_value"]
  for i in range(len(LIST_MOUSE_BUTTONS)):
   if hasattr(self, 'mouse_button_combos') and i < len(self.mouse_button_combos):
    if curr_name in key_values and i < len(key_values[curr_name]):
     self.mouse_button_combos[i].setCurrentText(key_values[curr_name][i])
  self.filling_in_fields(dict_save) # Заполнения полей.
  self.update_script_button_colors() # Проверить кнопки скриптов — серые при назначении
  self.start_startup_now(dict_save)# Запуск эмуляции.
  

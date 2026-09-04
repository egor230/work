import sys, os, subprocess, json, threading, re, time, evdev, glob, math, logging, socket
from evdev import UInput, ecodes
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, Qt, QThread
from PyQt6.QtGui import QIcon, QFont, QAction
from PyQt6.QtWidgets import ( QApplication, QWidget, QLabel, QVBoxLayout, QSystemTrayIcon, QMenu)
from pynput.keyboard import Controller, Key, Listener
from pynput import keyboard, mouse
from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import numpy as np
import sounddevice as sd

# Исключенные фразы
excluded_phrases = ["С чего начнём?Нарисовать картинку", "Для звонков телефон как-то удобнее, давайте попробую там.",
                    "Яндекс — с АлисойБыстрый поиск и Алиса всегда рядомПоиск текстом, картинкой или голосомУмная",
                    "Три заветных слова: мобильное приложение Яндекса. Там такое наверняка можно сделать."]


def set_mute(mute: str):
 subprocess.run(["pactl", "set-source-mute", "54", mute], check=True)


def is_text_stable(driver, timeout=5):
 while True:
  try:  # Ждём 3 секунды перед повторной проверкой
   initial_text = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
   time.sleep(timeout)  # Снова получаем текст и сравниваем
   final_text = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
   if initial_text == final_text:
    break
  #  placeholder_element = driver.find_element(By.CSS_SELECTOR, '.AliceChat-StreamingPlaceholder')
  #  if  placeholder_element:
  #   pass
  except:
   break
 message, counts = get_user_messages(driver)
 return message, counts


def get_last_three_messages(driver, class_name):
 messages = driver.find_elements(By.CLASS_NAME, class_name)  # Найти все элементы с заданным классом
 last_three_messages = [message.text.strip() for message in messages[-3:]]  # Получить текст последних трех элементов
 return last_three_messages


def get_last_from_alica(driver):
 return [m.find_element_by_css_selector(".markdown-text span").text for m in
         driver.find_elements_by_class_name("chat__message")
         if "from-user" not in m.find_element_by_class_name("message-bubble_container").get_attribute("class")][-3:]


def get_element_attributes(driver, element):  # Получает все атрибуты элемента и возвращает их в виде словаря."""
 attributes = driver.execute_script("""
        var items = {};
        for (var i = 0; i < arguments[0].attributes.length; i++) {
            var item = arguments[0].attributes[i];
            items[item.name] = item.value;
        }
        return items;    """, element)  # return attributes

def error_closse(driver):  # print("quit")
 script1 = '''#!/bin/bash
   echo $pid
   kill $pid  '''
 subprocess.call(['bash', '-c', script1])
 driver.close()
 driver.quit()
 # Завершение Python-скрипта
 sys.exit()

def is_connected():
 try:  # попытаемся установить соединение с google.com на порту 80
  socket.create_connection(('www.google.com', 80))
  return True
 except OSError:
  pass
 return False

def get_option():
 prefs = {'safebrowsing.enabled': True, "credentials_enable_service": False,
          "profile.password_manager_enabled": False,  # "profile.managed_default_content_settings.images": 0,           # - Отключить загрузку CSS:
          # "profile.default_content_setting_values.javascript": 2,    # - Отключить загрузку JavaScript:
          # "profile.default_content_setting_values.cache": 0
          }  # - Включить кэширование:
 option = webdriver.ChromeOptions()
 option.add_experimental_option("prefs", prefs)
 option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
 option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.7.6367.118 Safari/537.36")
 option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
 option.add_argument("--use-fake-ui-for-media-stream")  # звук
 option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
 option.add_argument("--disable-blink-features=AutomationControlled")
 # option.add_argument("--disable-gpu")
 option.add_argument('--disable-infobars')
 option.add_argument('--disable-web-security')
 option.add_argument("--disable-notifications")
 option.add_experimental_option("useAutomationExtension", False)
 option.add_argument('--mute-audio')  # Отключаем звук на всех страницах
 # option.add_argument("--disk-cache-size=0")
 # option.add_argument("--media-cache-size=0")
 # option.add_argument("--disable-images")
 # option.add_argument("--automatic-wait-for-preview")
 # option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
 # option.add_argument("--disable-extensions")cle-chrome')
 # option.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
 # option.add_argument('--ignore-certificate-errors')
 # option.add_argument('--allow-running-insecure-content')
 # option.add_argument("--disable-dev-shm-usage")
 # option.add_argument("--no-sandbox")

 return option


class SmartTyper:
 def __init__(self):
  try:
   subprocess.run(["sudo", "modprobe", "ntsync"], capture_output=True)
  except Exception:
   pass

  # 1. Общие символы (одинаково печатаются в обеих раскладках)
  self.COMMON_MAP = {
   ' ': ecodes.KEY_SPACE, '\n': ecodes.KEY_ENTER, '\t': ecodes.KEY_TAB,
   '1': ecodes.KEY_1, '2': ecodes.KEY_2, '3': ecodes.KEY_3, '4': ecodes.KEY_4,
   '5': ecodes.KEY_5, '6': ecodes.KEY_6, '7': ecodes.KEY_7, '8': ecodes.KEY_8,
   '9': ecodes.KEY_9, '0': ecodes.KEY_0, '-': ecodes.KEY_MINUS, '=': ecodes.KEY_EQUAL,
   '\\': ecodes.KEY_BACKSLASH, '!': ecodes.KEY_1, '%': ecodes.KEY_5, '*': ecodes.KEY_8,
   '(': ecodes.KEY_9, ')': ecodes.KEY_0, '_': ecodes.KEY_MINUS, '+': ecodes.KEY_EQUAL
  }
  self.COMMON_SHIFT = set(['!', '%', '*', '(', ')', '_', '+'])

  # 2. Английские буквы
  self.EN_MAP = {
   'q': ecodes.KEY_Q, 'w': ecodes.KEY_W, 'e': ecodes.KEY_E, 'r': ecodes.KEY_R, 't': ecodes.KEY_T,
   'y': ecodes.KEY_Y, 'u': ecodes.KEY_U, 'i': ecodes.KEY_I, 'o': ecodes.KEY_O, 'p': ecodes.KEY_P,
   'a': ecodes.KEY_A, 's': ecodes.KEY_S, 'd': ecodes.KEY_D, 'f': ecodes.KEY_F, 'g': ecodes.KEY_G,
   'h': ecodes.KEY_H, 'j': ecodes.KEY_J, 'k': ecodes.KEY_K, 'l': ecodes.KEY_L, 'z': ecodes.KEY_Z,
   'x': ecodes.KEY_X, 'c': ecodes.KEY_C, 'v': ecodes.KEY_V, 'b': ecodes.KEY_B, 'n': ecodes.KEY_N,
   'm': ecodes.KEY_M
  }

  # 3. Русские буквы
  self.RU_MAP = {
   'й': ecodes.KEY_Q, 'ц': ecodes.KEY_W, 'у': ecodes.KEY_E, 'к': ecodes.KEY_R, 'е': ecodes.KEY_T,
   'н': ecodes.KEY_Y, 'г': ecodes.KEY_U, 'ш': ecodes.KEY_I, 'щ': ecodes.KEY_O, 'з': ecodes.KEY_P,
   'х': ecodes.KEY_LEFTBRACE, 'ъ': ecodes.KEY_RIGHTBRACE, 'ф': ecodes.KEY_A, 'ы': ecodes.KEY_S,
   'в': ecodes.KEY_D, 'а': ecodes.KEY_F, 'п': ecodes.KEY_G, 'р': ecodes.KEY_H, 'о': ecodes.KEY_J,
   'л': ecodes.KEY_K, 'д': ecodes.KEY_L, 'ж': ecodes.KEY_SEMICOLON, 'э': ecodes.KEY_APOSTROPHE,
   'я': ecodes.KEY_Z, 'ч': ecodes.KEY_X, 'с': ecodes.KEY_C, 'м': ecodes.KEY_V, 'и': ecodes.KEY_B,
   'т': ecodes.KEY_N, 'ь': ecodes.KEY_M, 'б': ecodes.KEY_COMMA, 'ю': ecodes.KEY_DOT, 'ё': ecodes.KEY_GRAVE
  }

  # 4. Строго английская пунктуация (требует английскую раскладку)
  self.EN_ONLY_PUNCT = {
   '@': ecodes.KEY_2, '#': ecodes.KEY_3, '$': ecodes.KEY_4, '^': ecodes.KEY_6, '&': ecodes.KEY_7,
   '{': ecodes.KEY_LEFTBRACE, '}': ecodes.KEY_RIGHTBRACE, '|': ecodes.KEY_BACKSLASH,
   '<': ecodes.KEY_COMMA, '>': ecodes.KEY_DOT, '~': ecodes.KEY_GRAVE,
   '`': ecodes.KEY_GRAVE, '[': ecodes.KEY_LEFTBRACE, ']': ecodes.KEY_RIGHTBRACE
  }
  self.EN_ONLY_PUNCT_SHIFT = set(['@', '#', '$', '^', '&', '{', '}', '|', '<', '>', '~'])

  # 5. Строго русская пунктуация (требует русскую раскладку)
  self.RU_ONLY_PUNCT = {
   '№': ecodes.KEY_3
  }
  self.RU_ONLY_PUNCT_SHIFT = set(['№'])

  # 6. Универсальная пунктуация (работает в ОБЕИХ раскладках, БЕЗ переключения)
  # Для английской раскладки
  self.PUNCT_EN = {
   ',': ecodes.KEY_COMMA,
   '.': ecodes.KEY_DOT,
   '/': ecodes.KEY_SLASH,
   ';': ecodes.KEY_SEMICOLON,
   "'": ecodes.KEY_APOSTROPHE,
   '?': ecodes.KEY_SLASH,
   ':': ecodes.KEY_SEMICOLON,
   '"': ecodes.KEY_APOSTROPHE,
   '…': ecodes.KEY_DOT  # Троеточие в английской раскладке
  }
  self.PUNCT_EN_SHIFT = set(['?', ':', '"'])

  # Для русской раскладки
  self.PUNCT_RU = {
   ',': ecodes.KEY_SLASH,
   '.': ecodes.KEY_SLASH,
   '/': ecodes.KEY_BACKSLASH,
   ';': ecodes.KEY_4,
   '?': ecodes.KEY_7,
   ':': ecodes.KEY_6,
   '"': ecodes.KEY_2,
   '…': ecodes.KEY_SLASH  # Троеточие в русской раскладке
  }
  self.PUNCT_RU_SHIFT = set([',', '/', ';', '?', ':', '"'])

  self.physical_keyboard = self.find_keyboard()
  self.ui = self.create_virtual_keyboard()

  # --- ВКЛЮЧЕНИЕ NUMLOCK С ГАРАНТИЕЙ LED ---
  self.ensure_numlock_on()

 def find_keyboard(self):
  for path in glob.glob("/dev/input/event*"):
   try:
    dev = evdev.InputDevice(path)
    if "keyboard" in dev.name.lower() or "Keyboard" in dev.name:
     return dev
   except Exception:
    continue
  print("[ERROR] Клавиатура не найдена. Запустите скрипт с sudo.")
  sys.exit(1)

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
                   ecodes.KEY_NUMLOCK
                   ],
   ecodes.EV_LED: [ecodes.LED_NUML]
  }

  ui = UInput(capabilities, vendor=0x1234, product=0x5678,
              bustype=ecodes.BUS_USB, name="Smart-Virtual-Keyboard"
              )

  try:
   self.physical_keyboard.set_led(ecodes.LED_NUML, 1)
  except Exception as e:
   print(f"[WARN] Не удалось установить LED на физической клавиатуре: {e}")

  ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
  ui.syn()
  time.sleep(0.06)
  ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 0)
  ui.syn()
  time.sleep(0.1)

  ui.write(ecodes.EV_LED, ecodes.LED_NUML, 1)
  ui.syn()

  return ui

 def ensure_numlock_on(self):
  """Надёжно включает NumLock и держит индикатор включённым"""
  print("[INFO] Принудительное включение NumLock...")
  try:
   self.physical_keyboard.set_led(ecodes.LED_NUML, 1)
   self.ui.write(ecodes.EV_LED, ecodes.LED_NUML, 1)
   self.ui.syn()

   # Эмуляция нажатия NumLock
   self.ui.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
   self.ui.syn()
   time.sleep(0.5)
  except Exception as e:
   print(f"[WARN] Ошибка при включении NumLock: {e}")
   time.sleep(0.2)
   
 def get_current_layout(self):
  """
  Определение текущей раскладки RU/US.

  ВАЖНО:
  LED mask используется аккуратно:
  состояние Caps Lock отбрасывается при сравнении.
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
   
   for line in result.stdout.splitlines():
    if "LED mask:" in line:
     mask_str = line.split("LED mask:")[-1].strip().split()[0]
     
     try:
      mask = int(mask_str, 16)
     except ValueError:
      break
     
     # Убираем Caps Lock из маски.
     # Благодаря этому Caps не будет восприниматься
     # как изменение раскладки.
     mask_without_caps = mask & ~0x04
     
     #
     # Для стандартной конфигурации ru/us:
     #
     # 0x00001000 — одна XKB-группа
     # 0x00000000 — другая.
     #
     if mask_without_caps & 0x1000:
      layout = "us"
     else:
      layout = "ru"
     
     self._current_layout = layout
     return layout
  
  except Exception as e:
   print(f"[WARN] Ошибка определения раскладки: {e}")
  
  # Не возвращаем слепо US при любой ошибке.
  # Это важно во время печати русского текста.
  return getattr(self, "_current_layout", "us")

 
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
  Переключает только между RU <-> US.
 
  После каждого переключения проверяется реальное
  состояние раскладки.
  """
  if lang not in ("ru", "us"):
   return False
  
  for attempt in range(8):
   
   current = self.get_current_layout()
   
   if current == lang:
    self._current_layout = lang
    return True
   
   try:
    subprocess.run(
     ["xte", "key", "ISO_Next_Group"],
     check=True,
     timeout=1
    )
   
   except Exception as e:
    print(f"[WARN] Ошибка переключения раскладки: {e}")
   
   # Не нужно ждать 1.6 секунды после каждого символа.
   # Даём XKB время переключить группу.
   for _ in range(10):
    time.sleep(0.05)
    
    current = self.get_current_layout()
    
    if current == lang:
     self._current_layout = lang
     return True
  
  print(f"[ERROR] Не удалось переключить раскладку на {lang}")
  return False
 
 
 def type_text(self, text, delay=0.05):
  """
  Печать русского/английского текста.
 
  Учитывает:
  - RU/US;
  - переключение между RU и US прямо внутри строки;
  - Caps Lock;
  - Shift + Caps Lock;
  - знаки препинания;
  - восстановление первоначальной раскладки.
  """
  
  shift_delay = 0.03
  
  original_layout = self.get_current_layout()
  current_layout = original_layout
  
  # Запоминаем реальное состояние Caps Lock.
  caps_on = self.is_capslock_on()
  
  for ch in text:
   
   lower_ch = ch.lower()
   needed_layout = current_layout
   
   keycode = None
   need_shift = False
   
   # ------------------------------------------------
   # Русские буквы
   # ------------------------------------------------
   
   if lower_ch in self.RU_MAP:
    
    needed_layout = "ru"
    keycode = self.RU_MAP[lower_ch]
    
    # Таблица:
    #
    # Caps OFF + а -> Shift OFF
    # Caps OFF + А -> Shift ON
    # Caps ON  + а -> Shift ON
    # Caps ON  + А -> Shift OFF
    #
    need_shift = ch.isupper() != caps_on
   
   # ------------------------------------------------
   # Английские буквы
   # ------------------------------------------------
   
   elif lower_ch in self.EN_MAP:
    
    needed_layout = "us"
    keycode = self.EN_MAP[lower_ch]
    
    need_shift = ch.isupper() != caps_on
   
   # ------------------------------------------------
   # Общие символы
   # ------------------------------------------------
   
   elif ch in self.COMMON_MAP:
    
    keycode = self.COMMON_MAP[ch]
    need_shift = ch in self.COMMON_SHIFT
   
   # ------------------------------------------------
   # Только английские символы
   # ------------------------------------------------
   
   elif ch in self.EN_ONLY_PUNCT:
    
    needed_layout = "us"
    keycode = self.EN_ONLY_PUNCT[ch]
    need_shift = ch in self.EN_ONLY_PUNCT_SHIFT
   
   # ------------------------------------------------
   # Только русские символы
   # ------------------------------------------------
   
   elif ch in self.RU_ONLY_PUNCT:
    
    needed_layout = "ru"
    keycode = self.RU_ONLY_PUNCT[ch]
    need_shift = ch in self.RU_ONLY_PUNCT_SHIFT
   
   # ------------------------------------------------
   # Символы, зависящие от раскладки
   # ------------------------------------------------
   
   elif ch in self.PUNCT_EN or ch in self.PUNCT_RU:
    
    if current_layout == "us":
     keycode = self.PUNCT_EN.get(ch)
     
     if keycode is not None:
      need_shift = ch in self.PUNCT_EN_SHIFT
    
    else:
     keycode = self.PUNCT_RU.get(ch)
     
     if keycode is not None:
      need_shift = ch in self.PUNCT_RU_SHIFT
   
   # ------------------------------------------------
   # Неизвестный символ
   # ------------------------------------------------
   
   else:
    print(f"[WARN] Неизвестный символ: {repr(ch)}")
    continue
   
   if keycode is None:
    continue
   
   # ------------------------------------------------
   # Переключение RU / US
   # ------------------------------------------------
   
   if current_layout != needed_layout:
    
    if self.set_layout(needed_layout):
     current_layout = needed_layout
    
    else:
     print(
      f"[ERROR] Не удалось установить "
      f"раскладку {needed_layout} для {repr(ch)}"
     )
     continue
   
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
    
    time.sleep(shift_delay)
   
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
    
    time.sleep(max(delay / 3.5, 0.01))
    
    self.ui.write(
     ecodes.EV_KEY,
     keycode,
     0
    )
    self.ui.syn()
   
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
  # Возвращаем исходную раскладку
  # ----------------------------------------------------
  
  if current_layout != original_layout:
   self.set_layout(original_layout)
 

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
keyboard = Controller()
def on_press(key):
  key = str(key).replace(" ", "")
  if key == "Key.shift_r":
      k.set_flag(True)
      return True
  if key in ["Key.space", "Key.right", "Key.left", "Key.down", "Key.up"]:
      k.set_flag(False)
      return True
  if key == "Key.alt":
      driver = k.get_driver()
      k.update_dict()
      return True
  return True
def on_release(key):
  pass
  return True

def start_listener():
  global listener
  listener = Listener(on_press=on_press, on_release=on_release)
  listener.start()
start_listener()

# llm=load_model(MODEL_PATH)
def replace(match):
 res = k.get_dict()
 return res[match.group(0)]

def repeat(text1: str):
 text = text1.replace("!", ".")
 k.save_text(text)
 text1 = ""
 res = k.get_dict()
 # Передаём список ключей (словосочетаний) вместо словаря
 k.save_words(list(res.keys()))
 words = k.get_words()
 try:
  # Регулярное выражение ищет целые слова и фразы (с пробелами)
  # Используем (?<!\w) и (?!\w) для границ, чтобы не заменять части слов
  words_regex = r'(?<!\w)(' + '|'.join(map(re.escape, words)) + r')(?!\w)'
  text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
  k.save_text(text1)
 except Exception as ex:
  print(f"Ошибка: {ex}")
 return text1

typer = SmartTyper()

def press_keys(text):
 try:
  text = repeat(text)
  print(text)
  # Спецсимволы, которые лучше отправлять через key, а не type
  # char_to_xdotool = {",": "comma", ":": "colon"}
  # Сброс sticky-клавиш и NumLock (выполняется один раз)
  reset_keys_script = '''#!/bin/bash
                xte 'keyup Shift_R'
                sleep 0.1
                xte 'keyup Shift_L'
                sleep 0.1
                xkbset -sticky
                xte "key Num_Lock"
                exit '''
  #subprocess.run(['bash', '-c', reset_keys_script])
  #time.sleep(1)
  typer.type_text(text, delay=0.1)
  #subprocess.call(['xkbset', 'sticky']) # Включаем sticky keys обратно
 except Exception as ex1:
  print(ex1)

def process_text(previous_message1):
  text = previous_message1 + str(" ")
  text=text[0].lower()+ text[1:]
  if k.get_flag() == True:
    k.set_flag(False)
    text0 = text[0].upper() + text[1:]
    press_keys(text0)
  else:
    press_keys(text)


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
def get_mute_status(source_id):  # Получает статус Mute для источника '54' с помощью pactl и grep.
 try:
  r = subprocess.run(["pactl", "get-source-mute", source_id],  capture_output=True, text=True, check=True)
  # print(r)
  if "да" in str(r.stdout.lower()):
   return False
  else:
   return True
 except:
  return False

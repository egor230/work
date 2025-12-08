import os, time, json, subprocess, re, threading, socket, uuid, glob, sys, pyaudio, shutil, pyautogui, pystray, whisper, wave, requests, torch
import whisper, tempfile, queue, torchaudio
from pathlib import Path
from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from urllib3 import HTTPConnectionPool
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
from deepdiff import DeepDiff
from PIL import Image
from io import BytesIO
from pynput import *
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key
from pystray import Menu, MenuItem, Icon
import tkinter as tk
from tkinter import Frame, Label
# import numpy as np
# select,
# import speech_recognition as sr

# Словарь клавиш из оригинального скрипта
KEYS = {    "LBUTTON": 0x01, "RBUTTON": 0x02, "CANCEL": 0x03, "MBUTTON": 0x04, "XBUTTON1": 0x05,
    "XBUTTON2": 0x06, "BACK": 0x08, "TAB": 0x09, "CLEAR": 0x0C, "RETURN": 0x0D,
    "SHIFT": 0x10, "CONTROL": 0x11, "MENU": 0x12, "PAUSE": 0x13, "CAPITAL": 0x14,
    "KANA": 0x15, "JUNJA": 0x17, "FINAL": 0x18, "KANJI": 0x19, "ESCAPE": 0x1B,
    "CONVERT": 0x1C, "NONCONVERT": 0x1D, "ACCEPT": 0x1E, "MODECHANGE": 0x1F, "SPACE": 0x20,
    "PRIOR": 0x21, "NEXT": 0x22, "END": 0x23, "HOME": 0x24, "LEFT": 0x25, "UP": 0x26,
    "RIGHT": 0x27, "DOWN": 0x28, "SELECT": 0x29, "PRINT": 0x2A, "EXECUTE": 0x2B,
    "SNAPSHOT": 0x2C, "INSERT": 0x2D, "DELETE": 0x2E, "HELP": 0x2F, "key0": 0x30,
    "key1": 0x31, "key2": 0x32, "key3": 0x33, "key4": 0x34, "key5": 0x35, "key6": 0x36,
    "key7": 0x37, "key8": 0x38, "key9": 0x39, "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44,
    "E": 0x45, "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A, "K": 0x4B, "L": 0x4C,
    "M": 0x4D, "N": 0x4E, "O": 0x4F, "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54,
    "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59, "Z": 0x5A, "LWIN": 0x5B,
    "RWIN": 0x5C, "APPS": 0x5D, "SLEEP": 0x5F, "NUMPAD0": 0x60, "NUMPAD1": 0x61,
    "NUMPAD2": 0x62, "NUMPAD3": 0x63, "NUMPAD4": 0x64, "NUMPAD5": 0x65, "NUMPAD6": 0x66,
    "NUMPAD7": 0x67, "NUMPAD8": 0x68, "NUMPAD9": 0x69, "MULTIPLY": 0x6A, "ADD": 0x6B,
    "SEPARATOR": 0x6C, "SUBTRACT": 0x6D, "DECIMAL": 0x6E, "DIVIDE": 0x6F, "F1": 0x70,
    "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B, "F13": 0x7C, "F14": 0x7D,
    "F15": 0x7E, "F16": 0x7F, "F17": 0x80, "F18": 0x81, "F19": 0x82, "F20": 0x83,
    "F21": 0x84, "F22": 0x85, "F23": 0x86, "F24": 0x87, "NUMLOCK": 0x90, "SCROLL": 0x91,
    "OEM_FJ_JISHO": 0x92, "OEM_FJ_MASSHOU": 0x93, "OEM_FJ_TOUROKU": 0x94, "OEM_FJ_LOYA": 0x95,
    "OEM_FJ_ROYA": 0x96, "LSHIFT": 0xA0, "RSHIFT": 0xA1, "LCONTROL": 0xA2, "RCONTROL": 0xA3,
    "LMENU": 0xA4, "RMENU": 0xA5, "BROWSER_BACK": 0xA6, "BROWSER_FORWARD": 0xA7,
    "BROWSER_REFRESH": 0xA8, "BROWSER_STOP": 0xA9, "BROWSER_SEARCH": 0xAA,
    "BROWSER_FAVORITES": 0xAB, "BROWSER_HOME": 0xAC, "VOLUME_MUTE": 0xAD, "VOLUME_DOWN": 0xAE,
    "VOLUME_UP": 0xAF, "MEDIA_NEXT_TRACK": 0xB0, "MEDIA_PREV_TRACK": 0xB1, "MEDIA_STOP": 0xB2,
    "MEDIA_PLAY_PAUSE": 0xB3, "LAUNCH_MAIL": 0xB4, "LAUNCH_MEDIA_SELECT": 0xB5,
    "LAUNCH_APP1": 0xB6, "LAUNCH_APP2": 0xB7, "OEM_1": 0xBA, "OEM_PLUS": 0xBB,
    "OEM_COMMA": 0xBC, "OEM_MINUS": 0xBD, "OEM_PERIOD": 0xBE, "OEM_2": 0xBF, "OEM_3": 0xC0,
    "ABNT_C1": 0xC1, "ABNT_C2": 0xC2, "OEM_4": 0xDB, "OEM_5": 0xDC, "OEM_6": 0xDD,
    "OEM_7": 0xDE, "OEM_8": 0xDF, "OEM_AX": 0xE1, "OEM_102": 0xE2, "ICO_HELP": 0xE3,
    "PROCESSKEY": 0xE5, "ICO_CLEAR": 0xE6, "PACKET": 0xE7, "OEM_RESET": 0xE9, "OEM_JUMP": 0xEA,
    "OEM_PA1": 0xEB, "OEM_PA2": 0xEC, "OEM_PA3": 0xED, "OEM_WSCTRL": 0xEE, "OEM_CUSEL": 0xEF,
    "OEM_ATTN": 0xF0, "OEM_FINISH": 0xF1, "OEM_COPY": 0xF2, "OEM_AUTO": 0xF3, "OEM_ENLW": 0xF4,
    "OEM_BACKTAB": 0xF5, "ATTN": 0xF6, "CRSEL": 0xF7, "EXSEL": 0xF8, "EREOF": 0xF9,
    "PLAY": 0xFA, "ZOOM": 0xFB, "PA1": 0xFD, "OEM_CLEAR": 0xFE}

def set_mute(mute: str):
 subprocess.run(["pactl", "set-source-mute", "54", mute], check=True)
 
def is_text_stable(driver, timeout=3):
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
 return True
def get_user_messages(driver):  # Извлекаем текст всех сообщений пользователя
 # Находим все контейнеры сообщений пользователя
 user_m = driver.find_elements(By.CSS_SELECTOR, ".MessageBubble-Container_from-user")
 if user_m:
  # Берем последний контейнер
  last_user_container = user_m[-1]
  # Находим внутри него сам элемент с текстом сообщения
  message = last_user_container.find_element(By.CSS_SELECTOR, ".MessageBubble").text.strip()
  counts = len(user_m)
  message = repeat(message)
  return message, counts  # Возвращаем результаты
def get_latest_message(driver, len_c=0):
 try:
  driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")  # filter_elem = WebDriverWait(driver, 1).until( EC.presence_of_element_located((By.CSS_SELECTOR, ".yamb-oknyx-lottie.svelte-rdfi3w"))).get_attribute("data-testid")
  # aria_label= mic_button.get_attribute('aria-label')  # Ожидание наличия элемента на странице
  element =  driver.find_element(By.CSS_SELECTOR, '.AliceChat-StreamingPlaceholder')
  if element.is_displayed():  # Проверка видимости элемента
   message, counts = get_user_messages(driver)   # button.click()
   return message, counts + 1
  else:
    return "", len_c
 except Exception as ex:
  # user_m = [message.text.strip() for message in driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')]
  # counts = len(user_m)
  pass
  return "", len_c  # Возврат по умолчанию, если ни одно условие не выполнилось    # pass       #

def get_last_three_messages(driver, class_name):
 messages = driver.find_elements(By.CLASS_NAME, class_name)  # Найти все элементы с заданным классом
 last_three_messages = [message.text.strip() for message in messages[-3:]]  # Получить текст последних трех элементов
 return last_three_messages

def get_last_from_alica(driver):
 return [m.find_element_by_css_selector(".markdown-text span").text for m in
         driver.find_elements_by_class_name("chat__message")
         if "from-user" not in m.find_element_by_class_name("message-bubble_container").get_attribute("class")][-3:]

def get_element_attributes(element):  # Получает все атрибуты элемента и возвращает их в виде словаря."""
 attributes = driver.execute_script("""
        var items = {};
        for (var i = 0; i < arguments[0].attributes.length; i++) {
            var item = arguments[0].attributes[i];
            items[item.name] = item.value;
        }
        return items;    """, element) # return attributes

def del_all_chats(driver):  # Находим все чаты
 try:
  chats = driver.find_elements(By.CSS_SELECTOR, ".ChatListGroup-List .ChatListItem")
  for i in range(len(chats)):
   chats = driver.find_elements(By.CSS_SELECTOR, ".ChatListGroup-List .ChatListItem")
   if len(chats) < 2:
    break
   more_button = chats[0].find_element(By.CSS_SELECTOR, ".ChatListItem-Button_more")
   driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_button)
   time.sleep(0.5)
   more_button.click()
   delete_button = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((
        By.XPATH,
        "//div[@role='button' and contains(@class, 'ContextMenuItem')]"
        "[.//span[@class='ContextMenuItem-Text' and text()='Удалить чат']]"
    ))
)
   driver.execute_script("arguments[0].click();", delete_button)

   time.sleep(1.5)  # ждём пока чат реально исчезнет

 except Exception as e:
   print(f"Ошибка: {e}")
   pass

def cut_image(driver):# Получение скриншота всей страницы и сохранение его в файл
 screenshot = driver.get_screenshot_as_png()
 with open('screenshot.png', 'wb') as file:
    file.write(screenshot) # Открываем файл в бинарном режиме
 with open('screenshot.png', 'rb') as file:
    screenshot = file.read()    # Загружаем скриншот в объект Image
    image = Image.open(BytesIO(screenshot))
     # Определяем размеры изображения
    width, height = image.size    # Определяем координаты для правого нижнего угла
    # Например, вырезаем угол размером 200x200 пикселей
    left = width - 100
    top = height - 100
    right = width
    bottom = height
    # Обрезаем изображение
    cropped_image = image.crop((left + 50, top + 15, right - 13, bottom - 43))
    # Сохраняем или показываем результат
    cropped_image.save("cropped_corner.png")

  # with open('page_content.html', 'w', encoding='utf-8') as file:
  #    file.write(html_content)
  # Найдите все элементы с классом message-bubble
#  html_content = driver.page_source  # Используйте BeautifulSoup для парсинга HTML
 # soup = BeautifulSoup(html_content, 'html.parser')
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
  
  def get_words(self):
    return self.word

class get_lang:
  def __init__(self):
    self.text = ""
  
  def save_text(self, text):
    self.text = text
  
  def get_text(self):
    return self.text

k = save_key()
k.update_dict()
time.sleep(2.2)

def error_closse(driver):
  # print("quit")
  subprocess.call(['bash', '-c', script])
  script1 = '''#!/bin/bash
   echo $pid
   kill $pid  '''
  subprocess.call(['bash', '-c', script1])
  driver.close()
  driver.quit()

  # Завершение Python-скрипта
  sys.exit()

def replace(match):
  res = k.get_dict()
  return res[match.group(0)]

def repeat(text):
  # text = "linux менч установить линукс минт помоги мне установить "
  # print(text)
  k.save_text(text)
  text1 = ""
  res = k.get_dict()
  k.save_words(res)
  words = k.get_words()
  # print(words)
  try:
   # Создаем регулярное выражение для всех слов и словосочетаний из словаря
   words_regex = r'\b(' + r'|'.join(map(re.escape, words)) + r')\b'
   # Выполняем замену с учетом регистра
   text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
   k.save_text(text1)
   # Дополнительная замена для слов из словаря res
   for word, replacement in res.items():
    text1 = re.sub(r'\b' + re.escape(word) + r'\b', replacement, text1, flags=re.IGNORECASE)
   k.save_text(text1)
  except Exception as ex:
   print(f"Ошибка: {ex}")  # Выводим ошибку для диагностики
  return text1
    # for i in words:
    #   text = k.get_text()
    #   reg = r'\b' + r'\b|\b'.join([i]) + r'\b'
    #   text1 = re.sub(reg, replace, text)
    #   k.save_text(text1)
    #  k.save_text(text1)

def is_connected():
  try:  # попытаемся установить соединение с google.com на порту 80
    socket.create_connection(('www.google.com', 80))
    return True
  except OSError:
    pass
  return False

def process_text(previous_message1, k):
  text = previous_message1 + str(" ")
  if k.get_flag() == True:
    k.set_flag(False)
    text0 = text[0].upper() + text[1:]
    press_keys(text0)
  else:
    press_keys(text)

  def get_current_layout():
    """Определяет текущую раскладку клавиатуры."""
    try:
      layout = subprocess.check_output("setxkbmap -query | grep layout", shell=True).decode()
      return layout.strip().split()[-1]
    except Exception:
      return None

def switch_layout(to_layout):
  """Переключает раскладку на указанную."""
  subprocess.call(["setxkbmap", to_layout])


def get_char_layout(char):
  """Определяет, к какой раскладке относится символ."""
  if 'a' <= char.lower() <= 'z' or char in "~!@#$%^&*()_+{}|:\"<>?":
    return 'us'
  elif 'а' <= char.lower() <= 'я' or char in "ёйцукенгшщзхъфывапролджэячсмитьбю":
    return 'ru'
  elif char == ' ':
    return 'space'
  else:
    return 'unknown'
keyboard = Contr1()
def press_keys(text):  # xte 'keyup Shift_L'
  try:   #
   print(text)
   # text="lunix mint"
   for char in text:
    if char in ['a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E', 'f', 'F', 'g', 'G', 'h', 'H', 'i', 'I', 'j', 'J', 'k', 'K', 'l', 'L', 'm', 'M',
     'n', 'N', 'o', 'O', 'p', 'P', 'q', 'Q', 'r', 'R', 's', 'S', 't', 'T', 'u', 'U', 'v', 'V', 'w', 'W', 'x', 'X', 'y', 'Y', 'z', 'Z',' ']:  # Диапазон от пробела до тильды (ASCII 32-126)#
     subprocess.call(['xdotool', 'type', '--delay', '9', char])
      # pyautogui.write(char, interval=0.01)
    else:  # Русский или смешанный вкладку ак
     if char.isupper():  # Если символ заглавный
          keyboard.press(char.upper())  # Нажимаем строчную версию символа
          keyboard.release(char.upper())
     else:
        keyboard.press(char)
        keyboard.release(char)
        time.sleep(0.03)  # Уменьшение задержки
   #
  except Exception as ex1:
    print(ex1)
    return
def press_key_enter():
  script = '''#!/bin/bash
 xte 'key Return'
 '''

class work_key:
  def __init__(self):
    self.keys_list = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', 'a', 's', 'd', 'f', 'g',
                      'h', 'j', 'k', 'l', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ]
    self.keys_list1 = ['BackSpace', 'Tab', 'Return', 'KP_Enter', 'Escape', 'Delete', 'Home', 'End', 'Page_Up',
   'Page_Down', 'F1', 'Up', 'Down', 'Left', 'Right', 'Control_L', 'ISO_Next_Group', 'Control_R', 'Shift_L', 'Shift_R', 'Alt_L', 'Alt_R', 'Super_L',
   'Super_R', 'Caps_Lock', 'Num_Lock', 'Scroll_Lock', 'space', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
   '1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

      # subprocess.call(['bash', '-c', mouse_wheel])
  def key_press(self, key):# Нажать.
    print(key)
    press = '''#!/bin/bash
    xte 'keydown {0}'
    sleep 0.1    # Небольшая пауза для надёжности
    xte 'keyup {0}'
    exit 0 '''
    key1= key.lower()
    if key1 in self.keys_list or key in self.keys_list1:
      thread0 = threading.Thread(target=lambda: subprocess.call(['bash', '-c', press.format(key)]))      #thread.daemon = True  # Установка атрибута daemon в значение True
      thread0.daemon
      thread0.start()
      return 0

class save_ln:
  def __init__(self):
    self.text = ""
  
  def save_text(self, text):
    self.text = text
  
  def get_text(self):
    return self.text

def get_option():
  prefs = {'safebrowsing.enabled': True, "credentials_enable_service": False,
           "profile.password_manager_enabled": False, #"profile.managed_default_content_settings.images": 0,           # - Отключить загрузку CSS:
           # "profile.default_content_setting_values.javascript": 2,    # - Отключить загрузку JavaScript:
           # "profile.default_content_setting_values.cache": 0
            }# - Включить кэширование:
  option = webdriver.ChromeOptions()
  option.add_experimental_option("prefs", prefs)
  option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
  option.add_argument( "user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.7.6367.118 Safari/537.36")
  option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
  option.add_argument("--use-fake-ui-for-media-stream")  # звук
  option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
  option.add_argument("--disable-blink-features=AutomationControlled")
  option.add_argument("--disable-gpu")
  option.add_argument('--disable-infobars')
  option.add_argument('--disable-web-security')
  option.add_argument("--disk-cache-size=0")
  option.add_argument("--media-cache-size=0")
  option.add_argument("--disable-images")
  option.add_argument("--automatic-wait-for-preview")
  option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
  option.add_argument("--disable-extensions")
  option.add_argument("--disable-autofill")
  option.add_argument("--disable-background-timer-throttling")  # Отключение ограничения фоновых таймеров
  option.add_argument("--disable-background-networking")  # Отключение фоновой сетевой активности
  option.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/google-chrome')
  # option.add_argument("--disable-notifications")
  option.add_experimental_option("useAutomationExtension", False)
  # option.add_argument('--ignore-certificate-errors')
  # option.add_argument('--allow-running-insecure-content')
  # option.add_argument("--disable-dev-shm-usage")
  # option.add_argument("--no-sandbox")
  
  return option

  def get_latest_message(driver, len_c=0):
   try:
    driver.execute_script(
     "window.scrollTo(0, document.body.scrollHeight);")  # filter_elem = WebDriverWait(driver, 1).until( EC.presence_of_element_located((By.CSS_SELECTOR, ".yamb-oknyx-lottie.svelte-rdfi3w"))).get_attribute("data-testid")
    # aria_label= mic_button.get_attribute('aria-label')  # Ожидание наличия элемента на странице
    element = driver.find_element(By.CLASS_NAME, "chat__streaming-placeholder")
    if element.is_displayed():  # Проверка видимости элемента
     message, counts = get_user_messages(driver)  # button.click()
     return message, counts + 1
    else:
     return "", len_c
   except Exception as ex:
    user_m = [message.text.strip() for message in driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')]
    counts = len(user_m)
    pass
    return "", len_c  # Возврат по умолчанию, если ни одно условие не выполнилось    # pass       #

  def is_text_stable(driver, timeout=3):
   while True:
    try:  # Ждём 3 секунды перед повторной проверкой
     initial_text = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
     time.sleep(timeout)  # Снова получаем текст и сравниваем
     final_text = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
     if initial_text == final_text:
      break
    #  placeholder_element = driver.find_element(By.CSS_SELECTOR, '.chat__streaming-placeholder.svelte-10qurrr')
    #  if  placeholder_element:
    #   pass
    except:
     break
   return True
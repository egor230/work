import os, time, json, subprocess, re, threading, socket, sys, pyaudio, shutil, pyautogui, pystray, requests, numpy as np
from queue import Queue
from pathlib import Path
from urllib3 import HTTPConnectionPool
from bs4 import BeautifulSoup
from deepdiff import DeepDiff
from PIL import Image
from io import BytesIO
from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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
        return items;    """, element) # return attributes

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
    bottom = height    # Обрезаем изображение
    cropped_image = image.crop((left + 50, top + 15, right - 13, bottom - 43))
    # Сохраняем или показываем результат
    cropped_image.save("cropped_corner.png")

  # with open('page_content.html', 'w', encoding='utf-8') as file:
  #    file.write(html_content)
  # Найдите все элементы с классом message-bubble
#  html_content = driver.page_source  # Используйте BeautifulSoup для парсинга HTML
 # soup = BeautifulSoup(html_content, 'html.parser')

def error_closse(driver): # print("quit")
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
  # option.add_argument("--disk-cache-size=0")
  # option.add_argument("--media-cache-size=0")
  # option.add_argument("--disable-images")
  # option.add_argument("--automatic-wait-for-preview")
  option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
  # option.add_argument("--disable-extensions")
  # option.add_argument("--disable-autofill")
  option.add_argument("--disable-background-timer-throttling")  # Отключение ограничения фоновых таймеров
  option.add_argument("--disable-background-networking")  # Отключение фоновой сетевой активности
  # option.add_argument('--user-data-dir=/home/egor/.config/google-chrome')
  option.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
  # option.add_argument("--disable-notifications")
  option.add_experimental_option("useAutomationExtension", False)
  option.add_argument('--mute-audio')  # Отключаем звук на всех страницах
  # option.add_argument('--ignore-certificate-errors')
  # option.add_argument('--allow-running-insecure-content')
  # option.add_argument("--disable-dev-shm-usage")
  # option.add_argument("--no-sandbox")
  
  return option


import os, time, json, subprocess, re, threading, socket, uuid,  glob, sys, threading
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from pynput.keyboard import Key, Controller
from pynput import *
from urllib3 import HTTPConnectionPool
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from pytq_libs_voice import *
from write_text import *
try:
  option = webdriver.ChromeOptions()
  option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
  prefs = {'safebrowsing.enabled': True,
           "credentials_enable_service": False,
           "profile.password_manager_enabled": False,
           "credentials_enable_service": False,
           "profile.password_manager_enabled": False,
           "profile.managed_default_content_settings.images": 0,  # - Отключить загрузку CSS:
           # "profile.default_content_setting_values.javascript": 2,           # - Отключить загрузку JavaScript:
           "profile.default_content_setting_values.cache": 0  # - Включить кэширование:
           }
  option = webdriver.ChromeOptions()
  option.add_experimental_option("prefs", prefs)
  option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
  option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36")
  option.add_argument("--use-fake-ui-for-media-stream")  # звук
  option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
  option.add_argument("--disable-blink-features=AutomationControlled")
  option.add_argument('--disable-web-security')
  option.add_argument("--disk-cache-size=0")
  option.add_argument("--media-cache-size=0")
  # option.add_argument("--automatic-wait-for-preview")
  option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
  option.add_argument("--disable-site-isolation-trials")
  option.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/google-chrome')
  try:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
    driver.get("https://chat.mistral.ai/chat")  # открыть сайт        # Пауза для загрузки контента
    html_content = driver.page_source
    with open('page_content.html', 'w', encoding='utf-8') as file:
       file.write(html_content)
    # Поиск кнопки по атрибуту aria-label
    # Ждём, пока кнопка станет кликабельной (самый надёжный способ)
    time.sleep(2)  # React иногда рисует кнопку чуть позже

    buttons = driver.find_elements(By.CSS_SELECTOR, '.flex.ms-auto')
    if buttons:
     buttons[1].click()  # нажимаем первую
    print("🎤 Запись голоса запущена!")
    time.sleep(6)

    button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-label="Transcribe audio message"]'))
    )
    button.click()
    print("Кнопка нажата по aria-label")

    prose_mirror = WebDriverWait(driver, 10).until(
     EC.presence_of_element_located((By.CSS_SELECTOR, '.ProseMirror'))
    )

    # Получаем текст из всех параграфов
    paragraphs = prose_mirror.find_elements(By.TAG_NAME, 'p')

    # Или просто весь текст
    full_text = prose_mirror.text
    print(f"Весь текст: {full_text}")
    input()
    while True:
      # Прокрутка на высоту экрана
      driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
      # Пауза для загрузки контента
      time.sleep(1.5)
      # Получение новой высоты страницы
      new_height = driver.execute_script("return document.body.scrollHeight")

      # Если высота не изменилась, выходим из цикла
      if new_height == last_height:
        break
      last_height = new_height
    print("1")
    articles_dict= get_list_stati(driver)
    for index, (key, value) in enumerate(articles_dict.items()):
      print(f"{index} : {key} - {value}")
    # Печатаем полученный словарь
    # print(articles_dict)
  except Exception as ex2:
      print(ex2)
      if 'no such window: target window' in str(ex2):
          print("exit no such window: target window already closed")

      # print(ex2)  # print("error")
      time.sleep(5)
      pass
except Exception as ex1:
    print(ex1)  # driver.close()  # driver.quit()
    pass
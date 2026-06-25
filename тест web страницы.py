import os, time, json, time, subprocess, re, threading, socket, uuid, time, select, glob, sys, threading

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from pynput.keyboard import Key, Controller
from pynput import *
from urllib3 import HTTPConnectionPool
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

script = '''#!/bin/bash
# Ищем идентификаторы процессов, содержащих слово "chrome"
pids=$(pgrep -f "chrome")
# Перебираем найденные идентификаторы процессов и отправляем им сигнал завершения
for pid in $pids; do
    kill $pid
done

pids=$(pgrep -f "chromedriver")
# Перебираем найденные идентификаторы процессов и отправляем им сигнал завершения
for pid in $pids; do
    kill $pid
done
'''
# subprocess.call(['bash', '-c', script])

time.sleep(2.2)
def error_closse(driver):
  # print("quit")
  subprocess.call(['bash', '-c', script])
  script1 = '''#!/bin/bash
   echo $pid
   kill $pid
  '''
  subprocess.call(['bash', '-c', script1])
  driver.close()
  driver.quit()

# Завершение Python-скрипта
  sys.exit()
def is_connected():

    try: # попытаемся установить соединение с google.com на порту 80
        socket.create_connection(('www.google.com', 80))
        return True
    except OSError:
        pass
    return False

driver = 0
try:
  prefs = {'safebrowsing.enabled': True,
           "credentials_enable_service": False,
           "profile.password_manager_enabled": False,
           "credentials_enable_service": False,
           "profile.password_manager_enabled": False,
           "profile.managed_default_content_settings.images": 0,
           # - Отключить загрузку CSS:
           # "profile.default_content_setting_values.javascript": 2,
           # - Отключить загрузку JavaScript:
           "profile.default_content_setting_values.cache": 0
           # - Включить кэширование:
           }
  option = webdriver.ChromeOptions()
  # option.add_experimental_option("prefs", prefs)

  # Установка опций для Chrome
  option.add_argument("disable-infobars")  # Отключить информационные строки
  option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.60 Safari/537.36")
  option.add_argument("--disable-popup-blocking")  # Отключить блокировку всплывающих окон
  option.add_experimental_option("excludeSwitches", ["enable-automation"])  # Исключить переключатели, позволяющие обнаружить автоматизацию
  option.add_experimental_option('useAutomationExtension', False)

  # adress = os.getcwd() + str('/chromedriver')
  # s=Service(adress)
  # # s=Service('/usr/local/bin/chromedriver')
  # option.binary_location = '/usr/bin/google-chrome'
  # s=Service('/mnt/89d7250f-eddb-4218-bdc6-018b7fdb958f/linux must have/chromedriver_linux64/chrome-linux64/chrome')

  option.add_argument('--user-data-dir=/home/egor/.config/google-chrome')
  try:
    while 1:
      time.sleep(1)
      if is_connected():
        break
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                              options=option)
    # driver.set_window_size(624, 568)  # optiol
    driver.maximize_window()
    # driver.set_window_position(600, 250)
    driver.get("https://developers.sber.ru/gigachat/78bd1d47-c42c-4138-8747-dd7ca80d38b2/sessions/create")  # открыть сайт

    # Ожидаем, пока элемент не будет кликабелен
    # element = driver.find_element('//*[@class="sc-jFAcUc kHcRm"]')
    # element.click()
    # кликаем по элементу, как только он станет кликабельным

    input()# Находим элемент textarea по его ID
    #
    # textarea = driver.find_element(By.ID, "chatTextArea")
    #
    # # Отчищаем текстовое поле, если это необходимо
    # textarea.clear()
    #
    # # Вводим текст в элемент textarea
    # textarea.send_keys("отпиши  какие могут быть симптомы  сердечно-сосудистым заболеваниям. самых распространённых только не сухо не так  официально ")
    #
    # # Если требуется отправить форму, имитируем нажатие Enter
    # textarea.send_keys(Keys.ENTER)
    #
    # button = WebDriverWait(driver, 10).until(
    #     EC.element_to_be_clickable((By.CLASS_NAME, "plasma__sc-14cj1yw-0"))
    # )
    # Нажимаем на кнопку
    input()# Находим элемент textarea по его ID
  except Exception as ex2:
    print("lkjn")
    if 'no such window: target window' in str(ex2):
      print("exit no such window: target window already closed")
      error_closse(driver)
    # print(ex2)  # print("error")
    time.sleep(5)
    pass

except Exception as ex1:
  # print(ex1)  # driver.close()  # driver.quit()
  pass

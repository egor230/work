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


def get_cached_chromedriver():
 import glob as _glob
 candidates = []
 for path in _glob.glob(os.path.expanduser("~/.wdm/drivers/chromedriver/linux64/*/chromedriver-linux64/chromedriver")):
  ver = path.split("/linux64/")[1].split("/")[0]
  parts = [int(x) for x in ver.split(".") if x.isdigit()]
  candidates.append((parts, path))
 if not candidates:
  return None
 candidates.sort(key=lambda t: t[0], reverse=True)
 return candidates[0][1]

try:
  option = webdriver.ChromeOptions()

  option.binary_location = '/usr/bin/google-chrome-stable'
  option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
  option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
  option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36")
  option.add_argument("--use-fake-ui-for-media-stream")  # звук
  option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
  
  option.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
  # Указываем путь к chromedriver (если не в PATH, укажите явно)
  # service = Service("/usr/local/bin/chromedriver")  # Или используйте ChromeDriverManager().install()
  # options.add_argument("--headless")

  driver_path = get_cached_chromedriver()
  if not driver_path:
   driver_path = ChromeDriverManager().install()
  driver = webdriver.Chrome(service=Service(driver_path), options=option)
  # Инициализация драйвера
  # driver = webdriver.Chrome(service=service, options=option)

  # Открываем сайт
  driver.get("https://arena.ai")
  input()
except Exception as ex1:
    print(ex1)  # driver.close()  # driver.quit()
    pass
    # prefs = {'safebrowsing.enabled': True,  "credentials_enable_service": False,
    #          "profile.password_manager_enabled": False, "credentials_enable_service": False,
    #          "profile.password_manager_enabled": False,    "profile.managed_default_content_settings.images": 0,  # - Отключить загрузку CSS:
    #          # "profile.default_content_setting_values.javascript": 2,           # - Отключить загрузку JavaScript:
    #          "profile.default_content_setting_values.cache": 0  # - Включить кэширование:
    #          }
    # option.add_experimental_option("prefs", prefs)
    # option.add_argument("--disable-blink-features=AutomationControlled")
    # option.add_argument('--disable-web-security')
    # option.add_argument("--disk-cache-size=0")
    # option.add_argument("--media-cache-size=0")
    # option.add_argument("--automatic-wait-for-preview")
    # option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
    # option.add_argument("--disable-site-isolation-trials")
    # option.add_argument('--user-data-dir=/home/egor/.config/google-chrome')
    # prefs = {'safebrowsing.enabled': True,
    #          "credentials_enable_service": False,
    #          "profile.password_manager_enabled": False,
    #          "credentials_enable_service": False,
    #          "profile.password_manager_enabled": False,
    #          "profile.managed_default_content_settings.images": 0,
    #          # - Отключить загрузку CSS:
    #          # "profile.default_content_setting_values.javascript": 2,
    #          # - Отключить загрузку JavaScript:
    #          "profile.default_content_setting_values.cache": 0
    #          # - Включить кэширование:
    #          }
    # option.add_experimental_option("prefs", prefs)
    # option.add_argument('--disable-infobars')
    # option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
    # option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36")
    # option.add_argument("--disable-dev-shm-usage")
    # option.add_argument("--use-fake-ui-for-media-stream")  # звук
    # # option.add_argument('--allow-running-insecure-content')
    # option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
    # option.add_argument("--disable-blink-features=AutomationControlled")
    # option.add_argument('--disable-web-security')
    # option.add_argument("--disk-cache-size=0")
    # option.add_argument("--media-cache-size=0")
    # option.add_argument("--automatic-wait-for-preview")
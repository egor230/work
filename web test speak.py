import os, time, subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

driver = 0
prefs = {'safebrowsing.enabled': True,
         "credentials_enable_service": False,
         "profile.password_manager_enabled": False,
         "credentials_enable_service": False,
         "profile.password_manager_enabled": False,
         "profile.managed_default_content_settings.images": 0,  # - Отключить загрузку CSS:
         # "profile.default_content_setting_values.javascript": 2,           # - Отключить загрузку JavaScript:
         "profile.default_content_setting_values.cache": 0  # - Включить кэширование:
         }

try:
  option = webdriver.ChromeOptions()
  # option.add_experimental_option("prefs", prefs)
  option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
  option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36")
  option.add_argument("--use-fake-ui-for-media-stream")  # звук
  option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
  option.add_argument('--disable-web-security')
  option.add_argument("--disable-blink-features=AutomationControlled")
  option.add_experimental_option("useAutomationExtension", True)
  option.add_argument("--disable-dev-shm-usage")  # помогает в Linux с /dev/shm
  option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36")
  option.add_argument("--disable-blink-features=AutomationControlled")  # Скрыть признаки автоматизации
  option.add_argument("--disable-notifications")  # Отключить уведомления
  option.add_argument("--use-fake-ui-for-media-stream")  # Разрешить доступ к микрофону
  option.add_extension('/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache/Browsec VPN.crx')  # Загрузка расширения
  option.add_argument("--user-data-dir=/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache/chrome_profile")  # Папка для профиля Chrome
  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                            options=option)
  driver.get("https://www.speechtexter.com")  # открыть сайт    # Пауза для загрузки контента
  time.sleep(2)
  input()
except Exception as ex2:
   print(ex2)
   pass


  # option.add_argument("--disable-dev-shm-usage")  # Совместимость с Linux

  # # Указываем путь к пользовательскому профилю Chrome
  # option.add_argument('--ignore-certificate-errors')
  # option.add_argument('--allow-running-insecure-content')
  # driver.delete_all_cookies()
  # driver.execute_cdp_cmd('Network.clearBrowserCache', {})

  # option.add_argument("--disable-blink-features=AutomationControlled")
  # option.add_argument('--disable-web-security')
  # option.add_argument("--automatic-wait-for-preview")
  # option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
  # option.add_argument("--disable-blink-features=AutomationControlled") # driver.set_window_position(600, 650)  # driver.set_window_size(624, 368) # optiol

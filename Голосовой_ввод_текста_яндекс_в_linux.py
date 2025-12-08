from libs_voice import *
import tkinter as tk
from tkinter import Frame, Label
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key
driver = 0
previous_message = None
def on_press(key):  # обработчик клави.  # print(key )
 key = str(key).replace(" ", "")
 if key == "Key.shift_r":  #
  k.set_flag(True)
  return True
 if key == "Key.space" or key == "Key.right" or key == "Key.left" \
  or key == "Key.down" or key == "Key.up":
  k.set_flag(False)
  return True
 if key == "Key.alt":
  driver = k.get_driver()
  k.update_dict()
  return True
 else:
  return True
def on_release(key):
 pass
 return True
def start_listener():
 global listener
 listener = keyboard.Listener(on_press=on_press, on_release=on_release)
 listener.start()

start_listener()  # Запускаем слушатель# driver.set_window_position(1, 505)
option = get_option()  # Включить настройки.# option.add_argument("--headless")  # Включение headless-режима
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)  # driver.set_window_size(553, 357)  # optiol
driver.get("https://alice.yandex.ru/chat/01938823-14ea-4000-bd7a-3cca57830d6a/")  # открыть сайт
# Размер окна: Ширина = 693, Высота = 407  # Координаты окна: X = 662, Y = 292
excluded_phrases = ["С чего начнём?Нарисовать картинку", "Для звонков телефон как-то удобнее, давайте попробую там.", "Яндекс — с АлисойБыстрый поиск и Алиса всегда рядомПоиск текстом, картинкой или голосомУмная",
                    "Три заветных слова: мобильное приложение Яндекса. Там такое наверняка можно сделать."]  # input()      # Получение текущего адреса страницы

html = driver.page_source
# with open('page_source.txt', 'w', encoding='utf-8') as file:
#   file.write(html)

# ---------- настройки ----------
ICON_PATH = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.png"
mic_on = True
tray = None   # будет создано в start_tray()
counts = 0  # len([message.text.strip() for message in driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')])
previous_message = ""
def tray_left(icon, button):
 global mic_on
 mic_on = not mic_on
 set_mute("0" if mic_on else "1")
 icon.title = "OFF" if mic_on else "ON"

def start_tray():
 global tray
 img = Image.open(ICON_PATH)
 tray = Icon("OFF" if mic_on else "ON", img, title="OFF" if mic_on else "ON",
             menu=Menu(MenuItem("ON OFF", tray_left)) )
 tray.on_click = tray_left
 tray.run()

set_mute("0" if mic_on else "1") # вкл микрофон.

def run_app(driver, len_c):
 def update_label():
   nonlocal len_c
   try:
    if not mic_on:
      root.withdraw()  # Сначала скрываем окно
    else:
      root.deiconify()
      last_user_container = driver.find_elements(By.CSS_SELECTOR, ".MessageBubble-Container_from-user")[-1]
      message = last_user_container.find_element(By.CSS_SELECTOR, ".MessageBubble").text.strip()
      #   oknyx_lottie = soup.find('div', class_='StandaloneOknyx')  # Ищем SVG, у которого нет класса animation-hidden
      #   active_svg = oknyx_lottie.find('svg', class_=lambda x: x and 'animation-hidden' not in x.split())
      #   if oknyx_lottie and active_svg:
      #  message = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text   # <-- должна быть определена где-то

      label.config(text=str(message))
      len_message = len(message) * 10
      if message and len(message) < 4:
        len_message = len(message) * 10 + 12
      root.geometry(f"{len_message}x20+600+1025")
      mic_button = driver.find_element(By.CSS_SELECTOR, ".StandaloneOknyx")  # Альтернатива без ожидания, если элемент точно есть
      aria_label = mic_button.get_attribute('aria-label')
      if 'слушать' in aria_label:
       root.deiconify()
      # else:
      #  if 'стоп' in aria_label:
      #    root.withdraw()
   except Exception as e:
       # print(e)
       pass
   root.after(450, lambda: update_label())
 
 root = tk.Tk()
 frame = Frame(root)
 label = tk.Label(frame, text="...", font='Times 14', anchor="center")
 label.pack(padx=3, fill=tk.X, expand=True)
 frame.pack(fill=tk.X)
 root.overrideredirect(True)
 root.resizable(True, True)
 root.attributes("-topmost", True)
 update_label()
 threading.Thread(target=start_tray, daemon=True).start()
 root.mainloop()

try:
 driver.implicitly_wait(5)  # Даём странице время загрузиться
 # expand_button = WebDriverWait(driver, 10).until(  EC.element_to_be_clickable((By.XPATH, '//button[@title="Развернуть"]')))# Кликаем на кнопку
 # expand_button.click()  # Находим кнопку с title="Развернуть"
 # mode_button = WebDriverWait(driver, 10).until( EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Продвинутый режим"]]')) )
 # mode_button.click()
 # base_mode_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[.//h5[text()="Базовый режим"]]')))  # Кликаем на кнопку
 # base_mode_button.click()  # Находим первый элемент <li> в списке чатов
 new_chat_button = WebDriverWait(driver, 10).until(
  EC.element_to_be_clickable((By.XPATH, "//button[.//span[@class='AliceButton-Icon']]")) )

 del_all_chats(driver)# Ждём кнопку переключения режима

 new_chat_button.click() # Нажимаем на кнопку
 app_thread = threading.Thread(target=run_app, args=(driver, counts,))
 app_thread.start()
 url = str(driver.current_url)
 button = driver.find_element(By.CSS_SELECTOR, "button[data-testid='oknyx']")  # повторно находим кнопку
 button.click()
 while True:
  try:  # time.sleep(0.33)      # Найдите кнопку микрофона     # Получите значение aria-label
   mic_button = driver.find_element(By.CSS_SELECTOR, ".StandaloneOknyx") # Альтернатива без ожидания, если элемент точно есть
   aria_label = mic_button.get_attribute('aria-label')
   if 'слушать' in aria_label :# Жor "sus" in filter_elem:  # print("on")# 'listening' in filter_elem or
    button.click()
   message, counts1 = get_latest_message(driver, counts) # Находим ВНУТРИ него элемент с классом StandaloneOknyxCore, который содержит data-testid
   oknyx_core = mic_button.find_element(By.CSS_SELECTOR, ".StandaloneOknyxCore")
   # filter_elem = oknyx_core.get_attribute("data-testid")   # Получаем значение атрибута data-testid

   if (counts1 > counts and len(message) != 0 and not any(phrase in message for phrase in excluded_phrases)):
    thread = threading.Thread(target=process_text, args=(message, k,))  # break  #
    #thread.daemon
    thread.start()  #
    thread.join()
    print("+++++++")
    print(counts1)  # print(counts)
    counts = counts1  # break
    time.sleep(1.7)
    button.click()  # print(filter_elem)
  except Exception as ex1:  #   print(ex1)
   current_url = str(driver.current_url)  # Получение текущего адреса страницы
   if "/search/" in current_url:  # Проверка, содержится ли в адресе строка "/alice.yandex.ru/chat/"     # Переход на нужный URL
    print("22222")
    driver.get(url)
    time.sleep(4)  # Ждём, пока список чатов загрузится
    counts = 0
    # del_all_chats(driver)
    # button.click()
    pass
   pass

except Exception as ex1:
 print(ex1)
 pass  # print(number)
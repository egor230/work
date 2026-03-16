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
set_mute("0" if mic_on else "1")
driver.implicitly_wait(5)  # Даём странице время загрузиться
new_chat_button = WebDriverWait(driver, 10).until(
 EC.element_to_be_clickable((By.XPATH, "//button[.//span[@class='AliceButton-Icon']]")))

del_all_chats(driver)  # Ждём кнопку переключения режима

new_chat_button.click()  # Нажимаем на кнопку
url = str(driver.current_url)


class LabelUpdater:
 def __init__(self, root, driver, url, excluded_phrases, k):
  self.root = root
  self.driver = driver
  self.url = url
  self.excluded_phrases = excluded_phrases
  self.k = k
  self.counts = 0
  self.last_message = "..."
  self.mic_on = True  # предполагаем, что mic_on будет управляться отдельно
  
  self.setup_ui()
 
 def setup_ui(self):
  self.frame = tk.Frame(self.root)
  self.label = tk.Label(self.frame, text=self.last_message, font='Times 14', anchor="center")
  self.label.pack(padx=3, fill=tk.X, expand=True)
  self.frame.pack(fill=tk.X)
  
  self.root.overrideredirect(True)
  self.root.resizable(True, True)
  self.root.attributes("-topmost", True)
 
 def update_label(self):
  try:
   button = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='oknyx']")  # повторно находим кнопку
   if not self.mic_on:
    self.root.withdraw()  # Сначала скрываем окно
   else:
    self.root.deiconify()  # Всегда показываем окно когда микрофон включен
    message, counts1 = get_latest_message(self.driver, self.counts)
    
    # Обновляем текст только если есть новое сообщение
    if message and len(message.strip()) > 0:
     self.last_message = message
    # Если message пустое, сохраняем предыдущее значение
    
    self.label.config(text=str(self.last_message))
    len_message = len(self.last_message) * 10
    if self.last_message and len(self.last_message) < 4:
     len_message = len(self.last_message) * 10 + 12
    self.root.geometry(f"{len_message}x20+600+1025")
    
    mic_button = self.driver.find_element(By.CSS_SELECTOR, ".StandaloneOknyx")  # Альтернатива без ожидания, если элемент точно есть
    oknyx_core = mic_button.find_element(By.CSS_SELECTOR, ".StandaloneOknyxCore")
    aria_label = mic_button.get_attribute('aria-label')
    filter_elem = oknyx_core.get_attribute("data-testid")  # Получаем значение атрибута data-testid
    
    if 'слушать' in aria_label or "sus" in filter_elem:  # print("on")# 'listening' in filter_elem or
     button.click()  # Находим ВНУТРИ него элемент с классом StandaloneOknyxCore, который содержит data-testid
    
    if 'стоп' in aria_label:  # Жor "sus" in filter_elem:  # print("on")# 'listening' in filter_elem or
     print(filter_elem)
     # self.root.withdraw()  # Сначала скрываем окно
     self.root.deiconify()
    
    if (counts1 > self.counts and len(self.last_message) != 0 and not any(phrase in self.last_message for phrase in self.excluded_phrases)):
     thread = threading.Thread(target=process_text, args=(self.last_message, self.k,))  # break  #
     # thread.daemon
     thread.start()  #
     thread.join()
     print("+++++++")
     print(counts1)  # print(counts)
     self.counts = counts1  # break
     time.sleep(1.7)
     button.click()  # print(filter_elem)
  except Exception as ex1:  # print(ex1)
   current_url = str(self.driver.current_url)  # Получение текущего адреса страницы
   if "/search/" in current_url:  # Проверка, содержится ли в адресе строка "/alice.yandex.ru/chat/"
    print("22222")
    self.driver.get(self.url)
    time.sleep(4)  # Ждём, пока список чатов загрузится
    self.counts = 0
    # del_all_chats(driver)
    # button.click()
    pass
   pass
  finally:
   self.root.after(650, self.update_label)

root = tk.Tk()
frame = tk.Frame(root)
label = tk.Label(frame, text="...", font='Times 14', anchor="center")
label.pack(padx=3, fill=tk.X, expand=True)
frame.pack(fill=tk.X)
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)

# Предполагается, что driver, url, excluded_phrases, k определены где-то ранее
updater = LabelUpdater(root, driver, url, excluded_phrases, k)
threading.Thread(target=start_tray, daemon=True).start()
root.after(650, updater.update_label)
root.mainloop()
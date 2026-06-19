import  psutil
for proc in psutil.process_iter(['pid', 'username', 'cmdline']):

  cmdline = proc.info['cmdline']
  pid= proc.info['pid']
  if "Mouse_setting_control_for_buttons_python_for_linux" in cmdline:
   print(pid)

  # print(dict_save.get_cur_app())# после
  #  # # print(game)
  # print(dict_save.get_current_path_game()) # номер записи.
  # Если мы переключили надпись, стоит флажок запускать старте.
  # start_startup_now(dict_save, root)
  # key_work.key_release(key, 0)
  # if new_path_game != "": # если путь не пустой
  #   game = new_path_game# game новый путь
  # else:
  #   game = dict_save.get_cur_app() # если путь пуст то game это последняя выбранная игра
  # if start_startup.get():# Если кнопка пуск галочка стоит. Кнопка пуск
  #  start1(dict_save, root)# запуск подготовка функции к эмуляции
  # add_button_start = Button(text=" Пуск",  command= lambda:start1(dict_save, root))
  # add_button_start.place(x=780, y=300
  # add_button_start = dict_save.get_add_button_start()# Состояние кнопка пуск.
  # add_button_start["state"] = "disabled"  # выкл кнопку старт.
# filter_elem = WebDriverWait(driver, 4).until( EC.presence_of_element_located((By.CSS_SELECTOR, ".yamb-oknyx-lottie.svelte-rdfi3w"))
# ).get_attribute("data-testid")
# print(mic_button.get_attribute('aria-label'))
# print(driver.find_element(By.CSS_SELECTOR, ".yamb-oknyx-lottie.svelte-rdfi3w").get_attribute("data-testid"))
# while 1:
#   aria_label= mic_button.get_attribute('aria-label')
#   if 'слушать' in aria_label:

# print(aria_label)
# if filter_elem=="oknyx-lottie-suspended" :
#  last_message = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text        # Получаем текст последнего элемента

# command = [sys.executable,  # Путь к текущему интерпретатору Python
#            "text_display.py", str(driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1])]



 # print(dict_save.get_cur_app())#игра до
 # while game!=dict_save.get_cur_app(): # получить значение текущей активной строки.
 # dict_save.set_cur_app(game)
 # dict_save.set_current_path_game(game)
 # print("sw")
 # print("affer")
 # print(dict_save.get_cur_app())#игра после
 # print(dict_save.get_cur_app())
 # mouse_check_button(dict_save, res, dict_save.get_cur_app()) # флаг для удержания кнопки мыши.
# r1 = Checkbutton(variable=start_startup) # Галочка запускать при старте.
# r1.bind("<Button-1>", update_check_button)
# CreateToolTip(r1, text='Запускать при открытий')  # вывод надписи
# r1.place(x=720, y=105)
# process= threading.Thread(target=get_process, args=(dict_save, root,))
# process.start()
# win = keyboard_scrypt(root, " ")
   # print(new_path_game)
   # print(dict_save.get_current_path_game())
   # print(dict_save.get_cur_app())
# def get_process(dict_save, root):# это функция получается активный процесс и pid игр.
#  dict_save.set_current_path_game(dict_save.get_cur_app())
#  while 1:
#    try:
#     time.sleep(0.1)
#     process_id_active = int(subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip())
#     print(process_id_active)
#     dict_save.set_process_id_active(process_id_active)# текущий pid активного процесса.
#     dict_save.set_pid_and_path_window(get_pid_and_path_window()) # здесь мы получаем путь и pid процессов.
#     # print(dict_save.get_current_path_game())    # print( dict_save.get_cur_app())
#
#    except Exception as e:
#      #print(e)
#      pass
# Находим кнопку внутри первого <li> и кликаем
# buttons = driver.find_elements(By.CSS_SELECTOR, "li[class*='chat-list-item']")  # Выводим количество найденных кнопок
# li_element = buttons[0]  # Первый элемент из списка
# chat_button = li_element.find_element(By.CSS_SELECTOR, ".chat-list-item__chat")
# # Находим кнопку с текстом внутри этого <li>
#
# # Кликаем
# chat_button.click()
# buttons.click()

# print(dict_save.get_prev_game())# путь до предыдущей игры
# dict_save.set_prev_game(dict_save.get_current_path_game())
# dict_save.set_current_path_game(new_path_game) #Остановить обработчик клави.  print("change", dict_save.get_cur_app(), sep=" = " )# если поток слушателя оставлен     #time.sleep(1.3)
# dict_save.set_cur_app(new_path_game)#
# Определяем списки
en = ['a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E', 'f', 'F', 'g', 'G', 'h', 'H', 'i', 'I', 'j', 'J', 'k', 'K',
      'l', 'L', 'm', 'M', 'n', 'N', 'o', 'O', 'p', 'P', 'q', 'Q', 'r', 'R', 's', 'S', 't', 'T', 'u', 'U', 'v', 'V',
      'w', 'W', 'x', 'X', 'y', 'Y', 'z', 'Z', '.', ',']

ru = ['ф', 'Ф', 'и', 'И', 'с', 'С', 'в', 'В', 'у', 'У', 'а', 'А', 'п', 'П', 'р', 'Р', 'ш', 'Ш', 'о', 'О', 'л', 'Л',
      'д', 'Д', 'ь', 'Ь', 'т', 'Т', 'щ', 'Щ', 'з', 'З', 'й', 'Й', 'к', 'К', 'ы', 'Ы', 'е', 'Е', 'г', 'Г', 'м', 'М',
      'ц', 'Ц', 'ч', 'Ч', 'н', 'Н', 'я', 'Я', '-', '+', ' ']

# Находим кнопку с title="Развернуть"
# expand_button = WebDriverWait(driver, 10).until(
#   EC.element_to_be_clickable((By.XPATH, '//button[@title="Развернуть"]')))# Кликаем на кнопку
# expand_button.click()
# Ждём, пока список чатов загрузится
# chats = WebDriverWait(driver, 10).until(   EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".chat-list-group__list li.chat-list-item"))
# )
# chats[0].find_element(By.CSS_SELECTOR, "button.chat-list-item__chat").click()
# collapse_button = WebDriverWait(driver, 10).until(  EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Свернуть"]]')) ) # Кликаем на кнопку
# collapse_button.click()
# input()
# html_content = driver.page_source
# with open('page_source.html', 'w', encoding='utf-8') as file:
#   file.write(html_content)
# button.click()

# print(filter_elem)
#   # counts = counts + 1
#   print(counts)
# print(f"Произошла ошибка: {ex}")     # Возвращаем пустую строку и len_c, чтобы избежать None
# command = [sys.executable, "text_display.py", last_message]  # Запускаем скрипт
# subprocess.run(command)

# if counts > len_c  and  message != last_alisa_m:# and filter_elem == "oknyx-lottie-listening":  # counts % 2 == 0 andcounts_user > counts_alisa_m  # and filter_elem =="oknyx-lottie-listening"
#  is_text_stable(driver, 2)
#  message, counts = get_user_messages_info(driver)
#  print("user_m")
#  return message, counts
# else:
#  message, counts = get_user_messages_info(driver)
# alisa_m = driver.find_elements(By.CSS_SELECTOR, '[data-testid="message-bubble-container"]')
# last_alisa_m = alisa_m[-1].text  # последнее сообщение от алисы
# counts_alisa_m = len(alisa_m)
# if 'стоп' in aria_label: # print("ло")


# new_res = k.get_new_dict()
# for word, i in new_res.items():
#   text = k.get_text()
#   pattern = re.compile(re.escape(word), re.IGNORECASE)
#   text1 = pattern.sub(i, text)
#   k.save_text(text1)
# text = k.get_text()
# pattern = re.compile(re.escape(word), re.IGNORECASE)
# text1 = pattern.sub(i, text)
# k.save_text(text1)
'''

oknyx-lottie-suspended
oknyx-lottie-thinking
oknyx-lottie-listening
'''
# html_content = driver.page_source
# with open('page_source.txt', 'w', encoding='utf-8') as file:
#   file.write(html_content)

# collapse_button = WebDriverWait(driver, 10).until(  EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Свернуть"]]')) ) # Кликаем на кнопку
# collapse_button.click()
# JavaScript для поиска активного <svg> и группы <g>
find_number = """
const lottie = document.querySelector('[data-testid="oknyx-lottie-listening"]');
const activeSvg = Array.from(lottie.querySelectorAll('svg')).find(svg =>
    !svg.classList.contains('animation-hidden') && svg.style.display !== 'none'
);
if (activeSvg) {
    const activeGroup = Array.from(activeSvg.querySelectorAll('g[filter]')).find(g =>
        g.style.display !== 'none'
   del_all_chats(driver)
    );
    if (activeGroup) {
        const filterAttr = activeGroup.getAttribute('filter');
        const match = filterAttr.match(/#__lottie_element_(\\d+)/);
        return match ? parseInt(match[1]) : null;
    }
}
return null;
"""
# Находим элемент по классу
# elem = driver.find_element(By.CLASS_NAME, "animation-hidden")
#
# # Получаем HTML-код элемента
# outer_html = elem.get_attribute("outerHTML")
#
# print(outer_html)
# Получим значение style
# Находим элемент с классом "yamb-oknyx-lottie svelte-rdfi3w"
# button.click()
# time.sleep(2)
# button.click()
# button.click()
# while "слушать" not in mic_button.get_attribute('aria-label') and "suspended" not in WebDriverWait(driver, 4).until( EC.presence_of_element_located((By.CSS_SELECTOR, ".yamb-oknyx-lottie.svelte-rdfi3w"))
# ).get_attribute("data-testid"):
# time.sleep(2.3)
# button.click()     #     break
# button = WebDriverWait(driver, 5).until( EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[aria-label="Алиса, начни слушать"]')))
# button.click()
# lottie = driver.find_element(By.CSS_SELECTOR, '[data-testid="oknyx-lottie-listening"]')  # Находим контейнер

# driver.execute_script("document.querySelector('.standalone__header').style.display='none';")
# driver.execute_script(
#   "var element = document.querySelector('.standalone__sidebar'); element.parentNode.removeChild(element);")

# while True:    # Находим все сообщения пользователя
#  initial_text = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text        # Ждём 3 секунды перед повторной проверкой
#  time.sleep(timeout)    # Снова получаем текст и сравниваем
#  final_text = driver.find_elements(By.CLASS_NAME, 'message-bubble_container_from-user')[-1].text
#  if initial_text == final_text:
#    break
# Находим <span> по тексту "Продвинутый режим"
# span = WebDriverWait(driver, 10).until(
#   EC.presence_of_element_located((By.XPATH, '//span[text()="Продвинутый режим"]')))
# button = span.find_element(By.XPATH, "..")
# button.click()# Выполняем клик
# base_mode_option = WebDriverWait(driver, 10).until(
#  EC.element_to_be_clickable((By.XPATH, '//span[contains(text(), "Базовый режим")]/ancestor::button'))
# )
# base_mode_option.click()


# if key =="ж" and k.get_flag_screenshot():# print("jhn")
#   root.withdraw()  # свернуть панель подсказок.
#   dela(root)
#   root.withdraw()  # свернуть панель подсказок.
#   k.set_flag_screenshot(False)
#   load_coordinates_from_json()
#   return True
# if key=="Key.ctrl_r":
#   k.set_flag_screenshot(True)
#   return True
# k.set_flag_screenshot(False)
#

# def from_ghbdtn(text):
#   layout = dict(zip('''qwertyuiop[]asdfghjkl;'zxcvbnm,./`QWERTYUIOP{}ASDFGHJKL:"ZXCVBNM<>?~''',
#                     '''йцукенгшщзхъфывапролджэячсмитьбю.ёЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё''')
#                 )
#   if text not in layout.keys():
#     return text
#   res = str(layout[text])
#   return res

# if key == "Key.end":
#    load_coordinates_from_json()   #  return True
# k.set_flag(False)# флаг записи вводимое слово.
# k.set_swith(True)# откл блок обработчика
# clean_label()# очистка подсказок.
# if key == "Key.shift_r" and k.get_flag()==True:
#   # k.set_flag(False)
#   # k.set_replace(True)
#   return True

#
# if key == "<103>" and k.get_replace()==True and len(k.get_list())>6:
#    key1 = k.get_list()[6]
#    replacing_words(key1)
#    return True
# if key != "<105>" and swit==True:
#    print(arg[7].get())
#    key1=""
#
# if key != "<106>" and swit==True:
#    print(arg[8].get())
#    key1=""


# if key == "Key.space" or key =="Key.right"or key =="Key.left" or key =="Key.down" \
#   or key == "Key.delete" or key =="Key.up" and k.get_swith() == True:# блокировка обработчика.
#
#  print("unblock key")
#  k.backspace()
#  k.set_flag(True)# флаг записи вводимое слово.
#  k.set_swith(False)# откл блок обработчика
#  clean_label()# очистка подсказок.
#  return True

# print("block")
# clean_label()# очистка подсказок.
# swit1=swit1+1 # Блокировать ввод, пока не напишется слово
# print(swit1)
# print(k.get_len())
# if swit1==k.get_len():
# 0 swit1=0
# global swit1

# if filter_elem == "oknyx-lottie-thinking" and 'Алиса, стоп' in aria_label:
#  if len_c==0:
#   is_text_stable(driver, 4)
#   button.click()
#  message, counts = get_user_messages(driver)
#  # time.sleep(3)
#  # button.click()
#  return message, counts
# text_content = element.get_attribute('innerHTML')
# style = element.get_attribute('style')    # Ждём появления SVG-группы
# element = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'g[clip-path="url(#__lottie_element_8)"]'))   )
# # Получаем computed style (вычисленное значение display)
# display = driver.execute_script("""  return window.getComputedStyle(arguments[0]).getPropertyValue('display');
# """, element)     # print("Текущее display:", display)


# script = '''#!/bin/bash
# #gsettings set org.gnome.desktop.a11y.keyboard stickykeys-enable false '''
# subprocess.call(['bash', '-c', script])
# script = '''#!/bin/bash
# xte 'keydown Shift_L' 'sleep 1' 'keyup Shift_L'
# '''
# subprocess.call(['bash', '-c', script])
# keyboard.press(Key.shift)  # Удерживаем Shift
# keyboard.release(Key.shift)
#      result = subprocess.run(['xset', 'q'], capture_output=True, text=True)
#  # Проверка успешного выполнения команды
# if result.returncode == 0:      # Получение вывода команды
#  output = result.stdout
#  # Определение текущей раскладки
#  # if '00001000' in output:
#  #  target_layout="ru"
#  if '00000000' in output:
#   target_layout="en"
#   sc = ('xte "ISO_Next_Group"')  # Нажатие левой кнопки мыши
#   subprocess.call(['bash', '-c', sc])  # Дать доступ на чтение и запись любому
#   print("22222222222222222222222222222222")


# en = ['a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E', 'f', 'F', 'g', 'G', 'h', 'H', 'i', 'I', 'j', 'J', 'k', 'K',
#       'l', 'L', 'm', 'M', 'n', 'N', 'o', 'O', 'p', 'P', 'q', 'Q', 'r', 'R', 's', 'S', 't', 'T', 'u', 'U', 'v', 'V',
#       'w', 'W', 'x', 'X', 'y', 'Y', 'z', 'Z', '.', ',']
# ru = ['а', 'А', 'б', 'Б', 'в', 'В', 'г', 'Г', 'д', 'Д', 'е', 'Е', 'ё', 'Ё', 'ж', 'Ж', 'з', 'З', 'и', 'И', 'й', 'Й', 'к',
#       'К', 'л', 'Л', 'м', 'М', 'н', 'Н', 'о', 'О', 'п', 'П', 'р', 'Р', 'с', 'С', 'т', 'Т', 'у', 'У', 'ф', 'Ф', 'х', 'Х',
#       'ц', 'Ц', 'ч', 'Ч', 'ш', 'Ш', 'щ', 'Щ', 'ъ', 'Ъ', 'ы', 'Ы', 'ь', 'Ь', 'э', 'Э', 'ю', 'Ю', 'я', 'Я', '-', '+', ' ']
#
# ln = save_ln()
#
#
# def get_current_keyboard_layout():
#   result = subprocess.run(['xset', 'q'], capture_output=True, text=True)  # Проверка успешного выполнения команды
#   if result.returncode == 0:  # Получение вывода команды
#     output = result.stdout  # Определение текущей раскладки
#     if '00001000' in output:  # print("en")
#       return "en"
#     elif '00000000' in output:  # print("ru")
#       return "ru"
#   return None
#
#
# def switch_language(ln):  # print("opl")
#   script = f'''#!/bin/bash
#
#   xte 'keydown Shift_L' 'keydown Alt_L' 'keyup Shift_L' 'keyup Alt_L'
#   '''
#   subprocess.call(['bash', '-c', script, '_'])
#   time.sleep(0.8)
#   # print(ln)  # input()  # print(get_current_keyboard_layout())
#   while (ln != get_current_keyboard_layout()):
#     time.sleep(1.9)
#   # print("ok")
# ln.save_text(get_current_keyboard_layout())  # язык по умолчанию.
# if ln.get_text() != get_current_keyboard_layout():  # print("sw")
#   switch_language(ln.get_text())



  # else: #print(data_dict)  # print(games_checkmark_paths) # активного окна
    # if ".exe" in key_paths.lower():
    #   last_slash_index = key_paths.rfind('/')
    #   file_name = key_paths[last_slash_index + 1:]  # Берём всё после последнего '/'
    #   key_paths = str(file_name[:-4])#     print(key_paths)
    #   file_path = next((p for p in games_checkmark_paths if key_paths.lower() in p.lower()), None)#
    #   if file_path:#
    #    window_class = os.path.basename(file_name)  # например "game.exe"
    #    search_cmd = ["xdotool", "search", "--class", window_class]
    #    window_ids = subprocess.check_output(search_cmd).decode().split()
    #    for win_id in window_ids:
    #     xprop_cmd = ["xprop", "-id", win_id, "_NET_WM_STATE"]
    #     state = str(subprocess.check_output(xprop_cmd).decode())
    #     if "FOCUSED" in state:#         print(state)
    #      return games_checkmark_paths[get_index_of_path(file_path, games_checkmark_paths)]  # активного окна      #  elif "_NET_WM_STATE_VISIBLE" in state:

    # else:
     # key_paths = list(data_dict.values())
     # file_path = next((p for p in games_checkmark_paths if p in key_paths), None)
     # if file_path:
     #  return games_checkmark_paths[get_index_of_path(file_path, games_checkmark_paths)]  # активного окна
    #key_paths = list(data_dict.values())




















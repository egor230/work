from pathlib import Path
import pyperclip, requests
from libs_voice import *
backup_script_path = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта'''

# Вызываем скрипт
user = subprocess.run(['bash'], input=backup_script_path , stdout=subprocess.PIPE, text=True).stdout.strip()
list_proccers=["obsidian", "Mouse_setting_control_for_buttons_python_for_linux", "obsidian"] #, "nemo""WINWORD","Mouse_setting_control_for_buttons_python_for_linux",
def get_active_window_pid(): #	Получает PID активного окна разными способами. Если один способ не работает, пробует следующий.
  try:  # 1. Пробуем через xdotool
    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
    process_id = subprocess.check_output(['xdotool', 'getwindowpid', active_window_id]).decode().strip()
    return int(process_id)
  except Exception:
    pass  # Если xdotool не сработал, пробуем другой способ

  try:    # 2. Пробуем через xprop
    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
    xprop_output = subprocess.check_output(['xprop', '-id', active_window_id]).decode()
    for line in xprop_output.split("\n"):
      if "_NET_WM_PID" in line:
        return int(line.split()[-1])
  except Exception:
    pass
  try:    # 3. Пробуем через wmctrl
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    wmctrl_output = subprocess.check_output(['wmctrl', '-lp']).decode()
    for line in wmctrl_output.split("\n"):
      if active_window_name in line:
        parts = line.split()
        return int(parts[2])  # PID находится в третьем столбце
  except Exception:
    pass
  try:    # 4. Пробуем через pgrep по названию окна
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    process_id = subprocess.check_output(['pgrep', '-f', active_window_name]).decode().strip().split("\n")[0]
    return int(process_id)
  except Exception:
    pass
  try:    # 3. Получаем название активного окна
    active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
    process_list = subprocess.check_output(['ps', 'axf', '-o', 'pid,ppid,cmd']).decode().split("\n")
    for process in process_list:    # 4. Ищем процессы, связанные с этим окном
      parts = process.strip().split(maxsplit=2)
      if len(parts) < 3:
        continue
      pid, ppid, cmd = parts   # Проверяем, содержит ли команда название активного окна
      if active_window_name.lower() in cmd.lower():
        return int(pid)  # Возвращаем PID, если нашли
      return None  # Если ничего не сработало
  except Exception:
    pass

def check_current_active_window(p):# Получаем идентификатор активного окна
 try:
  active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
  process_id = int(get_active_window_pid())  # print(process_id)
  result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # print(result)
  for line in result.split("\n"):
   user_name = ' '.join(line.split()[0]).replace(" ", "")
   if user_name==user:
     process_name = ' '.join(line.split()[10:])
     pid_id = int(line.split()[1])  # или используйте другой индекс, если нужны другие данные
     if process_id == pid_id and p in str(process_name):
      print("ok")
      return True
  return False
 except:
   pass
backup_script_path = f'''#!/bin/bash
 current_user=$(whoami);
 echo $current_user
 exit;# Завершаем выполнение скрипта'''

 # Вызываем скрипт
user = subprocess.run(['bash'], input=backup_script_path, stdout=subprocess.PIPE, text=True).stdout.strip()
list_proccers = ["obsidian", "Mouse_setting_control_for_buttons_python_for_linux", "obsidian"]  # , "nemo""WINWORD","Mouse_setting_control_for_buttons_python_for_linux",

def get_active_window_pid():  # Получает PID активного окна разными способами. Если один способ не работает, пробует следующий.
  try:  # 1. Пробуем через xdotool
   active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
   process_id = subprocess.check_output(['xdotool', 'getwindowpid', active_window_id]).decode().strip()
   return int(process_id)
  except Exception:
   pass  # Если xdotool не сработал, пробуем другой способ
 
  try:  # 2. Пробуем через xprop
   active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
   xprop_output = subprocess.check_output(['xprop', '-id', active_window_id]).decode()
   for line in xprop_output.split("\n"):
    if "_NET_WM_PID" in line:
     return int(line.split()[-1])
  except Exception:
   pass
  try:  # 3. Пробуем через wmctrl
   active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
   wmctrl_output = subprocess.check_output(['wmctrl', '-lp']).decode()
   for line in wmctrl_output.split("\n"):
    if active_window_name in line:
     parts = line.split()
     return int(parts[2])  # PID находится в третьем столбце
  except Exception:
   pass
  try:  # 4. Пробуем через pgrep по названию окна
   active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
   process_id = subprocess.check_output(['pgrep', '-f', active_window_name]).decode().strip().split("\n")[0]
   return int(process_id)
  except Exception:
   pass
  try:  # 3. Получаем название активного окна
   active_window_name = subprocess.check_output(['xdotool', 'getwindowname', active_window_id]).decode().strip()
   process_list = subprocess.check_output(['ps', 'axf', '-o', 'pid,ppid,cmd']).decode().split("\n")
   for process in process_list:  # 4. Ищем процессы, связанные с этим окном
    parts = process.strip().split(maxsplit=2)
    if len(parts) < 3:
     continue
    pid, ppid, cmd = parts  # Проверяем, содержит ли команда название активного окна
    if active_window_name.lower() in cmd.lower():
     return int(pid)  # Возвращаем PID, если нашли
    return None  # Если ничего не сработало
  except Exception:
   pass

def check_current_active_window(p):  # Получаем идентификатор активного окна
  try:
   active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
   process_id = int(get_active_window_pid())  # print(process_id)
   result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # print(result)
   for line in result.split("\n"):
    user_name = ' '.join(line.split()[0]).replace(" ", "")
    if user_name == user:
     process_name = ' '.join(line.split()[10:])
     pid_id = int(line.split()[1])  # или используйте другой индекс, если нужны другие данные
     if process_id == pid_id and p in str(process_name):
      return True
   return False
  except:
   pass

 # new_file_name = "О чём могут рассказать руки детей.doc"
 # Копирование HTML в буфер обмена
def copy_to_clipboard(html_content):
  # Используем xclip для передачи HTML в буфер обмена
  process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'text/html'],
                             stdin=subprocess.PIPE)
  process.communicate(input=html_content.encode('utf-8'))
  print("HTML с текстом и изображениями скопирован в буфер обмена")

 # Функция для плавной прокрутки страницы вниз с проверкой загрузки
def scroll_page_smoothly(driver, target_title="В чём причина одиночества?", max_scrolls=150, scroll_pause=1):
  articles_dict = {}  # Словарь для хранения всех найденных статей
  target_found = False  # Флаг, найдена ли целевая статья
 
  for scroll_num in range(max_scrolls):
   print(f"--- Прокрутка #{scroll_num + 1} ---")
   # 1. Получаем высоту страницы ДО прокрутки
   last_height = driver.execute_script("return document.body.scrollHeight")
  
   # 2. Медленно и плавно прокручиваем вниз по частям
   current_position = driver.execute_script("return window.pageYOffset")
   target_position = last_height
  
   # Определяем параметры медленной прокрутки
   scroll_step = 900  # Количество пикселей за один шаг (можно уменьшить для еще более медленной прокрутки)
   scroll_delay = 0.03  # Задержка между шагами в секундах (можно увеличить для еще более медленной прокрутки)
  
   # Постепенно прокручиваем до конца страницы
   while current_position < target_position:
    current_position += scroll_step
    if current_position > target_position:
     current_position = target_position
   
    driver.execute_script(f"window.scrollTo({{top: {current_position}, behavior: 'smooth'}});")
    time.sleep(scroll_delay)  # Небольшая пауза между шагами
    # 3. Ждем, пока потенциально загрузится новый контент    # 4. Парсим страницу после прокрутки
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    articles = soup.find_all('article', attrs={'data-testid': 'floor-image-card'})
    # 5. Обрабатываем найденные статьи
    for article in articles:
     # --- Извлечение заголовка ---
     title_elem = article.find('div', attrs={'data-testid': 'card-part-title'})
     title = title_elem.get_text(strip=True) if title_elem else 'No title found'
    
     # --- Извлечение ссылки ---
     link_elem = article.find('a', attrs={'data-testid': 'card-article-link'})
     link = 'No link found'
     if link_elem and link_elem.has_attr('href'):
      link = link_elem['href']
      # Формируем абсолютную ссылку
      if not link.startswith(('http://', 'https://')):
       if link.startswith('/'):
        link = f"https://dzen.ru{link}"
       else:
        # На случай, если ссылка относительная, но не начинается с '/'
        link = f"https://dzen.ru/{link}"  # Добавляем в словарь, если данные корректны
      if title != 'No title found' and link != 'No link found':
       # Избегаем перезаписи, если статья уже была найдена ранее
       if title not in articles_dict:
        articles_dict[title] = link  # print(f"Добавлена: {title}...") # Опционально: лог добавления # --- Проверка на целевую статью ---
      if target_title in title:
       print(f"\nУспех! Статья '{target_title}' была найдена.")
       return articles_dict
      # Прекращаем внутренний цикл обработки статей
      # break
     
      # Если целевая статья найдена, выходим из внешнего цикла прокруток
    # if target_found:
    #  print("--- Прекращена прокрутка, так как статья найдена. ---")
    #  break
  
   # 6. Проверяем, загрузился ли новый контент
   new_height = driver.execute_script("return document.body.scrollHeight")

mouse_move_and_click = '''#!/bin/bash
 # Координаты для перемещения мыши и клика
 coordinates=(
     "242 70"
     "74 73"
     "1653 22"
 )

 # Функция для плавного перемещения мыши и клика
 move_and_click() {
     local x=$1
     local y=$2
     local steps=50  # Количество шагов для плавного перемещения
     local sleep_time=0.03  # Время ожидания между шагами

     # Получаем текущие координаты мыши
     local current_x=$(xdotool getmouselocation --shell | grep X= | cut -d'=' -f2)
     local current_y=$(xdotool getmouselocation --shell | grep Y= | cut -d'=' -f2)

     # Вычисляем шаги для перемещения
     local step_x=$(( (x - current_x) / steps ))
     local step_y=$(( (y - current_y) / steps ))

     # Плавное перемещение мыши
     for ((i=0; i<steps; i++)); do
         current_x=$((current_x + step_x))
         current_y=$((current_y + step_y))
         xdotool mousemove $current_x $current_y
         sleep $sleep_time
     done

     # Симулируем клик левой кнопкой мыши
     xdotool click 1
     sleep 3  # Ждем немного, чтобы увидеть результат
 }

 # Перебираем все координаты и выполняем клик
 for coord in "${coordinates[@]}"; do
     move_and_click $coord
 done'''

def clean_dictionary_keys(res):  # Список недопустимых символов в именах файлов
  invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
   # Создаем новый словарь
  cleaned_res = {}
  # Проходим по всем парам ключ-значение в исходном словаре
  for title, link in res.items():
   # Очищаем ключ (название статьи) от недопустимых символов
   clean_title = title
   for char in invalid_chars:
    clean_title = clean_title.replace(char, '')
   # Добавляем запись с очищенным ключом в новый словарь
   cleaned_res[clean_title] = link
  return cleaned_res

f = '''#!/bin/bash
    pkill -f "WINWORD" '''
def find_image(thread):
  images = ['/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/image word/вставить.png'
   , '/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/image word/сохранить.png'
            # , '/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/image word/закрыть.png'
            ]
  try:
   # images = get_image_paths(folder_path)
   print(images)
   # Многопоточный поиск
   for i in images:
    location = pyautogui.locateOnScreen(i, confidence=0.8)
    if location:
     # print(f"Изображение найдено: {i} в координатах {location}")
     center_x, center_y = pyautogui.center(location)
     while 1:  # Получаем текущие координаты мыши
      time.sleep(3)
      # Получаем координаты центра найденного изображения
      current_x, current_y = pyautogui.position()  # Проверяем, находится ли курсор на координатах изображения
      if (current_x, current_y) != (center_x, center_y):  # Перемещаем курсор мыши к найденным координатам
       pyautogui.moveTo(center_x, center_y, duration=0.5)  # Плавное перемещение
       # print("2")
      else:
       print("Курсор уже на изображении.")
       time.sleep(4)
       pyautogui.click(button='left')  # Это также можно опустить, так как 'left' - з
       time.sleep(4)
       break  # Если нужно остановиться после первого найденного изображения, используйте break
   # thread.join()
   subprocess.call(['bash', '-c', f])  #
  except Exception as ex2:
   print(ex2)
   pass

def run_wine_command(name):
 # Формируем полный путь к файлу
 name = os.path.join(os.getcwd(), str(name))
 word = '''#!/bin/bash
   FILE_PATH="{0}"
   # 1. Запускаем LibreOffice Writer в фоновом режиме
   # libreoffice --writer "$FILE_PATH" &
   wine \"{0}\" &
   # 2. Сохраняем ID процесса Writer
   LO_PID=$!
   # 3. Даем LibreOffice время на загрузку и становление активным окном (очень важно!)
   sleep 4
   # 4. Находим ID окна LibreOffice  Используем команду поиска окна по имени, связанному с файлом
   WINDOW_ID=$(xdotool search --pid "$LO_PID" --name "$(basename "$FILE_PATH")" | head -n 1)
   # 5. Если окно найдено, отправляем команду "Вставить" (Ctrl+V)
   if [ ! -z "$WINDOW_ID" ]; then
     xdotool windowactivate "$WINDOW_ID"
     xte "keydown Control_R" "key V" "keyup Control_R"
     sleep 3
     xte "keydown Shift_L" "key F12" "keyup Shift_L"
     sleep 6   # 6. Завершаем процесс LibreOffice
     # kill $LO_PID
   fi

   exit; '''.format(name)
 # Функция для выполнения команды
 run_command = lambda: subprocess.call(['bash', '-c', word])

 # Создание нового потока и запуск команды в нем
 thread = threading.Thread(target=run_command)
 thread.start()
 # Ожидание завершения потока
 # time.sleep(3)

 # Проверка активного окна
 while True:
   time.sleep(0.4)
   if check_current_active_window("WINWORD"):
     time.sleep(3)
     break
 return thread

def open_documents_from_dict(res1, driver, folder_path="статьи для книги", wine_word_path="/home/egor/.wine/drive_c/Program Files/Microsoft Office/OFFICE11/WINWORD.EXE"):
  res = clean_dictionary_keys(res1)
  for title in res.keys():  # Очищаем название от недопустимых символов для имени файла
   # Формируем имя файла (.doc)
   filename = f"{title}.doc"
   file_path = os.path.join(os.getcwd(), folder_path, filename)
   try:
    thread = run_wine_command(file_path)  # Замените "your_file.exe" на имя вашего файла
    thread.join()
    # copy_to_clipboard(url)
    print(file_path)

    subprocess.call(['bash', '-c', f])  #
    # input()
    # find_image(thread)
    # Опционально: добавить небольшую паузу между открытием файлов,
    # чтобы не перегружать систему, если открывается много документов сразу
    # time.sleep(1) # Потребуется import time
   except Exception as e:
    print(f"Ошибка при открытии файла '{file_path}': {e}")

def copy_and_rename_file(res, source_file="/home/egor/Шаблоны/doc.doc", target_folder="статьи для книги"):
  # Проверяем, существует ли папка "статьи для книги"
  if os.path.exists(target_folder) and os.path.isdir(target_folder):
   print(f"Папка '{target_folder}' найдена.")
  
   # Проверяем, существует ли исходный файл
   if os.path.exists(source_file):
   
    # Проходим по всем ключам словаря (названиям статей)
    for title in res.keys():
     # Очищаем название от недопустимых символов для имени файла
     # Можно добавить больше символов в список, если нужно
     invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
     clean_title = title
     for char in invalid_chars:
      clean_title = clean_title.replace(char, '')
    
     # Формируем новое имя файла (добавляем .doc если его нет)
     new_filename = f"{clean_title}.doc"
     print(f"Исходный файл '{new_filename}' найден.")
     destination_path = os.path.join(target_folder, new_filename)
    
     try:
      # Копируем и переименовываем файл
      shutil.copy2(source_file, destination_path)
      print(f"Файл скопирован и переименован: {destination_path}")
     except Exception as e:
      print(f"Ошибка при копировании файла для '{title}': {e}")
   else:
    print(f"Ошибка: Исходный файл '{source_file}' не найден.")
  else:
   print(f"Ошибка: Папка '{target_folder}' не найдена.")
# Копирование HTML в буфер обмена

def extract_content(html):
  soup = BeautifulSoup(html, 'html.parser')
  # Получаем текст, убирая лишние пробелы
  text = '\n'.join(line.strip() for line in soup.get_text().splitlines() if line.strip())
  # Получаем ссылки на изображения
  images = [img['src'] for img in soup.find_all('img') if 'src' in img.attrs and img['src'].startswith('http')]
  return text, images
# Функция для скачивания изображений
def download_image(img_url, folder="images"):
  os.makedirs(folder, exist_ok=True)
  try:
    response = requests.get(img_url, timeout=10)
    if response.status_code == 200:
      img_name = os.path.join(folder, img_url.split('/')[-1].split('?')[0])
      with open(img_name, 'wb') as f:
        f.write(response.content)
      return img_name
  except Exception as e:
    print(f"Не удалось скачать изображение {img_url}: {e}")
  return None

# Функция для создания документа Word
def create_doc(text, images, output_file="output.doc"):
  doc = Document()
  doc.add_paragraph(text)  # Добавляем текст
  for img_url in images:
    img_path = download_image(img_url)
    if img_path:
      try:
        doc.add_picture(img_path, width=Inches(5.0))  # Добавляем изображение
      except Exception as e:
        print(f"Не удалось добавить изображение {img_path}: {e}")
  doc.save(output_file)
  print(f"Документ сохранен как {output_file}")


mouse_move_and_click = '''#!/bin/bash
# Координаты для перемещения мыши и клика
coordinates=(
    "242 70"
    "74 73"
    "1653 22"
)

# Функция для плавного перемещения мыши и клика
move_and_click() {
    local x=$1
    local y=$2
    local steps=50  # Количество шагов для плавного перемещения
    local sleep_time=0.03  # Время ожидания между шагами

    # Получаем текущие координаты мыши
    local current_x=$(xdotool getmouselocation --shell | grep X= | cut -d'=' -f2)
    local current_y=$(xdotool getmouselocation --shell | grep Y= | cut -d'=' -f2)

    # Вычисляем шаги для перемещения
    local step_x=$(( (x - current_x) / steps ))
    local step_y=$(( (y - current_y) / steps ))

    # Плавное перемещение мыши
    for ((i=0; i<steps; i++)); do
        current_x=$((current_x + step_x))
        current_y=$((current_y + step_y))
        xdotool mousemove $current_x $current_y
        sleep $sleep_time
    done

    # Симулируем клик левой кнопкой мыши
    xdotool click 1
    sleep 3  # Ждем немного, чтобы увидеть результат
}

# Перебираем все координаты и выполняем клик
for coord in "${coordinates[@]}"; do
    move_and_click $coord
done'''

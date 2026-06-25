import pyperclip
import requests
from bs4 import BeautifulSoup
from urllib.request import urlopen
import string
import random
from libs_voice import *
def simplify_html(html):
  # Парсим HTML
  soup = BeautifulSoup(html, 'html.parser')
  # Находим контейнер статьи
  article = soup.find('div', class_='content--article-item__articleItem-WK')

  if not article:
    print("Статья с классом content--article-item__articleItem-WK не найдена")
    html_content = "<div>Статья не найдена</div>"
  else:    # Находим элемент с маркером "С подпиской рекламы не будет"
    marker_text = "С подпиской рекламы не будет"
    marker_element = article.find(lambda tag: marker_text in tag.get_text())

    if marker_element:      # Удаляем сам элемент с маркером и все последующие элементы
      for sibling in marker_element.find_next_siblings():
        sibling.decompose()  # Удаляем все следующие элементы
      marker_element.decompose()  # Удаляем сам маркер
    else:
      print("Маркер 'С подпиской рекламы не будет' не найден, обрабатываем всю статью")

    # Удаляем ненужные элементы внутри статьи (скрипты, стили)
    for tag in article(['script', 'style']):
      tag.decompose()

    # Удаляем ссылки (<a>), сохраняя их содержимое
    for a_tag in article.find_all('a'):
      a_tag.unwrap()

    # Преобразуем относительные ссылки на изображения в абсолютные
    for img in article.find_all('img'):
      src = img.get('src')
      if src and not src.startswith(('http://', 'https://')):
        img['src'] = f"{base_url}{src if src.startswith('/') else '/' + src}"

    # Преобразуем статью в строку HTML
    html_content = str(article).replace("Те, кто мне благодарен за мою помощь при работе с их руками, могут по своему желанию перевести мне денежную благодарность на карту с пометкой \"В дар\". Счёт карты 2202 2063 9554 7743 Сбербанк MИР.","")

  # Копируем результат в буфер обмена через xclip
  process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'text/html'],
                             stdin=subprocess.PIPE)
  process.communicate(input=html_content.encode('utf-8'))

  show_list_id = '''#!/bin/bash
    sleep 2.9
    copyq select 0  '''
  subprocess.run(['bash', '-c', show_list_id])
  print("Чистая статья (без рекламы и рекомендаций) скопирована в буфер обмена")
option = get_option()  # Включить настройки.
# option.add_argument("--headless")  # Включение headless-режима
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
driver.set_window_size(624, 568)  # optiol
driver.set_window_position(600, 250)

# URL страницы
#url = 'https://dzen.ru/a/Xp6ro8Axg3laFW4r'
url = pyperclip.paste()
driver.get(url)  # открыть сайт

# Ждем загрузки страницы
time.sleep(5)  # Длительность ожидания можно настроить
url=driver.page_source
simplify_html(url)
# Получаем HTML-код элемента
element = driver.find_element('xpath', '//*[@class="content--article-item-content__content-1S"]')
element_html = element.get_attribute('outerHTML')

# Парсим HTML-код элемента с помощью BeautifulSoup
#soup = BeautifulSoup(element_html, 'html.parser')


# images = soup.find_all('img')
#
# # Создаем папку, если она не существует
# folder_name = "картинка"
# if not os.path.exists(folder_name):
#     os.makedirs(folder_name)
# # Получаем список всех файлов в папке
# files = os.listdir(folder_name)
# a=[]
# # Удаляем каждый файл
# for file in files:
#  file_path = os.path.join(folder_name, file)
#  if os.path.isfile(file_path):
#    os.remove(file_path)# Удаляем файл
# print("Сохранение изображений в папку:", folder_name)
# for i, img in enumerate(images):
#  if img.has_attr('src'):
#   image_url = img['src']
#   try:
#       response = requests.get(image_url, stream=True)
#       response.raise_for_status()  # Проверяем на ошибки HTTP
#
#       file_name_path = os.path.join(folder_name, f"{i + 1}.jpg")  # Уникальное имя файла
#       with open(file_name_path, 'wb') as file:
#           for chunk in response.iter_content(chunk_size=8192):  # Записываем по частям
#               file.write(chunk)
#
#       # Открываем изображение с помощью Pillow
#       with Image.open(file_name_path) as img:
#
#           output = io.BytesIO()
#           img.save(output, format='PNG')
#           data = output.getvalue()
#       a.append(file_name_path)
#       # time.sleep(3)
#       print(f"Изображение {i + 1} сохранено: {file_name_path}")
#
#   except requests.exceptions.RequestException as e:
#       print(f"Ошибка при загрузке изображения {i + 1}: {e}")
# a.reverse()
response = requests.get(url)
# for file_name_path in a:
#   show_list_id = '''#!/bin/bash
#   xclip -selection clipboard -t image/png -i $"{0}" # Помещаем изображение в буфер обмена
#   sleep 1.9
#     '''.format(file_name_path)
#   subprocess.run(['bash', '-c', show_list_id])

# Получаем очищенный текст страницы
page_text = soup.get_text()
pyperclip.copy(page_text)
# Получаем все теги
all_tags = [tag.name for tag in soup.find_all()]
print("Текст страницы:")
print(page_text)
word = '''#!/bin/bash
wine \"/home/egor/.wine/drive_c/Program Files (x86)/Microsoft Office/OFFICE11/WINWORD.EXE\"
exit;  '''
subprocess.call(['bash', '-c', word])

# print("\nВсе теги на странице:")
# print(set(all_tags))  # Используем set для уникальных тегов

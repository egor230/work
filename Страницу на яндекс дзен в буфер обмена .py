from web_libs import *
#new_file_name = "О чём могут рассказать руки детей.doc"

def simplify_html(html, base_url="https://example.com"):
  """
  Упрощает HTML: извлекает статью, удаляет всё после текста "С подпиской рекламы не будет",
  включая рекламу, подписки и рекомендации, сохраняет только текст и изображения статьи,
  копирует результат в буфер обмена.

  Args:
      html (str): Исходный HTML-код
      base_url (str): Базовый URL для преобразования относительных ссылок на изображения

  Returns:
      None: Результат копируется в буфер обмена
  """
  # Парсим HTML
  soup = BeautifulSoup(html, 'html.parser')

  # Находим контейнер статьи
  article = soup.find('div', class_='content--article-item__articleItem-WK')

  if not article:
    print("Статья с классом content--article-item__articleItem-WK не найдена")
    html_content = "<div>Статья не найдена</div>"
  else:
    # Находим элемент с маркером "С подпиской рекламы не будет"
    marker_text = "С подпиской рекламы не будет"
    marker_element = article.find(lambda tag: marker_text in tag.get_text())

    if marker_element:
      # Удаляем сам элемент с маркером и все последующие элементы
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
try:
  option= get_option()# Включить настройки.
  option.add_argument('--no-sandbox')
  option.add_argument('--disable-dev-shm-usage')    # Указываем уникальную директорию для данных пользователя

  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
  driver.get( pyperclip.paste())# открыть сайт
  driver.implicitly_wait(5)   # Даём странице время загрузиться
  # Ожидаем полной загрузки страницы
  #print(f"Ожидание загрузки страницы: {url}")
  WebDriverWait(driver, 10).until(
  EC.presence_of_element_located((By.TAG_NAME, "body"))  # Ждем, пока <body> появится
  )

  # Получаем содержимое страницы
  html=driver.page_source
  # Парсим HTML-код элемента с помощью BeautifulSoup
  # Упрощаем HTML
  simplified_html = simplify_html(html)

  # Копируем в буфер обмена
  copy_to_clipboard(simplified_html)
  driver.quit()
  # input()
   # Создаем документ
except Exception as ex1:
 print(ex1)
 pass
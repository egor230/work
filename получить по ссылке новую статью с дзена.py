from libs_voice import *
from web_libs import *


def simplify_html(html, base_url="https://dzen.ru"):
 soup = BeautifulSoup(html, 'html.parser')

 # Пробуем несколько способов найти заголовок
 title_element = soup.find('h1', {'data-testid': 'article-title'})
 if not title_element:
  title_element = soup.find('h1', {'itemprop': 'headline'})

 # Дополнительные способы поиска заголовка
 if not title_element:
  # Ищем любой h1 с классом содержащим "title" или "header"
  title_element = soup.find('h1', class_=lambda x: x and any(word in x.lower() for word in ['title', 'header']) if x else False)

 if not title_element:
  # Ищем первый h1 на странице
  title_element = soup.find('h1')

 if not title_element:
  # Ищем в мета-тегах
  meta_title = soup.find('meta', {'property': 'og:title'}) or soup.find('meta', {'name': 'title'})
  if meta_title:
   title_text = meta_title.get('content', '').strip()
   if title_text:
    title_html = f"<h1>{title_text}</h1>"
   else:
    title_text = "Заголовок не найден"
    title_html = f"<h1>{title_text}</h1>"
  else:
   title_text = "Заголовок не найден"
   title_html = f"<h1>{title_text}</h1>"
 else:
  # Очищаем текст заголовка от лишних пробелов
  title_text = title_element.get_text(strip=True)
  title_text = ' '.join(title_text.split())
  title_html = f"<h1>{title_text}</h1>"

 article_body = soup.find('div', {'data-testid': 'article-body'})
 if not article_body:
  body_html = "<div>Текст статьи не найден</div>"
 else:
  body_copy = BeautifulSoup(str(article_body), 'html.parser').div
  if body_copy:
   for tag in body_copy(['script', 'style']):
    tag.decompose()
   for a_tag in body_copy.find_all('a'):
    a_tag.unwrap()
   for img in body_copy.find_all('img'):
    src = img.get('src')
    if src:
     src = src.strip()
     if not src.startswith(('http://', 'https://')):
      if src.startswith('/'):
       img['src'] = f"{base_url}{src}"
      else:
       img['src'] = f"{base_url}/{src}"
   body_copy.attrs = {}
   for tag in body_copy.find_all(True):
    tag.attrs = {k: v for k, v in tag.attrs.items() if k in ['src', 'href', 'alt']}
   body_html = str(body_copy)
  else:
   body_html = "<div>Ошибка обработки текста статьи</div>"

 html_content = f"{title_html}{body_html}".replace(
  "Те, кто мне благодарен за мою помощь при работе с их руками, могут по своему желанию перевести мне денежную благодарность на карту с пометкой \"В дар\". Счёт карты 2202 2063 9554 7743 Сбербанк MИР.",
  "")

 html_content = f"""
 <div>
   <style>
     img {{ max-width: 512px; max-height: 512px; width: auto; height: auto; }}
   </style>
   <div>{html_content}</div>
 </div>
 """

 try:
  # Используем xclip с коротким таймаутом или игнорируем ошибку, чтобы вернуть заголовок
  process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'text/html'], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
  try:
   process.communicate(input=html_content.encode('utf-8'), timeout=5)

   show_list_id = '''#!/bin/bash
             sleep 1.9
             copyq select 0  '''
   subprocess.run(['bash', '-c', show_list_id])

   if process.returncode == 0:
    subprocess.run(['copyq', 'write', 'text/html', html_content])
  except subprocess.TimeoutExpired:
   process.kill()
   print("Предупреждение: xclip не ответил вовремя, продолжаем выполнение.")

  return title_text

 except Exception as e:
  print(f"Ошибка при работе с буфером: {e}")
  return title_text

option = get_option()
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
# url = "https://dzen.ru/a/aIXI1UqpY3gfXc-D"
url = str(pyperclip.paste())
driver.get(url)
# Использование BeautifulSoup для парсинга
res = {}  # Ваш словарь для результатов
source = driver.page_source
res[simplify_html(source)] =url
# print(res)
time.sleep(3)  # Дополнительное время для загрузки контента
copy_and_rename_file(res)
open_documents_from_dict(res, driver)
driver.quit()
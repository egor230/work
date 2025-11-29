from libs_voice import *
from web_libs import *
def simplify_html(html, base_url="https://dzen.ru"):
 soup = BeautifulSoup(html, 'html.parser')
 title_element = soup.find('h1', {'data-testid': 'article-title'})
 if not title_element:
  title_html = "<h1>Заголовок не найден</h1>"
 else:
  title_copy = BeautifulSoup(str(title_element), 'html.parser').h1
  if title_copy:
   title_copy.attrs = {}
   title_html = str(title_copy)
  else:
   title_html = f"<h1>{title_element.get_text(strip=True)}</h1>"
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
 html_content1 = f"<div>{html_content}</div>"
 html_content = f"""
  <div>
   <style>
    img {{
     max-width: 512px;
     max-height: 512px;
     width: auto;
     height: auto;
    }}
   </style>
   {html_content1}
  </div>
  """
 try:
  # subprocess.run(['copyq', 'write', 'text/html', html_content])
  process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'text/html'], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
  stdout, stderr = process.communicate(input=html_content.encode('utf-8'), timeout=10)
  show_list_id = '''#!/bin/bash
    sleep 1.9
    copyq select 0  '''
  subprocess.run(['bash', '-c', show_list_id])
  if process.returncode == 0:
   print("Полный текст статьи успешно скопирован в буфер обмена.")
   subprocess.run(['copyq', 'write', 'text/html', html_content])
   return title_element.get_text(strip=True)
  else:
   print(f"Ошибка xclip: {stderr.decode('utf-8')}")
   # process_text = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
   # stdout_text, stderr_text = process_text.communicate(input=html_content.encode('utf-8'), timeout=10)
   # if process_text.returncode == 0:
   #  print("Текст успешно скопирован как обычный текст.")
   # else:
   #  print(f"Ошибка при копировании как текст: {stderr_text.decode('utf-8')}")
 
  return title_element.get_text(strip=True)
 except Exception as e:
  print(f"Неожиданная ошибка при копировании: {e}")

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
# time.sleep(3)  # Дополнительное время для загрузки контента
copy_and_rename_file(res)
open_documents_from_dict(res, driver)
driver.quit()
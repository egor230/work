from libs_voice import *  # Сохраняем ваш импорт


# Функция для плавной прокрутки страницы вниз с проверкой загрузки
def scroll_page_smoothly(driver, scrolls=3, scroll_pause=4):

 for i in range(scrolls):
  
  # Получаем текущую высоту страницы
  last_height = driver.execute_script("return document.body.scrollHeight")
  
  # Плавно прокручиваем вниз
  driver.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
  
  time.sleep(scroll_pause)
  
  # Проверяем, загрузился ли новый контент
  new_height = driver.execute_script("return document.body.scrollHeight")
  
  if new_height > last_height:
   pass
  else:
   print("Новый контент не загрузился, пробуем еще раз...")
   # Если контент не загрузился, делаем дополнительную прокрутку
   driver.execute_script("window.scrollTo(0, 0);")  # Прокручиваем вверх
   time.sleep(1)
   driver.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")  # И снова вниз
   time.sleep(scroll_pause)
 
def main():
 option = get_option()
 driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
 url = "https://dzen.ru/id/5e81d2448e05bc7f847fbaea?with_premium=1"
 driver.get(url)
 # input()
 # html_content = driver.page_source
 # with open('page_source.html', 'w', encoding='utf-8') as file:
 #   file.write(html_content)

 try:# Вызываем функцию прокрутки
  scroll_page_smoothly(driver, scrolls=3, scroll_pause=5)
  time.sleep(3)  # Дополнительное время для загрузки контента
  
  soup = BeautifulSoup(driver.page_source, 'html.parser')
  
  articles = soup.find_all('article', attrs={'data-testid': 'floor-image-card'})

  for i, article in enumerate(articles, 1):
   title_elem = article.find('div', attrs={'data-testid': 'card-part-title'})
   title = title_elem.get_text(strip=True) if title_elem else 'No title found'
 
   link_elem = article.find('a', attrs={'data-testid': 'card-article-link'})
   if link_elem and link_elem.has_attr('href'):
    link = link_elem['href']
    # Проверяем, является ли ссылка абсолютной
    if not link.startswith(('http://', 'https://')):
     # Предполагаем, что относительные ссылки начинаются с '/'
     if link.startswith('/'):
      link = f"https://dzen.ru{link}"
     else:
      link = f"https://dzen.ru/{link}"
   else:
    link = 'No link found'
 
   # Выводим результат сразу в цикле
   print(f"{i}. {title} - {link}")


 except Exception as e:
  print(f"Произошла ошибка: {str(e)}")
 finally:
  driver.quit()


if __name__ == "__main__":
 main()
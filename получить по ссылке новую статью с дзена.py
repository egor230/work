from libs_voice import *
from web_libs import *

def simplify_html(html, base_url="https://dzen.ru"):
 soup = BeautifulSoup(html, 'html.parser')
 title_element = None
 title_text = "Заголовок не найден"
 
 # 1. Проверяем h1 с data-testid
 title_element = soup.find('h1', {'data-testid': 'article-title'})
 
 # 2. Проверяем h1 с itemprop
 if not title_element:
  title_element = soup.find('h1', {'itemprop': 'headline'})
 
 # 3. Проверяем h1 с классами, содержащими "title", "header" или "heading"
 if not title_element:
  title_element = soup.find('h1', class_=lambda x: x and any(word in x.lower() for word in ['title', 'header', 'heading']) if x else False)
 
 # 4. Проверяем первый h1 на странице
 if not title_element:
  title_element = soup.find('h1')
 
 # 5. Проверяем тег <title>
 if not title_element:
  title_element = soup.find('title')
  if title_element:
   title_text = title_element.get_text(strip=True)
   title_html = f"<h1>{title_text}</h1>"
 
 # 6. Проверяем мета-теги (og:title, twitter:title, name="title")
 if not title_element or not title_text:
  meta_title = (
    soup.find('meta', {'property': 'og:title'}) or
    soup.find('meta', {'property': 'twitter:title'}) or
    soup.find('meta', {'name': 'title'})
  )
  if meta_title and meta_title.get('content'):
   title_text = meta_title.get('content', '').strip()
   title_html = f"<h1>{title_text}</h1>"
 
 # 7. Если ничего не нашли, используем дефолтный текст
 if not title_element and title_text == "Заголовок не найден":
  title_html = f"<h1>{title_text}</h1>"
 else:
  # Очищаем текст заголовка от лишних пробелов
  if title_element and title_element.name != 'title':
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

 def _prepare_profile(self):  # Подбирает рабочий user-data-dir (NTFS может быть read-only).
  import shutil as _shutil
  ntfs_profile = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome"
  local_profile = os.path.expanduser("~/.config/alice-voice-chrome")
  stale_locks = ("DevToolsActivePort", "SingletonLock", "SingletonCookie", "SingletonSocket")

  def _clean_locks(d):
   for name in stale_locks:
    p = os.path.join(d, name)
    try:
     if os.path.lexists(p):
      os.remove(p)
    except Exception:
     pass

  try:
   if os.path.isdir(ntfs_profile):
    _clean_locks(ntfs_profile)
    probe = os.path.join(ntfs_profile, ".write_test")
    with open(probe, "w"):
     pass
    os.remove(probe)
    return ntfs_profile
  except Exception as e:
   print(f"Профиль на NTFS недоступен для записи ({e}) — использую локальный профиль")
  try:
   if not os.path.isdir(os.path.join(local_profile, "Default")):
    print("Копирую профиль в локальное хранилище (один раз)...")
    os.makedirs(local_profile, exist_ok=True)
    _shutil.copytree(
     ntfs_profile, local_profile,
     ignore=_shutil.ignore_patterns(
      "Cache", "Code Cache", "GPUCache", "GrDpCache", "ShaderCache",
      "DawnGraphiteCache", "DawnWebGPUCache", "Crashpad", "Crash Reports",
      "Service Worker", "optimization_guide_model_store"),
     symlinks=True)
   _clean_locks(local_profile)
   return local_profile
  except Exception as e:
   print(f"Не удалось скопировать профиль ({e}) — использую чистый локальный профиль")
   os.makedirs(local_profile, exist_ok=True)
   return local_profile

def _chrome_version():
  import subprocess as _sp, re as _re
  for cmd in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
   try:
    out = _sp.run([cmd, "--version"], capture_output=True, text=True, timeout=10).stdout
    m = _re.search(r'(\d+\.\d+\.\d+\.\d+)', out)
    if m:
     return [int(x) for x in m.group(1).split(".")]
   except Exception:
    continue
  return None

def get_chromedriver_path():
  import glob as _glob, re as _re, os as _os
  def _ver(p):
   m = _re.search(r'(\d+\.\d+\.\d+\.\d+)', p)
   return [int(x) for x in m.group(1).split(".")] if m else None
  found = []
  for pat in (
   _os.path.expanduser("~/.wdm/drivers/chromedriver/linux64/*/chromedriver-linux64/chromedriver"),
  ):
   for path in _glob.glob(pat):
    if _os.access(path, _os.X_OK):
     v = _ver(path)
     if v:
      found.append((v, path))
  if not found:
   return None, []
  chrome_ver = _chrome_version()
  exact = None
  if chrome_ver and len(chrome_ver) >= 3:
   for v, p in found:
    if v[:3] == chrome_ver[:3]:
     exact = p
     break
  if exact:
   return exact, [exact]
  found.sort(key=lambda t: t[0], reverse=True)
  return found[0][1], [p for _, p in found]

def main():
  driver = None
  options = get_option()
  options.add_argument("--disable-extensions")
  # options.add_argument(f'--user-data-dir={self._prepare_profile()}')
  # options.add_argument("--headless=new")

  options.add_argument("--no-proxy-server")
  driver_path, candidates = get_chromedriver_path()
  last_err = None
  for path in (candidates or []):
   try:
    driver = webdriver.Chrome(service=Service(path), options=options)
    print(f"Chrome запущен с локальным драйвером: {path}")
    break
   except Exception as e:
    last_err = e
    print(f"Не удалось запустить Chrome с драйвером {path}: {e}")
  if driver is None:
   if candidates:
    print("Все локальные драйверы не подошли — пытаюсь скачать свежий (нужна сеть)...")
   else:
    print("Локальный chromedriver не найден — пытаюсь скачать (нужна сеть)...")
   try:
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=1) as ex:
     path = ex.submit(lambda: ChromeDriverManager().install()).result(timeout=120)
    driver = webdriver.Chrome(service=Service(path), options=options)
   except Exception as e:
    print(f"Не удалось получить chromedriver: {e}")
    if last_err:
     raise last_err
    raise

  url = "https://dzen.ru/a/anBARge4ThSHKg_w"
  # url = str(pyperclip.paste())
  driver.get(url)
  # Использование BeautifulSoup для парсинга
  res = {}  # Ваш словарь для результатов
  source = driver.page_source
  res[simplify_html(source)] = url
  # print(res)
  time.sleep(3)  # Дополнительное время для загрузки контента
  copy_and_rename_file(res)
  open_documents_from_dict(res, driver)
  driver.quit()

if __name__ == "__main__":
  main()

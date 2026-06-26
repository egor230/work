from pytq_libs_voice import *
import logging, pyperclip

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

class YouTubeSubtitleExtractor:
  def __init__(self):
    self.profile_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome"
    self.shadow_host_selector = "#-extension-root"
    self.button_text = "Get Subtitles"
    self.subtitle_item_selector = ".xiiOB8Kg"
    self.timestamp_selector = ".AM6JRIsD"
    self.service_words = [
      "YouTube Video Transcript", "Subtitles Pro Transcription Summary", "Export",
      "Language: English", "Language: Russian", "Contact us: sup@yt-transcript.help",
      "Get Subtitles", "Текст скопирован в буфер обмена", "Copy to clipboard",
    ]
    self.driver = None

  def open_url(self, url):  # Открывает URL и ждёт полной загрузки страницы
    logger.info(f"Открытие URL: {url}")
    self.driver.get(url)
    WebDriverWait(self.driver, 60).until(lambda d: d.execute_script("return document.readyState") == "complete")

  def get_latest_video_url(self, channel_url):  # Определяет тип ссылки и возвращает URL последнего видео или прямую ссылку
    options = get_option()
    options.add_argument('--user-data-dir=' + self.profile_path)
    self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    self.driver.set_page_load_timeout(60)
    self.driver.set_script_timeout(60)
    if '/watch?v=' in channel_url:
      logger.info(f"Ссылка является видео: {channel_url}")
      return channel_url
    base_url = channel_url.rstrip('/')
    videos_url = base_url if base_url.endswith('/videos') else f"{base_url}/videos"
    logger.info(f"Переход на вкладку видео канала: {videos_url}")
    self.open_url(videos_url)
    try:
      WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/watch?v=']")))
    except TimeoutException:
      logger.error("Не найдено ни одной ссылки на видео на странице канала.")
      return None
    video_url = self.driver.execute_script("var l=document.querySelectorAll('a[href*=\"/watch?v=\"]');return l.length?l[0].href:null;")
    if video_url:
      logger.info(f"Найдено последнее видео: {video_url}")
      return video_url
    logger.error("Не удалось извлечь ссылку на видео.")
    return None

  def prepare_video_page(self, video_url):  # Открывает страницу видео и ставит его на паузу
    self.open_url(video_url)
    self.driver.execute_script("document.querySelector('video')&&document.querySelector('video').pause();")

  def wait_for_extension_shadow_root(self, timeout=15):  # Ожидает появления shadow root расширения в DOM
    logger.info("Ожидание элемента расширения в DOM...")
    try:
      WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, self.shadow_host_selector)))
    except TimeoutException:
      logger.error("Элемент расширения не найден.")
      raise

  def click_get_subtitles(self, timeout=15):  # Ищет и нажимает кнопку получения субтитров в shadow root
    logger.info("Поиск и нажатие кнопки 'Get Subtitles'...")
    script = f"""var h=document.querySelector('{self.shadow_host_selector}');if(!h)return 'host not found';
var sr=h.shadowRoot;if(!sr)return 'shadowRoot not found';
var b=Array.from(sr.querySelectorAll('button')).find(function(x){{return x.textContent.indexOf('{self.button_text}')!==-1;}});
if(!b)return 'button not found';b.click();return 'clicked';"""
    start = time.time()
    while time.time() - start < timeout:
      if self.driver.execute_script(script) == 'clicked':
        logger.info("Кнопка нажата.")
        return
      time.sleep(0.5)
    raise TimeoutException(f"Не удалось нажать кнопку '{self.button_text}'.")

  def get_subtitles_raw_text(self):  # Извлекает сырой текст субтитров из shadow root расширения
    script = f"""var h=document.querySelector('{self.shadow_host_selector}');if(!h)return '';
var sr=h.shadowRoot;if(!sr)return '';
var items=sr.querySelectorAll('{self.subtitle_item_selector}');if(!items||!items.length)return '';
var t=[];for(var i=0;i<items.length;i++){{var c=items[i].cloneNode(true);
var ts=c.querySelector('{self.timestamp_selector}');if(ts)ts.remove();
var txt=c.textContent.trim();if(txt.length)t.push(txt);}}return t.join('\\n');"""
    return self.driver.execute_script(script) or ""

  def wait_for_subtitles_smart(self, initial_wait=5, check_interval=2, max_wait=60, min_items=3):  # Умное ожидание стабилизации субтитров с проверкой количества блоков
    logger.info(f"Ожидание загрузки субтитров (начальная пауза {initial_wait} сек)...")
    time.sleep(initial_wait)
    prev_count = stable_count = 0
    start_time = time.time()
    last_raw = ""
    while time.time() - start_time < max_wait:
      raw = self.get_subtitles_raw_text()
      last_raw = raw
      current_count = len([l for l in raw.split('\n') if l.strip()])
      logger.info(f"Найдено блоков субтитров: {current_count}")
      if current_count >= min_items:
        stable_count = stable_count + 1 if current_count == prev_count else 0
        if stable_count >= 3:
          logger.info(f"Субтитры загружены (блоков: {current_count}).")
          return raw
      else:
        stable_count = 0
      prev_count = current_count
      time.sleep(check_interval)
    if last_raw.strip():
      logger.warning("Время истекло, но субтитры частично загружены.")
      return last_raw
    raise TimeoutException("Субтитры не появились за отведённое время.")
  
  def clean_transcript(self, raw_text, group_sentences=True):  # Очищает текст от служебных слов и группирует предложения в абзацы
   if not raw_text:
    return ""
   
   text = raw_text
   
   # Удаляем служебные слова
   for word in self.service_words:
    text = text.replace(word, "")
   
   # Удаляем временные метки (только если они стоят отдельно, не внутри чисел)
   # Ищем паттерны типа 12:34 или 12:34:56, окруженные пробелами или началом/концом строки
   text = re.sub(r'(?:^|\s)\d{1,2}:\d{2}(?::\d{2})?(?:\s|$)', ' ', text)
   
   # Удаляем специальные обозначения в квадратных скобках
   text = re.sub(r'\[.*?\]', '', text)
   
   # Удаляем символы >>
   text = text.replace(">>", "")
   
   # Нормализуем пробелы (убираем множественные пробелы)
   text = re.sub(r' +', ' ', text)
   
   # Нормализуем переносы строк (не более двух подряд)
   text = re.sub(r'\n{3,}', '\n\n', text)
   
   # Убираем пробелы в начале и конце строк
   text = '\n'.join(line.strip() for line in text.split('\n'))
   
   if group_sentences:
    # Разбиваем на предложения
    sentences = re.findall(r'[^.!?]*[.!?]+', text)
    if len(sentences) > 1:
     # Группируем по 3-4 предложения в абзац для лучшей читаемости
     paragraphs = []
     for i in range(0, len(sentences), 3):
      paragraph = ' '.join(sentences[i:i + 3]).strip()
      if paragraph:
       paragraphs.append(paragraph)
     text = '\n\n'.join(paragraphs)
   
   # Финальная очистка
   text = text.strip()
   text=text.replace("  "," ")
   return text
  def get_video_title(self):  # Возвращает очищенный заголовок видео
    return self.driver.title.replace(" - YouTube", "").strip()

  def process_channel_from_clipboard(self):  # Основной метод: берёт ссылку из буфера, находит видео и сохраняет субтитры в файл
    channel_url = pyperclip.paste().strip()
    if not channel_url or "youtube.com" not in channel_url:
      logger.error(f"В буфере обмена не обнаружена корректная ссылка на YouTube. Найдено: {channel_url}")
      return
    logger.info(f"Ссылка получена из буфера обмена: {channel_url}")
    try:
      video_url = self.get_latest_video_url(channel_url)
      self.prepare_video_page(video_url)
      self.wait_for_extension_shadow_root()
      self.click_get_subtitles()
      raw_text = self.wait_for_subtitles_smart()
      clean_text = self.clean_transcript(raw_text, group_sentences=True)
      title = self.get_video_title()
      full_text = f"\n{clean_text}"
      save_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/важное/ии/web"
      os.makedirs(save_dir, exist_ok=True)
      safe_title = re.sub(r'[\\/*?:"<>|]', "", title.strip()) if title else f"video_{int(time.time())}"
      filepath = os.path.join(save_dir, f"{safe_title}.md")
      with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_text)
      logger.info(f"Текст сохранён в файл: {filepath}")
    except Exception as e:
      logger.error(f"Ошибка в процессе выполнения: {e}", exc_info=True)
    finally:
      if self.driver:
        self.driver.quit()
        logger.info("Браузер закрыт.")

if __name__ == "__main__":
  extractor = YouTubeSubtitleExtractor()
  extractor.process_channel_from_clipboard()
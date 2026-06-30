from pytq_libs_voice import *
import logging, pyperclip
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

class YouTubeSubtitleExtractor:
  def __init__(self):
    self.profile_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome"
    self.shadow_host_selector = "#-extension-root"
    self.button_text = "Get Subtitles"
    self.subtitle_item_selector = ".xiiOB8Kg"
    self.timestamp_selector = ".AM6JRIsD"
    self.save_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/важное/ии/web"
    self.service_words = [
      "YouTube Video Transcript", "Subtitles Pro Transcription Summary", "Export",
      "Language: English", "Language: Russian", "Contact us: sup@yt-transcript.help",
      "Get Subtitles", "Текст скопирован в буфер обмена", "Copy to clipboard",
    ]
    self.driver = None
    # Предкомпилируем регулярные выражения для скорости
    self._re_timestamp = re.compile(r'(?:^|\s)\d{1,2}:\d{2}(?::\d{2})?(?:\s|$)')
    self._re_brackets = re.compile(r'\[.*?\]')
    self._re_multi_space = re.compile(r' +')
    self._re_multi_newline = re.compile(r'\n{3,}')
    self._re_sentence = re.compile(r'[^.!?]*[.!?]+')
    self._re_unsafe_chars = re.compile(r'[\\/*?:"<>|]')

  def _init_driver(self) -> None:  # Создаёт и настраивает драйвер Chrome с пользовательским профилем
    options = get_option()
    options.add_argument('--user-data-dir=' + self.profile_path)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    self.driver.set_page_load_timeout(60)
    self.driver.maximize_window()

  def open_url(self, url: str) -> None:  # Открывает URL и ждёт полной загрузки страницы
    logger.info(f"Открытие URL: {url}")
    self.driver.get(url)
    WebDriverWait(self.driver, 60).until(lambda d: d.execute_script("return document.readyState") == "complete")

  def get_latest_video_url(self, channel_url: str) -> Optional[str]:  # Определяет тип ссылки и возвращает URL последнего видео или прямую ссылку
    self._init_driver()
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

  def prepare_video_page(self, video_url: str) -> None:  # Открывает страницу видео и ставит его на паузу
    self.open_url(video_url)
    self.driver.execute_script("var v=document.querySelector('video');if(v){v.pause();v.currentTime=0;}")

  def wait_for_extension_shadow_root(self, timeout: int = 15) -> None:  # Ожидает появления shadow root расширения в DOM
    logger.info("Ожидание элемента расширения в DOM...")
    try:
      WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, self.shadow_host_selector)))
    except TimeoutException:
      logger.error("Элемент расширения не найден.")
      raise

  def click_get_subtitles(self, timeout: int = 15) -> None:  # Ищет и нажимает кнопку получения субтитров в shadow root
    logger.info("Поиск и нажатие кнопки 'Get Subtitles'...")
    script = f"""var h=document.querySelector('{self.shadow_host_selector}');if(!h)return 'host not found';
var sr=h.shadowRoot;if(!sr)return 'shadowRoot not found';
var b=Array.from(sr.querySelectorAll('button')).find(function(x){{return x.textContent.indexOf('{self.button_text}')!==-1;}});
if(!b)return 'button not found';b.click();return 'clicked';"""
    start = time.monotonic()
    last_status = ""
    while time.monotonic() - start < timeout:
      last_status = self.driver.execute_script(script)
      if last_status == 'clicked':
        logger.info("Кнопка нажата.")
        return
      time.sleep(0.3)
    raise TimeoutException(f"Не удалось нажать кнопку '{self.button_text}'. Последний статус: {last_status}")

  def get_subtitles_raw_text(self) -> str:  # Извлекает сырой текст субтитров из shadow root расширения
    script = f"""var h=document.querySelector('{self.shadow_host_selector}');if(!h)return '';
var sr=h.shadowRoot;if(!sr)return '';
var items=sr.querySelectorAll('{self.subtitle_item_selector}');if(!items||!items.length)return '';
var t=[];for(var i=0;i<items.length;i++){{var c=items[i].cloneNode(true);
var ts=c.querySelector('{self.timestamp_selector}');if(ts)ts.remove();
var txt=c.textContent.trim();if(txt.length)t.push(txt);}}return t.join('\\n');"""
    try:
      return self.driver.execute_script(script) or ""
    except Exception as e:
      logger.warning(f"Ошибка при извлечении текста субтитров: {e}")
      return ""

  def wait_for_subtitles_smart(self, initial_wait: float = 3.0, check_interval: float = 1.0, max_wait: float = 60.0, min_items: int = 3) -> str:  # Умное ожидание стабилизации субтитров с проверкой количества блоков
    logger.info(f"Ожидание загрузки субтитров (начальная пауза {initial_wait} сек)...")
    time.sleep(initial_wait)
    prev_count = stable_count = 0
    start_time = time.monotonic()
    last_raw = ""
    while time.monotonic() - start_time < max_wait:
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

  def clean_transcript(self, raw_text: str, group_sentences: bool = True) -> str:  # Очищает текст от служебных слов и группирует предложения в абзацы
   if not raw_text:
    return ""

   text = raw_text

   # Удаляем служебные слова (сначала длинные, чтобы не было частичных совпадений)
   for word in sorted(self.service_words, key=len, reverse=True):
    text = text.replace(word, "")

   # Удаляем временные метки (только если они стоят отдельно, не внутри чисел)
   text = self._re_timestamp.sub(' ', text)

   # Удаляем специальные обозначения в квадратных скобках
   text = self._re_brackets.sub('', text)

   # Удаляем символы >>
   text = text.replace(">>", "")

   # Нормализуем пробелы (убираем множественные пробелы)
   text = self._re_multi_space.sub(' ', text)

   # Нормализуем переносы строк (не более двух подряд)
   text = self._re_multi_newline.sub('\n\n', text)

   # Убираем пробелы в начале и конце строк
   text = '\n'.join(line.strip() for line in text.split('\n'))

   if group_sentences:
    # Разбиваем на предложения
    sentences = self._re_sentence.findall(text)
    if len(sentences) > 1:
     # Группируем по 3 предложения в абзац для лучшей читаемости
     paragraphs = []
     for i in range(0, len(sentences), 3):
      paragraph = ' '.join(sentences[i:i + 3]).strip()
      if paragraph:
       paragraphs.append(paragraph)
     text = '\n\n'.join(paragraphs)

   # Финальная очистка
   text = text.strip()
   while "  " in text:
    text = text.replace("  ", " ")
   return text

  def get_video_title(self) -> str:  # Возвращает очищенный заголовок видео
    try:
      title = self.driver.title.replace(" - YouTube", "").strip()
      return title or f"video_{int(time.time())}"
    except Exception:
      return f"video_{int(time.time())}"

  def process_channel_from_clipboard(self) -> None:  # Основной метод: берёт ссылку из буфера, находит видео и сохраняет субтитры в файл
    try:
      channel_url = pyperclip.paste().strip()
    except Exception as e:
      logger.error(f"Не удалось прочитать буфер обмена: {e}")
      return
    if not channel_url or "youtube.com" not in channel_url:
      logger.error(f"В буфере обмена не обнаружена корректная ссылка на YouTube. Найдено: {channel_url}")
      return
    logger.info(f"Ссылка получена из буфера обмена: {channel_url}")
    try:
      video_url = self.get_latest_video_url(channel_url)
      if not video_url:
        logger.error("Не удалось получить URL видео.")
        return
      self.prepare_video_page(video_url)
      self.wait_for_extension_shadow_root()
      self.click_get_subtitles()
      raw_text = self.wait_for_subtitles_smart()
      clean_text = self.clean_transcript(raw_text, group_sentences=True)
      title = self.get_video_title()
      full_text = f"\n{clean_text}"
      save_path = Path(self.save_dir)
      save_path.mkdir(parents=True, exist_ok=True)
      safe_title = self._re_unsafe_chars.sub("", title.strip()) if title else f"video_{int(time.time())}"
      safe_title = safe_title.strip().rstrip('.') or f"video_{int(time.time())}"
      filepath = save_path / f"{safe_title}.md"
      filepath.write_text(full_text, encoding="utf-8")
      logger.info(f"Текст сохранён в файл: {filepath}")
    except TimeoutException as e:
      logger.error(f"Превышено время ожидания: {e}")
    except WebDriverException as e:
      logger.error(f"Ошибка драйвера браузера: {e}")
    except OSError as e:
      logger.error(f"Ошибка файловой системы: {e}")
    except Exception as e:
      logger.error(f"Ошибка в процессе выполнения: {e}", exc_info=True)
    finally:
      if self.driver:
        try:
          self.driver.quit()
        except Exception:
          pass
        logger.info("Браузер закрыт.")

if __name__ == "__main__":
  extractor = YouTubeSubtitleExtractor()
  extractor.process_channel_from_clipboard()
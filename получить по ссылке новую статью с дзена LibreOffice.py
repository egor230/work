# Получение статьи с Дзена и сохранение в LibreOffice (.odt)
# Копия скрипта "получить по ссылке новую статью с дзена.py",
# переписанная под LibreOffice вместо Microsoft Word (через Wine).
#
# Основная логика сохранена: берём ссылку (из буфера обмена или переменной),
# открываем страницу, вытаскиваем заголовок и текст статьи, вставляем в документ.
# Главное отличие и улучшение: вместо хрупкой автоматизации Word (xdotool/xte/copyq)
# мы формируем чистый HTML, скачиваем и встраиваем картинки локально,
# а затем конвертируем в .odt через libreoffice --headless. Это намного стабильнее.

# --- Стандартная библиотека ---
import os          # пути, имена файлов, создание папок
import sys         # аргументы командной строки
import time        # паузы ожидания загрузки
import shutil      # перемещение/удаление файлов и временных папок
import tempfile    # временные рабочие каталоги
import subprocess  # запуск libreoffice в фоне
import traceback   # печать ошибок без аварийного завершения
import base64      # упаковка картинок в data: URI
import io          # буфер для сжатия картинок в памяти

# --- Сторонние библиотеки (обязательные) ---
import requests             # скачивание картинок и страниц
from bs4 import BeautifulSoup  # парсинг HTML статьи
from selenium import webdriver  # управление браузером (рендер Дзена)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager  # авто-драйвер Chrome

# --- Опциональные библиотеки (при отсутствии скрипт не падает) ---
try:
    import pyperclip        # буфер обмена (если ссылка берётся из него)
except Exception:
    pyperclip = None        # при ошибке просто не используем буфер

try:
    from PIL import Image   # уменьшение слишком больших картинок
except Exception:
    Image = None            # без неё картинки вставляем как есть

# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLDER = os.path.join(BASE_DIR, "статьи для книги")
OUTPUT_FORMAT = "doc"          # Формат итогового документа: "doc" (Word) или "odt" (LibreOffice)
LIBREOFFICE_BIN = "libreoffice"
BASE_URL = "https://dzen.ru"

# Ссылка для теста. Чтобы взять ссылку из буфера обмена — закомментируйте эту
# строку и раскомментируйте следующую (как было в оригинале).
#URL = "https://dzen.ru/a/aQraudPcH22iXHT7"
URL = str(pyperclip.paste()).strip() if pyperclip else ""

# Текст благодарности/рекламы, который Дзен вставляет в конце — вырезаем.
DONATION_TEXT = (
    "Те, кто мне благодарен за мою помощь при работе с их руками, могут по своему "
    "желанию перевести мне денежную благодарность на карту с пометкой \"В дар\". "
    "Счёт карты 2202 2063 9554 7743 Сбербанк MИР."
)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")


# ---------------------------------------------------------------------------
# Параметры запуска Chrome (скопировано из libs_voice.get_option)
# ---------------------------------------------------------------------------
def get_option():
    prefs = {
        'safebrowsing.enabled': True,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    option = Options()
    option.add_experimental_option("prefs", prefs)
    option.add_experimental_option("excludeSwitches", ['enable-automation'])
    option.add_argument("user-agent=" + UA)
    option.add_argument("--disable-popup-blocking")
    option.add_argument("--disable-blink-features=AutomationControlled")
    option.add_argument("--disable-gpu")
    option.add_argument('--disable-infobars')
    option.add_argument("--disk-cache-size=0")
    option.add_argument("--media-cache-size=0")
    option.add_argument("--disable-extensions")
    option.add_argument("--disable-autofill")
    option.add_argument("--disable-background-timer-throttling")
    option.add_argument("--disable-background-networking")
    option.add_argument(
        "--user-data-dir="
        "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/google-chrome"
    )
    option.add_experimental_option("useAutomationExtension", False)
    return option


# ---------------------------------------------------------------------------
# Извлечение заголовка и тела статьи из HTML
# ---------------------------------------------------------------------------
def extract_title(soup):
    title_text = "Заголовок не найден"

    title_element = soup.find('h1', {'data-testid': 'article-title'})
    if not title_element:
        title_element = soup.find('h1', {'itemprop': 'headline'})
    if not title_element:
        title_element = soup.find(
            'h1',
            class_=lambda x: x and any(
                w in x.lower() for w in ['title', 'header', 'heading']
            ) if x else False)
    if not title_element:
        title_element = soup.find('h1')
    if not title_element:
        meta = (soup.find('meta', {'property': 'og:title'}) or
                soup.find('meta', {'property': 'twitter:title'}) or
                soup.find('meta', {'name': 'title'}))
        if meta and meta.get('content'):
            title_text = meta.get('content', '').strip()
            return title_text
    if not title_element:
        t = soup.find('title')
        if t:
            return t.get_text(strip=True)

    if title_element and title_element.name != 'title':
        title_text = title_element.get_text(strip=True)
        title_text = ' '.join(title_text.split())
    return title_text


def extract_body(soup, cookies=None):
    """Возвращает (html_тела, было_ли_найдено_тело)."""
    article_body = soup.find('div', {'data-testid': 'article-body'})
    if not article_body:
        # Запасные варианты контейнера статьи
        article_body = (
            soup.find('div', {'itemprop': 'articleBody'}) or
            soup.find('article') or
            soup.find('div', class_=lambda x: x and 'article' in x.lower() if x else False)
        )
    if not article_body:
        return "<div>Текст статьи не найден</div>", False

    body_copy = BeautifulSoup(str(article_body), 'html.parser').div
    if not body_copy:
        return "<div>Ошибка обработки текста статьи</div>", False

    for tag in body_copy(['script', 'style']):
        tag.decompose()

    # Убираем рекламные/служебные блоки
    for bad in body_copy.find_all(
            class_=lambda x: x and any(
                w in x.lower() for w in
                ['adv', 'banner', 'reklama', 'widget', 'subscribe', 'share']
            ) if x else False):
        bad.decompose()

    # Вырезаем блок благодарности/реквизитов. Дзен вставляет в него лишние
    # пробелы между символами ("Счёт  карты"), поэтому сжимаем пробелы перед
    # проверкой и удаляем весь абзац/блок целиком.
    for block in body_copy.find_all(['p', 'div', 'section']):
        norm = ' '.join(block.get_text(" ", strip=True).split())
        if "Счёт карты" in norm or ("в дар" in norm.lower() and "благодарность" in norm.lower()):
            block.decompose()

    # Скачиваем картинки и встраиваем прямо в HTML как data: URI
    # (LibreOffice при конвертации не подхватывает внешние файлы,
    #  а data: URI встраивает корректно).
    for img in body_copy.find_all('img'):
        src = (img.get('src') or img.get('data-src') or '').strip()
        if not src:
            img.decompose()
            continue
        if not src.startswith(('http://', 'https://')):
            src = f"{BASE_URL}{src}" if src.startswith('/') else f"{BASE_URL}/{src}"
        data_uri = download_image(src, cookies)
        if data_uri:
            img['src'] = data_uri
            img.attrs = {k: v for k, v in img.attrs.items()
                         if k in ('src', 'alt')}
        else:
            # Если скачать не удалось — оставляем ссылку как есть
            img['src'] = src
            img.attrs = {k: v for k, v in img.attrs.items()
                         if k in ('src', 'alt')}

    for a_tag in body_copy.find_all('a'):
        a_tag.unwrap()

    body_copy.attrs = {}
    for tag in body_copy.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items()
                     if k in ['src', 'href', 'alt']}

    return str(body_copy), True


def download_image(url, cookies=None):
    """Скачивает картинку и возвращает data: URI (или None при ошибке)."""
    try:
        headers = {"User-Agent": UA, "Referer": BASE_URL + "/"}
        r = requests.get(url, headers=headers, cookies=cookies or {}, timeout=20)
        if r.status_code != 200 or not r.content:
            return None
        ctype = r.headers.get("content-type", "").lower()
        if "png" in ctype:
            ext = "png"
        elif "gif" in ctype:
            ext = "gif"
        elif "webp" in ctype:
            ext = "webp"
        else:
            ext = "jpeg"
        data = r.content
        # Уменьшаем слишком большие картинки, чтобы документ не раздувался
        if Image is not None and ext in ("jpeg", "png"):
            try:
                im = Image.open(io.BytesIO(data))
                im = im.convert("RGB") if im.mode in ("RGBA", "P", "LA") else im
                if im.width > 720:
                    h = int(im.height * 720 / im.width)
                    im = im.resize((720, h))
                    buf = io.BytesIO()
                    im.save(buf, "JPEG")
                    data = buf.getvalue()
                    ext = "jpeg"
            except Exception:
                pass
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/{ext};base64,{b64}"
    except Exception as e:
        print(f"  Не удалось скачать картинку {url}: {e}")
        return None


def sanitize_filename(name):
    invalid = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '!']
    s = name
    for c in invalid:
        s = s.replace(c, '')
    s = s.strip().rstrip('.')
    return (s[:120] or "статья")


# ---------------------------------------------------------------------------
# Вставка статьи в шаблон через LibreOffice (UNO, headless — без GUI-автоматики)
# ---------------------------------------------------------------------------
# Шаблон-основа: копируем его и вставляем внутрь текст статьи (как в оригинале,
# только вместо Word под Wine — LibreOffice).
TEMPLATE_PATH = "/home/egor/Шаблоны/doc.doc"

# Код, выполняемый в Python с модулем uno (обычно системный python3, т.к. uno
# недоступен из venv). Открывает копию шаблона и вставляет HTML статьи в конец.
UNO_INSERT_HELPER = r'''
import uno, subprocess, time, os, sys
from com.sun.star.beans import PropertyValue

def main():
    target = sys.argv[1]      # путь к копии шаблона (куда вставляем)
    html_path = sys.argv[2]   # путь к HTML статьи
    port = int(sys.argv[3])
    prof = sys.argv[4]
    p = subprocess.Popen(
        ["libreoffice", "--headless",
         "-env:UserInstallation=file://" + prof,
         "--accept=socket,host=localhost,port=%d;urp;" % port],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ctx = None
    try:
        for _ in range(40):
            try:
                local = uno.getComponentContext()
                resolver = local.ServiceManager.createInstanceWithContext(
                    "com.sun.star.bridge.UnoUrlResolver", local)
                ctx = resolver.resolve(
                    "uno:socket,host=localhost,port=%d;urp;StarOffice.ComponentContext" % port)
                break
            except Exception:
                time.sleep(0.5)
        if ctx is None:
            raise RuntimeError("Не удалось подключиться к LibreOffice")
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL("file://" + os.path.abspath(target), "_default", 0, ())
        controller = doc.getCurrentController()
        vc = controller.getViewCursor()
        vc.gotoEnd(False)  # вставляем в конец шаблона
        dispatch = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
        props = (PropertyValue(Name="Name", Value="file://" + os.path.abspath(html_path)),
                 PropertyValue(Name="FilterName", Value="HTML (StarWriter)"))
        dispatch.executeDispatch(controller.getFrame(), ".uno:InsertDoc", "", 0, props)
        doc.store()
        doc.close(True)
        print("OK: статья вставлена в шаблон")
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()

main()
'''


def find_uno_python():
    # Ищем интерпретатор, в котором доступен модуль uno (нужен для UNO-моста).
    candidates = [sys.executable, "/usr/bin/python3", "python3"]
    seen = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        try:
            r = subprocess.run([c, "-c", "import uno"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if r.returncode == 0:
                return c
        except Exception:
            pass
    return None


def insert_article_into_doc(template_path, target_path, html_path):
    # 1. Копируем шаблон под именем будущей статьи
    shutil.copy2(template_path, target_path)
    # 2. Вставляем статью (HTML) внутрь копии через LibreOffice UNO
    uno_py = find_uno_python()
    if not uno_py:
        raise RuntimeError(
            "Не найден Python с модулем uno. Установите: sudo apt install python3-uno")
    helper = tempfile.NamedTemporaryFile(
        'w', suffix='.py', delete=False, dir=os.path.dirname(html_path))
    helper.write(UNO_INSERT_HELPER)
    helper.close()
    last_err = None
    for attempt in range(2):  # повтор при случайном конфликте LibreOffice/порта
        port = 2050 + (os.getpid() % 1000) + attempt
        prof = tempfile.mkdtemp(prefix="lo_uno_")
        try:
            r = subprocess.run(
                [uno_py, helper.name, target_path, html_path, str(port), prof],
                capture_output=True, text=True, timeout=180)
            if r.returncode == 0:
                os.unlink(helper.name)
                shutil.rmtree(prof, ignore_errors=True)
                return
            last_err = (r.stderr or r.stdout or "")[:1500]
        finally:
            shutil.rmtree(prof, ignore_errors=True)
    os.unlink(helper.name)
    if last_err:
        print("  Вывод LibreOffice (UNO):", last_err)
    raise RuntimeError("Не удалось вставить статью в шаблон через LibreOffice")


# Запасной вариант: если UNO недоступен — конвертируем HTML напрямую.
EXPORT_FILTERS = {
    "doc": "doc:MS Word 97",
    "odt": "odt",
    "docx": "docx:Office Open XML Text",
}


def convert_with_libreoffice(html_path, out_dir, fmt):
    profile = tempfile.mkdtemp(prefix="lo_profile_")
    target = EXPORT_FILTERS.get(fmt, fmt)
    try:
        cmd = [
            LIBREOFFICE_BIN,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--nofirststartwizard",
            "--convert-to", target,
            "--outdir", out_dir,
            html_path,
        ]
        subprocess.run(cmd, timeout=180, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    stem = os.path.splitext(os.path.basename(html_path))[0]
    produced = os.path.join(out_dir, f"{stem}.{fmt}")
    return produced if os.path.exists(produced) else None


# ---------------------------------------------------------------------------
# Основной процесс
# ---------------------------------------------------------------------------
def process_article(url):
    url = url.strip()
    if not url:
        print("Ссылка пуста — нечего обрабатывать.")
        return

    print(f"Открываю: {url}")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=get_option())
    work_dir = tempfile.mkdtemp(prefix="dzen_article_")

    try:
        driver.get(url)
        # Ждём появления тела статьи (вместо слепого sleep)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='article-body']")))
        except Exception:
            print("  Контейнер article-body не появился за 20с, продолжаем с тем, что есть.")
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        title_text = extract_title(soup)
        print(f"Заголовок: {title_text}")

        # Берём куки сессии браузера — они нужны, чтобы скачать картинки
        # с CDN Дзена (без них отдаётся 404).
        session_cookies = {c['name']: c['value'] for c in driver.get_cookies()}

        body_html, found = extract_body(soup, session_cookies)
        if not found:
            print("  ВНИМАНИЕ: тело статьи не найдено, документ может быть пустым.")

        # Убираем текст благодарности
        clean_body = body_html.replace(DONATION_TEXT, "")

        html_doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Liberation Serif, DejaVu Serif, serif; }}
  h1 {{ font-size: 22pt; }}
  img {{ max-width: 720px; height: auto; }}
</style>
</head>
<body>
<h1>{title_text}</h1>
<br><br>
{clean_body}
</body>
</html>"""

        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        safe_title = sanitize_filename(title_text)
        html_path = os.path.join(work_dir, f"{safe_title}.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_doc)

        target_path = os.path.join(OUTPUT_FOLDER, f"{safe_title}.{OUTPUT_FORMAT}")
        print("Копирую шаблон и вставляю статью через LibreOffice...")
        try:
            insert_article_into_doc(TEMPLATE_PATH, target_path, html_path)
            print(f"Готово: {target_path} ({os.path.getsize(target_path)} байт)")
        except Exception as e:
            print(f"  Ошибка вставки через LibreOffice: {e}")
            print("  Запасной вариант — конвертация HTML без шаблона...")
            produced = convert_with_libreoffice(html_path, OUTPUT_FOLDER, OUTPUT_FORMAT)
            if produced:
                if os.path.abspath(produced) != os.path.abspath(target_path):
                    shutil.move(produced, target_path)
                print(f"Готово (без шаблона): {target_path}")
            else:
                fallback = os.path.join(OUTPUT_FOLDER, f"{safe_title}.html")
                shutil.copy2(html_path, fallback)
                print(f"Сохранён HTML: {fallback}")

    finally:
        driver.quit()
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            URL = sys.argv[1]
        process_article(URL)
    except Exception:
        traceback.print_exc()

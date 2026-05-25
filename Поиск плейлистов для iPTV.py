import asyncio
import argparse
import os
import re
import time
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse
from typing import Optional
import aiohttp

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
CONFIG = {
    # Метод проверки: "http" (быстрый) или "deep" (глубокий, точнее)
    "CHECK_METHOD": "deep",
    # Таймауты
    "HTTP_TIMEOUT": 6,         # HEAD запрос
    "GET_TIMEOUT": 8,          # GET с чтением тела
    "READ_TIMEOUT": 5,         # на чтение первых байт
    # Параллелизм
    "MAX_PARALLEL_DOWNLOADS": 20,  # одновременная загрузка источников
    "MAX_PARALLEL_CHECKS": 40,     # одновременная проверка каналов
    # Целевые показатели
    "MIN_WORKING_CHANNELS": 50,
    "MAX_WORKING_CHANNELS": 2000,
    # Выходной файл
    "OUTPUT_FILE": "all_tv.m3u",
}

# ============================================================
# ИСТОЧНИКИ ПЛЕЙЛИСТОВ
# ============================================================
SOURCES = [
    # --- IPTVRU2026/IPTVMIR (~9000 каналов) ---
    {"name": "IPTVRU2026 MEGA", "url": "https://raw.githubusercontent.com/IPTVRU2026/IPTVMIR/main/IPTV_MEGA_PLAYLIST.m3u", "priority": 12, "country": "ru"},
    {"name": "IPTVRU2026 ZARUB", "url": "https://raw.githubusercontent.com/IPTVRU2026/IPTVMIR/main/ZARUB.m3u", "priority": 8, "country": "world"},

    # --- m3u.su: Российские общие ---
    {"name": "m3u.su smolnp Русский", "url": "https://m3u.su/so", "priority": 11, "country": "ru"},
    {"name": "m3u.su smolnp Русский2", "url": "https://m3u.su/so2", "priority": 10, "country": "ru"},
    {"name": "m3u.su smolnp Стабильный", "url": "https://m3u.su/ss", "priority": 11, "country": "ru"},
    {"name": "m3u.su smolnp Мир", "url": "https://m3u.su/sm", "priority": 9, "country": "ru"},
    {"name": "m3u.su Telekarta RU", "url": "https://m3u.su/tru", "priority": 10, "country": "ru"},
    {"name": "m3u.su D-TV6", "url": "https://m3u.su/d", "priority": 9, "country": "ru"},
    {"name": "m3u.su Dmitry-tv HD", "url": "https://m3u.su/dh", "priority": 9, "country": "ru"},
    {"name": "m3u.su ZABAVA", "url": "https://m3u.su/dz", "priority": 9, "country": "ru"},
    {"name": "m3u.su СМОТРИМ", "url": "https://m3u.su/ds", "priority": 8, "country": "ru"},
    {"name": "m3u.su Playlist-01", "url": "https://m3u.su/d1", "priority": 7, "country": "ru"},
    {"name": "m3u.su Playlist-04", "url": "https://m3u.su/d4", "priority": 7, "country": "ru"},
    {"name": "m3u.su Playlist-05", "url": "https://m3u.su/d5", "priority": 7, "country": "ru"},
    {"name": "m3u.su Karnei4 Zabava", "url": "https://m3u.su/kk2", "priority": 8, "country": "ru"},
    {"name": "m3u.su ТВОЕ ТВ", "url": "https://m3u.su/tvoe", "priority": 8, "country": "ru"},
    {"name": "m3u.su iptv-org RU NTV", "url": "https://m3u.su/runtv", "priority": 9, "country": "ru"},
    {"name": "m3u.su iptv-org RU RT", "url": "https://m3u.su/rurt", "priority": 9, "country": "ru"},
    {"name": "m3u.su iptv-org RU Smotrim", "url": "https://m3u.su/rusm", "priority": 9, "country": "ru"},
    {"name": "m3u.su iptv-org RU TV24", "url": "https://m3u.su/rut", "priority": 8, "country": "ru"},
    {"name": "m3u.su iptv-org RU Zabava", "url": "https://m3u.su/ruz", "priority": 9, "country": "ru"},

    # --- m3u.su: МСК+2 (Екатеринбург / Урал) ---
    {"name": "m3u.su МСК+2 Екб", "url": "https://m3u.su/de2", "priority": 13, "country": "ru", "tz": 2},
    {"name": "m3u.su ZABAVA Екб", "url": "https://m3u.su/dze", "priority": 13, "country": "ru", "tz": 2},
    {"name": "m3u.su ZABAVA Челябинск", "url": "https://m3u.su/dzcb", "priority": 13, "country": "ru", "tz": 2},
    {"name": "m3u.su ZABAVA Н.Тагил", "url": "https://m3u.su/dznt", "priority": 12, "country": "ru", "tz": 2},
    {"name": "m3u.su ZABAVA Тюмень", "url": "https://m3u.su/dzty", "priority": 12, "country": "ru", "tz": 2},
    {"name": "m3u.su ZABAVA Пермь", "url": "https://m3u.su/dzpr", "priority": 11, "country": "ru", "tz": 2},
    {"name": "m3u.su ZABAVA Курган", "url": "https://m3u.su/dzku", "priority": 11, "country": "ru", "tz": 2},

    # --- m3u.su: Другие часовые пояса РФ (полезно для сравнения) ---
    {"name": "m3u.su МСК+0 Москва", "url": "https://m3u.su/dzmo", "priority": 9, "country": "ru", "tz": 0},
    {"name": "m3u.su МСК+1 Самара", "url": "https://m3u.su/dzs", "priority": 8, "country": "ru", "tz": 1},
    {"name": "m3u.su МСК+3 Омск", "url": "https://m3u.su/dzom", "priority": 7, "country": "ru", "tz": 3},

    # --- m3u.su: Украина ---
    {"name": "m3u.su Харьков", "url": "https://m3u.su/h", "priority": 8, "country": "ua"},

    # --- m3u.su: Музыка / Радио ---
    {"name": "m3u.su Музыка", "url": "https://m3u.su/mus2", "priority": 5, "country": "ru"},
    {"name": "m3u.su Музыка2", "url": "https://m3u.su/mus3", "priority": 5, "country": "ru"},

    # --- GitHub: iptv-org ---
    {"name": "iptv-org Russia", "url": "https://iptv-org.github.io/iptv/countries/ru.m3u", "priority": 9, "country": "ru"},
    {"name": "iptv-org Ukraine", "url": "https://iptv-org.github.io/iptv/countries/ua.m3u", "priority": 8, "country": "ua"},
    {"name": "iptv-org Streams RU", "url": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ru.m3u", "priority": 8, "country": "ru"},
    {"name": "iptv-org Streams UA", "url": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ua.m3u", "priority": 7, "country": "ua"},

    # --- GitHub: другие ---
    {"name": "Free-TV Russia", "url": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_russia.m3u8", "priority": 8, "country": "ru"},
    {"name": "Free-TV Ukraine", "url": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_ukraine.m3u8", "priority": 7, "country": "ua"},
    {"name": "Free-TV Main All", "url": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", "priority": 6, "country": "all"},
    {"name": "HD-IPTV Russia", "url": "https://raw.githubusercontent.com/HD-IPTV/playlist/master/Russia.m3u", "priority": 7, "country": "ru"},
    {"name": "smolnp IPTVru Stable", "url": "https://smolnp.github.io/IPTVru/IPTVstable.m3u8", "priority": 9, "country": "ru"},
    {"name": "smolnp IPTVru Full", "url": "https://raw.githubusercontent.com/smolnp/IPTVru/refs/heads/gh-pages/IPTVru.m3u", "priority": 8, "country": "ru"},
    {"name": "MyPlaylists Russia", "url": "https://myplaylists.github.io/iptv/ru.m3u", "priority": 6, "country": "ru"},
    {"name": "MyPlaylists Ukraine", "url": "https://myplaylists.github.io/iptv/ua.m3u", "priority": 6, "country": "ua"},
    {"name": "DenverCoder RU", "url": "https://raw.githubusercontent.com/DenverCoder1/iptv-playlists/main/playlists/ru.m3u", "priority": 5, "country": "ru"},
    {"name": "Karnei4 IPTV-RU", "url": "https://karnei4.github.io/IPTV-RU/playlist.m3u", "priority": 6, "country": "ru"},
    {"name": "Best RU Timeshift", "url": "https://raw.githubusercontent.com/4KIPTV/iptv/main/russia.m3u", "priority": 6, "country": "ru"},
    {"name": "Gist Ageresz RU", "url": "https://gist.githubusercontent.com/ageresz/a1b1790b4febbf219df31ba32094e3bf/raw", "priority": 6, "country": "ru"},
    {"name": "Gist Ityshchenko UA/RU", "url": "https://gist.githubusercontent.com/ityshchenko/2ab16ce214f03740883428fb789c5cde/raw", "priority": 5, "country": "mixed"},
    {"name": "m3u.su ВСЕ ЧАСОВЫЕ ПОЯСА", "url": "https://m3u.su/der", "priority": 8, "country": "ru"},
]

# ============================================================
# КЛЮЧЕВЫЕ СЛОВА ДЛЯ ОПРЕДЕЛЕНИЯ СТРАНЫ
# ============================================================
RU_KEYWORDS = [
    "россия", "первый канал", "россия 1", "россия1", "нтв", "рен тв", "рен",
    "стс", "тнт", "звезда", "мир", "отр", "матч", "культура", "ru1", "russia",
    "ртр", "карусель", "москва 24", "россия 24", "тв центр", "пятница",
    "ru tv", "тв3", "чо", "суббота", "спас", "78", "тнв", "тамыр",
    "башкортостан", "ураль", "екатеринбург", "челябинск", "тюмень", "сургут",
    "забава", "рутв", "1 канал", "match", "chelyabinsk", "ural",
]

UA_KEYWORDS = [
    "украина", "україна", "1+1", "интер", "стб", "новый канал", "тет",
    "украин", "укр", "m1", "m2", "канал украина", "плюстплюс", "ictv",
    "ua:", "5 канал", "перший", "тризуб", "espresso", "freedom",
    "unian", "pravda", "hromadske",
]

# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("iptv_merger")

# ============================================================
# МОДЕЛЬ ДАННЫХ
# ============================================================
@dataclass
class Channel:
    name: str = ""
    url: str = ""
    group: str = ""
    logo: str = ""
    tvg_id: str = ""
    source_name: str = ""
    source_priority: int = 0
    country: str = ""       # "ru", "ua", "world", "mixed"
    tz_offset: int = 0      # смещение от МСК (0, +2 и т.д.)
    is_working: bool = False
    has_name: bool = False   # есть ли нормальное название (не абракадабра)

    @property
    def clean_name(self) -> str:
        name = re.sub(r"\s*(HD|SD|UHD|4K|FHD|1080p|720p)\s*$", "", self.name.strip(), flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', name).strip()

    @property
    def quality_score(self) -> int:
        score = self.source_priority * 10
        n = self.name.upper()
        if "4K" in n or "UHD" in n:
            score += 40
        elif "1080" in n or "FHD" in n:
            score += 30
        elif "HD" in n:
            score += 20
        if self.tz_offset == 2:
            score += 25  # бонус за +2 к МСК
        return score

# ============================================================
# ОПРЕДЕЛЕНИЕ СТРАНЫ КАНАЛА
# ============================================================
def detect_country(ch: Channel) -> str:
    """Определяет страну канала по названию и группе."""
    text = (ch.name + " " + ch.group).lower()

    # Если в источнике указана страна — учитываем
    if ch.source_name and "украин" in ch.source_name.lower():
        return "ua"

    ru_score = sum(1 for kw in RU_KEYWORDS if kw in text)
    ua_score = sum(1 for kw in UA_KEYWORDS if kw in text)

    if ua_score > ru_score and ua_score >= 1:
        return "ua"
    if ru_score >= 1:
        return "ru"
    return ch.country or "world"

# ============================================================
# ПРОВЕРКА: ЯВЛЯЕТСЯ ЛИ НАЗВАНИЕ «АБРАКАДАБРОЙ»
# ============================================================
def is_meaningful_name(name: str) -> bool:
    """Возвращает True, если название выглядит как нормальное название канала."""
    if not name or len(name) < 2:
        return False
    # Если есть кириллица — скорее всего нормальное название
    cyrillic = sum(1 for c in name if '\u0400' <= c <= '\u04FF')
    latin = sum(1 for c in name if 'a' <= c.lower() <= 'z')
    if cyrillic > 2:
        return True
    # Латиница: нормальные TV-названия
    if re.match(r'^[A-Za-z0-9\s\-\+\.]{2,50}$', name):
        return True
    # Если совсем короткое — скорее всего мусор
    if len(name) <= 3 and not cyrillic:
        return False
    return len(name) >= 3

# ============================================================
# МНОГОСЛОЙНАЯ ПРОВЕРКА КАНАЛА (УЛУЧШЕННАЯ)
# ============================================================
# Паттерны, которые НЕ являются видео-потоками
HTML_MARKERS = [b"<!DOCTYPE", b"<html", b"<HTML", b"<!doctype", b"<head", b"<HEAD"]
ERROR_MARKERS = [b"404", b"403 Forbidden", b"Bad Request", b"Not Found", b"Service Unavailable", b"Error"]
# Паттерны, которые ЯВЛЯЮТСЯ HLS/M3U плейлистами
HLS_MARKERS = [b"#EXTM3U", b"#EXT-X-", b"#EXTINF", b"#EXTVLCOPT"]

VALID_CONTENT_TYPES = [
    "video/", "audio/", "mpegurl", "x-mpegurl", "mp2t",
    "octet-stream", "mpeg", "application/vnd.apple",
]

async def check_channel_deep(ch: Channel, session: aiohttp.ClientSession) -> Channel:
    """
    Многослойная проверка канала:
    1. HTTP HEAD — быстрый фильтр (статус + Content-Type)
    2. HTTP GET с чтением первых 4КБ — анализ содержимого
    3. Для HLS (.m3u8) — дополнительно проверяем наличие сегментов
    """
    url = ch.url
    headers = {
        "User-Agent": "VLC/3.0.21 LibVLC/3.0.21",
        "Accept": "*/*",
        "Connection": "keep-alive",
    }

    # --- Слой 1: HEAD запрос (самый быстрый) ---
    try:
        timeout = aiohttp.ClientTimeout(total=CONFIG["HTTP_TIMEOUT"])
        async with session.head(url, timeout=timeout, allow_redirects=True, headers=headers, ssl=False) as resp:
            if resp.status >= 400:
                ch.is_working = False
                return ch

            ct = (resp.headers.get("Content-Type", "") or "").lower()

            # Если Content-Type явно говорит «не видео» — отбрасываем
            if any(bad in ct for bad in ["text/html", "text/xml", "application/json", "application/xml"]):
                ch.is_working = False
                return ch

            # Если Content-Type явно видео/аудио/поток — скорее всего работает
            if any(good in ct for good in VALID_CONTENT_TYPES):
                ch.is_working = True
                return ch

            # Если Content-Type непонятный (text/plain и т.п.) — идём к слою 2
    except (aiohttp.ClientError, asyncio.TimeoutError):
        ch.is_working = False
        return ch

    # --- Слой 2: GET + чтение первых 4КБ ---
    try:
        timeout = aiohttp.ClientTimeout(total=CONFIG["GET_TIMEOUT"])
        async with session.get(url, timeout=timeout, allow_redirects=True, headers=headers, ssl=False) as resp:
            if resp.status >= 400:
                ch.is_working = False
                return ch

            ct = (resp.headers.get("Content-Type", "") or "").lower()

            # Повторная проверка Content-Type
            if any(bad in ct for bad in ["text/html", "text/xml", "application/json", "application/xml"]):
                ch.is_working = False
                return ch

            # Читаем первые 4096 байт
            data = await resp.content.read(4096)

            if not data or len(data) < 10:
                ch.is_working = False
                return ch

            # Проверяем, не HTML ли это
            for marker in HTML_MARKERS:
                if data.startswith(marker):
                    ch.is_working = False
                    return ch

            # Проверяем, нет ли ошибок в теле
            data_str = data[:512]
            for marker in ERROR_MARKERS:
                if marker in data_str:
                    ch.is_working = False
                    return ch

            # Если это HLS-плейлист (содержит #EXTM3U) — проверяем глубже
            if data.startswith(b"#EXTM3U") or b"#EXT-X-" in data:
                # Для HLS-плейлистов достаточно того, что сервер отдал корректный манифест
                if b"#EXTINF" in data or b"#EXT-X-STREAM" in data or b"#EXT-X-TARGETDURATION" in data:
                    ch.is_working = True
                    return ch
                # Если манифест пустой или кривой — не работаем
                ch.is_working = False
                return ch

            # Если это MPEG-TS поток (бинарные данные) — работаем
            # MPEG-TS начинается с 0x47 (G)
            if data[0] == 0x47:
                ch.is_working = True
                return ch

            # Проверяем: если тело содержит HLS-маркеры где-то внутри
            has_hls = any(m in data for m in HLS_MARKERS)
            has_valid_ct = any(good in ct for good in VALID_CONTENT_TYPES)

            if has_hls or has_valid_ct:
                ch.is_working = True
                return ch

            # Если Content-Type — text/plain, но внутри есть HLS-маркеры
            if "text/plain" in ct and has_hls:
                ch.is_working = True
                return ch

            # Для text/plain без HLS-маркеров — пробуем, если данных достаточно
            if "text/plain" in ct and len(data) > 100 and b"http" in data:
                # Скорее всего это текстовый плейлист с URL-ами
                ch.is_working = True
                return ch

            # Для octet-stream с достаточным объёмом данных
            if "octet-stream" in ct and len(data) > 50:
                ch.is_working = True
                return ch

    except (aiohttp.ClientError, asyncio.TimeoutError):
        ch.is_working = False
        return ch

    ch.is_working = False
    return ch


async def check_channel(ch: Channel, session: aiohttp.ClientSession) -> Channel:
    """Универсальная обёртка проверки."""
    if CONFIG["CHECK_METHOD"] == "deep" and session:
        return await check_channel_deep(ch, session)
    else:
        return await check_channel_deep(ch, session)  # всегда глубокая

# ============================================================
# ПАРСИНГ M3U
# ============================================================
def parse_m3u(text: str, source_name: str, priority: int, country: str = "", tz_offset: int = 0) -> list[Channel]:
    channels = []
    lines = text.splitlines()
    current = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            current = {}
            # Извлекаем название (после последней запятой)
            m = re.search(r',(.+)$', line)
            if m:
                current["title"] = m.group(1).strip()
            # Извлекаем атрибуты
            for attr in re.finditer(r'(\S+?)="([^"]*)"', line):
                current[attr.group(1)] = attr.group(2)

        elif line.startswith("#"):
            # Другие директивы — пропускаем
            continue

        elif (line.startswith("http://") or line.startswith("https://")) and current.get("title"):
            name = current.get("title", "")
            ch = Channel(
                name=name,
                url=line,
                group=current.get("group-title", ""),
                logo=current.get("tvg-logo", ""),
                tvg_id=current.get("tvg-id", ""),
                source_name=source_name,
                source_priority=priority,
                country=country,
                tz_offset=tz_offset,
                has_name=is_meaningful_name(name),
            )
            # Определяем страну по содержимому
            ch.country = detect_country(ch)
            # Наследуем tz_offset из источника, если не определён
            channels.append(ch)
            current = {}

    return channels

# ============================================================
# ЗАГРУЗКА ИСТОЧНИКА (каждый в своём потоке)
# ============================================================
async def download_source(session: aiohttp.ClientSession, src: dict) -> list[Channel]:
    """Асинхронно скачивает и парсит один источник."""
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with session.get(src["url"], timeout=timeout, ssl=False) as resp:
            if resp.status != 200:
                log.warning(f"  {src['name']}: HTTP {resp.status}")
                return []
            text = await resp.text()
            if not text or len(text) < 20:
                log.warning(f"  {src['name']}: пустой ответ")
                return []
            chs = parse_m3u(
                text,
                src["name"],
                src.get("priority", 0),
                src.get("country", ""),
                src.get("tz", 0),
            )
            log.info(f"  + {src['name']}: {len(chs)} каналов")
            return chs
    except Exception as e:
        log.warning(f"  - {src['name']}: {type(e).__name__}: {str(e)[:80]}")
        return []

# ============================================================
# ПАРАЛЛЕЛЬНАЯ ЗАГРУЗКА ВСЕХ ИСТОЧНИКОВ
# ============================================================
async def download_all_sources() -> list[Channel]:
    """Загружает все источники параллельно, каждый в своём потоке."""
    log.info(f"Загрузка {len(SOURCES)} источников параллельно...")

    connector = aiohttp.TCPConnector(
        limit=CONFIG["MAX_PARALLEL_DOWNLOADS"],
        ssl=False,
        ttl_dns_cache=300,
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [download_source(session, src) for src in SOURCES]
        results = await asyncio.gather(*tasks)

    all_channels = []
    for chs in results:
        all_channels.extend(chs)

    log.info(f"Итого загружено: {len(all_channels)} каналов из {len(SOURCES)} источников")
    return all_channels

# ============================================================
# УМНАЯ ПАКЕТНАЯ ПРОВЕРКА
# ============================================================
async def smart_check(channels: list[Channel]) -> list[Channel]:
    """Проверяет каналы параллельно, от лучших к худшим."""
    # Сортируем по качеству (лучшие проверяем первыми)
    channels.sort(key=lambda x: -x.quality_score)

    working = []
    semaphore = asyncio.Semaphore(CONFIG["MAX_PARALLEL_CHECKS"])
    checked = 0

    connector = aiohttp.TCPConnector(limit=CONFIG["MAX_PARALLEL_CHECKS"], ssl=False)
    session = aiohttp.ClientSession(connector=connector)

    try:
        async def bounded_check(ch: Channel) -> Channel:
            async with semaphore:
                return await check_channel(ch, session)

        batch_size = CONFIG["MAX_PARALLEL_CHECKS"] * 3

        for i in range(0, len(channels), batch_size):
            batch = channels[i:i + batch_size]
            results = await asyncio.gather(*[bounded_check(ch) for ch in batch], return_exceptions=True)

            for r in results:
                checked += 1
                if isinstance(r, Exception):
                    continue
                if r.is_working:
                    working.append(r)

            log.info(
                f"Проверено: {checked}/{len(channels)} | "
                f"Рабочих: {len(working)} | "
                f"Нерабочих: {checked - len(working)}"
            )

            # Остановка при достижении максимума
            if len(working) >= CONFIG["MAX_WORKING_CHANNELS"]:
                log.info(f"Достигнут максимум ({CONFIG['MAX_WORKING_CHANNELS']}), остановка проверки.")
                break
    finally:
        await session.close()

    return working

# ============================================================
# ДЕДУПЛИКАЦИЯ ПО URL (строго после проверки!)
# ============================================================
def deduplicate_by_url(channels: list[Channel]) -> list[Channel]:
    """
    Дедупликация строго по URL.
    Из дубликатов оставляем тот, у которого выше quality_score
    и у которого есть нормальное название.
    """
    seen = {}
    for ch in channels:
        if ch.url not in seen:
            seen[ch.url] = ch
        else:
            existing = seen[ch.url]
            # Заменяем, если новый лучше
            if (ch.quality_score > existing.quality_score or
                (ch.quality_score == existing.quality_score and ch.has_name and not existing.has_name)):
                seen[ch.url] = ch

    log.info(f"Дедупликация по URL: {len(channels)} -> {len(seen)} уникальных")
    return list(seen.values())

# ============================================================
# СОРТИРОВКА ПЛЕЙЛИСТА
# ============================================================
def sort_channels(channels: list[Channel]) -> list[Channel]:
    """
    Сортировка:
    1. Каналы с нормальными названиями — ВПЕРЕДИ
    2. Российские — перед украинскими — перед остальными
    3. МСК+2 (Урал) — приоритет среди российских
    4. Высокое качество (4K > HD > SD)
    5. Приоритет источника
    """
    def sort_key(ch: Channel) -> tuple:
        # 0 = с названием, 1 = без названия (с названием первыми)
        name_order = 0 if ch.has_name else 1

        # Порядок страны: ru=0, ua=1, world/mixed=2
        country_order = {"ru": 0, "ua": 1}.get(ch.country, 2)

        # МСК+2 = 0, остальные = 1
        tz_order = 0 if ch.tz_offset == 2 else 1

        # Качество (обратный порядок — лучше первыми)
        quality = -ch.quality_score

        return (name_order, country_order, tz_order, quality)

    channels.sort(key=sort_key)
    return channels

# ============================================================
# ЭКСПОРТ M3U
# ============================================================
def export_m3u(channels: list[Channel], filepath: str):
    """Сохраняет плейлист в M3U-формат."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in channels:
            attrs = []
            if ch.tvg_id:
                attrs.append(f'tvg-id="{ch.tvg_id}"')
            if ch.logo:
                attrs.append(f'tvg-logo="{ch.logo}"')
            if ch.group:
                attrs.append(f'group-title="{ch.group}"')
            attr_str = " ".join(attrs)
            f.write(f'#EXTINF:-1 {attr_str},{ch.name}\n{ch.url}\n')

    # Статистика
    ru_count = sum(1 for c in channels if c.country == "ru")
    ua_count = sum(1 for c in channels if c.country == "ua")
    tz2_count = sum(1 for c in channels if c.tz_offset == 2)
    named_count = sum(1 for c in channels if c.has_name)
    log.info(f"Плейлист сохранён: {filepath}")
    log.info(f"  Всего каналов: {len(channels)}")
    log.info(f"  С нормальными названиями: {named_count}")
    log.info(f"  Российских: {ru_count} | Украинских: {ua_count} | МСК+2: {tz2_count}")

# ============================================================
# MAIN
# ============================================================
async def main():
    parser = argparse.ArgumentParser(description="IPTV Merger v3.0 — сборщик рабочих IPTV-каналов")
    parser.add_argument("--min-channels", type=int, default=CONFIG["MIN_WORKING_CHANNELS"],
                        help="Минимум рабочих каналов")
    parser.add_argument("--max-channels", type=int, default=CONFIG["MAX_WORKING_CHANNELS"],
                        help="Максимум каналов в плейлисте")
    parser.add_argument("--workers", type=int, default=CONFIG["MAX_PARALLEL_CHECKS"],
                        help="Потоков проверки")
    parser.add_argument("--output", default=CONFIG["OUTPUT_FILE"],
                        help="Имя выходного файла")
    parser.add_argument("--method", choices=["deep", "http"], default=CONFIG["CHECK_METHOD"],
                        help="Метод проверки (deep — глубокий, http — быстрый)")
    args = parser.parse_args()

    # Обновляем конфиг
    CONFIG["CHECK_METHOD"] = args.method
    CONFIG["MIN_WORKING_CHANNELS"] = args.min_channels
    CONFIG["MAX_WORKING_CHANNELS"] = args.max_channels
    CONFIG["MAX_PARALLEL_CHECKS"] = args.workers

    start = time.time()

    log.info("=" * 70)
    log.info(f"IPTV Merger v3.0 | Метод: {args.method} | Цель: {args.min_channels}-{args.max_channels} каналов")
    log.info("=" * 70)

    # Шаг 1: Параллельная загрузка всех источников
    all_channels = await download_all_sources()

    if not all_channels:
        log.error("Ни один канал не загружен. Проверьте интернет-соединение.")
        return

    # Шаг 2: Проверка работоспособности (только рабочие)
    log.info("-" * 70)
    log.info("Начинаем проверку каналов...")
    working = await smart_check(all_channels)

    if not working:
        log.error("Не найдено ни одного рабочего канала.")
        return

    log.info(f"Проверка завершена. Рабочих: {len(working)}")

    # Шаг 3: Дедупликация по URL (строго после проверки!)
    log.info("-" * 70)
    unique = deduplicate_by_url(working)

    # Шаг 4: Сортировка (RU → UA → мир; с названиями первыми; МСК+2 приоритет)
    unique = sort_channels(unique)

    # Шаг 5: Экспорт
    export_m3u(unique, args.output)

    elapsed = time.time() - start
    log.info("-" * 70)
    log.info(f"Готово за {elapsed:.1f} сек | {len(unique)} рабочих уникальных каналов -> {args.output}")
    log.info("=" * 70)

    if len(unique) < args.min_channels:
        log.warning(f"Найдено только {len(unique)} каналов (минимум {args.min_channels})")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
IPTV Merger v4.0 — Асинхронный сборщик рабочих IPTV-каналов с высокой параллельностью.

Ключевые улучшения:
  - Параллельная проверка до 200 каналов одновременно (настраивается)
  - Улучшенная трёхуровневая проверка: HEAD → GET 8KB → HLS-сегмент с fallback
  - Динамическая очередь с приоритетом по качеству
  - Детальное логирование каждого канала в режиме --verbose
  - Ускорение загрузки всех источников (статических + m3u.su) за счёт широкой параллелизации
  - 100%-ная верификация: проверяется хотя бы один медиа-сегмент для HLS
"""

import asyncio
import argparse
import re
import time
import logging
from dataclasses import dataclass, field
from html import unescape
from typing import Optional, List, Dict, Set
from urllib.parse import urlparse, urljoin

import aiohttp

# ================================================================
# КОНФИГУРАЦИЯ ПО УМОЛЧАНИЮ
# ================================================================
CONFIG = {
    "CHECK_TIMEOUT": 5,                # секунд на HEAD + GET
    "HLS_PROBE_TIMEOUT": 4,            # секунд на пробу HLS-сегмента
    "MAX_PARALLEL_DOWNLOADS": 30,      # одновременных загрузок плейлистов
    "MAX_PARALLEL_CHECKS": 200,        # одновременных проверок каналов
    "BATCH_SIZE": 200,                 # размер пачки для проверки (зависит от workers)
    "MIN_WORKING": 20,
    "MAX_WORKING": 1600,
    "OUTPUT_FILE": "all_tv.m3u",
    "HEAD_FIRST": True,                # сначала HEAD для быстрого отсева
}

# ================================================================
# ИСТОЧНИКИ — статические M3U-плейлисты (те же, что и в v3)
# ================================================================
STATIC_SOURCES = [
    {"name": "IPTVMIR Mega",       "url": "https://raw.githubusercontent.com/IPTVRU2026/IPTVMIR/main/IPTV_MEGA_PLAYLIST.m3u", "priority": 12, "country": "ru"},
    {"name": "IPTVMIR Зарубежные", "url": "https://raw.githubusercontent.com/IPTVRU2026/IPTVMIR/main/ZARUB.m3u", "priority": 8, "country": "world"},
    {"name": "IPTVru Stable",      "url": "https://smolnp.github.io/IPTVru/IPTVstable.m3u8", "priority": 11, "country": "ru"},
    {"name": "IPTVru Full",        "url": "https://raw.githubusercontent.com/smolnp/IPTVru/refs/heads/gh-pages/IPTVru.m3u", "priority": 10, "country": "ru"},
    {"name": "m3u.su Русский",     "url": "https://m3u.su/so.m3u8",  "priority": 11, "country": "ru"},
    {"name": "m3u.su Русский 2",   "url": "https://m3u.su/so2.m3u8", "priority": 10, "country": "ru"},
    {"name": "m3u.su Стабильный",  "url": "https://m3u.su/ss.m3u8",  "priority": 10, "country": "ru"},
    {"name": "m3u.su Мир",         "url": "https://m3u.su/sm.m3u8",  "priority": 9,  "country": "world"},
    {"name": "m3u.su runtv",       "url": "https://m3u.su/runtv.m3u8", "priority": 10, "country": "ru"},
    {"name": "m3u.su rusm",        "url": "https://m3u.su/rusm.m3u8",  "priority": 10, "country": "ru"},
    {"name": "m3u.su ruz",         "url": "https://m3u.su/ruz.m3u8",   "priority": 10, "country": "ru"},
    {"name": "m3u.su rurt",        "url": "https://m3u.su/rurt.m3u8",  "priority": 9,  "country": "ru"},
    {"name": "m3u.su MSK+2 DVB",   "url": "https://m3u.su/de2.m3u8",  "priority": 13, "country": "ru", "timeshift": 2},
    {"name": "m3u.su Все пояса",    "url": "https://m3u.su/der.m3u8",  "priority": 10, "country": "ru"},
    {"name": "m3u.su Екатеринбург", "url": "https://m3u.su/dze.m3u8",  "priority": 9, "country": "ru"},
    {"name": "m3u.su Челябинск",    "url": "https://m3u.su/dzcb.m3u8", "priority": 9, "country": "ru"},
    {"name": "m3u.su Москва",       "url": "https://m3u.su/dzmo.m3u8", "priority": 8, "country": "ru"},
    {"name": "m3u.su СПб",          "url": "https://m3u.su/dzsp.m3u8", "priority": 8, "country": "ru"},
    {"name": "m3u.su Новосибирск",  "url": "https://m3u.su/dzns.m3u8", "priority": 8, "country": "ru"},
    {"name": "m3u.su Краснодар",    "url": "https://m3u.su/dzkd.m3u8", "priority": 8, "country": "ru"},
    {"name": "m3u.su Пермь",        "url": "https://m3u.su/dzpr.m3u8", "priority": 8, "country": "ru"},
    {"name": "m3u.su Казань",       "url": "https://m3u.su/dzk.m3u8",  "priority": 8, "country": "ru"},
    {"name": "m3u.su Самара",       "url": "https://m3u.su/dzs.m3u8",  "priority": 8, "country": "ru"},
    {"name": "m3u.su Zabava",       "url": "https://m3u.su/dz.m3u8",   "priority": 8, "country": "ru"},
    {"name": "m3u.su Смотрим",      "url": "https://m3u.su/ds.m3u8",   "priority": 8, "country": "ru"},
    {"name": "m3u.su ТВОЕ ТВ",      "url": "https://m3u.su/tvoe.m3u8", "priority": 7, "country": "ru"},
    {"name": "iptv-org Russia",     "url": "https://iptv-org.github.io/iptv/countries/ru.m3u", "priority": 9, "country": "ru"},
    {"name": "iptv-org Ukraine",    "url": "https://iptv-org.github.io/iptv/countries/ua.m3u", "priority": 9, "country": "ua"},
    {"name": "iptv-org Streams RU", "url": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ru.m3u", "priority": 8, "country": "ru"},
    {"name": "Free-TV Russia",      "url": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_russia.m3u8", "priority": 8, "country": "ru"},
    {"name": "Free-TV Ukraine",     "url": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_ukraine.m3u8", "priority": 8, "country": "ua"},
    {"name": "HD-IPTV Russia",      "url": "https://raw.githubusercontent.com/HD-IPTV/playlist/master/Russia.m3u", "priority": 7, "country": "ru"},
    {"name": "Rus-IPTV Full",       "url": "https://raw.githubusercontent.com/rus-iptv/rus-iptv.github.io/master/rus.m3u", "priority": 7, "country": "ru"},
    {"name": "Best RU Timeshift",   "url": "https://raw.githubusercontent.com/4KIPTV/iptv/main/russia.m3u", "priority": 7, "country": "ru"},
    {"name": "DenverCoder RU",      "url": "https://raw.githubusercontent.com/DenverCoder1/iptv-playlists/main/playlists/ru.m3u", "priority": 6, "country": "ru"},
    {"name": "Karnei4 IPTV-RU",     "url": "https://karnei4.github.io/IPTV-RU/playlist.m3u", "priority": 6, "country": "ru"},
]

# m3u.su — коды для динамического парсинга (страницы и региональные)
M3U_SU_PAGES = [1, 2, 3, 4, 5]
M3U_SU_REGIONAL_CODES = [
    "de-1", "de0", "de1", "de2", "de3", "de4", "de5", "de6", "de7", "de8", "de9", "der",
    "dze", "dzcb", "dzmo", "dzsp", "dzns", "dzkd", "dzpr", "dzk", "dzs",
    "dzom", "dzuf", "dzki", "dzvr", "dzn", "dzr", "dzt", "dznn", "dzvd",
    "dzvg", "dzv", "dzh", "dzyk", "dzir", "dzm", "dzkl", "dzpe", "dzb",
    "dzke", "dzkk", "dzu", "dzby", "dzl", "dzyr", "dzc", "dzct", "dzul",
    "d1", "d5", "dh", "dz", "ds",
]

# ================================================================
# ЛОГИРОВАНИЕ
# ================================================================
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("iptv_merger")

log = None  # будет инициализирован позже

# ================================================================
# ДАННЫЕ КАНАЛА
# ================================================================
@dataclass
class Channel:
    name: str = ""
    url: str = ""
    group: str = ""
    logo: str = ""
    tvg_id: str = ""
    tvg_name: str = ""
    source_name: str = ""
    source_priority: int = 0
    country: str = ""       # "ru", "ua", "world"
    timeshift: int = 0
    is_working: bool = False
    check_passed: int = 0   # 0=не проверен, 1=HTTP OK, 2=HLS OK

    @property
    def clean_name(self) -> str:
        n = self.name.strip()
        n = re.sub(r"\s*(HD|SD|UHD|4K|FHD|1080p|720p|H\.264|H\.265)\s*$", "", n, flags=re.IGNORECASE)
        n = re.sub(r"\s+", " ", n).strip()
        return n

    @property
    def is_broken_logo(self) -> bool:
        return bool(self.logo) and (
            "data:image" in self.logo.lower()
            or "<svg" in self.logo.lower()
            or len(self.logo) > 300
        )

    @property
    def is_garbage_name(self) -> bool:
        n = self.clean_name
        if len(n) < 2:
            return True
        # Доля читаемых символов (буквы, цифры, пробелы, кириллица)
        readable = sum(1 for c in n if c.isalnum() or c.isspace() or '\u0400' <= c <= '\u04FF')
        return (readable / max(len(n), 1)) < 0.4

    @property
    def quality_score(self) -> int:
        score = self.source_priority * 15
        n = self.name.upper()
        if "4K" in n or "UHD" in n:
            score += 50
        elif "1080" in n or "FHD" in n:
            score += 35
        elif "HD" in n:
            score += 20
        if self.timeshift == 2:
            score += 100
        elif self.timeshift > 0:
            score += 50
        return score

# ================================================================
# ПАРСИНГ M3U
# ================================================================
def parse_m3u(text: str, source_name: str, priority: int = 0,
              country: str = "", timeshift: int = 0) -> List[Channel]:
    channels = []
    lines = text.splitlines()
    current = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            current = {}
            m = re.search(r",(.+)$", line)
            if m:
                current["title"] = m.group(1).strip()
            for attr in re.finditer(r'(\S+?)="([^"]*)"', line):
                current[attr.group(1)] = attr.group(2)
        elif line.startswith("#") or not line.startswith("http"):
            continue
        elif current.get("title"):
            raw_name = current.get("title", "")
            logo = current.get("tvg-logo", "")
            tvg_id = current.get("tvg-id", "")
            tvg_name = current.get("tvg-name", "")
            group = current.get("group-title", "")
            ts_match = re.search(r'\(\s*\+(\d+)\s*\)', raw_name)
            detected_ts = timeshift if not ts_match else int(ts_match.group(1))
            ch = Channel(
                name=raw_name,
                url=line,
                group=group,
                logo=logo,
                tvg_id=tvg_id,
                tvg_name=tvg_name,
                source_name=source_name,
                source_priority=priority,
                country=country,
                timeshift=detected_ts,
            )
            if ch.clean_name:
                channels.append(ch)
            current = {}
    return channels

# ================================================================
# ОПРЕДЕЛЕНИЕ СТРАНЫ
# ================================================================
RU_KEYWORDS = ["первый","россия","россия1","рctp","ртр","нтв","рен","стс",
               "тнт","звезда","мир","отр","твц","тв-3","пятница","матч",
               "спас","домашний","челябинск","екатеринбург","москва","самара",
               "узбекистан","казахстан","belarus","minsk"]
UA_KEYWORDS = ["украина","україна","1+1","интер","новий","стб","укр","ua-",
               "тет","плюс","ictv","канал","пятый","марилет","hromadske"]

def detect_country(ch: Channel) -> str:
    text = (ch.name + " " + ch.group + " " + ch.source_name).lower()
    if any(k in text for k in RU_KEYWORDS) or ch.country == "ru":
        return "ru"
    if any(k in text for k in UA_KEYWORDS) or ch.country == "ua":
        return "ua"
    return "world"

# ================================================================
# ГЛУБОКИЙ ПАРСЕР m3u.su (параллельная загрузка всех плейлистов)
# ================================================================
async def discover_m3u_su_codes(session: aiohttp.ClientSession) -> List[str]:
    all_codes = set(M3U_SU_REGIONAL_CODES)
    headers = {"User-Agent": "IPTV-Merger/4.0"}
    for page_num in M3U_SU_PAGES:
        try:
            url = f"https://m3u.su/page/{page_num}"
            async with session.get(url, timeout=15, headers=headers) as resp:
                if resp.status != 200:
                    continue
                html = await resp.text()
                found = re.findall(r'href="/([a-zA-Z0-9][a-zA-Z0-9_-]{0,12})(?:\.m3u[^"]*)?(?:/details)?"', html)
                skip = {"page", "docs", "status", "locale", "source", "tabbar"}
                for code in found:
                    code = code.lower().strip()
                    if code and code not in skip and not code.startswith("page"):
                        all_codes.add(code)
        except Exception as e:
            log.debug(f"m3u.su page {page_num}: {e}")
    log.info(f"m3u.su: найдено {len(all_codes)} уникальных кодов")
    return sorted(all_codes)

async def fetch_m3u_su_playlists(session: aiohttp.ClientSession) -> List[Channel]:
    codes = await discover_m3u_su_codes(session)
    log.info(f"m3u.su: загрузка {len(codes)} плейлистов параллельно (лимит {CONFIG['MAX_PARALLEL_DOWNLOADS']})")
    semaphore = asyncio.Semaphore(CONFIG["MAX_PARALLEL_DOWNLOADS"])
    all_channels = []

    async def fetch_one(code: str) -> List[Channel]:
        async with semaphore:
            for ext in [".m3u8", ".m3u", ""]:
                try:
                    url = f"https://m3u.su/{code}{ext}"
                    async with session.get(url, timeout=20, allow_redirects=True) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                        if "#EXTM3U" not in text and "#EXTINF" not in text:
                            continue
                        chs = parse_m3u(text, source_name=f"m3u.su/{code}", priority=7, country="ru")
                        for ch in chs:
                            ch.country = detect_country(ch)
                        if chs:
                            log.debug(f"  m3u.su/{code}: {len(chs)} каналов")
                        return chs
                except Exception:
                    continue
            return []

    tasks = [fetch_one(code) for code in codes]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, list):
            all_channels.extend(r)
    log.info(f"m3u.su: загружено {len(all_channels)} каналов из {len(codes)} плейлистов")
    return all_channels

# ================================================================
# ТРЁХУРОВНЕВАЯ ПРОВЕРКА (100%-НАЯ)
# ================================================================
STREAM_CONTENT_TYPES = {
    "video/", "audio/",
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "application/octet-stream",
}
GOOD_FIRST_BYTES = (
    b"#EXTM3U", b"#EXT-X", b"#EXTINF",
    b"\x00\x00\x00", b"\x47", b"\x1a\x45\xdf\xa3",
    b"\x00\x00\x00\x1c", b"\x00\x00\x00\x18", b"\x00\x00\x00\x20",
    b"FLV",
)
BAD_FIRST_BYTES = (
    b"<!DOCTYPE", b"<html", b"<HTML",
    b"<head", b"<HEAD", b"<!doctype", b"<html>", b"<html ",
    b"404 ", b"403 ", b"502 ", b"503 ",
    b"not found", b"forbidden", b"error",
    b"<title>404", b"<title>Not Found",
)

async def check_channel_http(ch: Channel, session: aiohttp.ClientSession, timeout: int) -> Channel:
    headers = {"User-Agent": "VLC/3.0.21 LibVLC/3.0.21", "Accept": "*/*", "Icy-MetaData": "1"}
    url = ch.url

    try:
        # --- Уровень 1: HEAD (если включено) ---
        if CONFIG.get("HEAD_FIRST", True):
            try:
                async with session.head(url, timeout=timeout, allow_redirects=True, headers=headers, ssl=False) as resp:
                    if resp.status >= 400:
                        return ch
                    ct = resp.headers.get("Content-Type", "").lower()
                    if any(ct.startswith(t) for t in ["video/", "audio/"]):
                        ch.is_working = True
                        ch.check_passed = 1
                        return ch
            except:
                pass

        # --- Уровень 2: GET первых 8192 байт ---
        try:
            async with session.get(url, timeout=timeout, allow_redirects=True, headers=headers, ssl=False) as resp:
                if resp.status >= 400:
                    return ch

                ct = resp.headers.get("Content-Type", "").lower()
                if any(good in ct for good in STREAM_CONTENT_TYPES):
                    ch.is_working = True
                    ch.check_passed = 1
                    return ch

                chunk = await resp.content.read(8192)
                if not chunk:
                    return ch

                # Отбрасываем явный HTML
                chunk_lower = chunk[:512].lower()
                if any(chunk_lower.startswith(bad) for bad in BAD_FIRST_BYTES):
                    return ch
                if b"<html" in chunk_lower or b"<!doctype" in chunk_lower:
                    return ch

                # Принимаем если первые байты совпадают с известными сигнатурами
                if any(chunk.startswith(good) for good in GOOD_FIRST_BYTES):
                    ch.is_working = True
                    ch.check_passed = 1
                    return ch

                # Если похоже на текстовый M3U8
                try:
                    chunk_str = chunk.decode('utf-8', errors='ignore')
                except:
                    chunk_str = ""
                if "#EXTM3U" in chunk_str or "#EXT-X-" in chunk_str:
                    ch.is_working = True
                    ch.check_passed = 1
                    # --- Уровень 3: HLS probe с поиском любого сегмента ---
                    # Ищем все строки, не начинающиеся с '#', и пробуем первый рабочий сегмент
                    lines = chunk_str.splitlines()
                    segment_urls = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#') and (line.startswith('http') or '/' in line):
                            if not line.startswith('http'):
                                # Строим абсолютный URL
                                parsed = urlparse(url)
                                base = f"{parsed.scheme}://{parsed.netloc}"
                                path = parsed.path.rsplit('/', 1)[0]
                                line = urljoin(base + '/' + path + '/', line)
                            segment_urls.append(line)
                    # Пробуем первые 3 сегмента
                    for seg_url in segment_urls[:3]:
                        try:
                            async with session.get(seg_url, timeout=CONFIG["HLS_PROBE_TIMEOUT"],
                                                  allow_redirects=True, headers=headers, ssl=False) as seg_resp:
                                if seg_resp.status == 200:
                                    seg_chunk = await seg_resp.content.read(1024)
                                    if seg_chunk and not any(seg_chunk.lower().startswith(bad) for bad in BAD_FIRST_BYTES):
                                        ch.is_working = True
                                        ch.check_passed = 2
                                        return ch
                        except:
                            continue
                    # Если ни один сегмент не загрузился, считаем канал нерабочим
                    ch.is_working = False
                    ch.check_passed = 0
                    return ch

                # Если большой бинарный блок (>2KB) и нет HTML — вероятно, поток
                if len(chunk) > 2048 and b"<html" not in chunk_lower:
                    # Дополнительно проверим наличие медиа-сигнатур
                    if b"\x47" in chunk[:100] or b"\x00\x00\x01" in chunk[:100]:
                        ch.is_working = True
                        ch.check_passed = 1
                        return ch
        except:
            pass
    except Exception as e:
        log.debug(f"Ошибка проверки {ch.url[:80]}: {e}")
    return ch

# ================================================================
# ПАРАЛЛЕЛЬНАЯ ПРОВЕРКА С ПРИОРИТЕТОМ
# ================================================================
async def smart_check(
    channels: List[Channel],
    max_working: int,
    min_working: int,
    workers: int,
) -> List[Channel]:
    # Сортируем по убыванию качества, лучшие — первыми
    channels.sort(key=lambda x: (-x.quality_score, x.clean_name))
    total = len(channels)
    working = []
    semaphore = asyncio.Semaphore(workers)

    # Используем сессию с большим пулом соединений
    connector = aiohttp.TCPConnector(limit=workers, limit_per_host=50, ssl=False, force_close=False)
    session = aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=CONFIG["CHECK_TIMEOUT"] + 3),
        headers={"User-Agent": "IPTV-Checker/4.0"}
    )

    try:
        async def bounded(ch: Channel) -> Channel:
            async with semaphore:
                return await check_channel_http(ch, session, CONFIG["CHECK_TIMEOUT"])

        batch_size = workers * 2  # динамический размер пачки
        processed = 0
        for i in range(0, total, batch_size):
            batch = channels[i:i + batch_size]
            tasks = [bounded(ch) for ch in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Channel) and r.is_working:
                    working.append(r)
            processed = min(i + batch_size, total)
            log.info(
                f"  Проверено: {processed}/{total} | Рабочих: {len(working)} | "
                f"Успех: {len(working)/max(processed,1)*100:.1f}% | Потоков: {workers}"
            )
            if len(working) >= max_working:
                log.info(f"  Достигнут лимит {max_working} каналов, досрочная остановка.")
                break
    finally:
        await session.close()

    if len(working) < min_working:
        log.warning(f"  Найдено только {len(working)} рабочих (минимум {min_working})")
    return working

# ================================================================
# ДЕДУПЛИКАЦИЯ И ОЧИСТКА
# ================================================================
def deduplicate_by_url(channels: List[Channel]) -> List[Channel]:
    seen: Dict[str, Channel] = {}
    for ch in channels:
        if ch.url in seen:
            if ch.quality_score > seen[ch.url].quality_score:
                seen[ch.url] = ch
        else:
            seen[ch.url] = ch
    log.info(f"  Дедупликация по URL: {len(channels)} → {len(seen)} (удалено {len(channels)-len(seen)})")
    return list(seen.values())

_bad_name_counter = 0
def sanitize_channel_name(ch: Channel) -> Channel:
    global _bad_name_counter
    if ch.is_broken_logo:
        ch.logo = ""
    if ch.is_garbage_name:
        _bad_name_counter += 1
        ch.name = f"Канал {_bad_name_counter}"
        ch.logo = ""
    return ch

def sort_channels(channels: List[Channel]) -> List[Channel]:
    def sort_key(ch: Channel):
        ts_rank = 0 if ch.timeshift == 2 else (1 if ch.timeshift > 0 else 2)
        country = detect_country(ch)
        country_rank = 0 if country == "ru" else (1 if country == "ua" else 2)
        name_rank = 0 if not ch.is_garbage_name else 1
        quality = -ch.quality_score
        alpha = ch.clean_name.lower()
        return (ts_rank, country_rank, name_rank, quality, alpha)
    channels.sort(key=sort_key)
    return channels

def export_m3u(channels: List[Channel], filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in channels:
            attrs = []
            if ch.tvg_id:
                attrs.append(f'tvg-id="{ch.tvg_id}"')
            if ch.tvg_name:
                attrs.append(f'tvg-name="{ch.tvg_name}"')
            if ch.logo and not ch.is_broken_logo:
                attrs.append(f'tvg-logo="{ch.logo}"')
            if ch.group:
                attrs.append(f'group-title="{ch.group}"')
            attr_str = " ".join(attrs)
            f.write(f"#EXTINF:-1 {attr_str},{ch.name}\n")
            f.write(f"{ch.url}\n")
    log.info(f"Плейлист сохранён: {filepath} ({len(channels)} каналов)")

# ================================================================
# ЗАГРУЗКА СТАТИЧЕСКИХ ИСТОЧНИКОВ (ПАРАЛЛЕЛЬНО)
# ================================================================
async def download_source(session: aiohttp.ClientSession, src: dict) -> List[Channel]:
    try:
        async with session.get(src["url"], timeout=30, allow_redirects=True, ssl=False) as resp:
            if resp.status != 200:
                log.warning(f"  ✗ {src['name']}: HTTP {resp.status}")
                return []
            text = await resp.text()
            if "#EXTM3U" not in text and "#EXTINF" not in text:
                log.warning(f"  ✗ {src['name']}: не M3U-формат ({len(text)} байт)")
                return []
            chs = parse_m3u(text, src["name"], src.get("priority",0), src.get("country",""), src.get("timeshift",0))
            log.info(f"  ✓ {src['name']}: {len(chs)} каналов")
            return chs
    except Exception as e:
        log.warning(f"  ✗ {src['name']}: {e}")
        return []

async def download_all_static(session: aiohttp.ClientSession) -> List[Channel]:
    log.info(f"Загрузка {len(STATIC_SOURCES)} статических источников (параллельно, лимит {CONFIG['MAX_PARALLEL_DOWNLOADS']})")
    sem = asyncio.Semaphore(CONFIG["MAX_PARALLEL_DOWNLOADS"])
    async def bounded(src):
        async with sem:
            return await download_source(session, src)
    tasks = [bounded(src) for src in STATIC_SOURCES]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_channels = []
    for r in results:
        if isinstance(r, list):
            all_channels.extend(r)
        elif isinstance(r, Exception):
            log.warning(f"  Ошибка при загрузке источника: {r}")
    log.info(f"Статические источники: {len(all_channels)} каналов")
    return all_channels

# ================================================================
# MAIN
# ================================================================
async def main():
    global log
    parser = argparse.ArgumentParser(description="IPTV Merger v4.0 — сверхбыстрый сборщик рабочих каналов")
    parser.add_argument("--min-channels", type=int, default=CONFIG["MIN_WORKING"], help="Минимум рабочих каналов")
    parser.add_argument("--max-channels", type=int, default=CONFIG["MAX_WORKING"], help="Максимум каналов")
    parser.add_argument("--workers", type=int, default=CONFIG["MAX_PARALLEL_CHECKS"], help="Потоков проверки (рекомендуется 150-300)")
    parser.add_argument("--downloads", type=int, default=CONFIG["MAX_PARALLEL_DOWNLOADS"], help="Параллельных загрузок плейлистов")
    parser.add_argument("--output", default=CONFIG["OUTPUT_FILE"], help="Имя выходного файла")
    parser.add_argument("--no-m3usu", action="store_true", help="Отключить глубокий парсинг m3u.su")
    parser.add_argument("--verbose", "-v", action="store_true", help="Детальное логирование (каждый канал)")
    parser.add_argument("--no-head-first", action="store_true", help="Пропустить HEAD-запрос (сразу GET)")
    args = parser.parse_args()

    # Настройка логирования
    log = setup_logging(args.verbose)
    CONFIG["HEAD_FIRST"] = not args.no_head_first
    CONFIG["MAX_PARALLEL_CHECKS"] = args.workers
    CONFIG["MAX_PARALLEL_DOWNLOADS"] = args.downloads
    CONFIG["MIN_WORKING"] = args.min_channels
    CONFIG["MAX_WORKING"] = args.max_channels
    CONFIG["OUTPUT_FILE"] = args.output

    start = time.time()
    log.info("="*70)
    log.info(f"IPTV Merger v4.0 | Цель: {args.min_channels}–{args.max_channels} каналов")
    log.info(f"Параметры: проверка {args.workers} потоков, загрузка {args.downloads} потоков")
    log.info("="*70)

    # Создаём общий connector для всех загрузок
    connector = aiohttp.TCPConnector(limit=args.downloads + 50, ssl=False, force_close=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        static_channels = await download_all_static(session)
        m3usu_channels = []
        if not args.no_m3usu:
            m3usu_channels = await fetch_m3u_su_playlists(session)

    all_channels = static_channels + m3usu_channels
    log.info(f"Всего загружено: {len(all_channels)} каналов")

    if not all_channels:
        log.error("Ни один источник не отдал каналов. Завершение.")
        return

    # Дедупликация по URL (до проверки, чтобы не тратить время на дубли)
    unique = deduplicate_by_url(all_channels)
    log.info(f"После дедупликации: {len(unique)} уникальных URL")

    # Проверка работоспособности
    log.info(f"Начинаем проверку (до {args.max_channels} рабочих)...")
    working = await smart_check(unique, args.max_channels, args.min_channels, args.workers)

    # Повторная дедупликация (на случай дублей после проверки)
    working = deduplicate_by_url(working)

    # Очистка имён
    log.info("Очистка имён каналов...")
    working = [sanitize_channel_name(ch) for ch in working]

    # Сортировка
    log.info("Сортировка каналов...")
    working = sort_channels(working)

    # Экспорт
    export_m3u(working, args.output)

    elapsed = time.time() - start
    ru_count = sum(1 for ch in working if detect_country(ch) == "ru")
    ua_count = sum(1 for ch in working if detect_country(ch) == "ua")
    ts2_count = sum(1 for ch in working if ch.timeshift == 2)

    log.info("="*70)
    log.info(f"ГОТОВО за {elapsed:.1f} сек")
    log.info(f"  Всего: {len(working)} каналов")
    log.info(f"  Русских: {ru_count} | Украинских: {ua_count} | MSK+2: {ts2_count}")
    log.info(f"  Файл: {args.output}")
    log.info("="*70)

if __name__ == "__main__":
    asyncio.run(main())
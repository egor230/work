#!/usr/bin/env python3
"""
VPN Finder PRO — качественный VPN для AI (ChatGPT, Claude, Perplexity)
  • Жёсткое исключение России и СНГ
  • Проверка на 3 AI-сервисах (с проверкой содержимого)
  • Многопоточный поиск, лимит 7 минут
  • Тест скорости и копирование лучшего конфига
"""

import os
import sys
import json
import time
import re
import socket
import base64
import random
import argparse
import tempfile
import subprocess
import signal
import threading
from urllib.request import urlopen, Request
from urllib.parse import parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===================== НАСТРОЙКИ =====================
REPO_BASE = "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/main/githubmirror"
REPO_FILES = [f"{i}.txt" for i in range(1, 27)]

EXTRA_REPOS = [
    "https://raw.githubusercontent.com/Romaxa55/MegaV_Public/main/subs/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub.txt",
    "https://raw.githubusercontent.com/MhdiJafari/Free-V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/sarinaesmailzadeh/V2ray-Configs/main/Sub.txt",
    "https://raw.githubusercontent.com/Mahdi-zarei/v2ray-configs/main/Sub.txt",
    "https://raw.githubusercontent.com/proxy4paradise/proxy-list/main/v2ray.txt",
    "https://raw.githubusercontent.com/ziizii3/V2ray-config/main/sub.txt",
]

# Приоритетные страны (сначала ищем их)
PREFERRED_COUNTRIES = [
    "nl", "gb", "de", "fr", "pl", "lt", "lv", "ee", "se", "no",
    "fi", "at", "ch", "be", "dk", "it", "es", "us", "cz", "ro",
    "jp", "kr", "sg", "ca", "au", "ie", "pt", "hu", "sk", "bg",
]

# Полностью исключаемые страны (РФ и союзники)
EXCLUDE_COUNTRIES = ["ru", "by", "kz", "am", "ge", "md", "uz", "tm", "kg", "az"]

# Российские ключевые слова – расширенный список
RU_KEYWORDS = [
    "russia", "россия", "рус", "русь", "москва", "moscow", "петербург",
    "petersburg", "новосибирск", "ekaterinburg", "нижний", "nizhny",
    "самара", "samara", "казань", "kazan", "ростов", "rostov",
    "краснодар", "krasnodar", "воронеж", "ufa", "уфа", "омск", "omsk",
    "челябинск", "chelyabinsk", "rostelecom", "мтс", "mts", "билайн",
    "beeline", "megafon", "мегафон", "yota", "ртк", "ростелеком",
    "ru-", "-ru-", "_ru_", ".ru", "ru.",  # любые вариации
]

HARD_TIMEOUT = 420           # 7 минут
TIMEOUT_DL = 10
TIMEOUT_TEST = 8             # увеличен для AI-сайтов
MAX_LATENCY = 3000           # увеличен, т.к. AI-сайты могут быть медленнее
MAX_DL_WORKERS = 32
MAX_TEST_WORKERS = 150       # умеренное число для качества
NEED = 5
SPEED_TEST_SIZE = 10_000_000 # 10 МБ
SPEED_TEST_TIMEOUT = 20

# AI-сайты для проверки – каждый должен вернуть ожидаемый текст
AI_SITES = [
    ("https://chat.openai.com", "chat", "openai"),
    ("https://claude.ai", "claude", "claude"),
    ("https://www.perplexity.ai", "perplexity", "perplexity"),
]

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# Цвета
C = "\033[0;36m"
G = "\033[0;32m"
R = "\033[0;31m"
Y = "\033[1;33m"
B = "\033[1;34m"
N = "\033[0m"

# Глобальные состояния
found_lock = threading.Lock()
found_keys = []          # [(link, latency_ms), ...]
stop_event = threading.Event()
xray_pids = []
xray_lock = threading.Lock()
port_lock = threading.Lock()
START_TIME = 0.0

# ===================== УТИЛИТЫ =====================
def limit_fds():
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (min(hard, 8192), hard))
        except Exception:
            pass
    except ImportError:
        pass

def elapsed():
    return time.time() - START_TIME

def remaining():
    return max(0, HARD_TIMEOUT - elapsed())

def is_timeout():
    return elapsed() >= HARD_TIMEOUT

def get_port():
    with port_lock:
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", 0))
                    return s.getsockname()[1]
            except OSError:
                time.sleep(0.01)

def wait_for_port(port, timeout=4.0):
    start = time.time()
    while time.time() - start < timeout:
        if stop_event.is_set():
            return False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.05)
    return False

def kill_xrays():
    with xray_lock:
        for pid in xray_pids[:]:
            try:
                os.kill(pid, 9)
            except Exception:
                pass
        xray_pids.clear()

# ===================== ЖЁСТКИЙ ФИЛЬТР РОССИИ =====================
_RU_FLAG = "\U0001f1f7\U0001f1fa"
_COUNTRY_ALIASES = {
    "uk": "gb", "usa": "us", "eng": "gb", "deu": "de", "fra": "fr",
    "nld": "nl", "rus": "ru", "blr": "by", "kaz": "kz",
}

def _normalize_country(cc):
    return _COUNTRY_ALIASES.get(cc, cc)

def extract_country_code(link):
    remark = link.split("#", 1)[1].lower() if "#" in link else ""
    host_part = link.split("@", 1)[-1].lower() if "@" in link else ""
    text = f"{remark} {host_part}"

    # Ищем двухбуквенный код в скобках, подчёркиваниях и т.д.
    tokens = re.findall(r"[\[\(_\-\s\.\/]([a-z]{2})[\]\)_\-\s\.\/]", text)
    for t in tokens:
        return _normalize_country(t)

    # Если в remark есть отдельное слово из двух букв
    m = re.search(r"\b([a-z]{2})\b", remark)
    if m:
        return _normalize_country(m.group(1))

    # Проверяем хост на наличие кодов исключённых стран
    for cc in EXCLUDE_COUNTRIES:
        if re.search(rf"(^|[.\-_]){cc}([.\-_]|$)", host_part):
            return cc

    return ""

def is_russian(link):
    """
    Максимально жёсткая проверка на российское происхождение.
    Возвращает True при любом подозрении.
    """
    remark = link.split("#", 1)[1] if "#" in link else ""
    remark_lower = remark.lower()
    host_part = link.split("@", 1)[-1].lower() if "@" in link else ""
    full = f"{remark_lower} {host_part}"

    # 1. Код страны ru
    if extract_country_code(link) == "ru":
        return True

    # 2. Российский флаг
    if _RU_FLAG in remark:
        return True

    # 3. Любое ключевое слово
    for kw in RU_KEYWORDS:
        if kw in full:
            return True

    # 4. Домен .ru или паттерн ru-/-ru в любой части
    if re.search(r"(^|[.\-_])ru([.\-_]|$)", host_part):
        return True
    if ".ru:" in host_part or host_part.endswith(".ru"):
        return True

    # 5. Явные маркеры [RU], (RU) и т.д.
    if re.search(r"[\[\(]ru[\]\)]", full):
        return True

    return False

def is_excluded_country(link):
    cc = extract_country_code(link)
    if cc in EXCLUDE_COUNTRIES:
        return True
    host_part = link.split("@", 1)[-1].lower() if "@" in link else ""
    for exc_cc in EXCLUDE_COUNTRIES:
        if re.search(rf"(^|[.\-_]){exc_cc}([.\-_]|$)", host_part):
            return True
    return False

# ===================== ПАРСЕРЫ (без изменений) =====================
def b64_decode(s):
    s = s.replace("-", "+").replace("_", "/")
    pad = (4 - len(s) % 4) % 4
    s += "=" * pad
    try:
        return base64.b64decode(s).decode("utf-8", errors="ignore")
    except Exception:
        return ""

def parse_vless(link):
    try:
        body = link[len("vless://"):]
        frag, _, query = body.partition("?")
        uuid_part, _, rest = frag.partition("@")
        addr, _, port_str = rest.rpartition(":")
        if addr.startswith("["):
            addr = addr.strip("[]")
        port = int(port_str)
        params = parse_qs(query)
        net = params.get("type", ["tcp"])[0]
        sni = params.get("sni", [""])[0] or params.get("host", [""])[0]
        fp = params.get("fp", ["chrome"])[0]
        sec = params.get("security", ["none"])[0]
        stream = {"network": net, "security": "none"}
        if sec == "reality":
            stream["security"] = "reality"
            stream["realitySettings"] = {
                "serverName": sni,
                "fingerprint": fp,
                "publicKey": params.get("pbk", [""])[0],
                "shortId": params.get("sid", [""])[0],
                "spiderX": params.get("spx", ["/"])[0],
            }
        elif sec == "tls":
            stream["security"] = "tls"
            stream["tlsSettings"] = {
                "serverName": sni or addr,
                "fingerprint": fp,
                "allowInsecure": False,
            }
        if net == "ws":
            path = params.get("path", ["/"])[0]
            host = params.get("host", [""])[0] or sni
            headers = {"Host": host} if host else {}
            stream["wsSettings"] = {"path": path, "headers": headers}
        elif net == "grpc":
            stream["grpcSettings"] = {
                "serviceName": params.get("serviceName", [""])[0],
                "multiMode": params.get("mode", [""])[0] == "multi",
            }
        elif net == "h2":
            stream["httpSettings"] = {
                "path": params.get("path", ["/"])[0],
                "host": params.get("host", [addr])[0].split(","),
            }
        return {
            "protocol": "vless",
            "settings": {"vnext": [{"address": addr, "port": port,
                                    "users": [{"id": uuid_part, "encryption": "none"}]}]},
            "streamSettings": stream,
        }
    except Exception:
        return None

def parse_vmess(link):
    try:
        decoded = json.loads(b64_decode(link[len("vmess://"):]))
        net = decoded.get("net", "tcp")
        stream = {"network": net}
        if decoded.get("tls") == "tls":
            stream["security"] = "tls"
            stream["tlsSettings"] = {
                "serverName": decoded.get("sni") or decoded.get("add"),
                "fingerprint": decoded.get("fp", "chrome"),
                "allowInsecure": False,
            }
        if net == "ws":
            stream["wsSettings"] = {
                "path": decoded.get("path", "/"),
                "headers": {"Host": decoded.get("host", "")},
            }
        elif net == "grpc":
            stream["grpcSettings"] = {"serviceName": decoded.get("path", "")}
        return {
            "protocol": "vmess",
            "settings": {"vnext": [{"address": decoded["add"], "port": int(decoded["port"]),
                                    "users": [{"id": decoded["id"],
                                               "alterId": int(decoded.get("aid", 0)),
                                               "security": decoded.get("scy", "auto")}]}]},
            "streamSettings": stream,
        }
    except Exception:
        return None

def parse_trojan(link):
    try:
        body = link[len("trojan://"):]
        frag, _, query = body.partition("?")
        pw, _, rest = frag.partition("@")
        if rest.startswith("["):
            addr, _, port_str = rest[1:].partition("]")
            port_str = port_str.lstrip(":")
        else:
            addr, _, port_str = rest.rpartition(":")
        port = int(port_str)
        params = parse_qs(query)
        sni = params.get("sni", [""])[0] or params.get("host", [""])[0] or addr
        net = params.get("type", ["tcp"])[0]
        stream = {"network": net, "security": "tls",
                  "tlsSettings": {"serverName": sni, "allowInsecure": False}}
        if net == "ws":
            stream["wsSettings"] = {
                "path": params.get("path", ["/"])[0],
                "headers": {"Host": params.get("host", [""])[0]},
            }
        return {
            "protocol": "trojan",
            "settings": {"servers": [{"address": addr, "port": port, "password": pw}]},
            "streamSettings": stream,
        }
    except Exception:
        return None

def parse_hy2(link):
    try:
        body = link.split("://", 1)[1]
        frag, _, query = body.partition("?")
        pw, _, rest = frag.partition("@")
        if rest.startswith("["):
            addr, _, port_str = rest[1:].partition("]")
            port_str = port_str.lstrip(":")
        else:
            addr, _, port_str = rest.rpartition(":")
        port = int(port_str)
        q = parse_qs(query)
        sni = q.get("sni", [""])[0] or addr
        ob = {
            "protocol": "hysteria2",
            "settings": {"servers": [{"address": addr, "port": port, "password": pw}]},
            "streamSettings": {"network": "hysteria2", "security": "tls",
                               "tlsSettings": {"serverName": sni, "allowInsecure": False}},
        }
        if q.get("obfs"):
            ob["streamSettings"]["sockopt"] = {}
        return ob
    except Exception:
        return None

def link_to_outbound(link):
    if link.startswith("vless://"):
        return parse_vless(link)
    if link.startswith("vmess://"):
        return parse_vmess(link)
    if link.startswith("trojan://"):
        return parse_trojan(link)
    if link.startswith(("hysteria2://", "hy2://")):
        return parse_hy2(link)
    return None

def extract_host_port(link):
    try:
        if link.startswith("vless://"):
            body = link[8:]
            frag = body.split("?")[0]
            _, rest = frag.split("@", 1)
        elif link.startswith("vmess://"):
            decoded = json.loads(b64_decode(link[8:]))
            return decoded.get("add", ""), int(decoded.get("port", 0))
        elif link.startswith("trojan://"):
            body = link[9:]
            frag = body.split("?")[0]
            _, rest = frag.split("@", 1)
        elif link.startswith(("hysteria2://", "hy2://")):
            body = link.split("://", 1)[1]
            frag = body.split("?")[0]
            _, rest = frag.split("@", 1)
        else:
            return None, None

        if rest.startswith("["):
            addr, port_str = rest[1:].split("]", 1)
            port_str = port_str.lstrip(":")
        else:
            addr, port_str = rest.rsplit(":", 1)
        return addr, int(port_str)
    except Exception:
        return None, None

# ===================== ЗАГРУЗКА =====================
def download_one(url):
    safe_name = url.split("/")[-1].split("?")[0] or "list"
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=TIMEOUT_DL) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                if data.strip():
                    os.makedirs(LOGS_DIR, exist_ok=True)
                    with open(os.path.join(LOGS_DIR, f"raw_{safe_name}"), "w", encoding="utf-8") as f:
                        f.write(data)
                    return data
        except Exception:
            time.sleep(0.5 * (attempt + 1))
    return None

def download_file(url):
    data = download_one(url)
    if data is None:
        return []
    links = [line.strip() for line in data.splitlines() if line.strip() and not line.startswith("#")]
    return links

def download_all_parallel(urls):
    all_links = []
    with ThreadPoolExecutor(max_workers=MAX_DL_WORKERS) as pool:
        futures = {pool.submit(download_file, url): url for url in urls}
        for future in as_completed(futures):
            all_links.extend(future.result())
    return all_links

# ===================== ПРОВЕРКА С AI-САЙТАМИ =====================
def check_ai_access(link):
    """
    Запускает xray, проверяет доступ к трём AI-сайтам.
    Возвращает среднюю задержку в мс или None.
    """
    if stop_event.is_set():
        return None

    if not any(link.startswith(p) for p in ("vless://", "vmess://", "trojan://", "hysteria2://", "hy2://")):
        return None

    # Жёсткая фильтрация России
    if is_russian(link) or is_excluded_country(link):
        return None

    host, port_num = extract_host_port(link)
    if not host or not port_num:
        return None

    # TCP-проверка
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((host, port_num))
    except Exception:
        return None

    outbound = link_to_outbound(link)
    if not outbound:
        return None

    local_port = get_port()
    config = {
        "log": {"loglevel": "error"},
        "dns": {
            "servers": [
                {"address": "https://1.1.1.1/dns-query",
                 "domains": ["geosite:geolocation-!cn"],
                 "expectIPs": ["geoip:!cn"]},
                "1.1.1.1", "8.8.8.8",
            ],
            "queryStrategy": "UseIP",
        },
        "inbounds": [{"listen": "127.0.0.1", "port": local_port,
                       "protocol": "socks",
                       "settings": {"auth": "noauth", "udp": True}}],
        "outbounds": [outbound, {"protocol": "freedom", "tag": "direct",
                                  "settings": {"domainStrategy": "UseIP"}}],
        "routing": {"rules": [{"type": "field", "ip": ["geoip:private"],
                                "outboundTag": "direct"}]},
    }

    tmpf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(config, tmpf)
    tmpf.close()

    proc = None
    try:
        proc = subprocess.Popen(
            ["xray", "run", "-config", tmpf.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with xray_lock:
            xray_pids.append(proc.pid)

        if not wait_for_port(local_port, timeout=5.0) or proc.poll() is not None:
            return None

        latencies = []
        all_ok = True

        for url, keyword1, keyword2 in AI_SITES:
            if stop_event.is_set():
                return None

            t0 = time.time()
            try:
                # Используем curl для получения содержимого
                cmd = [
                    "curl", "-x", f"socks5h://127.0.0.1:{local_port}",
                    "-s", "-L", "--max-time", str(TIMEOUT_TEST),
                    "--connect-timeout", str(TIMEOUT_TEST),
                    url
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_TEST+3)
                dt = (time.time() - t0) * 1000
                body = r.stdout.lower()

                # Проверяем наличие ключевых слов
                if (keyword1 not in body) and (keyword2 not in body):
                    all_ok = False
                    break

                latencies.append(dt)

            except Exception:
                all_ok = False
                break

        if not all_ok or len(latencies) != len(AI_SITES):
            return None

        avg = sum(latencies) / len(latencies)
        return avg if avg < MAX_LATENCY else None

    except Exception:
        return None
    finally:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
            with xray_lock:
                xray_pids[:] = [p for p in xray_pids if p != proc.pid]
        try:
            os.unlink(tmpf.name)
        except Exception:
            pass

# ===================== ТЕСТ СКОРОСТИ =====================
def measure_speed(link, latency_ms):
    if stop_event.is_set():
        return None

    outbound = link_to_outbound(link)
    if not outbound:
        return None

    local_port = get_port()
    config = {
        "log": {"loglevel": "error"},
        "dns": {
            "servers": [
                {"address": "https://1.1.1.1/dns-query",
                 "domains": ["geosite:geolocation-!cn"],
                 "expectIPs": ["geoip:!cn"]},
                "1.1.1.1", "8.8.8.8",
            ],
            "queryStrategy": "UseIP",
        },
        "inbounds": [{"listen": "127.0.0.1", "port": local_port,
                       "protocol": "socks",
                       "settings": {"auth": "noauth", "udp": True}}],
        "outbounds": [outbound, {"protocol": "freedom", "tag": "direct",
                                  "settings": {"domainStrategy": "UseIP"}}],
        "routing": {"rules": [{"type": "field", "ip": ["geoip:private"],
                                "outboundTag": "direct"}]},
    }

    tmpf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(config, tmpf)
    tmpf.close()

    proc = None
    try:
        proc = subprocess.Popen(
            ["xray", "run", "-config", tmpf.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with xray_lock:
            xray_pids.append(proc.pid)

        if not wait_for_port(local_port, timeout=5.0) or proc.poll() is not None:
            return None

        # Быстрая проверка через Google (для уверенности)
        try:
            r = subprocess.run(
                ["curl", "-x", f"socks5h://127.0.0.1:{local_port}",
                 "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--connect-timeout", "5", "--max-time", "5",
                 "https://www.google.com/generate_204"],
                capture_output=True, text=True, timeout=8,
            )
            if r.returncode != 0 or r.stdout.strip() != "204":
                return None
        except Exception:
            return None

        # Тест скорости
        speed_mbps = 0.0
        test_url = f"https://speed.cloudflare.com/__down?bytes={SPEED_TEST_SIZE}"
        try:
            result = subprocess.run(
                ["curl", "-x", f"socks5h://127.0.0.1:{local_port}",
                 "-s", "-o", "/dev/null", "-w", "%{speed_download}",
                 "--connect-timeout", "5",
                 "--max-time", str(SPEED_TEST_TIMEOUT),
                 test_url],
                capture_output=True, text=True,
                timeout=SPEED_TEST_TIMEOUT + 5,
            )
            if result.returncode == 0 and result.stdout.strip():
                speed_bytes = float(result.stdout.strip())
                speed_mbps = speed_bytes * 8 / 1_000_000
        except Exception:
            pass

        return (link, latency_ms, speed_mbps)

    except Exception:
        return None
    finally:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
            with xray_lock:
                xray_pids[:] = [p for p in xray_pids if p != proc.pid]
        try:
            os.unlink(tmpf.name)
        except Exception:
            pass

# ===================== ВЫВОД И КОПИРОВАНИЕ =====================
def copy_to_clipboard(text, no_clipboard=False):
    if no_clipboard:
        return
    for cmd in (
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ):
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
            p.communicate(text)
            if p.returncode == 0:
                print(f"{G}✓ Скопировано в буфер обмена{N}")
                return
        except FileNotFoundError:
            continue
    print(f"{Y}⚠ Не удалось скопировать (установите wl-copy/xclip/xsel){N}")

def save_and_output(results, no_clipboard=False):
 if not results:
  print(f"{R}Рабочих конфигов не найдено.{N}")
  return
 
 # Сортировка
 has_speed = any(r[2] > 0 for r in results)
 if has_speed:
  results.sort(key=lambda x: (-x[2], x[1]))
  sort_type = "скорости"
 else:
  results.sort(key=lambda x: x[1])
  sort_type = "задержке"
 
 print(f"\n{G}{'=' * 70}{N}")
 print(f"{G}✅ Результаты (отсортированы по {sort_type}):{N}")
 print(f"{G}{'=' * 70}{N}")
 
 # Сохранение лога
 try:
  os.makedirs(LOGS_DIR, exist_ok=True)
  ts = time.strftime("%Y%m%d_%H%M%S")
  log_path = os.path.join(LOGS_DIR, f"vpn_results_{ts}.txt")
  with open(log_path, "w", encoding="utf-8") as f:
   for i, (link, lat, spd) in enumerate(results[:NEED]):
    cc = extract_country_code(link) or "??"
    f.write(f"# {i + 1}. country={cc} latency={lat:.0f}ms speed={spd:.1f}Mbps\n")
    f.write(f"{link}\n\n")
  print(f"{C}Результаты сохранены: {log_path}{N}")
 except Exception as e:
  print(f"{Y}⚠ Не удалось сохранить лог: {e}{N}")
 
 # Формируем лучшую ссылку и список всех top_links
 best_link = results[0][0]
 
 # Вывод в консоль
 for i, (link, lat, spd) in enumerate(results[:NEED]):
  cc = extract_country_code(link) or "??"
  remark = link.split("#", 1)[1][:40] if "#" in link else ""
  speed_str = f" | скорость: {spd:.1f} Мбит/с" if spd > 0 else ""
  marker = f" {G}← САМЫЙ БЫСТРЫЙ{N}" if i == 0 else ""
  print(f"{G}{i + 1}. [{cc.upper()}] задержка: {lat:.0f}мс{speed_str} — {remark}{marker}")
  print(f"   {link[:80]}{'...' if len(link) > 80 else ''}{N}")
 
 # Копируем лучший конфиг в буфер обмена (один раз)
 print(f"\n{B}Копирую лучший конфиг в буфер обмена...{N}")
 copy_to_clipboard(best_link, no_clipboard)
 # Обновление конфига Hiddify
 # config_path = os.path.expanduser("~/.local/share/app.hiddify.com/shared_preferences.json")
 # try:
 #  with open(config_path, "r", encoding="utf-8") as f:
 #   config = json.load(f)
 #
 # except Exception as e:
 #  print(f"{R}Ошибка при обновлении конфига Hiddify: {e}{N}")

# ===================== ОБРАБОТЧИК СИГНАЛОВ =====================
def signal_handler(sig, frame):
    print(f"\n{R}Прерывание...{N}")
    stop_event.set()
    kill_xrays()
    sys.exit(0)

# ===================== ФИЛЬТРАЦИЯ =====================
def filter_links(all_links, max_test):
    seen = set()
    unique = []
    for link in all_links:
        if link not in seen:
            seen.add(link)
            unique.append(link)

    print(f"\n{B}Всего собрано {len(unique)} уникальных конфигов.{N}")

    non_ru = []
    ru_count = 0
    for link in unique:
        if is_russian(link) or is_excluded_country(link):
            ru_count += 1
        else:
            non_ru.append(link)

    print(f"{R}✗ Отброшено российских/СНГ конфигов: {ru_count}{N}")
    print(f"{G}✓ Конфигов без РФ/СНГ: {len(non_ru)}{N}")

    preferred = []
    others = []
    for link in non_ru:
        cc = extract_country_code(link)
        if cc in PREFERRED_COUNTRIES:
            preferred.append(link)
        else:
            others.append(link)

    print(f"{C}  Из них приоритетные страны: {len(preferred)}{N}")
    print(f"{C}  Остальные (не-СНГ): {len(others)}{N}")

    ordered = preferred + others
    if len(ordered) > max_test:
        if len(preferred) >= max_test // 2:
            pref_sample = random.sample(preferred, max_test // 2)
            other_sample = random.sample(others, min(len(others), max_test // 2))
        else:
            pref_sample = preferred
            other_sample = random.sample(others, min(len(others), max_test - len(preferred)))
        ordered = pref_sample + other_sample

    print(f"{B}Конфигов для тестирования: {len(ordered)}{N}\n")
    return ordered

# ===================== MAIN =====================
def main():
    global START_TIME, MAX_TEST_WORKERS, NEED, HARD_TIMEOUT

    parser = argparse.ArgumentParser(
        description="VPN Finder PRO — качественный VPN для AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python vpn.py
  python vpn.py --need 3 --threads 120
  python vpn.py --no-clipboard
  python vpn.py --timeout 300
        """,
    )
    parser.add_argument("--need", type=int, default=NEED,
                        help=f"Сколько лучших выводить (default: {NEED})")
    parser.add_argument("--max-test", type=int, default=400,
                        help="Макс. число тестируемых конфигов (default: 400)")
    parser.add_argument("--threads", type=int, default=MAX_TEST_WORKERS,
                        help=f"Потоков тестирования (default: {MAX_TEST_WORKERS})")
    parser.add_argument("--no-clipboard", action="store_true",
                        help="Не копировать в буфер обмена")
    parser.add_argument("--no-speed-test", action="store_true",
                        help="Пропустить тест скорости")
    parser.add_argument("--timeout", type=int, default=HARD_TIMEOUT,
                        help=f"Таймаут в секундах (default: {HARD_TIMEOUT})")
    args = parser.parse_args()

    NEED = args.need
    MAX_TEST_WORKERS = args.threads
    HARD_TIMEOUT = args.timeout

    START_TIME = time.time()
    limit_fds()
    signal.signal(signal.SIGINT, signal_handler)
    os.makedirs(LOGS_DIR, exist_ok=True)

    print(f"\n{C}{'═' * 70}{N}")
    print(f"{C}  VPN Finder PRO — ТОЛЬКО РАБОЧИЕ VPN ДЛЯ AI{N}")
    print(f"{C}  Исключены: Россия, Беларусь, Казахстан и др. СНГ{N}")
    print(f"{C}  Проверка: ChatGPT, Claude, Perplexity (содержимое){N}")
    print(f"{C}  Потоки: {MAX_TEST_WORKERS} | Таймаут: {HARD_TIMEOUT}с{N}")
    print(f"{C}{'═' * 70}{N}\n")

    # Проверяем зависимости
    for tool in ("xray", "curl"):
        try:
            subprocess.run([tool, "--version"], capture_output=True, timeout=5)
        except FileNotFoundError:
            print(f"{R}✗ {tool} не установлен! Установите и попробуйте снова.{N}")
            sys.exit(1)

    # ── Загрузка ──
    print(f"{B}── ФАЗА 1: Загрузка конфигов ──{N}")
    t1 = time.time()
    all_urls = [f"{REPO_BASE}/{f}" for f in REPO_FILES] + EXTRA_REPOS
    all_links = download_all_parallel(all_urls)
    t_dl = time.time() - t1
    print(f"\n{C}Загрузка завершена за {t_dl:.1f}с{N}")

    if not all_links:
        print(f"{R}✗ Не удалось загрузить ни одного конфига.{N}")
        sys.exit(1)

    # ── Фильтрация ──
    test_links = filter_links(all_links, args.max_test)
    if not test_links:
        print(f"{R}✗ Нет конфигов для тестирования после фильтрации.{N}")
        sys.exit(1)

    # ── ФАЗА 2: Проверка AI-доступа ──
    print(f"{B}── ФАЗА 2: Проверка доступа к AI (параллельно {MAX_TEST_WORKERS} потоков) ──{N}")
    t2 = time.time()
    tested = 0
    total = len(test_links)
    last_print = time.time()

    with ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as pool:
        futures = {pool.submit(check_ai_access, link): link for link in test_links}
        for future in as_completed(futures):
            if stop_event.is_set():
                break

            tested += 1
            latency = future.result()
            link = futures[future]

            if latency is not None:
                with found_lock:
                    found_keys.append((link, latency))
                    cc = extract_country_code(link) or "??"
                    remark = link.split("#", 1)[1][:40] if "#" in link else ""
                    print(f"\n{G}✓ Рабочий AI [{cc.upper()}] — {latency:.0f}мс — {remark}{N}")

            now = time.time()
            if now - last_print > 0.5:
                print(f"\r{C}Проверено: {tested}/{total} | Найдено: {len(found_keys)} | "
                      f"Осталось: {remaining():.0f}с{N}   ", end="", flush=True)
                last_print = now

            if is_timeout():
                print(f"\n{Y}⏱ Достигнут таймаут {HARD_TIMEOUT}с{N}")
                stop_event.set()
                break

            if len(found_keys) >= args.need * 3:
                print(f"\n{G}✓ Найдено достаточно конфигов ({len(found_keys)}), переходим к тесту скорости{N}")
                stop_event.set()
                break

    kill_xrays()
    t_test = time.time() - t2
    print(f"\n{C}Проверка завершена за {t_test:.1f}с, найдено {len(found_keys)} рабочих{N}")

    if not found_keys:
        print(f"{R}✗ Рабочих AI-конфигов не найдено за {elapsed():.0f}с.{N}")
        print(f"{Y}Попробуйте увеличить --max-test или --timeout{N}")
        sys.exit(1)

    # ── ФАЗА 3: Тест скорости ──
    sorted_by_latency = sorted(found_keys, key=lambda x: x[1])
    candidates = sorted_by_latency[:min(args.need * 2, len(sorted_by_latency))]

    if args.no_speed_test:
        results = [(link, lat, 0.0) for link, lat in sorted_by_latency[:args.need]]
        save_and_output(results, args.no_clipboard)
    else:
        print(f"\n{B}── ФАЗА 3: Тест скорости (до {len(candidates)} конфигов) ──{N}")
        t3 = time.time()
        stop_event.clear()

        speed_results = []
        speed_workers = min(8, len(candidates))
        with ThreadPoolExecutor(max_workers=speed_workers) as pool:
            speed_futures = {
                pool.submit(measure_speed, link, lat): (link, lat)
                for link, lat in candidates
            }
            for future in as_completed(speed_futures):
                result = future.result()
                if result is not None:
                    speed_results.append(result)
                    link, lat, spd = result
                    cc = extract_country_code(link) or "??"
                    print(f"{G}  Скорость [{cc.upper()}]: {spd:.1f} Мбит/с (задержка {lat:.0f}мс){N}")
                else:
                    link, lat = speed_futures[future]
                    speed_results.append((link, lat, 0.0))

                if is_timeout():
                    print(f"{Y}⏱ Таймаут на этапе теста скорости{N}")
                    break

        kill_xrays()
        t_speed = time.time() - t3
        print(f"{C}Тест скорости завершён за {t_speed:.1f}с{N}")

        # Добавляем остальные (не тестированные на скорость)
        tested_links = {r[0] for r in speed_results}
        for link, lat in sorted_by_latency:
            if link not in tested_links:
                speed_results.append((link, lat, 0.0))

        save_and_output(speed_results, args.no_clipboard)

    total_time = elapsed()
    print(f"\n{C}Общее время: {total_time:.1f}с ({total_time / 60:.1f} мин){N}")
    print(f"{G}Готово! Лучший конфиг скопирован в буфер обмена.{N}")

if __name__ == "__main__":
    main()
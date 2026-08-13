import os, sys, json, time, threading, tempfile, subprocess, signal, socket, base64, random, argparse, re, statistics
from urllib.request import urlopen, Request
from urllib.parse import parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import resource
    def _limit_fds():
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (min(hard, 4096), hard))
        except Exception:
            pass
except Exception:
    def _limit_fds():
        pass

# ==================== НАСТРОЙКИ ====================
REPO_ORIG = "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/main/githubmirror"
FILES_ORIG = [f"{i}.txt" for i in range(1, 27)]

EXTRA_REPOS = [
 "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
 "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt",
 "https://raw.githubusercontent.com/Romaxa55/MegaV_Public/main/subs/vless.txt",
 "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub.txt",
 "https://raw.githubusercontent.com/MhdiJafari/Free-V2ray-Config/main/All_Configs_Sub.txt"
]

NEED = 1
TIMEOUT_DL = 25
TIMEOUT_TEST = 6
XRAY_PORT_BASE = 10900
MAX_DL_WORKERS = 16
MAX_TEST_WORKERS = 80

# Глобальный тайм-бюджет работы скрипта (сек). Скрипт гарантированно
# завершается не позже этого времени и выдаёт лучшее из найденного.
MAX_TIME = 180
# Сколько секунд из бюджета зарезервировать под повторную проверку (re-probe) кандидатов.
REPROBE_BUDGET = 40
# Сколько раз прогонять каждого кандидата при re-probe.
REPROBE_TIMES = 3
# Сколько лучших по latency кандидатов отправить на re-probe.
REPROBE_TOP = 8

HIDDIFY_APPIMAGE = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/Hiddify-Linux-x64-AppImage.AppImage"
LAUNCH_HIDDIFY = True

PREFERRED_COUNTRIES = ["nl", "gb", "de", "fr", "pl", "lt", "lv", "ee", "se", "no", "fi", "at", "ch", "be", "dk", "it", "es", "us", "cz", "ro", "fi"]
FALLBACK_TO_ANY = True
EXCLUDE_COUNTRIES = ["ru", "by", "kz"]

# Нейтральные сайты для замера latency и базовой связности (не зависят от VPN).
LATENCY_SITES = [
    "https://cp.cloudflare.com/generate_204",
    "https://www.gstatic.com/generate_204",
    "https://www.google.com/generate_204"
]

# Реальная проверка доступности ChatGPT / OpenAI. Достаточно, чтобы ответил
# хотя бы один из этих эндпоинтов (любой HTTP-код = мы дошли до инфры OpenAI,
# а не до RU-блокировки на уровне соединения).
CHATGPT_SITES = [
    "https://chatgpt.com/",
    "https://api.openai.com/v1/models"
]
CHATGPT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Маркеры страниц блокировки/заглушек — их наличие в теле = VPN не пускает.
BLOCK_MARKERS = [
    "access denied", "just a moment", "cf-chl", "verify you are human",
    "you are blocked", "your access has been", "unsupported_country",
    "attention required", "доступ ограничен", "enable javascript and cookies"
]

MAX_LATENCY = 2500

LOGS_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/logs"

C = "\033[0;36m"; G = "\033[0;32m"; R = "\033[0;31m"; Y = "\033[1;33m"; N = "\033[0m"

found_lock = threading.Lock()
found_keys = []          # список кортежей (link, latency) — только прошедшие ChatGPT
stop_event = threading.Event()
deadline = 0.0
xray_pids = []
xray_lock = threading.Lock()
port_lock = threading.Lock()
NO_CLIPBOARD = False


def kill_xrays():
    with xray_lock:
        for p in xray_pids[:]:
            try:
                os.kill(p, 9)
            except Exception:
                pass
        xray_pids.clear()


def get_port():
    with port_lock:
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", 0))
                    return s.getsockname()[1]
            except OSError:
                time.sleep(0.01)


def wait_for_port(port, timeout=2.5):
    start = time.time()
    while time.time() - start < timeout:
        if stop_event.is_set():
            return False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                return True
        time.sleep(0.05)
    return False


def time_left():
    return max(0.0, deadline - time.time())


# ==================== ЗАГРУЗКА СПИСКОВ ====================
def download_one(url):
    safe = url.split("/")[-1].split("?")[0] or "list"
    tmp = os.path.join(LOGS_DIR, f".dl_{safe}")
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["curl", "-sSL", "--retry", "2", "--retry-delay", "1",
                 "--connect-timeout", "10", "-m", str(TIMEOUT_DL),
                 "-A", "Mozilla/5.0", "-o", tmp, url],
                capture_output=True, timeout=TIMEOUT_DL + 15)
            if r.returncode == 0 and os.path.getsize(tmp) > 0:
                with open(tmp, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read()
                return data
        except Exception:
            pass
    return None


def download_file(url):
    data = download_one(url)
    if data is None:
        print(f"{R}Ошибка загрузки {url}{N}")
        return []
    links = [line.strip() for line in data.splitlines() if line.strip() and not line.startswith('#')]
    print(f"{G}Загружено {len(links)} ссылок из {url.split('/')[-1][:50]}{N}")
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        safe = url.split("/")[-1].split("?")[0] or "list"
        with open(os.path.join(LOGS_DIR, f"raw_{safe}"), "w", encoding="utf-8") as f:
            f.write(data)
    except Exception as e:
        print(f"{Y}⚠ Не удалось сохранить сырой список {url}: {e}{N}")
    finally:
        try:
            os.unlink(os.path.join(LOGS_DIR, f".dl_{safe}"))
        except Exception:
            pass
    return links


def download_all_parallel(urls):
    results = []
    with ThreadPoolExecutor(max_workers=MAX_DL_WORKERS) as pool:
        futs = {pool.submit(download_file, u): u for u in urls}
        for fut in as_completed(futs):
            results.extend(fut.result())
    return results


# ==================== ПАРСИНГ КОНФИГОВ ====================
def b64_decode(s):
    s = s.replace("-", "+").replace("_", "/")
    pad = (4 - len(s) % 4) % 4
    s += "=" * pad
    try:
        return base64.b64decode(s).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _normalize_country(cc):
    ali = {"uk": "gb", "usa": "us", "eng": "gb", "deu": "de", "fra": "fr",
           "nld": "nl", "rus": "ru", "blr": "by", "kaz": "kz"}
    return ali.get(cc, cc)


def extract_country(link):
    if "#" in link:
        remark = link.split("#", 1)[1].lower()
    else:
        remark = ""
    host_part = link.split("@", 1)[-1].lower()
    text = f"{remark} {host_part}"
    tokens = re.findall(r"[\[\(_\-\s\.\/]([a-z]{2})[\]\)_\-\s\.\/]", text)
    for t in tokens:
        return _normalize_country(t)
    m = re.search(r"\b([a-z]{2})\b", remark)
    if m:
        return _normalize_country(m.group(1))
    return ""


def link_contains_country(link, countries):
    if not countries:
        return True
    cc = extract_country(link)
    if cc and cc in countries:
        return True
    lower = link.lower()
    for c in countries:
        if f".{c}." in lower or f"-{c}-" in lower or f"[{c}]" in lower:
            return True
    return False


def link_excluded(link, countries):
    if not countries:
        return False
    cc = extract_country(link)
    return cc in countries


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
                "serverName": sni, "fingerprint": fp,
                "publicKey": params.get("pbk", [""])[0],
                "shortId": params.get("sid", [""])[0],
                "spiderX": params.get("spx", ["/"])[0]
            }
        elif sec == "tls":
            stream["security"] = "tls"
            stream["tlsSettings"] = {"serverName": sni or addr, "fingerprint": fp,
                                     "allowInsecure": False}

        if net == "ws":
            path = params.get("path", ["/"])[0]
            host = params.get("host", [""])[0] or sni
            headers = {"Host": host} if host else {}
            stream["wsSettings"] = {"path": path, "headers": headers}
        elif net == "grpc":
            stream["grpcSettings"] = {"serviceName": params.get("serviceName", [""])[0],
                                      "multiMode": params.get("mode", [""])[0] == "multi"}
        elif net == "h2":
            stream["httpSettings"] = {"path": params.get("path", ["/"])[0],
                                      "host": params.get("host", [addr])[0].split(",")}

        return {
            "protocol": "vless",
            "settings": {"vnext": [{"address": addr, "port": port,
                                    "users": [{"id": uuid_part, "encryption": "none"}]}]},
            "streamSettings": stream
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
            stream["tlsSettings"] = {"serverName": decoded.get("sni") or decoded.get("add"),
                                     "fingerprint": decoded.get("fp", "chrome"),
                                     "allowInsecure": False}
        if net == "ws":
            stream["wsSettings"] = {"path": decoded.get("path", "/"),
                                    "headers": {"Host": decoded.get("host", "")}}
        elif net == "grpc":
            stream["grpcSettings"] = {"serviceName": decoded.get("path", "")}
        return {
            "protocol": "vmess",
            "settings": {"vnext": [{"address": decoded["add"], "port": int(decoded["port"]),
                                    "users": [{"id": decoded["id"],
                                               "alterId": int(decoded.get("aid", 0)),
                                               "security": decoded.get("scy", "auto")}]}]},
            "streamSettings": stream
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
            stream["wsSettings"] = {"path": params.get("path", ["/"])[0],
                                    "headers": {"Host": params.get("host", [""])[0]}}
        return {"protocol": "trojan",
                "settings": {"servers": [{"address": addr, "port": port, "password": pw}]},
                "streamSettings": stream}
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
        ob = {"protocol": "hysteria2",
              "settings": {"servers": [{"address": addr, "port": port, "password": pw}]},
              "streamSettings": {"network": "hysteria2", "security": "tls",
                                 "tlsSettings": {"serverName": sni, "allowInsecure": False}}}
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


# ==================== ЗАПУСК XRAY И ТЕСТЫ ====================
def run_xray(outbound):
    """Запускает xray с одним outbound, возвращает (proc, port) или (None, None)."""
    port = get_port()
    config = {
        "log": {"loglevel": "error"},
        "dns": {
            "servers": [
                {"address": "https://1.1.1.1/dns-query", "domains": ["geosite:geolocation-!cn"], "expectIPs": ["geoip:!cn"]},
                "1.1.1.1",
                "8.8.8.8"
            ],
            "queryStrategy": "UseIP"
        },
        "inbounds": [{"listen": "127.0.0.1", "port": port, "protocol": "socks",
                      "settings": {"auth": "noauth", "udp": True}}],
        "outbounds": [outbound, {"protocol": "freedom", "tag": "direct",
                                 "settings": {"domainStrategy": "UseIP"}}],
        "routing": {"rules": [{"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"}]}
    }
    tmpf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(config, tmpf)
    tmpf.close()

    proc = None
    try:
        proc = subprocess.Popen(["xray", "run", "-config", tmpf.name],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with xray_lock:
            xray_pids.append(proc.pid)
        if not wait_for_port(port) or proc.poll() is not None:
            return None, None
        return proc, port
    finally:
        try:
            os.unlink(tmpf.name)
        except Exception:
            pass


def curl_via(port, site, timeout=TIMEOUT_TEST, ua=None):
    cmd = ["curl", "-x", f"socks5h://127.0.0.1:{port}", "-s", "-o", "/dev/null",
           "-w", "%{http_code}", "--connect-timeout", str(timeout),
           "--max-time", str(timeout), site]
    if ua:
        cmd += ["-A", ua]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 3)
    return r


def probe_site(port, site, timeout=TIMEOUT_TEST, ua=None, body=False):
    """Возвращает (http_code, body). body читается из временного файла."""
    tmpb = os.path.join(tempfile.gettempdir(), "_vpntest_body")
    cmd = ["curl", "-x", f"socks5h://127.0.0.1:{port}", "-s", "-o", tmpb,
           "-w", "%{http_code}", "--connect-timeout", str(timeout),
           "--max-time", str(timeout), site]
    if ua:
        cmd += ["-A", ua]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 3)
    code = r.stdout.strip()
    if not body:
        return code, ""
    try:
        with open(tmpb, "r", encoding="utf-8", errors="ignore") as f:
            b = f.read()
    except Exception:
        b = ""
    return code, b


def measure_latency(port):
    """Замер latency по нейтральным сайтам. Возвращает (avg_ms, ok_count)."""
    latencies = []
    ok = 0
    for site in LATENCY_SITES:
        start = time.time()
        r = curl_via(port, site)
        elapsed = (time.time() - start) * 1000
        code = r.stdout.strip()
        if r.returncode == 0 and code in ("200", "204", "301", "302"):
            ok += 1
            latencies.append(elapsed)
        elif r.returncode == 0 and code:
            latencies.append(elapsed + 500)
    if not latencies:
        return None, 0
    return sum(latencies) / len(latencies), ok


def chatgpt_reachable(port):
    """True, только если OpenAI РЕАЛЬНО отвечает (не блокирует).

    Основной признак: api.openai.com/v1/models отвечает 200/401 с JSON.
    Это однозначно значит, что IP не заблокирован OpenAI (заблокированные
    получают 403 / Cloudflare / обрыв соединения).
    Запасной: реальная страница chatgpt.com без маркеров заглушки.
    """
    if stop_event.is_set():
        return False

    # 1) API OpenAI — самый надёжный дискриминатор.
    code, body = probe_site(port, "https://api.openai.com/v1/models",
                            ua=CHATGPT_UA, body=True)
    low = body.lower()
    if code in ("200", "401") and ('"error"' in low or '"data"' in low):
        return True

    # 2) Запасной: страница ChatGPT, но только если это не заглушка.
    code, body = probe_site(port, "https://chatgpt.com/", ua=CHATGPT_UA, body=True)
    low = body.lower()
    if code == "200" and "chatgpt" in low and not any(m in low for m in BLOCK_MARKERS):
        return True

    return False


def check_key(link):
    """Возвращает (latency_ms, True), если конфиг рабочий И доступен ChatGPT, иначе None."""
    if stop_event.is_set() or time_left() <= 0:
        return None
    if not any(link.startswith(p) for p in ("vless://", "vmess://", "trojan://", "hysteria2://", "hy2://")):
        return None

    outbound = link_to_outbound(link)
    if not outbound:
        return None

    proc, port = run_xray(outbound)
    if proc is None or port is None:
        return None

    try:
        avg, ok = measure_latency(port)
        if avg is None or avg >= MAX_LATENCY:
            return None
        if not chatgpt_reachable(port):
            return None
        return (avg, True)
    except Exception:
        return None
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        with xray_lock:
            xray_pids[:] = [p for p in xray_pids if p != proc.pid]


def reprobe(link, times):
    """Повторный прогон кандидата. Возвращает (median_latency, chatgpt_ok_count)."""
    lats = []
    chat_ok = 0
    for _ in range(times):
        if stop_event.is_set() or time_left() <= 0:
            break
        res = check_key(link)
        if res is None:
            continue
        lats.append(res[0])
        chat_ok += 1
    if not lats:
        return None, 0
    return statistics.median(lats), chat_ok


# ==================== ВЫВОД / HIDDIFY ====================
def copy_to_clipboard(text):
    if NO_CLIPBOARD:
        return
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
            p.communicate(text)
            if p.returncode == 0:
                print(f"{G}✓ Скопировано в буфер{N}")
                return
        except FileNotFoundError:
            continue
    print(f"{Y}⚠ Не удалось скопировать автоматически{N}")


def launch_hiddify(best):
    try:
        sub_file = os.path.join(tempfile.gettempdir(), "vpn_subscription.txt")
        with open(sub_file, "w", encoding="utf-8") as f:
            f.write("\n".join(best))
        print(f"{C}Запуск Hiddify...{N}")
        print(f"{C}Конфиги в буфере обмена и в файле: {sub_file}{N}")
        print(f"{C}В Hiddify: '+' → Import from Clipboard (или укажите файл подписки).{N}")
        subprocess.Popen([HIDDIFY_APPIMAGE])
    except Exception as e:
        print(f"{R}Не удалось запустить Hiddify: {e}{N}")


def process_results(best, alternatives):
    if not best:
        print(f"{R}Рабочий VPN с доступом к ChatGPT не найден за отведённое время.{N}")
        return

    data = "\n".join([best[0]] + alternatives)
    copy_to_clipboard(data)

    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(LOGS_DIR, f"selected_{ts}.txt"), "w", encoding="utf-8") as f:
            f.write(f"# BEST latency={best[1]:.0f}ms chatgpt=ok\n{best[0]}\n")
            for i, link in enumerate(alternatives):
                f.write(f"# alt {i+1}\n{link}\n")
        print(f"{C}Отобранные конфиги сохранены в logs/selected_{ts}.txt{N}")
    except Exception as e:
        print(f"{Y}⚠ Не удалось сохранить отобранные конфиги: {e}{N}")

    print(f"\n{G}✅ ЛУЧШИЙ VPN (доступен ChatGPT):{N}")
    print(f"{G}{best[0]}{N}  {G}← медиана latency {best[1]:.0f}мс{N}")
    if alternatives:
        print(f"\n{Y}Запасные (по скорости):{N}")
        for link in alternatives:
            print(f"{Y}{link}{N}")

    if LAUNCH_HIDDIFY:
        launch_hiddify([best[0]] + alternatives)


def signal_handler(sig, frame):
    print(f"\n{R}Прерывание...{N}")
    stop_event.set()
    kill_xrays()
    sys.exit(0)


# ==================== ГЛАВНАЯ ====================
def main():
    global NEED, LAUNCH_HIDDIFY, PREFERRED_COUNTRIES, MAX_TIME, deadline, NO_CLIPBOARD
    parser = argparse.ArgumentParser(description="Поиск ЛУЧШЕГО VPN с доступом к ChatGPT (VLESS/VMess/Trojan/Hysteria2).")
    parser.add_argument("--need", type=int, default=NEED, help="Сколько ключей выдать (1 = только лучший + запасные, default: %(default)s)")
    parser.add_argument("--max-test", type=int, default=2000, help="Макс. число тестируемых конфигов")
    parser.add_argument("--max-time", type=int, default=MAX_TIME, help="Общий тайм-бюджет в секундах (default: %(default)s)")
    parser.add_argument("--reprobe", type=int, default=REPROBE_TIMES, help="Сколько раз прогонять кандидата (default: %(default)s)")
    parser.add_argument("--countries", default=",".join(PREFERRED_COUNTRIES),
                        help="Приоритетные страны (через запятую, 2-буквенные коды)")
    parser.add_argument("--no-hiddify", action="store_true", help="Не запускать Hiddify")
    parser.add_argument("--no-clipboard", action="store_true", help="Не копировать в буфер обмена")
    args = parser.parse_args()

    NEED = max(1, args.need)
    LAUNCH_HIDDIFY = not args.no_hiddify
    PREFERRED_COUNTRIES = [c.strip().lower() for c in args.countries.split(",") if c.strip()]
    MAX_TIME = max(20, args.max_time)
    reprobe_times = max(1, args.reprobe)
    NO_CLIPBOARD = args.no_clipboard

    _limit_fds()
    signal.signal(signal.SIGINT, signal_handler)
    os.makedirs(LOGS_DIR, exist_ok=True)

    deadline = time.time() + MAX_TIME
    # Бюджет на сканирование: оставляем запас на re-probe лучших кандидатов.
    scan_deadline = deadline - REPROBE_BUDGET

    print(f"\n{C}{'=' * 70}{N}")
    print(f"{C}Поиск ЛУЧШЕГО VPN с доступом к ChatGPT{N}")
    print(f"{C}Тайм-бюджет: {MAX_TIME}с | re-probe: {reprobe_times}х | нужно выдать: {NEED}{N}")
    print(f"{C}{'=' * 70}{N}")

    for tool in ("xray", "curl"):
        try:
            subprocess.run([tool, "--version"], capture_output=True, timeout=5)
        except FileNotFoundError:
            print(f"{R}{tool} не установлен!{N}")
            sys.exit(1)

    all_links = []
    all_links.extend(download_all_parallel([f"{REPO_ORIG}/{f}" for f in FILES_ORIG]))
    all_links.extend(download_all_parallel(EXTRA_REPOS))

    seen = set()
    unique_links = []
    for l in all_links:
        if l not in seen:
            seen.add(l)
            unique_links.append(l)
    all_links = unique_links

    print(f"\nВсего собрано {len(all_links)} уникальных конфигов.")

    preferred = [l for l in all_links if link_contains_country(l, PREFERRED_COUNTRIES)]
    preferred = [l for l in preferred if not link_excluded(l, EXCLUDE_COUNTRIES)]
    test_links = preferred
    if not test_links:
        if FALLBACK_TO_ANY:
            test_links = [l for l in all_links if not link_excluded(l, EXCLUDE_COUNTRIES)]
            if len(test_links) > 400:
                test_links = random.sample(test_links, 400)
            print(f"{Y}Приоритетные конфиги не найдены, фоллбэк на общий список ({len(test_links)}).{N}")
        else:
            print(f"{R}Приоритетных конфигов не найдено.{N}")

    if len(test_links) > args.max_test:
        test_links = random.sample(test_links, args.max_test)
        print(f"{Y}Случайная выборка для теста: {len(test_links)}{N}")

    print(f"Конфигов для теста: {len(test_links)}\n")

    # ----- ФАЗА 1: сканирование -----
    tested = 0
    total = len(test_links)
    with ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as pool:
        futures = {pool.submit(check_key, link): link for link in test_links}
        for future in as_completed(futures):
            if stop_event.is_set() or time.time() >= scan_deadline:
                break
            tested += 1
            res = future.result()
            link = futures[future]
            if res is not None:
                with found_lock:
                    found_keys.append((link, res[0]))
                    print(f"\n{G}✓ ChatGPT доступен ({res[0]:.0f}мс) — {link[:60]}...{N}")
            print(f"\r{C}Сканирование: {tested}/{total} | Найдено с ChatGPT: {len(found_keys)} | осталось ~{int(time_left())}с{N}   ",
                  end="", flush=True)

    kill_xrays()

    if not found_keys:
        process_results(None, [])
        print(f"\n{R}Готово (ничего не найдено).{N}")
        return

    # ----- ФАЗА 2: re-probe лучших кандидатов -----
    print(f"\n\n{C}Найдено {len(found_keys)} кандидатов. Повторная проверка лучших...{N}")
    candidates = sorted(found_keys, key=lambda x: x[1])[:REPROBE_TOP]
    probed = []  # (link, median_latency, chat_ok)
    for link, lat in candidates:
        if stop_event.is_set() or time.time() >= deadline:
            break
        med, ok = reprobe(link, reprobe_times)
        if med is None:
            continue
        probed.append((link, med, ok))
        print(f"{G}  {link[:55]}... медиана {med:.0f}мс, ChatGPT {ok}/{reprobe_times}{N}")

    kill_xrays()

    # Выбираем лучшего: максимум успешных ChatGPT-прогонов, затем минимум latency.
    if not probed:
        # fallback: берём самого быстрого из первой фазы
        best = min(found_keys, key=lambda x: x[1])
        alternatives = [k[0] for k in sorted(found_keys, key=lambda x: x[1]) if k[0] != best[0]][:NEED - 1]
        process_results(best, alternatives)
        print(f"\n{G}Готово!{N}")
        return

    probed.sort(key=lambda x: (-x[2], x[1]))
    best = probed[0]
    best_entry = (best[0], best[1])
    alternatives = [p[0] for p in probed[1:] if p[0] != best[0]][:NEED - 1]

    process_results(best_entry, alternatives)
    print(f"\n{G}Готово!{N}")


if __name__ == "__main__":
    main()

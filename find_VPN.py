#!/usr/bin/env python3
import os, sys, json, time, threading, tempfile, subprocess, signal, socket, base64, random, argparse, re, statistics, functools
from urllib.request import urlopen, Request
from urllib.parse import parse_qs, quote
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
    "https://raw.githubusercontent.com/MhdiJafari/Free-V2ray-Config/main/All_Configs_Sub.txt",
]

NEED = 1
TIMEOUT_DL = 25
TIMEOUT_TEST = 6
XRAY_PORT_BASE = 10900
MAX_DL_WORKERS = 16
MAX_TEST_WORKERS = 80

MAX_TIME = 180
REPROBE_BUDGET = 40
REPROBE_TIMES = 3
REPROBE_TOP = 8

HIDDIFY_APPIMAGE = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/Hiddify-Linux-x64-AppImage.AppImage"
LAUNCH_HIDDIFY = True
PREFERRED_COUNTRIES = ["nl", "gb", "de", "fr", "pl", "lt", "lv", "ee", "se", "no", "fi", "at", "ch", "be", "dk", "it", "es", "us", "cz", "ro"]
FALLBACK_TO_ANY = True
EXCLUDE_COUNTRIES = ["ru", "by", "kz"]

LATENCY_SITES = [
    "https://cp.cloudflare.com/generate_204",
    "https://www.gstatic.com/generate_204",
    "https://www.google.com/generate_204",
]

CHATGPT_SITES = [
    "https://chatgpt.com/",
    "https://api.openai.com/v1/models",
]
CHATGPT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
BLOCK_MARKERS = [
    "access denied", "just a moment", "cf-chl", "verify you are human",
    "you are blocked", "your access has been", "unsupported_country",
    "attention required", "доступ ограничен", "enable javascript and cookies",
]

# ==================== ПРОВЕРКА GEMINI ====================
TARGET = "gemini"   # что проверяем как критерий "VPN работает"
GEMINI_SITE = "https://gemini.google.com/"
GEMINI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
GEMINI_BLOCK_MARKERS = [
    "not available in your country", "isn't available in your country",
    "unavailable in your country", "not supported in your country",
    "your country isn", "is not available in your region",
    "gemini is not available", "this service is not available in your country",
]

MAX_LATENCY = 2500
LOGS_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/logs"

PROTOCOL_PRIORITY = {"vless": 0, "trojan": 1, "hysteria2": 2, "hy2": 2, "vmess": 3}
MAX_PER_SERVER = 4

TCP_PRE_TIMEOUT = 2.5
CACHE_FILE = os.path.join(LOGS_DIR, "cache.json")
CACHE_TTL_GOOD = 24 * 3600
CACHE_TTL_DEAD = 6 * 3600

SPEED_BYTES = 4000000
SPEED_TIMEOUT = 7

# ==================== ПОСТОЯННЫЙ VPN ====================
RUN_BEST = True
RUN_PORT = 10999
RUN_MONITOR = True
MONITOR_INTERVAL = 45
RUNNING_PROC = None

# ==================== ЦВЕТА ====================
C = "\033[0;36m"; G = "\033[0;32m"; R = "\033[0;31m"; Y = "\033[1;33m"; N = "\033[0m"

# ==================== ГЛОБАЛЬНОЕ СОСТОЯНИЕ ====================
found_lock = threading.Lock()
found_keys = []
stop_event = threading.Event()
deadline = 0.0
xray_pids = []
xray_lock = threading.Lock()
port_lock = threading.Lock()
NO_CLIPBOARD = False

dns_cache = {}
dns_lock = threading.Lock()
tcp_cache = {}
server_lock = threading.Lock()
persist_cache = {}
cache_dirty = False
run_server_ok = set()
run_server_dead = set()
run_server_blocked = set()


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
                capture_output=True, timeout=TIMEOUT_DL + 15
            )
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
        params = parse_qs(query.split("#", 1)[0])
        net = params.get("type", ["tcp"])[0]
        sni = params.get("sni", [""])[0] or params.get("host", [""])[0] or addr
        fp = params.get("fp", ["chrome"])[0]
        sec = params.get("security", ["none"])[0]
        stream = {"network": net, "security": "none"}
        if sec == "reality":
            stream["security"] = "reality"
            stream["realitySettings"] = {
                "serverName": sni, "fingerprint": fp,
                "publicKey": params.get("pbk", [""])[0],
                "shortId": params.get("sid", [""])[0],
                "spiderX": params.get("spx", [""])[0],
            }
        elif sec == "tls":
            stream["security"] = "tls"
            stream["tlsSettings"] = {"serverName": sni, "fingerprint": fp}
        if net == "ws":
            stream["wsSettings"] = {
                "path": params.get("path", ["/"])[0],
                "headers": {"Host": params.get("host", [addr])[0]}
            }
        elif net == "grpc":
            stream["grpcSettings"] = {"serviceName": params.get("serviceName", [""])[0]}
        elif net == "http":
            stream["httpSettings"] = {
                "path": params.get("path", ["/"])[0],
                "host": params.get("host", [addr])[0].split(",")
            }
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
        decoded = json.loads(b64_decode(link[len("vmess://"):].split("#", 1)[0]))
        net = decoded.get("net", "tcp")
        stream = {"network": net}
        if decoded.get("tls") == "tls":
            stream["security"] = "tls"
            stream["tlsSettings"] = {"serverName": decoded.get("sni") or decoded.get("add"),
                                     "fingerprint": "chrome"}
        if net == "ws":
            stream["wsSettings"] = {"path": decoded.get("path", "/"),
                                    "headers": {"Host": decoded.get("host", decoded.get("add"))}}
        return {
            "protocol": "vmess",
            "settings": {"vnext": [{"address": decoded.get("add"), "port": int(decoded.get("port", 443)),
                                     "users": [{"id": decoded.get("id"), "alterId": int(decoded.get("aid", 0)),
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
        params = parse_qs(query.split("#", 1)[0])
        sni = params.get("sni", [""])[0] or params.get("host", [""])[0] or addr
        net = params.get("type", ["tcp"])[0]
        stream = {"network": net, "security": "tls",
                  "tlsSettings": {"serverName": sni, "allowInsecure": False}}
        if net == "ws":
            stream["wsSettings"] = {"path": params.get("path", ["/"])[0],
                                    "headers": {"Host": params.get("host", [""])[0]}}
        return {
            "protocol": "trojan",
            "settings": {"servers": [{"address": addr, "port": port, "password": pw}]},
            "streamSettings": stream
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
        q = parse_qs(query.split("#", 1)[0])
        sni = q.get("sni", [""])[0] or addr
        ob = {
            "protocol": "hysteria2",
            "settings": {"servers": [{"address": addr, "port": port, "password": pw}]},
            "streamSettings": {"network": "hysteria2", "security": "tls",
                               "tlsSettings": {"serverName": sni, "allowInsecure": False}}
        }
        if q.get("obfs"):
            ob["streamSettings"]["sockopt"] = {}
        return ob
    except Exception:
        return None


@functools.lru_cache(maxsize=30000)
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


def link_server(link):
    ob = link_to_outbound(link)
    if not ob:
        return None
    proto = ob.get("protocol", "")
    if proto in ("vless", "vmess"):
        v = ob.get("settings", {}).get("vnext", [{}])
        if v:
            return v[0].get("address"), v[0].get("port"), proto
    elif proto in ("trojan", "hysteria2", "hy2"):
        s = ob.get("settings", {}).get("servers", [{}])
        if s:
            return s[0].get("address"), s[0].get("port"), proto
    return None


def _proto_of(link):
    if link.startswith("vless://"):
        return "vless"
    if link.startswith("vmess://"):
        return "vmess"
    if link.startswith("trojan://"):
        return "trojan"
    if link.startswith(("hysteria2://", "hy2://")):
        return "hysteria2"
    return "?"


def order_key(link):
    skey = link_server(link)
    cached = cached_server_state(*skey[:2]) if skey else None
    proto = _proto_of(link)
    pr = PROTOCOL_PRIORITY.get(proto, 9)
    if cached == "good":
        return (0, pr)
    return (1, pr)


def server_ip(link):
    skey = link_server(link)
    if not skey:
        return None, None
    addr = skey[0]
    try:
        socket.inet_aton(addr)
        return addr, None
    except OSError:
        pass
    with dns_lock:
        if addr in dns_cache:
            return dns_cache[addr], addr
    try:
        ip = socket.gethostbyname(addr)
        with dns_lock:
            dns_cache[addr] = ip
        return ip, addr
    except Exception:
        return None, addr


# ==================== TCP / КЭШ ====================

def tcp_alive(addr, port, timeout=TCP_PRE_TIMEOUT):
    try:
        with socket.create_connection((addr, port), timeout=timeout):
            return True
    except Exception:
        return False


def cached_server_state(addr, port):
    info = persist_cache.get(f"{addr}:{port}")
    if not info:
        return None
    age = time.time() - info.get("ts", 0)
    if info.get("status") == "good" and age < CACHE_TTL_GOOD:
        return "good"
    if info.get("status") in ("dead", "blocked") and age < CACHE_TTL_DEAD:
        return info["status"]
    return None


def tcp_alive_cached(addr, port):
    key = (addr, port)
    if key in tcp_cache:
        return tcp_cache[key]
    st = cached_server_state(addr, port)
    if st == "dead":
        tcp_cache[key] = False
        return False
    if st in ("good", "blocked"):
        tcp_cache[key] = True
        return True
    alive = tcp_alive(addr, port)
    tcp_cache[key] = alive
    if not alive:
        persist_server(key, "dead")
    return alive


def persist_server(key, status, lat=None):
    global cache_dirty
    with server_lock:
        k = f"{key[0]}:{key[1]}"
        info = persist_cache.get(k, {})
        info["status"] = status
        info["ts"] = time.time()
        if lat is not None:
            info["lat"] = lat
        persist_cache[k] = info
        cache_dirty = True


def load_cache():
    global persist_cache
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            persist_cache = data.get("servers", {}) or {}
    except Exception:
        persist_cache = {}


def save_cache():
    global cache_dirty
    if not cache_dirty:
        return
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"servers": persist_cache}, f, ensure_ascii=False)
        cache_dirty = False
    except Exception:
        pass


def geo_lookup(ips):
    result = {}
    ips = [ip for ip in ips if ip]
    if not ips:
        return result
    for i in range(0, len(ips), 100):
        chunk = ips[i:i + 100]
        try:
            req = Request("http://ip-api.com/batch?fields=status,query,countryCode",
                          data=json.dumps(chunk).encode("utf-8"),
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))
            for item in data:
                if item.get("status") == "success":
                    result[item.get("query")] = item.get("countryCode", "")
        except Exception:
            pass
    return result


# ==================== ЗАПУСК XRAY И ТЕСТЫ ====================

def run_xray(outbound):
    port = get_port()
    config = {
        "log": {"loglevel": "error"},
        "dns": {"servers": [
            {"address": "https://1.1.1.1/dns-query", "domains": ["geosite:geolocation-!cn"], "expectIPs": ["geoip:!cn"]},
            "1.1.1.1", "8.8.8.8"
        ], "queryStrategy": "UseIP"},
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
    if stop_event.is_set():
        return False
    code, body = probe_site(port, "https://api.openai.com/v1/models",
                            ua=CHATGPT_UA, body=True)
    low = body.lower()
    if code in ("200", "401"):
        if '"data"' in low:
            return True
        if '"error"' in low:
            if any(m in low for m in ("unsupported_country", "country_not_supported",
                                       "unsupported_country_code", "access_denied")):
                return False
            if any(m in low for m in ("invalid_api_key", "invalid_request_error",
                                       "requests exceed", "insufficient_quota")):
                return True
    code, body = probe_site(port, "https://chatgpt.com/", ua=CHATGPT_UA, body=True)
    low = body.lower()
    if code == "200" and "chatgpt" in low and not any(m in low for m in BLOCK_MARKERS):
        return True
    return False


def gemini_reachable(port):
    if stop_event.is_set():
        return False
    code, body = probe_site(port, GEMINI_SITE, timeout=TIMEOUT_TEST, ua=GEMINI_UA, body=True)
    low = body.lower()
    if code in ("301", "302", "303", "307", "308"):
        return True
    if code in ("200", "401"):
        if any(m in low for m in GEMINI_BLOCK_MARKERS):
            return False
        if "gemini" in low:
            return True
        if "google" in low and '"cf"' not in low and not any(m in low for m in BLOCK_MARKERS):
            return True
    return False


def target_reachable(port):
    if TARGET == "chatgpt":
        return chatgpt_reachable(port)
    return gemini_reachable(port)


def check_key(link):
    if stop_event.is_set() or time_left() <= 0:
        return None
    if not any(link.startswith(p) for p in ("vless://", "vmess://", "trojan://", "hysteria2://", "hy2://")):
        return None
    outbound = link_to_outbound(link)
    if not outbound:
        return None
    skey = link_server(link)
    if skey is None:
        return None
    addr, port, proto = skey
    sid = (addr, port)
    with server_lock:
        if sid in run_server_dead or sid in run_server_blocked:
            return None
    server_ok = sid in run_server_ok
    if cached_server_state(addr, port) in ("dead", "blocked"):
        return None
    if proto not in ("hysteria2", "hy2"):
        if not tcp_alive_cached(addr, port):
            with server_lock:
                run_server_dead.add(sid)
            return None
    proc, lport = run_xray(outbound)
    if proc is None or lport is None:
        return None
    try:
        avg, ok = measure_latency(lport)
        if avg is None or avg >= MAX_LATENCY:
            return None
        if server_ok:
            return (avg, True)
        if not target_reachable(lport):
            with server_lock:
                run_server_blocked.add(sid)
            persist_server(sid, "blocked", avg)
            return None
        with server_lock:
            run_server_ok.add(sid)
        persist_server(sid, "good", avg)
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
        return None, 0, 0.0
    sd = statistics.pstdev(lats) if len(lats) > 1 else 0.0
    return statistics.median(lats), chat_ok, sd


def measure_speed(port, timeout=SPEED_TIMEOUT):
    site = f"https://speed.cloudflare.com/__down?bytes={SPEED_BYTES}"
    cmd = ["curl", "-x", f"socks5h://127.0.0.1:{port}", "-s", "-o", "/dev/null",
           "-w", "%{speed_download}", "--connect-timeout", str(min(timeout, 4)),
           "--max-time", str(timeout), site]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        v = float(r.stdout.strip())
        if v > 0:
            return v / 1048576.0
    except Exception:
        pass
    return None


def probe_with_speed(link, timeout=SPEED_TIMEOUT):
    outbound = link_to_outbound(link)
    if not outbound:
        return None
    proc, port = run_xray(outbound)
    if proc is None or port is None:
        return None
    try:
        avg, ok = measure_latency(port)
        if avg is None:
            return None
        return (avg, measure_speed(port, timeout=timeout))
    except Exception:
        return None
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        with xray_lock:
            xray_pids[:] = [p for p in xray_pids if p != proc.pid]


def probe_candidates(candidates, probed_map, times):
    top = sorted(candidates, key=lambda x: x[1])[:REPROBE_TOP]
    for link, lat in top:
        if stop_event.is_set() or time_left() <= 5:
            break
        if link in probed_map:
            continue
        med, ok, sd = reprobe(link, times)
        if med is None:
            continue
        probed_map[link] = (med, ok, sd)
        print(f"{G} {link[:55]}... медиана {med:.0f}мс, {TARGET.upper()} {ok}/{times}{N}")


def scan_batch(links, until):
    tested_in_batch = set()
    if not links:
        return tested_in_batch
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as pool:
        futures = {pool.submit(check_key, l): l for l in links}
        for future in as_completed(futures):
            if stop_event.is_set() or time.time() >= until:
                break
            done += 1
            link = futures[future]
            tested_in_batch.add(link)
            res = future.result()
            if res is not None:
                with found_lock:
                    found_keys.append((link, res[0]))
                print(f"{G}✓ {TARGET.upper()} доступен ({res[0]:.0f}мс) — {link[:60]}...{N}")
            if not stop_event.is_set():
                print(f"\r{C}Сканирование: {done}/{len(links)} | Найдено с {TARGET.upper()}: {len(found_keys)} | осталось ~{int(time_left())}с{N} ",
                      end="", flush=True)
    return tested_in_batch


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


def sanitize_link(link):
    try:
        if "#" in link:
            pre, _, remark = link.partition("#")
            if remark:
                return f"{pre}#{quote(remark, safe='')}"
    except Exception:
        pass
    return link


def best_meta(e):
    lat, ok, sd, mbps, proto, country = e[1], e[2], e[3], e[4], e[5], e[6]
    s = f"latency={lat:.0f}ms chatgpt={ok} stddev={sd:.0f}"
    if mbps:
        s += f" speed={mbps:.1f}MB/s"
    s += f" proto={proto} country={country or '?'}"
    return s


def print_summary_row(e, rank):
    lat, ok, sd, mbps, proto, country = e[1], e[2], e[3], e[4], e[5], e[6]
    m = f"{mbps:.1f}MB/s" if mbps else "—"
    print(f"{G}{rank:<5} {lat:>6.0f}мс {m:<9} {proto:<10} {country or '?':<4} {e[0][:48]}{N}")


def pick_alternatives(entries, need):
    chosen = []
    seen_proto = set()
    for e in entries[1:]:
        if len(chosen) >= need:
            break
        if e[5] not in seen_proto:
            chosen.append(e)
            seen_proto.add(e[5])
    for e in entries[1:]:
        if len(chosen) >= need:
            break
        if e not in chosen:
            chosen.append(e)
    return chosen


# ==================== ПОСТОЯННЫЙ VPN ====================

def pick_run_port(preferred):
    for port in range(preferred, preferred + 50):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return get_port()


def stop_xray_proc(proc):
    if proc is None:
        return
    try:
        proc.kill()
    except Exception:
        pass
    with xray_lock:
        if proc.pid in xray_pids:
            xray_pids.remove(proc.pid)


def start_xray_persistent(outbound, port):
    config = {
        "log": {"loglevel": "error"},
        "dns": {"servers": [
            {"address": "https://1.1.1.1/dns-query", "domains": ["geosite:geolocation-!cn"], "expectIPs": ["geoip:!cn"]},
            "1.1.1.1", "8.8.8.8"
        ], "queryStrategy": "UseIP"},
        "inbounds": [{"listen": "127.0.0.1", "port": port, "protocol": "socks",
                      "settings": {"auth": "noauth", "udp": True}}],
        "outbounds": [outbound, {"protocol": "freedom", "tag": "direct",
                                  "settings": {"domainStrategy": "UseIP"}}],
        "routing": {"rules": [{"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"}]}
    }
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        cfg_path = os.path.join(LOGS_DIR, f"xray_persistent_{port}.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        proc = subprocess.Popen(
            ["xray", "run", "-config", cfg_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        with xray_lock:
            xray_pids.append(proc.pid)
        if not wait_for_port(port) or proc.poll() is not None:
            stop_xray_proc(proc)
            return None
        return proc
    except Exception as e:
        print(f"{R}Не удалось запустить постоянный xray: {e}{N}")
        return None


def try_start_working_link(link, port):
    outbound = link_to_outbound(link)
    if outbound is None:
        return None
    proc = start_xray_persistent(outbound, port)
    if proc is None:
        return None
    time.sleep(1)
    if not target_reachable(port):
        print(f"{Y}Ключ включён, но {TARGET.upper()} не открывается. Пропускаю.{N}")
        stop_xray_proc(proc)
        return None
    return proc


def run_best_persistent(final_entries):
    global RUNNING_PROC
    links = [e[0] for e in final_entries if e and e[0]]
    if not links:
        print(f"{R}Нет кандидатов для постоянного VPN.{N}")
        return
    port = pick_run_port(RUN_PORT)
    print(f"{C}Держим рабочий VPN на socks5h://127.0.0.1:{port}{N}")
    i = 0
    while not stop_event.is_set() and i < len(links):
        link = links[i]
        print(f"{C}Пробую включить VPN: {link[:70]}...{N}")
        proc = try_start_working_link(link, port)
        if proc is None:
            i += 1
            continue
        RUNNING_PROC = proc
        print(f"{G}✅ Рабочий VPN включён и {TARGET.upper()} открывается.{N}")
        print(f"{G}socks5h://127.0.0.1:{port}{N}")
        set_system_proxy(port)
        print(f"\nДля терминала:")
        print(f"export http_proxy=socks5h://127.0.0.1:{port}")
        print(f"export https_proxy=socks5h://127.0.0.1:{port}")
        print(f"export all_proxy=socks5h://127.0.0.1:{port}\n")
        if not RUN_MONITOR:
            return
        while not stop_event.is_set():
            time.sleep(MONITOR_INTERVAL)
            if proc.poll() is not None:
                print(f"{Y}xray умер. Переключаюсь на следующий ключ.{N}")
                stop_xray_proc(proc)
                RUNNING_PROC = None
                clear_system_proxy()
                i += 1
                break
            if not target_reachable(port):
                print(f"{Y}VPN включён, но {TARGET.upper()} перестал открываться. Переключаюсь.{N}")
                stop_xray_proc(proc)
                RUNNING_PROC = None
                clear_system_proxy()
                i += 1
                break
    print(f"{R}Не удалось оставить рабочий VPN.{N}")
    clear_system_proxy()


# ==================== СИСТЕМНЫЙ ПРОКСИ (чтобы любой браузер ходил через VPN) ====================

SYSTEM_PROXY = True


def _gset(*args):
    try:
        subprocess.run(["gsettings", *args], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def set_system_proxy(port):
    if not SYSTEM_PROXY:
        return
    ok = _gset("set", "org.gnome.system.proxy", "mode", "manual")
    if not ok:
        print(f"{Y}⚠ gsettings/GNOME недоступен — системный прокси не прописан. "
              f"Браузер настраивайте вручную на socks5h://127.0.0.1:{port}{N}")
        return
    _gset("set", "org.gnome.system.proxy.socks", "host", "127.0.0.1")
    _gset("set", "org.gnome.system.proxy.socks", "port", str(port))
    print(f"{G}✓ Системный прокси GNOME → socks5h://127.0.0.1:{port} "
          f"(браузеры Chromium/Chrome работают сразу){N}")


def clear_system_proxy():
    if not SYSTEM_PROXY:
        return
    _gset("set", "org.gnome.system.proxy", "mode", "none")
    print(f"{C}Системный прокси GNOME сброшен.{N}")


# ==================== ОБРАБОТКА РЕЗУЛЬТАТОВ ====================

def process_results(final_entries, need=1):
    if not final_entries:
        print(f"{R}Рабочий VPN с доступом к {TARGET.upper()} не найден за отведённое время.{N}")
        return
    best = final_entries[0]
    alternates = pick_alternatives(final_entries, max(0, need - 1))
    links_out = [sanitize_link(best[0])] + [sanitize_link(a[0]) for a in alternates]
    copy_to_clipboard("\n".join(links_out))
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(LOGS_DIR, f"selected_{ts}.txt"), "w", encoding="utf-8") as f:
            f.write(f"# BEST {best_meta(best)}\n{links_out[0]}\n")
            for i, a in enumerate(alternates):
                f.write(f"# alt {i+1} {best_meta(a)}\n{sanitize_link(a[0])}\n")
        with open(os.path.join(LOGS_DIR, "best_current.txt"), "w", encoding="utf-8") as f:
            f.write(f"# BEST {best_meta(best)}\n{links_out[0]}\n")
        print(f"{C}Отобранные конфиги: logs/selected_{ts}.txt и logs/best_current.txt{N}")
    except Exception as e:
        print(f"{Y}⚠ Не удалось сохранить отобранные конфиги: {e}{N}")
    print(f"{G}✅ ЛУЧШИЙ VPN (доступен {TARGET.upper()}):{N}")
    print_summary_row(best, "BEST")
    if alternates:
        print(f"{Y}Запасные:{N}")
        for i, a in enumerate(alternates, 1):
            print_summary_row(a, f"#{i+1}")
    if LAUNCH_HIDDIFY and not RUN_BEST:
        launch_hiddify(links_out)
    if RUN_BEST:
        run_best_persistent(final_entries)


def signal_handler(sig, frame):
    print(f"{R}Прерывание...{N}")
    stop_event.set()
    clear_system_proxy()
    kill_xrays()
    sys.exit(0)


# ==================== ГЛАВНАЯ ====================

def main():
    global NEED, LAUNCH_HIDDIFY, PREFERRED_COUNTRIES, MAX_TIME, deadline, NO_CLIPBOARD
    global RUN_BEST, RUN_PORT, RUN_MONITOR

    parser = argparse.ArgumentParser(description="Поиск ЛУЧШЕГО VPN с доступом к целевому сайту (VLESS/VMess/Trojan/Hysteria2).")
    parser.add_argument("--need", type=int, default=NEED, help="Сколько ключей выдать")
    parser.add_argument("--max-test", type=int, default=2000, help="Макс. число тестируемых конфигов")
    parser.add_argument("--max-time", type=int, default=MAX_TIME, help="Общий тайм-бюджет в секундах")
    parser.add_argument("--reprobe", type=int, default=REPROBE_TIMES, help="Сколько раз прогонять кандидата")
    parser.add_argument("--countries", default=",".join(PREFERRED_COUNTRIES),
                        help="Приоритетные страны (через запятую)")
    parser.add_argument("--no-hiddify", action="store_true", help="Не запускать Hiddify")
    parser.add_argument("--no-clipboard", action="store_true", help="Не копировать в буфер обмена")
    parser.add_argument("--run-best", action="store_true", default=RUN_BEST,
                        help="Оставить работать только тот VPN, который открывает целевой сайт (по умолчанию ВКЛ)")
    parser.add_argument("--no-run-best", action="store_true",
                        help="Не держать VPN, просто найти и выдать лучшие конфиги")
    parser.add_argument("--target", default=TARGET, choices=["gemini", "chatgpt"],
                        help="Какой сайт считать критерием работы VPN (по умолчанию gemini)")
    parser.add_argument("--no-system-proxy", action="store_true",
                        help="Не прописывать системный прокси GNOME (настраивать браузер вручную)")
    parser.add_argument("--run-port", type=int, default=RUN_PORT,
                        help="Локальный порт для постоянного SOCKS5 VPN")
    parser.add_argument("--no-monitor", action="store_true",
                        help="Не проверять периодически целевой сайт после включения")
    args = parser.parse_args()

    NEED = max(1, args.need)
    LAUNCH_HIDDIFY = not args.no_hiddify
    PREFERRED_COUNTRIES = [c.strip().lower() for c in args.countries.split(",") if c.strip()]
    MAX_TIME = max(20, args.max_time)
    reprobe_times = max(1, args.reprobe)
    NO_CLIPBOARD = args.no_clipboard
    globals()["TARGET"] = args.target
    RUN_BEST = args.run_best and not args.no_run_best
    globals()["SYSTEM_PROXY"] = SYSTEM_PROXY and not args.no_system_proxy
    RUN_PORT = args.run_port
    RUN_MONITOR = not args.no_monitor

    _limit_fds()
    signal.signal(signal.SIGINT, signal_handler)
    os.makedirs(LOGS_DIR, exist_ok=True)
    load_cache()
    deadline = time.time() + MAX_TIME

    reprobe_budget = min(REPROBE_BUDGET, max(10, MAX_TIME // 3))
    scan_deadline = deadline - reprobe_budget

    print(f"{C}{'=' * 70}{N}")
    print(f"{C}Поиск ЛУЧШЕГО VPN с доступом к {TARGET.upper()}{N}")
    print(f"{C}Тайм-бюджет: {MAX_TIME}с | re-probe: {reprobe_times}х | нужно выдать: {NEED}{N}")
    if RUN_BEST:
        print(f"{C}Режим: ПОСТОЯННЫЙ VPN (порт {RUN_PORT}){N}")
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
    print(f"Всего собрано {len(all_links)} уникальных конфигов.")

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

    test_links.sort(key=order_key)

    per_server = {}
    deduped = []
    for l in test_links:
        sk = link_server(l)
        key = (sk[0], sk[1]) if sk else (l[:24], 0)
        if per_server.get(key, 0) >= MAX_PER_SERVER:
            continue
        per_server[key] = per_server.get(key, 0) + 1
        deduped.append(l)
    test_links = deduped

    if len(test_links) > args.max_test:
        test_links = test_links[:args.max_test]
    print(f"{Y}Оставлены первые {len(test_links)} (по приоритету).{N}")

    good_cached = sum(1 for l in test_links
                      if (sk := link_server(l)) and cached_server_state(*sk[:2]) == "good")
    print(f"Конфигов для теста: {len(test_links)} (проверенных ранее: ~{good_cached})")

    # ФАЗА 1: сканирование
    print(f"{C}Фаза 1: сканирование до ~{max(0, int(scan_deadline - time.time()))}с...{N}")
    tested_links = scan_batch(test_links, scan_deadline)
    kill_xrays()

    # ФАЗА 2: re-probe
    probed_map = {}
    if found_keys:
        print(f"{C}Найдено {len(found_keys)} кандидатов. Повторная проверка лучших...{N}")
        probe_candidates(found_keys, probed_map, reprobe_times)
        kill_xrays()

    # ФАЗА 2b: продолжаем поиск
    stable_bar = max(2, reprobe_times - 1)

    def stable_count(pm):
        return sum(1 for _, (_, ok, _) in pm.items() if ok >= stable_bar)

    scan_end = deadline - 15
    while time_left() > 30 and stable_count(probed_map) < NEED:
        remaining = [l for l in test_links if l not in tested_links]
        if not remaining:
            break
        print(f"{Y}Ищем ещё (стабильных меньше {NEED}; нетронуто: {len(remaining)})...{N}")
        tested_links |= scan_batch(remaining, time.time() + min(time_left() - 15, 40))
        kill_xrays()
        if found_keys:
            probe_candidates(found_keys, probed_map, reprobe_times)
            kill_xrays()

    if not probed_map and found_keys:
        probed_map = {l: (lat, 1, 0.0) for l, lat in sorted(found_keys, key=lambda x: x[1])[:REPROBE_TOP]}

    if not probed_map:
        process_results([], NEED)
        print(f"{R}Готово (ничего не найдено).{N}")
        save_cache()
        return

    probed = sorted(probed_map.items(), key=lambda kv: (-kv[1][1], kv[1][0], kv[1][2]))
    probed = sorted(probed, key=lambda kv: 0 if kv[1][1] >= stable_bar else 1)

    # ФИНАЛЬНЫЙ ГЕЙТ
    print(f"{C}Финальная проверка перед выдачей (нестабильное отбракуем)...{N}")
    gated = []
    for link, _ in probed[:6]:
        if time_left() <= 15:
            gated.append(link)
            break
        runs = [check_key(link), check_key(link)]
        ok_runs = sum(1 for r in runs if r)
        if ok_runs >= 1:
            gated.append(link)
            if ok_runs == 2:
                break
        else:
            print(f"{Y} отбракован: {link[:55]}{N}")
    if gated:
        probed = [kv for kv in probed if kv[0] in gated]
    kill_xrays()

    # ФАЗА 3: скорость и геолокация
    speed_map = {}
    speed_targets = [link for link, _ in probed[:5]]
    if speed_targets and time_left() > 10:
        print(f"{C}Замер скорости финалистов...{N}")
        with ThreadPoolExecutor(max_workers=min(5, len(speed_targets))) as pool:
            futs = {pool.submit(probe_with_speed, link): link for link in speed_targets}
            for fut in as_completed(futs):
                res = fut.result()
                if res is not None:
                    speed_map[futs[fut]] = res[1]
        kill_xrays()

    ips = []
    for link, _ in probed[:8]:
        ip, _ = server_ip(link)
        if ip:
            ips.append(ip)
    geo = geo_lookup(list(dict.fromkeys(ips)))

    final = []
    for link, (med, ok, sd) in probed[:8]:
        ip, _ = server_ip(link)
        country = geo.get(ip) or extract_country(link)
        final.append((link, med, ok, sd, speed_map.get(link), _proto_of(link), country))

    process_results(final, NEED)
    save_cache()
    print(f"{G}Готово!{N}")


if __name__ == "__main__":
    main()
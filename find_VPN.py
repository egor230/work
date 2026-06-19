import os, sys, json, time, threading, tempfile, subprocess, signal, socket, base64
from urllib.request import urlopen, Request
from urllib.parse import parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== НАСТРОЙКИ ====================
REPO_ORIG = "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/main/githubmirror"
FILES_ORIG = ["1.txt", "6.txt", "22.txt", "23.txt", "24.txt", "25.txt"]

EXTRA_REPOS = [
 "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
 "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt",
 "https://raw.githubusercontent.com/Romaxa55/MegaV_Public/main/subs/vless.txt",
 "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub.txt",
 "https://raw.githubusercontent.com/MhdiJafari/Free-V2ray-Config/main/All_Configs_Sub.txt"
]

NEED = 5
TIMEOUT_DL = 12
TIMEOUT_TEST = 6
XRAY_PORT_BASE = 10900
MAX_DL_WORKERS = 10
MAX_TEST_WORKERS = 25

PREFERRED_COUNTRIES = ["nl", "gb", "uk", "de", "fr", "pl", "lt", "lv", "ee", "se", "no", "fi", "at", "ch", "be", "dk", "ru"]
FALLBACK_TO_ANY = True

TEST_SITES = ["https://cp.cloudflare.com/generate_204", "https://www.gstatic.com/generate_204", "https://yandex.ru/"]

C = "\033[0;36m";
G = "\033[0;32m";
R = "\033[0;31m";
Y = "\033[1;33m";
N = "\033[0m"

found_lock = threading.Lock()
found_keys = []
stop_event = threading.Event()
xray_pids = []
xray_lock = threading.Lock()
port_counter = XRAY_PORT_BASE
port_lock = threading.Lock()


def kill_xrays():
 with xray_lock:
  for p in xray_pids[:]:
   try:
    os.kill(p, 9)
   except:
    pass
  xray_pids.clear()


def get_port():
 global port_counter
 with port_lock:
  port_counter += 1
  return port_counter


def wait_for_port(port, timeout=2.5):
 start = time.time()
 while time.time() - start < timeout:
  if stop_event.is_set(): return False
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
   s.settimeout(0.1)
   if s.connect_ex(('127.0.0.1', port)) == 0: return True
  time.sleep(0.05)
 return False


def download_file(url):
 try:
  req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
  with urlopen(req, timeout=TIMEOUT_DL) as resp:
   data = resp.read().decode("utf-8", errors="ignore")
   links = [line.strip() for line in data.splitlines() if line.strip() and not line.startswith('#')]
   print(f"{G}Загружено {len(links)} ссылок из {url.split('/')[-1][:50]}{N}")
   return links
 except Exception as e:
  print(f"{R}Ошибка загрузки {url}: {e}{N}")
  return []


def b64_decode(s):
 s = s.replace("-", "+").replace("_", "/")
 pad = (4 - len(s) % 4) % 4
 s += "=" * pad
 try:
  return base64.b64decode(s).decode("utf-8", errors="ignore")
 except:
  return ""


def link_contains_country(link, countries):
 if not countries: return True
 lower = link.lower()
 try:
  name = lower.split("#", 1)[1] if "#" in lower else ""
  text = f"{lower} {name}"
  for c in countries:
   if any(x in text for x in [f".{c}.", f".{c}", f"{c}.", f" {c} ", f"[{c}]", f"-{c}-"]):
    return True
 except:
  pass
 return False


def parse_vless(link):
 try:
  body = link[len("vless://"):]
  frag, _, query = body.partition("?")
  uuid_part, _, rest = frag.partition("@")
  addr, _, port_str = rest.rpartition(":")
  port = int(port_str)
  params = parse_qs(query)
  net = params.get("type", ["tcp"])[0]
  sni = params.get("sni", [""])[0] or params.get("host", [""])[0]
  fp = params.get("fp", ["chrome"])[0]
  sec = params.get("security", ["none"])[0]
  
  stream = {"network": net}
  if sec == "reality":
   stream["security"] = "reality"
   stream["realitySettings"] = {
    "serverName": sni, "fingerprint": fp,
    "publicKey": params.get("pbk", [""])[0],
    "shortId": params.get("sid", [""])[0]
   }
  elif sec == "tls":
   stream["security"] = "tls"
   stream["tlsSettings"] = {"serverName": sni or addr, "fingerprint": fp}
  
  return {
   "protocol": "vless",
   "settings": {"vnext": [{"address": addr, "port": port, "users": [{"id": uuid_part, "encryption": "none"}]}]},
   "streamSettings": stream
  }
 except:
  return None


def parse_vmess(link):
 try:
  decoded = json.loads(b64_decode(link[len("vmess://"):]))
  net = decoded.get("net", "tcp")
  stream = {"network": net}
  if decoded.get("tls") == "tls":
   stream["security"] = "tls"
   stream["tlsSettings"] = {"serverName": decoded.get("sni") or decoded.get("add"), "fingerprint": decoded.get("fp", "chrome")}
  return {
   "protocol": "vmess",
   "settings": {"vnext": [{"address": decoded["add"], "port": int(decoded["port"]), "users": [{"id": decoded["id"], "alterId": int(decoded.get("aid", 0)), "security": "auto"}]}]},
   "streamSettings": stream
  }
 except:
  return None


def parse_trojan(link):
 try:
  body = link[len("trojan://"):]
  frag, _, query = body.partition("?")
  pw, _, rest = frag.partition("@")
  addr, _, port_str = rest.rpartition(":")
  port = int(port_str)
  params = parse_qs(query)
  sni = params.get("sni", [""])[0] or params.get("host", [""])[0]
  stream = {"network": params.get("type", ["tcp"])[0], "security": "tls", "tlsSettings": {"serverName": sni}}
  return {"protocol": "trojan", "settings": {"servers": [{"address": addr, "port": port, "password": pw}]}, "streamSettings": stream}
 except:
  return None


def parse_hy2(link):
 try:
  body = link.split("://", 1)[1]
  frag, _, query = body.partition("?")
  pw, _, rest = frag.partition("@")
  addr, _, port_str = rest.rpartition(":")
  port = int(port_str)
  sni = parse_qs(query).get("sni", [""])[0]
  return {
   "protocol": "hysteria2",
   "settings": {"servers": [{"address": addr, "port": port, "password": pw}]},
   "streamSettings": {"network": "hysteria2", "security": "tls", "tlsSettings": {"serverName": sni or addr}}
  }
 except:
  return None


def link_to_outbound(link):
 if link.startswith("vless://"): return parse_vless(link)
 if link.startswith("vmess://"): return parse_vmess(link)
 if link.startswith("trojan://"): return parse_trojan(link)
 if link.startswith(("hysteria2://", "hy2://")): return parse_hy2(link)
 return None


def check_key(link):
 if stop_event.is_set(): return None
 if not any(link.startswith(p) for p in ("vless://", "vmess://", "trojan://", "hysteria2://", "hy2://")):
  return None
 
 outbound = link_to_outbound(link)
 if not outbound: return None
 
 port = get_port()
 config = {
  "log": {"loglevel": "error"},
  "dns": {"servers": ["8.8.8.8", "1.1.1.1"]},
  "inbounds": [{"listen": "127.0.0.1", "port": port, "protocol": "socks", "settings": {"auth": "noauth", "udp": False}}],
  "outbounds": [outbound, {"protocol": "freedom", "tag": "direct"}]
 }
 
 tmpf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
 json.dump(config, tmpf)
 tmpf.close()
 
 proc = None
 try:
  proc = subprocess.Popen(["xray", "run", "-config", tmpf.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  with xray_lock:
   xray_pids.append(proc.pid)
  
  if not wait_for_port(port) or proc.poll() is not None:
   return None
  
  success = 0
  latencies = []
  for site in TEST_SITES:
   if stop_event.is_set(): return None
   start = time.time()
   r = subprocess.run(["curl", "-x", f"socks5h://127.0.0.1:{port}", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                       "--connect-timeout", str(TIMEOUT_TEST), "--max-time", str(TIMEOUT_TEST), site],
                      capture_output=True, text=True, timeout=TIMEOUT_TEST + 3)
   elapsed = (time.time() - start) * 1000
   if r.returncode == 0 and r.stdout.strip() in ("200", "204", "301", "302"):
    success += 1
    latencies.append(elapsed)
  
  return sum(latencies) / len(latencies) if success >= 2 else None
 
 except:
  return None
 finally:
  if proc:
   try:
    proc.kill()
   except:
    pass
   with xray_lock:
    xray_pids[:] = [p for p in xray_pids if p != proc.pid]
  try:
   os.unlink(tmpf.name)
  except:
   pass


def copy_to_clipboard(text):
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


def process_results():
 if not found_keys: return
 
 def sort_key(x):
  is_eu = any(c in x[0].lower() for c in PREFERRED_COUNTRIES)
  return (0 if is_eu else 1, x[1])
 
 sorted_keys = sorted(found_keys, key=sort_key)
 best = [k[0] for k in sorted_keys[:NEED]]
 
 data = "\n".join(best)
 b64 = base64.b64encode(data.encode()).decode()
 copy_to_clipboard(b64)
 
 print(f"\n{G}✅ Найдено {len(best)} рабочих ключей{N}")
 for link in best:
  print(f"{G}{link}{N}")


def signal_handler(sig, frame):
 print(f"\n{R}Прерывание...{N}")
 stop_event.set()
 kill_xrays()
 process_results()
 sys.exit(0)


def main():
 signal.signal(signal.SIGINT, signal_handler)
 print(f"\n{C}{'=' * 70}{N}")
 print(f"{C}Поиск рабочих VPN для России (2026){N}")
 print(f"{C}{'=' * 70}{N}")
 
 for tool in ("xray", "curl"):
  try:
   subprocess.run([tool, "--version"], capture_output=True, timeout=5)
  except FileNotFoundError:
   print(f"{R}{tool} не установлен!{N}")
   sys.exit(1)
 
 all_links = []
 for f in FILES_ORIG:
  all_links.extend(download_file(f"{REPO_ORIG}/{f}"))
 for url in EXTRA_REPOS:
  all_links.extend(download_file(url))
 
 print(f"\nВсего собрано {len(all_links)} конфигов.")
 
 eu_links = [l for l in all_links if link_contains_country(l, PREFERRED_COUNTRIES)]
 others = [l for l in all_links if l not in eu_links] if FALLBACK_TO_ANY else []
 test_links = eu_links + others[:400]
 
 print(f"Приоритет (EU+RU): {len(eu_links)} | Остальные: {len(others)}\n")
 
 tested = 0
 with ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as pool:
  futures = {pool.submit(check_key, link): link for link in test_links}
  for future in as_completed(futures):
   if stop_event.is_set(): break
   tested += 1
   latency = future.result()
   link = futures[future]
   
   if latency is not None and latency < 2500:
    with found_lock:
     if len(found_keys) < NEED:
      found_keys.append((link, latency))
      print(f"{G}✓ Рабочий ({latency:.0f}мс) — {link[:65]}...{N}")
   
   if len(found_keys) >= NEED:
    stop_event.set()
    break
   
   print(f"\r{C}Проверено: {tested}/{len(test_links)} | Найдено: {len(found_keys)}{N}   ", end="", flush=True)
 
 kill_xrays()
 process_results()
 print(f"\n{G}Готово!{N}")


if __name__ == "__main__":
 main()
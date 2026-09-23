#!/usr/bin/env bash
# restore-config.sh — восстанавливает настройки из config-backup.json
# в chrome.storage.local расширения (через CDP, не трогая файлы расширения).
#
# Используется вместе с save-config.sh для переноса настроек
# между компьютерами (см. раздел 3 README-CUSTOM.md).
#
# Использование:
#   1) Chrome ДОЛЖЕН быть запущен с --remote-debugging-port=9222
#      (или скрипт сам запустит headless-инстанс)
#   2) Расширение ДОЛЖНО быть установлено (ID = ifojmbdceojdnhhagpmfnmjndpplcndi)
#   3) ./restore-config.sh [ПУТЬ_К_ПАПКЕ_РАСШИРЕНИЯ]

set -euo pipefail

EXT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
EXT_DIR="$(cd "$EXT_DIR" && pwd)"
CFG="$EXT_DIR/config-backup.json"
[[ -f "$CFG" ]] || { echo "ERROR: $CFG не найден" >&2; exit 1; }

# Запускаем Chrome headless (если нет запущенного с CDP)
CDP_PORT=9223
if ! curl -s "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null 2>&1; then
  echo "[*] Запускаю headless Chrome с CDP на порту $CDP_PORT..."
  set -m
  nohup google-chrome --headless=new \
    --remote-debugging-port=$CDP_PORT \
    --user-data-dir=/tmp/efyt-restore-profile \
    --no-sandbox --no-first-run --disable-gpu \
    >/tmp/efyt-restore-chrome.log 2>&1 &
  CHROME_PID=$!
  # Ждём CDP
  for i in $(seq 1 15); do
    sleep 1
    curl -s "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null 2>&1 && break
  done
fi

# Ищем target расширения (Service Worker)
TARGET=$(curl -s "http://127.0.0.1:$CDP_PORT/json" | python3 -c "
import sys, json
tabs = json.load(sys.stdin)
for t in tabs:
    if 'service_worker' in t.get('type','') or 'serviceWorker' in t.get('type',''):
        print(t['webSocketDebuggerUrl']); break
" 2>/dev/null)

if [[ -z "$TARGET" ]]; then
  echo "[!] Service Worker target не найден. Пробую через Chrome DevTools Protocol на уровне tabs."
  # Fallback: создаём blank tab и инжектим fetch
  TARGET=$(curl -s "http://127.0.0.1:$CDP_PORT/json" | python3 -c "
import sys, json
tabs = json.load(sys.stdin)
for t in tabs:
    if t.get('type') == 'page':
        print(t['webSocketDebuggerUrl']); break
" 2>/dev/null)
fi

if [[ -z "$TARGET" ]]; then
  echo "ERROR: не нашёл CDP target. Запусти Chrome вручную с --remote-debugging-port=$CDP_PORT"
  exit 1
fi

echo "[*] CDP target: $TARGET"

# Читаем config-backup.json и шлём все ключи в chrome.storage.local
# через CDP Runtime.evaluate
python3 - "$CFG" "$TARGET" <<'PY'
import sys, json, base64, urllib.request
from pathlib import Path

cfg_path, target_url = sys.argv[1], sys.argv[2]
cfg = json.loads(Path(cfg_path).read_text(encoding='utf-8'))

# Убираем метаданные
cfg.pop('_meta', None)

print(f"[*] Восстанавливаю {len(cfg)} ключей из {cfg_path}")

# CDP: подключаемся к target
# Для service worker: Runtime.evaluate с chrome.storage.local.set
# Для page: fetch к chrome-extension://<id>/... (не сработает)
# Лучший путь — через chrome.storage.local.set напрямую в SW context

# WebSocket via python (используем websockets или socket)
import socket, struct, json as _json

# Parse WebSocket URL
ws_url = target_url
# ws://127.0.0.1:9223/devtools/page/<id>
# Connect
import re
m = re.match(r'ws://([\d.]+):(\d+)(/.+)', ws_url)
if not m:
    print(f"Cannot parse: {ws_url}")
    sys.exit(1)
host, port, path = m.group(1), int(m.group(2)), m.group(3)

# Send handshake
s = socket.create_connection((host, port), timeout=10)
s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
# Read handshake response
import time
time.sleep(0.5)
hdrs = b''
while b'\r\n\r\n' not in hdrs:
    hdrs += s.recv(4096)
print(f"[*] WS connected: {hdrs[:100].decode('latin-1')}")

# Send CDP Runtime.evaluate
# Build the JS code to run
js_code = f"""
(async () => {{
  const cfg = {json.dumps(cfg)};
  // chrome.storage.local.set is available in service worker
  await chrome.storage.local.set(cfg);
  return Object.keys(cfg).join(', ');
}})()
"""

# Frame: FIN=1, opcode=1 (text), masked
payload = json.dumps({
    "id": 1,
    "method": "Runtime.evaluate",
    "params": {
        "expression": js_code,
        "awaitPromise": True,
        "returnByValue": True
    }
}).encode()

def _mask_frame(payload):
    frame = bytearray()
    frame.append(0x81)
    if len(payload) < 126:
        frame.append(0x80 | len(payload))
        mask = bytes([0x12, 0x34, 0x56, 0x78])
        frame.extend(mask)
        masked = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
        frame.extend(masked)
    elif len(payload) < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack('>H', len(payload)))
        mask = bytes([0x12, 0x34, 0x56, 0x78])
        frame.extend(mask)
        masked = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
        frame.extend(masked)
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack('>Q', len(payload)))
        mask = bytes([0x12, 0x34, 0x56, 0x78])
        frame.extend(mask)
        masked = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
        frame.extend(masked)
    return bytes(frame)

s.sendall(_mask_frame(payload))
time.sleep(2)

resp = b''
while len(resp) < 200:
    try:
        resp += s.recv(4096)
    except: break
print(f"[*] Response: {resp[:300].decode('latin-1', errors='replace')}")
s.close()

if b'result' in resp:
    print(f"[+] Настройки восстановлены: {list(cfg.keys())}")
    print(f"[+] Перезагрузи вкладки YouTube (F5) чтобы применить.")
else:
    print(f"[!] Ответ CDP не распознан, но команда отправлена.")
    print(f"[+] Проверь chrome.storage.local вручную.")
PY

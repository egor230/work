#!/usr/bin/env bash
#
# install-native-host.sh — регистрация native messaging host «com.efyt.channelspeeds»
# для Enhancer for YouTube (кастом, §12 README-CUSTOM.md).
#
# Хост (native-host/efyt-json-host.py) пишет таблицу скоростей по каналам
# в настоящий JSON-файл в папке расширения:
#
#   /home/egor/Downloads/расширения/Enhancer for YouTube/channelspeeds.json
#
# Chrome не даёт расширению писать в собственный каталог, поэтому пишущий
# процесс должен жить вне расширения — это и есть native host. Регистрация:
# манифест хоста кладётся в NativeMessagingHosts каждого установленного
# браузера, в allowed_origins вписывается ID расширения (вычисляется из
# efyt_private.pem — того же ключа, которым подписан .crx).
#
# Использование:
#   ./install-native-host.sh              # зарегистрировать
#   ./install-native-host.sh --uninstall  # убрать манифесты из всех браузеров
#
set -euo pipefail

EXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_PY="$EXT_DIR/native-host/efyt-json-host.py"
HOST_NAME="com.efyt.channelspeeds"
JSON_PATH="$EXT_DIR/channelspeeds.json"
HOST_MANIFEST="$HOST_NAME.json"

[[ -f "$HOST_PY" ]] || { echo "ERROR: $HOST_PY не найден" >&2; exit 1; }
[[ -f "$EXT_DIR/efyt_private.pem" ]] || { echo "ERROR: $EXT_DIR/efyt_private.pem не найден (нужен для вычисления ID расширения)" >&2; exit 1; }
chmod +x "$HOST_PY"

# ID расширения = SHA-256(SPKI)[:16] в алфавите a–p (то же, что печатает package-crx.sh)
EXT_ID="$(python3 - "$EXT_DIR/efyt_private.pem" <<'PY'
import sys, hashlib
from cryptography.hazmat.primitives import serialization
key = serialization.load_pem_private_key(open(sys.argv[1], "rb").read(), password=None)
spki = key.public_key().public_bytes(serialization.Encoding.DER,
                                     serialization.PublicFormat.SubjectPublicKeyInfo)
b = hashlib.sha256(spki).digest()[:16]
print("".join(chr(ord('a') + (x >> 4)) + chr(ord('a') + (x & 15)) for x in b))
PY
)"

if [[ "${1:-}" == "--uninstall" ]]; then
  for d in "$HOME/.config/google-chrome" "$HOME/.config/chromium" "$HOME/.config/yandex-browser" \
           "$HOME/.config/BraveSoftware/Brave-Browser" "$HOME/.config/vivaldi"; do
    [[ -f "$d/NativeMessagingHosts/$HOST_MANIFEST" ]] && rm -f "$d/NativeMessagingHosts/$HOST_MANIFEST" && echo "[-] убран: $d/NativeMessagingHosts/$HOST_MANIFEST"
  done
  echo "[+] Хост не удалён из браузеров. Перезапустите браузер."
  exit 0
fi

# 1) Куда хост пишет JSON (файл-конфиг хоста, читается при каждом запросе)
printf '%s\n' "$JSON_PATH" > "$EXT_DIR/native-host/path.txt"

# 2) Манифест хоста во все установленные браузеры
BROWSER_DIRS=()
for d in "$HOME/.config/google-chrome" "$HOME/.config/chromium" "$HOME/.config/yandex-browser" \
         "$HOME/.config/BraveSoftware/Brave-Browser" "$HOME/.config/vivaldi"; do
  [[ -d "$d" ]] && BROWSER_DIRS+=("$d")
done
[[ ${#BROWSER_DIRS[@]} -eq 0 ]] && BROWSER_DIRS=("$HOME/.config/google-chrome" "$HOME/.config/chromium")

python3 - "$EXT_ID" "$HOST_PY" "$HOST_NAME" "${BROWSER_DIRS[@]}" <<'PY'
import json, os, sys

ext_id, host_py, host_name = sys.argv[1], sys.argv[2], sys.argv[3]
browser_dirs = sys.argv[4:]
manifest = {
    "name": host_name,
    "description": "Enhancer for YouTube — пишет скорости по каналам в channelspeeds.json (папка расширения)",
    "path": host_py,
    "type": "stdio",
    "allowed_origins": ["chrome-extension://%s/" % ext_id],
}
for d in browser_dirs:
    nm = os.path.join(d, "NativeMessagingHosts")
    os.makedirs(nm, exist_ok=True)
    out = os.path.join(nm, host_name + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("[+] %s" % out)
PY

echo
echo "[+] ID расширения: $EXT_ID"
echo "[+] JSON-файл скоростей: $JSON_PATH"
echo "[+] Хост: $HOST_PY"
echo
echo "Готово. Перезапустите браузер — теперь каждая смена скорости"
echo "(колесо, кнопки, нативное меню YouTube, панель, горячие клавиши)"
echo "перезаписывает $JSON_PATH"
echo "Без хоста расширение работает в fallback-режиме: пишет тот же JSON"
echo "через chrome.downloads (папка загрузок/расширения/…, см. README §12)."

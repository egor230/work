#!/bin/bash
# ============================================================
# install.sh — установка native messaging host
# ВАЖНО (грабля 2026-09-09): браузер ОТКАЗЫВАЕТСЯ запускать host,
# если его файлы принадлежат root:root c правами 777 (ntfs-раздел
# /mnt/...). Chromium-безопасность молча убивает такой host —
# «расширение не печатает». Поэтому host КОПИРУЕТСЯ в домашнюю
# папку (ext4, egor:egor, 700/644) и манифест указывает туда.
#
# Запуск: bash install.sh <ID_РАСШИРЕНИЯ>
# ============================================================
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
HOST_NAME="voice_input_yandex"
HOST_HOME="$HOME/.local/share/voice-input-yandex"
VENV_PY="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python"

if [ -z "$1" ]; then
  echo "Использование: bash install.sh <ID_РАСШИРЕНИЯ>"
  echo "ID виден на странице расширений браузера (browser://extensions)."
  exit 1
fi
EXT_ID="$1"

# 1) копируем host в домашнюю папку с правильными правами
mkdir -p "$HOST_HOME"
cp "$DIR/native-host/native_host.py" "$HOST_HOME/"
cat > "$HOST_HOME/native_host.sh" <<EOF
#!/bin/bash
export DISPLAY=":0"
export XAUTHORITY="\$HOME/.Xauthority"
exec "$VENV_PY" "$HOST_HOME/native_host.py"
EOF
chmod 700 "$HOST_HOME/native_host.sh"
chmod 644 "$HOST_HOME/native_host.py"

# 2) манифест host: путь в домашнюю папку + ID расширения
for BROWSER_DIR in yandex-browser google-chrome chromium; do
  DEST="$HOME/.config/$BROWSER_DIR/NativeMessagingHosts"
  mkdir -p "$DEST"
  cat > "$DEST/$HOST_NAME.json" <<EOF
{
  "name": "$HOST_NAME",
  "description": "Голосовой ввод от Яндекса — печать распознанного текста через evdev",
  "path": "$HOST_HOME/native_host.sh",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXT_ID/"
  ]
}
EOF
  chmod 644 "$DEST/$HOST_NAME.json"
  echo "установлен: $DEST/$HOST_NAME.json"
done

# 3) сохранить эталонный манифест в папке расширения
cat > "$DIR/native-host/com.voice_input_yandex.json" <<EOF
{
  "name": "$HOST_NAME",
  "description": "Голосовой ввод от Яндекса — печать распознанного текста через evdev",
  "path": "$HOST_HOME/native_host.sh",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXT_ID/"
  ]
}
EOF

# 4) самопроверка: host должен стартовать и не упасть
echo "--- самопроверка host (5 c) ---"
python3 - <<PYEOF
import struct, json, subprocess, time, os
env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "XAUTHORITY")}
msg = json.dumps({"cmd": "print", "text": ""})   # пустой текст — только проверка запуска
p = subprocess.Popen(["$HOST_HOME/native_host.sh"], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
p.stdin.write(struct.pack("<I", len(msg.encode())) + msg.encode())
p.stdin.flush()
time.sleep(5)
p.terminate()
print("host прожил 5 c — OK")
PYEOF

echo "Готово. ПЕРЕЗАПУСТИТЕ БРАУЗЕР ПОЛНОСТЬЮ (закрыть все окна/процессы)."

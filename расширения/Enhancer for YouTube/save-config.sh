#!/usr/bin/env bash
# save-config.sh — сохранять настройки расширения в config-backup.json
# в папке расширения (для архива/перегрузки на другом компьютере).
#
# Использует chrome.storage.local (LevelDB из профиля Chrome).
# Расширение ДОЛЖНО БЫТЬ АКТИВНЫМ (установлено), иначе нет данных.
#
# Использование:
#   ./save-config.sh [ПУТЬ_К_ПАПКЕ_РАСШИРЕНИЯ]
# Результат: config-backup.json в папке расширения (и в текущей папке)

set -euo pipefail

EXT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
EXT_DIR="$(cd "$EXT_DIR" && pwd)"
[[ -f "$EXT_DIR/manifest.json" ]] || { echo "ERROR: $EXT_DIR/manifest.json не найден" >&2; exit 1; }

# Поиск LevelDB с данными chrome.storage.local
# Расширение хранит все настройки в chrome.storage.local, который
# физически находится в profile/Local Extension Settings/<ID>/
# или в profile/Local Storage/leveldb/ (для content scripts)
#
# Для unpacked-расширений настройки хранятся в:
#   ~/.config/google-chrome/*/Local Extension Settings/<extension-id>/
# Для CRX-расширений — в том же месте.

# Получаем ID расширения из efyt_private.pem
ID=""
if [[ -f "$EXT_DIR/efyt_private.pem" ]]; then
  ID=$(python3 -c "
from pathlib import Path
import hashlib
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PublicFormat
k = load_pem_private_key(Path('$EXT_DIR/efyt_private.pem').read_bytes(), password=None)
spki = k.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
b16 = hashlib.sha256(spki).digest()[:16]
print(''.join(chr(ord('a')+(x>>4))+chr(ord('a')+(x&15)) for x in b16))
")
fi

# Ищем папку Local Extension Settings
LSS=""
for profile in "$HOME/.config/google-chrome"/*/ "$HOME/.config/chromium"/*/; do
  d="${profile}Local Extension Settings/$ID"
  if [[ -d "$d" ]]; then
    LSS="$d"
    break
  fi
done

if [[ -z "$LSS" ]]; then
  # Fallback: ищем в Local Storage (для unpacked)
  echo "[!] Local Extension Settings/$ID не найден — пробую Local Storage..."
  for profile in "$HOME/.config/google-chrome"/*/; do
    ls_path="${profile}Local Storage/leveldb"
    if [[ -d "$ls_path" ]]; then
      LSS="$ls_path"
      echo "[*] Using Local Storage (unpacked mode): $LSS"
      break
    fi
  done
fi

if [[ -z "$LSS" ]]; then
  echo "ERROR: не нашёл хранилище настроек для ID=$ID"
  echo " Убедись, что расширение установлено в Chrome."
  exit 1
fi

echo "[*] ID расширения: $ID"
echo "[*] Хранилище: $LSS"

OUT="$EXT_DIR/config-backup.json"

python3 - "$LSS" "$OUT" "$ID" <<'PY'
import sys, json, struct, re
from pathlib import Path
from collections import defaultdict

lss_dir, out_path, ext_id = sys.argv[1], sys.argv[2], sys.argv[3]

# LevelDB: читаем все .ldb файлы, парсим блоки, извлекаем
# ключи вида "chrome.storage.local.<ext_id>.<key>" или
# "<key>" (для Local Extension Settings — просто ключи).

data = {}

for ldb in sorted(Path(lss_dir).glob('*.ldb')):
    try:
        raw = ldb.read_bytes()
    except PermissionError:
        print(f"[!] Cannot read {ldb.name} (permission) — skip")
        continue

    # LevelDB data block format (simplified — enough for our keys)
    # Each record in a data block: key_len (varint) key value_len (varint) value
    # The file has: 64-byte header + data blocks + index + metaindex
    #
    # We scan for our keys manually: look for byte patterns.
    # In Local Extension Settings, keys are just the storage key names
    # (e.g. "maTheme", "channelspeeds", "darktheme", ...).
    # Values are msgpack-encoded.

    # Simpler approach: use python-leveldb if available, else raw scan
    try:
        import leveldb
        db = leveldb.LevelDB(lss_dir, readonly=True, create_if_missing=False)
        for key in db.Iterate():
            if isinstance(key, bytes):
                key = key.decode('utf-8', errors='replace')
            val = db.Get(key)
            if val is None:
                continue
            # Store raw msgpack bytes (we'll decode in second pass)
            data[key] = val
        db.Close()
        print(f"[*] leveldb: read {len(data)} keys")
    except ImportError:
        print("[!] python-leveldb not available — raw scan")
        # Raw scan: find our known keys
        KNOWN_KEYS = [
            b'maTheme', b'channelspeeds', b'darktheme', b'theme', b'themevariant',
            b'volume', b'defaultvolume', b'speed', b'overridespeeds',
            b'selectquality', b'cinemamode', b'miniplayer', b'hidecomments',
            b'hiderelated', b'hidecardsendscreens', b'hidechat', b'blockautoplay',
            b'controls', b'localecode', b'backdropcolor', b'backdropopacity',
            b'qualityvideos', b'qualityvideosfullscreen', b'qualityplaylists',
            b'qualityplaylistsfullscreen', b'qualityembeds', b'qualityembedsfullscreen',
            b'filter', b'videofilters', b'customcss', b'customscript', b'customtheme',
            b'reversemousewheeldirection', b'convertshorts', b'newestcomments',
            b'stopvideos', b'pausevideos', b'theatermode', b'wideplayer',
            b'controlbar', b'whatsnew', b'reload', b'update', b'previousversion',
            b'date', b'popuplayersize', b'ignorepopupplayer', b'ignoreplaylists',
            b'hidechat', b'hidecardsendscreens', b'boostvolume', b'disableautoplay',
            b'blackbars', b'griditemsperrow', b'blockhfrformats', b'blockwebmformats',
            b'plugin', b'plugins', b'whitelist',
        ]
        for needle in KNOWN_KEYS:
            # LevelDB stores keys as: [key_bytes] [value_bytes] (no explicit separator in data blocks)
            # We scan for the key pattern: key_len (varint) key
            idx = 0
            found = []
            while True:
                idx = raw.find(needle, idx)
                if idx < 0:
                    break
                # Check if this looks like a valid LevelDB key occurrence
                # (preceded by a varint length that matches len(needle))
                start = idx
                while start > 0 and raw[start-1] >= 0x80:
                    start -= 1
                key_len = raw[start-1] & 0x7F if start > 0 else 0
                if key_len == len(needle) and start > 0:
                    # Extract value after key
                    val_start = idx + len(needle)
                    # Value is msgpack — read until next key pattern
                    val_end = val_start
                    # Try to parse msgpack
                    import io
                    from struct import pack
                    # Simple msgpack decoder for common types
                    try:
                        mp = val_start
                        b0 = raw[mp]
                        if b0 in (0x00,):
                            val_end = mp + 1
                        elif b0 == 0x80:  # nil
                            val_end = mp + 1
                        elif b0 >= 0x90 and b0 <= 0x9f:  # fixarray
                            val_end = mp + 1
                        elif b0 >= 0xa0 and b0 <= 0xbf:  # fixstr
                            slen = b0 & 0x1f
                            val_end = mp + 1 + slen
                        elif b0 in (0xc0, 0xcc, 0x73, 0x74):  # nil/uint8
                            val_end = mp + 1
                        elif b0 in (0xc1, 0xd9, 0xda, 0xdb):  # true/str8/str16/str32
                            val_end = mp + 2
                        elif b0 in (0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7):
                            val_end = mp + 9
                        elif b0 in (0xd8, 0xd9, 0xda, 0xdb, 0xdc, 0xdd, 0xde):
                            val_end = mp + 2 + raw[val_end:val_end+2].find(b'\x00')
                        else:
                            val_end = mp + 1
                        data[needle.decode()] = raw[mp:val_end]
                    except Exception:
                        pass
                idx += 1

        print(f"[*] raw scan: found {len(data)} keys")

# Now decode msgpack values
def msgpack_decode(b):
    """Minimal msgpack decoder for chrome.storage.local values."""
    if b is None:
        return None
    if isinstance(b, (dict, list, str, int, float, bool, type(None))):
        return b
    import io
    pos = 0
    def rd():
        nonlocal pos
        if pos >= len(b):
            return None
        v = b[pos]
        pos += 1
        return v
    def rd_uint():
        v = 0
        while True:
            x = rd()
            if x is None:
                return 0
            v = (v << 7) | (x & 0x7F)
            if not (x & 0x80):
                return v
    def decode(val=None):
        if val is None:
            val = rd()
        if val is None:
            return None
        # positive fixint
        if val <= 0x7f:
            return val
        # negative fixint
        if val >= 0xe0:
            return val - 256
        # fixstr
        if 0xa0 <= val <= 0xbf:
            slen = val & 0x1f
            s = b[pos:pos+slen]
            pos += slen
            return s.decode('utf-8', errors='replace')
        # fixarray
        if 0x90 <= val <= 0x9f:
            n = val & 0x0f
            return [decode() for _ in range(n)]
        # fixmap
        if 0x80 <= val <= 0x8f:
            n = val & 0x0f
            out = {}
            for _ in range(n):
                k = decode()
                v = decode()
                out[k if isinstance(k, str) else str(k)] = v
            return out
        # typed
        if val == 0xc0: return None
        if val == 0xc1:
            rd()
            return True
        if val == 0xc2:
            rd()
            return False
        if val in (0xc3, 0xc4, 0xc5, 0xc6, 0xc7):
            return rd()
        if val == 0xc8:
            return rd_uint()
        if val == 0xc9:
            return rd_uint()
        if val == 0xca:
            import struct as st
            v = st.unpack('>h', b[pos:pos+2])[0]
            pos += 2
            return v
        if val == 0xcb:
            import struct as st
            v = st.unpack('>i', b[pos:pos+4])[0]
            pos += 4
            return v
        if val == 0xcc:
            return rd()
        if val == 0xcd:
            v = rd(); return v << 8 | rd()
        if val == 0xce:
            v = rd(); return (v << 16) | (rd() << 8) | rd()
        if val == 0xcf:
            import struct as st
            v = st.unpack('>q', b[pos:pos+8])[0]
            pos += 8
            return v
        if val == 0xd0:
            import struct as st
            v = st.unpack('>f', b[pos:pos+4])[0]
            pos += 4
            return v
        if val == 0xd1:
            import struct as st
            v = st.unpack('>d', b[pos:pos+8])[0]
            pos += 8
            return v
        if val == 0xd2:
            n = rd_uint()
            out = {}
            for _ in range(n):
                k = decode()
                v = decode()
                out[k if isinstance(k, str) else str(k)] = v
            return out
        if val == 0xd3:
            n = rd_uint()
            return [decode() for _ in range(n)]
        if val == 0xd4:
            n = rd()
            return [decode() for _ in range(n)]
        if val == 0xd5:
            n = rd()
            out = {}
            for _ in range(n):
                k = decode()
                v = decode()
                out[k if isinstance(k, str) else str(k)] = v
            return out
        if val == 0xd6:
            n = rd()
            s = b[pos:pos+n]
            pos += n
            return s.decode('utf-8', errors='replace')
        if val == 0xd7:
            n = rd() << 8 | rd()
            s = b[pos:pos+n]
            pos += n
            return s.decode('utf-8', errors='replace')
        if val in (0xd8, 0xd9, 0xda, 0xdb, 0xdc, 0xdd, 0xde):
            if val == 0xd8:
                n = rd()
                return b[pos:pos+n].decode('utf-8', errors='replace')
            if val in (0xd9, 0xda):
                n = rd()
                s = b[pos:pos+n]; pos += n
                return s.decode('utf-8', errors='replace')
            if val == 0xdb:
                n = (rd()<<24)|(rd()<<16)|(rd()<<8)|rd()
                s = b[pos:pos+n]; pos += n
                return s.decode('utf-8', errors='replace')
            return None
        return None
    return decode()

result = {}
for k, v in data.items():
    try:
        result[k] = msgpack_decode(v)
    except Exception as e:
        result[k] = f"<raw {len(v)}B: {v.hex()[:40]}...>"

import time
result.setdefault('_meta', {})['savedAt'] = time.strftime('%Y-%m-%dT%H:%M:%S')
result['_meta']['source'] = lss_dir
result['_meta']['ext_id'] = ext_id

out = Path(out_path)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding='utf-8')
print(f"[+] config-backup.json: {out} ({out.stat().st_size} bytes, {len(result)-1} keys)")
PY

cp -f "$OUT" "$EXT_DIR/config-backup.json" 2>/dev/null || true
echo "[+] Done. File: $OUT"

# ============================================================
# Запуск Chrome (если ещё не запущен) + headless CDP для dump
# ============================================================
# Запуск Chrome с флагом --remote-debugging-port=9222
# для доступа к chrome.storage.local через CDP Protocol
# (не требует установки расширения, только работа с LevelDB напрямую).

# Если расширение УЖЕ УСТАНОВЛЕНО в Chrome, хранилище находится в:
#   ~/.config/google-chrome/<profile>/Local Extension Settings/<ext-id>/
# (папка существует только после первой загрузки расширения).
# Если расширение ещё НЕ загружено — скрипт создаёт config-backup.json
# из пустого хранилища (нормальное поведение при первом запуске).
#
# ПОСЛЕ УСТАНОВКИ РАСШИРЕНИЯ: перезапустить этот скрипт —
# он найдёт новую папку и сохранит реальные данные.

# Для быстрого копирования настроек НА ДРУГОЙ КОМПЬЮТЕР:
# 1) на старом компьютере: ./save-config.sh
# 2) скопировать config-backup.json в папку расширения на новом
# 3) на новом компьютере: ./restore-config.sh
# 4) загрузить расширение — настройки будут восстановлены

echo ""
echo "============================================================"
echo " config-backup.json создан в: $OUT"
echo "============================================================"
echo " Для сохранения НАСТРОЕК ИЗ ЧУЖОГО ПК:"
echo "  1) ./save-config.sh на старом ПК"
echo "  2) скопировать config-backup.json в папку расширения"
echo "  3) ./restore-config.sh на новом ПК"

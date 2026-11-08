#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
efyt-json-host.py — native messaging host для Enhancer for YouTube (кастом, §12).

Пишет таблицу скоростей по каналам (chrome.storage.local.channelspeeds)
в настоящий JSON-файл — в папку расширения. Chrome/Chromium не даёт
расширению писать в собственный каталог, поэтому запись делает этот хост.

Протокол (native messaging, stdio): 4 байта LE длины + JSON.

Запросы:
  {"type": "ping"}                                  -> {"ok": true, "version": 1, "path": ...}
  {"type": "read"}                                  -> {"ok": true, "data": <строка|null>, "mtimeMs": int, "path": ...}
  {"type": "write", "data": "<текст JSON>"}          -> {"ok": true, "mtimeMs": int, "path": ...}

Путь к JSON-файлу: native-host/path.txt (первая строка, абсолютный путь).
Если файла конфигурации нет — пишется channelspeeds.json рядом с папкой
расширения ( ../channelspeeds.json от каталога native-host ).

Регистрация: install-native-host.sh (кладёт манифест хоста в
NativeMessagingHosts установленных браузеров и path.txt).
"""

import json
import os
import struct
import sys

HOST_NAME = "com.efyt.channelspeeds"
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "path.txt")
DEFAULT_TARGET = os.path.normpath(os.path.join(HERE, os.pardir, "channelspeeds.json"))


def target_path():
    """Путь из path.txt (первая непустая строка) либо папка расширения."""
    try:
        with open(CONFIG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    return line
    except OSError:
        pass
    return DEFAULT_TARGET


def read_msg():
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return None
    (length,) = struct.unpack("<I", raw)
    if not length:
        return None
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


def send_msg(obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def handle(msg):
    kind = msg.get("type")
    path = msg.get("path") if isinstance(msg.get("path"), str) and msg.get("path") else target_path()

    if kind == "ping":
        return {"ok": True, "version": 1, "host": HOST_NAME, "path": target_path()}

    if kind == "read":
        try:
            with open(path, encoding="utf-8") as f:
                data = f.read()
            return {"ok": True, "data": data, "mtimeMs": int(os.path.getmtime(path) * 1000), "path": path}
        except FileNotFoundError:
            return {"ok": True, "data": None, "mtimeMs": 0, "path": path}
        except Exception as exc:  # noqa: BLE001 — наверх уходит текст ошибки
            return {"ok": False, "error": str(exc), "path": path}

    if kind == "write":
        data = msg.get("data")
        if not isinstance(data, str):
            return {"ok": False, "error": "no data", "path": path}
        try:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(data)
            os.replace(tmp, path)  # атомарная перезапись
            return {"ok": True, "mtimeMs": int(os.path.getmtime(path) * 1000), "path": path}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "path": path}

    return {"ok": False, "error": "unknown type: %r" % (kind,)}


def main():
    while True:
        try:
            msg = read_msg()
        except Exception:
            break
        if msg is None:
            break
        if not isinstance(msg, dict):
            send_msg({"ok": False, "error": "bad message"})
            continue
        try:
            send_msg(handle(msg))
        except Exception as exc:  # noqa: BLE001
            try:
                send_msg({"ok": False, "error": "internal: %s" % exc})
            except Exception:
                break


if __name__ == "__main__":
    main()

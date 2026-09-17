#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скачивает плейлист IPTV по ссылке из буфера обмена и сохраняет на рабочий стол."""

import os
import sys
import time
import subprocess

DESKTOP = os.path.expanduser("~/Рабочий стол")
SAVE_DIR = os.path.join(DESKTOP, "Плейлисты")


def read_clipboard():
    """Читает текст из буфера обмена (xclip -> xsel -> copyq)."""
    for cmd in (["xclip", "-o", "-selection", "clipboard"],
                ["xsel", "-b", "-o"],
                ["copyq", "clipboard"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return ""


def download_playlist(url, path):
    """Скачивает плейлист по url в path. Возвращает (ok, сообщение)."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        return False, str(e)
    return True, ""


def main():
    url = read_clipboard()
    if not url:
        print("Буфер обмена пуст")
        input("Нажмите Enter для выхода...")
        return
    # Берём первую строку, если скопировано несколько
    url = url.splitlines()[0].strip()
    if not url.lower().startswith(("http://", "https://")):
        print(f"В буфере обмена не ссылка: {url[:80]}")
        input("Нажмите Enter для выхода...")
        return

    os.makedirs(SAVE_DIR, exist_ok=True)
    name = url.rstrip("/").split("/")[-1]
    if not name or name == "":
        name = "playlist.m3u"
    if not name.endswith((".m3u", ".m3u8", ".txt")):
        name += ".m3u"
    path = os.path.join(SAVE_DIR, name)

    print(f"Ссылка: {url}")
    print(f"Файл:   {path}")
    print("Скачиваю...")
    ok, err = download_playlist(url, path)
    if not ok:
        print(f"Ошибка скачивания: {err}")
        try:
            os.remove(path)
        except OSError:
            pass
        input("Нажмите Enter для выхода...")
        return

    size = os.path.getsize(path)
    channels = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#EXTINF"):
                channels += 1
    print(f"Готово! Размер: {size / 1024 / 1024:.2f} МБ, каналов: {channels}")
    input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()

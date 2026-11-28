#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Переупорядочивает готовый all_tv.m3u: обычный канал, затем его (+2), (+3) ...

Не удаляет и не меняет ни один канал — только меняет порядок пар EXTINF+URL.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "all_tv.m3u")
DST = os.path.join(HERE, "all_tv_sorted.m3u")

PRIORITY = [
    "первый канал", "россия 1", "нтв", "пятый канал", "россия к",
    "россия 24", "карусель", "твц", "рен тв", "спас", "стс",
    "домашний", "тв3", "пятница!", "звезда", "мир", "тнт",
]


def base_name(title):
    n = re.sub(r"\s*\(\s*\+\d+\s*\)\s*$", "", title.strip())
    n = re.sub(r"\s*(HD|SD|UHD|4K|FHD|1080p|720p)\s*$", "", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip().lower()


def ts_of(title):
    m = re.search(r"\(\s*\+(\d+)\s*\)\s*$", title.strip())
    return int(m.group(1)) if m else 0


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SRC
    dst = sys.argv[2] if len(sys.argv) > 2 else DST

    lines = io.open(src, encoding="utf-8", errors="replace").read().splitlines()
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            url = ""
            j = i + 1
            while j < len(lines) and (lines[j].startswith("#") or not lines[j].strip()):
                j += 1
            if j < len(lines):
                url = lines[j]
            title = line.rsplit(",", 1)[-1].strip()
            entries.append((line, url, title))
            i = j + 1
        else:
            i += 1

    def key(entry):
        title = entry[2]
        base = base_name(title)
        pref = next((n for n, p in enumerate(PRIORITY) if base.startswith(p)),
                    len(PRIORITY))
        group = (0, pref) if pref < len(PRIORITY) else (1, base)
        return (group, ts_of(title), base)

    entries.sort(key=key)

    with io.open(dst, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for extinf, url, _ in entries:
            f.write(extinf + "\n")
            if url:
                f.write(url + "\n")

    ts = sum(1 for e in entries if ts_of(e[2]))
    print(f"Готово: {len(entries)} каналов (из них {ts} с таймшифтом) -> {dst}")
    print("Первые 12:")
    for extinf, _, title in entries[:12]:
        print("  " + title)


if __name__ == "__main__":
    main()

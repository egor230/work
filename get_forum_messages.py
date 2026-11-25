#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сбор ВСЕХ сообщений выбранного ника на форуме https://astrovedic.ucoz.ru/forum/

При запуске скрипт спрашивает:
  1) ник участника (по умолчанию: мартагона);
  2) имя файла (по умолчанию: "все сообщения <ник>.md");
  3) папку для сохранения (по умолчанию: текущая).

Затем через встроенный поиск форума находит все сообщения participants
и сохраняет их в Markdown в хронологическом порядке.

Зависимости: requests, beautifulsoup4  (pip install requests beautifulsoup4)
"""

import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as exc:
    print("Не хватает библиотеки:", exc)
    print("Установите:  pip install requests beautifulsoup4")
    sys.exit(1)

SITE = "https://astrovedic.ucoz.ru"
SEARCH_URL = SITE + "/forum/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
DEFAULT_NICK = "мартагона"
WORKERS = 4          # параллельных запросов
RETRIES = 4          # попыток на страницу
SIGNATURE_IN_HEADER = True   # подпись один раз в начале, а не в каждом сообщении


# ---------------------------------------------------------------------------
# Преобразование HTML-тела сообщения в читаемый Markdown
# ---------------------------------------------------------------------------
def clean_text(el):
    if el is None:
        return ""
    # <br> и '</br>' (кривой HTML форума иногда охватывает остаток текста)
    for tag in el.find_all("br"):
        if len(list(tag.children)):
            tag.insert_before("\n")
            tag.append("\n")
            tag.unwrap()
        else:
            tag.replace_with("\n")
    for tag in el.find_all("p"):
        tag.insert_before("\n")
        tag.insert_after("\n")
    for tag in el.find_all(["b", "strong"]):
        tag.replace_with("**" + tag.get_text() + "**")
    for tag in el.find_all(["i", "em"]):
        tag.replace_with("*" + tag.get_text() + "*")
    # сначала картинки (они часто лежат внутри ссылок), потом ссылки
    for tag in el.find_all("img"):
        alt, src = tag.get("alt", ""), tag.get("src", "")
        tag.replace_with(f"[图像: {alt} {src}]" if src else "")
    for tag in el.find_all("a"):
        href, txt = tag.get("href", ""), tag.get_text()
        if href and not href.startswith("javascript") and txt and href != txt:
            tag.replace_with(f"[{txt}]({href})")
        else:
            tag.replace_with(txt)

    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in el.get_text().split("\n")]
    out, blanks = [], 0
    for ln in lines:
        if not ln:
            blanks += 1
            if blanks > 1:
                continue
        else:
            blanks = 0
        out.append(ln)
    return "\n".join(out).strip()


def parse_posts(html, nick):
    """Извлечь сообщения одного ника из страницы результатов поиска."""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for tr in soup.select("tr.report-spam-target"):
        user = tr.select_one("a.postUser")
        if not user or user.get_text(strip=True).lower() != nick.lower():
            continue
        header = tr.find_all("td", class_="postTdTop")[-1]
        htext = header.get_text(" ", strip=True)
        m = re.search(r"Дата:\s*(.+?)\s*\|\s*Сообщение #\s*(\d+)\s*\|\s*Тема:\s*(.*)", htext)
        if not m:
            continue
        date, num, topic = m.group(1).strip(), m.group(2), m.group(3).strip()
        link = header.find("a", class_="postNumberLink")
        url = ""
        if link:
            mo = re.search(r"window\.open\('([^']+)'", link.get("onclick", ""))
            if mo:
                url = mo.group(1)
        body = clean_text(tr.select_one("span.ucoz-forum-post"))
        sig = tr.select_one("span.signatureView")
        found.append({
            "num": int(num),
            "date": date,
            "topic": topic,
            "url": url,
            "body": body,
            "signature": clean_text(sig) if sig else "",
        })
    return found, soup


# ---------------------------------------------------------------------------
# Поиск и скачивание страниц
# ---------------------------------------------------------------------------
def start_search(nick):
    """POST-запрос поиска по автору; вернуть (html, шаблон страниц, всего страниц)."""
    r = requests.post(
        SEARCH_URL,
        data={"a": "6", "user": nick, "o1": "0", "o2": "1", "o3": "0"},
        headers=HEADERS,
        timeout=30,
    )
    r.encoding = "utf-8"
    if "Записи участника" not in r.text:
        raise RuntimeError("Поиск не вернул результаты — проверьте ник и доступность сайта")
    return r.text


def pagination_template(html):
    """Найти ссылку «следующая страница» и заменить номер страницы на {p}."""
    m = re.search(r'class="switchNext"[^>]*href="([^"]+)"', html)
    if not m:
        m = re.search(r'href="([^"]+)"[^>]*class="switchNext"', html)
    if m:
        href = m.group(1)
        if re.search(r"0-0-\d+", href):
            return urljoin(SITE, re.sub(r"0-0-\d+", "0-0-{p}", href))
    return urljoin(SITE, "/forum/0-0-{p}-42-12")  # запасной вариант


def total_pages(html):
    m = re.search(r'numPages">(\d+)', html)
    return int(m.group(1)) if m else 1


def found_count(html):
    """Число найденных сообщений из «хлебных крошек» страницы поиска."""
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one("span.breadcrumb-curr")
    if el:
        m = re.search(r"\[\s*(\d+)\s*\]", el.get_text(" ", strip=True))
        if m:
            return m.group(1)
    return "?"


def download_page(args):
    p, template, cache_dir, use_cache = args
    path = os.path.join(cache_dir, f"page_{p:04d}.html")
    if use_cache and os.path.exists(path) and os.path.getsize(path) > 20000:
        return p, open(path, encoding="utf-8").read()
    url = template.format(p=p)
    last = ""
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.encoding = "utf-8"
            if r.status_code == 200 and "report-spam-target" in r.text:
                if use_cache:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(r.text)
                return p, r.text
            last = f"HTTP {r.status_code}, размер {len(r.text)}"
        except Exception as exc:
            last = repr(exc)
        time.sleep(1.5 * (attempt + 1))
    return p, None


# ---------------------------------------------------------------------------
# Сборка Markdown
# ---------------------------------------------------------------------------
def year_of(post):
    m = re.search(r"(\d{4})", post["date"])
    return m.group(1) if m else "?"


def build_markdown(posts, nick):
    posts.sort(key=lambda x: x["num"])
    years = Counter(year_of(p) for p in posts)
    signature = posts[0]["signature"] if posts else ""
    out = []

    out.append(f"# Все сообщения участника {nick} на форуме «Кристалл Духа»")
    out.append("")
    out.append(f"> **Источник:** {SEARCH_URL}  ")
    out.append(f"> **Ник:** {nick}  ")
    out.append("> **Отбор:** встроенный поиск форума, «Все темы и сообщения» → «Список сообщений», сортировка «Сначала старые»  ")
    out.append(f"> **Количество:** {len(posts)} сообщений  ")
    out.append(f"> **Период:** {posts[0]['date']} — {posts[-1]['date']}  ")
    out.append(f"> **Собрано:** {time.strftime('%d.%m.%Y')}")
    out.append("")
    if SIGNATURE_IN_HEADER and signature:
        out.append(f"> Подпись, прилагавшаяся к сообщениям: «{signature}» (здесь — один раз, ниже не повторяется).")
        out.append("")
    out.append("## Содержание (по годам)")
    out.append("")
    out.append("| Год | Сообщений | Номера сообщений |")
    out.append("|-----|-----------|------------------|")
    for y in sorted(years):
        nums = [p["num"] for p in posts if year_of(p) == y]
        out.append(f"| {y} | {years[y]} | № {min(nums)} – № {max(nums)} |")
    out.append("")
    out.append("---")
    out.append("")

    for p in posts:
        out.append(f"### Сообщение № {p['num']}")
        out.append("")
        out.append(f"- **Дата:** {p['date']}")
        out.append(f"- **Тема:** {p['topic']}")
        if p["url"]:
            out.append(f"- **Ссылка:** {p['url']}")
        out.append("")
        body = "\n".join(("\\" + ln) if ln.startswith("#") else ln
                         for ln in p["body"].split("\n"))
        out.append(body)
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Диалог
# ---------------------------------------------------------------------------
def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    value = input(prompt + suffix + ": ").strip()
    return value or default


def safe_name(text):
    return re.sub(r'[\\/:*?"<>|]', "_", text).strip() or "forum"


def main():
    print("Сбор всех сообщений участника форума astrovedic.ucoz.ru")
    print("-" * 55)
    nick = ask("Введите ник участника", DEFAULT_NICK)
    filename = ask("Имя файла для сохранения", f"все сообщения {nick}.md")
    if not filename.lower().endswith(".md"):
        filename += ".md"
    outdir = ask("Папка для сохранения (Enter — текущая)", os.getcwd())
    outdir = os.path.expanduser(outdir)
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, filename)
    if os.path.exists(outpath):
        if ask("Файл уже существует. Перезаписать? (y/N)", "N").lower() != "y":
            print("Отменено.")
            return

    print(f"\nИщем сообщения ника «{nick}» ...")
    first_html = start_search(nick)
    template = pagination_template(first_html)
    pages = total_pages(first_html)
    total = found_count(first_html)
    print(f"Найдено страниц: {pages}, сообщений по поиску: {total}")

    cache_dir = os.path.join(outdir, ".forum_cache", safe_name(nick))
    os.makedirs(cache_dir, exist_ok=True)
    pages_html = {1: first_html}
    t0 = time.time()
    tasks = [(p, template, cache_dir, True) for p in range(2, pages + 1)]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(download_page, t) for t in tasks]
        for i, fut in enumerate(as_completed(futures), start=1):
            p, html = fut.result()
            if html is None:
                print(f"  страница {p}: НЕ загружена")
            else:
                pages_html[p] = html
            if i % 50 == 0 or i == len(futures):
                print(f"  загружено {i}/{len(futures)} за {time.time() - t0:.0f} с", flush=True)

    posts = []
    for p in sorted(pages_html):
        found, _ = parse_posts(pages_html[p], nick)
        if not found:
            print(f"  предупреждение: на странице {p} сообщений не найдено")
        posts.extend(found)
    posts.sort(key=lambda x: x["num"])
    # убрать возможные повторы при обновлении поиска
    seen, unique = set(), []
    for p in posts:
        if p["num"] not in seen:
            seen.add(p["num"])
            unique.append(p)
    posts = unique

    if not posts:
        print("Сообщения не найдены. Проверьте ник.")
        return

    with open(outpath, "w", encoding="utf-8") as f:
        f.write(build_markdown(posts, nick))

    print(f"\nГотово! Сохранено сообщений: {len(posts)}")
    print(f"Файл: {outpath}")
    print(f"Размер: {os.path.getsize(outpath) / 1024 / 1024:.2f} МБ")
    print(f"Время: {time.time() - t0:.0f} с")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Downloader (версия для РФ — с обходом блокировок YouTube).

Что умеет:
  1. Читает ссылку на YouTube из буфера обмена.
  2. Сохраняет видео в ТЕКУЩУЮ директорию запуска скрипта.
  3. Автоматически применяет несколько способов обхода ошибки
     "Sign in to confirm you're not a bot" / "HTTP Error 403: Forbidden",
     которые массово появляются в России с 2024-2025:

     • Способ 1 (быстрый): пробует разные client-стратегии yt-dlp
       (--extractor-args "youtube:player_client=..."). Часто помогает
       без cookies и без прокси — потому что YouTube блокирует не все клиенты.
     • Способ 2 (cookies): передаёт cookies из установленного браузера
       (Chrome / Edge / Firefox / Brave), где вы залогинены в Google.
       Без PO-token это снимает "Sign in to confirm you're not a bot".
     • Способ 3 (PO Token): использует плагин bgutil-ytdlp-pot-provider
       (если установлен) для генерации PO-token и обхода 403.
     • Способ 4 (прокси): если у вас VPN/proxy — можно указать его
       через переменную окружения YT_PROXY или флагом --proxy.
     • Способ 5 (Tor): последняя попытка через SOCKS5 Tor на 127.0.0.1:9050
       (если Tor запущен).
     • Fallback: пробует просто обновить yt-dlp до nightly и скачать заново.

ЗАВИСИМОСТИ:
    pip install --upgrade yt-dlp pyperclip --break-system-packages
    # по желанию, для PO Token:
    pip install bgutil-ytdlp-pot-provider --break-system-packages
    # по желанию, для Tor:
    sudo apt install tor

БРАУЗЕРНЫЕ COOKIES:
    Скрипт сам найдёт ваш браузер и возьмёт cookies. Чтобы это работало,
    вы должны быть залогинены в Google/YouTube в одном из браузеров:
    Chrome / Edge / Firefox / Brave / Chromium.

ИСПОЛЬЗОВАНИЕ:
    python3 youtube_downloader.py            # берёт ссылку из буфера
    python3 youtube_downloader.py <URL>      # URL из аргумента
    YT_PROXY=socks5://127.0.0.1:9050 python3 youtube_downloader.py
"""

import os
import sys
import re
import shutil
import subprocess
import argparse
import time


# ---------- Проверка зависимостей ----------

try:
    import pyperclip
except ImportError:
    print("ОШИБКА: библиотека pyperclip не установлена.")
    print("        pip install pyperclip --break-system-packages")
    sys.exit(1)


# ---------- Константы ----------

YOUTUBE_RE = re.compile(
    r'(https?://)?(www\.|m\.)?'
    r'(youtube\.com/(watch\?v=|shorts/|embed/|v/|live/)|youtu\.be/)'
    r'[\w\-]{6,}',
    re.IGNORECASE,
)

# Клиенты yt-dlp, которые часто проходят там, где default-клиент блокирован.
# Порядок важен — перебираем от самого лёгкого к самому тяжёлому.
# Источник: github.com/yt-dlp/yt-dlp/issues (диагностика по РФ и 403).
PLAYER_CLIENT_STRATEGIES = [
    # tv_embedded — раньше всех проходит "Sign in to confirm"
    "tv_embedded",
    # web_safari / web_edge — иногда YouTube режет только chromium
    "web_safari",
    "web_edge",
    # mweb — мобильный клиент, не во всех регионах блочится
    "mweb",
    # web_creator — проходит, если в аккаунте есть канал
    "web_creator",
    # combinations
    "default,tv",
    "default,web_safari,tv_embedded",
    # фолбэк — обычный default
    "default",
]

# Браузеры для --cookies-from-browser (порядок важен).
BROWSERS = ["chrome", "edge", "firefox", "brave", "chromium", "vivaldi", "opera"]

# Таймаут на одну попытку (секунды). Скачивание длинного видео может быть долгим,
# поэтому таймаут задаём только на этап Metadata (чтобы быстро отвалиться по 403).
METADATA_TIMEOUT = 60


# ---------- Поиск yt-dlp ----------

# Минимально допустимая версия yt-dlp. YouTube часто меняет антибот-логику,
# версии старше ~3 месяцев уже не справляются с 403.
# Формат: YYYY.MM.DD
MIN_VERSION = "2025.06.01"

ALL_CANDIDATE_PATHS = [
    os.path.expanduser('~/.local/bin/yt-dlp'),    # pip --user (приоритет!)
    os.path.expanduser('~/.venv/bin/yt-dlp'),
    '/usr/local/bin/yt-dlp',
    '/usr/bin/yt-dlp',                            # apt — обычно самая старая
    shutil.which('yt-dlp'),                       # что найдено в PATH
]


def parse_version(version_str):
    """Преобразовать '2026.07.04' или 'nightly@2026.07.06.234510' в tuple (y, m, d)."""
    import re as _re
    m = _re.search(r'(\d{4})\.(\d{2})\.(\d{2})', version_str or '')
    if not m:
        return (0, 0, 0)
    return tuple(int(x) for x in m.groups())


def yt_dlp_version(yt_dlp):
    """Вернуть строку с версией yt-dlp."""
    try:
        out = subprocess.run(
            [yt_dlp, '--version'],
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.strip().split('\n')[0]
    except Exception:
        return 'unknown'


def find_all_yt_dlp():
    """Найти ВСЕ установленные yt-dlp и вернуть [(path, version_str), ...]."""
    seen = set()
    found = []
    for path in ALL_CANDIDATE_PATHS:
        if not path:
            continue
        path = os.path.realpath(path)
        if path in seen:
            continue
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            continue
        seen.add(path)
        ver = yt_dlp_version(path)
        found.append((path, ver))
    return found


def pick_best_yt_dlp(installed):
    """Выбрать самую свежую версию yt-dlp из списка."""
    if not installed:
        return None
    # сортируем по версии — самая свежая первой
    installed_sorted = sorted(
        installed,
        key=lambda p: parse_version(p[1]),
        reverse=True,
    )
    return installed_sorted[0][0]


def install_fresh_yt_dlp():
    """Поставить/обновить yt-dlp через pip в user-site.
    Игнорирует системный apt-пакет."""
    print("→ Устанавливаю свежий yt-dlp через pip (--user --ignore-installed)...")
    cmd = [
        sys.executable, '-m', 'pip', 'install',
        '--upgrade', '--user', '--ignore-installed',
        'yt-dlp',
    ]
    try:
        subprocess.run(cmd, timeout=180, check=False)
    except subprocess.TimeoutExpired:
        print("  таймаут pip install")
    except Exception as e:
        print(f"  ошибка pip: {e}")
    # после установки — обновим nightly
    pip_yt_dlp = os.path.expanduser('~/.local/bin/yt-dlp')
    if os.path.isfile(pip_yt_dlp):
        print("→ Обновляю до nightly (это часто чинит 403 само по себе)...")
        try:
            subprocess.run(
                [pip_yt_dlp, '-U', '--update-to', 'nightly'],
                timeout=120, check=False,
            )
        except Exception:
            pass
    return pip_yt_dlp if os.path.isfile(pip_yt_dlp) else None


def ensure_yt_dlp():
    """Гарантировать, что у нас свежий yt-dlp. Вернуть путь к бинарнику."""
    installed = find_all_yt_dlp()
    if installed:
        print("\nНайдены установленные yt-dlp:")
        for path, ver in installed:
            tag = ""
            if "apt" in path or path.startswith("/usr/bin/"):
                tag = "  ← системный apt (обычно устаревший)"
            elif "/.local/" in path:
                tag = "  ← pip --user (рекомендуемый)"
            print(f"  • {path}  →  {ver}{tag}")

    best = pick_best_yt_dlp(installed) if installed else None
    best_ver = yt_dlp_version(best) if best else 'unknown'

    # Проверим свежесть
    if parse_version(best_ver) < parse_version(MIN_VERSION):
        print(f"\nВерсия {best_ver} слишком старая (нужно ≥ {MIN_VERSION}).")
        print("Старые версии yt-dlp (особенно apt@2024.04) НЕ работают с YouTube —")
        print("именно это и вызывает у вас ошибку 403.")
        fresh = install_fresh_yt_dlp()
        if fresh:
            best = fresh
            best_ver = yt_dlp_version(fresh)
            print(f"\n✓ Установлена версия: {best_ver}")
            print(f"  путь: {best}")
        else:
            print("\n✗ Не удалось установить свежий yt-dlp через pip.")
    else:
        print(f"\nБуду использовать: {best} ({best_ver})")

    return best


# ---------- Буфер обмена ----------

def get_url_from_clipboard():
    """Получить YouTube-ссылку из буфера обмена."""
    try:
        text = pyperclip.paste()
    except Exception as e:
        print(f"Не удалось прочитать буфер обмена: {e}")
        return None
    if not text:
        return None

    match = YOUTUBE_RE.search(text.strip())
    if match:
        url = match.group(0)
        if not url.startswith('http'):
            url = 'https://' + url
        return url

    first_line = text.strip().splitlines()[0] if text.strip() else ''
    if first_line.startswith(('http://', 'https://')) and 'youtube' in first_line.lower():
        return first_line

    return None


# ---------- Запуск yt-dlp ----------

def run_yt_dlp(yt_dlp, args, cwd, timeout=None, label=""):
    """Запустить yt-dlp с заданными аргументами, вернуть (ok, output)."""
    cmd = [yt_dlp] + args
    if label:
        print(f"\n▶ Попытка: {label}")
    print("  " + " ".join(cmd[:12]) + (" ..." if len(cmd) > 12 else ""))
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, timeout=timeout,
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            return True, proc.stdout
        else:
            tail = (proc.stderr or proc.stdout or '')[-800:]
            print(f"  ✗ провал (rc={proc.returncode})")
            if tail.strip():
                print("  последние строки лога:")
                for line in tail.strip().splitlines()[-6:]:
                    print("    " + line)
            return False, proc.stderr or proc.stdout
    except subprocess.TimeoutExpired:
        print(f"  ✗ таймаут ({timeout}s)")
        return False, "timeout"
    except KeyboardInterrupt:
        print("\n  прервано пользователем")
        raise
    except Exception as e:
        print(f"  ✗ исключение: {e}")
        return False, str(e)


def try_metadata_only(yt_dlp, url, args, cwd):
    """Быстрая проверка — пройти ли youtube-экстрактор.
    Если падает на 403/sign-in — нет смысла начинать скачивание."""
    test_args = args + ['--skip-download', '--no-warnings', url]
    ok, _ = run_yt_dlp(yt_dlp, test_args, cwd, timeout=METADATA_TIMEOUT,
                       label="метаданные (проверка доступности)")
    return ok


# ---------- Стратегии обхода ----------

def strategy_client_variants(yt_dlp, url, output_dir):
    """Способ 1: перебор player_client."""
    print("\n=== Способ 1: перебор extractor-args player_client ===")
    output_template = os.path.join(output_dir, '%(title).200B [%(id)s].%(ext)s')
    base = [
        '--no-playlist',
        '-f', 'bestvideo+bestaudio/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--no-mtime',
        '--newline',
        '--no-cache-dir',
    ]
    for client in PLAYER_CLIENT_STRATEGIES:
        args = base + [
            '--extractor-args', f'youtube:player_client={client}',
        ]
        ok, _ = run_yt_dlp(yt_dlp, args + [url], output_dir, label=f"player_client={client}")
        if ok:
            return True
    return False


def strategy_with_cookies(yt_dlp, url, output_dir):
    """Способ 2: cookies из браузера."""
    print("\n=== Способ 2: cookies из браузера ===")
    output_template = os.path.join(output_dir, '%(title).200B [%(id)s].%(ext)s')
    base = [
        '--no-playlist',
        '-f', 'bestvideo+bestaudio/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--no-mtime',
        '--newline',
        '--no-cache-dir',
    ]
    for browser in BROWSERS:
        # проверим, что браузер хотя бы детектится
        args = base + [f'--cookies-from-browser', browser]
        ok, _ = run_yt_dlp(
            yt_dlp, args + [url], output_dir,
            label=f"cookies-from-browser={browser}",
        )
        if ok:
            return True
    return False


def strategy_with_pot(yt_dlp, url, output_dir):
    """Способ 3: PO Token через плагин bgutil-ytdlp-pot-provider."""
    print("\n=== Способ 3: PO Token (bgutil-ytdlp-pot-provider) ===")
    # Проверим наличие плагина
    try:
        import bgutil_ytdlp_pot_provider  # noqa
    except ImportError:
        print("  плагин bgutil-ytdlp-pot-provider не установлен.")
        print("  установка: pip install bgutil-ytdlp-pot-provider --break-system-packages")
        return False
    output_template = os.path.join(output_dir, '%(title).200B [%(id)s].%(ext)s')
    args = [
        '--no-playlist',
        '-f', 'bestvideo+bestaudio/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--no-mtime',
        '--newline',
        '--no-cache-dir',
        url,
    ]
    ok, _ = run_yt_dlp(yt_dlp, args, output_dir, label="PO Token plugin")
    return ok


def strategy_with_proxy(yt_dlp, url, output_dir, proxy):
    """Способ 4: прокси/VPN."""
    print(f"\n=== Способ 4: прокси ({proxy}) ===")
    output_template = os.path.join(output_dir, '%(title).200B [%(id)s].%(ext)s')
    args = [
        '--no-playlist',
        '--proxy', proxy,
        '-f', 'bestvideo+bestaudio/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--no-mtime',
        '--newline',
        '--no-cache-dir',
        url,
    ]
    ok, _ = run_yt_dlp(yt_dlp, args, output_dir, label=f"proxy={proxy}")
    return ok


def strategy_with_tor(yt_dlp, url, output_dir):
    """Способ 5: Tor SOCKS5 на 127.0.0.1:9050 (если запущен)."""
    print("\n=== Способ 5: Tor SOCKS5 (127.0.0.1:9050) ===")
    # Проверим, что Tor слушает порт
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect(('127.0.0.1', 9050))
        sock.close()
    except Exception:
        print("  Tor не запущен на 127.0.0.1:9050. Пропускаю.")
        print("  чтобы включить: sudo apt install tor && sudo service tor start")
        return False
    return strategy_with_proxy(yt_dlp, url, output_dir, 'socks5://127.0.0.1:9050')


# ---------- Главная функция ----------

def main():
    parser = argparse.ArgumentParser(
        description='YouTube Downloader с обходом блокировок (РФ).',
        add_help=True,
    )
    parser.add_argument('url', nargs='?', help='URL YouTube (если не задан — берётся из буфера)')
    parser.add_argument('--proxy', help='прокси в формате socks5://host:port или http://host:port')
    parser.add_argument('--update', action='store_true', help='переустановить yt-dlp до свежей nightly и выйти')
    args = parser.parse_args()

    print("=" * 64)
    print("  YouTube Downloader — версия для РФ (обход 403 / sign-in)")
    print("=" * 64)

    # Директория сохранения — откуда запущен скрипт
    output_dir = os.getcwd()
    print(f"Папка сохранения: {output_dir}")

    # Поиск И установка свежего yt-dlp (главная причина 403 — старая версия!)
    yt_dlp = ensure_yt_dlp()
    if not yt_dlp:
        print("\nОШИБКА: yt-dlp не найден и не установлен.")
        print("Установите вручную:")
        print("  pip install --upgrade --user --ignore-installed yt-dlp")
        print("  # затем:")
        print("  ~/.local/bin/yt-dlp --update-to nightly")
        sys.exit(1)

    if args.update:
        install_fresh_yt_dlp()
        sys.exit(0)

    # Получаем URL
    url = args.url or get_url_from_clipboard()
    if not url:
        print("\nВ буфере обмена нет YouTube-ссылки.")
        print("Скопируйте ссылку на видео, либо передайте её аргументом:")
        print("  python3 youtube_downloader.py 'https://youtube.com/watch?v=...'")
        sys.exit(1)

    print(f"URL: {url}")

    # Прокси из аргумента или из окружения
    proxy = args.proxy or os.environ.get('YT_PROXY')

    # ---------- Перебор стратегий ----------
    # Порядок: сначала бесплатные и быстрые (client-variants), потом
    # cookies (нужен залогиненный браузер), потом PO Token, потом proxy/Tor.

    strategies = [
        lambda: strategy_client_variants(yt_dlp, url, output_dir),
        lambda: strategy_with_cookies(yt_dlp, url, output_dir),
        lambda: strategy_with_pot(yt_dlp, url, output_dir),
    ]
    if proxy:
        strategies.append(lambda: strategy_with_proxy(yt_dlp, url, output_dir, proxy))
    strategies.append(lambda: strategy_with_tor(yt_dlp, url, output_dir))

    for i, strat in enumerate(strategies, 1):
        try:
            if strat():
                print("\n" + "=" * 64)
                print(f"  ✓ УСПЕХ! Видео сохранено в: {output_dir}")
                print("=" * 64)
                sys.exit(0)
        except KeyboardInterrupt:
            print("\nПрервано пользователем.")
            sys.exit(130)
        # между попытками — пауза, чтобы YouTube не пометил как бот-флуд
        time.sleep(2)

    # ---------- Всё провалилось ----------
    print("\n" + "=" * 64)
    print("  ✗ Все автоматические стратегии не сработали.")
    print("=" * 64)
    print("""
Ручные рекомендации:

1) Откройте youtube.com в Chrome/Edge/Firefox и залогиньтесь в Google.
   Затем перезапустите скрипт — способ №2 (cookies-from-browser) должен пройти.

2) Обновите yt-dlp до самой свежей nightly:
       yt-dlp -U --update-to nightly

3) Установите плагин PO Token:
       pip install bgutil-ytdlp-pot-provider --break-system-packages

4) Если ваш IP в РФ заблокирован YouTube — поднимите VPN/прокси и:
       YT_PROXY=socks5://127.0.0.1:1080 python3 youtube_downloader.py
   или:
       python3 youtube_downloader.py --proxy http://127.0.0.1:8080

5) Альтернатива — Tor:
       sudo apt install tor && sudo service tor start
   затем снова запустите этот скрипт (он сам попробует 127.0.0.1:9050).
""")
    sys.exit(1)


if __name__ == '__main__':
    main()

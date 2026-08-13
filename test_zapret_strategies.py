#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование стратегий zapret на конкретном YouTube-видео.

Для каждой стратегии из папки zapret:
  1. запускает zapret через service.sh
  2. дожидается, пока youtube.com отвечает
  3. через yt-dlp получает прямую ссылку на поток видео (googlevideo.com)
  4. качает первые ~8 МБ потока и измеряет реальную скорость (МБ/с)
  5. выбирает стратегию с максимальной скоростью и сохраняет её в conf.ini

Требования:
  - запуск от пользователя egor (sudo -n должен работать без пароля)
  - установлен yt-dlp, curl

Запуск:
  python3 test_zapret_strategies.py
  python3 test_zapret_strategies.py --video "https://www.youtube.com/watch?v=ZO764VPloRU"
  python3 test_zapret_strategies.py --only general_alt9.bat general_alt10.bat
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

# ----------------------------------------------------------------------------
# Конфигурация путей
# ----------------------------------------------------------------------------
SCRIPT_DIR = "/home/egor/Downloads/zapret-discord-youtube-linux"
SERVICE_SH = os.path.join(SCRIPT_DIR, "service.sh")
CONF_INI = os.path.join(SCRIPT_DIR, "conf.ini")
VIDEO_URL = "https://www.youtube.com/watch?v=ZO764VPloRU"

# Параметры тестирования
READY_TIMEOUT = 18       # сколько ждать появления youtube.com (с)
READY_POLL = 2           # интервал опроса (с)
YT_DLP_TIMEOUT = 30      # таймаут получения прямой ссылки
SPEED_TEST_BYTES = 8 * 1024 * 1024   # качаем первые 8 МБ потока
SPEED_TEST_TIMEOUT = 25  # таймаут скачивания куска
BETWEEN_WAIT = 2         # пауза после остановки перед следующей стратегией

LOG_FILE = "/tmp/opencode/zapret_strategy_test.json"

YT_DLP = shutil.which("yt-dlp") or "yt-dlp"


def sudo_prefix():
    if os.geteuid() == 0:
        return []
    return ["sudo"]


def run(cmd, timeout=60, capture=True, check=False):
    """Запуск команды (с sudo при необходимости)."""
    full = sudo_prefix() + cmd
    try:
        res = subprocess.run(
            full,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            text=True,
            timeout=timeout,
        )
        return res
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(e.cmd, 124, "", "timeout")


def get_strategies():
    res = run([SERVICE_SH, "strategy", "list"], timeout=30)
    out = res.stdout or ""
    strat = [l.strip() for l in out.splitlines() if l.strip().endswith(".bat")]
    # убираем дубли (custom <-> repo) и сортируем
    seen = []
    for s in strat:
        if s not in seen:
            seen.append(s)
    return seen


_running_proc = None


def stop_zapret():
    global _running_proc
    if _running_proc is not None:
        try:
            _running_proc.terminate()
            _running_proc.wait(timeout=5)
        except Exception:
            try:
                _running_proc.kill()
            except Exception:
                pass
        _running_proc = None
    # гарантированная остановка nfqws + очистка nftables
    run([SERVICE_SH, "kill"], timeout=30)
    time.sleep(BETWEEN_WAIT)


def start_strategy(name):
    """Запускает стратегию в фоне (service.sh run висит в sleep infinity)."""
    global _running_proc
    stop_zapret()
    _running_proc = subprocess.Popen(
        sudo_prefix() + [SERVICE_SH, "run", "-s", name, "-i", "any"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_youtube_ready():
    """Ждёт, пока https://www.youtube.com вернёт 2xx/3xx. Возвращает (ok, sec)."""
    deadline = time.time() + READY_TIMEOUT
    first = None
    while time.time() < deadline:
        t0 = time.time()
        res = run(
            ["curl", "-s", "-o", "/dev/null", "-L",
             "--max-time", "6",
             "-w", "%{http_code}",
             "https://www.youtube.com"],
            timeout=10,
        )
        code = (res.stdout or "").strip()
        if first is None:
            first = time.time() - t0
        if code and code[0] in ("2", "3"):
            return True, (time.time() - t0)
        time.sleep(READY_POLL)
    return False, READY_TIMEOUT


def get_stream_url(video_url):
    """Возвращает прямую ссылку на поток видео через yt-dlp (с повторами)."""
    for attempt in range(3):
        for fmt in ("best[height<=720]", "best"):
            res = run(
                [YT_DLP, "--no-warnings", "--no-playlist",
                 "--get-url", "-f", fmt, video_url],
                timeout=YT_DLP_TIMEOUT,
            )
            if res.returncode == 0 and res.stdout and "googlevideo" in res.stdout:
                return res.stdout.strip().splitlines()[0]
        time.sleep(3)  # YouTube иногда шлёт "confirm you're not a bot" — повтор
    return None


def measure_speed(url):
    """Качает первые SPEED_TEST_BYTES и возвращает (mbps, sec, http_code)."""
    res = run(
        ["curl", "-s", "-L", "-g",
         "--max-time", str(SPEED_TEST_TIMEOUT),
         "-r", f"0-{SPEED_TEST_BYTES - 1}",
         "-o", "/dev/null",
         "-w", "%{speed_download} %{time_total} %{http_code}",
         url],
        timeout=SPEED_TEST_TIMEOUT + 10,
    )
    out = (res.stdout or "").strip()
    try:
        speed_bps, ttotal, code = out.split()
        speed_bps = float(speed_bps)
        ttotal = float(ttotal)
        mbps = speed_bps / (1024 * 1024)
        return mbps, ttotal, code
    except Exception:
        return 0.0, 0.0, (out.split()[-1] if out else "000")


def test_strategy(name, video_url):
    print(f"\n=== Стратегия: {name} ===", flush=True)
    start_strategy(name)
    ready, rtime = wait_youtube_ready()
    if not ready:
        print("  youtube.com недоступен -> стратегия не работает", flush=True)
        stop_zapret()
        return {"name": name, "ready": False, "speed_mbps": 0.0,
                "comment": "youtube.com недоступен"}

    print(f"  youtube.com доступен за {rtime:.1f} с", flush=True)
    # небольшая пауза, чтобы стабилизировался маршрут (googlevideo)
    time.sleep(5)
    url = get_stream_url(video_url)
    if not url:
        print("  не удалось получить ссылку на поток (yt-dlp) -> видео заблокировано",
              flush=True)
        stop_zapret()
        return {"name": name, "ready": True, "speed_mbps": 0.0,
                "comment": "yt-dlp не дал ссылку"}

    mbps, ttotal, code = measure_speed(url)
    print(f"  поток: HTTP {code}, скорость {mbps:.2f} МБ/с за {ttotal:.1f} с",
          flush=True)
    stop_zapret()
    return {"name": name, "ready": True, "speed_mbps": round(mbps, 3),
            "code": code, "comment": "ok" if mbps > 0.2 else "слишком медленно"}


def save_best(results):
    working = [r for r in results if r.get("speed_mbps", 0) > 0.2]
    if not working:
        print("\nНи одна стратегия не дала рабочую скорость видео.", flush=True)
        return None
    working.sort(key=lambda r: r["speed_mbps"], reverse=True)
    best = working[0]
    with open(CONF_INI, "w") as f:
        f.write(best["name"] + "\n")
    print(f"\nЛучшая стратегия: {best['name']} ({best['speed_mbps']:.2f} МБ/с)")
    print(f"Сохранена в {CONF_INI}")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=VIDEO_URL)
    ap.add_argument("--only", nargs="*", default=None,
                    help="протестировать только эти стратегии (.bat)")
    ap.add_argument("--no-save", action="store_true",
                    help="не перезаписывать conf.ini")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    strats = get_strategies()
    if args.only:
        strats = [s for s in strats if s in args.only]
    if not strats:
        print("Стратегии не найдены.", file=sys.stderr)
        sys.exit(1)

    print(f"Будет протестировано стратегий: {len(strats)}")
    print("Видео:", args.video)

    results = []
    try:
        for name in strats:
            results.append(test_strategy(name, args.video))
    except KeyboardInterrupt:
        print("\nПрервано пользователем.", flush=True)
    finally:
        stop_zapret()

    # итоговая таблица
    results.sort(key=lambda r: r.get("speed_mbps", 0), reverse=True)
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ (по убыванию скорости):")
    print(f"{'Стратегия':<34}{'готовность':<12}{'МБ/с':<10}комментарий")
    print("-" * 60)
    for r in results:
        ready = "да" if r.get("ready") else "нет"
        spd = f"{r.get('speed_mbps', 0):.2f}" if r.get("ready") else "-"
        print(f"{r['name']:<34}{ready:<12}{spd:<10}{r.get('comment', '')}")

    with open(LOG_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    if not args.no_save:
        save_best(results)

    print(f"\nЛог сохранён: {LOG_FILE}")


if __name__ == "__main__":
    main()

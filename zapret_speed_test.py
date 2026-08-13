#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест скорости видео YouTube для каждой стратегии zapret.
Показывает, какая стратегия даёт самую быструю загрузку ролика.

Принцип (как в ручном тесте):
  1. Разрешаем прямую ссылку на видео через yt-dlp под заведомо рабочей стратегией.
  2. Эту же ссылку качаем через curl под КАЖДОЙ стратегией (одинаковый CDN-узел -
     честное сравнение), замеряем реальную скорость в байтах/сек.
  3. Стратегии, которые не могут скачать (http 000) - помечаем FAILED.
  4. Выводим таблицу, отсортированную по медианной скорости.

Требования: sudo без пароля (или с паролем), yt-dlp, curl.
"""

import argparse
import os
import subprocess
import sys
import time

ZAPRET_DIR = "/home/egor/Downloads/zapret-discord-youtube-linux"
SERVICE_SH = os.path.join(ZAPRET_DIR, "service.sh")
STRATEGIES_DIR = os.path.join(ZAPRET_DIR, "custom-strategies")
DEFAULT_VIDEO = "https://www.youtube.com/watch?v=ZO764VPloRU"
WARMUP_STRATEGIES = ["general_alt12.bat", "general_alt.bat", "general_exp.bat", "general_simple_fake.bat"]


def run_cmd(cmd, timeout=None):
    """Выполнить команду. Вернуть (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -2, "", "not found"


def list_strategies():
    """Список .bat стратегий из каталога zapret."""
    if not os.path.isdir(STRATEGIES_DIR):
        print(f"ОШИБКА: каталог стратегий не найден: {STRATEGIES_DIR}")
        sys.exit(1)
    names = sorted(f for f in os.listdir(STRATEGIES_DIR) if f.endswith(".bat"))
    if not names:
        print("ОШИБКА: нет .bat стратегий в", STRATEGIES_DIR)
        sys.exit(1)
    return names


def stop_zapret():
    """Полная остановка zapret (все воркеры + nfqws + правила)."""
    run_cmd(["sudo", "pkill", "-9", "-f", "service.sh ru[n]"])
    run_cmd(["sudo", "pkill", "-9", "-x", "nfqws"])
    run_cmd(["sudo", "pkill", "-9", "-x", "tpws"])
    time.sleep(2)
    run_cmd(["sudo", SERVICE_SH, "kill"])
    time.sleep(1)


def start_strategy(name, wait=5):
    """Запустить стратегию в фоне. Вернуть объект процесса."""
    p = subprocess.Popen(
        ["sudo", SERVICE_SH, "run", "-s", name, "-i", "any"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(wait)
    return p


def resolve_video_url(video, fmt):
    """Разрешить прямую ссылку на видео через yt-dlp."""
    cmd = ["yt-dlp", "--no-warnings", "-f", fmt, "-g", video]
    rc, out, err = run_cmd(cmd, timeout=60)
    if rc != 0:
        return None
    urls = [l for l in out.splitlines() if l.startswith("http")]
    return urls[-1] if urls else None


RANGE = "0-200000000"  # качаем с Range, чтобы получить 206 вместо 302 (youtube отдаёт 302 без Range)


def curl_measure(url, seconds):
    """Скачать url указанное время. Вернуть (http_code, speed_bps).

    Range обязателен: без него youtube отдаёт 302 и скорость не мерится.
    curl вернёт rc=28 (timeout) когда окно замера истекло - это НОРМАЛЬНО
    (ролик качается весь, мы намеренно обрываем). Важен только вывод -w.
    """
    cmd = ["curl", "-sL", "-r", RANGE, "-o", "/dev/null",
           "-w", "%{http_code} %{speed_download}",
           "--max-time", str(seconds), url]
    rc, out, err = run_cmd(cmd, timeout=seconds + 10)
    parts = out.split()
    if rc in (-1, -2) or len(parts) < 2:
        return "000", 0.0
    try:
        return parts[0], float(parts[1])
    except ValueError:
        return "000", 0.0


def is_ok(code):
    """200 или 206 = успешная закачка."""
    return code in ("200", "206")


def median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def mbps(bps):
    return bps / (1024 * 1024)


def main():
    ap = argparse.ArgumentParser(
        description="Скорость YouTube-видео для каждой стратегии zapret",
        formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--video", default=DEFAULT_VIDEO,
                    help="URL ролика (по умолчанию тестовый)")
    ap.add_argument("--format", default="18",
                    help="Формат видео (по умолчанию 18 = 360p)")
    ap.add_argument("--duration", type=int, default=6,
                    help="Длительность замера, сек (по умолчанию 6)")
    ap.add_argument("--runs", type=int, default=2,
                    help="Количество замеров на стратегию (по умолчанию 2)")
    ap.add_argument("--warmup", type=int, default=3,
                    help="Прогрев соединения, сек (по умолчанию 3)")
    ap.add_argument("--only", default="",
                    help="Тестировать только эти стратегии (через запятую)")
    ap.add_argument("--zapret-dir", default=ZAPRET_DIR,
                    help=f"Каталог zapret (по умолчанию {ZAPRET_DIR})")
    args = ap.parse_args()

    global SERVICE_SH, STRATEGIES_DIR
    SERVICE_SH = os.path.join(args.zapret_dir, "service.sh")
    STRATEGIES_DIR = os.path.join(args.zapret_dir, "custom-strategies")

    strategies = list_strategies()
    if args.only:
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        strategies = [s for s in strategies if s in wanted]
        if not strategies:
            print("ОШИБКА: ни одной стратегии из --only не найдено")
            sys.exit(1)

    print(f"zapret:    {args.zapret_dir}")
    print(f"видео:     {args.video}")
    print(f"формат:    {args.format}, замер: {args.duration}с x {args.runs}, прогрев: {args.warmup}с")
    print(f"стратегий: {len(strategies)}")
    print()

    # --- 1. Останавливаем zapret и разрешаем прямую ссылку под рабочей стратегией ---
    stop_zapret()
    url = None
    for warm in WARMUP_STRATEGIES:
        if warm not in strategies and warm not in ["general_alt12.bat", "general_alt.bat",
                                                    "general_exp.bat", "general_simple_fake.bat"]:
            continue
        print(f"[1/3] Разрешаю ссылку на видео (прогрев: {warm}) ...")
        start_strategy(warm, wait=5)
        for attempt in range(3):
            url = resolve_video_url(args.video, args.format)
            if url:
                code, _ = curl_measure(url, min(args.duration, 4))
                if is_ok(code):
                    break
                url = None
            time.sleep(2)
        stop_zapret()
        if url:
            print("      Ссылка получена:", url.split("?")[0])
            break

    if not url:
        print("ОШИБКА: не удалось получить рабочую ссылку на видео. Проверьте yt-dlp и сеть.")
        sys.exit(1)

    # --- 2. Тестируем каждую стратегию ---
    print(f"\n[2/3] Тестирую {len(strategies)} стратегий ...\n")
    results = []
    total = len(strategies)
    for idx, name in enumerate(strategies, 1):
        stop_zapret()
        proc = start_strategy(name)
        # прогрев соединения
        curl_measure(url, args.warmup)
        speeds, codes = [], set()
        for _ in range(args.runs):
            code, spd = curl_measure(url, args.duration)
            codes.add(code)
            speeds.append(int(spd))
            time.sleep(1)
        proc.terminate()
        ok = any(is_ok(c) for c in codes) and max(speeds, default=0) > 0
        results.append({
            "name": name, "ok": ok, "codes": codes,
            "max": max(speeds, default=0), "med": median(speeds),
            "runs": speeds,
        })
        print(f"  [{idx}/{total}] {name:<42} "
              f"{'OK ' if ok else 'FAIL'} max={mbps(results[-1]['max']):.1f} "
              f"med={mbps(results[-1]['med']):.1f} МБ/с", flush=True)

    # --- 3. Итоговая таблица ---
    stop_zapret()
    ok_results = [r for r in results if r["ok"]]
    bad_results = [r for r in results if not r["ok"]]

    print("\n" + "=" * 92)
    print("ИТОГ (сортировка по медиане скорости):")
    print("=" * 92)
    print(f"  {'Стратегия':<42} {'Пик':>8} {'Мед':>8}  Замеры, МБ/с")
    print("-" * 92)
    for r in sorted(ok_results, key=lambda x: (-x["med"], -x["max"])):
        runs = " ".join(f"{mbps(s):.1f}" for s in r["runs"])
        print(f"  {r['name']:<42} {mbps(r['max']):>7.1f} {mbps(r['med']):>7.1f}  {runs}")

    if bad_results:
        print("\nНЕ РАБОТАЮТ С ВИДЕО (http 000 - поток заблокирован):")
        print("-" * 92)
        for r in sorted(bad_results, key=lambda x: x["name"]):
            print(f"  {r['name']:<42} коды: {sorted(r['codes'])}")

    if ok_results:
        best = max(ok_results, key=lambda x: x["med"])
        print("\n" + "=" * 92)
        print(f"ЛУЧШАЯ СТРАТЕГИЯ: {best['name']} "
              f"(медиана {mbps(best['med']):.1f} МБ/с, пик {mbps(best['max']):.1f} МБ/с)")
        print(f"Запуск:  sudo {SERVICE_SH} run -s {best['name']} -i any")
        print("=" * 92)


if __name__ == "__main__":
    main()

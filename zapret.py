import os, sys, subprocess, time, tempfile, re, shutil, pathlib, datetime
from datetime import datetime

DIR = pathlib.Path("/home/egor/Загрузки/zapret-discord-youtube-linux")
SERVICE_SCRIPT = DIR / "service.sh"
CONF_FILE = DIR / "conf.env"
RESULTS_FILE = DIR / "auto_tune_youtube_results.txt"

WAIT_TIME = 2      # после запуска стратегии
CURL_TIMEOUT = 3

def print_header():
    print("================================================================")
    print("           YouTube Unblocker (ХМАО)  (Python-версия)           ")
    print("               + Auto Tune стратегий                           ")
    print("================================================================")
    print("")

def run_cmd(cmd, check=False, capture_output=True, text=True, shell=False, sudo=False, cwd=None):
    if sudo:
        cmd = ["sudo"] + cmd
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=text,
            shell=shell,
            cwd=cwd
        )
        return result
    except subprocess.CalledProcessError as e:
        if not check:
            return e
        raise

def check_programs(programs):
    missing = []
    for prog in programs:
        if prog == "nftables":
            if not (shutil.which("nft") or shutil.which("iptables") or pathlib.Path("/usr/sbin/nft").exists()):
                missing.append(prog)
        else:
            if not shutil.which(prog):
                missing.append(prog)
    return missing

def install_dependencies():
    print("[Установка зависимостей]")
    run_cmd(["apt", "update", "-y"], sudo=True)
    run_cmd(["apt", "install", "-y", "git", "curl", "nftables"], sudo=True)

def clone_repo():
    if not DIR.exists():
        print("-> Клонируем репозиторий...")
        run_cmd(["git", "clone", "--depth=1",
                 "https://github.com/Sergeydigl3/zapret-discord-youtube-linux.git",
                 str(DIR)])
    else:
        print("-> Репозиторий уже есть")

def prepare_scripts():
    os.chdir(DIR)
    for pattern in ["service.sh", "auto_tune_youtube.sh", "src/lib/*.sh", "src/cli/*.sh"]:
        for f in pathlib.Path(".").glob(pattern):
            f.chmod(0o755)

def download_deps_if_needed():
    if not (DIR / "nfqws").exists():
        print("-> Скачиваем компоненты zapret...")
        run_cmd([str(SERVICE_SCRIPT), "download-deps", "--default"])

def get_interfaces():
    interfaces = ["any"]
    try:
        for entry in os.listdir("/sys/class/net"):
            if entry != "lo":
                interfaces.append(entry)
    except:
        pass
    return interfaces

def load_strategy_files():
    if not SERVICE_SCRIPT.exists():
        return []
    result = run_cmd([str(SERVICE_SCRIPT), "strategy", "list"], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    lines = result.stdout.splitlines()
    return [line.strip() for line in lines if line.strip().endswith(".bat")]

def stop_zapret():
    run_cmd([str(SERVICE_SCRIPT), "kill"])
    run_cmd(["pkill", "-f", "nfqws"])
    run_cmd(["pkill", "-f", "tpws"])
    time.sleep(1)

# ────────────────────────────────────────────────────────────────
# Проверка YouTube (по аналогии с bash-скриптом)
# ────────────────────────────────────────────────────────────────

def check_youtube_main():
    with tempfile.NamedTemporaryFile() as tmp:
        cmd = [
            "curl", "-s", "--tlsv1.3",
            "--connect-timeout", str(CURL_TIMEOUT),
            "--max-time", str(CURL_TIMEOUT),
            "-o", tmp.name,
            "-w", "%{http_code}",
            "https://www.youtube.com"
        ]
        result = run_cmd(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False
        code = result.stdout.strip()
        if not code.startswith(("2", "3")):
            return False
        content = pathlib.Path(tmp.name).read_text(encoding="utf-8", errors="ignore")
        return "youtube" in content.lower()

def check_youtube_cdn():
    cmd = [
        "curl", "-s", "--tlsv1.3",
        "--connect-timeout", str(CURL_TIMEOUT),
        "--max-time", str(CURL_TIMEOUT),
        "-o", "/dev/null",
        "-w", "%{http_code}",
        "https://redirector.googlevideo.com"
    ]
    result = run_cmd(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False
    code = result.stdout.strip()
    return code != "000"

def check_youtube_full(verbose=True):
    if verbose:
        print("Проверяем YouTube (TLS 1.3):")
        print(" youtube.com...   ", end="", flush=True)
    main_ok = check_youtube_main()
    if verbose:
        print("✓" if main_ok else "✗")
    if not main_ok:
        return False

    if verbose:
        print(" googlevideo.com  ", end="", flush=True)
    cdn_ok = check_youtube_cdn()
    if verbose:
        print("✓" if cdn_ok else "✗")
    return cdn_ok

# ────────────────────────────────────────────────────────────────
# Интерактивный режим (оставлен почти без изменений)
# ────────────────────────────────────────────────────────────────

def interactive_mode(strategies):
    print("\nИнтерактивный запуск zapret")
    ifaces = get_interfaces()
    print("\nДоступные сетевые интерфейсы:")
    for i, iface in enumerate(ifaces, 1):
        print(f"{i}) {iface}")
    try:
        idx = int(input("Выберите интерфейс (номер): ") or "1") - 1
        iface = ifaces[idx]
    except:
        iface = "any"
    print(f"Выбран интерфейс: {iface}")

    use_gf = input("Включить Gamefilter? [y/N]: ").strip().lower().startswith("y")

    print("\nДоступные стратегии:")
    for i, name in enumerate(strategies, 1):
        print(f"{i:2}) {name}")
    choice = input("\nВыберите номер стратегии: ").strip()
    if not choice.isdigit():
        return
    idx = int(choice) - 1
    if not (0 <= idx < len(strategies)):
        return
    strategy = strategies[idx]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Выбрана стратегия: {strategy}")
    print(f"[{now}] GameFilter {'включен' if use_gf else 'выключен'}")

    stop_zapret()
    cmd = [str(SERVICE_SCRIPT), "run", "-s", strategy, "-i", iface]
    if use_gf:
        cmd.append("-g")

    print("Запуск zapret... (Ctrl+C для остановки)")
    try:
        proc = subprocess.Popen(cmd, cwd=str(DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(proc.stdout.readline, ''):
            print(line.rstrip())
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        stop_zapret()

# ────────────────────────────────────────────────────────────────
# Автотест стратегий (основная новая логика)
# ────────────────────────────────────────────────────────────────

def auto_test_strategies(strategies):
    print("\nАвтоматический подбор стратегии для YouTube")
    print("Проверяем без zapret...")
    if check_youtube_full(verbose=True):
        print("\nYouTube уже доступен без обхода. Ничего не требуется.")
        return

    print("\nYouTube недоступен. Начинаем тестирование стратегий...\n")
    stop_zapret()

    working = []
    tested = 0

    for i, strategy in enumerate(strategies, 1):
        print(f"[{i:2}/{len(strategies)}] {strategy:<40} ", end="", flush=True)
        run_cmd([str(SERVICE_SCRIPT), "run", "-s", strategy, "-i", "any"], cwd=str(DIR),
                capture_output=True)
        time.sleep(WAIT_TIME)

        tested += 1
        yt_ok = check_youtube_main()
        cdn_ok = check_youtube_cdn() if yt_ok else False

        status = "YT:✓ CDN:✓" if yt_ok and cdn_ok else \
                 "YT:✓ CDN:✗" if yt_ok else "YT:✗"
        color = "\033[0;32m" if yt_ok else "\033[0;31m"
        print(f"{color}{status}\033[0m")

        if yt_ok:
            working.append((i, strategy, 1 if cdn_ok else 0))

        stop_zapret()

    print("\n" + "="*70)
    print(f"Протестировано: {tested} стратегий")
    print(f"Рабочих (YT ✓): {len(working)}")
    print("="*70)

    if not working:
        print("Ни одна стратегия не помогла.")
        return

    print("\nРабочие стратегии (отсортированы по наличию CDN):")
    working.sort(key=lambda x: -x[2])  # сначала с CDN
    for num, name, cdn in working:
        cdn_str = "CDN ✓" if cdn else "CDN ✗"
        print(f"  {num:2}) {name:<45} {cdn_str}")

    print("\nВведите:")
    print("  s<номер>  — сохранить стратегию в conf.env")
    print("  <номер>   — сразу запустить эту стратегию")
    print("  Enter     — выйти")
    choice = input("> ").strip()

    if not choice:
        return

    if choice.lower().startswith("s") and choice[1:].isdigit():
        num = int(choice[1:])
        for n, name, _ in working:
            if n == num:
                with open(CONF_FILE, "w") as f:
                    f.write(f"interface=any\ngamefilter=false\nstrategy={name}\n")
                print(f"\nСохранено в {CONF_FILE}: strategy={name}")
                print("Запуск без меню: python zapret.py -nointeractive")
                return
        print("Номер не найден среди рабочих")

    elif choice.isdigit():
        num = int(choice)
        for n, name, _ in working:
            if n == num:
                print(f"\nЗапускаем стратегию {name} ...")
                stop_zapret()
                cmd = [str(SERVICE_SCRIPT), "run", "-s", name, "-i", "any"]
                subprocess.Popen(cmd, cwd=str(DIR))
                print("Запущено. Для остановки: Ctrl+C или ./service.sh kill")
                return
        print("Номер не найден среди рабочих")

def main():
    print_header()

    if "--install-deps" in sys.argv:
        install_dependencies()

    required = ["curl", "git", "nftables"]
    missing = check_programs(required)
    if missing:
        print(f"Отсутствуют: {', '.join(missing)}")
        print("Запустите с флагом --install-deps")
        sys.exit(1)

    clone_repo()
    prepare_scripts()
    download_deps_if_needed()

    strategies = load_strategy_files()
    if not strategies:
        print("Стратегии не найдены")
        sys.exit(1)

    while True:
        print("\nМеню:")
        print("1. Интерактивный запуск")
        print("2. Автотест всех стратегий (поиск рабочей для YouTube)")
        print("0. Выход")
        action = input("Выберите действие: ").strip()

        if action == "1":
            interactive_mode(strategies)
        elif action == "2":
            auto_test_strategies(strategies)
        elif action == "0":
            sys.exit(0)
        else:
            print("Неверный выбор")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop_zapret()
        print("\nОстановлено.")
        sys.exit(0)
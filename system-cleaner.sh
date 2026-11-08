#!/usr/bin/env bash
# system-cleaner.sh — консольный аналог вкладки "System Cleaner" из Stacer 1.1.0
#
# Категории (как в Stacer):
#   packages — кэши пакетов: apt /var/cache/apt/archives, pacman /var/cache/pacman/pkg,
#              dnf /var/cache/dnf, yum /var/cache/yum, zypper /var/cache/zypp
#   crash    — отчёты о сбоях: файлы в /var/crash
#   logs     — логи приложений: ВСЁ содержимое /var/log (включая подкаталоги!)
#   cache    — кэши приложений: всё содержимое ~/.cache
#   trash    — корзина: ~/.local/share/Trash/files и ~/.local/share/Trash/info
#
# Запуск:
#   ./system-cleaner.sh                  сканирование + подтверждение
#   ./system-cleaner.sh --dry-run        только сканирование, ничего не удалять
#   ./system-cleaner.sh --yes            без подтверждения (для cron)
#   ./system-cleaner.sh --logs --trash   чистить только выбранные категории
#
# Системные категории (packages, crash, logs) требуют root: если скрипт запущен
# не от root, для них автоматически используется sudo. Корзина и кэш чистятся
# для текущего пользователя (при запуске через sudo — для $SUDO_USER).

set -u

DRY_RUN=0
ASSUME_YES=0
SELECTED=()

usage() {
    cat <<'EOF'
Использование: system-cleaner.sh [ОПЦИИ] [КАТЕГОРИИ...]

Категории (по умолчанию все):
  --packages   кэши пакетов (apt/pacman/dnf/yum/zypper)
  --crash      отчёты о сбоях (/var/crash)
  --logs       логи (/var/log, удаляется всё содержимое, как в Stacer)
  --cache      кэши приложений (~/.cache)
  --trash      корзина (~/.local/share/Trash)

Опции:
  -n, --dry-run   только показать, что будет удалено
  -y, --yes       не спрашивать подтверждение
  -h, --help      эта справка
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -n|--dry-run) DRY_RUN=1 ;;
        -y|--yes)     ASSUME_YES=1 ;;
        --packages)   SELECTED+=(packages) ;;
        --crash)      SELECTED+=(crash) ;;
        --logs)       SELECTED+=(logs) ;;
        --cache)      SELECTED+=(cache) ;;
        --trash)      SELECTED+=(trash) ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "Неизвестный параметр: $1" >&2; usage; exit 1 ;;
    esac
    shift
done
[ ${#SELECTED[@]} -eq 0 ] && SELECTED=(packages crash logs cache trash)

# Чей домашний каталог чистить (при запуске через sudo — исходного пользователя)
TARGET_USER="${SUDO_USER:-$(id -un)}"
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
[ -n "$TARGET_HOME" ] || TARGET_HOME="$HOME"

# Системные категории требуют root/sudo
NEED_ROOT=0
for c in "${SELECTED[@]}"; do
    case "$c" in packages|crash|logs) NEED_ROOT=1 ;; esac
done
if [ "$NEED_ROOT" = 1 ] && [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
    echo "Нет sudo: системные категории (packages, crash, logs) пропущены. Запустите от root." >&2
    KEPT=()
    for c in "${SELECTED[@]}"; do
        case "$c" in cache|trash) KEPT+=("$c") ;; esac
    done
    SELECTED=("${KEPT[@]}")
    [ ${#SELECTED[@]} -eq 0 ] && exit 1
fi

# Менеджер пакетов — порядок определения как в Stacer: apt-get, dnf, yum, pacman, zypper.
# Примечание: в Stacer 1.1.0 для dnf/yum ошибочно чистился путь pacman — здесь исправлено.
PKG_DIRS=()
PKG_MODE=files
if command -v apt-get >/dev/null 2>&1; then
    PKG_DIRS=(/var/cache/apt/archives)
elif command -v dnf >/dev/null 2>&1; then
    PKG_DIRS=(/var/cache/dnf /var/cache/libdnf5); PKG_MODE=all
elif command -v yum >/dev/null 2>&1; then
    PKG_DIRS=(/var/cache/yum); PKG_MODE=all
elif command -v pacman >/dev/null 2>&1; then
    PKG_DIRS=(/var/cache/pacman/pkg)
elif command -v zypper >/dev/null 2>&1; then
    PKG_DIRS=(/var/cache/zypp); PKG_MODE=all
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

build_list() {
    local cat="$1" list="$WORK/$1.list" d
    : > "$list"
    case "$cat" in
        packages)
            for d in "${PKG_DIRS[@]}"; do
                [ -d "$d" ] || continue
                if [ "$PKG_MODE" = files ]; then
                    find "$d" -maxdepth 1 -type f ! -name lock -print0 >> "$list" 2>/dev/null
                else
                    find "$d" -mindepth 1 -maxdepth 1 -print0 >> "$list" 2>/dev/null
                fi
            done
            ;;
        crash)
            [ -d /var/crash ] && find /var/crash -maxdepth 1 -type f -print0 >> "$list" 2>/dev/null
            ;;
        logs)
            [ -d /var/log ] && find /var/log -mindepth 1 -maxdepth 1 -print0 >> "$list" 2>/dev/null
            ;;
        cache)
            [ -d "$TARGET_HOME/.cache" ] && find "$TARGET_HOME/.cache" -mindepth 1 -maxdepth 1 -print0 >> "$list" 2>/dev/null
            ;;
        trash)
            for d in "$TARGET_HOME/.local/share/Trash/files" "$TARGET_HOME/.local/share/Trash/info"; do
                [ -d "$d" ] && find "$d" -mindepth 1 -maxdepth 1 -print0 >> "$list" 2>/dev/null
            done
            ;;
    esac
}

count_of() { tr -cd '\0' < "$1" | wc -c; }

size_of() {
    if [ -s "$1" ]; then
        du -scb --files0-from="$1" 2>/dev/null | awk 'END {print $1+0}'
    else
        echo 0
    fi
}

label_of() {
    case "$1" in
        packages) echo "Кэши пакетов" ;;
        crash)    echo "Отчёты о сбоях" ;;
        logs)     echo "Логи приложений" ;;
        cache)    echo "Кэши приложений" ;;
        trash)    echo "Корзина" ;;
    esac
}

echo "Сканирование (пользователь: $TARGET_USER)..."
TOTAL=0
printf '%-20s %10s %12s\n' "Категория" "Объектов" "Размер"
printf '%-20s %10s %12s\n' "--------------------" "----------" "------------"
for cat in "${SELECTED[@]}"; do
    build_list "$cat"
    n=$(count_of "$WORK/$cat.list")
    s=$(size_of "$WORK/$cat.list")
    TOTAL=$((TOTAL + s))
    printf '%-20s %10s %12s\n' "$(label_of "$cat")" "$n" "$(numfmt --to=iec "$s")"
done
printf '%-20s %10s %12s\n' "--------------------" "----------" "------------"
printf '%-20s %10s %12s\n' "Итого" "" "$(numfmt --to=iec "$TOTAL")"

if [ "$DRY_RUN" = 1 ]; then
    echo "Режим --dry-run: ничего не удалено."
    exit 0
fi

if [ "$TOTAL" = 0 ]; then
    echo "Нечего чистить."
    exit 0
fi

for cat in "${SELECTED[@]}"; do
    if [ "$cat" = logs ] && [ -s "$WORK/logs.list" ]; then
        echo "Внимание: категория 'logs' удалит ВСЁ содержимое /var/log (включая journal) — как это делает Stacer."
    fi
done

if [ "$ASSUME_YES" != 1 ]; then
    if [ ! -t 0 ]; then
        echo "Нет терминала для подтверждения. Используйте --yes или --dry-run." >&2
        exit 1
    fi
    read -r -p "Удалить всё перечисленное? [y/N] " ans
    case "$ans" in
        y|Y|yes|YES|д|Д|да|ДА) ;;
        *) echo "Отменено."; exit 0 ;;
    esac
fi

# Как в Stacer: системные категории удаляются с повышением привилегий (sudo rm -rf)
clean_list() {
    local list="$WORK/$1.list" sys="$2"
    [ -s "$list" ] || return 0
    if [ "$sys" = 1 ] && [ "$(id -u)" -ne 0 ]; then
        xargs -0 -r sudo rm -rf -- < "$list"
    else
        xargs -0 -r rm -rf -- < "$list"
    fi
}

for cat in "${SELECTED[@]}"; do
    case "$cat" in
        packages|crash|logs) clean_list "$cat" 1 ;;
        cache|trash)         clean_list "$cat" 0 ;;
    esac
    echo "Очищено: $(label_of "$cat")"
done

echo "Готово. Освобождено (примерно): $(numfmt --to=iec "$TOTAL")"
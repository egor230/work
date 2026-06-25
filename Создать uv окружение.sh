#!/usr/bin/env bash
# =============================================================================
# ULTIMATE AUTONOMOUS PYTHON + UV SETUP SCRIPT
# Версия: 2.0 "Bulletproof Edition"
# Автор: ты + Grok 4
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ----------------------------- ЦВЕТА -----------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# -------------------------- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ --------------------------
WORK_DIR="$(pwd)"
PYTHON_INSTALL_SUBDIR="python_runtime"
VENV_NAME="myenv_uv_latest"

PYTHON_INSTALL_PATH="$WORK_DIR/$PYTHON_INSTALL_SUBDIR"
VENV_FULL_PATH="$WORK_DIR/$VENV_NAME"
ACTIVATE_SCRIPT="$VENV_FULL_PATH/bin/activate"

TEMP_DIR=""
PYTHON_TAR_FILE=""
PYTHON_SOURCE_DIR=""
PYTHON_VERSION=""
PYTHON_INTERPRETER=""
LOG_FILE=""

# Флаг самоуничтожения (по умолчанию — спрашиваем)
SELF_DESTRUCT=${SELF_DESTRUCT:-ask}

# ----------------------------- ФУНКЦИИ -----------------------------
log() {
    echo -e "${CYAN}[$(date +'%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"
}

success() { echo -e "${GREEN}✓ $1${NC}" | tee -a "$LOG_FILE"; }
error()   { echo -e "${RED}✗ ОШИБКА: $1${NC}" >&2 | tee -a "$LOG_FILE"; }
warn()    { echo -e "${YELLOW}⚠ $1${NC}" | tee -a "$LOG_FILE"; }
info()    { echo -e "${BLUE}ℹ $1${NC}" | tee -a "$LOG_FILE"; }

banner() {
    echo -e "${MAGENTA}"
    echo "================================================================================"
    echo "   $1"
    echo "================================================================================"
    echo -e "${NC}"
}

spinner() {
    local pid=$1
    local delay=0.15
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while ps -p $pid > /dev/null 2>&1; do
        local temp=${spinstr#?}
        printf " %c " "$spinstr"
        spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

check_disk_space() {
    local needed_gb=3
    local available_gb=$(df -BG "$WORK_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
    if (( available_gb < needed_gb )); then
        error "Недостаточно места! Нужно минимум ${needed_gb} ГБ, доступно ${available_gb} ГБ."
        exit 1
    fi
    info "Свободно на диске: ${available_gb} ГБ → достаточно."
}

install_system_deps() {
    banner "ЭТАП 0.2: УСТАНОВКА СИСТЕМНЫХ ЗАВИСИМОСТЕЙ"

    if command -v apt-get >/dev/null 2>&1; then
        log "Обнаружена Debian/Ubuntu"
        sudo apt-get update -qq
        sudo apt-get install -y build-essential zlib1g-dev libncurses5-dev \
            libgdbm-dev libnss3-dev libsqlite3-dev libreadline-dev libffi-dev \
            libssl-dev libbz2-dev liblzma-dev tk-dev uuid-dev libgdbm-compat-dev
    elif command -v dnf >/dev/null 2>&1; then
        log "Обнаружена Fedora/RHEL"
        sudo dnf groupinstall -y "Development Tools"
        sudo dnf install -y zlib-devel bzip2-devel openssl-devel ncurses-devel \
            sqlite-devel readline-devel tk-devel gdbm-devel db4-devel libffi-devel \
            xz-devel libuuid-devel
    elif command -v yum >/dev/null 2>&1; then
        log "Обнаружена CentOS/RHEL (yum)"
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y zlib-devel bzip2-devel openssl-devel ncurses-devel \
            sqlite-devel readline-devel tk-devel gdbm-devel libffi-devel xz-devel
    elif command -v zypper >/dev/null 2>&1; then
        log "Обнаружена openSUSE"
        sudo zypper install -y --type pattern devel_basis
        sudo zypper install -y zlib-devel libopenssl-devel libffi-devel
    elif command -v apk >/dev/null 2>&1; then
        log "Обнаружена Alpine Linux"
        apk add --no-cache build-base openssl-dev zlib-dev ncurses-dev \
            bzip2-dev sqlite-dev readline-dev libffi-dev xz-dev
    elif command -v pacman >/dev/null 2>&1; then
        log "Обнаружена Arch Linux"
        sudo pacman -Syu --noconfirm base-devel openssl zlib
    else
        warn "Неизвестный пакетный менеджер. Убедитесь, что зависимости для компиляции Python установлены вручную!"
        read -rp "Продолжить? (y/N): " yn
        [[ $yn =~ ^[Yy]$ ]] || exit 1
    fi
    success "Системные зависимости установлены/проверены"
}

install_uv() {
    banner "ЭТАП 0.3: УСТАНОВКА UV (самый быстрый менеджер пакетов Python)"

    if command -v uv >/dev/null 2>&1; then
        log "uv уже установлен: $(uv --version)"
        return 0
    fi

    log "Скачиваем и устанавливаем uv..."
    # Автоопределение архитектуры
    local arch=$(uname -m)
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local uv_url="https://astral.sh/uv/install.sh"

    if curl -LsSf "$uv_url" | sh; then
        source "$HOME/.cargo/env" 2>/dev/null || true
        if command -v uv >/dev/null 2>&1; then
            success "uv успешно установлен: $(uv --version)"
            return 0
        fi
    fi

    error "Не удалось установить uv автоматически"
    exit 1
}

get_latest_python() {
    banner "ЭТАП 1.1: ОПРЕДЕЛЕНИЕ ПОСЛЕДНЕЙ СТАБИЛЬНОЙ ВЕРСИИ PYTHON"

    log "Запрашиваем python.org..."
    local url=$(curl -s https://www.python.org/downloads/ | \
        grep -oE 'href="[^"]+Python-[0-9]+\.[0-9]+\.[0-9]+\.tgz"' | \
        head -1 | cut -d'"' -f2)

    if [[ -z "$url" ]]; then
        error "Не удалось найти последнюю стабильную версию на python.org"
        exit 1
    fi

    PYTHON_VERSION=$(basename "$url" | sed 's/Python-\(.*\)\.tgz/\1/')
    PYTHON_FULL_URL="https://www.python.org${url}"
    PYTHON_TAR_FILE="$WORK_DIR/Python-$PYTHON_VERSION.tgz"

    success "Найдена последняя версия: $PYTHON_VERSION"
    log "URL: $PYTHON_FULL_URL"
}

download_python() {
    banner "ЭТАП 1.2: ЗАГРУЗКА ИСХОДНИКОВ PYTHON $PYTHON_VERSION"

    if [[ -f "$PYTHON_TAR_FILE" ]]; then
        log "Архив уже существует, пропускаем загрузку"
        return 0
    fi

    log "Скачиваем (~25–35 МБ)..."
    wget --progress=bar:force:noscroll "$PYTHON_FULL_URL" -O "$PYTHON_TAR_FILE" 2>&1 | \
        stdbuf -oL tr '\r' '\n' | grep -oE '[0-9]+%' | while read -r percent; do
            printf "\r   Загрузка: %s" "$percent"
        done
    echo
    success "Исходники загружены"
}

compile_python() {
    banner "ЭТАП 1.4: КОМПИЛЯЦИЯ PYTHON $PYTHON_VERSION (5–15 минут)"

    [[ -d "$PYTHON_INSTALL_PATH" ]] && rm -rf "$PYTHON_INSTALL_PATH"
    mkdir -p "$PYTHON_INSTALL_PATH"

    cd "$PYTHON_SOURCE_DIR"

    log "Запуск ./configure --enable-optimizations ..."
    ./configure --prefix="$PYTHON_INSTALL_PATH" \
                --enable-optimizations \
                --with-ensurepip=install > /dev/null

    log "Запуск make -j$(nproc) ..."
    make -j"$(nproc)" > /dev/null &

    spinner $!
    wait $! || { error "Ошибка компиляции"; exit 1; }

    log "Запуск make install ..."
    make install > /dev/null

    PYTHON_INTERPRETER="$PYTHON_INSTALL_PATH/bin/python3"

    if [[ ! -x "$PYTHON_INTERPRETER" ]]; then
        error "Исполняемый файл Python не найден после компиляции!"
        exit 1
    fi

    success "Python $PYTHON_VERSION успешно скомпилирован и установлен!"
    log "Путь: $PYTHON_INTERPRETER"
    "$PYTHON_INTERPRETER" --version | tee -a "$LOG_FILE"
}

create_venv() {
    banner "ЭТАП 2: СОЗДАНИЕ UV-ВЕНВА"

    [[ -d "$VENV_FULL_PATH" ]] && rm -rf "$VENV_FULL_PATH"

    log "Создаём виртуальное окружение с помощью uv..."
    uv venv "$VENV_FULL_PATH" --python "$PYTHON_INTERPRETER" --seed > /dev/null

    success "Виртуальное окружение создано: $VENV_FULL_PATH"
}

final_report() {
    banner "ЗАВЕРШЕНИЕ — ВСЁ ГОТОВО!"

    echo -e "${BOLD}Python:${NC} $PYTHON_VERSION (скомпилирован с оптимизациями)"
    echo -e "${BOLD}Путь к Python:${NC} $PYTHON_INTERPRETER"
    echo -e "${BOLD}Виртуальное окружение:${NC} $VENV_FULL_PATH"
    echo -e "${BOLD}Активация:${NC} source $ACTIVATE_SCRIPT"
    echo
    echo -e "${GREEN}${BOLD}Теперь можешь работать с ультрабыстрым uv в полностью автономном окружении!${NC}"
    echo
    echo -e "${CYAN}Лог выполнения сохранён в: $LOG_FILE${NC}"
}

cleanup() {
    echo
    log "Запуск финальной очистки..."

    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        cd "$WORK_DIR" || true
        rm -rf "$TEMP_DIR" && log "Временная директория удалена"
    fi

    if [[ -f "$PYTHON_TAR_FILE" ]]; then
        rm -f "$PYTHON_TAR_FILE" && log "Архив Python удалён"
    fi

    # Самоуничтожение
    if [[ "$SELF_DESTRUCT" == "yes" ]] || \
       [[ "$SELF_DESTRUCT" == "ask" && -t 1 ]]; then
        if [[ "$SELF_DESTRUCT" == "ask" ]]; then
            read -rp "Удалить этот скрипт после завершения? (y/N): " ans
            [[ $ans =~ ^[Yy]$ ]] || return 0
        fi
        rm -f "$0" && log "Скрипт самоуничтожился"
    fi
}

trap cleanup EXIT

# ================================ MAIN ================================
main() {
    clear
    banner "ULTIMATE AUTONOMOUS PYTHON + UV SETUP v2.0"
    LOG_FILE="$(mktemp /tmp/ultimate-setup-log.XXXXXX.txt)"
    log "Лог: $LOG_FILE"

    check_disk_space

    # 0. Базовые проверки
    for cmd in curl wget tar make gcc; do
        command -v "$cmd" &>/dev/null || { error "Требуется $cmd"; exit 1; }
    done

    install_system_deps
    install_uv

    TEMP_DIR=$(mktemp -d -t python-build-XXXXXX)
    log "Временная папка: $TEMP_DIR"

    get_latest_python
    download_python

    log "Распаковка архива..."
    tar -xzf "$PYTHON_TAR_FILE" -C "$TEMP_DIR" --strip-components=1
    PYTHON_SOURCE_DIR="$TEMP_DIR"
    success "Исходники распакованы"

    compile_python
    create_venv
    final_report
}

main "$@"

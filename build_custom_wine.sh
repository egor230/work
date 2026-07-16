#!/bin/bash
# build_custom_wine.sh - Сборка только Wine 11.13
# Устанавливается в /opt/gaming-wine, симлинк создаётся в /usr/bin/wine
# Исходники читаются из папки скрипта (Custom wine/)

set -euo pipefail

# MangoHud (если в окружении установлен MANGOHUD=1) внедряется в процессы wine
# и ломает запуск (зависание на rpcss/OLE). MangoHud активируется при ЛЮБОМ значении
# переменной, поэтому её нужно именно СНЯТЬ (unset), а не выставлять в "0".
unset MANGOHUD 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="/tmp/wine-build-$$"
INSTALL_PREFIX="/opt/gaming-wine"
JOBS=$(nproc)

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[BUILD]${NC} $*"; }
ok() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err() { echo -e "${RED}[ERR]${NC} $*"; }

# URL для докачки отсутствующих исходников (имя_архива|url)
DOWNLOAD_URLS=(
    "wine-11.13.tar.xz|https://dl.winehq.org/wine/source/11.x/wine-11.13.tar.xz"
)

# Докачка отсутствующих архивов
download_sources() {
    for entry in "${DOWNLOAD_URLS[@]}"; do
        local f="${entry%%|*}"
        local url="${entry##*|}"
        if [[ -f "$SCRIPT_DIR/$f" ]]; then
            ok "Уже есть: $f"
            continue
        fi
        log "Архив $f не найден, скачиваю..."
        local tmp
        tmp="$(mktemp)"
        if ! wget -q --show-progress -O "$tmp" "$url"; then
            err "Не удалось скачать $url"
            rm -f "$tmp"
            exit 1
        fi
        mv "$tmp" "$SCRIPT_DIR/$f"
        ok "Скачан: $f"
    done
}

# Проверка наличия всех исходников (после докачки)
check_sources() {
    local missing=0
    for entry in "${DOWNLOAD_URLS[@]}"; do
        local f="${entry%%|*}"
        if [[ ! -f "$SCRIPT_DIR/$f" ]]; then
            err "Не найден даже после докачки: $SCRIPT_DIR/$f"
            missing=1
        fi
    done
    [[ $missing -eq 0 ]] || exit 1
}

# Создание временной папки сборки (без пробелов!)
setup_build_dir() {
    log "Создание временной папки сборки: $BUILD_DIR"
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
}

# Распаковка исходников
extract_sources() {
    log "Распаковка wine-11.13.tar.xz..."
    tar -xf "$SCRIPT_DIR/wine-11.13.tar.xz"
    ok "Исходники распакованы"
}

# --- WINE (новый WoW64: i386 + x86_64 в одной сборке) ---
build_wine() {
    log "=== Сборка Wine (WoW64: i386 + x86_64) ==="
    cd "$BUILD_DIR"
    mkdir -p wine-build
    cd wine-build

    ../wine-11.13/configure \
        --prefix="$INSTALL_PREFIX" \
        --enable-archs=i386,x86_64 \
        --with-vulkan --with-x --with-gstreamer --with-pulse \
        --with-opengl --with-fontconfig --with-freetype \
        --with-gnutls \
        --without-capi --without-pcap --disable-tests \
        2>&1 | tee configure.log

    log "Компиляция Wine (make -j$JOBS)..."
    make -j"$JOBS" 2>&1 | tee make.log

    log "Установка Wine..."
    sudo make install 2>&1 | tee install.log
    ok "Wine (WoW64) установлен в $INSTALL_PREFIX"
}

# --- Установка системных симлинков ---
install_system_links() {
    log "=== Создание системных симлинков ==="
    
    # Основной wine бинарник (в /usr/local/bin — приоритетнее /usr/bin,
    # чтобы наш кастомный wine перекрывал любые другие установки wine)
    for b in wine wine64 wineserver winecfg wineboot; do
        sudo ln -sf "$INSTALL_PREFIX/bin/$b" /usr/local/bin/$b
        sudo ln -sf "$INSTALL_PREFIX/bin/$b" /usr/bin/$b 2>/dev/null || true
    done
    
    # Библиотеки в ld.so.conf.d
    echo "$INSTALL_PREFIX/lib" | sudo tee /etc/ld.so.conf.d/gaming-wine.conf > /dev/null
    echo "$INSTALL_PREFIX/lib64" | sudo tee -a /etc/ld.so.conf.d/gaming-wine.conf > /dev/null
    sudo ldconfig
    
    ok "Системные ссылки созданы"
}

# --- Проверка установки ---
verify_install() {
    log "=== Проверка установки ==="
    echo "Wine версия:"
    /opt/gaming-wine/bin/wine --version
    /opt/gaming-wine/bin/wine64 --version 2>/dev/null || warn "wine64 не найден (только WoW64)"
    wineserver --version
    
    ok "Проверка завершена"
}

# --- Удаление ЧУЖОЙ/старой установки wine ---
WINE_TARGET_VERSION="wine-11.13"
cleanup_previous() {
    log "=== Проверка/удаление посторонних установок Wine ==="

    local keep_prefix=0
    if [[ -x "$INSTALL_PREFIX/bin/wine" ]]; then
        local cur
        cur="$("$INSTALL_PREFIX/bin/wine" --version 2>/dev/null || true)"
        if [[ "$cur" == "$WINE_TARGET_VERSION" ]]; then
            keep_prefix=1
            ok "В $INSTALL_PREFIX уже наш $WINE_TARGET_VERSION — сохраняем (идемпотентно)"
        else
            warn "В $INSTALL_PREFIX другая версия wine ('$cur') — удаляем"
        fi
    fi

    if [[ $keep_prefix -eq 0 && -d "$INSTALL_PREFIX" ]]; then
        log "Удаление $INSTALL_PREFIX ..."
        sudo rm -rf "$INSTALL_PREFIX"
        ok "Посторонняя установка удалена"
    fi

    # Удаляем ЧУЖИЕ системные wine-пакеты (winehq/дистрибутивные), если есть
    local wine_pkgs
    wine_pkgs="$(dpkg-query -W -f='${Package}\n' 2>/dev/null \
        | grep -E '^(wine|wine32|wine64|wine-stable|wine-staging|wine-devel|winehq-.*)$' || true)"
    if [[ -n "$wine_pkgs" ]]; then
        warn "Обнаружены системные пакеты wine — удаляю: $wine_pkgs"
        sudo apt-get remove -y $wine_pkgs 2>/dev/null || true
    fi

    # Удаляем посторонние симлинки/бинарники wine вне нашего INSTALL_PREFIX
    for b in wine wine64 wineserver winecfg wineboot; do
        for p in /usr/local/bin/$b /usr/bin/$b; do
            if [[ -e "$p" || -L "$p" ]]; then
                local tgt
                tgt="$(readlink -f "$p" 2>/dev/null || true)"
                if [[ "$tgt" != "$INSTALL_PREFIX/bin/"* ]]; then
                    sudo rm -f "$p" 2>/dev/null || true
                fi
            fi
        done
    done

    ok "Проверка посторонних установок завершена"
}

# --- Проверка зависимостей для сборки ---
check_deps() {
    log "=== Проверка зависимостей для сборки ==="
    local missing=()
    local pkgs=(
        gcc g++ make pkg-config flex bison gettext
        libx11-dev libxext-dev libxrender-dev libxrandr-dev
        libxcb1-dev libxi-dev libxt-dev libxxf86vm-dev
        libgl1-mesa-dev libglu1-mesa-dev libegl1-mesa-dev
        libfreetype-dev libfontconfig-dev
        libgnutls28-dev libpulse-dev
        libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
        libgstreamer-plugins-bad1.0-dev
        libva-dev libxslt1-dev libvulkan-dev
        libosmesa6-dev libsdl2-dev libudev-dev
        libunwind-dev libusb-1.0-0-dev libcups2-dev
        libdbus-1-dev libsane-dev liblcms2-dev
        libmpg123-dev libxml2-dev libssl-dev
        libcairo2-dev libxcomposite-dev libxcursor-dev
        libxdamage-dev libxfixes-dev libxinerama-dev
        libxkbfile-dev libxres-dev libxtst-dev libxv-dev
        libcapi20-dev libpcap-dev
        wget
    )
    for pkg in "${pkgs[@]}"; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            missing+=("$pkg")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Отсутствуют пакеты: ${missing[*]}"
        log "Устанавливаю отсутствующие пакеты..."
        sudo apt-get install -y "${missing[@]}" || {
            err "Не удалось установить зависимости"
            exit 1
        }
        ok "Зависимости установлены"
    else
        ok "Все зависимости для сборки присутствуют"
    fi
}

main() {
    log "=== НАЧАЛО СБОРКИ WINE ==="
    log "Исходники: $SCRIPT_DIR"
    log "Сборка в: $BUILD_DIR"
    log "Установка в: $INSTALL_PREFIX"
    log "Потоков: $JOBS"
    
    check_deps
    cleanup_previous
    download_sources
    check_sources
    setup_build_dir
    extract_sources
    build_wine
    install_system_links
    verify_install
    
    log "=== СБОРКА ЗАВЕРШЕНА УСПЕШНО ==="
    log "Используйте: wine --version  (должно показывать wine-11.13)"
}

# Запуск
main "$@"

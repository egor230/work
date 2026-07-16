#!/bin/bash
# ============================================================================
#  DXVK Game Launcher — Комплексный скрипт установки DXVK и запуска игр
#  через системный Wine на Linux
#
#  Версия:  1.0.0
#  Дата:    2026-07-09
#  Автор:   QwenPaw Agent (egor workspace)
#
#  Что делает:
#    1. Скачивает и устанавливает DXVK (3.0+) в системный Wine prefix
#    2. Заменяет локальные DXVK DLL в папках игр
#    3. Прописывает DLL overrides в реестр Wine
#    4. Запускает выбранные игры с оптимальными параметрами
#
#  Поддерживаемые игры (добавляйте свои через GAME_LIST):
#    - Alien Isolation (DX11)
#    - GTA San Andreas REMASTER (DX9)
#
#  Использование:
#    chmod +x dxvk_game_launcher.sh
#    ./dxvk_game_launcher.sh              # интерактивное меню
#    ./dxvk_game_launcher.sh --install    # только установка DXVK
#    ./dxvk_game_launcher.sh --launch-all # запуск всех игр
#    ./dxvk_game_launcher.sh --launch alien # запуск конкретной игры
#    ./dxvk_game_launcher.sh --status     # проверка состояния
#    ./dxvk_game_launcher.sh --uninstall  # откат к нативным DLL
#    ./dxvk_game_launcher.sh --verify     # проверка MD5 DLL
#    ./dxvk_game_launcher.sh --help       # справка
# ============================================================================
set -euo pipefail

# ============================================================================
#  НАСТРОЙКИ (можно менять)
# ============================================================================

# Версия DXVK для установки
DXVK_VERSION="${DXVK_VERSION:-3.0}"

# URL для скачивания DXVK
DXVK_URL="https://github.com/doitsujin/dxvk/releases/download/v${DXVK_VERSION}/dxvk-${DXVK_VERSION}.tar.gz"

# Куда скачивать и распаковывать
DXVK_ARCHIVE="/tmp/dxvk-${DXVK_VERSION}.tar.gz"
DXVK_DIR="/tmp/dxvk-${DXVK_VERSION}"

# ── Wine prefix ────────────────────────────────────────────────────────────
# Дефолтный системный Wine prefix (~/.wine)
# Если используется PortProton или другой prefix — измените эту переменную
WINEPREFIX="${WINEPREFIX:-${HOME}/.wine}"

# Пути к системным DLL в Wine prefix
SYS64="${WINEPREFIX}/drive_c/windows/system32"    # 64-bit DLLs
SYS32="${WINEPREFIX}/drive_c/windows/syswow64"     # 32-bit DLLs (для 32-bit игр)

# ── Дисплей ────────────────────────────────────────────────────────────────
# DISPLAY обязателен для wine — Xorg должен работать
# Автоопределение или принудительный выбор
DISPLAY="${DISPLAY:-:0}"

# ── Путь к играм ───────────────────────────────────────────────────────────
# Базовая директория с играми (NTFS)
GAME_BASE="/mnt/807EB5FA7EB5E954/games"

# ============================================================================
#  СПИСОК ИГР
# ============================================================================
#  Формат: "имя|путь|exe|битность|dxvk_dlls|launch_args|description"
#
#  Поля:
#    1. name         — короткое имя игры (для --launch)
#    2. path         — полный путь к папке игры
#    3. exe          — имя исполняемого файла
#    4. bits         — битность (32 или 64)
#    5. dxvk_dlls    — список DLL через запятую (d3d8,d3d9,d3d11,dxgi и т.д.)
#    6. launch_args  — аргументы запуска (пусто если нет)
#    7. description  — описание для меню
#
#  ⚠️  Добавляя новую игру, просто добавьте строку в GAME_LIST
# ============================================================================

GAME_LIST=(
    # Alien Isolation — DX11, 32-bit
    "alien|${GAME_BASE}/Alien Isolation|AI.exe|32|d3d11,d3d9,dxgi|-dx11 -skipintro 1|Alien: Isolation (DX11)"

    # GTA San Andreas REMASTER — DX9, 32-bit
    "gta|${GAME_BASE}/GTA San Andreas ( REMASTER )|gta_sa.exe|32|d3d8,d3d9||GTA: San Andreas REMASTER (DX9)"

    # ======================================================================
    #  ПРИМЕРЫ ДЛЯ НОВЫХ ИГР (раскомментируйте и измените):
    # ======================================================================
    # Witcher 3 — DX11, 64-bit
    # "witcher3|/path/to/witcher3|witcher3.exe|64|d3d11,dxgi||The Witcher 3: Wild Hunt"

    # Skyrim SE — DX11, 64-bit
    # "skyrim|/path/to/skyrim|SkyrimSE.exe|64|d3d11,dxgi||The Elder Scrolls V: Skyrim SE"

    # Hollow Knight — DX9, 32-bit
    # "hollow|/path/to/hollow_knight|Hollow Knight.exe|32|d3d9||Hollow Knight"

    # Dark Souls 3 — DX11, 64-bit
    # "ds3|/path/to/ds3|DarkSouls3.exe|64|d3d11,dxgi||Dark Souls III"
)

# ============================================================================
#  DLL ОВЕРРАЙДЫ
# ============================================================================
#  Все DirectX DLL, для которых Wine должен использовать DXVK вместо
#  нативных встроенных. Прописываются в реестр Wine.
# ============================================================================
DXVK_DLL_OVERRIDES=(
    "d3d8"          # Direct3D 8  (старые игры)
    "d3d9"          # Direct3D 9  (GTA SA, большинство игр до 2012)
    "d3d10core"     # Direct3D 10 Core
    "d3d11"         # Direct3D 11 (Alien Isolation, большинство современных)
    "dxgi"          # DXGI ( SwapChain, рендеринг)
)

# ============================================================================
#  ПАРАМЕТРЫ ЗАПУСКА ИГР (по умолчанию)
# ============================================================================
#  Эти переменные устанавливают окружение для запуска игр.
#  Каждая игра может переопределить через launch_env() функцию.
# ============================================================================

# DXVK настройки
export DXVK_ASYNC=1                        # Асинхронная компиляция шейдеров (убирает фризы)
export MESA_VK_WSI_PRESENT_MODE=mailbox    # Режим.presentation (mail box = без vsync задержек)
export DXVK_HUD="${DXVK_HUD:-}"            # HUD: fps,devinfo,frametimes,completion (пусто = выкл)

# FSR (FidelityFX Super Resolution) — апскейлинг
export WINE_FULLSCREEN_FSR=1               # Включить FSR
export WINE_FULLSCREEN_FSR_STRENGTH=5      # Сила FSR (0-5, 5 = максимальный апскейл)

# MangoHud — FPS counter
export MANGOHUD="${MANGOHUD:-0}"           # 0=выкл, 1=вкл

# ESync/FSync — мультипоточная синхронизация
export PW_USE_ESYNC="${PW_USE_ESYNC:-1}"
export PW_USE_FSYNC="${PW_USE_FSYNC:-1}"

# ============================================================================
#  ЦВЕТА И ВЫВОД
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
err()    { echo -e "${RED}[✗]${NC} $*"; }
info()   { echo -e "${BLUE}[i]${NC} $*"; }
header() { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}"; }

# ============================================================================
#  УТИЛИТЫ
# ============================================================================

# Проверка, что Wine доступен
check_wine() {
    if ! command -v wine &>/dev/null; then
        err "wine не найден в PATH"
        err "Установите Wine: sudo apt install wine"
        exit 1
    fi
    local wine_ver
    wine_ver=$(wine --version 2>/dev/null || echo "unknown")
    log "Wine: ${wine_ver}"
}

# Проверка, что Vulkan доступен
check_vulkan() {
    if ! command -v vulkaninfo &>/dev/null; then
        warn "vulkaninfo не найден — проверка Vulkan невозможна"
        return
    fi
    local gpu
    gpu=$(DISPLAY="${DISPLAY}" vulkaninfo 2>/dev/null | grep "deviceName" | head -1 | awk -F'= ' '{print $2}' || echo "unknown")
    local vk_ver
    vk_ver=$(DISPLAY="${DISPLAY}" vulkaninfo 2>/dev/null | grep "apiVersion" | head -1 | awk -F'= ' '{print $2}' || echo "unknown")
    log "GPU: ${gpu}"
    log "Vulkan API: ${vk_ver}"
}

# Проверка, что Xorg работает
check_display() {
    if ! xdpyinfo -display "${DISPLAY}" &>/dev/null 2>&1; then
        err "Xorg не работает на display ${DISPLAY}"
        err "Запустите Xorg или установите DISPLAY"
        exit 1
    fi
    log "Display: ${DISPLAY} (Xorg OK)"
}

# Проверка WINEPREFIX
check_prefix() {
    if [ ! -d "${WINEPREFIX}/drive_c/windows/system32" ]; then
        err "WINEPREFIX не найден: ${WINEPREFIX}"
        err "Инициализируйте префикс: WINEPREFIX=${WINEPREFIX} wineboot"
        exit 1
    fi
    log "WINEPREFIX: ${WINEPREFIX}"
}

# ============================================================================
#  СКАЧИВАНИЕ DXVK
# ============================================================================

download_dxvk() {
    header "Скачивание DXVK ${DXVK_VERSION}"

    # Проверяем, не скачано ли уже
    if [ -f "${DXVK_DIR}/x32/d3d9.dll" ] && [ -f "${DXVK_DIR}/x64/d3d11.dll" ]; then
        log "DXVK ${DXVK_VERSION} уже скачан: ${DXVK_DIR}"
        return 0
    fi

    info "Скачиваем ${DXVK_URL}..."
    if ! wget -q --show-progress "${DXVK_URL}" -O "${DXVK_ARCHIVE}" 2>&1; then
        err "Не удалось скачать DXVK"
        err "Проверьте подключение к интернету"
        exit 1
    fi

    info "Распаковываем..."
    tar xzf "${DXVK_ARCHIVE}" -C /tmp

    if [ ! -f "${DXVK_DIR}/x32/d3d9.dll" ]; then
        err "Распаковка не удалась — файлы не найдены"
        exit 1
    fi

    log "DXVK ${DXVK_VERSION} скачан и распакован"
    info "Содержимое:"
    ls -la "${DXVK_DIR}/x32/"*.dll 2>/dev/null | awk '{print "    " $NF " (" $5 " bytes)"}'
}

# ============================================================================
#  УСТАНОВКА DXVK В СИСТЕМНЫЙ WINE
# ============================================================================

install_dxvk_system() {
    header "Установка DXVK ${DXVK_VERSION} в системный Wine"

    # ── Бэкап нативных DLL ──────────────────────────────────────────────────
    # Сохраняем оригинальные Wine DLL на случай, если понадобится откат
    info "Создаём бэкапы нативных Wine DLL..."
    local backup_count=0
    for dll in "${DXVK_DLL_OVERRIDES[@]}"; do
        for dir in "${SYS64}" "${SYS32}"; do
            local src="${dir}/${dll}.dll"
            local bak="${dir}/${dll}.dll.native.bak"
            if [ -f "${src}" ] && [ ! -f "${bak}" ]; then
                cp "${src}" "${bak}"
                ((backup_count++))
            fi
        done
    done
    if [ "${backup_count}" -gt 0 ]; then
        log "Создано ${backup_count} бэкапов"
    else
        log "Бэкапы уже существуют, пропускаем"
    fi

    # ── Копирование DXVK DLL ────────────────────────────────────────────────
    info "Копируем DXVK x64 → system32..."
    cp -v "${DXVK_DIR}/x64/"*.dll "${SYS64}/" 2>&1 | while read -r line; do
        log "  ${line}"
    done

    info "Копируем DXVK x32 → syswow64..."
    cp -v "${DXVK_DIR}/x32/"*.dll "${SYS32}/" 2>&1 | while read -r line; do
        log "  ${line}"
    done

    # ── DLL Overrides через реестр ──────────────────────────────────────────
    # Без этого Wine игнорирует DXVK и использует нативные DLL
    info "Прописываем DLL overrides в реестр Wine..."
    for dll in "${DXVK_DLL_OVERRIDES[@]}"; do
        # native,builtin = сначала DXVK (native), потом Wine (builtin)
        WINEPREFIX="${WINEPREFIX}" DISPLAY="${DISPLAY}" \n            wine reg add "HKEY_CURRENT_USER\Software\Wine\DllOverrides" \n            /v "${dll}" /t REG_SZ /d "native,builtin" /f 2>/dev/null \n            && log "  ${dll} → native,builtin" \n            || warn "  ${dll}: не удалось прописать (возможно, wine ещё не инициализирован)"
    done

    log "DXVK ${DXVK_VERSION} установлен в системный Wine"
}

# ============================================================================
#  ЗАМЕНА ЛОКАЛЬНЫХ DXVK DLL В ПАПКАХ ИГР
# ============================================================================
#  ⚠️  КРИТИЧНО: Wine ищет DLL сначала в папке игры, потом в system32/syswow64!
#  Поэтому нужно заменить DLL и там тоже, иначе игра возьмёт старую версию.
# ============================================================================

replace_game_dxvk() {
    local game_name="$1"
    local game_path="$2"
    local game_bits="$3"
    local dxvk_dlls="$4"

    # Определяем архитектуру (x32 или x64)
    local arch="x32"
    if [ "${game_bits}" = "64" ]; then
        arch="x64"
    fi

    header "Замена DXVK DLL: ${game_name} (${arch})"

    # Папка с DLL нужной архитектуры
    local dxvk_src="${DXVK_DIR}/${arch}"

    if [ ! -d "${game_path}" ]; then
        err "Папка игры не найдена: ${game_path}"
        return 1
    fi

    # Разделяем список DLL через запятую
    IFS=',' read -ra dll_list <<< "${dxvk_dlls}"

    for dll in "${dll_list[@]}"; do
        local dll_file="${dll}.dll"
        local src="${dxvk_src}/${dll_file}"
        local dst="${game_path}/${dll_file}"
        local bak="${game_path}/${dll_file}.dxvk${DXVK_VERSION}.bak"

        # Проверяем исходник
        if [ ! -f "${src}" ]; then
            warn "  ${dll_file}: исходник не найден в ${dxvk_src}, пропускаем"
            continue
        fi

        # Бэкап текущей DLL (если она DXVK)
        if [ -f "${dst}" ]; then
            # Проверяем, DXVK ли это (по размеру или строкам)
            local is_dxvk
            is_dxvk=$(strings "${dst}" 2>/dev/null | grep -ci "dxvk" || true)
            if [ "${is_dxvk}" -gt 0 ]; then
                # Это DXVK — бэкапим
                if [ ! -f "${bak}" ]; then
                    cp "${dst}" "${bak}"
                    log "  ${dll_file}: бэкап создан ($(stat -c%s "${dst}") bytes)"
                fi
            else
                # Это оригинальная DLL игры — тоже бэкапим
                if [ ! -f "${dst}.orig.bak" ]; then
                    cp "${dst}" "${dst}.orig.bak"
                    log "  ${dll_file}: оригинальная DLL игры сохранена в .orig.bak"
                fi
            fi
        fi

        # Копируем DXVK DLL
        cp "${src}" "${dst}"
        local new_size
        new_size=$(stat -c%s "${dst}")
        log "  ${dll_file}: заменён DXVK ${DXVK_VERSION} (${new_size} bytes)"
    done
}

# ============================================================================
#  УСТАНОВКА DXVK В ПАПКИ ИГР
# ============================================================================

install_dxvk_games() {
    header "Установка DXVK ${DXVK_VERSION} в папки игр"

    for game_entry in "${GAME_LIST[@]}"; do
        IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"

        # Проверяем существование папки
        if [ ! -d "${path}" ]; then
            warn "Папка игры не найдена: ${path}, пропускаем"
            continue
        fi

        replace_game_dxvk "${name}" "${path}" "${bits}" "${dlls}"
    done
}

# ============================================================================
#  ВЕРИФИКАЦИЯ (ПРОВЕРКА MD5)
# ============================================================================
#  Проверяет, что DLL в папке игры совпадает с DXVK 3.0
# ============================================================================

verify_dxvk() {
    header "Верификация DXVK ${DXVK_VERSION} DLL"

    local all_ok=true

    for game_entry in "${GAME_LIST[@]}"; do
        IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"

        if [ ! -d "${path}" ]; then
            continue
        fi

        info "${desc}:"

        local arch="x32"
        if [ "${bits}" = "64" ]; then
            arch="x64"
        fi

        IFS=',' read -ra dll_list <<< "${dlls}"
        for dll in "${dll_list[@]}"; do
            local dll_file="${dll}.dll"
            local game_dll="${path}/${dll_file}"
            local ref_dll="${DXVK_DIR}/${arch}/${dll_file}"

            if [ ! -f "${game_dll}" ]; then
                warn "  ${dll_file}: НЕ НАЙДЕН в папке игры"
                all_ok=false
                continue
            fi

            if [ ! -f "${ref_dll}" ]; then
                warn "  ${dll_file}: эталонный файл не найден, пропускаем"
                continue
            fi

            local game_md5 ref_md5
            game_md5=$(md5sum "${game_dll}" | awk '{print $1}')
            ref_md5=$(md5sum "${ref_dll}" | awk '{print $1}')

            if [ "${game_md5}" = "${ref_md5}" ]; then
                log "  ${dll_file}: OK ✓ (MD5: ${game_md5:0:8}...)"
            else
                err "  ${dll_file}: НЕ СОВПАДАЕТ!"
                err "    Игра:   ${game_md5}"
                err "    DXVK:   ${ref_md5}"
                all_ok=false
            fi
        done
    done

    if ${all_ok}; then
        log "Все DLL совпадают с DXVK ${DXVK_VERSION}"
    else
        warn "Некоторые DLL не совпадают — запустите --install для исправления"
    fi
}

# ============================================================================
#  ЗАПУСК ИГРЫ
# ============================================================================

launch_game() {
    local game_entry="$1"
    IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"

    header "Запуск: ${desc}"

    # Проверяем существование
    if [ ! -d "${path}" ]; then
        err "Папка игры не найдена: ${path}"
        return 1
    fi

    if [ ! -f "${path}/${exe}" ]; then
        err "Исполняемый файл не найден: ${path}/${exe}"
        return 1
    fi

    # Проверяем, не запущена ли уже
    local running
    running=$(pgrep -f "${exe}" 2>/dev/null | head -1 || true)
    if [ -n "${running}" ]; then
        warn "${exe} уже запущена (PID: ${running})"
        warn "Для перезапуска: kill ${running}"
        return 0
    fi

    # Перемещаемся в папку игры
    cd "${path}" || { err "Не удалось перейти в ${path}"; return 1; }

    info "Запуск: wine ${exe} ${args}"
    info "WINEPREFIX: ${WINEPREFIX}"
    info "DXVK_ASYNC: ${DXVK_ASYNC}"
    info "FSR: ${WINE_FULLSCREEN_FSR} (strength=${WINE_FULLSCREEN_FSR_STRENGTH})"

    # Запускаем игру
    WINEPREFIX="${WINEPREFIX}" DISPLAY="${DISPLAY}" \n    DXVK_ASYNC="${DXVK_ASYNC}" \n    MESA_VK_WSI_PRESENT_MODE="${MESA_VK_WSI_PRESENT_MODE}" \n    WINE_FULLSCREEN_FSR="${WINE_FULLSCREEN_FSR}" \n    WINE_FULLSCREEN_FSR_STRENGTH="${WINE_FULLSCREEN_FSR_STRENGTH}" \n    MANGOHUD="${MANGOHUD}" \n    PW_USE_ESYNC="${PW_USE_ESYNC}" \n    PW_USE_FSYNC="${PW_USE_FSYNC}" \n    wine "${exe}" ${args} &

    local pid=$!
    sleep 5

    # Проверяем, запустилась ли игра
    if kill -0 "${pid}" 2>/dev/null; then
        log "Игра запущена (PID: ${pid})"
        # Проверяем наличие окна
        sleep 2
        local win
        win=$(DISPLAY="${DISPLAY}" wmctrl -lG 2>/dev/null | grep -i "${name}" | head -1 || true)
        if [ -n "${win}" ]; then
            log "Окно найдено: $(echo "${win}" | awk '{print $NF}')"
        else
            warn "Окно не найдено через wmctrl (может быть fullscreen, подождите)"
        fi
    else
        err "Игра не запустилась (процесс завершился)"
        return 1
    fi
}

# ============================================================================
#  ЗАПУСК ВСЕХ ИГР
# ============================================================================

launch_all() {
    header "Запуск всех игр"

    for game_entry in "${GAME_LIST[@]}"; do
        launch_game "${game_entry}" || true
        sleep 2  # Пауза между запусками
    done

    log "Все игры запущены"
}

# ============================================================================
#  ОТКАТ (УДАЛЕНИЕ DXVK)
# ============================================================================

uninstall_dxvk() {
    header "Откат DXVK — восстановление нативных DLL"

    # Восстановление системных DLL
    info "Восстанавливаем нативные Wine DLL..."
    for dll in "${DXVK_DLL_OVERRIDES[@]}"; do
        for dir in "${SYS64}" "${SYS32}"; do
            local bak="${dir}/${dll}.dll.native.bak"
            local dst="${dir}/${dll}.dll"
            if [ -f "${bak}" ]; then
                cp "${bak}" "${dst}"
                log "  ${dir##*/}/${dll}.dll: восстановлен"
            fi
        done
    done

    # Удаление DXVK из папок игр
    info "Удаляем DXVK DLL из папок игр..."
    for game_entry in "${GAME_LIST[@]}"; do
        IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"

        if [ ! -d "${path}" ]; then
            continue
        fi

        IFS=',' read -ra dll_list <<< "${dlls}"
        for dll in "${dll_list[@]}"; do
            local dll_file="${dll}.dll"
            local bak="${path}/${dll_file}.dxvk${DXVK_VERSION}.bak"
            local dst="${path}/${dll_file}"

            if [ -f "${bak}" ]; then
                cp "${bak}" "${dst}"
                log "  ${name}/${dll_file}: восстановлен из .bak"
            fi
        done
    done

    # Удаление DLL overrides
    info "Удаляем DLL overrides из реестра..."
    for dll in "${DXVK_DLL_OVERRIDES[@]}"; do
        WINEPREFIX="${WINEPREFIX}" DISPLAY="${DISPLAY}" \n            wine reg delete "HKEY_CURRENT_USER\Software\Wine\DllOverrides" \n            /v "${dll}" /f 2>/dev/null && log "  ${dll}: удалён" || true
    done

    log "Откат завершён. Используются нативные Wine DLL."
}

# ============================================================================
#  СОЗДАНИЕ .desktop ФАЙЛА ДЛЯ ЗАПУСКА ИЗ МЕНЮ
# ============================================================================

create_desktop_files() {
    header "Создание .desktop файлов"

    for game_entry in "${GAME_LIST[@]}"; do
        IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"

        if [ ! -d "${path}" ]; then
            continue
        fi

        local desktop_file="${HOME}/.local/share/applications/wine-${name}.desktop"

        cat > "${desktop_file}" << DESKTOP_EOF
[Desktop Entry]
Name=${desc}
Comment=Запуск через Wine + DXVK ${DXVK_VERSION}
Exec=env WINEPREFIX=${WINEPREFIX} DISPLAY=${DISPLAY} DXVK_ASYNC=1 WINE_FULLSCREEN_FSR=1 WINE_FULLSCREEN_FSR_STRENGTH=5 bash -c 'cd "${path}" && wine "${exe}" ${args}'
Icon=applications-games
Terminal=false
Type=Application
Categories=Game;
DESKTOP_EOF

        log "  Создан: ${desktop_file}"
    done
}

# ============================================================================
#  ИНТЕРАКТИВНОЕ МЕНЮ
# ============================================================================

show_menu() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "  ╔═══════════════════════════════════════════════════╗"
    echo "  ║       DXVK Game Launcher v1.0                    ║"
    echo "  ║       Установка DXVK ${DXVK_VERSION} + Запуск игр          ║"
    echo "  ╚═══════════════════════════════════════════════════╝"
    echo -e "${NC}"

    echo -e "  ${BOLD}Текущее состояние:${NC}"
    check_wine 2>/dev/null || true
    check_vulkan 2>/dev/null || true
    echo ""

    echo -e "  ${BOLD}Меню:${NC}"
    echo "  1) Установить DXVK ${DXVK_VERSION}"
    echo "  2) Запустить все игры"
    echo ""
    local i=3
    for game_entry in "${GAME_LIST[@]}"; do
        IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"
        echo "  ${i}) Запустить: ${desc}"
        ((i++))
    done
    echo ""
    echo "  ${i}) Верификация DLL"; ((i++))
    echo "  ${i}) Проверка состояния"; ((i++))
    echo "  ${i}) Создать .desktop файлы"; ((i++))
    echo "  ${i}) Откат (восстановить нативные DLL)"; ((i++))
    echo "  0) Выход"
    echo ""
    echo -n "  Выберите действие: "
}

# ============================================================================
#  СТАТУС
# ============================================================================

show_status() {
    header "Состояние системы"

    echo -e "\n${BOLD}Wine:${NC}"
    check_wine

    echo -e "\n${BOLD}Vulkan:${NC}"
    check_vulkan

    echo -e "\n${BOLD}Display:${NC}"
    check_display

    echo -e "\n${BOLD}WINEPREFIX:${NC}"
    check_prefix

    echo -e "\n${BOLD}DXVK в системном Wine:${NC}"
    for dll in "${DXVK_DLL_OVERRIDES[@]}"; do
        local sys_dll="${SYS32}/${dll}.dll"
        if [ -f "${sys_dll}" ]; then
            local is_dxvk
            is_dxvk=$(strings "${sys_dll}" 2>/dev/null | grep -ci "dxvk" || true)
            if [ "${is_dxvk}" -gt 0 ]; then
                log "  ${dll}.dll: DXVK ✓ ($(stat -c%s "${sys_dll}") bytes)"
            else
                warn "  ${dll}.dll: нативная Wine DLL ($(stat -c%s "${sys_dll}") bytes)"
            fi
        else
            err "  ${dll}.dll: НЕ НАЙДЕН"
        fi
    done

    echo -e "\n${BOLD}Запущенные игры:${NC}"
    local found=false
    for game_entry in "${GAME_LIST[@]}"; do
        IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"
        local pid
        pid=$(pgrep -f "${exe}" 2>/dev/null | head -1 || true)
        if [ -n "${pid}" ]; then
            log "  ${desc}: PID ${pid} ✓"
            found=true
        fi
    done
    if ! ${found}; then
        info "  Нет запущенных игр"
    fi
}

# ============================================================================
#  ГЛАВНОЕ МЕНЮ (CLI)
# ============================================================================

show_help() {
    echo "Использование: $(basename "$0") [ОПЦИЯ]"
    echo ""
    echo "Опции:"
    echo "  --install          Установить DXVK ${DXVK_VERSION} в системный Wine и папки игр"
    echo "  --launch-all       Запустить все игры из списка"
    echo "  --launch <name>    Запустить конкретную игру (alien, gta)"
    echo "  --verify           Проверить MD5 DLL в папках игр"
    echo "  --status           Показать состояние системы"
    echo "  --uninstall        Откатить DXVK, восстановить нативные DLL"
    echo "  --desktop          Создать .desktop файлы для запуска из меню"
    echo "  --help             Показать эту справку"
    echo ""
    echo "Без опций — интерактивное меню."
    echo ""
    echo "Поддерживаемые игры:"
    for game_entry in "${GAME_LIST[@]}"; do
        IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"
        echo "  ${name:12} — ${desc}"
    done
}

main() {
    # Проверяем зависимости
    check_wine
    check_display

    local action="${1:-}"

    case "${action}" in
        --install)
            download_dxvk
            install_dxvk_system
            install_dxvk_games
            verify_dxvk
            log "Установка завершена! Запустите игру: $(basename "$0") --launch-all"
            ;;
        --launch-all)
            launch_all
            ;;
        --launch)
            local target="${2:-}"
            if [ -z "${target}" ]; then
                err "Укажите имя игры: $(basename "$0") --launch <name>"
                exit 1
            fi
            local found=false
            for game_entry in "${GAME_LIST[@]}"; do
                IFS='|' read -r name path exe bits dlls args desc <<< "${game_entry}"
                if [ "${name}" = "${target}" ]; then
                    launch_game "${game_entry}"
                    found=true
                    break
                fi
            done
            if ! ${found}; then
                err "Игра '${target}' не найдена. Доступные: $(printf '%s ' $(for e in "${GAME_LIST[@]}"; do IFS='|' read -r n _ <<< "$e"; echo "$n"; done))"
                exit 1
            fi
            ;;
        --verify)
            download_dxvk
            verify_dxvk
            ;;
        --status)
            show_status
            ;;
        --uninstall)
            uninstall_dxvk
            ;;
        --desktop)
            create_desktop_files
            ;;
        --help|-h)
            show_help
            ;;
        "")
            # Интерактивное меню
            while true; do
                show_menu
                read -r choice
                case "${choice}" in
                    1)
                        download_dxvk
                        install_dxvk_system
                        install_dxvk_games
                        verify_dxvk
                        echo ""
                        echo -n "Нажмите Enter для продолжения..."
                        read -r
                        ;;
                    2)
                        launch_all
                        echo ""
                        echo -n "Нажмите Enter для продолжения..."
                        read -r
                        ;;
                    0)
                        echo "Выход."
                        exit 0
                        ;;
                    *)
                        # Числовые варианты для игр
                        if [[ "${choice}" =~ ^[0-9]+$ ]]; then
                            local idx=$((choice - 3))
                            local total=${#GAME_LIST[@]}
                            if [ "${idx}" -ge 0 ] && [ "${idx}" -lt "${total}" ]; then
                                launch_game "${GAME_LIST[$idx]}"
                                echo ""
                                echo -n "Нажмите Enter для продолжения..."
                                read -r
                            elif [ "${choice}" = "$((total + 3))" ]; then
                                download_dxvk
                                verify_dxvk
                                echo ""
                                echo -n "Нажмите Enter для продолжения..."
                                read -r
                            elif [ "${choice}" = "$((total + 4))" ]; then
                                show_status
                                echo ""
                                echo -n "Нажмите Enter для продолжения..."
                                read -r
                            elif [ "${choice}" = "$((total + 5))" ]; then
                                create_desktop_files
                                echo ""
                                echo -n "Нажмите Enter для продолжения..."
                                read -r
                            elif [ "${choice}" = "$((total + 6))" ]; then
                                uninstall_dxvk
                                echo ""
                                echo -n "Нажмите Enter для продолжения..."
                                read -r
                            else
                                err "Неизвестный вариант: ${choice}"
                                echo ""
                                echo -n "Нажмите Enter для продолжения..."
                                read -r
                            fi
                        else
                            err "Неизвестный вариант: ${choice}"
                            echo ""
                            echo -n "Нажмите Enter для продолжения..."
                            read -r
                        fi
                        ;;
                esac
            done
            ;;
        *)
            err "Неизвестная опция: ${action}"
            echo "Используйте --help для справки"
            exit 1
            ;;
    esac
}

# Запуск
main "$@"
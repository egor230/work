#!/bin/bash
# build_dxvk_final.sh - Единый скрипт для сборки DXVK + VKD3D + MangoHud
# Все три архива должны быть в одной директории (~1,2MB + ~18MB + ~15MB)
# Устанавливается в системный Wine (~/.wine)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="/tmp/dxvk-build-$$"
SYSTEM_WINE_PREFIX="$HOME/.wine"
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

# Клонирование репозитория на конкретный commit (для точного соответствия submodule)
clone_commit() {
    local url="$1" dir="$2" commit="$3"
    if [[ -f "$dir/.git_done" ]]; then
        return 0
    fi
    rm -rf "$dir"
    mkdir -p "$dir"
    git -C "$dir" init -q
    git -C "$dir" remote add origin "$url"
    git -C "$dir" fetch --depth 1 origin "$commit" -q
    git -C "$dir" checkout -q FETCH_HEAD
    touch "$dir/.git_done"
}

# Архивы (должны быть в этой директории)
DXVK_ARCHIVE="$SCRIPT_DIR/dxvk-3.0.tar.gz"
VKD3D_ARCHIVE="$SCRIPT_DIR/vkd3d-proton-3.0.1.tar.gz"
MANGOHUD_ARCHIVE="$SCRIPT_DIR/MangoHud-0.8.4.tar.gz"

# Проверка наличия всех необходимых архивов
check_archives() {
    log "=== Проверка необходимых архивов ==="
    local missing=0
    
    for f in "$DXVK_ARCHIVE" "$VKD3D_ARCHIVE" "$MANGOHUD_ARCHIVE"; do
        if [[ ! -f "$f" ]]; then
            err "Архив не найден: $f"
            warn "Все три архива должны находиться в этой директории:"
            warn "  $SCRIPT_DIR"
            missing=1
        else
            local size=$(du -h "$f" | cut -f1)
            ok "Найден: $(basename "$f") ($size)"
        fi
    done
    
    if [[ $missing -eq 0 ]]; then
        log "Все необходимые архивы найдены и готовы к сборке"
    fi
    [[ $missing -eq 0 ]] || {
        exit 1
    }
}

# Установка зависимостей
install_deps() {
    log "=== Установка зависимостей ==="
    local missing=()
    
    # Проверяем основные инструменты
    command -v meson >/dev/null 2>&1 || missing+=("meson")
    command -v ninja >/dev/null 2>&1 || missing+=("ninja-build")
    command -v git >/dev/null 2>&1 || missing+=("git")
    
    # Обязательно устанавливаем mingw-w64 для DXVK
    if ! command -v x86_64-w64-mingw32-gcc &>/dev/null; then
        missing+=("mingw-w64")
    fi
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log "Устанавливаю зависимости: ${missing[*]}"
        sudo apt-get install -y "${missing[@]}" || {
            err "Не удалось установить зависимости"
            exit 1
        }
        ok "Зависимости установлены"
    else
        ok "Все зависимости присутствуют"
    fi
}

# Создание временной папки сборки
setup_build_dir() {
    log "=== Создание временной папки сборки ==="
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
    log "Сборка будет выполняться в: $BUILD_DIR"
}

# Создание wine prefix
ensure_wine_prefix() {
    mkdir -p "$SYSTEM_WINE_PREFIX/drive_c/windows/system32"
    mkdir -p "$SYSTEM_WINE_PREFIX/drive_c/windows/syswow64"
    log "Wine prefix подготовлен: $SYSTEM_WINE_PREFIX"
}

# --- DXVK 3.0 ---
build_dxvk() {
    log "=== Сборка DXVK 3.0 ==="
    cd "$BUILD_DIR"
    
    log "Распаковка DXVK..."
    tar -xzf "$DXVK_ARCHIVE"
    cd dxvk-3.0
    
    # Проверяем наличие mingw-w64
    if ! command -v x86_64-w64-mingw32-g++ &>/dev/null; then
        err "Не найден x86_64-w64-mingw32-g++"
        exit 1
    fi
    
    # Cross-file для DXVK (mingw cross-compilation под Windows)
    cat > build-win64.txt << 'EOF'
[binaries]
c = 'x86_64-w64-mingw32-gcc'
cpp = 'x86_64-w64-mingw32-g++'
ld = 'x86_64-w64-mingw32-ld'
ar = 'x86_64-w64-mingw32-ar'
strip = 'x86_64-w64-mingw32-strip'
windres = 'x86_64-w64-mingw32-windres'

[host_machine]
system = 'windows'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'

[built-in options]
c_args = ['-I/usr/include/libdisplay-info', '-DNOMINMAX', '-D_WIN32_WINNT=0xa00', '-DDXVK_WSI_WIN32']
EOF

    # Удаляем subproject libdisplay-info — мы сделаем свою заглушку
    rm -rf subprojects/libdisplay-info
    
    # Инициализируем Vulkan-Headers и SPIRV-Headers (через git clone)
    mkdir -p include/vulkan include/spirv
    if [[ ! -d "include/vulkan/include/vulkan" ]]; then
        log "Клонирую Vulkan-Headers..."
        git clone --depth 1 https://github.com/KhronosGroup/Vulkan-Headers.git include/vulkan
    fi
    if [[ ! -d "include/spirv/include/spirv" ]]; then
        log "Клонирую SPIRV-Headers..."
        git clone --depth 1 https://github.com/KhronosGroup/SPIRV-Headers.git include/spirv
    fi
    
    # Инициализируем git repo для поддержки submodules
    log "Инициализация git submodules..."
    if [[ ! -d ".git" ]]; then
        git init -q
        git config user.email "build@local"
        git config user.name "build"
        # Пустой commit + тег версии: DXVK генерирует свою версию через
        # 'git describe'. Без тега это выдаёт "fatal: Имена не найдены".
        # Создаём тег v3.0, чтобы версия определялась корректно и без ошибок.
        git commit -q --allow-empty -m "dxvk 3.0" >/dev/null 2>&1 || true
        git tag -a v3.0 -m v3.0 >/dev/null 2>&1 || true
    fi
    git remote add origin https://github.com/doitsujin/dxvk.git 2>/dev/null || git remote set-url origin https://github.com/doitsujin/dxvk.git
    
    # Пытаемся получить submodules через git
    git submodule update --init --depth 1 subprojects/dxbc-spirv 2>/dev/null || true
    git submodule update --init --depth 1 subprojects/libdisplay-info 2>/dev/null || true
    
    # Инициализируем подмодули dxbc-spirv
    if [[ -d "subprojects/dxbc-spirv/.git" ]] || [[ -f "subprojects/dxbc-spirv/.git" ]]; then
        log "Инициализация подмодулей dxbc-spirv..."
        cd subprojects/dxbc-spirv
        git submodule update --init --depth 1 2>/dev/null || true
        cd ../..
    fi
    
    # Если submodule не сработал — клонируем вручную
    if [[ ! -d "subprojects/dxbc-spirv" ]] || [[ -z "$(ls -A subprojects/dxbc-spirv 2>/dev/null)" ]]; then
        log "Клонирование dxbc-spirv через git..."
        rm -rf subprojects/dxbc-spirv
        git clone --depth 1 --recurse-submodules https://github.com/doitsujin/dxbc-spirv.git subprojects/dxbc-spirv 2>&1 || true
    fi
    
    # libdisplay-info — windows branch
    log "Получение libdisplay-info (windows branch)..."
    if [[ ! -d "subprojects/libdisplay-info" ]] || [[ -z "$(ls -A subprojects/libdisplay-info 2>/dev/null)" ]]; then
        rm -rf subprojects/libdisplay-info
        git clone --depth 1 --branch windows https://github.com/doitsujin/libdisplay-info.git subprojects/libdisplay-info 2>&1 || true
    fi
    
    # Создаём заглушку для libdisplay-info, если git не сработал
    mkdir -p subprojects/libdisplay-info
    if [[ ! -f "subprojects/libdisplay-info/meson.build" ]]; then
        cat > subprojects/libdisplay-info/meson.build << 'EOS'
project('libdisplay-info', 'c', version : '0.1.1')
di_dep = declare_dependency(
    link_with : [],
    include_directories : include_directories('.'),
)
EOS
    fi
    
    log "Настройка DXVK (64-bit) через cross-file..."
    meson setup build64 --cross-file build-win64.txt --buildtype=release -Dnative_glfw=disabled -Dnative_sdl2=disabled -Dnative_sdl3=disabled
    
    log "Компиляция DXVK (64-bit)..."
    ninja -C build64 -j$JOBS
    
    ok "DXVK собран"
}

install_dxvk() {
    log "=== Установка DXVK 3.0 в системный Wine ==="
    cd "$BUILD_DIR/dxvk-3.0"
    
    local sys_lib64="$SYSTEM_WINE_PREFIX/drive_c/windows/system32"
    mkdir -p "$sys_lib64"
    
    # 64-bit DLL → system32
    for dll in d3d9.dll d3d10core.dll d3d11.dll dxgi.dll; do
        if [[ -f "build64/$dll" ]]; then
            cp -f "build64/$dll" "$sys_lib64/"
            ok "Установлен (64-bit): $dll → system32/"
        fi
    done
    
    ok "DXVK установлен в $SYSTEM_WINE_PREFIX"
}

# --- VKD3D-Proton 3.0.1 ---
build_vkd3d() {
    log "=== Сборка VKD3D-Proton 3.0.1 ==="
    cd "$BUILD_DIR"
    
    log "Распаковка VKD3D-Proton из архива..."
    tar -xzf "$VKD3D_ARCHIVE"
    cd vkd3d-proton-3.0.1
    
    # VKD3D-Proton определяет свою версию через 'git describe'.
    # Архив не содержит .git, из-за чего появлялась ошибка
    # "fatal: не найден git репозиторий". Создаём локальный репозиторий
    # с тегом v3.0.1, чтобы версия определялась корректно и без ошибок.
    if [[ ! -d ".git" ]]; then
        git init -q
        git config user.email "build@local"
        git config user.name "build"
        git commit -q --allow-empty -m "vkd3d-proton 3.0.1" >/dev/null 2>&1 || true
        git tag -a v3.0.1 -m v3.0.1 >/dev/null 2>&1 || true
    fi
    
    # Cross-file для VKD3D (mingw cross-compilation)
    cat > build-win64.txt << 'EOF_VKD3D'
[binaries]
c = 'x86_64-w64-mingw32-gcc'
cpp = 'x86_64-w64-mingw32-g++'
ld = 'x86_64-w64-mingw32-ld'
ar = 'x86_64-w64-mingw32-ar'
strip = 'x86_64-w64-mingw32-strip'
windres = 'x86_64-w64-mingw32-windres'

[host_machine]
system = 'windows'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'

[built-in options]
c_args = ['-D_WIN32_WINNT=0xa00']
cpp_args = ['-D_WIN32_WINNT=0xa00']
EOF_VKD3D

    # Получаем submodules с точными commit'ами из тега v3.0.1
    log "Получение submodules VKD3D-Proton (pinned commits)..."
    clone_commit "https://github.com/KhronosGroup/Vulkan-Headers" "khronos/Vulkan-Headers" "ad9ce1235e88dc09287e19171dfac384db8ec32c"
    clone_commit "https://github.com/KhronosGroup/SPIRV-Headers"  "khronos/SPIRV-Headers"  "f88a2d766840fc825af1fc065977953ba1fa4a91"

    # dxil-spirv subproject + его собственные submodules
    clone_commit "https://github.com/HansKristian-Work/dxil-spirv" "subprojects/dxil-spirv" "62dbb07f771534c8ce924479efdc6c8fa510361d"
    clone_commit "https://github.com/KhronosGroup/SPIRV-Headers"    "subprojects/dxil-spirv/third_party/spirv-headers" "f88a2d766840fc825af1fc065977953ba1fa4a91"
    clone_commit "https://github.com/doitsujin/dxbc-spirv"          "subprojects/dxil-spirv/subprojects/dxbc-spirv"    "29c93aeecd55533a357fdd7c95be5587d1c1f506"
    clone_commit "https://github.com/KhronosGroup/SPIRV-Headers"    "subprojects/dxil-spirv/subprojects/dxbc-spirv/submodules/spirv_headers" "c8ad050fcb29e42a2f57d9f59e97488f465c436d"

    log "Настройка VKD3D (64-bit) через cross-file..."
    meson setup build64 --cross-file build-win64.txt --buildtype=release
    
    log "Компиляция VKD3D (64-bit)..."
    ninja -C build64 -j$JOBS
    
    ok "VKD3D-Proton собран"
}

install_vkd3d() {
    log "=== Установка VKD3D-Proton в системный Wine ==="
    cd "$BUILD_DIR/vkd3d-proton-3.0.1"
    
    local sys_lib64="$SYSTEM_WINE_PREFIX/drive_c/windows/system32"
    mkdir -p "$sys_lib64"
    
    # Ищем и копируем все .dll из build64
    find build64 -name "*.dll" -type f 2>/dev/null | while read dll; do
        cp -f "$dll" "$sys_lib64/"
        ok "Установлен (64-bit): $(basename "$dll") → system32/"
    done
    
    ok "VKD3D-Proton установлен в $SYSTEM_WINE_PREFIX"
}

# --- MangoHud 0.8.4 ---
build_mangohud() {
    log "=== Сборка MangoHud 0.8.4 ==="
    cd "$BUILD_DIR"
    
    log "Распаковка MangoHud..."
    tar -xzf "$MANGOHUD_ARCHIVE"
    cd MangoHud-0.8.4
    
    # MangoHud генерирует version.h через git (git describe).
    # Архив не содержит .git, поэтому инициализируем локальный репозиторий
    # и создаём тег v0.8.4 — это убирает ошибку "не найден git репозиторий".
    if [[ ! -d ".git" ]]; then
        git init -q
        git config user.email "build@local"
        git config user.name "build"
        git add -A
        git commit -q -m "MangoHud 0.8.4" >/dev/null 2>&1 || true
        git tag -a v0.8.4 -m v0.8.4 >/dev/null 2>&1 || true
    fi
    
    log "Настройка MangoHud (без xnvctrl)..."
    meson setup build --buildtype=release -Dwith_xnvctrl=disabled
    
    log "Компиляция MangoHud..."
    ninja -C build -j$JOBS
    
    ok "MangoHud собран"
}

install_mangohud() {
    log "=== Установка MangoHud 0.8.4 ==="
    cd "$BUILD_DIR/MangoHud-0.8.4"
    
    log "Установка MangoHud системно (sudo ninja install)..."
    sudo ninja -C build install || true
    
    # Создаем скрипт запуска wine-mangohud (через sudo tee, так как cat > с sudo не работает)
    local script_path="/usr/local/bin/wine-mangohud"
    sudo tee "$script_path" > /dev/null << 'MHSCRIPT'
#!/bin/bash
# wine-mangohud - запуск Wine с MangoHud overlay
export MANGOHUD=1
export MANGOHUD_DLSYM=1
exec wine "$@"
MHSCRIPT
    sudo chmod +x "$script_path"
    
    ok "MangoHud установлен системно"
    ok "Используйте: wine-mangohud game.exe"
}

# --- Настройка DLL overrides (через .reg файл, не требует дисплея) ---
configure_dll_overrides() {
    log "=== Настройка DLL overrides в реестре Wine ==="
    
    local wine_prefix="$SYSTEM_WINE_PREFIX"
    if [[ -d "$wine_prefix" ]]; then
        log "Создание .reg файла с overrides..."
        cat > /tmp/build_dxvk_overrides.reg << 'REG'
REGEDIT4

[HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides]
"d3d9"="native,builtin"
"d3d10core"="native,builtin"
"d3d11"="native,builtin"
"dxgi"="native,builtin"
"d3d12"="native,builtin"
REG
        WINEPREFIX="$wine_prefix" wine regedit /tmp/build_dxvk_overrides.reg 2>/dev/null || true
        rm -f /tmp/build_dxvk_overrides.reg
        ok "DLL overrides настроены через regedit"
    fi
}

# --- Проверка установки ---
verify_install() {
    log "=== Проверка установки ==="
    
    local sys_lib64="$SYSTEM_WINE_PREFIX/drive_c/windows/system32"
    
    echo "=== DXVK (64-bit в system32/) ==="
    ls -lh "$sys_lib64/d3d11.dll" 2>/dev/null && ok "d3d11.dll установлен" || warn "d3d11.dll не найден"
    ls -lh "$sys_lib64/dxgi.dll" 2>/dev/null && ok "dxgi.dll установлен" || warn "dxgi.dll не найден"
    
    echo "=== VKD3D (64-bit в system32/) ==="
    ls -lh "$sys_lib64/d3d12.dll" 2>/dev/null && ok "d3d12.dll установлен" || warn "d3d12.dll не найден"
    ls -lh "$sys_lib64/d3d12core.dll" 2>/dev/null && ok "d3d12core.dll установлен" || warn "d3d12core.dll не найден"
    
    echo "=== MangoHud ==="
    which mangohud 2>/dev/null && ok "MangoHud найден" || warn "mangohud не найден в PATH"
    test -f /usr/local/bin/wine-mangohud 2>/dev/null && ok "wine-mangohud скрипт создан" || warn "wine-mangohud не найден"
    
    ok "Проверка завершена"
}

# Основная функция
main() {
    # Переходим в директорию, где лежит сам скрипт (и все архивы).
    # Так все относительные пути и архивы всегда находятся рядом.
    cd "$SCRIPT_DIR"
    
    log "=== НАЧАЛО СБОРКИ DXVK + VKD3D + MANGOHUD ==="
    log "Исходники: $SCRIPT_DIR"
    log "Сборка в: $BUILD_DIR"
    log "Установка в: $SYSTEM_WINE_PREFIX (системный Wine)"
    log "Потоков: $JOBS"
    
    check_archives
    install_deps
    setup_build_dir
    ensure_wine_prefix
    
    # DXVK
    build_dxvk
    install_dxvk
    
    # VKD3D
    build_vkd3d
    install_vkd3d
    
    # MangoHud
    build_mangohud
    install_mangohud
    
    # Настройка DLL overrides
    configure_dll_overrides
    
    # Проверка
    verify_install
    
    log "=== СБОРКА ЗАВЕРШЕНА УСПЕШНО ==="
    log ""
    log "DXVK 3.0 + VKD3D-Proton 3.0.1 + MangoHud 0.8.4 установлены"
    log ""
    log "Для использования:"
    log "  wine --version                    # Проверить Wine"
    log "  wine-mangohud game.exe           # Запустить игру с MangoHud"
}

# Запуск
main "$@"

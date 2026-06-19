#!/usr/bin/env bash
# ULTIMATE AUTONOMOUS PYTHON + UV SETUP v4.0 — «Полностью автоматический + Защита от несуществующих версий»
# Критические улучшения:
#   • Многоуровневая валидация версии Python (проверка формата + существование URL)
#   • Автоматический fallback на последнюю стабильную версию при ошибках
#   • Глубокая проверка загружаемых файлов (размер, сигнатура gzip, анализ содержимого)
#   • Интеллектуальные зеркала загрузки при недоступности основного URL
#   • Защита от 404 ошибок на всех этапах
# Автор: доработано с учетом реальных сценариев использования

set -euo pipefail
IFS=$'\n\t'

# --- Параметры ---
AUTO_YES=false    # если true — добавляем флаг -y к пакетным менеджерам
QUIET=false       # если true — сокращаем вывод (логи сохраняются)
WORK_DIR="$(pwd)"
PYTHON_INSTALL_SUBDIR="python_runtime"
VENV_NAME="myenv_uv_latest"
MAX_DOWNLOAD_ATTEMPTS=3
MIN_ARCHIVE_SIZE=5000000  # 5 MB (реальный архив Python ~25MB+)
MIRRORS=(
    "https://www.python.org/ftp/python"
    "https://npm.taobao.org/mirrors/python"  # Надежное зеркало для Китая
    "https://www.mirrorservice.org/sites/ftp.python.org/pub/python"  # Европейское зеркало
)

# --- Пути ---
PYTHON_INSTALL_PATH="$WORK_DIR/$PYTHON_INSTALL_SUBDIR"
VENV_FULL_PATH="$WORK_DIR/$VENV_NAME"
ACTIVATE_SCRIPT="$VENV_FULL_PATH/bin/activate"

TEMP_DIR=""
PYTHON_TAR_FILE=""
PYTHON_SOURCE_DIR=""
PYTHON_VERSION=""
PYTHON_INTERPRETER=""
PYTHON_BASE_URL=""
LOG_FILE=""

# --- Цвета ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
MAGENTA='\033[0;35m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# --- Логирование ---
log()    { echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')] ℹ $1${NC}" | tee -a "$LOG_FILE"; }
success(){ echo -e "${GREEN}[$(date +'%H:%M:%S')] ✓ $1${NC}" | tee -a "$LOG_FILE"; }
error()  { echo -e "${RED}[$(date +'%H:%M:%S')] ✗ ОШИБКА: $1${NC}" >&2 | tee -a "$LOG_FILE"; }
warn()   { echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠ ПРЕДУПРЕЖДЕНИЕ: $1${NC}" | tee -a "$LOG_FILE"; }
info()   { echo -e "${BLUE}[$(date +'%H:%M:%S')] → $1${NC}" | tee -a "$LOG_FILE"; }
detail() { echo -e "${MAGENTA}[$(date +'%H:%M:%S')]   ↳ $1${NC}" | tee -a "$LOG_FILE"; }

banner() {
    clear
    echo -e "${MAGENTA}$(printf '=%.0s' {1..80})\n   $1\n$(printf '=%.0s' {1..80})${NC}\n"
}

usage() {
    cat <<EOF
Usage: $0 [--yes|-y] [--quiet|-q] [--workdir DIR]

Options:
  -y, --yes        Автоматически отвечать "yes" для установок через пакетный менеджер
  -q, --quiet      Уменьшить количество выводимых сообщений (логи по-прежнему сохраняются)
  --workdir DIR    Рабочая директория (по умолчанию: текущая)
  -h, --help       Показать это сообщение
EOF
    exit 0
}

# --- Разбор аргументов ---
while (( "$#" )); do
    case "$1" in
        -y|--yes) AUTO_YES=true; shift ;;
        -q|--quiet) QUIET=true; shift ;;
        --workdir) WORK_DIR="$2"; shift 2 ;;
        -h|--help) usage ;;
        --) shift; break ;;
        *) warn "Неизвестный аргумент: $1"; usage ;;
    esac
done

LOG_FILE="/tmp/ultimate-python-setup-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

trap 'error "Неожиданное завершение. Выполняем очистку..."; cleanup || true; exit 1' ERR INT TERM

# --- Утилиты помощи ---
apt_yes() { $AUTO_YES && echo -n "-y" || echo -n ""; }
command_exists() { command -v "$1" >/dev/null 2>&1; }

# --- Проверка формата версии ---
valid_version_format() {
    [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] && return 0
    return 1
}

# --- Проверка существования URL ---
url_exists() {
    local url="$1"
    local timeout=5
    
    if command_exists curl; then
        # Проверка через HEAD запрос
        if curl -sSfLI --max-time "$timeout" "$url" >/dev/null 2>&1; then
            return 0
        fi
        # Если HEAD не поддерживается - проверяем первый байт
        if curl -sSfL --max-time "$timeout" --range 0-0 "$url" >/dev/null 2>&1; then
            return 0
        fi
    elif command_exists wget; then
        if wget --spider --quiet --timeout="$timeout" "$url" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# --- Проверка корректности архива ---
validate_archive() {
    local file="$1"
    
    # Проверка 1: Размер файла
    local size
    size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)
    if [ "$size" -lt "$MIN_ARCHIVE_SIZE" ]; then
        warn "Файл слишком маленький (размер: $size байт, минимум: $MIN_ARCHIVE_SIZE)"
        return 1
    fi
    
    # Проверка 2: Сигнатура gzip (1f 8b)
    if ! head -c 2 "$file" | hexdump -e '"%02x"' | grep -q "1f8b"; then
        warn "Файл не имеет сигнатуры gzip (ожидалось: 1f8b, получено: $(head -c 2 "$file" | hexdump -e '"%02x"'))"
        return 1
    fi
    
    # Проверка 3: Попытка распаковать
    if ! tar -tzf "$file" > /dev/null 2>&1; then
        warn "Файл не является валидным tar.gz архивом"
        return 1
    fi
    
    # Проверка 4: Анализ содержимого на наличие HTML
    if grep -qi "<html" "$file" 2>/dev/null; then
        warn "Файл содержит HTML-теги (возможно, страница ошибки)"
        return 1
    fi
    
    return 0
}

# --- Выбор зеркала ---
get_best_mirror() {
    for mirror in "${MIRRORS[@]}"; do
        local test_url="${mirror}/3.12.3/Python-3.12.3.tgz"  # Проверяем на известной версии
        if url_exists "$test_url"; then
            success "Рабочее зеркало найдено: $mirror"
            echo "$mirror"
            return 0
        fi
    done
    error "Все зеркала недоступны. Проверьте интернет-соединение."
    exit 1
}

# --- Проверка дистрибутива для установки зависимостей ---
detect_pkg_manager() {
    if command_exists apt-get || command_exists apt; then
        echo "apt"
    elif command_exists dnf; then
        echo "dnf"
    elif command_exists yum; then
        echo "yum"
    elif command_exists pacman; then
        echo "pacman"
    else
        echo "unknown"
    fi
}

# --- Установка системных зависимостей ---
check_system_deps() {
    banner "ПРОВЕРКА СИСТЕМНЫХ ЗАВИСИМОСТЕЙ"

    # Критические зависимости для сборки
    local deps=(
        curl wget tar gcc make
        libssl-dev zlib1g-dev libbz2-dev
        libreadline-dev libsqlite3-dev libncursesw5-dev
        libgdbm-dev liblzma-dev tk-dev
    )
    local missing=()
    local pm
    pm=$(detect_pkg_manager)

    log "Проверяем наличие критических зависимостей..."
    for dep in "${deps[@]}"; do
        if dpkg -s "$dep" >/dev/null 2>&1 || pacman -Qi "$dep" >/dev/null 2>&1 || command_exists "$dep"; then
            detail "Найдено: $dep"
        else
            warn "Не найдено: $dep"
            missing+=("$dep")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        error "Отсутствуют критические пакеты: ${missing[*]}"
        
        if ! command_exists sudo; then
            error "sudo недоступен. Установите пакеты вручную или запустите скрипт от имени root."
            exit 1
        fi

        case "$pm" in
            apt)
                info "Пытаемся установить через apt"
                sudo apt update -qq | tee -a "$LOG_FILE" || warn "apt update не прошёл"
                sudo apt install -qq $(apt_yes) "${missing[@]}" | tee -a "$LOG_FILE" || { 
                    error "Не удалось установить пакеты через apt"; 
                    exit 1; 
                }
                ;;
            dnf|yum)
                info "Пытаемся установить через $pm"
                sudo "$pm" install -y "${missing[@]}" | tee -a "$LOG_FILE" || { 
                    error "Не удалось установить пакеты через $pm"; 
                    exit 1; 
                }
                ;;
            pacman)
                info "Пытаемся установить через pacman"
                sudo pacman -S --noconfirm "${missing[@]}" | tee -a "$LOG_FILE" || { 
                    error "Не удалось установить пакеты через pacman"; 
                    exit 1; 
                }
                ;;
            *)
                error "Неизвестный пакетный менеджер ($pm). Установите вручную: ${missing[*]}"
                exit 1
                ;;
        esac
        success "Зависимости установлены"
    else
        success "Все системные зависимости удовлетворены"
    fi
}

# --- Получение последней стабильной версии Python ---
get_latest_python() {
    banner "ЭТАП 1: ПОИСК ПОСЛЕДНЕЙ СТАБИЛЬНОЙ ВЕРСИИ PYTHON"
    
    # Выбираем лучшее зеркало
    PYTHON_BASE_URL=$(get_best_mirror)
    
    # Метод 1: Официальный API (только стабильные версии)
    info "Метод 1: Запрос к официальному API python.org"
    if command_exists curl; then
        local api_data
        api_data=$(curl -sSfL --connect-timeout 10 "https://www.python.org/api/v2/downloads/release/?is_published=true&is_latest=true" 2>/dev/null || true)
        
        if [[ -n "$api_data" ]]; then
            # Извлекаем версию и проверяем формат
            if [[ "$api_data" =~ \"version\":\"([0-9]+\.[0-9]+\.[0-9]+)\" ]]; then
                PYTHON_VERSION="${BASH_REMATCH[1]}"
                
                if valid_version_format "$PYTHON_VERSION"; then
                    local test_url="${PYTHON_BASE_URL}/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"
                    if url_exists "$test_url"; then
                        PYTHON_FULL_URL="$test_url"
                        success "Версия подтверждена через API: $PYTHON_VERSION"
                        detail "URL: $PYTHON_FULL_URL"
                        return 0
                    else
                        warn "Версия $PYTHON_VERSION недоступна для загрузки"
                    fi
                else
                    warn "Некорректный формат версии из API: $PYTHON_VERSION"
                fi
            fi
        fi
    fi

    # Метод 2: Анализ страницы загрузок
    info "Метод 2: Анализ страницы загрузок"
    if command_exists curl; then
        local html
        html=$(curl -sSfL --connect-timeout 10 "https://www.python.org/downloads/" 2>/dev/null || true)
        
        if [[ -n "$html" ]]; then
            # Извлекаем все ссылки на архивы
            local links
            links=$(echo "$html" | grep -oE 'href="[^"]*Python-[0-9]+\.[0-9]+\.[0-9]+\.tgz"' | sed 's/href="//;s/"$//')
            
            while IFS= read -r link; do
                # Извлекаем версию из URL
                if [[ "$link" =~ Python-([0-9]+\.[0-9]+\.[0-9]+)\.tgz ]]; then
                    local candidate_version="${BASH_REMATCH[1]}"
                    
                    if valid_version_format "$candidate_version"; then
                        local candidate_url="https://www.python.org$link"
                        # Проверяем зеркала
                        for mirror in "${MIRRORS[@]}"; do
                            local test_url="${mirror}/${candidate_version}/Python-${candidate_version}.tgz"
                            if url_exists "$test_url"; then
                                PYTHON_VERSION="$candidate_version"
                                PYTHON_FULL_URL="$test_url"
                                success "Версия найдена через анализ страницы: $PYTHON_VERSION"
                                detail "URL: $PYTHON_FULL_URL"
                                return 0
                            fi
                        done
                    fi
                fi
            done <<< "$links"
        fi
    fi

    # Метод 3: Fallback на известные стабильные версии
    info "Метод 3: Fallback на безопасные версии"
    local safe_versions=(
        "3.12.7" "3.12.6" "3.12.5" "3.12.4" "3.12.3"  # Последние 3.12.x
        "3.11.9" "3.11.8" "3.11.7"                     # Резервные 3.11.x
    )
    
    for ver in "${safe_versions[@]}"; do
        for mirror in "${MIRRORS[@]}"; do
            local test_url="${mirror}/${ver}/Python-${ver}.tgz"
            if url_exists "$test_url"; then
                PYTHON_VERSION="$ver"
                PYTHON_FULL_URL="$test_url"
                warn "Используем последнюю стабильную версию: $PYTHON_VERSION"
                detail "URL: $PYTHON_FULL_URL"
                return 0
            fi
        done
    done

    # Критическая ошибка
    error "Не удалось определить рабочую версию Python. Проверьте доступность зеркал."
    detail "Попробуйте выполнить вручную: curl -I https://www.python.org/ftp/python/"
    exit 1
}

# --- Скачивание Python с интеллектуальной обработкой ошибок ---
download_python() {
    banner "ЭТАП 2: ЗАГРУЗКА PYTHON $PYTHON_VERSION"
    PYTHON_TAR_FILE="$WORK_DIR/Python-${PYTHON_VERSION}.tgz"

    # Проверяем существующий файл
    if [[ -f "$PYTHON_TAR_FILE" ]]; then
        info "Проверка существующего архива: $PYTHON_TAR_FILE"
        if validate_archive "$PYTHON_TAR_FILE"; then
            success "Существующий архив корректен"
            detail "Файл: $PYTHON_TAR_FILE — $(du -h "$PYTHON_TAR_FILE" | awk '{print $1}')"
            return 0
        else
            warn "Архив поврежден или не соответствует версии — удаляем"
            rm -f "$PYTHON_TAR_FILE"
        fi
    fi

    log "Источник: $PYTHON_FULL_URL"
    local attempt=1

    while [ $attempt -le $MAX_DOWNLOAD_ATTEMPTS ]; do
        info "Попытка загрузки #$attempt/$MAX_DOWNLOAD_ATTEMPTS..."
        
        # Удаляем частично загруженные файлы
        rm -f "$PYTHON_TAR_FILE".part 2>/dev/null || true
        
        if command_exists wget; then
            if wget --progress=bar:force --tries=1 --timeout=30 -c -O "$PYTHON_TAR_FILE".part "$PYTHON_FULL_URL" 2>&1 | tee -a "$LOG_FILE"; then
                mv "$PYTHON_TAR_FILE".part "$PYTHON_TAR_FILE"
                success "Загрузка завершена (wget)"
            else
                local wget_status=${PIPESTATUS[0]}
                if [ $wget_status -eq 8 ]; then  # Серверная ошибка (404 и т.д.)
                    error "Сервер вернул ошибку (код $wget_status). Версия $PYTHON_VERSION недоступна."
                    exit 1
                fi
                warn "wget завершился с ошибкой $wget_status, пробуем curl"
            fi
        elif command_exists curl; then
            if curl -L --progress-bar --retry 1 --max-time 30 -C - -o "$PYTHON_TAR_FILE".part "$PYTHON_FULL_URL" 2>&1 | tee -a "$LOG_FILE"; then
                mv "$PYTHON_TAR_FILE".part "$PYTHON_TAR_FILE"
                success "Загрузка завершена (curl)"
            else
                local curl_status=$?
                if [ $curl_status -eq 22 ]; then  # HTTP ошибка (404)
                    error "HTTP ошибка (код $curl_status). Версия $PYTHON_VERSION недоступна."
                    exit 1
                fi
                warn "curl завершился с ошибкой $curl_status"
            fi
        else
            error "Не установлены wget или curl. Установите вручную и повторите."
            exit 1
        fi

        # Валидация загруженного файла
        if [ -f "$PYTHON_TAR_FILE" ] && validate_archive "$PYTHON_TAR_FILE"; then
            success "Архив прошел все проверки"
            detail "Файл: $PYTHON_TAR_FILE — $(du -h "$PYTHON_TAR_FILE" | awk '{print $1}')"
            return 0
        else
            warn "Архив не прошел проверку. Удаляем и повторяем попытку..."
            rm -f "$PYTHON_TAR_FILE" 2>/dev/null || true
        fi

        attempt=$((attempt + 1))
        sleep 2
    done

    error "Не удалось скачать корректный архив после $MAX_DOWNLOAD_ATTEMPTS попыток"
    detail "Проверьте URL вручную: $PYTHON_FULL_URL"
    exit 1
}

# --- Распаковка и сборка ---
extract_and_compile_python() {
    banner "ЭТАП 3: КОМПИЛЯЦИЯ PYTHON $PYTHON_VERSION"

    TEMP_DIR=$(mktemp -d -t python-build-XXXXXX)
    detail "Временная директория: $TEMP_DIR"

    info "Распаковываем архив..."
    if ! tar -xzf "$PYTHON_TAR_FILE" -C "$TEMP_DIR" --strip-components=1; then
        error "Ошибка распаковки архива. Проверьте целостность файла."
        exit 1
    fi
    success "Архив распакован"
    PYTHON_SOURCE_DIR="$TEMP_DIR"

    mkdir -p "$PYTHON_INSTALL_PATH"
    pushd "$PYTHON_SOURCE_DIR" >/dev/null

    info "Запускаем ./configure"
    local configure_log="/tmp/python-configure-$(date +%s).log"
    if ! ./configure --prefix="$PYTHON_INSTALL_PATH" --enable-optimizations --with-ensurepip=install > "$configure_log" 2>&1; then
        error "configure завершился с ошибкой. Лог: $configure_log"
        tail -n 20 "$configure_log" | tee -a "$LOG_FILE"
        exit 1
    fi
    success "configure завершён успешно"

    local cores
    cores=$(nproc 2>/dev/null || echo 2)
    info "Запуск make с $cores ядрами"
    local make_log="/tmp/python-make-$(date +%s).log"
    if ! make -j "$cores" > "$make_log" 2>&1; then
        error "make завершился с ошибкой. Лог: $make_log"
        tail -n 50 "$make_log" | tee -a "$LOG_FILE"
        exit 1
    fi
    success "make завершён успешно"

    info "Установка (altinstall)"
    local install_log="/tmp/python-install-$(date +%s).log"
    if ! sudo make altinstall > "$install_log" 2>&1; then
        error "make altinstall завершился с ошибкой. Лог: $install_log"
        tail -n 50 "$install_log" | tee -a "$LOG_FILE"
        exit 1
    fi
    success "make altinstall завершён успешно"

    # Поиск интерпретатора
    PYTHON_INTERPRETER="$PYTHON_INSTALL_PATH/bin/python3"
    if [ ! -x "$PYTHON_INTERPRETER" ]; then
        PYTHON_INTERPRETER=$(find "$PYTHON_INSTALL_PATH/bin" -name 'python3*' -type f -executable 2>/dev/null | head -1)
    fi

    if [ -z "$PYTHON_INTERPRETER" ] || [ ! -x "$PYTHON_INTERPRETER" ]; then
        error "Не найден установленный интерпретатор в $PYTHON_INSTALL_PATH/bin"
        exit 1
    fi

    detail "Интерпретатор: $PYTHON_INTERPRETER — $($PYTHON_INTERPRETER --version 2>&1 | awk '{print $2}')"
    popd >/dev/null
}

# --- Установка uv ---
install_uv() {
    banner "ЭТАП 4: УСТАНОВКА UV"

    if [ -z "$PYTHON_INTERPRETER" ] || [ ! -x "$PYTHON_INTERPRETER" ]; then
        error "Python интерпретатор недоступен: $PYTHON_INTERPRETER"
        exit 1
    fi

    info "Используем интерпретатор: $PYTHON_INTERPRETER"
    local uv_installer="/tmp/uv-installer-$(date +%s).sh"

    # Попытка 1: Официальный скрипт
    if command_exists curl; then
        info "Попытка установки через официальный скрипт"
        if curl -fsSL --connect-timeout 10 https://astral.sh/uv/install.sh -o "$uv_installer"; then
            chmod +x "$uv_installer"
            if UV_INSTALL_DIR="$WORK_DIR/uv_bin" sh "$uv_installer" 2>&1 | tee -a "$LOG_FILE"; then
                export PATH="$WORK_DIR/uv_bin:$PATH"
                success "UV установлен через официальный скрипт"
                rm -f "$uv_installer"
                return 0
            fi
        fi
        rm -f "$uv_installer" 2>/dev/null || true
    fi

    # Попытка 2: pip
    info "Попытка установки через pip"
    if "$PYTHON_INTERPRETER" -m pip --version >/dev/null 2>&1; then
        if "$PYTHON_INTERPRETER" -m pip install --user --quiet uv >/dev/null 2>&1; then
            local user_bin
            user_bin=$("$PYTHON_INTERPRETER" -c 'import site; print(site.USER_BASE + "/bin")' 2>/dev/null)
            if [ -n "$user_bin" ] && [ -x "$user_bin/uv" ]; then
                export PATH="$user_bin:$PATH"
                success "UV установлен через pip (--user)"
                return 0
            fi
        fi
    fi

    # Попытка 3: pipx (если доступен)
    if command_exists pipx; then
        info "Попытка установки через pipx"
        if pipx install --quiet uv >/dev/null 2>&1; then
            export PATH="$HOME/.local/bin:$PATH"
            success "UV установлен через pipx"
            return 0
        fi
    fi

    warn "UV не установлен. Используем встроенный venv."
    detail "Для ручной установки UV выполните: curl -LsSf https://astral.sh/uv/install.sh | sh"
}

# --- Создание виртуального окружения ---
create_venv() {
    banner "ЭТАП 5: СОЗДАНИЕ ВИРТУАЛЬНОГО ОКРУЖЕНИЯ"

    if [ -d "$VENV_FULL_PATH" ]; then
        info "Удаляем существующее окружение: $VENV_FULL_PATH"
        rm -rf "$VENV_FULL_PATH"
    fi

    # Выбираем инструмент для создания venv
    local venv_cmd
    if command_exists uv; then
        venv_cmd="uv venv --python '$PYTHON_INTERPRETER'"
        info "Создаем venv через UV: $venv_cmd"
    else
        venv_cmd="'$PYTHON_INTERPRETER' -m venv"
        warn "UV недоступен. Используем встроенный venv."
    fi

    if eval "$venv_cmd '$VENV_FULL_PATH'" 2>&1 | tee -a "$LOG_FILE"; then
        success "Виртуальное окружение создано"
    else
        error "Ошибка создания виртуального окружения"
        exit 1
    fi

    # Проверка окружения
    if [ -f "$ACTIVATE_SCRIPT" ]; then
        info "Проверка работоспособности окружения"
        if bash -c "source '$ACTIVATE_SCRIPT' && python -c 'import sys; print(f\"Python {sys.version}\")'" 2>&1 | tee -a "$LOG_FILE"; then
            success "Виртуальное окружение работает корректно"
        else
            error "Ошибка проверки виртуального окружения"
            exit 1
        fi
    else
        error "Activate script не найден: $ACTIVATE_SCRIPT"
        exit 1
    fi
}

# --- Очистка временных файлов ---
cleanup() {
    banner "ЭТАП ЗАВЕРШЕНИЯ: ОЧИСТКА"
    
    # Удаление временных файлов
    for tmp in "$TEMP_DIR"/*.log; do
        [ -f "$tmp" ] && rm -f "$tmp"
    done
    
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        info "Удаляем временную директорию: $TEMP_DIR"
        rm -rf "$TEMP_DIR" || warn "Не удалось удалить $TEMP_DIR"
    fi

    # Сохраняем архив для отладки
    if [[ -f "$PYTHON_TAR_FILE" ]]; then
        detail "Архив сохранен для отладки: $PYTHON_TAR_FILE"
    fi

    success "Очистка завершена"
}

# --- Главная функция ---
main() {
    banner "ULTIMATE AUTONOMOUS PYTHON + UV SETUP v4.0"
    log "Лог будет сохраняться в: $LOG_FILE"
    log "Рабочая директория: $WORK_DIR"
    log "Текущее время: $(date)"

    cd "$WORK_DIR"

    # Критические проверки
    if ! command_exists curl && ! command_exists wget; then
        error "Не установлены curl или wget. Установите вручную и повторите."
        exit 1
    fi

    check_system_deps
    get_latest_python
    download_python
    extract_and_compile_python
    install_uv
    create_venv
    cleanup

    banner "УСТАНОВКА ЗАВЕРШЕНА"
    echo -e "${GREEN}${BOLD}🎉 УСПЕХ! Python ${PYTHON_VERSION} и venv настроены.${NC}"
    echo "Интерпретатор: $PYTHON_INTERPRETER"
    echo "Venv: $VENV_FULL_PATH"

    cat <<EOF

Чтобы активировать окружение:
    source $ACTIVATE_SCRIPT

Для проверки:
    python --version
    pip list

Лог выполнения: $LOG_FILE
EOF
}

main "$@"

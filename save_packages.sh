#!/bin/bash

# Папка для хранения .deb файлов
BACKUP_DIR="./backup_packages_deb"

# Переходим в директорию скрипта
cd "$(dirname "$0")" || { echo "❌ Не удалось перейти в директорию скрипта"; exit 1; }
echo "📂 Текущая директория: $(pwd)"

# Создание папки для бэкапа
setup_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR" || { echo "❌ Не удалось создать папку $BACKUP_DIR"; exit 1; }
        chmod 755 "$BACKUP_DIR" || { echo "❌ Не удалось установить права"; exit 1; }
        echo "📁 Создана папка $BACKUP_DIR"
    else
        chmod 755 "$BACKUP_DIR"
        echo "📁 Папка $BACKUP_DIR уже существует"
    fi
}

# Проверка утилит
check_tools() {
    local tools=("dpkg" "apt-get" "xargs" "awk" "grep")
    local missing=()
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &>/dev/null; then
            missing+=("$tool")
        fi
    done
    if [ ${#missing[@]} -ne 0 ]; then
        echo "❌ Отсутствуют: ${missing[*]}"
        echo "💡 Установите: sudo apt-get install ${missing[*]}"
        exit 1
    fi
    echo "✅ Все необходимые утилиты найдены"
}

# Проверка apt-get download
check_apt_download() {
    if ! apt-get --help | grep -q "download"; then
        echo "❌ apt-get download недоступен"
        echo "💡 Обновите apt: sudo apt-get update && sudo apt-get upgrade"
        exit 1
    fi
    echo "✅ apt-get download доступен"
}

# Создание бэкапа
create_backup() {
    echo "🔄 Получаем список пакетов..."
    dpkg --get-selections | grep -v deinstall | awk '{print $1}' > "$BACKUP_DIR/packages.list" || {
        echo "❌ Ошибка при получении списка"
        exit 1
    }

    total=$(wc -l < "$BACKUP_DIR/packages.list")
    echo "📊 Пакетов для бэкапа: $total"
    echo "📥 Скачиваем .deb файлы..."

    local ok=0 fail=0 skip=0

    while IFS= read -r pkg; do
        if ls "$BACKUP_DIR"/${pkg}_*.deb 1>/dev/null 2>&1; then
            ((skip++))
            echo "⏭️ $pkg (уже есть)"
            continue
        fi

        if (cd "$BACKUP_DIR" && apt-get download "$pkg" &>/dev/null); then
            ((ok++))
            echo "✅ $pkg"
        else
            ((fail++))
            echo "❌ $pkg"
        fi
    done < "$BACKUP_DIR/packages.list"

    echo "✅ Бэкап завершён!"
    echo "📊 Итог:"
    echo "   Скачано: $ok"
    echo "   Ошибок: $fail"
    echo "   Пропущено: $skip"
    echo "📁 Файлы в: $BACKUP_DIR"
    echo "📄 Список: $BACKUP_DIR/packages.list"
}

# Восстановление
restore_backup() {
    echo "🔄 Восстановление из $BACKUP_DIR..."
    [ -d "$BACKUP_DIR" ] || { echo "❌ Нет папки $BACKUP_DIR"; exit 1; }
    [ -f "$BACKUP_DIR/packages.list" ] || { echo "❌ Нет файла packages.list"; exit 1; }

    echo "📦 Устанавливаем .deb..."
    sudo dpkg -i "$BACKUP_DIR"/*.deb

    echo "🔧 Исправляем зависимости..."
    sudo apt-get install -f -y

    echo "✅ Восстановление завершено!"
}

# Главное меню
main() {
    echo "🚀 Менеджер бэкапа пакетов"
    echo "1. Создать бэкап"
    echo "2. Восстановить из бэкапа"
    echo "3. Выход"
    read -p "👉 Выберите (1 или 2): " choice

    case $choice in
        1) setup_backup_dir; check_tools; check_apt_download; create_backup ;;
        2) restore_backup ;;
        3) exit 0 ;;
        *) echo "❌ Неверный выбор"; exit 1 ;;
    esac
}

main


#!/bin/bash
gnome-terminal -- bash -c '
ZAPRET_DIR="/opt/zapret"
SERVICE="zapret"
ARCHIVE_URL="https://github.com/ImMALWARE/zapret-linux-easy/archive/refs/heads/main.zip"
ARCHIVE_NAME="main.zip"
TMP_DIR="/tmp/zapret-install"

# Функция: скачать архив, если его нет
download_archive_if_needed() {
    local archive_path="$TMP_DIR/$ARCHIVE_NAME"
    if [ ! -f "$archive_path" ]; then
        echo "Скачиваю свежий архив $ARCHIVE_NAME..."
        mkdir -p "$TMP_DIR"
        if ! curl -L -o "$archive_path" "$ARCHIVE_URL"; then
            echo "Ошибка скачивания архива!"
            exit 1
        fi
    else
        echo "Архив уже существует, пропускаю скачивание."
    fi
}

# Функция установки/обновления
install_or_update_zapret() {
    echo -e "\033[1;32mУстановка/обновление zapret-linux-easy\033[0m"

    # Удаляем старую версию
    if [ -d "$ZAPRET_DIR" ]; then
        echo "Удаляю старую версию в $ZAPRET_DIR..."
        sudo systemctl stop "$SERVICE" 2>/dev/null || true
        sudo rm -rf "$ZAPRET_DIR"
    fi

    # Создаём временную папку
    TMP="$TMP_DIR-$(date +%s)"
    mkdir -p "$TMP"
    cd "$TMP" || { echo "Ошибка перехода в $TMP"; exit 1; }

    # Скачиваем и распаковываем
    download_archive_if_needed
    echo "Распаковываю архив..."
    if ! unzip -q "$TMP_DIR/$ARCHIVE_NAME" -d "$TMP"; then
        echo "Ошибка распаковки архива!"
        exit 1
    fi
    cd "$TMP/zapret-linux-easy-main" || { echo "Ошибка перехода в папку с исходниками"; exit 1; }

    # Устанавливаем
    echo "Запускаю установку с автоматическим выбором iptables и всех интерфейсов..."
    if ! printf "1\n\n\n" | ./install.sh; then
        echo "Ошибка установки!"
        exit 1
    fi

    # Проверяем результат
    if [ -d "$ZAPRET_DIR" ]; then
        echo -e "\033[1;32mУстановка завершена. Папка $ZAPRET_DIR создана.\033[0m"
        sudo systemctl daemon-reload
        echo -e "\033[1;32mСервис $SERVICE готов к запуску.\033[0m"
    else
        echo -e "\033[1;31mОшибка: папка $ZAPRET_DIR не создана.\033[0m"
        exit 1
    fi
}

# Проверка статуса сервиса
get_status() {
    if sudo systemctl cat "$SERVICE" &>/dev/null; then
        STATUS=$(sudo systemctl is-active "$SERVICE" 2>/dev/null || echo "inactive")
        echo "Статус: \033[1;33m$STATUS\033[0m"
    else
        echo "Сервис $SERVICE \033[1;31mне установлен\033[0m"
    fi
}

# Меню
show_menu() {
    clear
    echo -e "\033[1;34m=== Управление zapret ===\033[0m"
    echo "Папка: $ZAPRET_DIR"
    get_status
    echo ""
    echo "1) Включить (start)"
    echo "2) Выключить (stop)"
    echo "3) Перезапустить"
    echo "4) Установить / обновить до последней версии"
    echo "5) Запустить проверку (check.sh)"
    echo "0) Выход"
    echo ""
    read -p "Выберите (0-5): " choice
}

# Первый запуск — если не установлен, ставим
if [ ! -d "$ZAPRET_DIR" ] || ! sudo systemctl cat "$SERVICE" &>/dev/null; then
    echo -e "\033[1;33mZapret не найден — ставлю последнюю версию...\033[0m"
    install_or_update_zapret
fi
sudo systemctl start "$SERVICE"; 
while true; do
    show_menu

    case "$choice" in
        1)
            sudo systemctl start "$SERVICE" && echo -e "\033[1;32mЗапущен\033[0m" || echo -e "\033[1;31mОшибка запуска\033[0m"
            ;;
        2)
            sudo systemctl stop "$SERVICE" && echo -e "\033[1;32mОстановлен\033[0m" || echo -e "\033[1;31mОшибка\033[0m"
            ;;
        3)
            sudo systemctl restart "$SERVICE" && echo -e "\033[1;32mПерезапущен\033[0m" || echo -e "\033[1;31mОшибка\033[0m"
            ;;
        4)
            install_or_update_zapret
            ;;
        5)
            if [ -f "$ZAPRET_DIR/check.sh" ]; then
                echo -e "\033[1;32mЗапускаю check.sh...\033[0m"
                "$ZAPRET_DIR/check.sh"
            else
                echo -e "\033[1;31mcheck.sh не найден\033[0m"
            fi
            ;;
        0)
            echo -e "\033[1;34mВыход\033[0m"
            exit 0
            ;;
        *)
            echo "\033[1;31mНеверный выбор\033[0m"
            ;;
    esac

    echo ""
    read -p "Нажми Enter для продолжения..."
done

exec bash'


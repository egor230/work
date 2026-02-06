#!/bin/bash
# Автоматическая установка и управление zapret-linux-easy (ImMALWARE)
# ВСЕ ДЕЛАЕТСЯ АВТОМАТИЧЕСКИ БЕЗ ВОПРОСОВ!

# Автоматическое получение прав суперпользователя
if [ "$EUID" -ne 0 ]; then
  echo "Запрашиваю права суперпользователя..."
  exec sudo "$0" "$@"
fi

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== УПРАВЛЕНИЕ ZAPRET (linux-easy) ===${NC}"
ZAPRET_DIR="/opt/zapret"
SERVICE="zapret"
ARCHIVE_URL="https://github.com/ImMALWARE/zapret-linux-easy/archive/refs/heads/main.zip"
ARCHIVE_NAME="main.zip"
TMP_DIR="/tmp/zapret-install"

# Функция: скачать архив, если его нет или он устарел
download_archive_if_needed() {
    local archive_path="$TMP_DIR/$ARCHIVE_NAME"
    if [ ! -f "$archive_path" ]; then
        echo "Скачиваю свежий архив main..."
        mkdir -p "$TMP_DIR"
        curl -L -o "$archive_path" "$ARCHIVE_URL"
    else
        echo "Архив уже существует, пропускаю скачивание."
    fi
}

# Функция полной (пере)установки — всегда свежая версия
install_or_update_zapret() {
    echo -e "${YELLOW}Установка/обновление zapret-linux-easy${NC}"

    # Удаляем старую версию, если она есть
    if [ -d "$ZAPRET_DIR" ]; then
        echo "Удаляю старую версию в $ZAPRET_DIR ..."
        sudo systemctl stop "$SERVICE" 2>/dev/null || true
        sudo systemctl disable "$SERVICE" 2>/dev/null || true
        sudo rm -rf "$ZAPRET_DIR"
    fi

    # Создаём временную папку
    TMP="$TMP_DIR-$(date +%s)"
    mkdir -p "$TMP"
    cd "$TMP"

    # Скачиваем архив, если нужно
    download_archive_if_needed

    # Распаковываем архив
    echo "Распаковываю..."
    unzip -q "$TMP_DIR/$ARCHIVE_NAME" -d "$TMP"
    cd "$TMP/zapret-linux-easy-main"

    # Запускаем установку с автоматическим выбором iptables и всех интерфейсов
    echo "Запускаю установку с автоматическим выбором iptables и всех интерфейсов..."
    printf "1\n\n\n" | ./install.sh

    # Проверяем, что папка /opt/zapret и сервис созданы
    if [ -d "$ZAPRET_DIR" ]; then
        echo -e "${GREEN}Установка завершена. Папка $ZAPRET_DIR создана.${NC}"
        # Перезагружаем systemd, чтобы подхватить новый сервис
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE"
        echo -e "${GREEN}Сервис $SERVICE включён и готов к запуску.${NC}"
    else
        echo -e "${RED}Ошибка: папка $ZAPRET_DIR не создана.${NC}"
        exit 1
    fi
}


# Проверка статуса
get_status() {
    if sudo systemctl cat "$SERVICE" &>/dev/null; then
        STATUS=$(sudo systemctl is-active "$SERVICE" 2>/dev/null || echo "inactive")
        ENABLED=$(sudo systemctl is-enabled "$SERVICE" 2>/dev/null || echo "disabled")
        echo "Статус: $STATUS | Автозапуск: $ENABLED"
    else
        echo "Сервис $SERVICE не установлен"
    fi
}

# Меню
show_menu() {
    clear
    echo -e "${GREEN}=== Управление zapret ===${NC}"
    echo "Папка: $ZAPRET_DIR"
    get_status
    echo ""
    echo "1) Включить (start)"
    echo "2) Выключить (stop)"
    echo "3) Включить автозапуск (enable)"
    echo "4) Отключить автозапуск (disable)"
    echo "5) Перезапустить"
    echo "6) Установить / обновить до последней версии"
    echo "7) Запустить проверку (check.sh)"
    echo "0) Выход"
    echo ""
    read -p "Выберите (0-7): " choice
}

# Первый запуск — если не стоит, сразу ставим
if [ ! -d "$ZAPRET_DIR" ] || ! sudo systemctl cat "$SERVICE" &>/dev/null; then
    echo -e "${YELLOW}Zapret не найден — ставлю последнюю версию...${NC}"
    install_or_update_zapret
fi

while true; do
    show_menu

    case "$choice" in
        1)
            sudo systemctl start "$SERVICE" && echo -e "${GREEN}Запущен${NC}" || echo -e "${RED}Ошибка запуска${NC}"
            ;;
        2)
            sudo systemctl stop "$SERVICE" && echo -e "${GREEN}Остановлен${NC}" || echo -e "${RED}Ошибка${NC}"
            ;;
        3)
            sudo systemctl enable "$SERVICE" && echo -e "${GREEN}Автозапуск включён${NC}" || echo -e "${RED}Ошибка${NC}"
            ;;
        4)
            sudo systemctl disable "$SERVICE" && echo -e "${GREEN}Автозапуск отключён${NC}" || echo -e "${RED}Ошибка${NC}"
            ;;
        5)
            sudo systemctl restart "$SERVICE" && echo -e "${GREEN}Перезапущен${NC}" || echo -e "${RED}Ошибка${NC}"
            ;;
        6)
            install_or_update_zapret
            ;;
        7)
            if [ -f "$ZAPRET_DIR/check.sh" ]; then
                echo -e "${YELLOW}Запускаю check.sh...${NC}"
                "$ZAPRET_DIR/check.sh"
            else
                echo -e "${RED}check.sh не найден${NC}"
            fi
            ;;
        0)
            echo -e "${GREEN}Выход${NC}"
            exit 0
            ;;
        *)
            echo "Неверный выбор"
            ;;
    esac

    echo ""
    read -p "Нажми Enter для продолжения..."
done


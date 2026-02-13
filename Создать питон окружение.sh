#!/bin/sh
gnome-terminal -- bash -c ' 
# Переходим в текущую папку откуда запускается скрипт
SCRIPT_DIR="$(dirname "$0")"

# --- КОНФИГУРАЦИЯ ---
# Важно: кавычки обязательны из-за пробелов в пути
VENV_PATH="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv"
PACKAGES_DIR="./myvenv_packages_backup"
REQ_FILE="./requirements_backup.txt"

# Проверка наличия python3.12
if ! command -v python3.12 &> /dev/null; then
    echo "Ошибка: python3.12 не найден в системе."
    echo "Установите его командой: sudo apt install python3.12"
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

# Установка модуля venv, если отсутствует (требует sudo)
if ! python3.12 -m venv -h &> /dev/null; then
    echo "Модуль venv не найден. Пробую установить python3.12-venv..."
    sudo apt install python3.12-venv -y
fi

# --- МЕНЮ ---
echo "============================================"
echo " Менеджер резервного копирования VENV"
echo "============================================"
echo "1) Сделать бэкап (сохранить пакеты в файлы)"
echo "2) Восстановить (создать venv из файлов)"
read -p "Выберите действие [1/2]: " choice

if [ "$choice" == "1" ]; then
    # --- РЕЖИМ БЭКАПА ---
    if [ -d "$VENV_PATH" ]; then
        echo "Активация окружения..."
        source "$VENV_PATH/bin/activate"
        
        echo "Сохранение списка зависимостей в $REQ_FILE..."
        pip freeze > "$REQ_FILE"
        
        mkdir -p "$PACKAGES_DIR"
        
        echo "Скачивание пакетов в $PACKAGES_DIR..."
        # --exists-action i: игнорировать, если пакет уже скачан
        pip download -r "$REQ_FILE" -d "$PACKAGES_DIR" --exists-action i
        
        echo "✅ Бэкап успешно завершен."
    else
        echo "❌ Ошибка: Виртуальное окружение не найдено по пути:"
        echo "$VENV_PATH"
    fi

elif [ "$choice" == "2" ]; then
    # --- РЕЖИМ ВОССТАНОВЛЕНИЯ ---
    if [ -f "$REQ_FILE" ] && [ -d "$PACKAGES_DIR" ]; then
        # Если папка venv уже есть, спрашиваем подтверждение
        if [ -d "$VENV_PATH" ]; then
            read -p "Окружение уже существует. Удалить и пересоздать? [y/N]: " confirm
            if [ "$confirm" == "y" ] || [ "$confirm" == "Y" ]; then
                echo "Удаление старого окружения..."
                rm -rf "$VENV_PATH"
            else
                echo "Отмена операции."
                exec bash
                exit 0
            fi
        fi

        echo "Создание нового виртуального окружения (python3.12)..."
        python3.12 -m venv "$VENV_PATH"
        
        echo "Активация и установка пакетов..."
        source "$VENV_PATH/bin/activate"
        
        # Установка только из локальной папки (без интернета)
        pip install --no-index --find-links="$PACKAGES_DIR" -r "$REQ_FILE"
        
        echo "✅ Восстановление завершено."
    else
        echo "❌ Ошибка: Файлы бэкапа не найдены ($REQ_FILE или папка $PACKAGES_DIR)."
        echo "Сначала выполните пункт 1."
    fi
else
    echo "Неверный выбор."
fi

# Держим терминал открытым
exec bash'
# Создаём виртуальное окружение с доступом к системным пакетам
#python -m venv myvenv --system-site-packages
# Активируем виртуальное окружение
#myvenv/bin/activate # Обновляем pip
#pip install --upgrade pip
#pip install -r "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/requirements.txt"
bash'






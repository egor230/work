#!/bin/sh
gnome-terminal -- bash -c ' 

# Переходим в текущую папку откуда запускается скрипт
cd "$(dirname "$0")" || exit 1

alias python="python3.12"
# Пути
VENV_PATH="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv"
PACKAGES_DIR="./myvenv_packages_backup"
REQ_FILE="./requirements_backup.txt"

echo "Выберите действие:"
echo "1) Сделать бэкап"
echo "2) Восстановить"
read -p "Введите номер (1 или 2): " choice

if [ "$choice" == "1" ]; then
  if [ -d "$VENV_PATH" ]; then
    echo "Обновляю бэкап из $VENV_PATH..."
    source "$VENV_PATH/bin/activate"
    
    # Создаем папку если нет
    mkdir -p "$PACKAGES_DIR"
    
    # Обновляем список зависимостей
    pip freeze > "$REQ_FILE"
    
    # Скачиваем только недостающее
    # Флаг --exists-action w заставляет pip перезаписывать или игнорировать существующие
    pip download --dest "$PACKAGES_DIR" -r "$REQ_FILE"
    
    echo "Бэкап актуализирован в $PACKAGES_DIR"
  else
    echo "Ошибка: Директория $VENV_PATH не обнаружена."
  fi
elif [ "$choice" == "2" ]; then
  echo "Восстановление..."
  python3 -m venv "$VENV_PATH"
  if [ -f "$REQ_FILE" ] && [ -d "$PACKAGES_DIR" ]; then
    source "$VENV_PATH/bin/activate"
    pip install --no-index --find-links="$PACKAGES_DIR" -r "$REQ_FILE"
    echo "Успешно восстановлено."
  else
    echo "Файлы бэкапа отсутствуют."
  fi
fi
# Создаём виртуальное окружение с доступом к системным пакетам
#python -m venv myvenv --system-site-packages
# Активируем виртуальное окружение
#myvenv/bin/activate # Обновляем pip
#pip install --upgrade pip
#pip install -r "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/requirements.txt"
bash'






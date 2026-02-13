#!/bin/bash
gnome-terminal -- bash -c '
USER_NAME=$(whoami)
sudo su
SOURCE_DIR="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux_must_have/python_linux/work/scripts"
TARGET_DIR="/home/egor/.local/share/nemo/scripts"
# Проверяем существование исходной директории
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Ошибка: Исходная директория не существует: $SOURCE_DIR"
    exit 1
fi

# Создаем целевую директорию, если её нет
mkdir -p "$TARGET_DIR"

# Перемещаем файлы
sudo cp -r "$SOURCE_DIR"/. "$TARGET_DIR"/

exit
exec bash'
 

#!/bin/bash
gnome-terminal -- bash -c '
USER_NAME=$(whoami)
sudo su
# Определяем путь к новому файлу настроек
SUDOERS_FILE="/etc/sudoers.d/nopasswd_$USER_NAME"

echo "Настройка беспарольного доступа для пользователя: $USER_NAME"

# Создаем временный файл для проверки синтаксиса
echo "$USER_NAME ALL=(ALL) NOPASSWD: ALL" > /tmp/sudoer_temp

# Проверяем синтаксис перед применением
visudo -cf /tmp/sudoer_temp

if [ $? -eq 0 ]; then
  # Если синтаксис верный, переносим файл в системную директорию
  sudo cp /tmp/sudoer_temp $SUDOERS_FILE
  # Устанавливаем правильные права доступа (обязательно 0440)
  sudo chmod 0440 $SUDOERS_FILE
  echo "Готово! Теперь вы можете использовать sudo без пароля."
else
  echo "Ошибка в синтаксисе. Изменения не применены."
fi

# Удаляем временный файл
rm /tmp/sudoer_temp
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
sudo mv "$SOURCE_DIR"/* "$TARGET_DIR"/
exit
exec bash'
 

#!/bin/bash

gnome-terminal -- bash -c '
# Автоматическое получение прав суперпользователя

echo "Запрашиваю права суперпользователя..."
#exec sudo "$0" "$@"

echo "Выберите действие:"
echo "1) Создать бэкап настроек"
echo "2) Восстановить настройки"
read -p "Введите номер: " choice

# Переход в директорию скрипта
cd "$(dirname "$0")" || exit 1
mkdir -p "reze"

# Пути
dest_path="./reze"
source_path="$HOME"
backup_dir="/mnt/807EB5FA7EB5E954/python_linux/User data backup"

if [ "$choice" == "1" ]; then
  echo "Запуск резервного копирования настроек из $source_path..."
  # Используем exclude, чтобы не копировать лишнее и mnt
  sudo rsync -avh --progress --update \
    --exclude=".cache" \
    --exclude="Downloads" \
    --exclude="Videos" \
    --exclude="/mnt" \
    "$source_path/" "$dest_path"

  echo "Сохранение копии скрипта и данных в архив..."
  mkdir -p "$backup_dir"
  cp "$0" "$backup_dir/backup_script_copy.sh"
  sudo rsync -avh "$dest_path/" "$backup_dir/reze_folder/"
  echo "Готово. Данные синхронизированы с $backup_dir"

elif [ "$choice" == "2" ]; then
  echo "Запуск восстановления данных в $source_path..."
  sudo rsync -avh --progress --update "$dest_path/" "$source_path"
  echo "Восстановление завершено."

else
  echo "Неверный выбор. Завершение работы."
fi

echo "Нажмите любую клавишу для выхода"
read -n 1
exec bash'

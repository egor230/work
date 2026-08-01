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

if [ "$choice" == "1" ]; then
  echo "Запуск резервного копирования настроек из $source_path..."
  # Используем exclude, чтобы не копировать лишнее и mnt
  sudo rsync -ai --progress --update --modify-window=1 \
    --exclude=".cache" \
    --exclude="Downloads" \
    --exclude="Videos" \
    --exclude="/mnt" \
    "$source_path/" "$dest_path"

  echo "Готово. Бэкап сохранен в $dest_path"

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

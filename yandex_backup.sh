#!/bin/bash
sleep 1;
# Переходим в директорию запуска
cd "$(dirname "$0")" || exit 1

# Проверка и установка необходимых утилит
for pkg in rsync pv; do
  if ! command -v $pkg &> /dev/null; then
    echo "Пакет $pkg не найден. Устанавливаю..."
    sudo apt update && sudo apt install -y $pkg
  fi
done

# Переменные
current_user=$(whoami)
current_directory="$(pwd)/yandex-browser"
source_directory="/home/$current_user/.config/yandex-browser"

# Создаем папку бэкапа если её нет
if [ ! -d "$current_directory" ]; then
  mkdir -p "$current_directory"
fi

echo "Выберите действие:"
echo "1) Создать бэкап"
echo "2) Восстановить"
read -p "Введите номер: " choice

sleep 1

if [ "$choice" == "1" ]; then
  echo "Копирую данные в $current_directory"
  # Расчет размера для pv и запуск rsync
  size=$(sudo du -sb "$source_directory" | awk '{print $1}')
  sudo rsync -a --info=progress2 --update "$source_directory/" "$current_directory/" | pv -lep -s "$size" > /dev/null
  echo "Готово."

elif [ "$choice" == "2" ]; then
  echo "Восстанавливаю данные в $source_directory"
  size=$(sudo du -sb "$current_directory" | awk '{print $1}')
  sudo rsync -a --info=progress2 --update "$current_directory/" "$source_directory/" | pv -lep -s "$size" > /dev/null
  # Исправляем права владельца после sudo rsync
  sudo chown -R "$current_user:$current_user" "$source_directory"
  echo "Восстановление завершено."
fi

exit 0

#xdotool key F3;cd /home/$current_user/.config;# Переходим в директорию /home/имя_пользователя
#chown -R $USER;

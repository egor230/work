#!/bin/bash

sleep 1
cd "$(dirname "$0")" || exit 1

for pkg in rsync pv dconf-cli; do
  if ! command -v $pkg &> /dev/null; then
    echo "Пакет $pkg не найден. Устанавливаю..."
    sudo apt update && sudo apt install -y $pkg
  fi
done
#!/bin/bash

sleep 1
cd "$(dirname "$0")" || exit 1

for pkg in rsync pv dconf-cli; do
  if ! command -v $pkg > /dev/null; then
    echo "Пакет $pkg не найден. Устанавливаю..."
    sudo apt update && sudo apt install -y $pkg
  fi
done

current_user=$(whoami)
current_directory="$(pwd)/mint_full_backup"
browser_backup="$current_directory/yandex-browser"
settings_backup="$current_directory/system_settings"

source_browser="/home/$current_user/.config/yandex-browser"
source_menus="/home/$current_user/.config/menus"
source_apps="/home/$current_user/.local/share/applications"
source_themes="/home/$current_user/.themes"

mkdir -p "$browser_backup"
mkdir -p "$settings_backup/menus"
mkdir -p "$settings_backup/apps"
mkdir -p "$settings_backup/themes"

echo "Меню бэкапа (Linux Mint Cinnamon):"
echo "1) Создать полный бэкап (Браузер + Панели + Меню + Темы)"
echo "2) Восстановить всё"
read -p "Выберите действие: " choice

sleep 1

if [ "$choice" == "1" ]; then
  echo "Внимание: Закройте браузер перед началом для точности данных."
  
  echo "Шаг 1: Сохраняю настройки Cinnamon и панели..."
  dconf dump /org/cinnamon/ > "$settings_backup/cinnamon.dconf"
  
  echo "Шаг 2: Сохраняю структуру меню и ярлыки..."
  [ -d "$source_menus" ] && rsync -a "$source_menus/" "$settings_backup/menus/"
  [ -d "$source_apps" ] && rsync -a "$source_apps/" "$settings_backup/apps/"

  echo "Шаг 3: Копирую темы..."
  [ -d "$source_themes" ] && rsync -a "$source_themes/" "$settings_backup/themes/"

  echo "Шаг 4: Копирую Яндекс Браузер..."
  if [ -d "$source_browser" ]; then
    size=$(du -sb "$source_browser" | awk '{print $1}')
    rsync -av --delete "$source_browser/" "$browser_backup/" | pv -lep -s "$size" > /dev/null
  fi
  echo "Все данные сохранены в $current_directory"

elif [ "$choice" == "2" ]; then
  echo "Шаг 1: Восстановление настроек панелей..."
  if [ -f "$settings_backup/cinnamon.dconf" ]; then
    dconf load /org/cinnamon/ < "$settings_backup/cinnamon.dconf"
  fi

  echo "Шаг 2: Восстановление структуры меню..."
  mkdir -p "$source_menus" "$source_apps"
  [ -d "$settings_backup/menus" ] && rsync -a "$settings_backup/menus/" "$source_menus/"
  [ -d "$settings_backup/apps" ] && rsync -a "$settings_backup/apps/" "$source_apps/"

  echo "Шаг 3: Восстановление тем..."
  mkdir -p "$source_themes"
  [ -d "$settings_backup/themes" ] && rsync -a "$settings_backup/themes/" "$source_themes/"

  echo "Шаг 4: Восстановление Яндекс Браузера..."
  if [ -d "$browser_backup" ]; then
    [ -d "$source_browser" ] && rm -rf "$source_browser"
    mkdir -p "$source_browser"
    size=$(du -sb "$browser_backup" | awk '{print $1}')
    rsync -av "$browser_backup/" "$source_browser/" | pv -lep -s "$size" > /dev/null
  fi
  
  sudo chown -R "$current_user:$current_user" "$source_browser"
  sudo chown -R "$current_user:$current_user" "$source_menus"
  sudo chown -R "$current_user:$current_user" "$source_apps"
  sudo chown -R "$current_user:$current_user" "$source_themes"
  
  echo "Восстановление завершено. Перезагрузите Cinnamon (Alt+F2, r, Enter)."
fi

exit 0

#xdotool key F3;cd /home/$current_user/.config;# Переходим в директорию /home/имя_пользователя
#chown -R $USER;

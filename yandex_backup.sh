#!/bin/bash
cd "$(dirname "$0")" || exit 1

# Определение пользователя и домашней директории
current_user=$(whoami)
home_dir="$HOME"
backup_base_dir="$(pwd)/mint_full_backup"
browser_backup="$backup_base_dir/yandex-browser"
settings_backup="$backup_base_dir/system_settings"
config_backup="$settings_backup/config"  # для .config

# Исходные пути
source_browser="$home_dir/.config/yandex-browser"
source_menus="$home_dir/.config/menus"
source_apps="$home_dir/.local/share/applications"
source_themes="$home_dir/.themes"
source_nemo_config="$home_dir/.config/nemo"
source_nemo_bookmarks="$home_dir/.config/gtk-3.0/bookmarks"
source_config="$home_dir/.config"  # общий .config

# Создание директорий для бэкапа
mkdir -p "$browser_backup"
mkdir -p "$settings_backup/menus"
mkdir -p "$settings_backup/apps"
mkdir -p "$settings_backup/themes"
mkdir -p "$settings_backup/nemo/config"
mkdir -p "$config_backup"

echo "Меню бэкапа (Linux Mint Cinnamon):"
echo "1) Создать полный бэкап (Браузер + Панели + Меню + Темы + Nemo + .config)"
echo "2) Восстановить всё"
read -p "Выберите действие: " choice

sleep 1

backup() {
  echo "Внимание: Закройте браузер перед началом для точности данных."

  echo "Шаг 1: Сохраняю настройки Cinnamon и панели..."
  dconf dump /org/cinnamon/ > "$settings_backup/cinnamon.dconf"

  echo "Шаг 2: Сохраняю структуру меню и ярлыки..."
  [ -d "$source_menus" ] && rsync -a "$source_menus/" "$settings_backup/menus/"
  [ -d "$source_apps" ] && rsync -a "$source_apps/" "$settings_backup/apps/"

  echo "Шаг 3: Копирую темы..."
  [ -d "$source_themes" ] && rsync -a "$source_themes/" "$settings_backup/themes/"

  echo "Шаг 4: Сохраняю настройки Nemo (закладки и конфигурацию)..."
  [ -d "$source_nemo_config" ] && rsync -a "$source_nemo_config/" "$settings_backup/nemo/config/"
  [ -f "$source_nemo_bookmarks" ] && cp "$source_nemo_bookmarks" "$settings_backup/nemo/bookmarks"

  echo "Шаг 5: Копирую Яндекс Браузер (профиль и куки)..."
  if [ -d "$source_browser" ]; then
    size=$(du -sb "$source_browser" | awk '{print $1}')
    rsync -avH --delete "$source_browser/" "$browser_backup/" | pv -lep -s "$size" > /dev/null
  fi

  echo "Шаг 6: Копирую общие настройки .config (исключая уже сохранённые папки)..."
  if [ -d "$source_config" ]; then
    # Исключаем папки/файлы, которые уже сохранили отдельно, чтобы избежать дублирования
    exclude_opts=(
      --exclude="yandex-browser"
      --exclude="menus"
      --exclude="nemo"
      --exclude="gtk-3.0/bookmarks"
    )
    size=$(du -sb "$source_config" | awk '{print $1}')
    rsync -avH "${exclude_opts[@]}" "$source_config/" "$config_backup/" | pv -lep -s "$size" > /dev/null
  fi

  echo "Все данные сохранены в $backup_base_dir"
}

restore() {
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

  echo "Шаг 4: Восстановление настроек Nemo..."
  if [ -d "$settings_backup/nemo/config" ]; then
    mkdir -p "$source_nemo_config"
    rsync -a "$settings_backup/nemo/config/" "$source_nemo_config/"
  fi
  if [ -f "$settings_backup/nemo/bookmarks" ]; then
    mkdir -p "$(dirname "$source_nemo_bookmarks")"
    cp "$settings_backup/nemo/bookmarks" "$source_nemo_bookmarks"
  fi

  echo "Шаг 5: Восстановление Яндекс Браузера..."
  if [ -d "$browser_backup" ]; then
    # Удаляем существующую папку браузера, чтобы избежать конфликтов старых файлов
    [ -d "$source_browser" ] && rm -rf "$source_browser"
    mkdir -p "$source_browser"
    size=$(du -sb "$browser_backup" | awk '{print $1}')
    rsync -avH "$browser_backup/" "$source_browser/" | pv -lep -s "$size" > /dev/null
  fi

  echo "Шаг 6: Восстановление общих настроек .config (без замены уже восстановленных папок)..."
  if [ -d "$config_backup" ]; then
    # Те же исключения, но для восстановления используем --ignore-existing, чтобы не затирать
    # папки, восстановленные ранее (меню, nemo, браузер)
    exclude_opts=(
      --exclude="yandex-browser"
      --exclude="menus"
      --exclude="nemo"
      --exclude="gtk-3.0/bookmarks"
    )
    mkdir -p "$source_config"
    rsync -avH --ignore-existing "${exclude_opts[@]}" "$config_backup/" "$source_config/"
  fi

  echo "Шаг 7: Корректировка владельца файлов..."
  sudo chown -R "$current_user:$current_user" "$source_browser" 2>/dev/null || true
  sudo chown -R "$current_user:$current_user" "$source_menus" 2>/dev/null || true
  sudo chown -R "$current_user:$current_user" "$source_apps" 2>/dev/null || true
  sudo chown -R "$current_user:$current_user" "$source_themes" 2>/dev/null || true
  sudo chown -R "$current_user:$current_user" "$source_nemo_config" 2>/dev/null || true
  sudo chown "$current_user:$current_user" "$source_nemo_bookmarks" 2>/dev/null || true

  echo "Восстановление завершено. Перезагрузите Cinnamon (Alt+F2, r, Enter)."
}

case "$choice" in
  1) backup ;;
  2) restore ;;
  *) echo "Неверный выбор." ; exit 1 ;;
esac

exit 0

#xdotool key F3;cd /home/$current_user/.config;# Переходим в директорию /home/имя_пользователя
#chown -R $USER;

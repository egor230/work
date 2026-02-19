#!/usr/bin/env bash
#
# Скрипт делает твою сборку Wine → системной (заменяет всё)
# Полная чистка старого Wine + префикса
# Один общий префикс ~/.wine (32-битный)
# Только необходимые компоненты для Office 2003
# Без алиасов, без отдельных папок — просто wine = твой Word 2003
#

set -euo pipefail

# Путь к твоей кастомной сборке (не меняй, если путь правильный)
WINE_BUILD="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/PROTON-SAREK10-29-ASYNC"
INSTALL_DIR="/opt/wine"           # куда поставим твою сборку как основную
LOG="$HOME/wine.log"

echo "Начало полной замены Wine на кастомную сборку" | tee -a "$LOG"
echo "Дата: $(date)" | tee -a "$LOG"

# 1. Полная чистка ВСЕГО старого Wine (системного + пользовательского)
echo "Полная очистка старого Wine..." | tee -a "$LOG"

sudo apt remove --purge -y \
    wine wine32 wine64 wine-stable wine-devel wine-staging \
    winehq-stable winehq-devel winehq-staging \
    playonlinux lutris bottles \
    winetricks 2>/dev/null || true

sudo apt autoremove --purge -y
sudo apt autoclean

# Удаляем все возможные репозитории WineHQ
sudo rm -f /etc/apt/sources.list.d/*wine*.list
sudo rm -f /usr/share/keyrings/winehq* /etc/apt/keyrings/winehq*

# Удаляем ВСЕ префиксы (самое важное для чистоты)
rm -rf "$HOME/.wine" "$HOME/.local/share/wineprefixes" "$HOME/.cache/wine" "$HOME/.cache/winetricks" 2>/dev/null || true
rm -rf "$HOME/.local/share/applications/wine*" "$HOME/.local/share/desktop-directories/wine*" 2>/dev/null || true

# 2. Установка минимально нужных пакетов (без лишнего)
echo "Установка зависимостей..." | tee -a "$LOG"
sudo dpkg --add-architecture i386 2>/dev/null || true
sudo apt update -qq

sudo apt install -y --no-install-recommends \
    cabextract \
    winetricks \
    libgl1:i386 libc6:i386 libpulse0:i386 libasound2-plugins:i386

# 3. Установка твоей сборки как системной
echo "Установка кастомной сборки в $INSTALL_DIR ..." | tee -a "$LOG"
sudo rm -rf "$INSTALL_DIR" 2>/dev/null || true
sudo mkdir -p "$INSTALL_DIR"
sudo cp -a "$WINE_BUILD/." "$INSTALL_DIR/"
sudo chmod -R 755 "$INSTALL_DIR"

# 4. Симлинки — перехватываем ВСЕ команды wine*
echo "Перехватываем команды wine в /usr/local/bin ..." | tee -a "$LOG"
for bin in wine wine64 wineserver wineboot winecfg wineserver-preloader; do
    sudo ln -sf "$INSTALL_DIR/bin/$bin" "/usr/local/bin/$bin" 2>/dev/null || true
done

# 5. Профиль окружения (чтобы PATH всегда видел твою сборку первым)
echo "Создаём /etc/profile.d/wine-custom.sh ..." | tee -a "$LOG"
sudo bash -c "cat > /etc/profile.d/wine-custom.sh" << 'EOF'
# Кастомный Wine (Office 2003) — системный
export PATH="/opt/wine/bin:$PATH"
export WINEDLLPATH="/opt/wine/lib:/opt/wine/lib64"
export WINEARCH=win32
export WINEDEBUG=-all
EOF
sudo chmod +x /etc/profile.d/wine.sh

# Применяем сразу
export PATH="/opt/wine/bin:$PATH"
export WINEARCH=win32
export WINEDEBUG=-all

# 6. Создаём чистый 32-битный префикс ~/.wine
echo "Создаём чистый префикс ~/.wine ..." | tee -a "$LOG"
rm -rf "$HOME/.wine" 2>/dev/null || true
wineboot --init >/dev/null 2>&1
sleep 5

# 7. Самый стабильный набор для Office 2003
echo "Установка компонентов winetricks (Office 2003)..." | tee -a "$LOG"
winetricks -q  corefonts tahoma fontfix \
    riched20 riched30 msxml3 gdiplus mfc42 \
    fontsmooth=rgb \
    2>&1 | tee -a "$LOG"

echo "Готово! Wine настроен для работы с Word 2003."


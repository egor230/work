#!/bin/bash
set -e  # останов при любой ошибке
set -x  # подробный вывод (можно убрать позже)
# 1. Убиваем все процессы wine, включая фоновые и системные

# 2. Удаляем все бинарники wine из стандартных и нестандартных мест
#sudo find /usr/local/bin /usr/bin /bin /opt ~/.local/bin ~/bin -type f -name "*wine*" -exec rm -f {} \; 2>/dev/null || true
#sudo find /usr/local/bin /usr/bin /bin /opt ~/.local/bin ~/bin -type f -name "*wineserver*" -exec rm -f {} \; 2>/dev/null || true
#sudo find /usr/local/sbin /usr/sbin /sbin -type f -name "*wine*" -exec rm -f {} \; 2>/dev/null || true
# -------------------------------
# Функция для проверки наличия команды
# -------------------------------
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ Команда $1 не найдена. Установите её."
        exit 1
    fi
}

# -------------------------------
# 1. Полная зачистка процессов
# 2. Удаление всех бинарников Wine из системы
# -------------------------------
echo ">>> 2. Поиск и удаление всех бинарников Wine"
sudo find /usr/local/bin /usr/bin /bin /opt ~/.local/bin ~/bin -type f -name "*wine*" -exec rm -f {} \; 2>/dev/null || true
sudo find /usr/local/bin /usr/bin /bin /opt ~/.local/bin ~/bin -type f -name "*wineserver*" -exec rm -f {} \; 2>/dev/null || true
sudo find /usr/lib /usr/lib32 /usr/lib64 -name "*wine*" -type f -exec rm -f {} \; 2>/dev/null || true
sudo rm -rf /opt/wine* /opt/winehq* ~/wine* ~/Wine*

# -------------------------------
# 3. Удаление всех пакетов Wine и winetricks
# -------------------------------
#echo ">>> 3. Удаление пакетов"
sudo apt remove --purge -y wine* winehq* winetricks 2>/dev/null || true
sudo apt autoremove -y
sudo apt autoclean

# -------------------------------
# 4. Удаление репозиториев и ключей
# -------------------------------
echo ">>> 4. Удаление репозиториев Wine"
sudo rm -f /etc/apt/sources.list.d/winehq*
sudo rm -f /etc/apt/keyrings/winehq*
sudo rm -f /etc/apt/trusted.gpg.d/winehq.gpg
sudo rm -f /etc/apt/trusted.gpg.d/winehq.asc

# -------------------------------
# 5. Удаление пользовательских конфигов
# -------------------------------
#echo ">>> 5. Удаление конфигов и кэша"
rm -rf "$HOME/.wine"
rm -rf "$HOME/.cache/wine"
rm -rf "$HOME/.config/wine"
rm -rf "$HOME/.local/share/wine"
rm -rf "$HOME/.winetricks"
rm -rf "$HOME/.local/share/applications/wine"
#echo ">>> 7. Настройка WineHQ"
#sudo dpkg --add-architecture i386
#sudo mkdir -pm755 /etc/apt/keyrings
#wget -qO- https://dl.winehq.org/wine-builds/winehq.key | sudo tee /etc/apt/keyrings/winehq-archive.key >/dev/null
#
#UBUNTU_NAME=$(grep UBUNTU_CODENAME /etc/os-release | cut -d= -f2)
#sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/$UBUNTU_NAME/winehq-$UBUNTU_NAME.sources
#sudo apt update
#
#if ! apt-cache policy winehq-staging | grep -q "Candidate"; then
#echo "Ошибка: пакет не найден"
#exit 1
#fi
#

UBUNTU_VERSION=$(grep UBUNTU_CODENAME /etc/os-release | cut -d= -f2)

if [[ "$UBUNTU_VERSION" == "focal" ]]; then
  REPO="focal"
elif [[ "$UBUNTU_VERSION" == "jammy" ]]; then
  REPO="jammy"
elif [[ "$UBUNTU_VERSION" == "noble" ]]; then
  REPO="noble"
elif [[ "$UBUNTU_VERSION" == "bionic" ]]; then
  REPO="bionic"
else
  echo "Не удалось определить версию Ubuntu для Linux Mint. Проверьте вручную."
  exit 1
fi

sudo apt update && sudo apt upgrade -y
sudo dpkg --add-architecture i386
sudo apt install -y wget gnupg2 software-properties-common

sudo mkdir -pm 755 /etc/apt/keyrings
wget -O - https://dl.winehq.org/wine-builds/winehq.key | sudo gpg --dearmor -o /etc/apt/keyrings/winehq-archive.key

sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/$REPO/winehq-$REPO.sources

sudo apt update
sudo apt install --install-recommends winehq-staging -y

sudo rm /etc/apt/sources.list.d/winehq-$REPO.sources
sudo rm /etc/apt/keyrings/winehq-archive.key

wine --version

# 9. Создание 32-битного префикса с отключением wow64
# -------------------------------
echo ">>> 9. Создание 32-битного префикса (wow64 off)"
export WINEARCH=win32
export WINEPREFIX="$HOME/.wine"
export WINEDEBUG=-all
# Отключаем wow64 через переменную окружения (для новых версий Wine)
export WINE_WOW64=0

# Удаляем возможный старый префикс (на всякий случай)
rm -rf "$WINEPREFIX"
# Инициализация
$WINE_BIN wineboot --init

# Ждём готовности
for i in {1..30}; do
    if [ -f "$WINEPREFIX/system.reg" ]; then
        echo "✅ Префикс создан"
        break
    fi
    sleep 2
done

# Проверяем, что syswow64 не создан
if [ -d "$WINEPREFIX/drive_c/windows/syswow64" ]; then
    echo "❌ ОШИБКА: Префикс 64-битный (syswow64 существует). Отмена."
    exit 1
else
    echo "✅ Префикс 32-битный (syswow64 отсутствует)"
fi

# Проверяем regedit
if ! $WINE_BIN regedit /? >/dev/null 2>&1; then
    echo "❌ regedit не работает. Возможно, проблема с префиксом."
    ls -la "$WINEPREFIX/drive_c/windows"
    exit 1
fi
echo "✅ regedit работает"

# -------------------------------
# 10. Обновление winetricks до последней версии
# -------------------------------
echo ">>> 10. Обновление winetricks"
sudo apt remove -y winetricks 2>/dev/null || true
wget -q https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks -O /tmp/winetricks
chmod +x /tmp/winetricks
sudo mv /tmp/winetricks /usr/local/bin/winetricks
check_command winetricks

# -------------------------------
# 11. Установка библиотек группами
# -------------------------------
echo ">>> 11. Установка библиотек (это займёт время)"
# Определяем команду winetricks с полными переменными
WINETRICKS_CMD="env WINEPREFIX=$WINEPREFIX WINEARCH=$WINEARCH WINEDEBUG=-all /usr/local/bin/winetricks -q"

# Группа 1: базовые и d3dx9
$WINETRICKS_CMD d3dx9

# Группа 2: основные рантаймы
$WINETRICKS_CMD gdiplus riched20 corefonts faudio remove_mono winxp dotnet40 gdiplus_winxp mfc70

# Группа 3: VC++ и DXVK
$WINETRICKS_CMD vcrun2010 dxvk d3dx10 d3dcompiler_47 xact dotnet48 physx quartz

# Группа 4: остальные VC++ и изоляция
$WINETRICKS_CMD vcrun2005 vcrun2013 vcrun2022 isolate_home sandbox

# Группа 5: прочие библиотеки
$WINETRICKS_CMD mfc42 msaa dinput dinput8 allfonts msxml3 ie8 wmp10 windowscodecs mspatcha

# Группа 6: финальные
$WINETRICKS_CMD ole32 msxml6 riched30 mscoree fontsmooth=rgb

# -------------------------------
# 12. Завершение
# -------------------------------
echo ">>> 12. Ожидание завершения фоновых процессов"
$WINESERVER_BIN -w

echo ">>> Запуск wineserver в фоне"
$WINESERVER_BIN -p

echo
echo "======================================================"
echo "✅ УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО"
echo "Префикс: $WINEPREFIX (32 бита)"
echo "Wine: $($WINE_BIN --version)"
echo "======================================================"

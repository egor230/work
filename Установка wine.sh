#!/bin/bash
set -e  # останов при любой ошибке
set -x  # подробный вывод (можно убрать, если не нужно)

echo ">>> ЯДЕРНАЯ ЗАЧИСТКА ВСЕГО, ЧТО СВЯЗАНО С WINE"

# 1. Убиваем все процессы wine, включая фоновые и системные
sudo pkill -9 -f "wine|wineserver|wine-preloader" 2>/dev/null || true
killall -9 wineserver wine wine64 wine-preloader wine64-preloader 2>/dev/null || true
wineserver -k 2>/dev/null || true
sudo lsof -ti:2048-2050 | xargs -r sudo kill -9 2>/dev/null || true  # порты wineserver
sleep 3

# 2. Удаляем все бинарники wine из стандартных и нестандартных мест
sudo find /usr/local/bin /usr/bin /bin /opt ~/.local/bin ~/bin -type f -name "*wine*" -exec rm -f {} \; 2>/dev/null || true
sudo find /usr/local/bin /usr/bin /bin /opt ~/.local/bin ~/bin -type f -name "*wineserver*" -exec rm -f {} \; 2>/dev/null || true
sudo find /usr/local/sbin /usr/sbin /sbin -type f -name "*wine*" -exec rm -f {} \; 2>/dev/null || true

# 3. Удаляем каталоги, где мог быть установлен Wine вручную
sudo rm -rf /opt/wine* /opt/winehq* ~/wine* ~/Wine* ~/.cache/wine* ~/.config/wine* ~/.local/share/wine* ~/.wine*

# 4. Полное удаление пакетов Wine и winetricks
sudo apt remove --purge -y wine* winehq* winetricks 2>/dev/null || true
sudo apt autoremove -y
sudo apt autoclean

# 5. Удаление всех репозиториев и ключей Wine
sudo rm -f /etc/apt/sources.list.d/winehq*
sudo rm -f /etc/apt/keyrings/winehq*
sudo rm -f /etc/apt/trusted.gpg.d/winehq.gpg
sudo rm -f /etc/apt/trusted.gpg.d/winehq.asc

# 6. Очистка PATH от возможных упоминаний старых бинарников
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin"

echo ">>> ПРОВЕРКА: после зачистки не должно быть wine в PATH"
which wine 2>/dev/null && echo "ОШИБКА: wine всё ещё найден" && exit 1
which wineserver 2>/dev/null && echo "ОШИБКА: wineserver всё ещё найден" && exit 1

echo ">>> НАСТРОЙКА РЕПОЗИТОРИЯ WINEHQ (ТОЛЬКО STAGING)"
sudo dpkg --add-architecture i386
sudo mkdir -pm755 /etc/apt/keyrings

# Скачиваем ключ
wget -qO- https://dl.winehq.org/wine-builds/winehq.key | sudo tee /etc/apt/keyrings/winehq-archive.key >/dev/null

# Определяем кодовое имя Ubuntu
UBUNTU_CODENAME=$(lsb_release -sc)
sudo wget -NP /etc/apt/sources.list.d/ \
    https://dl.winehq.org/wine-builds/ubuntu/dists/$UBUNTU_CODENAME/winehq-$UBUNTU_CODENAME.sources

sudo apt update

# Проверяем, доступен ли winehq-staging
if ! apt-cache policy winehq-staging | grep -q "Candidate"; then
    echo "ОШИБКА: winehq-staging не найден. Вывод apt-cache:"
    apt-cache policy winehq-staging
    exit 1
fi

echo ">>> УСТАНОВКА WINEHQ-STAGING И WINETRICKS"
sudo apt install -y --install-recommends winehq-staging winetricks

# Проверка, что бинарники появились
echo ">>> Проверка установки:"
ls -la /usr/bin/wine* | head -5
WINE_BIN=$(which wine)
WINESERVER_BIN=$(which wineserver)
echo ">>> wine: $WINE_BIN"
echo ">>> wineserver: $WINESERVER_BIN"

# Выводим версии
$WINE_BIN --version
$WINESERVER_BIN --version

# Убеждаемся, что нет других версий
if command -v wineserver >/dev/null; then
    WINESERVER_PATH=$(which wineserver)
    echo ">>> wineserver path: $WINESERVER_PATH"
else
    echo "ОШИБКА: wineserver не найден после установки"
    exit 1
fi

echo ">>> СОЗДАНИЕ ЧИСТОГО 32-БИТНОГО ПРЕФИКСА С ПОЛНЫМИ ПУТЯМИ"
export WINEARCH=win32
export WINEPREFIX="$HOME/.wine"
export WINEDEBUG=-all
export WINE=$WINE_BIN
export WINESERVER=$WINESERVER_BIN

# Полная инициализация
$WINE_BIN wineboot --init

# Ждём готовности
echo ">>> Ожидание создания префикса..."
for i in {1..30}; do
    if [ -f "$WINEPREFIX/system.reg" ]; then
        echo ">>> Префикс создан"
        break
    fi
    sleep 2
done

# Проверяем regedit (используем полный путь)
if ! $WINE_BIN regedit /? >/dev/null 2>&1; then
    echo "ОШИБКА: regedit не отвечает. Содержимое префикса:"
    ls -la "$WINEPREFIX/drive_c/windows"
    exit 1
fi
echo ">>> regedit работает корректно"

# Убеждаемся, что это 32-битный префикс (нет syswow64)
if [ -d "$WINEPREFIX/drive_c/windows/syswow64" ]; then
    echo "ОШИБКА: Префикс 64-битный (обнаружен syswow64). Переменная WINEARCH не сработала."
    exit 1
fi
echo ">>> Префикс 32-битный (syswow64 отсутствует)"

echo ">>> УСТАНОВКА БИБЛИОТЕК ЧЕРЕЗ WINETRICKS"
# Используем полные пути и явные переменные
WINETRICKS_CMD="env WINEPREFIX=$WINEPREFIX WINEARCH=$WINEARCH WINEDEBUG=-all winetricks -q"

# Устанавливаем группами для надёжности
$WINETRICKS_CMD d3dx9
$WINETRICKS_CMD gdiplus riched20 corefonts faudio remove_mono winxp
$WINETRICKS_CMD dotnet40 gdiplus_winxp mfc70 vcrun2010 dxvk d3dx10 d3dcompiler_47 xact
$WINETRICKS_CMD dotnet48 physx quartz vcrun2005 vcrun2013 vcrun2022 isolate_home sandbox
$WINETRICKS_CMD mfc42 msaa dinput dinput8 allfonts msxml3 ie8 wmp10 windowscodecs mspatcha
$WINETRICKS_CMD ole32 msxml6 riched30 mscoree fontsmooth=rgb

echo ">>> ЗАВЕРШЕНИЕ ФОНОВЫХ ПРОЦЕССОВ"
$WINESERVER_BIN -w

echo ">>> ЗАПУСК WINESERVER В ФОНЕ"
$WINESERVER_BIN -p

echo
echo "======================================================"
echo "✅ УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО"
echo "Префикс: $WINEPREFIX (32 бита)"
echo "Wine: $($WINE_BIN --version)"
echo "======================================================"

# Опционально: показать окно настроек
# $WINE_BIN winecfg

# По желанию можно открыть winecfg для дополнительных настроек
# winecfg

# По желанию можно открыть winecfg для дополнительных настроек
# winecfg

#sudo apt install -y xclip xsel
#В открывшемся окне winecfg:
#
#Перейди на вкладку «Библиотеки» (Libraries)
#
#В поле «Новая библиотека» по очереди добавь:
#
#gdiplus
#
#ole32
#
#oleaut32
#
#Для каждой выбери «(native, builtin)» и нажми ОК

#
#winetricks andale arial comicsans courier georgia impact times trebuchet verdana webdings  calibri physx tahoma lucida 7zip openal baekmuk cambria candara consolas constantia corbel droid eufonts ipamona liberation meiryo micross opensymbol sourcehansans takao uff unifont vlgothic wenquanyi wenquanyizenhei allfonts pptfonts directplay riched30 richtx32 fakechinese fakejapanese fakekorean cjkfonts
#winetricks

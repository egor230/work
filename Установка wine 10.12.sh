#!/bin/bash
sudo wineboot -y
wineserver -k
killall -9 wineserver wine-preloader wine
sudo apt remove --purge -y wine* wineserver* winetricks
sudo apt autoremove -y
wineserver -k
sudo rm /etc/apt/sources.list.d/winehq.list
sudo rm /usr/share/keyrings/winehq-archive.key
sudo rm /etc/apt/keyrings/winehq-archive.key
sudo mkdir -pm 755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
echo "--- Установка системных зависимостей ---"
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y build-essential flex bison git wget pv winetricks \
  libasound2-dev libasound2-dev:i386 libpulse-dev libpulse-dev:i386 \
  libdbus-1-dev libdbus-1-dev:i386 libfontconfig1-dev libfontconfig1-dev:i386 \
  libfreetype6-dev libfreetype6-dev:i386 libgnutls28-dev libgnutls28-dev:i386 \
  libpng-dev libpng-dev:i386 libx11-dev libx11-dev:i386 libxtst-dev libxtst-dev:i386 \
  libgdiplus libxcomposite-dev libxcomposite-dev:i386 libvulkan-dev libvulkan-dev:i386

# Устанавливаем необходимые утилиты для добавления репозиториев
sudo apt install -y software-properties-common wget
# Параметры
WINE_VERSION="10.12"
INSTALL_DIR="/opt/wine-$WINE_VERSION"
cd "$(dirname "$0")" || exit 1
mkdir -p "wine_build"
BUILD_DIR="./wine_build"
SRC_FILE="wine-$WINE_VERSION.tar.xz"
SRC_URL="https://dl.winehq.org/wine/source/10.x/$SRC_FILE"

# 3. Работа с исходниками
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

if [ -f "$SRC_FILE" ]; then
  echo "--- Исходники найдены, скачивание не требуется ---"
else
  echo "--- Скачивание исходников Wine $WINE_VERSION ---"
  wget --show-progress "$SRC_URL"
fi

if [ ! -d "wine-$WINE_VERSION" ]; then
  echo "--- Распаковка архива ---"
  pv "$SRC_FILE" | tar -xJ
fi

# 4. Сборка с индикацией
cd "wine-$WINE_VERSION"
mkdir -p build && cd build

echo "--- Конфигурация сборки (WoW64) ---"
../configure --prefix="$INSTALL_DIR" --enable-archs=i386,x86_64

echo "--- Начало сборки. Это займет время. ---"
echo "--- Используется ядер процессора: $(nproc) ---"

# Сборка с выводом прогресса (счетчик строк)
make -j2 2>&1 | pv -l -p > /dev/null

# 5. Установка
echo "--- Установка Wine в систему ---"
sudo make install

# 6. Создание ссылок для запуска командой 'wine'
echo "--- Настройка путей запуска ---"
sudo ln -sf "$INSTALL_DIR/bin/wine" /usr/local/bin/wine
sudo ln -sf "$INSTALL_DIR/bin/wine64" /usr/local/bin/wine64
sudo ln -sf "$INSTALL_DIR/bin/winecfg" /usr/local/bin/winecfg
sudo ln -sf "$INSTALL_DIR/bin/wineserver" /usr/local/bin/wineserver

# 7. Установка библиотек для Word и буфера обмена
echo "--- Установка библиотек (riched20, gdiplus, ole32) для Word и буфера ---"
# Обновляем winetricks до свежей версии
sudo winetricks --self-update

# Устанавливаем компоненты в префикс по умолчанию
wine wineboot -u
winetricks -q riched20 riched30 gdiplus windowscodecs ole32

echo "--- Установка завершена! ---"
wine --version
# Устанавливаем winetricks для удобного управления компонентами Windows
#sudo apt install winetricks -y

# ⬇️ 2. Устанавливаем нужные библиотеки в текущий префикс Wine
winetricks -q d3dx9 gdiplus riched20 corefonts msxml6

# ⬇️ 3. Настраиваем Wine — выставляем нужные библиотеки в режим native,builtin
winetricks -q vcrun2010 dxvk d3dx10 d3dcompiler_47 xact dotnet48 physx quartz corefonts vcrun2005 vcrun2013 vcrun2022 isolate_home sandbox mfc42 faudio remove_mono winxp dotnet40 gdiplus gdiplus_winxp mfc70 msaa dinput dinput8 corefonts allfonts msxml3 ie8 wmp10 windowscodecs mspatcha riched20 ole32 msxml6 riched30 mscoree fontsmooth=rgb
winecfg
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

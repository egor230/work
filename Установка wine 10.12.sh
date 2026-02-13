#!/bin/bash
# Очистка старых процессов и пакетов
#wineserver -k
#killall -9 wineserver wine-preloader wine 2>/dev/null
#sudo apt remove --purge -y wine* wineserver* winetricks
#sudo apt autoremove -y
#
# Удаление старых репозиториев
sudo rm /etc/apt/sources.list.d/winehq.list 2>/dev/null
sudo rm /usr/share/keyrings/winehq-archive.key 2>/dev/null
sudo rm /etc/apt/keyrings/winehq-archive.key 2>/dev/null

# Подготовка архитектуры и зависимостей
#echo "--- Установка зависимостей ---"
# 1. Исправление зависимостей и инструментов сборки
echo "--- Установка инструментов и библиотек (64 и 32 бит) ---"
sudo dpkg --add-architecture i386
sudo apt update
# Устанавливаем недостающие flex, bison и мульти-архитектурный компилятор
sudo apt install -y flex bison gcc-multilib g++-multilib pkg-config

# Установка ключевых библиотек разработки для обеих архитектур
sudo apt install -y \
  libx11-dev libx11-dev:i386 \
  libfreetype6-dev libfreetype6-dev:i386 \
  libvulkan-dev libvulkan-dev:i386 \
  libxcomposite-dev libxcomposite-dev:i386 \
  libxcursor-dev libxcursor-dev:i386 \
  libxfixes-dev libxfixes-dev:i386 \
  libxi-dev libxi-dev:i386 \
  libxrandr-dev libxrandr-dev:i386 \
  libxrender-dev libxrender-dev:i386 \
  libxext-dev libxext-dev:i386 \
  libgstreamer1.0-dev libgstreamer1.0-dev:i386 \
  libgstreamer-plugins-base1.0-dev libgstreamer-plugins-base1.0-dev:i386 \
  libsdl2-dev libsdl2-dev:i386 \
  libgnutls28-dev libgnutls28-dev:i386 \
  libfontconfig1-dev libfontconfig1-dev:i386 \
  libgpg-error-dev libgpg-error-dev:i386


# Параметры сборки
WINE_VERSION="10.12"
INSTALL_DIR="/opt/wine-$WINE_VERSION"
BUILD_DIR="$HOME/wine_build"
SRC_FILE="wine-$WINE_VERSION.tar.xz"
SRC_URL="https://dl.winehq.org/wine/source/10.x/$SRC_FILE"

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || exit 1

if [[ ! -f "$SRC_FILE" ]]; then
  echo "Скачиваю $SRC_URL..."
  wget "$SRC_URL"
fi

if [[ ! -d "wine-$WINE_VERSION" ]]; then
  tar -xJf "$SRC_FILE"
fi

cd "wine-$WINE_VERSION" || exit 1
mkdir -p build64 build32

# 2. Сборка 64-бит
echo "--- Сборка Wine 64-bit ---"
cd build64
if [ ! -f config.status ]; then
  ../configure --prefix="$INSTALL_DIR" --enable-win64 --with-x
fi
make -j4
cd ..

# 3. Сборка 32-бит
echo "--- Сборка Wine 32-bit ---"
cd build32
# Здесь магия: указываем компилятору использовать 32 бита и путь к 64-битной сборке
if [ ! -f config.status ]; then
  PKG_CONFIG_PATH=/usr/lib/i386-linux-gnu/pkgconfig \
  CC="gcc -m32" \
  CXX="g++ -m32" \
  ../configure --prefix="$INSTALL_DIR" --with-wine64=../build64 --with-x
fi
make -j4
cd ..

# 4. Установка
echo "--- Установка ---"
cd build32 && sudo make install
cd ../build64 && sudo make install

# Удаляем старые битые ссылки и создаем новые
sudo rm -f /usr/local/bin/wine /usr/local/bin/wine64 /usr/local/bin/wineserver
sudo ln -s "$INSTALL_DIR/bin/wine" /usr/local/bin/wine
sudo ln -s "$INSTALL_DIR/bin/wine64" /usr/local/bin/wine64
sudo ln -s "$INSTALL_DIR/bin/wineserver" /usr/local/bin/wineserver

# Теперь создание префикса
echo "--- Создание 32-битного префикса ---"
rm -rf "$HOME/.wine"
WINEARCH=win32 WINEPREFIX="$HOME/.wine" /usr/local/bin/wine wineboot --init
# Установка дополнительных компонентов
#echo "--- Установка дополнительных компонентов ---"
winetricks -q d3dx9 gdiplus riched20 corefonts msxml6
winetricks -q vcrun2010 dxvk d3dx10 d3dcompiler_47 xact dotnet48 physx quartz corefonts vcrun2005 vcrun2013 vcrun2022 isolate_home sandbox mfc42 faudio remove_mono winxp dotnet40 gdiplus gdiplus_winxp mfc70 msaa dinput dinput8 corefonts allfonts msxml3 ie8 wmp10 windowscodecs mspatcha  ole32 msxml6 riched30 mscoree fontsmooth=rgb
#
# Настройка Wine
winecfg

echo "--- Установка завершена! ---"
wine --version

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

#!/bin/bash
sudo wineboot -y
wineserver -k
killall -9 wineserver wine-preloader wine
#sudo apt remove --purge -y wine* wineserver* winetricks
sudo apt autoremove -y
wineserver -k
sudo rm /etc/apt/sources.list.d/winehq.list
sudo rm /usr/share/keyrings/winehq-archive.key
sudo rm /etc/apt/keyrings/winehq-archive.key
sudo mkdir -pm 755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
# Добавляем поддержку 32-битной архитектуры (важно для Wine)
sudo dpkg --add-architecture i386

# Обновляем список пакетов
sudo apt update

# Устанавливаем необходимые утилиты для добавления репозиториев
sudo apt install -y software-properties-common wget

# Загружаем и добавляем ключ репозитория WineHQ
wget -nc https://dl.winehq.org/wine-builds/winehq.key
sudo mkdir -p /usr/share/keyrings
sudo mv winehq.key /usr/share/keyrings/winehq-archive.key

echo "deb [signed-by=/etc/apt/keyrings/winehq-archive.key] https://dl.winehq.org/wine-builds/ubuntu/ noble main" | sudo tee /etc/apt/sources.list.d/winehq.list
# Обновляем индексы пакетов после добавления репозитория
sudo apt update
sudo apt install libasound2-plugins:i386 libdbus-1-3:i386 libfreetype6:i386 libgnutls30:i386 libjpeg-turbo8:i386 libpng16-16:i386 libncurses6:i386 libx11-6:i386 libxcomposite1:i386 libxcursor1:i386 libxext6:i386 libxi6:i386 libxinerama1:i386 libxrandr2:i386 libxrender1:i386 libxtst6:i386

# Устанавливаем Wine Development с рекомендуемыми зависимостями
sudo apt install --install-recommends winehq-devel -y


# Устанавливаем winetricks для удобного управления компонентами Windows
sudo apt install winetricks -y

# ⬇️ 2. Устанавливаем нужные библиотеки в текущий префикс Wine
#winetricks -q d3dx9 gdiplus riched20 corefonts msxml6

# ⬇️ 3. Настраиваем Wine — выставляем нужные библиотеки в режим native,builtin
#winetricks -q vcrun2010 dxvk d3dx10 d3dcompiler_47 xact dotnet48 physx quartz corefonts vcrun2005 vcrun2013 vcrun2022 isolate_home sandbox mfc42 faudio remove_mono winxp dotnet40 gdiplus gdiplus_winxp mfc70 msaa dinput dinput8 corefonts allfonts msxml3 ie8 wmp10 windowscodecs mspatcha riched20 ole32 msxml6 riched30 mscoree fontsmooth=rgb
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

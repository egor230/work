#!/bin/bash
sudo wineboot -y
wineserver -k
killall -9 wineserver wine-preloader wine
#sudo apt remove --purge -y wine* wineserver* winetricks
sudo apt autoremove -y
wineserver -k
sudo apt install --install-recommends winehq-devel -y
sudo apt install wine-devel wine-devel-i386 wine-devel-amd64 libwine libwine:i386 fonts-wine
sudo apt-get install winetricks -y

# ⬇️ 2. Устанавливаем нужные библиотеки в текущий префикс Wine
winetricks -q gdiplus riched20 msxml6 corefonts

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

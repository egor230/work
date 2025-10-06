#!/bin/bash
sudo wineboot -y
sudo apt install --install-recommends winehq-devel -y
sudo apt install wine-devel wine-devel-i386 wine-devel-amd64 libwine libwine:i386 fonts-wine
sudo apt-get install winetricks -y
winetricks  vcrun2010 dxvk d3dx10 d3dcompiler_47 xact dotnet48 physx quartz corefonts vcrun2005 vcrun2013 vcrun2022 isolate_home sandbox mfc42 faudio remove_mono winxp dotnet40 gdiplus gdiplus_winxp mfc70 msaa dinput dinput8 corefonts allfonts msxml3 ie8 wmp10 windowscodecs mspatcha riched20 ole32 msxml6 riched30 mscoree fontsmooth=rgb

#winetricks andale arial comicsans courier georgia impact times trebuchet verdana webdings  calibri physx tahoma lucida 7zip openal baekmuk cambria candara consolas constantia corbel droid eufonts ipamona liberation meiryo micross opensymbol sourcehansans takao uff unifont vlgothic wenquanyi wenquanyizenhei allfonts pptfonts directplay riched30 richtx32 fakechinese fakejapanese fakekorean cjkfonts
#winetricks

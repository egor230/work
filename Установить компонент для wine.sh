#!/bin/bash
sudo apt install --install-recommends winehq-devel -y
sudo apt install wine-devel wine-devel-i386 wine-devel-amd64 libwine libwine:i386 fonts-wine
winetricks -q  d3dx9 vcrun2010 dxvk vcrun2022 isolate_home sandbox mfc42 faudio andale arial comicsans courier georgia impact times trebuchet verdana webdings corefonts calibri physx tahoma lucida 7zip openal vcrun2005 vcrun2008 vcrun2010 vcrun2012 vcrun2013 baekmuk cambria candara consolas constantia corbel droid eufonts ipamona liberation meiryo micross opensymbol sourcehansans takao uff unifont vlgothic wenquanyi wenquanyizenhei allfonts pptfonts directplay remove_mono winxp dotnet40 gdiplus gdiplus_winxp mfc70 msaa riched30 richtx32 fakechinese fakejapanese fakekorean cjkfonts
winetricks
exit;

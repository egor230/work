#!/bin/bash
gnome-terminal -- bash -c '
# 1. Полное удаление пакетов Wine и Winetricks
sudo apt remove --purge "wine*" winetricks -y
sudo apt remove --purge wine winetricks wine-stable wine-devel wine-staging -y
sudo apt autoremove --purge -y
sudo apt clean

sudo rm -f /etc/apt/sources.list.d/winehq.list
sudo rm -f /usr/share/keyrings/winehq-archive.key
sudo rm -f /etc/apt/keyrings/winehq-archive.key

rm -rf ~/.wine
rm -rf ~/.local/share/applications/wine-extension-txt.desktop
rm -rf ~/.local/share/applications/wine-extension-xml.desktop

sudo dpkg --configure -a
sudo apt update

wine --version

sudo apt --fix-broken install -y
sudo apt install -f
sudo dpkg --configure -a
# 2. Удаление конфликтующих репозиториев и ключей
sudo rm -f /etc/apt/sources.list.d/winehq.list
sudo rm -f /usr/share/keyrings/winehq-archive.key
sudo rm -f /etc/apt/keyrings/winehq-archive.key

# 3. Очистка пользовательских префиксов и меню (удаляет все Windows-программы)
rm -rf ~/.wine
rm -rf ~/.local/share/applications/wine*
rm -rf ~/.local/share/desktop-directories/wine*

# 4. Исправление структуры и обновление базы пакетов
sudo dpkg --configure -a
sudo apt update

# Проверка версии
wine --version
sudo apt autoremove -y
sudo apt clean -y
sudo apt update
sudo apt --fix-broken install -y
sudo apt install -f
sudo dpkg --configure -a
wine --version
sudo apt install --install-recommends winehq-devel -y
sudo apt install wine-devel wine-devel-i386 wine-devel-amd64 libwine libwine:i386 fonts-wine
sudo apt install winetricks -y
winetricks -q d3dx9 vcrun2010 dxvk vcrun2022 isolate_home sandbox mfc42 faudio andale arial comicsans courier georgia impact times trebuchet verdana webdings corefonts calibri physx tahoma lucida 7zip openal vcrun2005 vcrun2008 vcrun2010 vcrun2012 vcrun2013 baekmuk cambria candara consolas constantia corbel droid eufonts ipamona liberation meiryo micross opensymbol sourcehansans takao uff unifont vlgothic wenquanyi wenquanyizenhei allfonts pptfonts directplay remove_mono winxp dotnet40 gdiplus gdiplus_winxp mfc70 msaa riched30 richtx32 fakechinese fakejapanese fakekorean cjkfonts
winetricks
exit;
exec bash'

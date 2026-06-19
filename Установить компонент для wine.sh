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
sudo apt autoremove -y
sudo apt clean -y
sudo apt update
sudo apt --fix-broken install -y
sudo apt install -f
sudo dpkg --configure -a
sudo dpkg --add-architecture i386 && sudo apt update  
wine --version
sudo apt install wine-devel wine-devel-i386 wine-devel-amd64 libwine libwine:i386 fonts-wine
sudo apt install winetricks -y
#export WINEARCH=win32
export WINEPREFIX=~/.wine
winecfg /v win7 
mkdir -p ~/.wine/drive_c/users/egor/AppData/Roaming
wine reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v "AppData" /t REG_SZ /d "C:\users\egor\AppData\Roaming" /f
winetricks -q corefonts tahoma mfc42 riched20 riched30 msxml3 gdiplus
winetricks -q mfc42 riched20 riched30
export WINEDLLOVERRIDES="riched20,riched30,msxml3,mfc42=n,b"
export LANG=ru_RU.UTF-8 
#winetricks -q mfc42 riched20 riched30
exit;
exec bash'
#sudo apt install wine-devel wine-devel-i386 wine-devel-amd64 libwine libwine:i386 fonts-wine

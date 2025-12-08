#!/bin/bash
gnome-terminal -- bash -c '
sudo apt remove --purge wine* winetricks -y
sudo apt autoremove --purge -y
sudo apt autoclean -y
sudo apt update
sudo dpkg --configure -a
sudo apt-get remove winetricks -y
sudo apt remove --purge wine winehq-devel wine-devel wine32-devel wine64-devel libwine libwine:i386 fonts-wine -y
sudo apt autoremove --purge -y
sudo apt autoremove -y
sudo apt clean -y
sudo apt update
sudo apt --fix-broken install -y
sudo apt install -f
sudo dpkg --configure -a
wine --version
exit;
exec bash'

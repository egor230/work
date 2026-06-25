#!/bin/bash
gnome-terminal -- bash -c '
sudo apt-get install pv -y
sudo apt-get install xautomation -y
sudo apt-get install xdotool -y
sudo apt install ffmpeg -y
sudo add-apt-repository ppa:obsproject/obs-studio -y
sudo apt install obs-studio -y
sudo apt install kdenlive -y
sudo apt-get install ttf-mscorefonts-installer -y
sudo fc-cache -f -v
sudo apt install curl -y
sudo apt-get install xclip xsel -y
sudo apt install yad libnotify-bin xclip -y
sudo apt install cuneiform doublecmd-gtk enca ffmpeg freecad imagemagick mediainfo openscad recoll secure-delete tesseract-ocr tesseract-ocr-rus unoconv -y
sudo apt-get install ia32-libs -y
sudo apt-get install extundelete -y
sudo apt-get install testdisk -y
sudo apt-get install scrot -y
sudo apt install tesseract-ocr -y
sudo apt-get install totem -y
sudo apt install gstreamer1.0-plugins-bad:i386 -y
sudo apt-get install tesseract-ocr -y
sudo apt-get install tesseract-ocr-rus -y
# Install dependencies (Ubuntu/Debian)
sudo apt install build-essential tesseract-ocr tesseract-ocr-eng libtesseract-dev libleptonica-dev -y
sudo apt-get install wl-clipboard -y
sudo apt-get install spice-vdagent -y
sudo apt-get install ovmf -y
sudo add-apt-repository ppa:alessandro-strada/ppa
sudo apt-get update -y
sudo apt-get install google-drive-ocamlfuse -y
sudo apt-get install 9mount -y
sudo apt install samba -y
sudo apt install remmina -y
sudo apt install software-properties-common -y
apt install nmap -y

sudo apt install poppler-utils -y
sudo apt-get update -y
sudo apt-get install libnfs-dev libiscsi-dev libepoxy-dev -y
sudo apt install git libglib2.0-dev libfdt-dev libpixman-1-dev zlib1g-dev -y
sudo apt install libnfs-dev libiscsi-dev libepoxy-dev -y
sudo apt install ninja-build -y

sudo apt install libaio-dev libbluetooth-dev libbrlapi-dev libbz2-dev libcap-ng-dev libcurl4-gnutls-dev libgtk-3-dev libibverbs-dev libjpeg8-dev libncurses5-dev libnuma-dev librbd-dev librdmacm-dev libsasl2-dev libsdl1.2-dev libseccomp-dev libsnappy-dev libssh-dev libvde-dev libvdeplug-dev libvte-2.91-dev libxen-dev liblzo2-dev valgrind xfslibs-dev libnfs-dev libiscsi-dev -y
sudo apt-get install libasound2-plugins:i386 -y
sudo apt install alsa-oss -y
sudo apt install simplescreenrecorder -y
sudo apt install deja-dup -y 
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update
echo "1" | sudo -S  sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys B7579F80E494ED3406A59DF9081525E2B4F1283B;
sudo apt-add-repository universe;
sudo apt-add-repository ppa:cubic-wizard/release;
sudo apt update;
sudo apt install --no-install-recommends cubic;b



sudo apt-get remove --auto-remove libqgispython3.10.4
sudo apt-get install libqgispython3.10.4

sudo apt install meson



exec bash'

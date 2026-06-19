#!/bin/bash
gnome-terminal -- bash -c '
sudo apt install libvulkan1 libwayland-client0 libwayland-server0
sudo apt --fix-broken install
sudo add-apt-repository ppa:alessandro-strada/ppa -y
sudo add-apt-repository ppa:cappelikan/ppa -y
sudo add-apt-repository ppa:alessandro-strada/ppa -y
sudo add-apt-repository ppa:ubuntu-desktop/ppa -y
sudo add-apt-repository ppa:3v1n0/gamescope -y   
sudo add-apt-repository universe -y
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
apt --fix-broken install
sudo apt-get update -y
sudo apt install -y google-chrome-stable
sudo apt install python3-tk -y
sudo apt install gamescope vulkan-tools -y 
sudo apt-get install pv -y
sudo apt-get install xautomation -y
sudo apt-get install xdotool -y
sudo apt install ffmpeg -y
sudo apt install vlc -y
sudo apt install copyq -y
sudo apt install obs-studio -y
sudo apt install kdenlive -y
sudo apt-get install ttf-mscorefonts-installer -y
sudo fc-cache -f -v
sudo apt install curl -y
sudo apt-get install xclip xsel -y
sudo apt install yad libnotify-bin xclip -y
sudo apt install build-essential git meson ninja-build cmake \
libx11-dev libx11-xcb-dev libxxf86vm-dev libxres-dev libxmu-dev \
libsdl2-dev libinput-dev libseat-dev libxcb-composite0-dev \
libxcb-icccm4-dev libxcb-res0-dev glslang-tools libpipewire-0.3-dev \
libwlroots-dev libvulkan-dev libliftoff-dev libavif-dev \
libbenchmark-dev wayland-protocols -y
sudo apt-get remove --auto-remove libqgispython3.10.4
sudo apt-get install libqgispython3.10.4
sudo apt install meson ninja-build libwayland-dev libegl1-mesa-dev libvulkan-dev libgl1-mesa-dev libgbm-dev libdrm-dev libjpeg-dev libpng-dev libwayland-egl-backend-dev luajit libxkbcommon-dev libinput-dev libcairo2-dev -y
sudo apt-get install mesa-vulkan-drivers vulkan-utils
sudo apt install libaio-dev libbluetooth-dev libbrlapi-dev libbz2-dev libcap-ng-dev libcurl4-gnutls-dev libgtk-3-dev libibverbs-dev libjpeg8-dev libncurses5-dev libnuma-dev librbd-dev librdmacm-dev libsasl2-dev libsdl1.2-dev libseccomp-dev libsnappy-dev libssh-dev libvde-dev libvdeplug-dev libvte-2.91-dev libxen-dev liblzo2-dev valgrind xfslibs-dev libnfs-dev libiscsi-dev -y￼￼
sudo apt install xkbset -y
sudo apt install meson -y
sudo apt install meson cmake pkg-config libx11-dev libxext-dev libpipewire-0.3-dev -y
sudo apt install libwayland-dev -y
sudo apt install libopenvr-dev -y
sudo apt install git build-essential meson cmake pkg-config libx11-dev libxext-dev libgl1-mesa-dev libpipewire-0.3-dev libwayland-dev libvulkan-dev -y
sudo apt install build-essential python3-pip python3-dev python3-setuptools libusb-1.0-0-dev libudev-dev -y
sudo apt-get install portaudio19-dev -y
sudo apt install libheif1 heif-thumbnailer -y
sudo apt install gameconqueror -y   
sudo apt-get install libasound2-plugins:i386 -y
sudo apt install alsa-oss -y
sudo apt install simplescreenrecorder -y
cd "$(dirname "$0")" || exit 1
sudo apt --fix-broken install
# Определение имени пользователя и путей
USER_NAME=$(whoami)
DEST_CONFIG="/home/$USER_NAME/.config"
SOURCE_CONFIG="/mnt/807EB5FA7EB5E954/python_linux/User data backup/.config"
DEB_DIR="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/deb packages"

# Функция для установки и копирования
install_and_config() {
  PACKAGE_FILE=$1
  echo "Установка: $PACKAGE_FILE"
  
  # Установка пакета
  sudo apt install ./"$PACKAGE_FILE" -y
  
  # Копирование настроек (если папка существует в бэкапе)
  # Мы используем флаг -r для папок
  cp -r "$SOURCE_CONFIG/." "$DEST_CONFIG/"
  
  echo "Готово для $PACKAGE_FILE"
  echo "--------------------------"
}

# Список ваших пакетов
install_and_config "anydesk.deb"
install_and_config "chromium.deb"
install_and_config "copyq_9.0.0_Debian_10-1_amd64.deb"
install_and_config "cursor_2.2.17_amd64.deb"
install_and_config "Hiddify-Debian-x64.deb"
install_and_config "obs-studio_26.1.2+dfsg1-2_amd64.deb"
install_and_config "pdfsam_5.2.8-1_amd64 объединить pdf.deb"
install_and_config "pinta_1.6-2_all.deb"
install_and_config "portproton_1.7-3_amd64.deb"
install_and_config "windscribe.deb"
install_and_config "Yandex.deb"

# Исправление зависимостей, если возникли проблемы
sudo apt install -f -y
# Удалить всё
sudo dpkg --remove --force-remove-reinstreq obs-studio
sudo apt purge obs-studio

# Скачать все нужные пакеты
wget http://archive.ubuntu.com/ubuntu/pool/main/f/ffmpeg/libavcodec58_4.2.7-0ubuntu0.1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/main/f/ffmpeg/libavformat58_4.2.7-0ubuntu0.1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/main/f/ffmpeg/libavutil56_4.2.7-0ubuntu0.1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/main/f/ffmpeg/libswscale5_4.2.7-0ubuntu0.1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/universe/m/mbedtls/libmbedcrypto3_2.16.9-0.1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/universe/m/mbedtls/libmbedtls12_2.16.9-0.1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/universe/m/mbedtls/libmbedx509-0_2.16.9-0.1_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/universe/x/x264/libx264-160_2%3a0.155.2917+git0a84d98-2_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/main/p/python3.9/libpython3.9_3.9.5-3~20.04.2_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/main/p/python3.9/python3.9_3.9.5-3~20.04.2_amd64.deb
wget http://archive.ubuntu.com/ubuntu/pool/universe/o/obs-studio/libobs0_26.1.2+dfsg1-2_amd64.deb

# Установить всё
sudo dpkg -i libavutil56_*.deb libswscale5_*.deb libavcodec58_*.deb libavformat58_*.deb libmbedcrypto3_*.deb libmbedtls12_*.deb libmbedx509-0_*.deb libx264-160_*.deb libpython3.9_*.deb python3.9_*.deb libobs0_*.deb

# Установить OBS 26.1.2
sudo dpkg -i obs-studio_26.1.2.deb

# Исправить зависимости
sudo apt install -f
sudo apt install mesa-vulkan-drivers mesa-vulkan-drivers:i386 libgbm1 libgbm1:i386 libgl1-mesa-dri libgl1-mesa-dri:i386 mesa-va-drivers mesa-va-drivers:i386
sudo apt install gamemode
echo "Все пакеты установлены, настройки скопированы."
exit
exec bash'
 

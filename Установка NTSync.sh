#!/bin/bash
#gnome-terminal -- bash -c '
# Обновление системы
# Удаление ненужных пакетов
sudo apt autoremove -y

# Установка зависимостей с разрешением изменения зафиксированных пакетов
sudo apt install git build-essential dkms linux-headers-$(uname -r) wine wine-staging steam -y --allow-change-held-packages

# Установка NTSync
git clone https://github.com/EasyNetDev/ntsync-dkms.git
cd ntsync-dkms
sudo make
sudo mkdir -p /lib/modules/$(uname -r)/updates/fs/ntsync
sudo cp ntsync/6.14/drivers/misc/ntsync.ko /lib/modules/$(uname -r)/updates/fs/ntsync/
sudo depmod -a
sudo modprobe ntsync

# Проверка модуля
lsmod | grep ntsync
echo "Установка NTSync завершена!"

#exec bash' 


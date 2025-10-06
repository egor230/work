#!/bin/bash
# Путь к VMDK диску
VMDK_FILE="/path/to/disk.vmdk"

# Точка монтирования
MOUNT_POINT="/mnt/vmdk"

# Отключить любые ранее подключенные nbd устройства
sudo qemu-nbd --list | while read -r line; do
  sudo qemu-nbd --disconnect $line
done

# Подключить VMDK
sudo qemu-nbd --connect=$VMDK_FILE

# Найти номер нужного раздела
PARTITION=$(sudo fdisk -l /dev/nbd0 | grep '86G' | awk '{print $1}')

# Создать точку монтирования
sudo mkdir -p $MOUNT_POINT

# Монтировать раздел
sudo mount -o rw /dev/${PARTITION} $MOUNT_POINT

# Размонтировать при выходе
#trap 'sudo umount $MOUNT_POINT; sudo qemu-nbd --disconnect /dev/nbd0' EXIT
exit

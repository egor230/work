#!/bin/bash

gnome-terminal -- bash -c '
username=$(whoami)

# название архива
archive_name="backup.tar.gz"

additional_dir="/.yandex_update"
# добавить новые файлы 
sudo tar -rf "$archive_name" "$additional_dir"

# перезаписать архив
sudo tar -czf "$archive_name" "$additional_dir"


# добавляем файлы из другой директории
#sudo tar -xzf "$archive_name" # извлечь под root
additional_dir="/usr/share/doc/yandex-browser-stable"
# добавить новые файлы 
#sudo tar -rf "$archive_name" "$additional_dir"

# перезаписать архив
#sudo tar -czf "$archive_name" "$additional_dir"


exec bash'

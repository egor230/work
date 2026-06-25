#!/bin/bash

gnome-terminal -- bash -c '
username=$(whoami)

echo "Восстановление из бэкапа. Нажмите Enter для продолжения"
read

addresses=(
  ["/.yandex_update"]=".yandex_update"  
  ["/usr/share/doc/yandex-browser-stable"]="yandex-browser-stable"  
  ["/opt/yandex"]="yandex"
  ["/opt/yandex/browser/video_translation/_metadata/yandex"]="yandex" 
  ["/home/$username/.yandex"]=".yandex"
  ["/home/$username/.cache/yandex-browser"]="yandex-browser"
  ["/home/$username/.config/yandex-browser"]="yandex-browser"
)

tar -czvf "yandex.tar.gz" $(for i in "${!addresses[@]}"; do echo "--directory=$i ${addresses[$i]}" ; done)
exec bash'

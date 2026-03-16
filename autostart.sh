#!/bin/bash
#sudo xmodmap ~/.Xmodmap
xkbcomp default.xkb $DISPLAY; # расскладка.
sudo usermod -aG input $USER;
sudo journalctl --vacuum-time=1s
sudo rm /var/log/Xorg.0.log
sudo modprobe -r kvm_amd kvm
#sudo locale-gen
# Получаем текущую раскладку (зависит от системы)
current_layout=$(xset -q | grep -A 0 'LED mask' | awk '{print $10}')

# Проверяем, что раскладка не русская
if [ "$current_layout" == "00001002" ]; then #000000002 
    # Имитируем нажатие Shift+Alt для переключения раскладки
    xte "keydown Shift_L" "keyup Shift_L" "keydown Alt_L" "keyup Alt_L"
    xte "keyup Shift_L" "keyup Alt_L"    # Дополнительные keyup на случай "залипания" клавиш (как в вашем примере)  
fi
nemo "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project";
#rivalcfg --sensitivity '610'
sudo usermod -aG sudo $USER;
sudo usermod -aG vboxusers $USER
cd "/mnt/807EB5FA7EB5E954/python_linux";
#find ~/Library/Caches -type f -delete 2>/dev/null
#find /Library/Caches -type f -delete 2>/dev/null # Удаляем все в ~/.cache/*, КРОМЕ папки Obsidian
#find ~/.cache/ -mindepth 1 -maxdepth 1 ! -name "Obsidian" -exec rm -rf {} + 2>/dev/null
#find ~/Library/Logs -type f -delete 2>/dev/null
#find /Library/Logs -type f -delete 2>/dev/null
#sudo rm -rf /var/log/* 2>/dev/null
#rm -rf /tmp/* 2>/dev/null
#rm -rf /var/tmp/* 2>/dev/null
#TARGET_DIR="/home/egor"  # Удаляем все .log файлы # Удаляем все .log файлы, 
#find "$TARGET_DIR" -type f \
#  -name "*.log" -delete
#find "$TARGET_DIR" -type f \ # Удаляем все .tmp файлы, исключая путь, содержащий .PyCharmCE2019.3
#  -name "*.tmp" -delete
cvt 1920 1080 90 
xrandr --newmode "1920x1080_90.00" 270.15 1920 2072 2280 2640 1080 1081 1084 1137 -HSync +Vsync
xrandr --addmode HDMI-A-0 1920x1080_90.00
xrandr --output HDMI-A-0 --mode 1920x1080_90.00
sleep 0.31
xte "keyup Shift_L" "keyup Alt_L"
xrandr --output HDMI-A-0 --brightness 0.73
sudo chown -R $USER:$USER ~/
sudo chown -R $USER:$USER /mnt/807EB5FA7EB5E954
systemctl --user list-units --type=service | grep -i windscribe
#sudo modprobe -r kvm_intel kvm_amd kvm

#xinput set-button-map 9 1 2 3 4 5 6 7 8 9;
# xte "keydown ISO_Next_Group"
#echo -n "" | xclip -i -selection primary
# Получаем информацию о подключенных мониторах
#monitor_info=$(xrandr --query)
# Извлекаем идентификатор первого подключенного монитора
# Извлекаем имя первого монитора
#monitor1=$(xrandr --query | grep "connected" | awk "{print $1}")
#echo "$monitor1"
#monitor=${monitor1%% *}
#xrandr --output "$monitor" --brightness 0.63

#sleep 0.5;
# Проверяем, существует ли файл Add_disk.img
#if [ ! -f "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/системы/Add_disk.img" ]; then
#    echo "Файл Add_disk.img не найден."
#    exit 1
#fi
#while true; do
#  sleep 1
#  sudo mount -o rw,noauto "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/системы/Add_disk.img" /media/egor
#
#  if [ $? -eq 0 ]; then
#    echo "Диск успешно подключен"
#    sleep 4.9
#    break
#  fi
#done
#xte 'key Num_Lock';
exit;

#xkbcomp default.xkb $DISPLAY; # расскладка.
# Создание точки монтирования
#sudo mkdir -p /mnt/e;

#xinput set-button-map 9 1 2 3 4 5 6 7 8 9;
#xinput disable 11;
#xinput disable 14;
#xinput disable 16;
#xinput disable 17;
#xinput set-button-map 10 1 2 3 4 5 6 7 11 10
# Выполнение команды
#gnome-terminal -- bash -c '
#cd /mnt/89d7250f-eddb-4218-bdc6-018b7fdb958f/python_linux/Project
#source ./venv/bin/activate
#python3.8 /mnt/89d7250f-eddb-4218-bdc6-018b7fdb958f/python_linux/Project/num_delete.py
#exec bash
#'

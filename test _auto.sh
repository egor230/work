#!/bin/bash
sudo usermod -aG sudo $USER;
#sudo chown -R $USER:$USER /mnt/807EB5FA7EB5E954
cd "/mnt/807EB5FA7EB5E954/python_linux";
sleep 1
xte 'keydown Shift_L' 'keydown Alt_L' 'keyup Shift_L' 'keyup Alt_L'; #
sudo usermod -aG input $USER;
#xte 'key Num_Lock';
xinput set-button-map 15 1 2 3 4 5 6 7 8 9;
# Извлекаем идентификатор первого подключенного монитора
# Получаем информацию о подключенных мониторах
monitor_info=$(xrandr --query)

# Извлекаем имя первого монитора
monitor1=$(xrandr --query | grep "connected" | awk "{print $1}")
echo "$monitor1"
monitor=${monitor1%% *}
xrandr --output "$monitor" --brightness 0.63
xkbcomp default.xkb $DISPLAY; # расскладка.
nemo;
sleep 8;
# Проверяем, существует ли файл Add_disk.img
#if [ ! -f "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/системы/Add_disk.img" ]; then
#    echo "Файл Add_disk.img не найден."
#    exit 1
#fi
#attempts=10
#
#for ((i=1; i<=attempts; i++)); do
#
# Подключение диска
#  gio set /media/egor metadata::nemo-automount-handled false
#
#  sudo mount -o rw, noauto'/mnt/807EB5FA7EB5E954/софт/виртуальная машина/системы/Add_disk.img' /media/egor
#  gio set /media/egor metadata::nemo-automount-handled false
#  if [ $? -eq 0 ]; then
#    echo "Диск успешно подключен"
#    gio set "/media/egor" metadata::nemo-folders '["/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project"]'
#    sleep 4.9
#    xte 'keydown Alt_R' 'keydown Space' 'keyup Alt_R' 'keyup Space'
#
#    break
#  fi
#
#  echo "Попытка $i не удалась, ожидаем 5 секунд..."
#
#  sleep 15
#
#done

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

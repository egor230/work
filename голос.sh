#!/bin/bash
gnome-terminal -- bash -c '
cd "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project";
sleep 1; # Даем немного времени терминалу загрузиться
xdotool key Control_R+Shift_R+t;
sleep 1;
xdotool key F3;
source myenv/bin/activate && python "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/голос.py";
exec bash'

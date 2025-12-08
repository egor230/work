#!/bin/bash
gnome-terminal -- bash -c '
sleep 0.2;
xte "keydown Control_R" "keydown Shift_R" "key t" "keyup Control_R" "keyup Shift_R"
sleep 0.2;
xte "keydown F3" "keyup F3"
cd "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project" && source myenv/bin/activate && python "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Голосовой_ввод_текста_яндекс_в_linux.py";
exit;
exec bash'
 

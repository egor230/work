#!/bin/bash
gnome-terminal -- bash -c '
sleep 0.4;
xte "keydown Control_R" "keydown Shift_R" "key t" "keyup Control_R" "keyup Shift_R"
sleep 0.4;
xte "keydown F3" "keyup F3"
cd "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project" && source myenv/bin/activate && python "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/набор_текста.py";
exit;
exec bash'
 

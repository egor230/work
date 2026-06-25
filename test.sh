#!/bin/bash
gnome-terminal -- bash -c '
#cd "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project" && source myenv/bin/activate && python "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/test.py";
xte "keydown ISO_Next_Group"
xte "keyup ISO_Next_Group"

sleep 2;
exit;
exec bash'

#!/bin/bash
gnome-terminal -- bash -c '
sleep 0.2;
xte "keydown Control_R" "keydown Shift_R" "key t" "keyup Control_R" "keyup Shift_R"
sleep 0.2;
xte "keydown F3" "keyup F3"
SCRIPT_PATH="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/Голосовой_ввод_текста_яндекс_pytq.py";
"$PYTHON_EXECUTABLE" "$SCRIPT_PATH";
#exit;
exec bash' 

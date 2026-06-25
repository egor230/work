#!/bin/bash
gnome-terminal -- bash -c ' 
sleep 0.2;
xte "keydown Control_R" "keydown Shift_R" "key t" "keyup Control_R" "keyup Shift_R"
sleep 1.3;
xte "keydown F3" "keyup F3"; # Прямой путь к интерпретатору внутри myenv
PYTHON_EXECUTABLE="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python"; # Путь к скрипту
SCRIPT_PATH="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/faster-whisper 2.py"; # Команда для запуска:
"$PYTHON_EXECUTABLE" "$SCRIPT_PATH";
exit;
exec bash'
 

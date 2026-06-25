#!/bin/bash
gnome-terminal -- bash -c 'sleep 1;
file=("$NEMO_SCRIPT_SELECTED_FILE_PATHS");  # Получаем имена выбранных файлов  
selected_file="${file%?}"
cd /mnt/807EB5FA7EB5E954/софт/виртуальная\ машина/linux\ must\ have/python_linux/Project && source myenv/bin/activate && python "$selected_file";
exit;
exec bash'


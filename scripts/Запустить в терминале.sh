#!/bin/bash
gnome-terminal -- bash -c 'sleep 1;
current_directory=$(pwd)   # Получаем текущую директорию с обработкой пробелов
cd "$current_directory";
selected_files=("$NEMO_SCRIPT_SELECTED_FILE_PATHS")  # Получаем имена выбранных файлов
file_name=$(basename "${selected_files[0]}")
echo "$file_name"
chmod +x "$file_name"
./"$file_name"  # Запускаем первый файл из выделенных
read;
exit
exec bash'

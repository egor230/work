#!/bin/bash
cd "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project"
source myenv/bin/activate

selected_files=("$NEMO_SCRIPT_SELECTED_FILE_PATHS")  # Получаем имена выбранных файлов
python "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Создать Desktop ярлык.py" $selected_files
exit

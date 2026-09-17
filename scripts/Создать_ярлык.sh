#!/bin/bash
# Создаёт .desktop-ярлык со значком для выделенного файла (AppImage/exe/deb/архив/скрипт...).
# Иконка подбирается автоматически: извлекается из файла (AppImage/PE/архив),
# берётся из картинки рядом, либо из системных значков.

# Nemo передаёт пути, разделённые переводами строк — так пробелы в именах не ломаются
IFS=$'\n' read -r -d '' -a selected_files <<< "$NEMO_SCRIPT_SELECTED_FILE_PATHS"

if [ ${#selected_files[@]} -eq 0 ]; then
    zenity --error --text="Не выбран ни один файл" 2>/dev/null || echo "нет выделенных файлов"
    exit 1
fi

PYTHON_BIN="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/myenv/bin/python"
SCRIPT_PATH="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/Создать Desktop ярлык.py"

"$PYTHON_BIN" "$SCRIPT_PATH" "${selected_files[@]}"

exit 0

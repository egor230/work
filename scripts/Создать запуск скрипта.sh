#!/bin/bash

# Получаем список выбранных файлов. В Nemo пути разделены символом новой строки.
# Этот способ корректно обрабатывает пути с пробелами.
IFS=$'\n' read -r -d '' -a selected_files <<< "$NEMO_SCRIPT_SELECTED_FILE_PATHS"

# Проходим по всем выбранным файлам и проверяем их расширение
for file in "${selected_files[@]}"; do
    # Приводим имя к нижнему регистру (${file,,}) для проверки и смотрим, заканчивается ли оно на .sh
    if [[ "${file,,}" == *.sh ]]; then
        # Выводим уведомление в Linux Mint (опционально, но удобно)
        notify-send "Ошибка" "Нельзя выполнять этот скрипт для файлов с расширением .sh" 2>/dev/null
        exit 1
    fi
done

# Если проверка пройдена успешно, определяем пути в переменные для удобства чтения
PYTHON_BIN="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python"
SCRIPT_PATH="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/Создать запуск скрипта.py"

# Запускаем Python-скрипт, корректно передавая все выбранные файлы (даже с пробелами в именах)
"$PYTHON_BIN" "$SCRIPT_PATH" "${selected_files[@]}"

exit 0

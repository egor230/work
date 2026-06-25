#!/bin/bash

# Проверяем, есть ли выбранные файлы/папки (переменная NEMO_SCRIPT_SELECTED_FILE_PATHS)
if [ -n "$NEMO_SCRIPT_SELECTED_FILE_PATHS" ]; then
    # Берём первый путь из списка (первая строка)
    selected_path=$(echo "$NEMO_SCRIPT_SELECTED_FILE_PATHS" | head -n1)
    # Убираем возможные кавычки, которые Nemo может добавлять при пробелах в имени
    selected_path="${selected_path#\"}"
    selected_path="${selected_path%\"}"
    # Копируем путь в буфер обмена
    echo -n "$selected_path" | xsel --clipboard --input
else
    # Ничего не выбрано — копируем текущую директорию
    current_dir=$(pwd)
    echo -n "$current_dir" | xsel --clipboard --input
fi

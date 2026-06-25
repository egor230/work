#!/bin/bash
gnome-terminal -- bash -c 'sleep 1;
current_directory="$(pwd)"  # Получаем текущую директорию с обработкой пробелов

echo "$current_directory"

# Получаем имена выбранных файлов
selected_files=("$NEMO_SCRIPT_SELECTED_FILE_PATHS")

# Перебираем выбранные файлы
for file in "${selected_files[@]}"; do
    # Имя файла без пути
    file_name=$(basename -- "$file")

    file_name_no_extension="${file_name%.*}"
    # Создаем имя для .desktop файла (замените пробелы на подчеркивания или что-то подобное)
    desktop_file_name="${file_name_no_extension// /_}.desktop"
    file1="${file%?}"
# Создаем содержимое .desktop файла
    desktop_file_content="[Desktop Entry]
    Name="$file_name_no_extension.desktop"
    Exec=\"$file1\"
    Icon=\"$file1\"
    Terminal=false
    Type=Application"

    # Полный путь для .desktop файла
    desktop_file_path="$current_directory/$desktop_file_name"

    # Записываем содержимое в .desktop файл
    echo "$desktop_file_content" > "$desktop_file_path"
done

# Подождать 5 секунд и закрыть терминал
sleep 5;
exit;
exec bash'

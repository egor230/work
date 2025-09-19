#!/bin/bash

# Папка для сохранения скриншотов
save_dir="/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Screenshots"

# Создаем папку, если она не существует
mkdir -p "$save_dir"

# Проверяем, существует ли папка
if [ ! -d "$save_dir" ]; then
    echo "Ошибка: Не удалось создать или найти директорию $save_dir"
    exit 1
fi

# Получаем текущие дату и время для имени файла
current_date=$(date +"%Y-%m-%d")
hours=$(date +"%H")
minutes=$(date +"%M")
seconds=$(date +"%S")

filename="${hours}_${minutes}_${seconds}_${current_date}.png"
filepath="${save_dir}/${filename}"

# Проверяем наличие необходимых инструментов
if ! command -v xclip &> /dev/null; then
    echo "Ошибка: xclip не установлен. Установите его командой: sudo apt install xclip"
    exit 1
fi

image_saved=false

# Проверка наличия изображения в буфере обмена (формат image/png)
if xclip -selection clipboard -t image/png -o > /dev/null 2>&1; then
    # Сохраняем изображение из буфера обмена в файл
    if xclip -selection clipboard -t image/png -o > "$filepath"; then
        if [ -s "$filepath" ]; then
            echo "✅ Изображение из буфера обмена успешно сохранено в $filepath"
            image_saved=true
        else
            echo "⚠️  Файл создан, но он пустой. Удаляем..."
            rm -f "$filepath"
        fi
    else
        echo "❌ Ошибка при сохранении изображения из буфера"
    fi
else
    echo "📋 В буфере обмена нет изображения"
fi
exit 0

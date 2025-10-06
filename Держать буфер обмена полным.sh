#!/bin/bash
# Получить текущую дату/время
now=$(date +"%F %T")

# Разбить на отдельные элементы
current_date=$(date +"%F")
hours=$(date +"%H")
minutes=$(date +"%M")
seconds=$(date +"%S")

# Сформировать имя файла
filename="/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Screenshots/${hours} ${minutes} ${seconds} ${current_date}.png"
# Проверяем, есть ли в буфере обмена URL изображения
image_url=$(copyq read 0)    # Получаем URL изображения из буфера обмена
if echo "$image_url" | grep -q "http"; then    # Скачиваем изображение
    curl -L -o "$filename" "$image_url" --retry 3 --retry-delay 1 --fail 
    sleep 0.3         #copyq remove 0  # Удаляем URL из буфера обмена
    echo  "$filename"
    xclip -selection clipboard -t image/png -i "$filename" # Помещаем изображение в буфер обмена
    sleep 0.6     
    copyq select 0
fi

# Проверяем, существует ли файл
if [ -e "$image_url" ]; then        #copyq remove 0  # Удаляем URL из буфера обмена
    xclip -selection clipboard -t image/png -i "$image_url" # Помещаем изображение в буфер обмена
    sleep 0.6  
    copyq select 0
fi
if [ -z "$(copyq clipboard)" ]; then
   echo "empty"
   copyq select 0
   sleep 0.3
fi
exit;

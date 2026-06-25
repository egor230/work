#!/bin/bash

sleep 1

# Получаем список устройств ввода
input_list=$(xinput list)

# Ищем строку с устройством "USB OPTICAL MOUSE"
mouse_line=$(echo "$input_list" | grep "USB OPTICAL MOUSE")

# Если строка найдена, извлекаем ID
if [ -n "$mouse_line" ]; then
    mouse_id=$(echo "$mouse_line" | grep -o "id=[0-9]*" | head -n 1 | cut -d "=" -f 2)
    echo "ID устройства 'USB OPTICAL MOUSE': $mouse_id"
fi

exec bash

#!/bin/bash

# Настройка переменных среды
#export WINEDLLOVERRIDES="d3d8,d3d9,ddraw,dinput8,dsound=n,b"
#export PW_VULKAN_USE=2
#export WINE_FULLSCREEN_FSR=1
#export WINE_FULLSCREEN_FSR_STRENGTH=1
export WINE_SIMULATE_WRITE=COPY

# Локализация (опционально)
export LC_ALL=ru_RU.UTF-8
export LANG=ru_RU.UTF-8

# Пути
WINEPREFIX_PATH="/home/egor/PortProton/data/prefixes/DEFAULT"
WINE_PATH="/home/egor/PortProton/data/dist/WINE_LG_10-10-1"
GAME_PATH="/home/egor/PortProton/data/prefixes/DEFAULT/drive_c/Program Files/Paint.NET/PaintDotNet.exe"

# Параметры gamescope
GAMESCOPE_ARGS="-f --force-windows-fullscreen -W 1920 -H 1080 -w 1920 -h 1080 -r 90 -S auto -F fsr --sharpness 20"

# Назначаем переменные
export WINEPREFIX="$WINEPREFIX_PATH"

# Запуск через gamescope
"$WINE_PATH/bin/wine" "$GAME_PATH"

exit; 

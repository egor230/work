#!/bin/bash

# 1. Добавление архитектуры i386 (если ещё не добавлена)
sudo dpkg --add-architecture i386

# 2. Скачивание и добавление ключа WineHQ
sudo mkdir -pm755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key

# 3. Добавление репозитория WineHQ для Bookworm
sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources

# 4. Обновление списка пакетов
sudo apt update

# 5. Исправление сломанных пакетов (если есть)
sudo apt --fix-broken install

# 6. Установка winehq-devel
sudo apt install --install-recommends winehq-devel -y


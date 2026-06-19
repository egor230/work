#!/bin/bash
sudo rm -f /etc/apt/sources.list.d/winehq-bookworm.sources

# 2. Добавление архитектуры i386
sudo dpkg --add-architecture i386

# 3. Подготовка папки для ключей и скачивание ключа
sudo mkdir -pm755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key

# 4. Добавление правильного репозитория для вашей системы (Ubuntu Noble / Linux Mint Zena)
sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources

# 5. Обновление и установка
sudo apt update
sudo apt install --install-recommends winehq-devel -y


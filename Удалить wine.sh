#!/bin/bash
gnome-terminal -- bash -c '
# 1. Полное удаление пакетов Wine и Winetricks
sudo apt remove --purge "wine*" winetricks -y
sudo apt autoremove --purge -y
sudo apt clean

# 2. Удаление конфликтующих репозиториев и ключей
sudo rm -f /etc/apt/sources.list.d/winehq.list
sudo rm -f /usr/share/keyrings/winehq-archive.key
sudo rm -f /etc/apt/keyrings/winehq-archive.key

# 3. Очистка пользовательских префиксов и меню (удаляет все Windows-программы)
rm -rf ~/.wine
rm -rf ~/.local/share/applications/wine*
rm -rf ~/.local/share/desktop-directories/wine*

# 4. Исправление структуры и обновление базы пакетов
sudo dpkg --configure -a
sudo apt update

# 5. Настройка архитектуры и ключей для новой установки
sudo dpkg --add-architecture i386
sudo mkdir -pm 755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key

# 6. Добавление актуального репозитория для вашей версии (Noble)
echo "deb [signed-by=/etc/apt/keyrings/winehq-archive.key] https://dl.winehq.org/wine-builds/ubuntu/ noble main" | sudo tee /etc/apt/sources.list.d/winehq.list

# 7. Финальная установка Wine Development и Winetricks
sudo apt update
sudo apt install --install-recommends winehq-devel -y
sudo apt install winetricks -y

# Проверка версии
wine --version
sudo apt autoremove -y
sudo apt clean -y
sudo apt update
sudo apt --fix-broken install -y
sudo apt install -f
sudo dpkg --configure -a
wine --version

exit;
exec bash'

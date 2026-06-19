#!/bin/bash

# Остановка при любых ошибках
set -e

echo "========================================="
echo " СБОРКА WINE + MANGOHUD В /home/egor/buld"
echo "========================================="

# 1. Жестко задаем рабочую директорию в Home
WORKDIR="/home/egor/buld"
mkdir -p "$WORKDIR"
cd "$WORKDIR"
echo "[*] Рабочая директория: $WORKDIR"

# Выдаем полные права на эту папку
chmod -R 777 "$WORKDIR"

# Решаем проблему Git с NTFS раз и навсегда для текущего пользователя
git config --global --add safe.directory '*'

# 2. Удаление старых конфликтующих пакетов Wine
echo "[*] Удаление старых пакетов Wine во избежание конфликтов..."
sudo apt autoremove -y --purge wine-devel wine-devel-amd64 wine-devel-i386 || true

# 3. Установка ВСЕХ зависимостей сразу (и для Wine, и для MangoHud, и для Word 2003)
echo "[*] Установка зависимостей (это может занять пару минут)..."
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y build-essential flex bison gcc-multilib g++-multilib \
libx11-dev libfreetype-dev pkg-config libasound2-dev libgl1-mesa-dev \
libvulkan-dev libxext-dev libxcursor-dev libxi-dev libxrandr-dev libxfixes-dev \
libxinerama-dev libxxf86vm-dev libpng-dev libjpeg-dev gettext curl \
mingw-w64 libfontconfig1-dev libfontconfig1:i386 \
meson ninja-build glslang-dev libglvnd-dev libdbus-1-dev libdbus-1-dev:i386 \
libx11-dev:i386 libvulkan-dev:i386 git

# ==========================================
# 4. СБОРКА MANGOHUD
# ==========================================
echo "[*] Клонирование MangoHud..."
rm -rf MangoHud # Удаляем старую попытку, если есть
git clone --depth 1 https://github.com/flightlessmango/MangoHud.git
cd MangoHud

echo "[*] Сборка MangoHud (64-bit и 32-bit для Word 2003)..."
# Собираем с помощью официального скрипта
./build.sh build
sudo ./build.sh install

echo "[+] MangoHud успешно установлен!"
cd "$WORKDIR"

# ==========================================
# 5. СБОРКА WINE (WoW64 - 64+32 бит)
# ==========================================
echo "[*] Клонирование Wine..."
rm -rf wine # Удаляем старую попытку, если есть
git clone --depth 1 https://github.com/ValveSoftware/wine.git
cd wine

echo "[*] Начало сборки Wine (будет быстрее, но всё равно нужно подождать)..."

# Шаг А: Сборка 64-битной части
echo "[*] --> Сборка 64-бит..."
mkdir -p build64
cd build64
../configure --prefix=/usr/local --enable-win64 --with-mingw
make -j$(nproc)

# Шаг Б: Сборка 32-битной части (обязательно для OFFICE11)
echo "[*] --> Сборка 32-бит..."
cd ..
mkdir -p build32
cd build32
../configure --prefix=/usr/local --with-wine64=../build64 --with-mingw
make -j$(nproc)

# 6. Установка 1 системного файла из репозитория как системного
echo "[*] Копирование системного файла wineserver в /usr/local/bin/..."
if [ -f "server/wineserver" ]; then
    sudo cp "server/wineserver" "/usr/local/bin/wineserver_custom"
    sudo chmod +x /usr/local/bin/wineserver_custom
    echo "[+] Системный файл wineserver установлен в /usr/local/bin/"
else
    echo "[-] Файл wineserver не найден!"
fi

# 7. Установка Wine в систему
echo "[*] Установка 32-бит части..."
sudo make install

echo "[*] Установка 64-бит части..."
cd ../build64
sudo make install

# 8. ОЧИСТКА ИСХОДНИКОВ (как ты просил)
echo "[*] Удаление исходников Wine и MangoHud для освобождения места..."
cd "$WORKDIR"
rm -rf wine MangoHud
echo "[+] Исходники удалены!"

echo "========================================="
echo " УСТАНОВКА УСПЕШЕННО ЗАВЕРШЕНА!         "
echo "========================================="
echo "[*] Проверка версии Wine:"
wine --version

echo "========================================="
echo " ИНСТРУКЦИЯ ДЛЯ WORD 2003:"
echo " 1. Обязательно выполни: rm -rf ~/.wine"
echo " 2. Настрой Wine: winecfg"
echo " 3. Запуск Word с MangoHud:"
echo "    mangohud wine \"C:\\Program Files (x86)\\Microsoft Office\\OFFICE11\\WINWORD.EXE\""
echo "========================================="

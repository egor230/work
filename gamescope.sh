#!/bin/bash
gnome-terminal -- bash -c '

sudo apt --fix-broken install
sudo add-apt-repository ppa:3v1n0/gamescope -y
sudo apt update
sudo apt install gamescope vulkan-tools -y
sudo apt install libgssapi-krb5-2:i386 libgssapi-krb5-2 winbind -y
sudo setcap "cap_sys_nice=eip" $(which gamescope)
sudo setcap "cap_sys_nice=eip" /usr/games/gamescope

# 1. Исправляем возможные ошибки пакетов
sudo apt --fix-broken install

# 2. Добавляем PPA. 
# Для Mint 22 (Ubuntu 24.04) этот PPA может быть не самым свежим.
# Если не заработает, лучше использовать встроенный в PortProton или системный.
sudo add-apt-repository ppa:3v1n0/gamescope -y
sudo apt update

# 3. Установка gamescope и необходимых инструментов для AMD
sudo apt install gamescope vulkan-tools mesa-vulkan-drivers mesa-vulkan-drivers:i386 -y

# 4. Установка библиотек для решения ошибок Kerberos/NTLM из твоего лога
# В логе были ошибки: "no Kerberos support" и "no NTLM support"
sudo apt install libgssapi-krb5-2 libgssapi-krb5-2:i386 winbind -y 

# 5. Применяем права доступа. 
# Проверяем оба возможных пути, где может лежать gamescope
GS_PATH=$(which gamescope)
if [ -z "$GS_PATH" ]; then
  GS_PATH="/usr/games/gamescope"
fi

echo "Применяю setcap к: $GS_PATH"
sudo setcap "cap_sys_nice=eip" "$GS_PATH"

# 6. Проверка результата
getcap "$GS_PATH"
exec bash'

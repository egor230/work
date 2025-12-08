#!/bin/bash

# Проверка версии VirtualBox
if command -v vboxmanage &> /dev/null; then
    version=$(vboxmanage --version)
    echo "Установленная версия VirtualBox: $version"
else
    echo "VirtualBox не установлен."
    exit 1
fi

# Удаление VirtualBox
echo "Удаление VirtualBox..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt-get remove --purge virtualbox-\* -y
    sudo apt-get autoremove -y
elif [[ "$OSTYPE" == "darwin"* ]]; then
    sudo rm -rf /Applications/VirtualBox.app
    sudo rm -rf ~/Library/VirtualBox
    sudo pkgutil --forget org.virtualbox.pkg.virtualbox
    sudo rm -rf /Library/Application\ Support/VirtualBox
    sudo rm -rf /Library/Preferences/org.virtualbox.app.VirtualBox.plist
    sudo rm -rf /Library/Preferences/org.virtualbox.app.VirtualBoxVM.plist
fi

echo "VirtualBox удалён."

sudo apt autoremove -y

# Обновляем список пакетов sudo apt update

# Устанавливаем необходимые зависимости для сборки модулей ядра
sudo apt install -y gcc make linux-headers-$(uname -r) dkms

# Устанавливаем VirtualBox из локального deb-пакета
sudo dpkg -i virtualbox-7.20.deb || sudo apt --fix-broken install -y

VBoxManage internalcommands sethduuid "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/системы/windows 7/Windows 7 Диск с.vdi"
VBoxManage internalcommands sethduuid "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/системы/win 10/Disk C.vdi"
VBoxManage internalcommands sethduuid "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/системы/test/test.vdi"


# Добавляем текущего пользователя в группы vboxusers и audio
sudo usermod -aG vboxusers,audio $USER

echo "Установка VirtualBox завершена. Перезагрузите систему или выйдите и войдите заново, чтобы изменения групп вступили в силу."

#exec bash' 


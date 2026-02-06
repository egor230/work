#!/bin/bash
# =============================================================================
# ABSOLUTE VULKAN FIX - NO MORE ERRORS
# Полное исправление Vulkan для Linux Mint 22.1 X11
# =============================================================================

# Запуск с sudo
if [ "$EUID" -ne 0 ]; then
    echo "Запускаю с sudo..."
    exec sudo bash "$0" "$@"
fi

LOG="/tmp/vulkan-safe-fix.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== Безопасное обновление Vulkan для Radeon 780M ==="

# 1. Проверка железа
echo "Проверка видеокарты..."
if ! lspci | grep -iq "AMD"; then
  echo "Ошибка: AMD GPU не найден. Прерывание."
  exit 1
fi

# 2. Резервное копирование
echo "Создание бэкапов в /tmp/vulkan_backup..."
mkdir -p /tmp/vulkan_backup
cp /etc/environment /tmp/vulkan_backup/
[ -f /etc/X11/xorg.conf.d/10-amd.conf ] && cp /etc/X11/xorg.conf.d/10-amd.conf /tmp/vulkan_backup/

# 3. Очистка (только через apt, без rm -rf системных папок)
echo "Удаление конфликтующих драйверов..."
apt purge -y amdvlk vulkan-amdvlk 2>/dev/null || true

# 4. Репозитории и установка
add-apt-repository -y ppa:kisak/kisak-mesa
apt update
apt install -y mesa-vulkan-drivers mesa-vulkan-drivers:i386 libvulkan1 libvulkan1:i386 vulkan-tools

# 5. Проверка наличия .so файлов перед созданием ICD
LIB_64="/usr/lib/x86_64-linux-gnu/libvulkan_radeon.so"
LIB_32="/usr/lib/i386-linux-gnu/libvulkan_radeon.so"

if [ -f "$LIB_64" ]; then
  echo "Библиотека 64-бит найдена. Создаю конфиг..."
  mkdir -p /usr/share/vulkan/icd.d/
  cat > /usr/share/vulkan/icd.d/radeon_icd.x86_64.json << EOF
{
  "file_format_version": "1.0.0",
  "ICD": {
    "library_path": "$LIB_64",
    "api_version": "1.3.274"
  }
}
EOF
else
  echo "Критическая ошибка: $LIB_64 не найден!"
  exit 1
fi

# 6. Настройка окружения (безопасное добавление)
if ! grep -q "VK_ICD_FILENAMES" /etc/environment; then
  echo "VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json" >> /etc/environment
fi

# 7. Финальная проверка и предложение перезагрузки
echo "=== Настройка завершена успешно ==="
# 1. Установка недостающих 32-битных библиотек (нужно для Steam и игр)
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y mesa-vulkan-drivers mesa-vulkan-drivers:i386 libvulkan1 libvulkan1:i386 vulkan-tools

# 2. Создание структуры папок, если она была нарушена
sudo mkdir -p /usr/share/vulkan/icd.d

# 3. Создание корректного 64-битного конфига для RADV
sudo tee /usr/share/vulkan/icd.d/radeon_icd.x86_64.json << 'EOF'
{
    "file_format_version": "1.0.0",
    "ICD": {
        "library_path": "/usr/lib/x86_64-linux-gnu/libvulkan_radeon.so",
        "api_version": "1.3.274"
    }
}
EOF

# 4. Создание корректного 32-битного конфига (исправляет твою ошибку из лога)
sudo tee /usr/share/vulkan/icd.d/radeon_icd.i686.json << 'EOF'
{
    "file_format_version": "1.0.0",
    "ICD": {
        "library_path": "/usr/lib/i386-linux-gnu/libvulkan_radeon.so",
        "api_version": "1.3.274"
    }
}
EOF

# 5. Установка правильных прав на файлы
sudo chmod 644 /usr/share/vulkan/icd.d/*.json

# 6. Очистка старых переменных окружения и установка актуальных
sudo sed -i '/VK_ICD_FILENAMES/d' /etc/environment
sudo bash -c 'echo "VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json:/usr/share/vulkan/icd.d/radeon_icd.i686.json" >> /etc/environment'

# 7. Добавление пользователя в группы управления графикой
sudo usermod -aG video,render $USER

echo "Готово! Пожалуйста, перезагрузи компьютер для применения изменений."
read -p "Для применения драйверов нужна перезагрузка. Перезагрузить сейчас? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  reboot
fi

#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(pwd)
DOWNLOAD_DIR="$SCRIPT_DIR/proton-downloads"
PROTON_ARCHIVE="$DOWNLOAD_DIR/proton.tar.gz"
PROTON_URL="https://github.com/pythonlover02/Proton-Sarek/releases/download/Proton-Sarek10-17/Proton-Sarek10-17.tar.gz"
INSTALL_DIR="$SCRIPT_DIR/sarek-dist"
BACKUP_PATH="$SCRIPT_DIR/wine-prefix-backup"

echo "Проверка бэкапа"
if [ ! -d "$BACKUP_PATH" ]; then
  if [ -d "$HOME/.wine" ]; then
    mkdir -p "$BACKUP_PATH"
    cp -rp "$HOME/.wine" "$BACKUP_PATH/"
  fi
fi

echo "Проверка и загрузка Wine"
mkdir -p "$DOWNLOAD_DIR"
if [ ! -f "$PROTON_ARCHIVE" ]; then
  curl -L "$PROTON_URL" -o "$PROTON_ARCHIVE"
fi

if [ ! -d "$INSTALL_DIR" ]; then
  mkdir -p "$INSTALL_DIR"
  tar -xzf "$PROTON_ARCHIVE" -C "$INSTALL_DIR" --strip-components 1
fi

echo "Очистка портативных версий MangoHud для исключения конфликтов"
find /home/$USER -name "mangohud" -type f 2>/dev/null | while read -r m_file; do
  if [[ ! "$m_file" =~ ^/usr/ ]]; then
    rm -f "$m_file" || true
  fi
done

echo "Установка системных компонентов"
sudo apt install -y \
  mangohud 
echo "Принудительная настройка Vulkan слоя"
sudo mkdir -p /usr/share/vulkan/implicit_layer.d/
cat << 'EOF' | sudo tee /usr/share/vulkan/implicit_layer.d/mangohud.json
{
  "file_format_version": "1.0.0",
  "layer": {
    "name": "VK_LAYER_MANGOHUD_overlay",
    "type": "GLOBAL",
    "library_path": "/usr/lib/x86_64-linux-gnu/libMangoHud.so",
    "api_version": "1.3.0",
    "implementation_version": "1",
    "description": "MangoHud overlay layer",
    "functions": {
      "vkGetInstanceProcAddr": "overlay_GetInstanceProcAddr",
      "vkGetDeviceProcAddr": "overlay_GetDeviceProcAddr"
    },
    "enable_environment": { "MANGOHUD": "1" },
    "disable_environment": { "DISABLE_MANGOHUD": "1" }
  }
}
EOF
echo "Установка 32-битной и 64-битной версий MangoHud"
sudo apt install -y mangohud mangohud:i386

echo "Создание конфигурации MangoHud"
mkdir -p "$HOME/.config/MangoHud"
cat << 'EOF' > "$HOME/.config/MangoHud/MangoHud.conf"
position=top-left
font_size=24
cpu_stats
gpu_stats
fps
vulkan_driver
wine
EOF

echo "Принудительная настройка Vulkan слоев для 32-битных и 64-битных приложений"
sudo mkdir -p /usr/share/vulkan/implicit_layer.d/

# 64-битный слой
cat << 'EOF' | sudo tee /usr/share/vulkan/implicit_layer.d/mangohud.x86_64.json
{
  "file_format_version": "1.0.0",
  "layer": {
    "name": "VK_LAYER_MANGOHUD_overlay",
    "type": "GLOBAL",
    "library_path": "/usr/lib/x86_64-linux-gnu/libMangoHud.so",
    "api_version": "1.3.0",
    "implementation_version": "1",
    "description": "MangoHud overlay layer",
    "functions": {
      "vkGetInstanceProcAddr": "overlay_GetInstanceProcAddr",
      "vkGetDeviceProcAddr": "overlay_GetDeviceProcAddr"
    },
    "enable_environment": { "MANGOHUD": "1" },
    "disable_environment": { "DISABLE_MANGOHUD": "1" }
  }
}
EOF

# 32-битный слой
cat << 'EOF' | sudo tee /usr/share/vulkan/implicit_layer.d/mangohud.i386.json
{
  "file_format_version": "1.0.0",
  "layer": {
    "name": "VK_LAYER_MANGOHUD_overlay",
    "type": "GLOBAL",
    "library_path": "/usr/lib/i386-linux-gnu/libMangoHud.so",
    "api_version": "1.3.0",
    "implementation_version": "1",
    "description": "MangoHud overlay layer",
    "functions": {
      "vkGetInstanceProcAddr": "overlay_GetInstanceProcAddr",
      "vkGetDeviceProcAddr": "overlay_GetDeviceProcAddr"
    },
    "enable_environment": { "MANGOHUD": "1" },
    "disable_environment": { "DISABLE_MANGOHUD": "1" }
  }
}
EOF

echo "Создание обертки wine с поддержкой MangoHud для 32-битных и 64-битных приложений"
sudo tee /usr/local/bin/wine > /dev/null << 'EOF'
#!/bin/bash
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
export WINEARCH="${WINEARCH:-win64}"
export WINEDEBUG="${WINEDEBUG:--all}"
export MANGOHUD=1
export MANGOHUD_CONFIG=position=top-left,font_size=24,cpu_stats,gpu_stats,fps,vulkan_driver,wine
export VK_INSTANCE_LAYERS=VK_LAYER_MANGOHUD_overlay

# Определяем разрядность приложения и загружаем соответствующую библиотеку MangoHud
if [ -f "$1" ]; then
    # Проверяем разрядность исполняемого файла
    BITNESS=$(file -b "$1" | grep -o '32-bit\|64-bit' | head -1)
    if [ "$BITNESS" = "32-bit" ]; then
        export LD_PRELOAD="/usr/lib/i386-linux-gnu/libMangoHud.so${LD_PRELOAD:+:$LD_PRELOAD}"
    else
        export LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libMangoHud.so${LD_PRELOAD:+:$LD_PRELOAD}"
    fi
else
    # По умолчанию загружаем 64-битную версию
    export LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libMangoHud.so${LD_PRELOAD:+:$LD_PRELOAD}"
fi

# Используем нативный wine из системы
exec /usr/bin/wine "$@"
EOF



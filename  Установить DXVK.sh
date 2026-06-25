#!/bin/bash
gnome-terminal -- bash -c '
CURRENT_DIR=$(pwd)
DXVK_VERSION="2.3"
DXVK_ARCHIVE="dxvk-$DXVK_VERSION.tar.gz"
DXVK_URL="https://github.com/doitsujin/dxvk/releases/download/v$DXVK_VERSION/$DXVK_ARCHIVE"

echo "Работаем в директории: $CURRENT_DIR"

echo "Настройка реестра Wine..."
wine reg add "HKEY_CURRENT_USER\Software\Wine\X11 Driver" /v "Managed" /t REG_SZ /d "N" /f

if [ ! -f "$CURRENT_DIR/$DXVK_ARCHIVE" ]; then
echo "Скачивание DXVK..."
wget -O "$CURRENT_DIR/$DXVK_ARCHIVE" "$DXVK_URL"
fi

if [ ! -d "$CURRENT_DIR/dxvk-$DXVK_VERSION" ]; then
echo "Распаковка DXVK..."
tar -xf "$CURRENT_DIR/$DXVK_ARCHIVE" -C "$CURRENT_DIR"
fi

echo "Установка DLL файлов..."
mkdir -p ~/.wine/drive_c/windows/system32
mkdir -p ~/.wine/drive_c/windows/syswow64

cp "$CURRENT_DIR/dxvk-$DXVK_VERSION/x64/".dll ~/.wine/drive_c/windows/system32/
cp "$CURRENT_DIR/dxvk-$DXVK_VERSION/x32/".dll ~/.wine/drive_c/windows/syswow64/

echo "Настройка библиотек (Overrides)..."
wine reg add "HKEY_CURRENT_USER\Software\Wine\DllOverrides" /v "d3d11" /t REG_SZ /d "native" /f
wine reg add "HKEY_CURRENT_USER\Software\Wine\DllOverrides" /v "d3d10core" /t REG_SZ /d "native" /f
wine reg add "HKEY_CURRENT_USER\Software\Wine\DllOverrides" /v "d3d9" /t REG_SZ /d "native" /f
wine reg add "HKEY_CURRENT_USER\Software\Wine\DllOverrides" /v "dxgi" /t REG_SZ /d "native" /f

echo "Перезапуск Wine..."
wineserver -k

echo "DXVK настроен в текущей папке!"

exec bash'

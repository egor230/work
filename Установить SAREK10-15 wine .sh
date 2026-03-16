#!/bin/bash
#gnome-terminal -- bash -c '	

# Этот скрипт удаляет системный Wine (предполагая Ubuntu/Debian с apt),
# делает резервную копию текущего Wine prefix (~/.wine) в папку WineBackup в текущей директории,
# и настраивает сборку PROTON-SAREK10-15-ASYNC как системную версию Wine, вызываемую по команде 'wine'.
# Новая сборка будет установлена в /opt/wine-sarek для глобального доступа.
# Симлинки создаются в /usr/local/bin, чтобы команда 'wine' указывала на новую сборку.
# Учитываем возможные ситуации:
# - Если Wine не установлен через apt, пропустим удаление.
# - Если директория сборки не существует, скрипт прервётся.
# - Если ~/.wine не существует, пропустим бэкап.
# - Проверяем права root для установки в /opt.
# - После установки экспортируем переменные для немедленного использования.
# - Бэкап создаётся в текущей директории (где запущен скрипт) в папке WineBackup с временной меткой.

# Предупреждение: Запустите этот скрипт в терминале с sudo, если нужно (для удаления и установки).
# Перед запуском: Убедитесь, что /home/egor/PortProton/data/dist/PROTON-SAREK10-15-ASYNC существует и содержит bin/wine и т.д.

# Шаг 1: Проверка существования директории сборки
SAREK_DIR="/home/egor/PortProton/data/dist/PROTON-SAREK10-15-ASYNC"
if [ ! -d "$SAREK_DIR" ]; then
    echo "Ошибка: Директория $SAREK_DIR не существует. Проверьте путь и попробуйте снова."
    exit 1
fi

# Шаг 2: Резервная копия текущего Wine prefix в текущей директории
WINE_PREFIX="$HOME/.wine"
CURRENT_DIR=$(pwd)
BACKUP_DIR="$CURRENT_DIR/WineBackup_$(date +%Y%m%d_%H%M%S)"
if [ -d "$WINE_PREFIX" ]; then
    echo "Создаём резервную копию $WINE_PREFIX в $BACKUP_DIR..."
    mkdir -p "$BACKUP_DIR"
    cp -r "$WINE_PREFIX" "$BACKUP_DIR/.wine"
    if [ $? -ne 0 ]; then
        echo "Ошибка при создании бэкапа. Проверьте права и место на диске."
        exit 1
    fi
    echo "Бэкап создан успешно в $BACKUP_DIR."
else
    echo "Wine prefix ($WINE_PREFIX) не найден, пропускаем бэкап."
fi

# Шаг 3: Удаление системного Wine (только если установлен через apt)
echo "Проверяем и удаляем системный Wine..."
if dpkg -l | grep -q wine; then
    sudo apt update
    sudo apt remove --purge wine wine64 wine32 wine-stable wine-devel wine-staging -y
    sudo apt autoremove -y
    echo "Системный Wine удалён."
else
    echo "Системный Wine не найден (или не установлен через apt), пропускаем удаление."
fi

# Шаг 4: Установка новой сборки в /opt/wine-sarek
INSTALL_DIR="/opt/wine-sarek"
if [ -d "$INSTALL_DIR" ]; then
    echo "Директория $INSTALL_DIR уже существует. Удаляем старую установку..."
    sudo rm -rf "$INSTALL_DIR"
fi

echo "Копируем сборку в $INSTALL_DIR..."
sudo cp -r "$SAREK_DIR" "$INSTALL_DIR"
if [ $? -ne 0 ]; then
    echo "Ошибка при копировании. Проверьте права и место на диске."
    exit 1
fi

# Делаем исполняемыми бинарники
sudo chmod +x "$INSTALL_DIR/bin/"*

# Шаг 5: Создание симлинков для wine, wine64 и т.д. в /usr/local/bin
echo "Создаём симлинки в /usr/local/bin..."
sudo ln -sf "$INSTALL_DIR/bin/wine" /usr/local/bin/wine
sudo ln -sf "$INSTALL_DIR/bin/wine64" /usr/local/bin/wine64
sudo ln -sf "$INSTALL_DIR/bin/wineserver" /usr/local/bin/wineserver
sudo ln -sf "$INSTALL_DIR/bin/winecfg" /usr/local/bin/winecfg

# Шаг 6: Обновление PATH и WINEPREFIX в ~/.bashrc
if ! grep -q "$INSTALL_DIR/bin" "$HOME/.bashrc"; then
    echo "export PATH=\"$INSTALL_DIR/bin:\$PATH\"" >> "$HOME/.bashrc"
    echo "export WINEPREFIX=\"$WINE_PREFIX\"" >> "$HOME/.bashrc"  # Сохраняем старый prefix
    source "$HOME/.bashrc"
    echo "PATH и WINEPREFIX обновлены. Перезапустите терминал или выполните 'source ~/.bashrc'."
else
    echo "PATH уже содержит $INSTALL_DIR/bin, пропускаем добавление."
fi

# Шаг 7: Тестирование
echo "Тестируем новую установку..."
wine --version
if [ $? -ne 0 ]; then
    echo "Ошибка: Wine не запускается. Проверьте установку."
    exit 1
fi

echo "Установка завершена успешно! Теперь 'wine' вызывает PROTON-SAREK10-15-ASYNC."
echo "Ваш старый prefix сохранён в $WINE_PREFIX и доступен для использования."
echo "Бэкап создан в $BACKUP_DIR."
echo "Если нужно восстановить бэкап: mv $BACKUP_DIR/.wine $WINE_PREFIX"
echo "Совет: Эта сборка заменяет системный Wine, так как она лучше совместима и уже настроена. Ваш prefix не затронут, и вы можете использовать его как обычно с новой сборкой."

#exec bash' 


#!/bin/bash

# Указываем целевую папку для chromedriver
TARGET_DIR="/usr/local/bin"  # Можно изменить на нужную папку
CHROMEDRIVER_ZIP="chromedriver-linux64.zip"
CHROMEDRIVER_DIR="chromedriver-linux64"
CHROMEDRIVER_URL="https://chromedriver.storage.googleapis.com/LATEST_RELEASE"

# Проверяем, установлены ли необходимые утилиты
if ! command -v wget &> /dev/null; then
    echo "Ошибка: утилита 'wget' не установлена. Установите ее с помощью 'sudo apt install wget'."
    exit 1
fi

if ! command -v unzip &> /dev/null; then
    echo "Ошибка: утилита 'unzip' не установлена. Установите ее с помощью 'sudo apt install unzip'."
    exit 1
fi

# Переходим в текущую папку
cd "$(pwd)" || { echo "Ошибка: не удалось перейти в текущую папку"; exit 1; }

# Проверяем текущую версию chromedriver
CURRENT_VERSION=""
if command -v chromedriver &> /dev/null; then
    CURRENT_VERSION=$(chromedriver --version | awk '{print $2}')
    echo "Текущая версия chromedriver: $CURRENT_VERSION"
else
    echo "chromedriver не установлен."
fi

# Получаем последнюю версию chromedriver
echo "Проверяем последнюю версию chromedriver..."
LATEST_VERSION=$(wget -qO- "$CHROMEDRIVER_URL")
if [ -z "$LATEST_VERSION" ]; then
    echo "Ошибка: не удалось получить последнюю версию chromedriver."
    exit 1
fi
echo "Последняя версия chromedriver: $LATEST_VERSION"

# Сравниваем версии
if [ "$CURRENT_VERSION" = "$LATEST_VERSION" ]; then
    echo "У вас уже установлена последняя версия chromedriver ($CURRENT_VERSION)."
    exit 0
fi

# Запрашиваем подтверждение у пользователя
echo "Доступна новая версия chromedriver ($LATEST_VERSION). Хотите скачать и установить её? (да/нет)"
read -r RESPONSE
if [ "$RESPONSE" != "y" ]; then
    echo "Установка отменена пользователем."
    exit 0
fi

# Формируем URL для скачивания
DOWNLOAD_URL="https://chromedriver.storage.googleapis.com/${LATEST_VERSION}/${CHROMEDRIVER_ZIP}"

# Скачиваем chromedriver
echo "Скачиваем chromedriver версии ${LATEST_VERSION}..."
wget -O "$CHROMEDRIVER_ZIP" "$DOWNLOAD_URL"
if [ $? -ne 0 ]; then
    echo "Ошибка: не удалось скачать chromedriver."
    exit 1
fi

# Распаковываем архив
echo "Распаковываем $CHROMEDRIVER_ZIP..."
unzip -o "$CHROMEDRIVER_ZIP" -d .
if [ $? -ne 0 ]; then
    echo "Ошибка: не удалось распаковать $CHROMEDRIVER_ZIP."
    exit 1
fi

# Проверяем, существует ли файл chromedriver
if [ ! -f "$CHROMEDRIVER_DIR/chromedriver" ]; then
    echo "Ошибка: файл chromedriver не найден в распакованной папке $CHROMEDRIVER_DIR."
    exit 1
fi

# Перемещаем chromedriver в целевую папку с использованием sudo
echo "Перемещаем chromedriver в $TARGET_DIR..."
sudo mv "$CHROMEDRIVER_DIR/chromedriver" "$TARGET_DIR/"
if [ $? -ne 0 ]; then
    echo "Ошибка: не удалось переместить chromedriver в $TARGET_DIR."
    exit 1
fi

# Устанавливаем права на выполнение с использованием sudo
sudo chmod +x "$TARGET_DIR/chromedriver"
if [ $? -ne 0 ]; then
    echo "Ошибка: не удалось установить права на выполнение."
    exit 1
fi

# Очищаем временные файлы
echo "Очищаем временные файлы..."
rm -rf "$CHROMEDRIVER_ZIP" "$CHROMEDRIVER_DIR"

echo "ChromeDriver успешно установлен в $TARGET_DIR/chromedriver!"

# Проверяем, что chromedriver доступен
if command -v chromedriver &> /dev/null; then
    echo "Проверка: chromedriver доступен, версия:"
    chromedriver --version
else
    echo "Ошибка: chromedriver не найден в PATH. Проверьте, добавлена ли $TARGET_DIR в PATH."
    exit 1
fi

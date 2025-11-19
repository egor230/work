#!/bin/bash

# Переустановка Ollama на Linux Mint с использованием официального tarball
# Этот скрипт удалит старую версию, скачает и установит свежую без ошибок

set -e  # Остановка при ошибке

echo "=== Переустановка Ollama на Linux Mint ==="

# Шаг 1: Остановка и отключение сервиса
echo "Останавливаем сервис Ollama..."
sudo systemctl stop ollama || true
sudo systemctl disable ollama || true

# Шаг 2: Удаление старых файлов
echo "Удаляем старые файлы Ollama..."
sudo rm -f /usr/local/bin/ollama /usr/bin/ollama
sudo rm -rf /usr/lib/ollama /usr/share/ollama
sudo rm -f /etc/systemd/system/ollama.service
sudo userdel ollama || true
sudo groupdel ollama || true

# Шаг 3: Обновление пакетов и зависимости
echo "Обновляем систему и устанавливаем зависимости..."
sudo apt install -y curl wget git fuse3 uidmap

# Шаг 4: Определение архитектуры
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        ARCH="amd64"
        DOWNLOAD_URL="https://ollama.com/download/ollama-linux-amd64.tgz"
        ;;
    aarch64|arm64)
        ARCH="arm64"
        DOWNLOAD_URL="https://ollama.com/download/ollama-linux-arm64.tgz"
        ;;
    *)
        echo "Неподдерживаемая архитектура: $ARCH"
        exit 1
        ;;
esac

echo "Архитектура: $ARCH"

# Шаг 5: Скачивание tarball
echo "Скачиваем Ollama для $ARCH..."
TEMP_TGZ="/tmp/ollama-linux-$ARCH.tgz"
curl -L -o "$TEMP_TGZ" "$DOWNLOAD_URL"

# Проверка скачивания (размер должен быть > 50MB)
FILE_SIZE=$(stat -c%s "$TEMP_TGZ")
if [ "$FILE_SIZE" -lt 50000000 ]; then
    echo "Ошибка: Файл скачан не полностью (размер: $FILE_SIZE байт). Проверьте интернет."
    rm -f "$TEMP_TGZ"
    exit 1
fi
echo "Скачано успешно: $FILE_SIZE байт"

# Шаг 6: Распаковка в /usr
echo "Распаковываем Ollama в /usr..."
sudo rm -rf /usr/lib/ollama  # Очистка старых lib
sudo tar -C /usr -xzf "$TEMP_TGZ"
rm -f "$TEMP_TGZ"

# Делаем бинарник исполняемым (на всякий случай)
sudo chmod +x /usr/bin/ollama

# Шаг 7: Создание пользователя ollama (опционально, но рекомендуется для изоляции)
echo "Создаем пользователя ollama..."
sudo groupadd -r ollama || true
sudo useradd -r -g ollama -s /bin/false -d /usr/share/ollama -m ollama || true
sudo mkdir -p /usr/share/ollama/.ollama/models
sudo chown -R ollama:ollama /usr/share/ollama

# Шаг 8: Создание systemd сервиса (официальный стиль)
echo "Создаем службу systemd..."
SERVICE_FILE="/etc/systemd/system/ollama.service"
cat > /tmp/ollama.service <<EOL
[Unit]
Description=Ollama Service
Documentation=https://ollama.com
After=network-online.target
Wants=network-online.target

[Service]
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_MODELS=/usr/share/ollama/.ollama/models"
User=ollama
Group=ollama
ExecStartPre=-/bin/rm -rf /usr/share/ollama/.ollama/models/blobs/sha256
ExecStartPre=-/bin/mkdir -p /usr/share/ollama/.ollama/models/blobs/sha256
ExecStartPre=/bin/chown -R ollama:ollama /usr/share/ollama/.ollama
ExecStart=/usr/bin/ollama serve
LimitNOFILE=65535
LimitNPROC=65535

[Install]
WantedBy=default.target
EOL

sudo mv /tmp/ollama.service "$SERVICE_FILE"
sudo systemctl daemon-reload

# Шаг 9: Включение и запуск сервиса
echo "Включаем и запускаем сервис..."
sudo systemctl enable ollama
sudo systemctl start ollama

# Ждем запуска
sleep 5

# Шаг 10: Проверка статуса
echo "Проверяем статус Ollama..."
sudo systemctl status ollama --no-pager -l

# Дополнительная проверка
if sudo -u ollama /usr/bin/ollama --version &> /dev/null; then
    echo "✅ Ollama успешно установлена и работает!"
    echo "Версия: $(/usr/bin/ollama --version)"
    echo "Для скачивания модели выполните: ollama pull llama3"
    echo "Сервис доступен на http://localhost:11434"
else
    echo "⚠️ Возможна проблема. Проверьте логи: journalctl -u ollama -f"
    echo "Также проверьте файл: file /usr/bin/ollama"
fi

echo "=== Установка завершена ==="

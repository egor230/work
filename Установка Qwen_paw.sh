#!/bin/bash
set -e

# Переходим в папку, где лежит сам скрипт
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Установка QwenPaw (облачный режим) ==="
echo "Рабочая директория: $(pwd)"

# Проверка файловой системы (NTFS может давать проблемы)
CURRENT_FS=$(df -T "$(pwd)" | awk 'NR==2 {print $2}')
if [[ "$CURRENT_FS" == "ntfs" || "$CURRENT_FS" == "fuseblk" ]]; then
    echo "ВНИМАНИЕ: вы работаете на NTFS-разделе. Рекомендуется ext4."
    read -p "Продолжить? (y/n): " CONTINUE
    [[ "$CONTINUE" != "y" ]] && exit 1
fi

# 1. Системные зависимости
echo "[1/6] Установка системных зависимостей..."
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv curl

# 2. Node.js 20
echo "[2/6] Проверка Node.js..."
NODE_MAJOR=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1)
if [[ -z "$NODE_MAJOR" || "$NODE_MAJOR" -lt 20 ]]; then
    echo "Устанавливаем Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi
echo "Node.js: $(node -v)"

# 3. Клонирование репозитория (с проверкой)
echo "[3/6] Подготовка репозитория QwenPaw..."
if [[ -e "QwenPaw" ]]; then
    if [[ ! -d "QwenPaw" ]]; then
        echo "Объект 'QwenPaw' существует, но не является директорией. Удаляем..."
        rm -rf QwenPaw
    else
        echo "Папка QwenPaw уже существует. Обновляем..."
        cd QwenPaw && git pull && cd ..
    fi
fi
if [[ ! -d "QwenPaw" ]]; then
    git clone https://github.com/agentscope-ai/QwenPaw.git
fi
cd QwenPaw

# 4. Виртуальное окружение
echo "[4/6] Создание виртуального окружения в $(pwd)/myvenv ..."
if [[ ! -d "myvenv" ]]; then
    python3 -m venv myvenv
fi
source myvenv/bin/activate

# 5. Сборка веб-интерфейса
echo "[5/6] Сборка веб-интерфейса..."
cd console
if [[ ! -d "dist" ]]; then
    npm ci
    npm run build
else
    echo "Web-интерфейс уже собран"
fi
cd ..
mkdir -p src/qwenpaw/console
cp -R console/dist/. src/qwenpaw/console/

# 6. Установка Python-пакета
echo "[6/6] Установка qwenpaw в виртуальное окружение..."
pip install --upgrade pip
pip install -e .

# Инициализация конфигурации
if [[ ! -d "$HOME/.qwenpaw" ]]; then
    qwenpaw init --defaults
fi

echo ""
echo "=========================================="
echo "Установка завершена!"
echo "Виртуальное окружение: $(pwd)/myvenv"
echo "=========================================="
echo ""
echo "Для запуска выполните:"
echo "  cd $(pwd)"
echo "  source myvenv/bin/activate"
echo "  ./run.sh"
echo ""
echo "Или просто запустите ./run.sh (он сам активирует venv)"
echo "=========================================="
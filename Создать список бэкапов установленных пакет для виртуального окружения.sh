#!/bin/bash
# backup_packages.sh - Скрипт для бэкапа пакетов

echo "=== Начинаю бэкап пакетов ==="
echo ""

# Находим venv в текущей папке и подпапках
if [ -f "myvenv/bin/activate" ]; then
    VENV="myvenv"
    echo "✅ Найден venv: myvenv"
elif [ -f "venv/bin/activate" ]; then
    VENV="venv"
    echo "✅ Найден venv: venv"
elif [ -f ".venv/bin/activate" ]; then
    VENV=".venv"
    echo "✅ Найден venv: .venv"
else
    # Ищем любую папку с bin/activate в текущей директории
    echo "🔍 Ищу виртуальное окружение..."
    for dir in */; do
        if [ -f "${dir}bin/activate" ]; then
            VENV="${dir%/}"
            echo "✅ Найден venv: $VENV"
            break
        fi
    done
fi

if [ -z "$VENV" ]; then
    echo "❌ Не найден venv в текущей папке"
    echo "Текущая папка: $(pwd)"
    echo "Содержимое:"
    ls -la
    exit 1
fi

echo ""
echo "Текущий путь: $(pwd)"
echo "Путь к venv: $(pwd)/$VENV"
echo ""

# Активируем venv
echo "Активирую виртуальное окружение..."
source "$VENV/bin/activate"

echo "Python: $(python --version 2>&1)"
echo ""

# Создаем папку для бэкапа
BACKUP_DIR="python_packages"
if [ -d "$BACKUP_DIR" ]; then
    echo "⚠️  Папка $BACKUP_DIR уже существует, очищаю..."
    rm -rf "$BACKUP_DIR"
fi

mkdir -p "$BACKUP_DIR"
echo "✅ Создана папка: $BACKUP_DIR"
echo ""

# Получаем список пакетов
echo "Получаю список пакетов..."
# Используем только нормальные пакеты, игнорируем ошибки
pip list --format=freeze 2>/dev/null | grep -v "Warning:" | grep -v "WARNING:" | grep -v "ERROR:" > requirements.txt

# Проверяем, что файл не пустой
if [ ! -s "requirements.txt" ]; then
    echo "⚠️  Файл requirements.txt пуст, пробую другой метод..."
    pip freeze 2>/dev/null | grep -E '^[a-zA-Z]' > requirements.txt
fi

PACKAGE_COUNT=$(wc -l < requirements.txt 2>/dev/null || echo "0")
echo "✅ Найдено пакетов: $PACKAGE_COUNT"

if [ "$PACKAGE_COUNT" -eq "0" ]; then
    echo "❌ Нет пакетов для бэкапа"
    deactivate
    exit 1
fi

echo ""
echo "Скачиваю пакеты..."
echo "Это может занять время..."
echo ""

# Скачиваем пакеты, игнорируем ошибки
DOWNLOADED=0
TOTAL=0

while read -r package; do
    TOTAL=$((TOTAL + 1))
    echo -n "[$TOTAL/$PACKAGE_COUNT] $package... "
    
    if pip download -d "$BACKUP_DIR" --quiet --no-deps "$package" 2>/dev/null; then
        echo "✅"
        DOWNLOADED=$((DOWNLOADED + 1))
    else
        echo "❌ (пропущен)"
    fi
done < requirements.txt

echo ""
echo "📊 Результат:"
echo "   Всего пакетов: $PACKAGE_COUNT"
echo "   Успешно скачано: $DOWNLOADED"
echo "   Пропущено: $((PACKAGE_COUNT - DOWNLOADED))"
echo ""

# Создаем чистый список только скачанных пакетов
if [ "$DOWNLOADED" -gt 0 ]; then
    echo "Создаю clean_requirements.txt..."
    > clean_requirements.txt
    
    while read -r package; do
        pkg_name=$(echo "$package" | cut -d'=' -f1)
        if ls "$BACKUP_DIR"/"$pkg_name"* 2>/dev/null | grep -q .; then
            echo "$package" >> clean_requirements.txt
        fi
    done < requirements.txt
    
    CLEAN_COUNT=$(wc -l < clean_requirements.txt)
    echo "✅ Создан clean_requirements.txt ($CLEAN_COUNT пакетов)"
fi

# Деактивируем venv
deactivate

echo ""
echo "========================================"
echo "✅ БЭКАП ВЫПОЛНЕН УСПЕШНО!"
echo "========================================"
echo ""
echo "Созданы файлы:"
echo "1. requirements.txt - список всех пакетов ($PACKAGE_COUNT шт.)"
if [ -f "clean_requirements.txt" ]; then
    echo "2. clean_requirements.txt - чистый список ($CLEAN_COUNT шт.)"
fi
echo "3. $BACKUP_DIR/ - папка с пакетами ($DOWNLOADED файлов)"
echo ""
echo "Для установки без интернета:"
echo "pip install --no-index --find-links=./$BACKUP_DIR -r ./clean_requirements.txt"
echo ""
echo "📁 Файлы готовы к переносу на другой компьютер!"
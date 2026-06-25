#!/bin/bash
# install_from_backup.sh - Установка пакетов БЕЗ интернета

echo "=== УСТАНОВКА ПАКЕТОВ БЕЗ ИНТЕРНЕТА ==="
echo ""

# Проверяем наличие папки с пакетами
if [ ! -d "python_packages" ]; then
    echo "❌ ОШИБКА: Папка 'python_packages' не найдена!"
    echo ""
    echo "Содержимое текущей папки:"
    ls -la
    echo ""
    echo "Убедитесь что в папке есть файлы пакетов (.whl, .tar.gz)"
    exit 1
fi

echo "✅ Папка с пакетами найдена: python_packages/"
echo ""

# Ищем файл со списком пакетов
if [ -f "clean_requirements.txt" ]; then
    REQUIREMENTS_FILE="clean_requirements.txt"
    echo "✅ Использую чистый список: clean_requirements.txt"
elif [ -f "requirements.txt" ]; then
    REQUIREMENTS_FILE="requirements.txt"
    echo "✅ Использую: requirements.txt"
else
    echo "❌ ОШИБКА: Не найден файл со списком пакетов!"
    echo "   Нужен requirements.txt или clean_requirements.txt"
    exit 1
fi

# Проверяем что файл не пустой
if [ ! -s "$REQUIREMENTS_FILE" ]; then
    echo "❌ ОШИБКА: Файл $REQUIREMENTS_FILE пуст!"
    exit 1
fi

# Считаем пакеты
PACKAGE_COUNT=$(wc -l < "$REQUIREMENTS_FILE" 2>/dev/null || echo "0")
echo "📦 Пакетов в списке: $PACKAGE_COUNT"
echo ""

# Проверяем файлы в папке
FILES_COUNT=$(find python_packages -name "*.whl" -o -name "*.tar.gz" -o -name "*.zip" 2>/dev/null | wc -l)
if [ "$FILES_COUNT" -eq 0 ]; then
    echo "❌ ОШИБКА: В папке нет файлов пакетов!"
    echo "   Первые файлы в папке:"
    ls python_packages/ | head -5
    exit 1
fi

echo "📄 Файлов пакетов найдено: $FILES_COUNT"
echo ""

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ ОШИБКА: Python3 не найден!"
    exit 1
fi

echo "🐍 Python3 найден: $(python3 --version 2>&1)"
echo ""

# Создаем новое виртуальное окружение
VENV_NAME="venv"

if [ -d "$VENV_NAME" ]; then
    echo "⚠️  Виртуальное окружение '$VENV_NAME' уже существует"
    echo ""
    read -p "Удалить и создать заново? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Удаляю старое окружение..."
        rm -rf "$VENV_NAME"
    else
        echo "✅ Использую существующее окружение"
    fi
fi

if [ ! -d "$VENV_NAME" ]; then
    echo "🔄 Создаю новое виртуальное окружение '$VENV_NAME'..."
    python3 -m venv "$VENV_NAME"
    
    if [ $? -ne 0 ]; then
        echo "❌ Не удалось создать виртуальное окружение"
        exit 1
    fi
    echo "✅ Виртуальное окружение создано"
fi

echo ""

# Активируем venv
echo "🔧 Активирую виртуальное окружение..."
source "$VENV_NAME/bin/activate"

if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "❌ Не удалось активировать виртуальное окружение"
    exit 1
fi

echo "✅ Виртуальное окружение активировано"
echo "   Python: $(python --version 2>&1)"
echo ""

# Устанавливаем пакеты БЕЗ интернета
echo "🚀 НАЧИНАЮ УСТАНОВКУ БЕЗ ИНТЕРНЕТА..."
echo "   Использую только локальные пакеты"
echo ""
echo "========================================"

# Пробуем установить все пакеты сразу
echo "📦 Пробую установить все пакеты..."
pip install \
    --no-index \
    --find-links=./python_packages \
    -r ./"$REQUIREMENTS_FILE" \
    --quiet \
    --disable-pip-version-check \
    --no-warn-script-location

if [ $? -eq 0 ]; then
    echo "✅ ВСЕ пакеты успешно установлены!"
else
    echo "⚠️  Были проблемы, устанавливаю по одному..."
    echo ""
    
    SUCCESS=0
    FAILED=0
    
    # Устанавливаем пакеты по одному (как в скрипте бэкапа)
    while read -r package; do
        echo -n "Устанавливаю $package... "
        
        if pip install \
            --no-index \
            --find-links=./python_packages \
            --quiet \
            --disable-pip-version-check \
            "$package" 2>/dev/null; then
            echo "✅"
            SUCCESS=$((SUCCESS + 1))
        else
            echo "❌"
            FAILED=$((FAILED + 1))
            # Сохраняем неудачные пакеты
            echo "$package" >> failed_packages.txt 2>/dev/null
        fi
    done < "$REQUIREMENTS_FILE"
    
    echo ""
    echo "========================================"
    echo "📊 РЕЗУЛЬТАТЫ УСТАНОВКИ:"
    echo "   Успешно: $SUCCESS"
    echo "   Не удалось: $FAILED"
    
    if [ "$FAILED" -gt 0 ]; then
        echo ""
        echo "⚠️  Не установленные пакеты сохранены в failed_packages.txt"
    fi
fi

echo "========================================"
echo ""

# Показываем установленные пакеты
INSTALLED_COUNT=$(pip list --format=freeze 2>/dev/null | wc -l)
echo "📦 Всего установлено пакетов: $INSTALLED_COUNT"
echo ""

if [ "$INSTALLED_COUNT" -gt 0 ]; then
    echo "Список установленных пакетов:"
    pip list --format=columns | head -10
    
    if [ "$INSTALLED_COUNT" -gt 10 ]; then
        echo "... и ещё $((INSTALLED_COUNT - 10)) пакетов"
    fi
fi

# Деактивируем venv
echo ""
echo "🔧 Деактивирую виртуальное окружение..."
deactivate

echo ""
echo "========================================"
echo "✅ УСТАНОВКА ЗАВЕРШЕНА!"
echo "========================================"
echo ""
echo "📁 Создано виртуальное окружение: $VENV_NAME/"
echo ""
echo "📝 КОМАНДЫ ДЛЯ РАБОТЫ:"
echo "1. Активировать: source $VENV_NAME/bin/activate"
echo "2. Проверить: pip list"
echo "3. Деактивировать: deactivate"
echo ""
echo "💡 Все пакеты установлены БЕЗ интернета!"
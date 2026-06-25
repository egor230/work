#!/bin/bash
#gnome-terminal -- bash -c '
# Каталог, куда будут сохранены пакеты.
DOWNLOAD_DIR="python_package_backup"

# Имя файла с требованиями
REQUIREMENTS_FILE="requirements.txt"
VENV_NAME="myvenv" 

# Полный относительный путь к активационному файлу
VENV_ACTIVATE="./$VENV_NAME/bin/activate"

# --- Проверки ---

echo "--- Начинаем процесс создания бэкапа ---"

# Проверка существования активационного скрипта в текущей директории
if [ ! -f "$VENV_ACTIVATE" ]; then
  echo "ОШИБКА: Виртуальное окружение не найдено в текущей папке."
  echo "       Ожидаемый путь: $VENV_ACTIVATE"
  echo "       Убедитесь, что вы находитесь в правильной директории или проверьте VENV_NAME."
  exit 1
fi

# --- Основные шаги ---

echo "1. Создание каталога для бэкапа ($DOWNLOAD_DIR)..."
# Создание папки бэкапа, если ее нет
mkdir -p $DOWNLOAD_DIR

echo "2. Активация виртуального окружения ($VENV_NAME)..."
# Используем относительный путь для активации
source $VENV_ACTIVATE
if [ $? -ne 0 ]; then
  echo "ОШИБКА: Не удалось активировать виртуальное окружение."
  deactivate 2>/dev/null 
  exit 1
fi

echo "3. Создание файла с требованиями ($REQUIREMENTS_FILE)..."
# Создаем файл requirements.txt в текущей директории
pip freeze > $REQUIREMENTS_FILE

echo "4. Загрузка всех пакетов и их зависимостей в каталог $DOWNLOAD_DIR..."
# Загрузка локальных копий пакетов
pip download \
  --dest $DOWNLOAD_DIR \
  -r $REQUIREMENTS_FILE \
  --progress

echo "5. Деактивация виртуального окружения."
deactivate

echo "✅ Бэкап завершен."
echo "   Пакеты сохранены в каталоге: ./$DOWNLOAD_DIR"
echo "   Список пакетов: ./$REQUIREMENTS_FILE"

#exec bash' 


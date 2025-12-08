#!/bin/bash
# Определяем текущую директорию
CURRENT_DIRECTORY=$(pwd)
SOURCE_DIRECTORY="$CURRENT_DIRECTORY/Project"
TARGET_ARCHIVE="$CURRENT_DIRECTORY/Project.tar"

# Проверяем существование источника
if [ ! -d "$SOURCE_DIRECTORY" ]; then
  echo "Директория $SOURCE_DIRECTORY не найдена."
  exit 1
fi

# Переходим в родительскую директорию Project
cd "$CURRENT_DIRECTORY" || exit 1

# --- 1. Поиск .py файлов для включения и создание списка файлов ---

# Создаем временный файл для хранения списка файлов
FILES_LIST=$(mktemp)

# Записываем все найденные .py файлы (Project/файл.py) в список FILES_LIST
find "$SOURCE_DIRECTORY" -type f -name "*.py" -print > "$FILES_LIST"

# Читаем количество найденных файлов для вывода
PY_FILE_COUNT=$(wc -l < "$FILES_LIST")

if [ "$PY_FILE_COUNT" -eq 0 ]; then
  echo "Нет .py файлов для архивации в $SOURCE_DIRECTORY!"
  rm -f "$FILES_LIST"
  exit 1
fi

echo "Найдено .py файлов: $PY_FILE_COUNT"

# --- 2. Логика архивации/обновления ---

if [ ! -f "$TARGET_ARCHIVE" ]; then
  # Если архив не существует, создаем его, используя список из файла
  echo "Создание нового архива $TARGET_ARCHIVE..."
  tar -cvf "$TARGET_ARCHIVE" -T "$FILES_LIST"
else
  echo "Обновление существующего архива $TARGET_ARCHIVE..."

  # 2.1 Удаляем старые версии .py файлов из архива (требует tar --delete)
  # Для этого нужно передать список файлов, которые нужно удалить.
  tar --delete -f "$TARGET_ARCHIVE" -T "$FILES_LIST" 2>/dev/null

  # 2.2 Добавляем обновленные .py файлы
  # Используем -rf для добавления к существующему архиву
  tar -rf "$TARGET_ARCHIVE" -T "$FILES_LIST"
fi

# --- 3. Проверка результата ---
if [ $? -eq 0 ]; then
  echo "Архивирование завершено успешно. Обновлены файлы (всего $PY_FILE_COUNT):"
  # Выводим первые 10 файлов из списка для проверки
  head -n 10 "$FILES_LIST" | sed 's/^Project\///'
  # ... и показываем, что это не полный список
  if [ "$PY_FILE_COUNT" -gt 10 ]; then
    echo "... (и еще $((PY_FILE_COUNT - 10)) файлов)"
  fi
else
  echo "Ошибка при обновлении архива!"
  rm -f "$FILES_LIST"
  exit 1
fi

# Очистка: удаляем временный файл со списком
rm -f "$FILES_LIST"
exit 0

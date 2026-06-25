#!/bin/bash

# Путь к исходной папке с документами
SOURCE_DIR=$(pwd)

# Путь к выходной папке для PDF документов
OUTPUT_DIR="/mnt/807EB5FA7EB5E954/развития/книги/наша книга/впадина марса/Том 16"

# Проверить, существует ли исходная папка
if [ ! -d "$SOURCE_DIR" ]; then
  echo "Исходная папка не найдена: $SOURCE_DIR"
  exit 1
fi

# Проверить, существует ли выходная папка, и создать её, если нет
if [ ! -d "$OUTPUT_DIR" ]; then
  mkdir -p "$OUTPUT_DIR"
fi

# Перебрать все файлы с расширением .doc в исходной папке
for DOC_FILE in "$SOURCE_DIR"/*.doc; do
  if [ -f "$DOC_FILE" ]; then
    # Преобразовать файл в PDF
    libreoffice --headless --convert-to pdf "$DOC_FILE" --outdir "$OUTPUT_DIR"
    if [ $? -eq 0 ]; then
      echo "Успешно преобразован: $DOC_FILE"
    else
      echo "Ошибка преобразования: $DOC_FILE"
    fi
  fi
done

echo "Все файлы были обработаны."

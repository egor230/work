#!/bin/bash

# Получаем текст из буфера обмена
text=$(copyq read 0)

# Проверяем, что текст не пустой
if [ -z "$text" ]; then
    echo "Ошибка: Буфер обмена пуст."
    exit 1
fi

# Экранируем специальные символы для RTF: \, {, }, и заменяем перенос строки на \par
rtf_text=$(echo "$text" | sed 's/\\/\\\\/g; s/{/\\{/g; s/}/\\}/g; s/\n/\\par /g')

# Формируем RTF-контент с размером шрифта 14 пунктов (\fs28) и кодировкой Windows-1251
rtf_content="{\\rtf1\\ansi\\ansicpg1251\\deff0\\deflang1049 {\\fonttbl{\\f0\\froman\\fcharset204 Times New Roman;}}\\viewkind4\\uc1\\pard\\lang1049\\f0\\fs28 ${rtf_text}\\par}"

# Сохраняем RTF-контент во временный файл для надежной передачи
temp_file=$(mktemp)
echo -n "$rtf_content" > "$temp_file"

# Отправляем данные в буфер обмена
copyq write text/plain "$text"
copyq write text/rtf - < "$temp_file"

# Удаляем временный файл
rm "$temp_file"

# Проверяем, что RTF записан в буфер обмена
rtf_check=$(copyq read text/rtf 0)
if [[ "$rtf_check" == *"\\fs28"* ]]; then
    echo "Текст успешно отформатирован в Times New Roman 14 и помещен в буфер обмена."
else
    echo "Ошибка: RTF не записан корректно."
    echo "Содержимое RTF: $rtf_check"
    exit 1
fi

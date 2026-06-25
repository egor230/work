import pyperclip  # Для получения пути из буфера обмена
import re        # Для разделения текста на предложения
import textwrap  # Для форматирования строк с шириной 80 символов

# Получаем путь к файлу из буфера обмена
file_path = str(pyperclip.paste())


def remove_duplicates(text):
 text = text.replace("[музыка]", "").replace("[аплодисменты]", "")
 lines = text.split("\n")
 result_lines = []
 prev_line = None
 
 for line in lines:
  # Пропускаем пустые строки
  if line == '':
   continue
  # Проверяем на дубликаты непустых строк
  if line != prev_line:
   result_lines.append(line)
   prev_line = line
 
 # print(result_lines)
 # input()
 return " ".join(result_lines)


# Читаем текст из файла
try:
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
except FileNotFoundError:
    print(f"Файл не найден: {file_path}")
    exit(1)

# Убираем лишние кавычки из текста
text = text.replace('"', '')

# Разделяем текст на предложения
# Используем регулярное выражение: разбиваем по пробелу после точки, восклицательного или вопросительного знака
sentences = re.split(r'(?<=[.!?])\s+', text.strip())
# sentences= remove_duplicates(str(sentences))
# Группируем предложения в абзацы по 7 штук
paragraphs = []
for i in range(0, len(sentences), 7):
    # Объединяем до 7 предложений в один абзац
    paragraph = ' '.join(sentences[i:i + 7])
    paragraphs.append(paragraph)

# Форматируем каждый абзац с шириной строки 80 символов
formatted_paragraphs = []
for paragraph in paragraphs:
    # textwrap.wrap разбивает текст на строки длиной не более 80 символов
    wrapped_lines = textwrap.wrap(paragraph, width=80)
    # Объединяем строки в абзац с переносами
    formatted_paragraphs.append('\n'.join(wrapped_lines))

# Объединяем абзацы с двойным переносом строки и выводим результат
formatted_text = '\n\n'.join(formatted_paragraphs)
print(formatted_text)

# Опционально: сохраняем результат в новый файл
# with open(file_path, 'w', encoding='utf-8') as file:
#     file.write(formatted_text)
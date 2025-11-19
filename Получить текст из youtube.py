import os, re, subprocess, pyperclip
from itertools import zip_longest

def remove_duplicates(text):
 lines = text.split("\n")
 result_lines = []
 prev_line = None
 for line in lines:
  # Пропускаем пустые строки
  if line.strip() == '':
   continue
  # Проверяем на дубликаты непустых строк
  if line.strip() != prev_line:
   result_lines.append(line.strip())
   prev_line = line.strip()
 return "\n".join(result_lines)

def clean_text(content): # Если content это список, объединяем в строку
 if isinstance(content, list):
  content = " ".join(content)
 # Регулярное выражение для удаления временных меток SRT
 clean_content = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n.*?\n', '', content)
 # Удаляем теги </c>
 clean_content = re.sub(r'</c>', '', clean_content)
 # Удаляем временные метки в формате [00:00:00]
 pattern = r'\[\d{2}:\d{2}:\d{2}\]'
 clean_content = re.sub(pattern, '', clean_content)
 
 # Удаляем специальные обозначения
 clean_content = clean_content.replace("[музыка]", "").replace("[аплодисменты]", "").replace("[Music]", "").replace("[Applause]", "")
 
 # Удаляем дубликаты строк
 clean_content = remove_duplicates(clean_content)
 return clean_content
def format_text(text, sentences_per_paragraph=7, max_line_length=120):
 # 1. Очистка текста и надежное разделение на предложения
 # Убираем множественные пробелы и переносы
 text = re.sub(r'\s+', ' ', text.strip())
 # Разделяем текст, сохраняя знаки препинания (. ! ?), чтобы
 # гарантировать, что каждое предложение завершено
 parts = re.split(r'([.!?])', text)
 sentences = []
 temp_sentence = ""
 for part in parts:
  if part.strip():   # Если это знак препинания, завершаем текущее предложение
   if part.strip() in ['.', '!', '?']:
    temp_sentence += part.strip()
    sentences.append(temp_sentence.strip())
    temp_sentence = ""
   # Если это текст, добавляем его. Добавляем пробел перед ним,
   # если это не начало временного предложения.
   else:
    if temp_sentence and not temp_sentence.endswith(' '):
     temp_sentence += ' '
    temp_sentence += part.strip()
 
 # Добавляем оставшуюся часть, если она есть
 if temp_sentence.strip():
  sentences.append(temp_sentence.strip())
 
 if not sentences:
  return '' # 2. Группируем в абзацы и форматируем линии (перенос только по предложениям)
 paragraphs_output = []
 for i in range(0, len(sentences), sentences_per_paragraph):
  # Группируем предложения для текущего абзаца
  paragraph_sentences = sentences[i:i + sentences_per_paragraph]
  lines = []
  current_line = ''
  for sent in paragraph_sentences: # Проверяем, поместится ли предложение в текущую строку
   # Добавляем пробел только если строка current_line не пуста
   new_line = current_line + (' ' if current_line else '') + sent
   if len(new_line) <= max_line_length:
    # Предложение помещается, обновляем текущую строку
    current_line = new_line
   else:
    # 1. Завершаем предыдущую строку
    if current_line:
     lines.append(current_line)
    # 2. Текущее предложение начинает новую строку.
    current_line = sent
  # Добавляем последнюю незавершенную строку абзаца
  if current_line:
   lines.append(current_line)
  paragraphs_output.append('\n'.join(lines))
 return '\n\n'.join(paragraphs_output)

# Получаем текст из буфера обмена
clipboard_text = str(pyperclip.paste()).strip()

# Если буфер обмена пуст, используем тестовый текст
if not clipboard_text:
 print("Буфер обмена пуст. Используйте текст из файла субтитров.")
 exit()

# Очищаем текст
cleaned_text = clean_text(clipboard_text)

if not cleaned_text:
 print("Не удалось обработать текст")
 exit()

# Форматируем текст (7 предложений в абзаце, максимальная длина строки 120 символов)
formatted_text = format_text(cleaned_text, sentences_per_paragraph=7, max_line_length=140)

# Сохранение текста в файл
new_file_path = 'Текст из youtube ролика.txt'

try:
 with open(new_file_path, "w", encoding="utf-8") as file:
  file.write(formatted_text)
  subprocess.call(["xdg-open", new_file_path])
except Exception as e:
 print(f"Ошибка при сохранении файла: {e}")
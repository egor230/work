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

def clean_text(content):
 # Если content это список, объединяем в строку
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
 # Убираем лишние пробелы и переносы строк
 text = re.sub(r'\s+', ' ', text.strip())
 
 # Разбиваем текст на предложения
 sentences = re.split(r'(?<=[.!?])\s+', text)
 
 # Фильтруем пустые предложения и очищаем от лишних знаков
 clean_sentences = []
 for sentence in sentences:
  sentence = sentence.strip()
  if sentence:
   # Убираем лишние знаки препинания в конце
   sentence = re.sub(r'[.!?]+$', '', sentence)
   # Добавляем только одну точку в конце
   sentence = sentence.strip() + '.'
   clean_sentences.append(sentence)
 
 if not clean_sentences:
  return ""
 
 # Группируем предложения в абзацы
 paragraphs = []
 for i in range(0, len(clean_sentences), sentences_per_paragraph):
  paragraph_sentences = clean_sentences[i:i + sentences_per_paragraph]
  # Объединяем предложения в абзац
  paragraph = ' '.join(paragraph_sentences)
  
  # Разбиваем длинные строки на более короткие
  if len(paragraph) > max_line_length:
   words = paragraph.split()
   lines = []
   current_line = ""
   
   for word in words:
    if len(current_line + " " + word) <= max_line_length:
     if current_line:
      current_line += " " + word
     else:
      current_line = word
    else:
     if current_line:
      lines.append(current_line)
     current_line = word
   
   if current_line:
    lines.append(current_line)
   
   paragraph = '\n'.join(lines)
  else:
   # Добавляем точку в конце абзаца, если её нет
   if paragraph and not paragraph.endswith('.'):
    paragraph += '.'
  
  paragraphs.append(paragraph)
 
 # Объединяем абзацы с двумя переносами строк между ними
 return '\n\n'.join(paragraphs)

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
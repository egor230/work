import os
import re
from docx import Document

def main():
  output = "16 том.docx"
  
  # Получаем список всех файлов в текущей папке
  all_files = os.listdir('.')
  
  # Фильтруем файлы: ищем только .docx, которые не являются итоговым файлом
  # Используем регулярку, чтобы игнорировать возможные проблемы с кодировкой пробелов
  files = [f for f in all_files if f.endswith('.docx') and f != output]
  
  # Сортируем список
  files.sort()
  
  if not files:
    print("Файлы .docx не найдены.")
    return
  
  final = Document()
  
  for fname in files:
    print(f"Обработка: {fname}...")
    try:
      # Используем имя файла как есть, но убеждаемся, что работаем в текущей папке
      src = Document(fname)
      for element in src.element.body:
        # Пропускаем настройки разделов, чтобы избежать поломки структуры
        if element.tag.endswith('sectPr'):
          continue
        final.element.body.append(element)
      final.add_page_break()
    except Exception as e:
      print(f"Ошибка при обработке {fname}: {e}")
  
  final.save(output)
  print(f"\nГотово! Результат сохранен в {output}")

if __name__ == "__main__":
  main()
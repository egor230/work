import re
from pathlib import Path


def split_text_into_groups(file_path, group_size=5):
  # Пробуем разные кодировки для русского текста
  encodings = ['utf-8', 'cp1251', 'koi8-r', 'iso-8859-5']

  for encoding in encodings:
    try:
      text = Path(file_path).read_text(encoding=encoding)
      break
    except UnicodeDecodeError:
      continue
  else:
    raise ValueError("Не удалось определить кодировку файла")

  # Улучшенное разделение на предложения с помощью регулярки
  sentences = re.findall(r'[^.!?]+[.!?]', text)

  # Фильтрация пустых элементов
  sentences = [s.strip() for s in sentences if s.strip()]

  # Группировка по 5 предложений
  groups = [sentences[i:i + group_size] for i in range(0, len(sentences), group_size)]

  return groups


if __name__ == "__main__":
  file_path = "/mnt/807EB5FA7EB5E954/работа/От Николая/dusha-v-trotilovom-ekvivalente.txt"

  try:
    groups = split_text_into_groups(file_path,10)

    # Вывод групп с нумерацией
    for i, group in enumerate(groups, 1):
      print(f"\nОтрывок {i}:")
      for sentence in group:
        print(f" {sentence}")

  except Exception as e:
    print(f"Ошибка: {str(e)}")
    print("Попробуйте следующие решения:")
    print("1. Установите chardet: pip install chardet")
    print("2. Проверьте путь к файлу и права доступа")
    print("3. Укажите явно кодировку если знаете её")
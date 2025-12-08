from bs4 import BeautifulSoup


def get_classes_and_ids(html_content):
 soup = BeautifulSoup(html_content, 'html.parser')
 classes = set()
 ids = set()
 element_classes = []
 
 for element in soup.find_all(class_=True):
  classes.update(element.get('class', []))
  element_classes.append((element.name, element.get('class', [])))
 
 for element in soup.find_all(id=True):
  ids.add(element.get('id'))
 
 return classes, ids, element_classes


def compare_html_files(old_file_path, new_file_path):
 try:
  with open(old_file_path, 'r', encoding='utf-8') as f:
   old_content = f.read()
  with open(new_file_path, 'r', encoding='utf-8') as f:
   new_content = f.read()
 except UnicodeDecodeError:
  print("Ошибка: Проблема с кодировкой файлов. Убедитесь, что оба файла в UTF-8.")
  return set(), set(), []
 
 old_classes, old_ids, old_element_classes = get_classes_and_ids(old_content)
 new_classes, new_ids, new_element_classes = get_classes_and_ids(new_content)
 
 print(f"\nОбщее количество классов в старом файле: {len(old_classes)}")
 print(f"Общее количество классов в новом файле: {len(new_classes)}")
 print(f"Общее количество ID в старом файле: {len(old_ids)}")
 print(f"Общее количество ID в новом файле: {len(new_ids)}")
 
 new_unique_classes = new_classes - old_classes
 new_unique_ids = new_ids - old_ids
 
 class_changes = []
 for i, (old_elem, new_elem) in enumerate(zip(old_element_classes, new_element_classes)):
  if old_elem[0] == new_elem[0]:
   old_class_set = set(old_elem[1])
   new_class_set = set(new_elem[1])
   if old_class_set != new_class_set:
    replaced = old_class_set - new_class_set
    added = new_class_set - old_class_set
    if replaced or added:
     class_changes.append((i, old_elem[0], replaced, added))
 return new_unique_classes, new_unique_ids, class_changes

old_file = 'old_page_source.txt'
new_file = 'page_source.txt'
try:
 new_classes, new_ids, class_changes = compare_html_files(old_file, new_file)
 
 print("\nНовые классы, которых нет в старом файле:")
 if new_classes:
  for class_name in sorted(new_classes):
   print(f"- {class_name}")
 else:
  print("Новых классов не найдено")
 
 # print("\nНовые ID, которых нет в старом файле:")
 # if new_ids:
 #  for id_name in sorted(new_ids):
 #   print(f"- {id_name}")
 # else:
 #  print("Новых ID не найдено")
 
 print("\nЗамены классов в элементах:")
 if class_changes:
  for index, tag, replaced, added in class_changes:
   # print(f"Элемент {tag} (позиция {index}):")
   if replaced:
    print(f"  Удалены классы: {', '.join(sorted(replaced))}")
   if added:
    print(f"  Добавлены классы: {', '.join(sorted(added))}")
 # else:
 #  print("Замен классов не найдено")

except FileNotFoundError as e:
 print(f"Ошибка: Один из файлов не найден - {e}")
except Exception as e:
 print(f"Произошла ошибка: {e}")
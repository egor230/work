import os, subprocess, sys, time, pyperclip, requests, threading
from datetime import datetime
import requests

def save_image_from_clipboard():
 try:
  url = subprocess.check_output(["copyq", "read", "text/plain"], text=True).strip()
  if not url.startswith("http"):
   print("В буфере не ссылка:", url)
   return

  now = datetime.now()
  base_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/Screenshots"
  filename = f"{base_path}/{now:%H %M %S %Y-%m-%d}.png"
  os.makedirs(base_path, exist_ok=True)
  # Скрипт для помещения изображения в буфер обмена через copyq
  show_list_id = '''#!/bin/bash
     xclip -selection clipboard -t image/png -i "{0}" # Помещаем изображение в буфер обмена
     sleep 2.9
     copyq select 0'''.format(filename)

  subprocess.run(['bash', '-c', show_list_id])
  time.sleep(0.1)

  # if os.path.exists(filename):
  #  print("Файл уже существует")
  #  return

  # print("Скачиваю:", url)
  #
  # headers = {
  #  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  #  "Accept": "image/avif,image/webp,*/*",
  #  "Referer": "https://www.google.com/"  # иногда очень помогает
  # }
  #
  # r = requests.get(url, headers=headers, timeout=12, verify=False)
  # r.raise_for_status()
  #
  # with open(filename, "wb") as f:
  #  f.write(r.content)
  #
  # print("Сохранено:", filename)

 except subprocess.CalledProcessError:
  print("CopyQ не отвечает")
 except requests.exceptions.RequestException as e:
  print("Ошибка загрузки:", str(e))
 except Exception as e:
  print("Ошибка:", str(e))

save_image_from_clipboard()
def quit_script():
  result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # print(result)
  name_scrypt = sys.argv[0] # Вызываем скрипт
  i = 0
  try:
   for line in result.split("\n"):
    process_name = ' '.join(line.split()[10:])
    if name_scrypt in process_name:
     i = i + 1
     if i == 2:
      sys.exit(0)
      break
  except:
    pass

# quit_script()
url=str(pyperclip.paste()) #copy(text)get_paths_file()
print(url)
# url = "https://preview.reve.art/api/project/fc228c34-3790-4941-b5a6-0448606676b0/image/6ca950be-cbac-4944-8c35-78e164bf7ff2/url/filename/6ca950be-cbac-4944-8c35-78e164bf7ff2?fit=contain&width=512log/zamknutost2"
if len(url) == 0:
    sys.exit(0)

# if "reve" in url:
#   # Получаем текущую дату для имени файла
#   current_date = datetime.now().strftime("%Y-%m-%d")
#   print(current_date)
#   # Извлекаем имя файла из URL
#   base_filename = os.path.basename(url)
#
#   # Указываем путь для сохранения файла
#   filename = f"/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Screenshots/{current_date}-{base_filename}.webp"
#   try:
#    print(filename)
#    # Скачиваем файл
#    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
#    response = requests.get(url, headers=headers, stream=True)
#
#    if response.status_code == 200:
#     with open(filename, 'wb') as file:
#       for chunk in response.iter_content(1024):
#         file.write(chunk)
#       print(f"Изображение успешно скачано и сохранено в {filename}.")
#    else:
#      print(response.status_code)
#   except Exception as e:
#    print(e)
#
# input()
#with open("ссылки.txt", 'a', encoding='utf-8') as file:
#  # Записываем строку и переходим на новую строку
#  file.write(url + '\n')
if url.startswith("http") and not os.path.exists(url):
  script = f'''#!/bin/bash
  gnome-terminal -- bash -c '
  now=$(date +"%F %T")   # Получить текущую дату/время
  current_date=$(date +"%F")
  hours=$(date +"%H") # Разбить на отдельные элементы
  minutes=$(date +"%M")
  seconds=$(date +"%S")  # Сформировать имя файла
  filename="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/Screenshots/${{hours}} ${{minutes}} ${{seconds}} ${{current_date}}.png"
  if [ ! -f "$filename" ]; then    # Он пуст  
   if curl -L -o "$filename" "{url}" --retry 3 --retry-delay 1 --fail -k; then # Скачиваем изображение
    sleep 2.4 
    convert "$filename" -resize 512x512 "$filename"  
    xclip -selection clipboard -t image/png -i "$filename"
    sleep 1.9 
    copyq select 0
  else
    echo "Error downloading file '$filename'."
  fi
  fi'
  '''
  subprocess.run(['bash', '-c', script])
  time.sleep(0.1)#
  sys.exit(0)
t=['.PNG', '.JPG','.JPEG','.BMP','.png', '.jpg','.jpeg','.bmp']
_, ext = os.path.splitext(url)
if "/mnt" in url and ext.lower() in t and os.path.exists(url):#  print(url)
  show_list_id = f'''#!/bin/bash
    xclip -selection clipboard -t image/png -i $"{url}" # Помещаем изображение в буфер обмена
    sleep 1.9
    copyq select 0  '''
  subprocess.run(['bash', '-c', show_list_id])
#   sys.exit(0)
# url ="https://avatars.mds.yandex.net/i?id=e5061532fa53b0201f220571db878486-4988848-images-thumbs&n=13"


# print(url)
# time.sleep(3)
# with open("test buff.txt", 'w') as file:  # Записываем текст в файл
#   file.write(url)

import time, json, os,  subprocess, psutil, pyperclip, sys, re, io
from os import path

import pytesseract
# Загрузите изображение с использованием PIL
from PIL import Image, ImageFilter, ImageEnhance
import Gtk

clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

# Функция обратного вызова для получения содержимого
def on_image_received(clipboard, image):
    if image:
        image.savev('clipboard_image.png', 'png', [], [])
    else:
        print('Изображение не найдено')

def on_text_received(clipboard, text):
    if text:
        with open('clipboard_text.html', 'w') as f:
            f.write(text)
    else:
        print('Текст не найден')

# Запрос содержимого буфера обмена
clipboard.request_image(on_image_received)
clipboard.request_text(on_text_received)

# Запуск цикла обработки событий


Gtk.main()

# # Получить данные изображения из буфера обмена
# p = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-o'], stdout=subprocess.PIPE)
# image_data, _ = p.communicate()
#
# # Преобразовать данные в изображение
# image = Image.open(io.BytesIO(image_data))
# image.save('clipboard_image.png')
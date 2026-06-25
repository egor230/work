import os
import time

import cv2
import pytesseract
import pyperclip
import numpy as np
import subprocess
import easyocr
from PIL import Image


def text_recognition(file_path):
  reader = easyocr.Reader(["ru", "en"])
  img = Image.open(file_path)
  img_rgb = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)
  result = reader.readtext(img_rgb, detail=0, batch_size=1)
  return result
# Получаем изображение из буфера обмена
# Команда для сохранения изображения из буфера обмена
cmd = "xclip -selection clipboard -t image/png -o > /tmp/screenshot.png"
temp_file_path = "/tmp/screenshot.png"
text = text_recognition(temp_file_path)
if os.path.exists(temp_file_path):
    os.remove(temp_file_path)
# Выполнение команды
p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
time.sleep(1)
img = Image.open(temp_file_path)
temp_file_path = img.resize((img.width // 2, img.height // 2))
print("text")
# Используем pytesseract для распознавания текста на изображении
text = pytesseract.image_to_string(temp_file_path, lang="eng+rus")
# Отправляем распознанный текст в буфер обмена
pyperclip.copy(text)


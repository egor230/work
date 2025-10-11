from write_text import *
from faster_whisper import WhisperModel
import os, sys
import tkinter as tk
from tkinter import Frame, Label
cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/whisper/"# Путь к модели
model_size = "large-v3"
model_dir = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_size}", "snapshots")
if not os.path.exists(model_dir):# Проверка существования папки snapshots
    print(f"Ошибка: Папка snapshots не найдена: {model_dir}. Убедитесь, что модель скачана.")
    sys.exit(1)

# Поиск первого snapshot
snapshot = next((d for d in os.listdir(model_dir) if os.path.isdir(os.path.join(model_dir, d))), None)
if not snapshot:
    print("Ошибка: Нет snapshots в кэше. Скачайте модель заново.")
    sys.exit(1)

# Путь к модели и проверка model.bin
model_path = os.path.join(model_dir, snapshot)
if not os.path.exists(os.path.join(model_path, "model.bin")):
    print(f"Ошибка: Файл model.bin не найден в {model_path}")
    sys.exit(1)

# Загрузка модели
try:
    model = WhisperModel(model_path, device="cpu", compute_type="int8")
    print("Модель загружена успешно.")
except Exception as e:
    print(f"Ошибка загрузки модели: {e}")
    sys.exit(1)

def record_audio(duration=8, fs=44100):# Запись аудио с микрофона
  print("star...")
  recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
  sd.wait()
  audio_file = "temp.wav"
  write(audio_file, fs, recording)
  print(f"Запись завершена, файл сохранён как {audio_file}")

def audio(model): # Путь к аудиофайлу
 try:
   audio_file = "temp.wav"
   segments, info = model.transcribe( audio_file, beam_size=4, language="ru" ) # Только русский
   message_parts = []
   for segment in segments:
    text = segment.text.strip()
    if text:  # Проверяем, что строка не пустая
     message_parts.append(text)
   message = ' '.join(message_parts)
   # На всякий случай принудительно кодируем-раскодируем:
   # message = str(message)
   return message
 except Exception as e:
  print(e)
  pass
 # thread = threading.Thread(target=process_text, args=(message, k))
 # thread.start()
 # thread.join()

def update_label(label):
  try:
    mic_on = True
    if mic_on:
      label.config(text="Говорите...")
      thread = threading.Thread(target=record_audio)
      thread.start()
      thread.join()  # Ждем завершения записи
      label.config(text="Стоп")
      message = audio(model)  # Замените "model" на вашу модель
      if message:
          # message = repeat(message)
        print(f"Сообщение: {message}")нь
  except Exception as ex1:
      print(f"Ошибка: {ex1}")
  finally:
       # Планируем следующее обновление через 1 секунду
       root.after(1000, lambda: update_label(label))

# Создаем главное окно
root = tk.Tk()
frame = tk.Frame(root)
label = tk.Label(frame, text="...", font='Times 14', anchor="center")
label.pack(padx=3, fill=tk.X, expand=True)
frame.pack(fill=tk.X)

# Настройки окна
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)

# Запускаем периодическое обновление метки
root.after(1000, lambda: update_label(label))

# Запускаем главный цикл
root.mainloop()
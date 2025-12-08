import os
import torch
import soundfile as sf
import numpy as np
from transformers import AutoModelForCTC, AutoProcessor

# Путь к директории, где хранится модель
model_dir = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache/models--t-tech--T-one/snapshots/24e33e99601ff73559a759415b57f120e9034a28"

def load_audio(file_path):
 try:
  audio, sample_rate = sf.read(file_path)
  # Если аудио стерео, конвертируем в моно
  if len(audio.shape) > 1:
   audio = audio.mean(axis=1)
  # Если sample_rate не 16kHz, нужно ресемплировать (для простоты предполагаем 16kHz)
  return audio
 except Exception as e:
  print(f"Ошибка при загрузке аудио: {e}")
  return None


def transcribe_audio(audio_file_path):
 try:
  # Загрузка модели и процессора
  print("Загрузка модели...")
  processor = AutoProcessor.from_pretrained(model_dir)
  model = AutoModelForCTC.from_pretrained(model_dir)
  print("Модель загружена успешно")
  
  # Загрузка аудио
  print("Загрузка аудио файла...")
  audio = load_audio(audio_file_path)
  if audio is None:
   return None
  
  # Предобработка аудио
  print("Предобработка аудио...")
  input_values = processor(audio, sampling_rate=16000, return_tensors="pt", padding="longest").input_values
  
  # Распознавание
  print("Распознавание речи...")
  with torch.no_grad():
   logits = model(input_values).logits
  
  # Декодирование
  predicted_ids = torch.argmax(logits, dim=-1)
  transcription = processor.batch_decode(predicted_ids)
  
  return transcription[0]
 
 except Exception as e:
  print(f"Ошибка при распознавании: {e}")
  return None


# Пример использования
if __name__ == "__main__":
 # Укажите путь к вашему аудио файлу (должен быть в формате WAV, 16kHz, моно)
 audio_file = "12_02_04_11_09_2025.wav"  # Замените на путь к вашему файлу
 
 if os.path.exists(audio_file):
  result = transcribe_audio(audio_file)
  if result:
   print(f"Распознанный текст: {result}")
  else:
   print("Не удалось распознать речь")
 else:
  print(f"Файл {audio_file} не найден")

print("Модель успешно загружена из указанной директории.")

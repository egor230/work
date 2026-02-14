import os
import time
import sounddevice as sd
import numpy as np
import wave
from pathlib import Path
import logging
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
MODEL_ID = "mistralai/Voxtral-Mini-3B-2507"
FILENAME = "consolidated.safetensors"
CACHE_DIR = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
AUDIO_PATH = CACHE_DIR / "recorded_audio.wav"
RECORD_SECONDS = 10
SAMPLE_RATE = 16000
CHANNELS = 1

# Создаем кэш-директорию
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Глобальные переменные для модели и токенизатора
model = None
tokenizer = None

def check_and_load_model():
    """Проверяет и загружает модель только если она еще не загружена"""
    global model, tokenizer

    print("Проверка и загрузка модели Voxtral...")

    try:
        # Проверяем наличие модели в кэше
        model_path = hf_hub_download(
            repo_id=MODEL_ID,
            filename=FILENAME,
            cache_dir=str(CACHE_DIR),
            local_files_only=True  # Только проверка без скачивания
        )
        print(f"Модель найдена в кэше: {model_path}")
    except Exception as e:
        logger.error(f"Модель не найдена в кэше! Скачивание модели: {e}")
        # Скачиваем модель, если она не найдена в кэше
        model_path = hf_hub_download(
            repo_id=MODEL_ID,
            filename=FILENAME,
            cache_dir=str(CACHE_DIR)
        )
        print(f"Модель скачана и сохранена в кэше: {model_path}")

    # Загружаем модель и токенизатор
    start_time = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, cache_dir=str(CACHE_DIR))
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, cache_dir=str(CACHE_DIR))

    print(f"Модель успешно загружена за {time.time() - start_time:.2f} сек")

    return model, tokenizer

def record_audio(output_path, duration=RECORD_SECONDS, samplerate=SAMPLE_RATE):
    """Записывает аудио с микрофона"""
    print(f"Запись аудио ({duration} сек)...")

    try:
        audio_data = sd.rec(
            int(duration * samplerate),
            samplerate=samplerate,
            channels=CHANNELS,
            dtype='int16'
        )
        sd.wait()

        with wave.open(str(output_path), 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            wf.writeframes(audio_data.tobytes())

        print(f"Аудио сохранено в {output_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка записи аудио: {e}")
        return False

def transcribe_with_voxtral(audio_file_path):
    """Транскрибирует аудио с помощью Voxtral"""
    global model, tokenizer

    try:
        # Здесь должна быть ваша логика преобразования аудио в текст
        # Для модели Voxtral. В текущей реализации Voxtral не является ASR моделью,
        # поэтому вам нужно добавить либо:
        # 1. Отдельный ASR модуль перед Voxtral
        # 2. Или преобразование аудио в текст другим способом

        # Примерный код (требует доработки под ваш конкретный случай):
        prompt = "Транскрибируй следующее аудио: " + str(audio_file_path)

        inputs = tokenizer(prompt, return_tensors="pt")
        outputs = model.generate(**inputs, max_new_tokens=200)

        transcription = tokenizer.decode(outputs[0], skip_special_tokens=True)

        print("Распознавание завершено")
        return transcription
    except Exception as e:
        logger.error(f"Ошибка распознавания: {e}")
        return None

def main():
  """Основной рабочий цикл"""
  global model, tokenizer

  while True:
      print("\n" + "="*50)
      print("1. Записать и обработать аудио (20 сек)")

      # Записываем аудио
      if record_audio(AUDIO_PATH):
          # Проверяем и загружаем модель
          model, tokenizer = check_and_load_model()

          # Обрабатываем аудио
          result = transcribe_with_voxtral(AUDIO_PATH)

          if result:
              print("\nРезультат обработки:")
              print("-"*50)
              print(result)
              print("-"*50)
              break
          else:
              print("Не удалось обработать аудио")
              break

if __name__ == "__main__":
    main()

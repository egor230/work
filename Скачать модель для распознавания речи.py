from huggingface_hub import snapshot_download

import os, subprocess, torch, shutil, gigaam, tempfile, torchaudio, time
from pathlib import Path

# # Настройка директории кэша
# cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
# cache_dir.mkdir(parents=True, exist_ok=True)
# os.environ["XDG_CACHE_HOME"] = str(cache_dir)
#folder_path = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache/gigaam/")
import gigaam
import os
from pathlib import Path
import os, subprocess, torch, shutil, gigaam, tempfile, torchaudio, time
# Укажите вашу папку для кэша моделей
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)

# Устанавливаем переменные окружения до импорта gigaam
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)

# Устанавливаем переменные окружения для кэширования
os.environ["TORCH_HOME"] = str(cache_dir / "gigaam")
os.environ["XDG_CACHE_HOME"] =  str(cache_dir / "gigaam")
os.environ["GIGAAM_CACHE_DIR"] = str(cache_dir / "gigaam")  # Пробуем кастомную переменную

os.environ["CACHE_DIR"] =  str(cache_dir / "gigaam")
# Настройка потоков для PyTorch
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"
torch.set_num_threads(8)
try:
    # Загрузка модели
    model = gigaam.load_model("v2_rnnt")  # или просто "rnnt", если v2 — версия по умолчанию

    # Путь к аудиофайлу
    audio_path = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/12_02_04_11_09_2025.wav"

    # Распознавание речи
    transcription = model.transcribe(audio_path)

    # Вывод результата
    print("Распознанный текст:", transcription)
except Exception as e:
    print(f"Ошибка распознавания: {e}")

# convert_final.py — 100% рабочий вариант
import subprocess
import sys
import os
from pathlib import Path

SOURCE_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/podlodka_model"
OUTPUT_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/podlodka_model_ct2"

# Удаляем старую папку если есть
if os.path.exists(OUTPUT_DIR):
    print(f"Удаляю старую папку: {OUTPUT_DIR}")
    os.system(f"rm -rf '{OUTPUT_DIR}'")

print("Запускаю конвертацию в faster-whisper (CTranslate2) формат...")
print("Это займёт 2–7 минут, смотри прогресс ниже ↓\n")

# Самая надёжная команда — официальная из документации faster-whisper
cmd = f"""
ct2-transformers-converter \
  --model "{SOURCE_DIR}" \
  --output_dir "{OUTPUT_DIR}" \
  --copy_files tokenizer.json \
  --quantization int8_float16 \
  --force
""".strip()

# Запускаем и показываем ВЕСЬ вывод в режиме реального времени
result = os.system(cmd)

if result == 0:
    print("\nГОТОВО! Модель сконвертирована.")
    print(f"Папка: {OUTPUT_DIR}")
    print("\nТеперь используй так (самый короткий код):")

else:
    print("\nОшибка конвертации! Убедитесь, что установлен ctranslate2:")
    print("pip install ctranslate2 transformers[torch]")
    sys.exit(1)
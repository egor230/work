import json
import sys
import os
from typing import List, Tuple

# ------------------- НАСТРОЙКИ -------------------
# Используем Qwen2.5 14B GGUF через ModelScope
MODEL_DISPLAY_NAME = "qwen2.5:14b"
MODELSCOPE_MODEL_ID = "qwen/Qwen2.5-14B-Instruct-GGUF"
GGUF_FILENAME = "qwen2.5-14b-instruct-q4_k_m.gguf"  # подберите нужный квантизатор

# Пути (оставлены как у вас)
REPLACEMENTS_PATH = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/list for replacements.json"
CACHE_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/"
MODELS_DIR = os.path.join(CACHE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# ------------------- ЗАГРУЗКА МОДЕЛИ ЧЕРЕЗ MODELSCOPE -------------------
def download_model() -> str:
    """Скачивает GGUF-файл из ModelScope в MODELS_DIR и возвращает полный путь."""
    model_path = os.path.join(MODELS_DIR, GGUF_FILENAME)
    if os.path.exists(model_path):
        print(f"✅ Модель уже существует: {model_path}")
        return model_path

    print(f"⚠️ Модель не найдена. Начинаю загрузку через ModelScope...")
    print(f"Репозиторий: {MODELSCOPE_MODEL_ID}, файл: {GGUF_FILENAME}")

    try:
        from modelscope.hub.file_download import model_file_download
        # model_file_download скачивает конкретный файл в кэш, возвращает локальный путь
        downloaded_path = model_file_download(
            model_id=MODELSCOPE_MODEL_ID,
            file_path=GGUF_FILENAME,
            cache_dir=MODELS_DIR,
            revision='master'   # можно указать нужную ветку/тег
        )
        # Проверяем, что файл скачался и скопируем/переместим в MODELS_DIR, если нужно
        # Но model_file_download уже сохраняет в подпапку кэша. Для простоты будем использовать его напрямую.
        print(f"✅ Модель загружена: {downloaded_path}")
        return downloaded_path
    except ImportError:
        print("❌ Модуль modelscope не установлен. Установите: pip install modelscope")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка загрузки модели через ModelScope: {e}")
        print("Проверьте название модели и файла. Доступные GGUF для Qwen: https://modelscope.cn/models?page=1&name=Qwen+GGUF")
        sys.exit(1)

# Инициализация модели
model_path = download_model()
print(f"Загружаю модель из {model_path}...")

try:
    from llama_cpp import Llama
    llm = Llama(
        model_path=model_path,
        n_ctx=4096,
        n_threads=8,       # подберите под ваш CPU
        verbose=False
    )
    print("✅ Модель загружена в память")
except ImportError:
    print("❌ llama-cpp-python не установлен. Установите: pip install llama-cpp-python")
    sys.exit(1)
except Exception as e:
    print(f"❌ Ошибка при загрузке модели в память: {e}")
    sys.exit(1)

# ------------------- ОСТАЛЬНОЙ КОД (без изменений) -------------------
def load_replacements() -> List[Tuple[str, str]]:
    """Загружает словарь замен из JSON."""
    try:
        with open(REPLACEMENTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return list(data.items())[:30]
        elif isinstance(data, list):
            return data[:30]
        return []
    except FileNotFoundError:
        print(f"⚠️ Файл {REPLACEMENTS_PATH} не найден. Работаем без замен.")
        return []
    except Exception as e:
        print(f"⚠️ Ошибка загрузки замен: {e}")
        return []

def get_correction_prompt(dirty_text: str, replacements: List[Tuple[str, str]]) -> str:
    prompt = """Ты — профессиональный корректор русского текста, специализирующийся на исправлении ошибок автоматического распознавания речи (ASR).

Пользователь отправляет текст, полученный из голосового ввода. В нём часто бывают фонетические ошибки, опечатки, неправильные предлоги, окончания и слитные слова.

Твоя задача: исправить все ошибки, сделать текст грамматически правильным и естественным, но максимально сохранить оригинальный смысл. 
Не перефразируй, не добавляй ничего от себя.

Правила:
- Исправляй только ошибки.
- Сохраняй имена, названия, цифры и термины без изменений.
- Выводи ТОЛЬКО исправленный текст. Без объяснений и комментариев.

"""
    if replacements:
        prompt += "\nПри исправлении обязательно учитывай следующие частые замены:\n"
        for wrong, correct in replacements[:15]:
            prompt += f'"{wrong}" → "{correct}"\n'
    prompt += f"\nТекст для исправления:\n{dirty_text}"
    return prompt

def correct_text(dirty_text: str) -> str:
    replacements = load_replacements()
    prompt = get_correction_prompt(dirty_text, replacements)

    try:
        response = llm(
            prompt,
            max_tokens=2048,
            temperature=0.2,
            stop=["</s>"],   # стоп-токен для Qwen
            echo=False
        )
        return response['choices'][0]['text'].strip()
    except Exception as e:
        print(f"Ошибка при обращении к модели: {e}")
        return dirty_text

# ------------------- ЗАПУСК -------------------
if __name__ == "__main__":
    print("=== Исправитель ошибок голосового ввода (Python) ===\n")
    print(f"Используется модель: {MODELSCOPE_MODEL_ID} / {GGUF_FILENAME}")
    print(f"Модель хранится в: {model_path}\n")

    while True:
        text = input("Введи текст с ошибками (или 'выход' для завершения):\n> ")
        if text.lower() in ["выход", "exit", "quit", "йцукен"]:
            break
        if not text.strip():
            continue

        print("\nИсправляю...")
        fixed = correct_text(text)

        print("\n✅ Исправленный текст:")
        print(fixed)
        print("-" * 70)
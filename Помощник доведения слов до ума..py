# Импорт необходимых библиотек
import sys
import os
import re
import contextlib

from llama_cpp import Llama

# Укажите путь к вашей модели
model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/model-q4_K.gguf"

# Загружаем модель один раз
llm = Llama(
    model_path=model_path,
    n_ctx=2048,
    n_threads=4,
    verbose=False
)

def fix_text(text: str) -> str:
    """Исправляет опечатки и грамматику в русском тексте. Возвращает ТОЛЬКО исправленный текст."""
    prompt = f"""[INST] Исправь ошибки в следующем русском тексте. Ответь строго одним предложением — только исправленный вариант, без пояснений, кавычек, скобок и лишних слов.

Текст: {text} [/INST]"""

    output = llm(
        prompt,
        max_tokens=256,
        temperature=0.0,        # детерминированный результат
        top_p=0.9,
        stop=["[/INST]", "</s>"]
    )
    return output["choices"][0]["text"].strip()

# Пример
if __name__ == "__main__":
    original = "како дала в питоне напесать фенкцию которай счатает hello world?"
    corrected = fix_text(original)
    print("Исправлено:", corrected)
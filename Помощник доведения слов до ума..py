# Импорт необходимых библиотек
import sys
import os
import re
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton
from PyQt5.QtCore import Qt
from llama_cpp import Llama
import contextlib

from llama_cpp import Llama  # Импорт для локальной модели (GGUF)

# Глобальная инициализация модели (загружается один раз при запуске скрипта)
model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/ollama/gemma-3-270m-it-F16.gguf"
llm = Llama(
  model_path=model_path,
  n_ctx=2048,  # Контекст (можно увеличить, если нужно)
  n_threads=4,  # Потоки CPU (адаптируй под свою машину)
  verbose=False  # Без лишнего лога
)


def generate_response(prompt):
  """
  Исправляет опечатки в русском предложении и возвращает только исправленный текст.
  """
  system_prompt = """Ты специалист по исправлению текста на русском языке. 
    Внимательно прочитай оригинальный вопрос и исправь все опечатки, грамматические ошибки и неправильное написание слов (например, "питон" → "Python", "како дала" → "как дела").
    Не добавляй ничего лишнего: только исправленный вариант текста.
    Формат ответа: [Исправленный текст: <твой исправленный вариант>]"""

  full_prompt = f"{system_prompt}\n\nОригинальный текст: {prompt}\n\n"

  try:
    output = llm(
      full_prompt,
      max_tokens=150,  # Достаточно для исправления текста
      temperature=0.1,  # Низкая температура для точности исправлений
      top_p=0.9,
      echo=False,
      stop=["[", "]"]  # Остановка на границах формата, чтобы не генерировать лишнее
    )
    raw_text = output['choices'][0]['text'].strip()

    # Постобработка: извлекаем только исправленный текст
    if "[Исправленный текст:" in raw_text:
      corrected = raw_text.split("[Исправленный текст:")[1].split("]")[0].strip()
    else:
      corrected = raw_text  # Fallback, если формат сломался

    return corrected
  except Exception as e:
    return f"Ошибка: {str(e)}"  # Или оригинальный промпт как fallback


# Пример использования (можно вызывать много раз — модель уже загружена)
if __name__ == "__main__":
  test_prompt = "како дала в питоне напесать фенкцию которай счатает hello world?"
  corrected = generate_response(test_prompt)
  print(corrected)  # Вывод: "Как дела в Python написать функцию которая считает hello world?" (или подобное)
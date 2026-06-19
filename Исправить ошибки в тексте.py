import json, sys, time, os
from typing import List, Tuple
from llama_cpp import Llama

# ================== НАСТРОЙКИ ==================
MODEL_PATH = "/mnt/807EB5FA7EB5E954/Program Files/ai models/mradermacher/gemma-4-E2B-it-heretic-GGUF/gemma-4-E2B-it-heretic.Q4_K_S.gguf"
# MMPROJ_PATH = "/mnt/807EB5FA7EB5E954/Program Files/ai models/lmstudio-community/gemma-4-E2B-it-GGUF/mmproj-gemma-4-E2B-it-BF16.gguf"

if not os.path.exists(MODEL_PATH):
 print("Нет модели:", MODEL_PATH)
 sys.exit(1)
t = time.time()
llm = Llama(
    model_path=MODEL_PATH,
    # mmproj=MMPROJ_PATH,  # 🔥 Оставь, только если реально используешь мультимодальность
    n_ctx=1024,          # ⬇️ Уменьши, если не нужен полный 4096. Экономит память и время старта
    n_threads=os.cpu_count() or 8,
    n_batch=512,         # Влияет на скорость обработки промпта, не на загрузку
    logits_all=False,
    verbose=False,
    use_mmap=True,       # 🔥 Ключевое для скорости загрузки. Включает memory mapping
    use_mlock=False,     # Лучше False: True блокирует память сразу и замедляет старт
)
prompt = """
Ты — продвинутый корректор текста с функцией восстановления смысла.

Твоя задача: максимально точно исправить текст, даже если он сильно искажен.

РАЗРЕШЕНО:
- заменять слова полностью, если они искажены
- исправлять фонетические ошибки (как при плохом распознавании речи)
- восстанавливать слова по контексту
- исправлять грамматику и орфографию
- менять форму слов (склонение, род, число)
- заменять бессмысленные фразы на осмысленные

ЗАПРЕЩЕНО:
- удалять смысл текста
- придумывать новый смысл, которого нет в оригинале

ПРАВИЛА:
1. Если слово похоже на другое по звучанию — исправь его:
   пример: "дея" → "дела"
2. Если фраза не имеет смысла — восстанови её по контексту
3. Исправляй регистр:
   вы → Вы, вам → Вам, ваш → Ваш
4. Исправляй имена и термины (с заглавной буквы)
5. Используй агрессивную коррекцию, если текст явно испорчен
6. Если сомневаешься — выбери наиболее вероятный вариант

ВАЖНО:
- НЕ сохраняй ошибочные слова, если они явно неправильные
- Приоритет: ЧИТАЕМОСТЬ и СМЫСЛ

Отвечай только исправленным текстом.
"""
def correct(text: str) -> str:
 if not text.strip():
  return text

 try:
  response = llm.create_chat_completion(
   messages=[
    {"role": "system", "content": prompt},
    {"role": "user", "content": text}
   ],
   max_tokens=256,
   temperature=0.0,
  )

  return response["choices"][0]["message"]["content"].strip()

 except Exception as e:
  print("Ошибка:", e)
  return text

# ================== ЗАПУСК ==================
if __name__ == "__main__":
 print("=== ASR Corrector (Gemma-4) ===\n")

 print(time.time() - t)
 while True:
  try:
   user_input = input("Текст > ")
  except:
   break

  if user_input.lower() in ["выход", "exit", "quit", "йцукен"]:
   break

  if not user_input.strip():
   continue

  print("→ Исправляю...")
  result = correct(user_input)
  print("✅", result)
  print("-" * 70)
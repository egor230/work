import os

# ← Диагностика: проверим, куда HF думает кэшировать
print("=== ДИАГНОСТИКА КЭША ===")
print("Твой MODEL_PATH:", "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache")
print("HF_HOME из env:", os.environ.get("HF_HOME", "НЕ ЗАДАН!"))
print("HUGGINGFACE_HUB_CACHE из env:", os.environ.get("HUGGINGFACE_HUB_CACHE", "НЕ ЗАДАН!"))
print("TRANSFORMERS_CACHE из env:", os.environ.get("TRANSFORMERS_CACHE", "НЕ ЗАДАН!"))
print("Дефолтный кэш HF (если env игнорирует):", os.path.expanduser("~/.cache/huggingface/hub"))

# Проверим, есть ли там GigaAM
default_cache = os.path.expanduser("~/.cache/huggingface/hub")
if os.path.exists(default_cache):
    print("Содержимое дефолтного кэша (первые 10 файлов):")
    import subprocess
    result = subprocess.run(["ls", "-la", default_cache], capture_output=True, text=True)
    print(result.stdout[:500])  # Только первые 500 символов, чтобы не спамить
else:
    print("Дефолтный кэш не существует.")

# ← Твои env (оставь как есть)
MODEL_PATH = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache"
os.environ["HF_HOME"] = MODEL_PATH
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(MODEL_PATH, "hub")  # Добавь поддиректорию — это часто фиксит
os.environ["TRANSFORMERS_CACHE"] = os.path.join(MODEL_PATH, "transformers")

from transformers import AutoModel

model = AutoModel.from_pretrained(
    "ai-sage/GigaAM-v3",
    revision="e2e_rnnt",
    trust_remote_code=True
)
print("Модель загружена! Если ошибок нет — проверь папку заново.")
import os
from transformers import AutoModel, AutoProcessor, AutoConfig
from transformers.onnx import export

# 1. Определите пути
# Ключ 1: Используем ИМЯ РЕПОЗИТОРИЯ, чтобы активировать пользовательский код
REPO_ID = "ai-sage/GigaAM-v3"
REVISION = "e2e_rnnt"

# Ключ 2: Путь к локальным весам (для from_pretrained)
model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/hub/models--ai-sage--GigaAM-v3/snapshots/7655ad717f8122257385bb4b2f373db3697e8680"

output_file_onnx = "gigaam_model.onnx"
output_dir_onnx = "gigaam_onnx_export"

# --- Шаг 2: Загрузка через Auto... (с исправленной логикой) ---

print("Загрузка конфигурации, процессора и модели...")
try:
 # 1. Загрузка Конфигурации: Используем REPO_ID, чтобы библиотека знала, какой код активировать.
 config = AutoConfig.from_pretrained(
  REPO_ID,
  revision=REVISION,
  trust_remote_code=True
 )

 # 2. Загрузка Процессора: Используем REPO_ID. После активации кода это сработает.
 processor = AutoProcessor.from_pretrained(
  REPO_ID,
  revision=REVISION,
  trust_remote_code=True
 )

 # 3. Загрузка Модели: Используем REPO_ID для определения класса,
 # но используем параметр cache_dir, чтобы брать веса из вашей ЛОКАЛЬНОЙ папки.
 model = AutoModel.from_pretrained(
  REPO_ID,
  revision=REVISION,
  config=config,
  trust_remote_code=True,
  device_map="cpu",
  low_cpu_mem_usage=True,
  # ↓↓↓ ГЛАВНОЕ ИСПРАВЛЕНИЕ: Указываем, откуда брать веса, без полного переопределения пути
  cache_dir=os.path.dirname(os.path.dirname(model_path))
 ).eval()

except Exception as e:
 print(f"❌ Критическая ошибка при загрузке: {e}")
 exit(1)

# --- Шаг 3: Экспорт в ONNX ---

os.makedirs(output_dir_onnx, exist_ok=True)

print("Экспорт модели в ONNX...")
try:
 # Используем функцию export, передавая явные классы и пути
 export(
  model=model,
  model_name="gigaam",
  # Для model_dir используем локальный путь для ONNX
  model_dir=model_path,
  output=os.path.join(output_dir_onnx, output_file_onnx),
  opset=17,
  tokenizer=processor.tokenizer,
  feature_extractor=processor.feature_extractor,
  config=config,
  device="cpu",
 )

 print(f"✅ Модель успешно сохранена в: {output_dir_onnx}/{output_file_onnx}")
 print("---")
 print("ВАЖНО: Для полноценного распознавания вам нужно перенести:")
 print(f"1. Файл {output_file_onnx}")
 print(f"2. Файлы процессора/токенизатора (config.json, tokenizer.model) из папки {model_path}")

except Exception as e:
 print(f"❌ Критическая ошибка при экспорте в ONNX: {e}")
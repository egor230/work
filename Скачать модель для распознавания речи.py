import os
from transformers import AutoProcessor, AutoModelForCTC

# Укажите точный путь, который вы запросили
LOCAL_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/saiga_asr_model"

# Самая крупная и точная модель Wav2Vec2 для русского языка
# (Замените на имя конкретного чекпоинта Saiga, если найдете,
# но этот XLS-R 300M является золотым стандартом в этом классе)
MODEL_NAME = "jonatasgrosman/wav2vec2-large-xlsr-53-russian"

# Создание целевой папки, если она не существует
if not os.path.exists(LOCAL_DIR):
  os.makedirs(LOCAL_DIR)

print(f"Начинается загрузка модели {MODEL_NAME} в папку: {LOCAL_DIR}")

try:
  # Загрузка и сохранение Процессора/Токенизатора
  processor = AutoProcessor.from_pretrained(MODEL_NAME)
  processor.save_pretrained(LOCAL_DIR)
  print("Процессор загружен и сохранен.")

  # Загрузка и сохранение самой Модели
  model = AutoModelForCTC.from_pretrained(MODEL_NAME)
  model.save_pretrained(LOCAL_DIR)
  print("Модель успешно загружена и сохранена.")

except Exception as e:
  print(f"Ошибка при загрузке модели: {e}")
  print("Проверьте соединение с Интернетом и наличие необходимых прав доступа к папке.")
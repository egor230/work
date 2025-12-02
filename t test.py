from huggingface_hub import hf_hub_download
import os
#
# repo_id = "openai/whisper-large-v3-turbo"
# filename = "model.safetensors" # Имя файла весов, который тебе нужен
#
# # Директория, куда ты хочешь сохранить файл
# local_dir = "whisper_files"
# os.makedirs(local_dir, exist_ok=True)
#
# print(f"Скачивание {filename} из {repo_id}...")
#
# # Функция скачает файл и вернет локальный путь к нему
# cached_file = hf_hub_download(
#   repo_id = repo_id,
#   filename = filename,
#   local_dir = local_dir, # Куда сохранить
#   local_dir_use_symlinks = False # Фактически сохранить файл, а не симлинк
# )
#
# print(f"\n---")
# print(f"Файл успешно скачан и сохранен по пути: {cached_file}")

# whisper_local.py
import os
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

# # Путь к твоему safetensors-файлу
# local_model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/whisper_files"
#
# # Если хочешь, можешь переименовать папку в просто "whisper-large-v3-turbo"
# # mv cache/whisper_files whisper-large-v3-turbo
#
# # Загружаем процессор (токенизатор + feature extractor) с HF (он маленький, ~500 МБ)
# processor = AutoProcessor.from_pretrained("openai/whisper-large-v3-turbo")
#
# # Загружаем модель с локального safetensors (ОЧЕНЬ БЫСТРО, без скачивания!)
# model = AutoModelForSpeechSeq2Seq.from_pretrained(
#     local_model_path,          # ← вот сюда указываем свою папку
#     torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
#     low_cpu_mem_usage=True,    # важно на CPU, экономит ОЗУ
#     device_map="auto",         # "cuda" если есть GPU, иначе "cpu"
#     local_files_only=True,     # ← обязательно, иначе опять полезет в интернет
# )
#
# # Создаём пайплайн — самый удобный способ использовать Whisper
# pipe = pipeline(
#     "automatic-speech-recognition",
#     model=model,
#     tokenizer=processor.tokenizer,
#     feature_extractor=processor.feature_extractor,
#     max_new_tokens=128,
#     chunk_length_s=30,               # для длинных аудио
#     batch_size=16,                   # увеличь до 24–32 если есть ≥16 ГБ RAM
#     torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
#     device_map="auto",
# )
#
# # Пример использования
# audio_path = "temp.wav"  # ← положи сюда свой wav/mp3/m4a и т.д.
#
# result = pipe(audio_path, generate_kwargs={"language": "russian", "task": "transcribe"})
# # result = pipe(audio_path)  # если язык автоопределение
#
# print("Распознано:")
# print(result["text"])
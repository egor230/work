import os
from transformers import AutoModel

# ==================== КЭШ ====================
MODEL_PATH = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache"
os.environ["HF_HOME"] = MODEL_PATH
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(MODEL_PATH, "hub")
os.environ["TRANSFORMERS_CACHE"] = os.path.join(MODEL_PATH, "transformers")
# pip install torch==2.8.0+cpu torchaudio==2.8.0+cpu --index-url https://download.pytorch.org/whl/cpu
# ==================== Загружаем модель ====================
print("Загружаем GigaAM-v3 (e2e_rnnt)...")
import os
import time
from pathlib import Path
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download


def monitor_download(model_name, download_dir):
 print(f"📥 Мониторинг загрузки модели: {model_name}")

 # Создаем папку если не существует
 Path(download_dir).mkdir(parents=True, exist_ok=True)

 # Запускаем скачивание
 snapshot_download(
  repo_id=model_name,
  local_dir=download_dir,
  local_dir_use_symlinks=False,
  resume_download=True
 )

 # Проверяем размер скачанных файлов
 total_size = sum(f.stat().st_size for f in Path(download_dir).rglob('*') if f.is_file())
 print(f"📊 Общий размер модели: {total_size / (1024 ** 3):.2f} GB")


# Использование
model_name = "bzikst/faster-whisper-large-v3-russian"
download_path = "./my_whisper_model"

monitor_download(model_name, download_path)

print("🔄 Загружаем модель в память...")
model = WhisperModel(
 download_path,
 device="cpu",
 compute_type="int8"
)
print("✅ Готово!")
# revision = "e2e_rnnt"  # can be any v3 model: ssl, ctc, rnnt, e2e_ctc, e2e_rnnt
# model = AutoModel.from_pretrained(
#     "ai-sage/GigaAM-v3",
#     revision=revision,        # или "rnnt" — обе работают,
#     device_map="cpu",
#     trust_remote_code=True,     # ← без этого вообще ничего не будет
# )
#
print("Модель загружена на CPU")
# # ==================== Запуск ====================
# audio_path = "temp.wav"
# transcription = model.transcribe(audio_path)
# print(transcription)
#

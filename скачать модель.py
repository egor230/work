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

revision = "e2e_rnnt"  # can be any v3 model: ssl, ctc, rnnt, e2e_ctc, e2e_rnnt
model = AutoModel.from_pretrained(
    "ai-sage/GigaAM-v3",
    revision=revision,        # или "rnnt" — обе работают,
    device_map="cpu",
    trust_remote_code=True,     # ← без этого вообще ничего не будет
)

print("Модель загружена на CPU")
# ==================== Запуск ====================
audio_path = "temp.wav"
transcription = model.transcribe(audio_path)
print(transcription)



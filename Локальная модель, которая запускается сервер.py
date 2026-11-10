import os
import uvicorn
from llama_cpp.server.app import create_app
from llama_cpp.server.settings import Settings

MODEL_DIR = os.environ.get("MODEL_DIR", "/mnt/807EB5FA7EB5E954/Program Files/ai models/mradermacher/tr-gemma-128k-4b-GGUF")

def pick_model(model_dir):
    candidates = [f for f in os.listdir(model_dir) if f.lower().endswith(".gguf") and "mmproj" not in f.lower()]
    if not candidates:
        raise FileNotFoundError(f"В папке нет .gguf модели: {model_dir}")
    def rank(name):
        n = name.lower()
        return (0 if "q4_k_m" in n else 1 if "q4" in n else 2, n)
    return os.path.join(model_dir, sorted(candidates, key=rank)[0])

MODEL_PATH = os.environ.get("MODEL_PATH") or pick_model(MODEL_DIR)
MODEL_ALIAS = os.environ.get("MODEL_ALIAS") or os.path.basename(MODEL_PATH).split(".")[0].lower()

def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default

settings = Settings(
  model=MODEL_PATH,
  model_alias=MODEL_ALIAS,
  n_ctx=env_int("LLM_CTX", 8192),
  n_gpu_layers=env_int("LLM_GPU_LAYERS", -1),
  n_threads=env_int("LLM_THREADS", 8),
  n_threads_batch=env_int("LLM_THREADS_BATCH", 16),
  n_batch=env_int("LLM_BATCH", 1024),
  n_ubatch=env_int("LLM_UBATCH", 512),
  flash_attn=True,
  seed=42,
)

app = create_app(settings=settings)

if __name__ == "__main__":
  uvicorn.run(app, host="0.0.0.0", port=env_int("PORT", 8000))

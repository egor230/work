import os
import sys

# Папка с моделью по умолчанию (можно переопределить через MODEL_DIR).
DEFAULT_MODEL_DIR = "/mnt/807EB5FA7EB5E954/Program Files/ai models/unsloth/Qwen3-4B-Instruct-2507-GGUF"
MODEL_DIR = os.environ.get("MODEL_DIR", DEFAULT_MODEL_DIR)

# llama-server из llama.cpp: умеет настоящие tool calls и встроенные файловые инструменты.
LLAMA_SERVER = os.environ.get("LLAMA_SERVER", "/home/egor/llama.cpp-b12317/llama-server")

# Приоритет квантов: сначала самые удачные по качеству/скорости.
QUANT_PRIORITY = ("q4_k_m", "q4_k_s", "q4", "q5_k_m", "q3_k_m", "q5", "q6_k", "q8_0")


def pick_model(model_dir: str) -> str:
    if not os.path.isdir(model_dir):
        raise FileNotFoundError(f"Папка с моделью не найдена: {model_dir}")

    candidates = []
    for name in os.listdir(model_dir):
        low = name.lower()
        if not low.endswith(".gguf"):
            continue
        if "mmproj" in low or low.startswith("mtp-") or ".partial" in low:
            continue
        candidates.append(os.path.join(model_dir, name))

    if not candidates:
        raise FileNotFoundError(f"В папке нет .gguf модели: {model_dir}")

    def rank(path: str):
        name = os.path.basename(path).lower()
        for index, quant in enumerate(QUANT_PRIORITY):
            if quant in name:
                return (index, name)
        return (len(QUANT_PRIORITY), name)

    return sorted(candidates, key=rank)[0]


def default_alias(path: str) -> str:
    name = os.path.basename(path).rsplit(".", 1)[0].lower()
    for suffix in ("-q8_0", "-q6_k", "-q5_k_m", "-q5_k_s", "-q5_0", "-q4_k_m", "-q4_k_s", "-q4_0", "-q3_k_m", "-q3_k_s", "-q2_k"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "да")


CLI_MODEL = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
MODEL_PATH = CLI_MODEL or os.environ.get("MODEL_PATH") or pick_model(MODEL_DIR)
if not os.path.isfile(MODEL_PATH):
    raise FileNotFoundError(f"Файл модели не найден: {MODEL_PATH}")

MODEL_ALIAS = os.environ.get("MODEL_ALIAS") or default_alias(MODEL_PATH)
HOST = os.environ.get("LLM_HOST", "0.0.0.0")
PORT = env_int("PORT", 8000)
CTX = env_int("LLM_CTX", 8192)
GPU_LAYERS = env_int("LLM_GPU_LAYERS", 99)
THREADS = env_int("LLM_THREADS", 8)
THREADS_BATCH = env_int("LLM_THREADS_BATCH", 16)
FLASH_ATTN = env_bool("LLM_FLASH_ATTN", False)
WEBUI = env_bool("LLM_WEBUI", False)

# Инструменты, которые сервер отдаёт модели. exec_shell_command намеренно не включён:
# включить всё можно через SERVER_TOOLS=all.
SERVER_TOOLS = os.environ.get(
    "SERVER_TOOLS",
    "read_file,file_glob_search,grep_search,write_file,edit_file",
)

if not os.path.isfile(LLAMA_SERVER):
    raise FileNotFoundError(
        f"Не найден llama-server: {LLAMA_SERVER}\n"
        "Укажите путь через LLAMA_SERVER=/путь/к/llama-server"
    )

args = [
    LLAMA_SERVER,
    "-m", MODEL_PATH,
    "-a", MODEL_ALIAS,
    "--host", HOST,
    "--port", str(PORT),
    "-ngl", str(GPU_LAYERS),
    "-c", str(CTX),
    "-np", "1",
    "-t", str(THREADS),
    "-tb", str(THREADS_BATCH),
    "-fa", "on" if FLASH_ATTN else "off",
    "--tools", SERVER_TOOLS,
]

if not WEBUI:
    args.append("--no-webui")

print(f"Модель: {MODEL_PATH}")
print(f"Алиас: {MODEL_ALIAS}")
print(f"Движок: llama-server ({LLAMA_SERVER})")
print(f"GPU-слои: {GPU_LAYERS}, потоков: {THREADS}/{THREADS_BATCH}, контекст: {CTX}")
print(f"Инструменты: {SERVER_TOOLS}")
print(f"Сервер: http://{HOST}:{PORT} (OpenAI API: /v1/chat/completions)")

os.execv(LLAMA_SERVER, args)

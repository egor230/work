#!/usr/bin/env python3
"""Агент для локальной модели: одна строчка — путь к модели, остальное автоматически.

Запуск:
  python3 агент.py                                # подключиться к запущенному серверу или запустить свой
  python3 агент.py "/путь/к/папке/модели"         # путь к папке или .gguf; можно строкой MODEL_DIR = "..."
  python3 агент.py --task "задача"                # одна задача вместо консольного диалога

Сервер поднимается автоматически в текущем окружении (sys.executable -m llama_cpp.server),
если не запущен, и продолжает работать в фоне после выхода.
Все действия агент выполняет автоматически, без запросов подтверждения.
"""
import argparse
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

# сервер возвращает вызовы инструментов текстом внутри content, а не полем tool_calls
TOOL_CALL_RE = re.compile("<" + "tool_call" + r">\s*(.*?)\s*" + "</" + "tool_call" + ">", re.DOTALL)
THINK_RE = re.compile(r"<think>.*?" + "</think>", re.DOTALL)
MAX_TOOL_OUTPUT = 8000
HISTORY_CHAR_LIMIT = 12000

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Выполнить shell-команду (bash) в рабочей папке, вернуть stdout/stderr и код возврата.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell-команда"},
                    "timeout": {"type": "integer", "description": "Таймаут в секундах, по умолчанию 120"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Прочитать содержимое текстового файла.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Путь к файлу"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Записать текст в файл (перезаписывает). Создаёт родительские папки.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к файлу"},
                    "content": {"type": "string", "description": "Содержимое файла"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Показать список файлов и папок в каталоге.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Путь к каталогу, по умолчанию рабочая папка"}},
                "required": [],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Ты — локальный агент на компьютере пользователя. Решай задачи с помощью инструментов. "
    "Рабочая папка: {workdir}; относительные пути считаются от неё.\n"
    "Правила:\n"
    "- Действуй пошагово: вызывай инструменты, анализируй результаты и продолжай, пока задача не выполнена полностью.\n"
    "- Для файлов используй read_file/write_file/list_dir, для остального — run_command.\n"
    "- Не выдумывай содержимое файлов и вывод команд: опирайся только на результаты инструментов.\n"
    "- Если инструмент вернул ошибку, честно сообщи, что действие не выполнено; никогда не выдавай желаемое за действительное.\n"
    "- Когда задача выполнена, дай краткий финальный ответ на русском без вызовов инструментов."
)


def visible_text(content):
    return THINK_RE.sub("", TOOL_CALL_RE.sub("", content or "")).strip()


def truncate(text):
    if len(text) <= MAX_TOOL_OUTPUT:
        return text
    return text[:MAX_TOOL_OUTPUT] + "\n...[обрезано]"


def extract_calls(message):
    calls = []
    for raw in TOOL_CALL_RE.findall(message.get("content") or ""):
        cid = f"call_{len(calls)}"
        try:
            obj = json.loads(raw)
            args = obj.get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args)
            calls.append({"id": cid, "name": obj.get("name"), "args": args})
        except json.JSONDecodeError:
            calls.append({"id": cid, "name": None, "args": {}, "error": f"Невалидный JSON в tool_call: {raw[:200]}"})
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        calls.append({"id": tc.get("id") or f"call_{len(calls)}", "name": fn.get("name"), "args": args})
    return calls


def probe(url):
    try:
        with urllib.request.urlopen(url + "/models", timeout=2) as resp:
            return json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return None


def port_free(port):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def log_tail(path, n=15):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except OSError:
        return ""


def parse_model_arg(value):
    if not value:
        return None, None
    if "=" in value:
        value = value.split("=", 1)[1]
    value = value.strip().strip('"').strip("'").strip()
    if os.path.isdir(value):
        return value, None
    if os.path.isfile(value):
        return os.path.dirname(value), value
    sys.exit(f"Путь к модели не существует: {value}")


def pick_model(model_dir):
    candidates = [f for f in os.listdir(model_dir) if f.lower().endswith(".gguf") and "mmproj" not in f.lower()]
    if not candidates:
        sys.exit(f"В папке нет .gguf модели: {model_dir}")
    def rank(name):
        n = name.lower()
        return (0 if "q4_k_m" in n else 1 if "q4" in n else 2, n)
    return os.path.join(model_dir, sorted(candidates, key=rank)[0])


def ensure_server(url, model_dir, model_path):
    info = probe(url)
    if info:
        return url, info, None
    if not model_path:
        if not model_dir:
            sys.exit('Сервер не запущен. Передайте путь к модели одной строкой: python3 агент.py "/путь/к/папке/модели"')
        model_path = pick_model(model_dir)
    if importlib.util.find_spec("llama_cpp") is None:
        sys.exit("В текущем окружении нет llama_cpp_python. Установите: pip install llama-cpp-python — или запустите сервер отдельно.")
    port = urllib.parse.urlsplit(url).port or 8000
    if not port_free(port):
        for p in range(port + 1, port + 11):
            if port_free(p):
                port = p
                break
        else:
            sys.exit("Нет свободного порта для запуска сервера.")
        url = f"http://localhost:{port}/v1"
    cmd = [
        sys.executable, "-m", "llama_cpp.server",
        "--model", model_path,
        "--model_alias", os.path.basename(model_path).split(".")[0].lower(),
        "--host", "0.0.0.0", "--port", str(port),
        "--n_ctx", os.environ.get("LLM_CTX", "8192"),
        "--n_gpu_layers", os.environ.get("LLM_GPU_LAYERS", "-1"),
        "--n_threads", os.environ.get("LLM_THREADS", "8"),
        "--n_threads_batch", os.environ.get("LLM_THREADS_BATCH", "16"),
        "--flash_attn", "true",
    ]
    log_path = os.path.join(tempfile.gettempdir(), f"llama_server_{port}.log")
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    print(f"Запускаю сервер в текущем окружении на порту {port} (pid {proc.pid}), лог: {log_path}")
    print(f"Модель: {model_path}")
    deadline = time.time() + 240
    while time.time() < deadline:
        if proc.poll() is not None:
            sys.exit(f"Сервер не запустился, конец лога:\n{log_tail(log_path)}")
        info = probe(url)
        if info:
            return url, info, proc.pid
        time.sleep(2)
    sys.exit(f"Сервер не стал готов за 240 секунд, лог: {log_path}")


class Agent:
    def __init__(self, url, model, workdir, max_steps):
        self.url = url.rstrip("/")
        self.model = model
        self.workdir = os.path.abspath(workdir)
        self.max_steps = max_steps
        self.history = []

    def api(self, path, payload=None):
        req = urllib.request.Request(
            self.url + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.load(resp)

    def resolve(self, path):
        return os.path.abspath(os.path.join(self.workdir, path))

    def exec_tool(self, name, args):
        if name == "run_command":
            try:
                timeout = int(args.get("timeout", 120))
            except (TypeError, ValueError):
                timeout = 120
            try:
                proc = subprocess.run(
                    args.get("command", ""), shell=True, cwd=self.workdir,
                    capture_output=True, text=True, timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                return "Ошибка: команда превысила таймаут."
            return f"exit_code={proc.returncode}\n{proc.stdout or ''}{proc.stderr or ''}"
        if name == "read_file":
            try:
                with open(self.resolve(args.get("path", "")), encoding="utf-8", errors="replace") as f:
                    return f.read()
            except OSError as e:
                return f"Ошибка чтения: {e}"
        if name == "write_file":
            path = self.resolve(args.get("path", ""))
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(args.get("content", ""))
                return f"OK, записан файл: {path}"
            except OSError as e:
                return f"Ошибка записи: {e}"
        if name == "list_dir":
            path = self.resolve(args.get("path") or ".")
            try:
                entries = sorted(os.listdir(path))
            except OSError as e:
                return f"Ошибка: {e}"
            lines = [e + ("/" if os.path.isdir(os.path.join(path, e)) else "") for e in entries[:300]]
            return "\n".join(lines) or "(пустой каталог)"
        return f"Неизвестный инструмент: {name}"

    def trim_history(self):
        while len(self.history) > 2 and sum(len(m.get("content") or "") for m in self.history) > HISTORY_CHAR_LIMIT:
            self.history.pop(0)
        while self.history and self.history[0]["role"] == "tool":
            self.history.pop(0)

    def run_task(self, task):
        self.trim_history()
        conversation = self.history + [{"role": "user", "content": task}]
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(workdir=self.workdir)}] + conversation
        for _ in range(self.max_steps):
            try:
                resp = self.api("/chat/completions", {
                    "model": self.model,
                    "messages": messages,
                    "tools": TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.3,
                    "max_tokens": 2048,
                })
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")
                print(f"Ошибка сервера {e.code}: {body[:500]}")
                if "context" in body.lower():
                    print("Переполнен контекст — история очищена.")
                    self.history = []
                    return
                break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                print(f"Нет связи с сервером {self.url}: {e}")
                break
            message = resp["choices"][0]["message"]
            text = visible_text(message.get("content"))
            if text:
                print(f"\n{text}")
            assistant_msg = {"role": "assistant", "content": message.get("content") or ""}
            conversation.append(assistant_msg)
            messages.append(assistant_msg)
            calls = extract_calls(message)
            if not calls:
                break
            for call in calls:
                print(f"\n[инструмент] {call['name']}: {json.dumps(call['args'], ensure_ascii=False)[:300]}")
                result = call["error"] if call.get("error") else self.exec_tool(call["name"], call["args"])
                result = truncate(result)
                preview = result if len(result) <= 500 else result[:500] + "..."
                print("  " + preview.replace("\n", "\n  "))
                tool_msg = {"role": "tool", "tool_call_id": call["id"], "content": result}
                conversation.append(tool_msg)
                messages.append(tool_msg)
        else:
            print("\nДостигнут лимит шагов.")
        self.history = conversation
        self.trim_history()


def main():
    parser = argparse.ArgumentParser(description="Агент для локальной модели: путь к модели одной строкой, остальное автоматически")
    parser.add_argument("model", nargs="?", help='путь к папке модели или .gguf; можно строкой MODEL_DIR = "..."')
    parser.add_argument("--task", help="выполнить одну задачу и выйти (без аргумента — консольный диалог)")
    parser.add_argument("--url", default=os.environ.get("LLM_URL", "http://localhost:8000/v1"))
    parser.add_argument("--workdir", default=os.getcwd(), help="рабочая папка агента")
    parser.add_argument("--max-steps", type=int, default=15, help="максимум шагов цикла на задачу")
    args = parser.parse_args()

    model_dir, model_path = parse_model_arg(args.model)
    url, info, server_pid = ensure_server(args.url, model_dir, model_path)
    agent = Agent(url, info["data"][0]["id"], args.workdir, args.max_steps)

    print(f"Агент подключён: {agent.url}, модель {agent.model}")
    print(f"Рабочая папка: {agent.workdir}")
    print("Все действия выполняются автоматически, без подтверждений.")
    if server_pid:
        print(f"Сервер продолжит работать в фоне после выхода; остановить: kill {server_pid}")

    if args.task:
        agent.run_task(args.task)
        return

    print("Команды: /reset — очистить историю, /exit — выход.")
    while True:
        try:
            task = input("\nЗадача> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not task:
            continue
        if task in ("/exit", "/quit"):
            break
        if task == "/reset":
            agent.history = []
            print("История очищена.")
            continue
        agent.run_task(task)


if __name__ == "__main__":
    main()
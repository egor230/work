#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ОДИН скрипт - ВСЁ В ОДНОМ:
  1. Сам ставит библиотеку llama-cpp-python в ТЕКУЩЕЕ виртуальное окружение (один раз)
  2. Сам загружает модель прямо в этот Python-процесс
  3. Сам включает веб-сервер (доступ по IP из сети, OpenAI-совместимый API)
  4. Сам печатает адрес подключения
  5. Крутится, пока не нажмёшь Ctrl+C или не выйдешь

Запуск (одна команда):
    python3 qwen_chat.py                 # рабочая модель по умолчанию
    python3 qwen_chat.py --model qwen38   # Qwen3.8-27B (нужен главный файл модели)
    python3 qwen_chat.py --model /путь/к/другому.gguf
    python3 qwen_chat.py --prompt "Привет"  # разовый вопрос вместо чата
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --- модели -------------------------------------------------------------
# Рабочая модель (полный файл, гарантированно грузится)
DEFAULT_MODEL = "/mnt/807EB5FA7EB5E954/Program Files/ai models/lmstudio-community/Qwen2.5-Coder-1.5B-Instruct-GGUF/Qwen2.5-Coder-1.5B-Instruct-Q8_0.gguf"

# Qwen3.8-27B: в этой папке только MTP-модуль (0.9 ГБ) и vision-модуль,
# ГЛАВНЫЙ файл модели ~15 ГБ отсутствует - загрузка невозможна до его скачивания
QWEN38_MTP = "/mnt/807EB5FA7EB5E954/Program Files/ai models/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf"

WEB_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Локальная модель - чат</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;background:#1e1e2e;color:#eee}
 .wrap{max-width:760px;margin:0 auto;padding:16px}
 .msg{padding:10px 14px;border-radius:10px;margin:8px 0;white-space:pre-wrap;line-height:1.4}
 .user{background:#31324d;margin-left:60px}
 .bot{background:#45475a;margin-right:60px}
 #box{min-height:50vh;max-height:60vh;overflow-y:auto}
 input{width:70%;padding:10px;border-radius:8px;border:none;background:#31324d;color:#eee;font-size:15px}
 button{padding:10px 18px;border-radius:8px;border:none;background:#7aa2f7;color:#111;font-size:15px}
</style></head><body><div class="wrap">
<h2>Локальная модель</h2>
<div id="box"><div class="msg bot">Модель запущена. Пиши вопрос ниже.</div></div>
<div><input id="q" autofocus placeholder="Сообщение..." onkeydown="if(event.key==='Enter')send()"><button onclick="send()">Отправить</button></div>
<script>
const hist=[];
function add(who,txt){const d=document.createElement('div');d.className='msg '+who;d.textContent=txt;
 document.getElementById('box').appendChild(d);document.getElementById('box').scrollTop=1e9;}
async function send(){
 const q=document.getElementById('q');if(!q.value.trim())return;
 const text=q.value;q.value='';hist.push({role:'user',content:text});add('user',text);
 const w=document.createElement('div');w.className='msg bot';w.textContent='...';
 document.getElementById('box').appendChild(w);
 try{
  const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({model:'local-model',messages:hist})});
  const j=await r.json();
  const a=j.choices[0].message.content;w.textContent=a;hist.push({role:'assistant',content:a});
 }catch(e){w.textContent='Ошибка: '+e;}
}
</script></div></body></html>
"""


def vtuple(v):
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except Exception:
        return (0, 0, 0)


def ensure_llama_cpp(min_ver="0.3.36"):
    import importlib
    try:
        import llama_cpp
        if vtuple(getattr(llama_cpp, "__version__", "0")) >= vtuple(min_ver):
            return
        print(f">> Версия llama-cpp-python {getattr(llama_cpp, '__version__', '?')} слишком старая. Обновляю до {min_ver}+...")
    except ImportError:
        print(f">> Библиотека llama-cpp-python не найдена. Устанавливаю в это окружение (один раз)...")
    rc = subprocess.call([sys.executable, "-m", "pip", "install", "-U", "llama-cpp-python"])
    if rc != 0:
        print("ОШИБКА: не удалось установить/обновить библиотеку (нужен интернет один раз).")
        print("Вручную: " + sys.executable + " -m pip install -U llama-cpp-python")
        sys.exit(1)
    # перезапускаем процесс, чтобы подхватить новую библиотеку
    print(">> Готово. Перезапускаю скрипт с новой библиотекой...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


def get_local_ip():
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5).stdout.split()
        ips = [i for i in out if not i.startswith("127.")]
        if ips:
            return ips[0]
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def resolve_model(arg):
    if arg in (None, "", "default"):
        return DEFAULT_MODEL, "по умолчанию"
    if arg == "qwen38":
        return QWEN38_MTP, "qwen38"
    return arg, "custom"


def main():
    ap = argparse.ArgumentParser(description="Всё в одном: запуск локальной модели + веб-API + чат")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--model", default=None, help="qwen38, default или путь к .gguf")
    ap.add_argument("--prompt", default=None, help="разовый вопрос вместо чата")
    args = ap.parse_args()

    ensure_llama_cpp()
    from llama_cpp import Llama

    model_path, src = resolve_model(args.model)
    if not os.path.isfile(model_path):
        print(f"ОШИБКА: файл модели не найден: {model_path}")
        sys.exit(1)

    # --- загрузка модели (без страшных трейсбеков) ---
    print(f">> Загружаю модель ({os.path.basename(model_path)})...")
    t0 = time.time()
    try:
        llm = Llama(model_path=model_path, n_ctx=args.ctx,
                    n_threads=max(4, (os.cpu_count() or 4) // 2), verbose=False)
    except Exception:
        llm = None
    if llm is None:
        print(f"\nНЕ УДАЛОСЬ загрузить: {model_path}")
        if src == "qwen38":
            print("  Этот файл - MTP-модуль (0.9 ГБ). Главный файл модели Qwen3.8-27B (~15 ГБ)")
            print("  отсутствует в папке HauhauCS/...-MTP-GGUF. Скачайте его - и скрипт пойдёт.")
        if src == "default":
            sys.exit(1)
        print("  Пробую рабочую модель по умолчанию...")
        model_path = DEFAULT_MODEL
        llm = Llama(model_path=model_path, n_ctx=args.ctx,
                    n_threads=max(4, (os.cpu_count() or 4) // 2), verbose=False)
    print(f">> Модель загружена за {time.time() - t0:.0f} сек.")

    model_lock = threading.Lock()

    def generate(messages, max_tokens=2048):
        with model_lock:
            out = llm.create_chat_completion(
                messages=messages, temperature=0.7, max_tokens=max_tokens, top_p=0.9)
            return out["choices"][0]["message"]["content"]

    # --- веб-сервер (доступ по IP) ---
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/chat"):
                self._send(200, WEB_PAGE, "text/html")
            elif self.path == "/health":
                self._send(200, "ok")
            elif self.path == "/v1/models":
                self._send(200, json.dumps({"data": [{"id": "local-model"}]}))
            else:
                self._send(404, json.dumps({"error": "не найдено"}))

        def do_POST(self):
            if self.path == "/v1/chat/completions":
                try:
                    req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                    ans = generate(req.get("messages", []), int(req.get("max_tokens", 2048)))
                    self._send(200, json.dumps({"choices": [{"message": {"role": "assistant", "content": ans}}]}))
                except Exception as e:
                    self._send(500, json.dumps({"error": str(e)}))
            else:
                self._send(404, json.dumps({"error": "не найдено"}))

    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    except OSError:
        print(f"ОШИБКА: порт {args.port} занят. Попробуй --port 8081")
        sys.exit(1)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    # --- баннер с адресом ---
    ip = get_local_ip()
    print()
    print("=" * 62)
    print("  ВСЁ ЗАПУЩЕНО. Подключайся по адресу:")
    print()
    print(f"    Веб-чат:   http://{ip}:{args.port}/chat")
    print(f"    API:       http://{ip}:{args.port}/v1  (OpenAI-совместимый)")
    print()
    print(f"  Модель: {os.path.basename(model_path)} | контекст: {args.ctx}")
    print("  Скрипт крутится - остановить: 'exit' или Ctrl+C")
    print("=" * 62)
    print()

    # --- чат / разовый вопрос ---
    history = []
    if args.prompt:
        print(generate([{"role": "user", "content": args.prompt}]))
    else:
        print("Чат (выход - 'exit' / Ctrl+C, очистить историю - '/clear')\n")
        while True:
            try:
                user = input("Вы > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if user.lower() in ("exit", "quit"):
                break
            if user == "/clear":
                history = []
                print("История очищена.")
                continue
            if not user:
                continue
            history.append({"role": "user", "content": user})
            print("Модель думает... ", end="", flush=True)
            answer = generate(history)
            print(answer + "\n")
            history.append({"role": "assistant", "content": answer})

    httpd.shutdown()
    print("\n>> Сервер остановлен. Пока!")


if __name__ == "__main__":
    main()

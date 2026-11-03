#!/usr/bin/env python3
"""
qwen_server.py - локальный OpenAI-совместимый сервер на llama.cpp (llama-cpp-python).

Возможности:
  * сам ставит llama-cpp-python при необходимости (один раз);
  * загружает GGUF-модель и прогревает её (первый запрос не тормозит);
  * /v1/chat/completions - формат OpenAI: обычный и потоковый режим (stream),
    вызов инструментов (tools -> tool_calls), сообщения role=tool;
  * /v1/models, /health, веб-чат на /chat;
  * сам создаёт готовый opencode.json, если его ещё нет (модель + полный доступ);
  * подходит для OpenCode и других OpenAI-клиентов.

Инструменты (файлы, папки, shell) выполняет КЛИЕНТ (например OpenCode) на своей машине.
Сервер лишь даёт модели возможность выбрать инструмент и вернуть его вызов.

Запуск:
    python3 qwen_server.py
    python3 qwen_server.py --port 8080 --ctx 32768 --gpu-layers -1
    python3 qwen_server.py --model "/путь/к/модели.gguf" --api-key secret123
"""
import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_MODEL = ("/mnt/807EB5FA7EB5E954/Program Files/ai models/saidutta69/Qwen2.5-7B-Instruct-1M-heretic/Qwen2.5-7B-Instruct-1M-heretic-Q4_K_M.gguf")

OPEN_TAG = "<tool_call>"
CLOSE_TAG = "</tool_call>"

CFG = None                      # аргументы командной строки (заполняется в main)
llm = None                      # загруженная модель
model_lock = threading.Lock()   # llama.cpp обрабатывает запросы по одному

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
 input{padding:10px;border-radius:8px;border:none;background:#31324d;color:#eee;font-size:15px}
 #q{width:70%}
 button{padding:10px 18px;border-radius:8px;border:none;background:#7aa2f7;color:#111;font-size:15px}
</style></head><body><div class="wrap">
<h2>Локальная модель</h2>
<div><input id="key" placeholder="API-ключ (если задан на сервере)" style="width:100%;margin-bottom:8px"></div>
<div id="box"><div class="msg bot">Модель запущена. Пиши вопрос ниже.</div></div>
<div><input id="q" autofocus placeholder="Сообщение..." onkeydown="if(event.key==='Enter')send()"><button onclick="send()">Отправить</button></div>
<script>
const hist=[];
const box=document.getElementById('box');
function add(who,txt){const d=document.createElement('div');d.className='msg '+who;d.textContent=txt;
 box.appendChild(d);box.scrollTop=1e9;return d;}
async function send(){
 const q=document.getElementById('q');if(!q.value.trim())return;
 const text=q.value;q.value='';hist.push({role:'user',content:text});add('user',text);
 const w=add('bot','...');
 const headers={'Content-Type':'application/json'};
 const k=document.getElementById('key').value.trim();
 if(k)headers['Authorization']='Bearer '+k;
 try{
   const r=await fetch('/v1/chat/completions',{method:'POST',headers:headers,
     body:JSON.stringify({model:'local-model',messages:hist})});
   const j=await r.json();
   if(j.error)throw new Error(j.error.message);
   const a=j.choices[0].message.content||'';
   w.textContent=a;hist.push({role:'assistant',content:a});
 }catch(e){w.textContent='Ошибка: '+e.message;}
}
</script></div></body></html>
"""


# ============================ утилиты ============================

def sse(obj):
    return b"data: " + json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n\n"


def normalize_content(c):
    """content может быть строкой, списком частей или None."""
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for p in c:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and "text" in p:
                parts.append(str(p["text"]))
            elif isinstance(p, dict) and p.get("type") == "image_url":
                parts.append("[изображение не поддерживается этой локальной моделью]")
        return "\n".join(parts)
    return str(c)


def _loads_loose(s):
    """Пытается превратить строку в dict JSON, терпя ```-обёртки, висячие запятые и мусор вокруг."""
    s = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", s.strip())
    variants = [s, re.sub(r",\s*([}\]])", r"\1", s)]   # вторая - с убранными висячими запятыми
    for v in variants:
        try:
            obj = json.loads(v)
        except Exception:
            continue
        return obj if isinstance(obj, dict) else None
    a, b = s.find("{"), s.rfind("}")
    if a == -1 or b <= a:
        return None
    frag = s[a:b + 1]
    for v in (frag, re.sub(r",\s*([}\]])", r"\1", frag)):
        try:
            obj = json.loads(v)
        except Exception:
            continue
        return obj if isinstance(obj, dict) else None
    return None


def _to_tool_call(obj):
    name = str(obj.get("name") or obj.get("tool") or "").strip()
    if not name:
        return None
    args = obj.get("arguments", obj.get("parameters", obj.get("args", {})))
    if args is None:
        args = {}
    if isinstance(args, str):
        args_s = args if args.strip() else "{}"
    else:
        args_s = json.dumps(args, ensure_ascii=False)
    return {"id": "call_" + uuid.uuid4().hex[:24], "type": "function",
            "function": {"name": name, "arguments": args_s}}


def _fallback_json_call(text, names):
    """Модель ответила голым JSON вида {"name": ..., "arguments": ...} без тегов."""
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip()).strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    obj = _loads_loose(t)
    if not obj or obj.get("name") not in names:
        return None
    return _to_tool_call(obj)


def split_output(text, names):
    """
    Делит ответ модели на: (текст до вызова, список tool_calls, текст после).
    names = None -> инструменты выключены, всё возвращаем как текст.
    """
    if not names:
        return text, [], ""
    first = text.find(OPEN_TAG)
    if first == -1:
        call = _fallback_json_call(text, names)
        return ("", [call], "") if call else (text, [], "")
    before = text[:first]
    calls, after = [], []
    pos = first
    while True:
        s = text.find(OPEN_TAG, pos)
        if s == -1:
            after.append(text[pos:])
            break
        after.append(text[pos:s])
        e = text.find(CLOSE_TAG, s)
        end = e if e != -1 else len(text)
        inner = text[s + len(OPEN_TAG):end]
        obj = _loads_loose(inner)
        call = _to_tool_call(obj) if obj else None
        if call:
            calls.append(call)
        else:
            after.append(text[s:end + len(CLOSE_TAG) if e != -1 else end])
        if e == -1:
            break
        pos = e + len(CLOSE_TAG)
    return before, calls, "".join(after)


def build_tools_block(tools, tool_choice="auto"):
    sigs = "\n".join(json.dumps(t, ensure_ascii=False) for t in tools)
    text = (
        "# Tools\n\n"
        "You may call one or more functions to assist with the user query.\n\n"
        "You are provided with function signatures within <tools></tools> XML tags:\n"
        "<tools>\n" + sigs + "\n</tools>\n\n"
        "For each function call, return a json object with function name and arguments "
        "within <tool_call></tool_call> XML tags:\n"
        "<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call>\n\n"
        "Rules: when the next step depends on a tool result, call ONE tool and wait for the result; "
        "use exact parameter names from the schema; arguments must be valid JSON; "
        "keep file paths exactly as given (including spaces and Cyrillic); "
        "never invent tool results - after each <tool_response> either continue the task "
        "or call the next tool. "
        "When the task is finished, answer the user in plain text WITHOUT tool calls."
    )
    forced = ""
    if isinstance(tool_choice, dict):
        fname = ((tool_choice.get("function") or {}).get("name")) or ""
        if fname:
            forced = f' In this reply you MUST call the function "{fname}".'
    elif tool_choice == "required":
        forced = " In this reply you MUST call a tool."
    return text + forced


def convert_messages(messages, tools, tool_choice="auto"):
    """OpenAI-сообщения -> простые system/user/assistant с текстовыми <tool_call>/<tool_response>."""
    system_texts, body, pending = [], [], []

    def flush():
        if pending:
            body.append({"role": "user", "content": "\n".join(
                "<tool_response>\n" + t + "\n</tool_response>" for t in pending)})
            pending.clear()

    for m in messages:
        role = m.get("role", "user")
        if role in ("system", "developer"):
            system_texts.append(normalize_content(m.get("content")))
            continue
        if role == "tool":
            pending.append(normalize_content(m.get("content")))
            continue
        flush()
        if role == "assistant":
            text = normalize_content(m.get("content")).strip()
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except Exception:
                        args = {"raw": args}
                call = json.dumps({"name": fn.get("name", ""), "arguments": args}, ensure_ascii=False)
                text = (text + "\n" if text else "") + OPEN_TAG + "\n" + call + "\n" + CLOSE_TAG
            body.append({"role": "assistant", "content": text})
        else:
            body.append({"role": "user", "content": normalize_content(m.get("content"))})
    flush()

    sys_text = "\n\n".join(s for s in system_texts if s.strip())
    if tools:
        sys_text = (sys_text + "\n\n" if sys_text else "") + build_tools_block(tools, tool_choice)
    out = [{"role": "system", "content": sys_text}] if sys_text else []
    return out + body


def fit_messages(msgs, want):
    """Обрезает старые сообщения, чтобы промпт + ответ влезли в контекст."""
    ctx = llm.n_ctx()
    want = min(want, ctx // 2)
    counts = [len(llm.tokenize(m["content"].encode("utf-8"), add_bos=False)) + 8 for m in msgs]
    keep = [i for i, m in enumerate(msgs) if m["role"] == "system"]
    rest = [i for i, m in enumerate(msgs) if m["role"] != "system"]

    def total(idxs):
        return sum(counts[i] for i in idxs)

    while len(rest) > 1 and total(keep) + total(rest) > ctx - want - 16:
        rest.pop(0)
    used = total(keep) + total(rest)
    avail = ctx - used - 16
    if avail < 64:
        raise ValueError(f"Промпт ({used} токенов) не помещается в контекст {ctx}. "
                         f"Запусти сервер с большим --ctx.")
    return [msgs[i] for i in keep + rest], min(want, avail), used


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


def vtuple(v):
    try:
        return tuple(int(re.sub(r"\D", "", x) or 0) for x in v.split(".")[:3])
    except Exception:
        return (0, 0, 0)


def ensure_llama_cpp(min_ver="0.3.0"):
    try:
        import llama_cpp
        if vtuple(getattr(llama_cpp, "__version__", "0")) >= vtuple(min_ver):
            return
        print(f">> llama-cpp-python {llama_cpp.__version__} устарел, обновляю...")
    except ImportError:
        print(">> llama-cpp-python не найден, устанавливаю (один раз, может занять несколько минут)...")
    if os.environ.get("QWEN_SERVER_RESTARTED"):
        return  # уже перезапускались - не зацикливаемся
    rc = subprocess.call([sys.executable, "-m", "pip", "install", "-U", "llama-cpp-python"])
    if rc != 0:
        print("ОШИБКА установки. Попробуй вручную: " + sys.executable + " -m pip install -U llama-cpp-python")
        sys.exit(1)
    print(">> Готово, перезапускаю скрипт...")
    os.environ["QWEN_SERVER_RESTARTED"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ============================ HTTP ============================

class Handler(BaseHTTPRequestHandler):
    server_version = "LocalQwen/2.1"
    protocol_version = "HTTP/1.1"   # keep-alive: клиенты переиспользуют соединения
    timeout = 300                   # мёртвые соединения не держим вечно

    def log_message(self, fmt, *args):
        print("  [http] " + (fmt % args))

    # --- вспомогательное ---
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _error(self, code, msg, etype="invalid_request_error"):
        self._json(code, {"error": {"message": msg, "type": etype}})

    def _html(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        if not CFG.api_key:
            return True
        auth = self.headers.get("Authorization", "")
        key = auth[7:] if auth.startswith("Bearer ") else self.headers.get("x-api-key", "")
        return key == CFG.api_key

    # --- маршруты ---
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path in ("/", "/chat"):
            return self._html(WEB_PAGE)
        if path == "/health":
            return self._json(200, {"status": "ok"})
        if path in ("/v1/models", "/models"):
            if not self._authorized():
                return self._error(401, "неверный API-ключ", "authentication_error")
            ids = list(dict.fromkeys([CFG.model_name, "local-model"]))
            return self._json(200, {"object": "list", "data": [
                {"id": i, "object": "model", "created": 0, "owned_by": "local"} for i in ids]})
        self._error(404, "не найдено: " + path, "not_found")

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path not in ("/v1/chat/completions", "/chat/completions"):
            return self._error(404, "не найдено: " + path, "not_found")
        if not self._authorized():
            return self._error(401, "неверный API-ключ", "authentication_error")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._error(400, f"некорректный JSON: {e}")
        try:
            self._chat(req)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"  ОШИБКА запроса: {e}")
            try:
                self._error(500, str(e), "server_error")
            except Exception:
                pass

    # --- чат ---
    def _chat(self, req):
        messages = req.get("messages") or []
        if not messages:
            return self._error(400, "пустой список messages")

        tools = [t for t in (req.get("tools") or []) if isinstance(t, dict)]
        tool_choice = req.get("tool_choice", "auto")
        if CFG.no_tools or tool_choice == "none":
            tools = []
        names = {(t.get("function") or {}).get("name") for t in tools} - {None} if tools else None
        tools_on = bool(names)

        stream = bool(req.get("stream"))
        want = int(req.get("max_tokens") or req.get("max_completion_tokens") or CFG.max_tokens)
        temperature = float(req.get("temperature", CFG.temperature))
        top_p = float(req.get("top_p", 0.9))
        stop = req.get("stop")
        if isinstance(stop, str):
            stop = [stop]
        model_name = str(req.get("model") or CFG.model_name)
        include_usage = bool((req.get("stream_options") or {}).get("include_usage"))

        msgs = convert_messages(messages, tools if tools_on else [], tool_choice)
        msgs, max_new, n_prompt = fit_messages(msgs, want)

        gen_kwargs = {"max_tokens": max_new, "temperature": temperature, "top_p": top_p}
        if stop:
            gen_kwargs["stop"] = stop[:8]
        for k in ("presence_penalty", "frequency_penalty"):
            if req.get(k) is not None:
                try:
                    gen_kwargs[k] = float(req[k])
                except (TypeError, ValueError):
                    pass

        if stream:
            return self._stream(msgs, gen_kwargs, tools_on, names,
                                model_name, include_usage, n_prompt)

        with model_lock:
            t0 = time.time()
            out = llm.create_chat_completion(messages=msgs, **gen_kwargs)
        u = out.get("usage") or {}
        print(f"  [gen] {u.get('completion_tokens', '?')} ток. за {time.time() - t0:.1f}с "
              f"(промпт ~{n_prompt} ток.)")
        text = out["choices"][0]["message"].get("content") or ""
        before, calls, after = split_output(text, names)
        content = (before + after).strip()
        message = {"role": "assistant", "content": (content or None) if calls else content}
        if calls:
            message["tool_calls"] = calls
        self._json(200, {
            "id": "chatcmpl-" + uuid.uuid4().hex[:24],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [{"index": 0, "message": message,
                         "finish_reason": "tool_calls" if calls else "stop"}],
            "usage": out.get("usage") or {},
        })

    def _stream(self, msgs, gen_kwargs, tools_on, names,
                model_name, include_usage, n_prompt):
        cid = "chatcmpl-" + uuid.uuid4().hex[:24]
        created = int(time.time())

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._cors()
        self.end_headers()

        def emit(delta, finish=None):
            self.wfile.write(sse({"id": cid, "object": "chat.completion.chunk", "created": created,
                                  "model": model_name,
                                  "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}))
            self.wfile.flush()

        emit({"role": "assistant", "content": ""})
        acc, sent, n_gen, finish = "", 0, 0, "stop"
        try:
            with model_lock:
                t0 = time.time()
                gen = llm.create_chat_completion(messages=msgs, stream=True, **gen_kwargs)
                try:
                    for part in gen:
                        ch = part.get("choices") or []
                        if not ch:
                            continue
                        d = ch[0].get("delta") or {}
                        tok = d.get("content") or ""
                        if not tok:
                            continue
                        n_gen += 1
                        acc += tok
                        if not tools_on:
                            emit({"content": tok})
                            sent = len(acc)
                            continue
                        # Похоже на вызов без тегов (голый или ```-обёрнутый JSON) - ждём окончания
                        if acc.lstrip().startswith(("{", "```")):
                            continue
                        i = acc.find(OPEN_TAG)
                        if i != -1:                 # начался вызов инструмента - текст не стримим
                            if i > sent:
                                emit({"content": acc[sent:i]})
                                sent = i
                            continue
                        # держим хвост, который может оказаться началом тега
                        safe = len(acc) - (len(OPEN_TAG) - 1)
                        if safe > sent:
                            emit({"content": acc[sent:safe]})
                            sent = safe
                finally:
                    gen.close()
            print(f"  [gen] ~{n_gen} ток. за {time.time() - t0:.1f}с (промпт ~{n_prompt} ток.)")

            if tools_on:
                before, calls, after = split_output(acc, names)
                if calls:
                    if len(before) > sent:
                        emit({"content": before[sent:]})
                    for idx, tc in enumerate(calls):
                        # как у OpenAI: сначала чанк с id и именем, затем аргументы отдельным куском
                        emit({"tool_calls": [{"index": idx, "id": tc["id"], "type": "function",
                                              "function": {"name": tc["function"]["name"],
                                                           "arguments": ""}}]})
                        emit({"tool_calls": [{"index": idx,
                                              "function": {"arguments": tc["function"]["arguments"]}}]})
                    finish = "tool_calls"
                else:
                    full = before + after
                    if len(full) > sent:
                        emit({"content": full[sent:]})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            print(f"  ОШИБКА генерации: {e}")
            try:
                emit({"content": f"\n\n[ошибка генерации: {e}]"})
            except Exception:
                return

        try:
            emit({}, finish)
            if include_usage:
                self.wfile.write(sse({"id": cid, "object": "chat.completion.chunk", "created": created,
                                      "model": model_name, "choices": [],
                                      "usage": {"prompt_tokens": n_prompt, "completion_tokens": n_gen,
                                                "total_tokens": n_prompt + n_gen}}))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception:
            pass
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            print(f"  ОШИБКА генерации: {e}")
            try:
                emit({"content": f"\n\n[ошибка генерации: {e}]"})
            except Exception:
                return

        try:
            emit({}, finish)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception:
            pass


# ============================ запуск ============================

def _free_port_from_our(port):
    """Если порт держит старый запуск qwen_chat.py — останавливаем его."""
    pids = []
    try:
        out = subprocess.run(["lsof", "-t", "-i", "tcp:%d" % port],
                             capture_output=True, text=True, timeout=5)
        pids = [t for t in out.stdout.split() if t.isdigit()]
    except Exception:
        pass
    if not pids:
        try:
            out = subprocess.run(["fuser", "-n", "tcp", str(port)],
                                 capture_output=True, text=True, timeout=5)
            txt = (out.stderr + " " + out.stdout).split(":", 1)[-1]
            pids = [t for t in txt.split() if t.isdigit()]
        except Exception:
            pass
    for pid in pids:
        try:
            if int(pid) == os.getpid():
                continue
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                if b"qwen_chat" in f.read():
                    print(">> Порт %d занят старым qwen_chat.py (PID %s) - останавливаю" % (port, pid))
                    os.kill(int(pid), signal.SIGTERM)
        except Exception:
            pass
    time.sleep(1.5)


def bind_server(host, port):
    _free_port_from_our(port)
    for p in range(port, port + 20):
        try:
            return ThreadingHTTPServer((host, p), Handler), p
        except OSError:
            continue
    sys.exit(f"ОШИБКА: не удалось занять ни один порт от {port} до {port + 19}")


def main():
    global CFG, llm
    ap = argparse.ArgumentParser(description="Локальный OpenAI-совместимый сервер на llama.cpp")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="путь к .gguf")
    ap.add_argument("--model-name", default=None, help="имя модели в API (по умолчанию имя файла)")
    ap.add_argument("--host", default="0.0.0.0", help="0.0.0.0 - доступ из сети, 127.0.0.1 - только этот ПК")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--ctx", type=int, default=32768, help="размер контекста (OpenCode шлёт большие промпты)")
    ap.add_argument("--threads", type=int, default=max(4, (os.cpu_count() or 8) // 2))
    ap.add_argument("--gpu-layers", type=int, default=0, help="слоёв на GPU (-1 = все)")
    ap.add_argument("--max-tokens", type=int, default=4096, help="лимит ответа по умолчанию")
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--chat-format", default=None,
                    help="например chatml; по умолчанию берётся шаблон из файла модели")
    ap.add_argument("--q8-kv", action="store_true",
                    help="KV-кэш в 8 бит - примерно вдвое меньше памяти под большой контекст")
    ap.add_argument("--api-key", default=None, help="если задан - клиенты должны передавать этот ключ")
    ap.add_argument("--no-tools", action="store_true", help="не передавать инструменты модели")
    CFG = ap.parse_args()
    if not CFG.model_name:
        CFG.model_name = os.path.splitext(os.path.basename(CFG.model))[0]

    if not os.path.isfile(CFG.model):
        sys.exit(f"ОШИБКА: файл модели не найден: {CFG.model}")

    if not CFG.chat_format and "qwen" in os.path.basename(CFG.model).lower():
        # У многих Qwen-GGUF в метаданных нет chat_template: без явного формата
        # llama-cpp-python сваливается в llama-2 шаблон и модель отвечает мусором.
        CFG.chat_format = "chatml"
        print(">> Обнаружен Qwen - применяю шаблон ChatML (<|im_start|>/<|im_end|>)")

    ensure_llama_cpp()
    from llama_cpp import Llama

    kv_kwargs = {}
    if CFG.q8_kv:
        q8 = None
        try:
            from llama_cpp import ggml as _ggml
            q8 = _ggml.GGML_TYPE_Q8_0
        except Exception:
            try:
                from llama_cpp import llama_cpp as _bind
                q8 = _bind.GGML_TYPE_Q8_0
            except Exception:
                q8 = 8  # значение GGML_TYPE_Q8_0 в enum ggml
        kv_kwargs = {"type_k": q8, "type_v": q8}
        print(">> KV-кэш: Q8_0")

    print(f">> Загружаю модель {os.path.basename(CFG.model)} ...")
    t0 = time.time()
    try:
        llm = Llama(model_path=CFG.model, n_ctx=CFG.ctx, n_threads=CFG.threads,
                    n_gpu_layers=CFG.gpu_layers, chat_format=CFG.chat_format,
                    verbose=False, **kv_kwargs)
    except Exception as e:
        if kv_kwargs:
            print(f">> Не удалось загрузить с Q8-KV ({e}), пробую без него...")
            try:
                llm = Llama(model_path=CFG.model, n_ctx=CFG.ctx, n_threads=CFG.threads,
                            n_gpu_layers=CFG.gpu_layers, chat_format=CFG.chat_format, verbose=False)
            except Exception as e2:
                sys.exit(f"ОШИБКА загрузки модели: {e2}")
        else:
            sys.exit(f"ОШИБКА загрузки модели: {e}")
    print(f">> Модель загружена за {time.time() - t0:.0f} сек.")

    print(">> Прогреваю модель (первый запрос будет быстрым)...")
    tw = time.time()
    try:
        llm.create_chat_completion(messages=[{"role": "user", "content": "Hi"}],
                                   max_tokens=4, temperature=0.0)
        print(f">> Прогрев завершён за {time.time() - tw:.1f} сек.")
    except Exception as e:
        print(f">> Прогрев пропущен: {e}")

    try:
        import llama_cpp as _lc
        if hasattr(_lc, "llama_supports_gpu_offload"):
            if not _lc.llama_supports_gpu_offload() and CFG.gpu_layers != 0:
                print(">> ВНИМАНИЕ: эта сборка llama-cpp-python БЕЗ поддержки GPU, "
                      "--gpu-layers игнорируется")
            elif _lc.llama_supports_gpu_offload() and CFG.gpu_layers == 0:
                print(">> Подсказка: сборка умеет GPU - можно ускорить генерацию: --gpu-layers -1")
    except Exception:
        pass

    srv, port = bind_server(CFG.host, CFG.port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    ip = get_local_ip()
    base = f"http://127.0.0.1:{port}"
    print()
    print("=" * 66)
    print("  СЕРВЕР ЗАПУЩЕН")
    print(f"  API (OpenCode и др.):  {base}/v1")
    if ip != "127.0.0.1":
        print(f"  API из сети:           http://{ip}:{port}/v1")
    print(f"  Веб-чат:               {base}/chat")
    print(f"  Имя модели в API:      {CFG.model_name}")
    print(f"  Контекст: {CFG.ctx} | инструменты: {'выкл' if CFG.no_tools else 'вкл (выполняет клиент)'}")
    print(f"  API-ключ: {'задан (--api-key)' if CFG.api_key else 'не требуется'}")
    print("=" * 66)

    cfg = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "local": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Local Qwen",
                "options": {"baseURL": f"{base}/v1", "apiKey": CFG.api_key or "none"},
                "models": {
                    CFG.model_name: {
                        "name": CFG.model_name,
                        "tool_call": True,
                        "limit": {"context": CFG.ctx,
                                  "output": min(CFG.max_tokens, CFG.ctx // 2)},
                    }
                },
            }
        },
        "model": f"local/{CFG.model_name}",
        "permission": {"edit": "allow", "bash": "allow", "read": "allow",
                       "glob": "allow", "grep": "allow", "task": "allow",
                       "webfetch": "allow", "websearch": "allow",
                       "external_directory": {"*": "allow"}},
    }

    # 1) конфиг для проекта - в текущую папку, если там его ещё нет
    cfg_path = os.path.abspath("opencode.json")
    if os.path.exists(cfg_path):
        print(f">> {cfg_path} уже существует - не перезаписываю.")
    else:
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print(f">> Конфиг OpenCode создан: {cfg_path}")
            print("   Полный доступ без вопросов: edit/bash/read/webfetch = allow.")
        except OSError as e:
            print(f">> Не удалось записать {cfg_path}: {e}")

    # 2) глобальный конфиг - только если его вообще нет (иначе не мешаем)
    home_cfg_dir = os.path.expanduser("~/.config/opencode")
    global_cfg = os.path.join(home_cfg_dir, "opencode.json")
    global_cfgc = os.path.join(home_cfg_dir, "opencode.jsonc")
    if not (os.path.exists(global_cfg) or os.path.exists(global_cfgc)):
        try:
            os.makedirs(home_cfg_dir, exist_ok=True)
            with open(global_cfg, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print(f">> Глобальный конфиг OpenCode создан: {global_cfg}")
        except OSError:
            pass
    else:
        existing = global_cfgc if os.path.exists(global_cfgc) else global_cfg
        print(f">> Глобальный конфиг OpenCode уже есть ({existing}) - не трогаю.")
        print("   Провайдер для этой модели (если ещё не добавлен):")
        print("     \"local\": {")
        print(f"       \"npm\": \"@ai-sdk/openai-compatible\",")
        print(f"       \"options\": {{\"baseURL\": \"{base}/v1\"}},")
        print(f"       \"models\": {{\"{CFG.model_name}\": {{\"name\": \"Local Qwen\"}}}}")
        print("     }")

    print()
    print("Конфиг целиком (для ручной вставки):")
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
    print()
    print("Остановить: Ctrl+C")

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n>> Останавливаю сервер...")
    finally:
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    main()
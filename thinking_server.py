"""thinking_server.py — автономный SSE-сервер потока мыслей.

Механизм сервера взят из zai_agent.py (FastAPI + uvicorn + StreamingResponse,
OpenAI-совместимые эндпоинты /v1/chat/completions и /v1/models).

Стрим «мышления» идёт через for-цикл с паузой 3 секунды, в конце — «задача решена».

Запуск:  myvenv/bin/python thinking_server.py --host 127.0.0.1 --port 8001
Проверка: curl -N -X POST http://127.0.0.1:8001/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d '{"model":"thinking-server","stream":true,"messages":[{"role":"user","content":"привет"}]}'
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from typing import Any, Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI()

DEFAULT_MODEL = "GLM-5-Turbo"
THINK_PIECES = [
    "я думаю над Вашей задачей",
    "анализирую полученное сообщение",
    "проверяю варианты решения",
]
WORD_DELAY = 0.35
PHRASE_PAUSE = 1.2
FINAL_TEXT = "задача решена"


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict[str, Any]] = Field(min_length=1)
    stream: bool = False


class ThinkingIngest(BaseModel):
    text: str = Field(min_length=1)


def _prompt_from_messages(messages: list[dict[str, Any]]) -> str:
    parts = []
    for item in messages:
        content = item.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(x.get("text", x)) if isinstance(x, dict) else str(x)
                               for x in content)
        if str(content).strip():
            parts.append(str(content).strip())
    return "\n\n".join(parts)


def _chunk(cmpl_id: str, created: int, model_name: str,
           delta: dict[str, Any], finish: str | None) -> str:
    data = json.dumps({"id": cmpl_id, "object": "chat.completion.chunk",
                       "created": created, "model": model_name,
                       "choices": [{"index": 0, "delta": delta,
                                    "finish_reason": finish}]},
                      ensure_ascii=False)
    return f"data: {data}\n\n"


def _thinking_generator(prompt: str, model: str | None) -> Iterator[str]:
    cmpl_id = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())
    model_name = model or DEFAULT_MODEL

    for phrase in THINK_PIECES:
        for word in phrase.split(" "):
            yield _chunk(cmpl_id, created, model_name,
                         {"thinking": word + " ", "reasoning_content": word + " "}, None)
            time.sleep(WORD_DELAY)
        time.sleep(PHRASE_PAUSE)

    yield _chunk(cmpl_id, created, model_name, {"content": FINAL_TEXT}, None)
    yield _chunk(cmpl_id, created, model_name, {}, "stop")
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions", response_model=None)
def completions(req: ChatRequest):
    prompt = _prompt_from_messages(req.messages)
    model_name = req.model or DEFAULT_MODEL

    if req.stream:
        return StreamingResponse(
            _thinking_generator(prompt, model_name),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    full_thinking = "\n".join(THINK_PIECES + [f"сообщение клиента: {prompt}"])
    answer = FINAL_TEXT
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": answer},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": len(prompt.split()),
                  "completion_tokens": len(answer.split()),
                  "total_tokens": len(prompt.split()) + len(answer.split())},
        "thinking": full_thinking,
        "reasoning_content": full_thinking,
    }


@app.post("/ingest/thinking", response_model=None)
def ingest_thinking(req: ThinkingIngest):
    return StreamingResponse(
        _thinking_generator(req.text, DEFAULT_MODEL),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
def root():
    return {"ok": True, "service": "zai-agent-think"}


@app.get("/health")
def health():
    return {"ok": True, "ready": True, "service": "zai-agent-think"}


@app.get("/v1/models")
def models():
    return {"object": "list",
            "data": [{"id": DEFAULT_MODEL, "object": "model",
                      "owned_by": "zai", "created": int(time.time())}]}


def _free_port(host: str, port: int) -> None:
    import socket
    probe = socket.socket()
    try:
        probe.bind((host, port))
        probe.close()
        return
    except OSError:
        pass
    finally:
        try:
            probe.close()
        except Exception:
            pass
    import subprocess
    for cmd in (["fuser", "-k", f"{port}/tcp"],
                ["pkill", "-f", f"thinking_server.py.*--port {port}"]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
            break
        except Exception:
            continue
    time.sleep(1.5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    _free_port(args.host, args.port)
    import uvicorn
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()

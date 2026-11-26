#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QwenChat Agent — FastAPI-агент для https://chat.qwen.ai/ с подробными логами.

Модель управления: FastAPI (поток) -> очередь -> ZaiWorker (поток браузера).
Агент извлекает ответ и мышление из DOM чата Qwen, выполняет файловые команды
[WRITE]/[EDIT]/[READ]/... и shell-команды [EXEC]...[/EXEC].

Настройки подключения (URL, профиль Chrome, модель) — в блоке Constants ниже.
Профиль Chrome по умолчанию: .../python_linux/work/google-chrome
(используется его последняя активная папка Profile 1 с сохранённой сессией).
"""
from __future__ import annotations

import argparse
import atexit
import json
import logging
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright
from openai import OpenAI

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Сайт, к которому подключается агент. Имя ZAI_URL оставлено как алиас для
# обратной совместимости со старыми вызовами/документацией.
QWEN_URL = "https://chat.qwen.ai/"
ZAI_URL = QWEN_URL
# Модель, выбранная в разметке страницы: [aria-label="Select Model"] -> Qwen3.7-Plus
DEFAULT_MODEL = "Qwen3.7-Plus"
# Профиль Chrome пользователя (куки/сессия Qwen лежат в Profile 1 этого профиля).
DEFAULT_PROFILE = ("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/"
                   "python_linux/work/google-chrome")
DEFAULT_CDP_PORT = 9224
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36")
LOG = logging.getLogger("qwen-agent")

# ---------------------------------------------------------------------------
# Локальная модель-исполнитель («руки»). Портировано из arena_agent.py,
# где эта схема проверена на реальных задачах.
# ---------------------------------------------------------------------------
DEFAULT_LOCAL_TOOL_URL = "http://127.0.0.1:8080/v1"
DEFAULT_LOCAL_TOOL_MODEL = "qwen3-4b-instruct-2507"
LOCAL_MODEL_LAUNCHER = (Path(__file__).resolve().parent /
                        "Локальная модель, которая запускается сервер.py")
LOCAL_MODEL_STATE_DIR = Path(
  os.environ.get("QWEN_AGENT_STATE_DIR", "~/.local/state/qwen-agent")
).expanduser()
LOCAL_MODEL_LOG = LOCAL_MODEL_STATE_DIR / "local_model.log"
LOCAL_MODEL_PID_FILE = LOCAL_MODEL_STATE_DIR / "local_model.pid"
_local_model_process: subprocess.Popen | None = None

LOCAL_TOOL_SYSTEM_PROMPT = (
  "You are a local tool-execution agent. You receive a single short "
  "instruction from a smarter model. Your ONLY job is to execute the "
  "instruction using your built-in tools, then report a concise result.\n"
  "Rules:\n"
  "1. Use the provided tools directly; do not narrate plans.\n"
  "2. If the instruction contains an exact command, path or content, pass it "
  "to the tool VERBATIM. Do not rewrite, shorten or translate it.\n"
  "3. After a tool returns, inspect rc/output. If it failed, try one minimal "
  "fix, then stop and report the error.\n"
  "4. When done, reply with a short line: DONE: <one-line summary>.\n"
  "5. Never run destructive commands (rm -rf /, mkfs, dd to /dev/*).\n"
  "6. Working directory: {workdir}\n"
)
LOCAL_TOOL_JSON_PROMPT = (
  "\n\n=== HOW TO CALL TOOLS ===\n"
  "Do NOT write shell commands as plain text and do NOT narrate. Answer with "
  "ONE JSON object and nothing else:\n"
  "{\"name\": \"<tool>\", \"arguments\": {...}}\n"
  "Examples:\n"
  "{\"name\": \"exec_shell_command\", \"arguments\": {\"command\": \"ls -la /tmp\"}}\n"
  "{\"name\": \"write_file\", \"arguments\": {\"path\": \"a.md\", \"content\": \"...\"}}\n"
  "{\"name\": \"read_file\", \"arguments\": {\"path\": \"a.md\"}}\n"
  "After you receive tool results and the task is done, answer with plain "
  "text: DONE: <short summary>. One tool call per message.\n"
)
KNOWN_LOCAL_TOOLS = {
  "exec_shell_command", "read_file", "write_file", "edit_file",
  "file_glob_search", "grep_search",
}
_LOCAL_TOOL_JSON_RE = re.compile(r"\{\s*\"(?:name|tool|function)\"\s*:")
_LOCAL_TOOL_FN_RE = re.compile(
  r"functions\.([a-z_]+)\s*:\s*(\{[\s\S]*?\})\s*(?=functions\.|$)", re.M
)

LOCAL_TOOLS_OPENAI = [
  {"type": "function", "function": {
   "name": "exec_shell_command",
   "description": "Execute a shell command locally. Returns stdout/stderr and rc.",
   "parameters": {"type": "object", "properties": {
    "command": {"type": "string", "description": "Bash command to execute."}},
                  "required": ["command"]}}},
  {"type": "function", "function": {
   "name": "read_file",
   "description": "Read a local file.",
   "parameters": {"type": "object", "properties": {
    "path": {"type": "string"}}, "required": ["path"]}}},
  {"type": "function", "function": {
   "name": "write_file",
   "description": "Create or overwrite a local file.",
   "parameters": {"type": "object", "properties": {
    "path": {"type": "string"}, "content": {"type": "string"}},
                  "required": ["path", "content"]}}},
  {"type": "function", "function": {
   "name": "edit_file",
   "description": "Replace an exact unique substring in a local file.",
   "parameters": {"type": "object", "properties": {
    "path": {"type": "string"}, "old_string": {"type": "string"},
    "new_string": {"type": "string"}},
                  "required": ["path", "old_string", "new_string"]}}},
  {"type": "function", "function": {
   "name": "file_glob_search",
   "description": "Find files matching a glob pattern.",
   "parameters": {"type": "object", "properties": {
    "pattern": {"type": "string"}, "path": {"type": "string"}},
                  "required": ["pattern"]}}},
  {"type": "function", "function": {
   "name": "grep_search",
   "description": "Search file contents for a pattern.",
   "parameters": {"type": "object", "properties": {
    "pattern": {"type": "string"}, "path": {"type": "string"},
    "case_sensitive": {"type": "boolean"}},
                  "required": ["pattern", "path"]}}},
]

# System profile file (attached to chat as a file on first message)
SYSTEM_PROFILE_PATH = "/home/egor/Downloads/fast_work/Deepseek_agent/Memory/system-profile.md"
# Tools reference, also attached to the chat as a file so the model reads it from the dialog
TOOLS_DOC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zai_tools.md")
AGENT_MAX_TOOL_ITERS = 6

# ---------------------------------------------------------------------------
# Optional backend tools
# ---------------------------------------------------------------------------
try:
 from backend import py_write_guard, json_repair_tool
except Exception:  # pragma: no cover
 py_write_guard = None
 json_repair_tool = None

# ---------------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------------
_DENY_TOOL = re.compile(
 r"\b(mkfs|fdisk|parted)\b|"
 r"\bdd\b[^\n;|]*\bof\s*=\s*/dev/(sd|nvme|hd)[a-z0-9]*\b|"
 r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+(/|/\s*\*|~)(\s|$)"
)
# Require CLOSING slash so we only catch real [EXEC]...[/EXEC] blocks
_EXEC_RE = re.compile(r"\[EXEC\][ \t]*\r?\n?([\s\S]*?)[ \t]*\r?\n?[ \t]*\[/(?:EXEC|RESULT)\]")
_FENCE_BASH_RE = re.compile(r"```(?:bash|sh|shell|console|zsh|cmd)\s*\r?\n([\s\S]*?)```", re.I)

# Explicit file operations (model controls exact path)
_FILE_WRITE_RE = re.compile(
 r"\[WRITE\s+path=[\"']?([^\"'\]\n]+?)[\"']?\s*\](.*?)\[/WRITE\]", re.S | re.I)
_FILE_EDIT_RE = re.compile(
 r"\[EDIT\s+path=[\"']?([^\"'\]\n]+?)[\"']?\s*\](.*?)\[/EDIT\]", re.S | re.I)
_FILE_APPEND_RE = re.compile(
 r"\[APPEND\s+path=[\"']?([^\"'\]\n]+?)[\"']?\s*\](.*?)\[/APPEND\]", re.S | re.I)
_FILE_REPLACE_RE = re.compile(
 r"\[REPLACE\s+path=[\"']?([^\"'\]\n]+?)[\"']?\s*\]\s*<<<OLD>>>(.*?)<<<NEW>>>(.*?)\[/REPLACE\]",
 re.S | re.I)
_FILE_READ_RE = re.compile(
 r"\[READ\s+path=[\"']?([^\"'\]\n]+?)[\"']?\]", re.I)
_FILE_DELETE_RE = re.compile(
 r"\[DELETE\s+path=[\"']?([^\"'\]\n]+?)[\"']?\]", re.I)
_FILE_LIST_RE = re.compile(
 r"\[LIST\s+path=[\"']?([^\"'\]\n]+?)[\"']?\]", re.I)

AGENT_FS_INSTRUCTION = (
 "[SYSTEM] You are a file-system coding agent with FULL access to the filesystem. "
 "You can CREATE, READ, EDIT, APPEND, REPLACE, DELETE files and LIST directories "
 "ANYWHERE on disk — and YOU decide every path yourself.\n"
 "A full tools reference is attached to this chat as the file 'zai_tools.md' — read it "
 "and follow its command format exactly. The model (you) is responsible for choosing "
 "the exact file path in every command; the agent does NOT guess or relocate paths.\n"
 "Key rules:\n"
 "- ALWAYS specify the exact path in each tool command. Quote paths with spaces or "
 "non-ASCII characters: \"/home/egor/Рабочий стол/calc.py\".\n"
 "- To create/overwrite a file: [WRITE path=\"...\"]...[/WRITE].\n"
 "- To edit a file: first [READ] it, then [EDIT] (full replace) or [REPLACE] (partial, any format).\n"
 "- To run code: write it with [WRITE], then run it with an [EXEC] shell command. "
 "Python blocks in your answer are NOT auto-saved or auto-run by the agent.\n"
 "- If an [EXEC] command fails (rc!=0): read the error, FIX the code (emit an updated "
 "[WRITE]/[EDIT]) and re-run. NEVER resubmit identical, already-failed code.\n"
 "- Max {max_iters} tool iterations.\n"
 "User request:\n"
)

# ---------------------------------------------------------------------------
# Local executor (small model) configuration
# ---------------------------------------------------------------------------
# Большая облачная модель = ТОЛЬКО планировщик: выдаёт инструкцию.
# Маленькая локальная модель (Qwen 1.5B) = исполнитель: читает инструкцию
# и через инструменты реально пишет/читает/меняет файлы и exec'ит.
LOCAL_PLANNER_INSTRUCTION = (
 "[SYSTEM] You are a PLANNER, not an executor. You do NOT write files, run "
 "commands, or use any tools — a local executor model performs the work.\n"
 "Given the user request below, output a CONCISE, ORDERED instruction telling "
 "the local executor exactly what to do: which files to create or modify (with "
 "full paths and the key content/outline), and which shell commands to run. "
 "Be concrete and unambiguous. Output ONLY the instruction text — no commentary, "
 "no code fences, no meta-explanation.\n"
 "User request:\n"
)

LOCAL_EXECUTOR_SYSTEM = (
 "You are a local file-system executor. You receive an INSTRUCTION from a larger "
 "planning model describing what to build or change. Your ONLY job is to execute "
 "it using the provided tools, in the correct order, until the instruction is "
 "complete.\n"
 "Rules:\n"
 "- Call the tools to actually perform each step; never only describe them.\n"
 "- Read a file before editing it (read_file, then write_file with new content).\n"
 "- Prefer absolute paths; quote paths containing spaces.\n"
 "- When the instruction is fully satisfied, respond with the single word DONE "
 "and make no tool calls.\n"
 "- Never explain; never add steps beyond the instruction.\n"
)

LOCAL_TOOL_SCHEMAS = [
 {"type": "function", "function": {
  "name": "write_file",
  "description": "Create or overwrite a file at the given path with the provided content.",
  "parameters": {"type": "object", "properties": {
   "path": {"type": "string", "description": "Absolute or work-dir-relative file path"},
   "content": {"type": "string", "description": "Full file content to write"}},
                 "required": ["path", "content"]}}},
 {"type": "function", "function": {
  "name": "read_file",
  "description": "Read a file's content.",
  "parameters": {"type": "object", "properties": {
   "path": {"type": "string", "description": "File path"}}, "required": ["path"]}}},
 {"type": "function", "function": {
  "name": "list_dir",
  "description": "List the contents of a directory.",
  "parameters": {"type": "object", "properties": {
   "path": {"type": "string", "description": "Directory path"}}, "required": ["path"]}}},
 {"type": "function", "function": {
  "name": "delete_file",
  "description": "Delete a file or an empty directory.",
  "parameters": {"type": "object", "properties": {
   "path": {"type": "string", "description": "Path to delete"}}, "required": ["path"]}}},
 {"type": "function", "function": {
  "name": "run_cmd",
  "description": "Run a shell command via bash and return its rc and output.",
  "parameters": {"type": "object", "properties": {
   "command": {"type": "string", "description": "Shell command to execute"}},
                 "required": ["command"]}}},
]

# ---------------------------------------------------------------------------
# JavaScript: extract {thinking, answer} from the LAST assistant message
# (the sibling that follows the LAST .user-message in the DOM).
# ---------------------------------------------------------------------------
# JS-экстрактор ответа из DOM. Поддерживает как chat.z.ai (старый режим), так и
# chat.qwen.ai: селекторы Qwen ([class*="assistant-message"], .markdown-body,
# .ql-editor, textarea.message-input-textarea и т.д.) добавлены первыми, а старые
# селекторы оставлены как фолбэки. Код собирается напрямую из <pre>/<code>, т.к.
# и Z.ai, и Qwen рендерят markdown без буквальных маркеров ``` в DOM.
EXTRACT_JS = r"""
() => {
  const norm = (s) => (s || '').replace(/\u00a0/g, ' ').trim();
  const isUser = (el) => {
    const c = (typeof el.className === 'string' ? el.className : '').toLowerCase();
    return (c.includes('user') && !c.includes('user-content')) || c.includes('user-message');
  };
  const visible = (el) => !!(el && el.getClientRects && el.getClientRects().length);

  // ---- 1) Ищем ПОСЛЕДНИЙ узел ответа ассистента ----
  let node = null;

  // A) Z.ai: подъём от последнего .thinking-chain-container.
  const tcs = document.querySelectorAll('.thinking-chain-container');
  if (tcs.length) {
    let n = tcs[tcs.length - 1], guard = 0;
    while (n && guard++ < 60) {
      const c = (typeof n.className === 'string') ? n.className : '';
      if (/message|assistant|bubble|response/i.test(c)) { node = n; break; }
      n = n.parentElement;
    }
  }

  // B) Qwen / универсальные явные контейнеры ассистента.
  if (!node) {
    const sels = [
      '[class*="assistant-message" i]', '[class*="assistant_message" i]',
      '[class*="bot-message" i]', '[class*="qwen-message" i]',
      '[class*="message-answer" i]', '[class*="answer-content" i]',
      '[class*="response-message" i]'
    ];
    const found = Array.from(document.querySelectorAll(sels.join(',')))
      .filter(el => visible(el) && !isUser(el));
    if (found.length) node = found[found.length - 1];
  }

  // C) Сосед после последнего сообщения пользователя.
  if (!node) {
    const users = Array.from(document.querySelectorAll(
      '.user-message, [class*="user-message" i], [class*="message-user" i]'
    )).filter(visible);
    if (users.length) {
      let n = users[users.length - 1].nextElementSibling, guard = 0;
      while (n && guard++ < 50) {
        const c = (typeof n.className === 'string') ? n.className : '';
        if (/message|assistant|response|content/i.test(c) && !isUser(n)) { node = n; break; }
        n = n.nextElementSibling;
      }
    }
  }

  // D) Последний не-user элемент с реальным текстом.
  if (!node) {
    const all = Array.from(document.querySelectorAll(
      '[class*="assistant" i], [class*="message" i], [class*="bot" i], ' +
      '[class*="response" i], [class*="markdown-body" i], .ql-editor'
    )).filter(el => visible(el) && !isUser(el) && norm(el.innerText).length > 0 &&
                    !el.closest('.qwen-thinking-selector, .message-input, .mode-select'));
    for (let k = all.length - 1; k >= 0; k--) {
      if (!/user/i.test(all[k].className || '')) { node = all[k]; break; }
    }
  }
  if (!node) return null;

  // ---- 2) Мышление: blockquote (Z.ai), [class*=think/reason] или details (Qwen) ----
  const thinkSel = 'blockquote, [class*="thinking-chain" i], [class*="thought" i], ' +
                   '[class*="think" i], [class*="reason" i], details';
  const tParts = [];
  node.querySelectorAll(thinkSel).forEach(el => {
    if (el.closest('.qwen-thinking-selector, .message-input')) return;
    const t = norm(el.innerText);
    if (t && !/^(thought process|thinking|思考|мышление|reasoning)\s*$/i.test(t) &&
        !tParts.some(x => t.includes(x) || x.includes(t))) tParts.push(t);
  });
  const thinking = tParts.join('\n\n');

  // ---- 3) Ответ (исключаем блоки мышления) ----
  const contentSel = '.text-start, .markdown-body, .ql-editor, ' +
                     '[class*="message-content" i], [class*="content" i], [class*="answer" i]';
  const parts = [];
  node.querySelectorAll(contentSel).forEach(el => {
    if (el.closest(thinkSel) || el.closest('.qwen-thinking-selector, .message-input')) return;
    const t = norm(el.innerText);
    if (t && !/^(thought process|thinking|思考|мышление|reasoning)/i.test(t) &&
        !parts.some(x => t.includes(x) || x.includes(t))) parts.push(t);
  });
  let answer = parts.join('\n\n');
  if (!answer) {
    const clone = node.cloneNode(true);
    clone.querySelectorAll(thinkSel).forEach(el => el.remove());
    answer = norm(clone.innerText);
  }

  // ---- 4) Блоки кода <pre>/<code> (fence-маркеров в DOM нет) ----
  const code = [], seen = new Set();
  node.querySelectorAll(
    'pre, pre code, code, [class*="code" i], [class*="hljs" i], [class*="language-" i]'
  ).forEach(el => {
    const t = norm(el.innerText);
    if (t && !seen.has(t)) { seen.add(t); code.push(t); }
  });

  // ---- 5) Ещё генерирует? Кнопка Stop (англ./рус./кит.) ----
  let generating = false;
  const stopSels = [
    'button[aria-label*="stop" i]', 'button[aria-label*="останов" i]',
    'button[aria-label*="停止" i]', '[data-testid*="stop" i]',
    '[class*="stop-button" i]', '[class*="stop_generate" i]'
  ];
  for (const s of stopSels) {
    const el = document.querySelector(s);
    if (visible(el)) { generating = true; break; }
  }

  return {thinking: thinking, answer: answer, code: code, generating: generating};
}
"""

# Раскрытие свёрнутого блока рассуждений: Z.ai (.thinking-chain-container с
# svg.-rotate-90) и Qwen/универсальные панели (details без open, aria-expanded=false).
# Возвращает строку с типом раскрытого блока или null.
THINK_EXPAND_JS = r"""
() => {
  const zc = document.querySelector('.thinking-chain-container');
  if (zc && zc.querySelector('svg.-rotate-90')) {
    const b = zc.querySelector('button');
    if (b) { b.click(); return 'zai'; }
  }
  const all = Array.from(document.querySelectorAll(
    'details, [aria-expanded="false"], [class*="think" i], [class*="reason" i]'
  ));
  for (const el of all) {
    if (!el.getClientRects || !el.getClientRects().length) continue;
    if (el.closest('.qwen-thinking-selector, .message-input, .mode-select, ' +
                   '[aria-label="Select Model"]')) continue;
    const collapsedDetails = el.tagName === 'DETAILS' && !el.open;
    const collapsedAria = el.getAttribute('aria-expanded') === 'false';
    const text = (el.innerText || '').trim();
    const arrow = el.querySelector('svg, [class*="arrow" i], [class*="chevron" i], ' +
                                   '[class*="rotate" i], [class*="down" i]');
    if (!(collapsedDetails || collapsedAria || (text.length < 60 && arrow))) continue;
    const btn = /^(BUTTON|SUMMARY|DETAILS)$/.test(el.tagName) || el.getAttribute('role') === 'button'
              ? el : (el.querySelector('button, [role="button"], summary') || el);
    btn.click();
    return 'qwen';
  }
  return null;
}
"""


# ---------------------------------------------------------------------------
# Локальный tool-агент («руки») и автозапуск модели
# ---------------------------------------------------------------------------
def _balanced_json_at(text: str, start: int) -> str | None:
  depth, in_str, esc = 0, False, False
  for i in range(start, len(text)):
    ch = text[i]
    if in_str:
      if esc:
        esc = False
      elif ch == "\\":
        esc = True
      elif ch == '"':
        in_str = False
      continue
    if ch == '"':
      in_str = True
    elif ch == "{":
      depth += 1
    elif ch == "}":
      depth -= 1
      if depth == 0:
        return text[start:i + 1]
  return None


def _parse_local_tool_json(text: str) -> list[dict[str, Any]]:
  out: list[dict[str, Any]] = []
  for m in _LOCAL_TOOL_JSON_RE.finditer(text or ""):
    raw = _balanced_json_at(text, m.start())
    if not raw:
      continue
    try:
      obj = json.loads(raw)
    except Exception:
      continue
    if not isinstance(obj, dict):
      continue
    fn = obj.get("function") if isinstance(obj.get("function"), dict) else obj
    name = str(fn.get("name") or fn.get("tool") or "").strip()
    if name not in KNOWN_LOCAL_TOOLS or any(c["name"] == name for c in out):
      continue
    args = fn.get("arguments", fn.get("parameters", {}))
    if isinstance(args, str):
      try:
        args = json.loads(args)
      except Exception:
        args = {"command": args} if name == "exec_shell_command" else {}
    if not isinstance(args, dict):
      args = {}
    out.append({"name": name, "arguments": args})
  if out:
    return out
  for m in _LOCAL_TOOL_FN_RE.finditer((text or "").replace("```", "")):
    name, raw = m.group(1), m.group(2)
    if name not in KNOWN_LOCAL_TOOLS:
      continue
    try:
      args = json.loads(raw)
    except Exception:
      continue
    out.append({"name": name, "arguments": args if isinstance(args, dict) else {}})
  return out


def _url_is_local(base_url: str) -> bool:
  return (urlparse(base_url).hostname or "") in ("127.0.0.1", "localhost", "::1")


def _url_port(base_url: str) -> int:
  try:
    return int(urlparse(base_url).port or 8080)
  except Exception:
    return 8080


def _local_model_is_ready(base_url: str, timeout: float = 4.0) -> list[str]:
  try:
    with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=timeout) as r:
      data = json.loads(r.read().decode("utf-8"))
    return [str(m.get("id", "")) for m in data.get("data", []) if m.get("id")]
  except Exception as e:
    LOG.debug("[LOCAL-TOOL] /models недоступен: %s", e)
    return []


def autostart_local_model(base_url: str, wait_seconds: float = 180.0) -> bool:
  """Поднимает лаунчер локальной модели, если /v1/models не отвечает.
  Никогда не бросает исключения: без модели агент работает с прямым исполнением.
  """
  global _local_model_process
  if _local_model_is_ready(base_url):
    LOG.info("[LOCAL-TOOL] локальная модель уже запущена: %s", base_url)
    return True
  if not _url_is_local(base_url):
    LOG.info("[LOCAL-TOOL] %s — удалённый адрес, локальный автозапуск пропущен", base_url)
    return False
  if not LOCAL_MODEL_LAUNCHER.is_file():
    LOG.warning("[LOCAL-TOOL] лаунчер не найден: %s", LOCAL_MODEL_LAUNCHER)
    return False
  if _local_model_process is None or _local_model_process.poll() is not None:
    try:
      LOCAL_MODEL_STATE_DIR.mkdir(parents=True, exist_ok=True)
      env = os.environ.copy()
      env.setdefault("PORT", str(_url_port(base_url)))
      env.setdefault("LLM_HOST", "127.0.0.1")
      env.setdefault("SERVER_TOOLS", "all")
      env.setdefault("LLM_GPU_LAYERS", "0")
      env.setdefault("LLM_THREADS", "8")
      env.setdefault("LLM_THREADS_BATCH", "16")
      env.setdefault("LLM_CTX", "8192")
      env.setdefault("CHAT_FORMAT", "chatml")
      with LOCAL_MODEL_LOG.open("ab") as logf:
        logf.write(
          f"\n===== {time.strftime('%F %T')} автозапуск из qwen_агент.py "
          f"(port={_url_port(base_url)}, python={sys.executable}) =====\n".encode("utf-8")
        )
        logf.flush()
        _local_model_process = subprocess.Popen(
          [sys.executable, str(LOCAL_MODEL_LAUNCHER)],
          cwd=str(LOCAL_MODEL_LAUNCHER.parent), env=env,
          stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT,
          start_new_session=True,
        )
      LOCAL_MODEL_PID_FILE.write_text(str(_local_model_process.pid), encoding="utf-8")
      LOG.info("[LOCAL-TOOL] автозапуск модели pid=%s port=%s log=%s",
               _local_model_process.pid, _url_port(base_url), LOCAL_MODEL_LOG)
    except Exception as e:
      LOG.warning("[LOCAL-TOOL] не удалось запустить модель: %s", e)
      return False
  else:
    LOG.info("[LOCAL-TOOL] модель уже стартует (pid=%s), жду...", _local_model_process.pid)
  deadline = time.time() + wait_seconds
  while time.time() < deadline:
    if _local_model_is_ready(base_url, timeout=8.0):
      LOG.info("[LOCAL-TOOL] локальная модель готова: %s", base_url)
      return True
    if _local_model_process is not None and _local_model_process.poll() is not None:
      LOG.warning("[LOCAL-TOOL] процесс модели завершился (rc=%s)", _local_model_process.returncode)
      return False
    time.sleep(2)
  LOG.warning("[LOCAL-TOOL] модель не ответила за %s сек; работаем без неё", wait_seconds)
  return False


def _shutdown_local_model() -> None:
  global _local_model_process
  proc = _local_model_process
  if proc is not None and proc.poll() is None:
    LOG.info("[LOCAL-TOOL] останавливаю локальную модель pid=%s", proc.pid)
    try:
      proc.terminate()
      proc.wait(timeout=10)
    except Exception:
      proc.kill()
  _local_model_process = None


def _local_model_watchdog(worker: Any, interval: float = 15.0) -> None:
  """Фоновая проверка: модель, не успевшая загрузиться к старту, может
  подняться позже — тогда переключаем агент с прямого режима на «руки»."""
  while True:
   time.sleep(interval)
   local = worker.local_tools
   if local is None or local.ready:
    continue
   try:
    if local.probe():
     worker.local_model_optional = False
     LOG.info("[LOCAL-TOOL] локальная модель стала доступна — переключаюсь на неё")
   except Exception as e:
    LOG.debug("[LOCAL-TOOL] watchdog probe failed: %s", e)


class LocalToolAgent:
  """«Руки»: локальная модель исполняет конкретные инструменты.

  Перенесено из arena_agent.py (проверенный протокол: JSON-вызов
  {"name", "arguments"} + результаты инструментов ролью "tool").
  """

  def __init__(self, base_url: str, model: str, work_dir: Path, worker: Any,
               tool_timeout: float = 300, max_iters: int = 8,
               request_timeout: float = 300) -> None:
    self.base_url = base_url.rstrip("/")
    self.model = model
    self.work_dir = work_dir
    self.worker = worker
    self.tool_timeout = tool_timeout
    self.max_iters = max_iters
    self.request_timeout = request_timeout
    self.ready = False
    self._models_cache: list[str] = []

  def _get_models(self, force: bool = False, timeout: float = 4.0) -> list[str]:
    if not force and self._models_cache:
      return self._models_cache
    ids = _local_model_is_ready(self.base_url, timeout)
    if ids:
      self._models_cache = ids
    return ids

  def _ensure_model_alias(self, ids: list[str] | None = None) -> bool:
    ids = ids if ids is not None else self._get_models(force=True)
    if not ids:
      return False
    if self.model in ids:
      return True
    old = self.model
    self.model = ids[0]
    LOG.warning("[LOCAL-TOOL] алиас '%s' не найден; использую '%s'", old, self.model)
    return True

  def probe(self, timeout: float = 6.0) -> bool:
    ids = self._get_models(force=True, timeout=timeout)
    if not ids:
      self.ready = False
      LOG.warning("[LOCAL-TOOL] сервер недоступен: %s", self.base_url)
      return False
    self._ensure_model_alias(ids)
    self.ready = True
    LOG.info("[LOCAL-TOOL] готов, модель=%s, доступны=%s", self.model, ", ".join(ids))
    return True

  def _post_chat(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {"model": self.model, "messages": messages, "temperature": 0.0,
               "max_tokens": 1536, "tools": LOCAL_TOOLS_OPENAI, "tool_choice": "auto"}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_exc: BaseException | None = None
    alias_retried = False
    for attempt in range(3):
      req = urllib.request.Request(
        self.base_url + "/chat/completions", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
      try:
        with urllib.request.urlopen(req, timeout=self.request_timeout) as r:
          return json.loads(r.read().decode("utf-8"))
      except urllib.error.HTTPError as e:
        detail = ""
        try:
          detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
          pass
        last_exc = RuntimeError(f"HTTP {e.code}: {detail or e.reason}")
        if not alias_retried and self._ensure_model_alias():
          alias_retried = True
          payload["model"] = self.model
          body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
          continue
      except Exception as e:
        last_exc = e
      if attempt < 2:
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"llama-server недоступен ({self.base_url}): {last_exc}")

  def _execute_local_tool(self, name: str, args: dict[str, Any]) -> tuple[int, str]:
    a = {k: str(v) for k, v in args.items()}
    if name == "exec_shell_command":
      cmd = a.get("command", "").strip()
      if not cmd:
        return 1, "exec_shell_command: пустая команда"
      if _DENY_TOOL.search(cmd):
        return 1, "Команда отклонена: входит в запрещённый список."
      return ZaiWorker.exec_tool_command(cmd, self.work_dir, self.tool_timeout)
    if name in ("read_file", "write_file", "edit_file"):
      try:
        p = ZaiWorker.resolve_safe(a.get("path", ""), self.work_dir)
      except Exception as e:
        return 1, f"Недопустимый путь: {e}"
      if name == "read_file":
        if not p.is_file():
          return 1, f"Файл не найден: {p}"
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) > 20000:
          text = text[:20000] + "\n…(обрезано)"
        return 0, text
      if name == "write_file":
        content = a.get("content", "")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return 0, f"OK: записано {len(content.encode('utf-8'))} байт в {p}"
      old, new = a.get("old_string", ""), a.get("new_string", "")
      if not p.is_file():
        return 1, f"Файл не найден: {p}"
      text = p.read_text(encoding="utf-8", errors="replace")
      if old not in text:
        return 1, "old_string не найден в файле"
      if text.count(old) > 1:
        return 1, f"old_string встречается {text.count(old)} раз — уточни контекст"
      text = text.replace(old, new, 1)
      if p.suffix == ".py":
        try:
          compile(text, str(p), "exec")
        except SyntaxError as e:
          return 1, f"Синтаксическая ошибка после замены, откат: {e}"
      p.write_text(text, encoding="utf-8")
      return 0, f"OK: замена в {p.name}"
    if name == "file_glob_search":
      import glob as _glob
      pattern, base = a.get("pattern", ""), a.get("path", "") or "."
      try:
        full = base if os.path.isabs(base) else str(self.work_dir / base)
      except Exception:
        full = str(self.work_dir)
      matches = sorted(_glob.glob(os.path.join(full, pattern), recursive=True))
      out = "\n".join(matches[:200]) if matches else "(нет совпадений)"
      return 0, f"{len(matches)} совпадений:\n{out}"
    if name == "grep_search":
      pattern = a.get("pattern", "")
      path = a.get("path", ".")
      flag = "--text" if a.get("case_sensitive", "true").lower() in ("true", "1", "yes") else "-i"
      full = path if os.path.isabs(path) else str(self.work_dir / path)
      try:
        proc = subprocess.run(
          ["grep", "-rn", flag, pattern, full] if os.path.isdir(full) else ["grep", "-n", flag, pattern, full],
          capture_output=True, text=True, timeout=30)
        out = (proc.stdout or "").strip()
        if len(out) > 3500:
          out = out[:3500] + "\n…(обрезано)"
        return 0, out or "(нет совпадений)"
      except Exception as e:
        return 1, f"grep error: {e}"
    return 1, f"Неизвестный инструмент: {name}"

  def verbatim_instruction(self, command: str) -> str:
   """Жёсткая инструкция: выполнить команду ДОСЛОВНО, без переформулирований."""
   return (
    "Run exactly this bash command with exec_shell_command.\n"
    f"command = {json.dumps(command, ensure_ascii=False)}\n"
    "Do not modify, shorten, translate or re-quote the command. "
    "Use the string value of command as the tool argument."
   )

  def execute(self, instruction: str, single_shot: bool = False) -> dict[str, Any]:
    system = LOCAL_TOOL_SYSTEM_PROMPT.format(workdir=self.work_dir) + LOCAL_TOOL_JSON_PROMPT
    messages: list[dict[str, Any]] = [
      {"role": "system", "content": system},
      {"role": "user", "content": instruction},
    ]
    tool_log: list[dict[str, Any]] = []
    final = instruction
    try:
      for i in range(self.max_iters):
        try:
          resp = self._post_chat(messages)
        except Exception as e:
          # llama_cpp.server иногда отвергает историю с role:"tool" (HTTP 500).
          # Если инструменты уже отработали — возвращаем их реальный вывод,
          # а не роняем всю задачу.
          if tool_log:
            LOG.warning("[LOCAL-TOOL] следующий запрос к модели упал, "
                        "использую сырой вывод инструментов: %s", str(e)[:300])
            parts = [f"[{c.get('name')} rc={c.get('rc')}]\n{c.get('output','')}"
                     for c in tool_log]
            final = "DONE: инструменты выполнены\n" + "\n".join(parts)
            break
          raise
        choice = (resp.get("choices") or [{}])[0]
        msg = choice.get("message", {}) or {}
        tool_calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        if not tool_calls:
          parsed = _parse_local_tool_json(content)
          if parsed:
            tool_calls = [
              {"id": f"call_{i}_{k}", "function": {
                "name": c["name"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
              for k, c in enumerate(parsed)
            ]
        if not tool_calls:
          final = (content or "").strip()
          if not final and tool_log:
            last = tool_log[-1]
            final = (f"DONE: {last['name']} rc={last['rc']}\n"
                     f"{str(last.get('output') or '')[:1500]}")
          if not final:
            final = "(локальная модель не вернула текст)"
          break
        messages.append({"role": "assistant", "content": content or "",
                         "tool_calls": tool_calls})
        for tc in tool_calls:
          fn = tc.get("function") or {}
          tname = fn.get("name", "")
          raw_args = fn.get("arguments", "{}")
          try:
            targs = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
          except Exception:
            targs = {}
          if not isinstance(targs, dict):
            targs = {}
          tc_id = tc.get("id") or f"call_{i}_{len(tool_log)}"
          if tname not in KNOWN_LOCAL_TOOLS:
            rc, out = 1, f"Неизвестный инструмент: {tname}"
          else:
            LOG.info("[LOCAL-TOOL] iter=%s call=%s args=%s", i + 1, tname,
                     json.dumps(targs, ensure_ascii=False)[:200])
            rc, out = self._execute_local_tool(tname, targs)
          tool_log.append({"iter": i + 1, "name": tname, "args": targs,
                           "rc": rc, "output": out[:500]})
          messages.append({"role": "tool", "tool_call_id": tc_id, "name": tname,
                           "content": f"rc={rc}\n{out}"})
        # Повторный запрос к llama_cpp.server с историей tool-calls часто падает
        # HTTP 500. Для одиночной команды он и не нужен: результат уже есть.
        if single_shot and tool_log:
          last = tool_log[-1]
          final = f"DONE: {last['name']} rc={last['rc']}\n{last.get('output') or ''}"
          break
      else:
        final = "(бюджет tool-loop исчерпан)"
    except Exception as e:
      LOG.warning("[LOCAL-TOOL] ошибка: %s", e)
      return {"answer": f"ОШИБКА локального tool-агента: {e}", "tool_calls": tool_log,
              "complete": False, "unavailable": True}
    return {"answer": final, "tool_calls": tool_log,
            "complete": bool(tool_log) or not instruction.strip()}

  def execute_direct(self, tc: dict[str, Any]) -> dict[str, Any]:
    name = str(tc.get("name", ""))
    args = tc.get("arguments") or {}
    if not isinstance(args, dict):
      args = {}
    try:
      rc, out = self._execute_local_tool(name, args)
      ok = rc == 0
      return {"answer": f"{'DONE' if ok else 'FAIL'}: прямое исполнение {name} (rc={rc})\n{out}",
              "tool_calls": [{"iter": 0, "name": name, "args": args, "rc": rc,
                              "output": out[:500]}],
              "complete": ok, "direct": True}
    except Exception as e:
      return {"answer": f"ОШИБКА прямого исполнения {name}: {e}",
              "tool_calls": [], "complete": False, "direct": True}

  def verify_artifact(self, path: str) -> dict[str, Any]:
    qpath = shlex.quote(str(path))
    if str(path).endswith(".py"):
      cmd = f"test -s {qpath} && {sys.executable} -m py_compile {qpath} && wc -c {qpath}"
    else:
      cmd = f"test -s {qpath} && wc -c {qpath}"
    task = ("Проверь, что файл существует и непуст, выполнив ровно эту команду:\n"
            f"command = {json.dumps(cmd)}\n"
            "Если rc=0 — ответь DONE: <размер>, иначе FAIL: <ошибка>.")
    return self.execute(task)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
# Схема запроса /ask (нестриминговый).
class AskRequest(BaseModel):
 message: str = Field(min_length=1)
 model: str | None = None
 timeout: float = Field(default=300, ge=10, le=900)


# Схема запроса смены модели.
class ModelRequest(BaseModel):
 model: str = Field(min_length=1)


# Схема OpenAI-совместимого чата.
class ChatRequest(BaseModel):
 model: str | None = None
 messages: list[dict[str, Any]] = Field(min_length=1)
 stream: bool = False
 temperature: float | None = None
 max_tokens: int | None = None


# Схема запроса произвольной shell-команды.
class ExecRequest(BaseModel):
 command: str = Field(min_length=1)
 timeout: float | None = None


# Схема запроса пути ФС.
class FsPathRequest(BaseModel):
 path: str = "."


# Схема запроса чтения файла.
class FsReadRequest(BaseModel):
 path: str = Field(min_length=1)
 max_chars: int = 20000


# Схема запроса записи файла.
class FsWriteRequest(BaseModel):
 path: str = Field(min_length=1)
 content: str = ""
 append: bool = False


# Схема запроса создания папки.
class FsMkdirRequest(BaseModel):
 path: str = Field(min_length=1)


# Схема запроса удаления.
class FsDeleteRequest(BaseModel):
 path: str = Field(min_length=1)


# Схема ингеста внешнего мышления (кусочки текста, которые агент обработает как ответ модели).
class ThinkingIngest(BaseModel):
 text: str = Field(min_length=1)


# Схема прямого задания локальному исполнителю (минуя облачную модель).
class ToolExecRequest(BaseModel):
 instruction: str = Field(min_length=1)
 tool: str | None = None
 timeout: float | None = None


# ---------------------------------------------------------------------------
# Job / Settings
# ---------------------------------------------------------------------------
# Задача для очереди воркера (тип, данные, событие готовности).
@dataclass
class Job:
 kind: str
 payload: dict[str, Any]
 done: threading.Event
 result: Any = None
 error: BaseException | None = None


# Параметры запуска браузера (профиль, модель, CDP-порт).
@dataclass
class BrowserSettings:
 profile: Path
 model: str
 cdp_port: int
 headed: bool
 url: str = QWEN_URL


_SYSTEM_PATH_GUARD = ("/etc", "/usr", "/sys", "/proc", "/boot", "/bin",
                      "/sbin", "/lib", "/lib64", "/var", "/")


# ===========================================================================
# ZaiWorker
# ===========================================================================
# Поток-воркер: держит браузер и исполняет запросы к чату (по умолчанию chat.qwen.ai).
class ZaiWorker(threading.Thread):
 
 @staticmethod
 def collapse_tool_tags(text: str) -> str:
  """Свёртка файловых тегов для итогового сообщения:
  [WRITE path="X"]...[/WRITE] (и EDIT/APPEND/REPLACE/READ/DELETE/LIST)
  заменяется на одно значение пути X. [EXEC] не трогаем."""
  text = _FILE_WRITE_RE.sub(lambda m: m.group(1).strip(), text)
  text = _FILE_EDIT_RE.sub(lambda m: m.group(1).strip(), text)
  text = _FILE_APPEND_RE.sub(lambda m: m.group(1).strip(), text)
  text = _FILE_REPLACE_RE.sub(lambda m: m.group(1).strip(), text)
  text = _FILE_READ_RE.sub(lambda m: m.group(1).strip(), text)
  text = _FILE_DELETE_RE.sub(lambda m: m.group(1).strip(), text)
  text = _FILE_LIST_RE.sub(lambda m: m.group(1).strip(), text)
  return text

 # Принимает внешний текст мышления (endpoint /ingest/thinking) и отдаёт его
 # в формате чанка, понятного SSE-генератору. Внедрение в сам чат не
 # поддерживается — метод добавлен, чтобы эндпоинт не падал с AttributeError.
 def send_thinking_to_agent(self, text: str) -> list[dict[str, Any]]:
  return [{"type": "thinking_delta", "delta": text}]

 # Выполняет shell-команду и возвращает (rc, вывод); блокирует опасные команды.
 # 24: exec_tool_command — выполняет shell-команду на хосте
 @staticmethod
 def exec_tool_command(cmd: str, work_dir: Path, timeout: float) -> tuple[int, str]:
  print("24: exec_tool_command — выполняет shell-команду на хосте")
  cmd = cmd.strip()
  LOG.info("[EXEC] running: %s", cmd[:300])
  
  if cmd.startswith("json_repair ") or cmd.startswith("validate_json "):
   if not json_repair_tool:
    return 1, "json_repair_tool unavailable"
   parts = cmd.split(maxsplit=1)
   sub, arg = parts[0], (parts[1].strip().strip("\"'") if len(parts) > 1 else "")
   if not arg:
    return 1, "No file path specified."
   if sub == "validate_json":
    ok, msg = json_repair_tool.validate_json_file(arg)
    return (0 if ok else 1), f"validate_json {arg}: {msg}"
   r = json_repair_tool.repair_json_file(arg, make_backup=True)
   note = f"json_repair {arg}: {r['message']}"
   if r.get("backed_up"):
    note += f" (backup: {r['backed_up']})"
   return (0 if r["ok"] else 1), note
  
  notes: list[str] = []
  if py_write_guard:
   try:
    cmd, ns = py_write_guard.rewrite_unsafe_py_writes(cmd)
    notes.extend(ns)
   except Exception as e:
    LOG.debug("[EXEC] py_write_guard rewrite error: %s", e)
  
  if _DENY_TOOL.search(cmd):
   LOG.warning("[EXEC] DENIED by blocklist: %s", cmd[:200])
   return 1, "Command denied (matches blocklist)."
  
  try:
   proc = subprocess.Popen(
    ["bash", "-c", cmd],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    cwd=work_dir,
    start_new_session=True,
    env={**os.environ},
   )
   try:
    output, _ = proc.communicate(timeout=timeout)
   except subprocess.TimeoutExpired:
    LOG.warning("[EXEC] timeout %ss, killing", timeout)
    try:
     os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
     proc.kill()
    output, _ = proc.communicate()
    return 124, f"Timed out ({timeout}s)."
  except Exception as e:
   LOG.exception("[EXEC] failed to run command")
   return 2, f"Failed: {e}"
  
  rc = proc.returncode
  
  if py_write_guard:
   for fn in (py_write_guard.guard_written_python_files,
              py_write_guard.verify_python_files,
              py_write_guard.invalid_python_files):
    try:
     res = fn(cmd)
     if fn.__name__.startswith("invalid") and res and rc == 0:
      rc = 3
      output = "INVALID PYTHON: " + "; ".join(res)
     elif isinstance(res, list):
      notes.extend(res)
    except Exception as e:
     LOG.debug("[EXEC] guard %s error: %s", fn.__name__, e)
  
  if json_repair_tool:
   try:
    for p in json_repair_tool._find_json_write_targets(cmd):
     ok, _ = json_repair_tool.validate_json_file(p)
     if not ok:
      r = json_repair_tool.repair_json_file(p, make_backup=True)
      notes.append(f"json_repair {p}: {r['message']}")
   except Exception as e:
    LOG.debug("[EXEC] json_repair error: %s", e)
  
  output = (output or "").strip()
  if len(output) > 3500:
   output = output[:3500] + "\n…(truncated)"
  if not output:
   output = "(no output)"
  if notes:
   output += "\n\n[py_write_guard]\n" + "\n".join(f"- {n}" for n in notes)
  LOG.info("[EXEC] rc=%s output.len=%d", rc, len(output))
  return rc, output
 
 # Нормализует путь: абсолютные разрешены везде, кроме системных каталогов.
 @staticmethod
 def resolve_safe(path_str: str, work_dir: Path) -> Path:
  """Resolve a path.

  - Absolute paths are allowed anywhere except a few critical system dirs.
  - Relative paths are resolved against work_dir.
  """
  p = Path(str(path_str).strip().strip('"').strip("'")).expanduser()
  if p.is_absolute():
   p = p.resolve()
   s = str(p)
   for bad in _SYSTEM_PATH_GUARD:
    if s == bad or s.startswith(bad + "/"):
     raise ValueError(f"Path blocked by safety policy: {p}")
   return p
  p = (work_dir / p).resolve()
  return p
 
 # ---------------------------------------------------------------------------
 # Chrome launcher
 # ---------------------------------------------------------------------------
 # Удаляет залипшие lock-файлы профиля Chrome перед запуском.
 @staticmethod
 def clean_profile_locks(profile: Path) -> None:
  if not profile.exists():
   return
  try:
   running = subprocess.run(
    ["pgrep", "-af", "--", f"--user-data-dir={profile}"],
    capture_output=True, text=True, timeout=3,
   ).stdout.strip()
   if running:
    return
  except Exception:
   pass
  for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
   try:
    (profile / name).unlink()
   except (FileNotFoundError, OSError):
    pass
 
 # Запускает Chrome в нужном профиле с CDP-портом для управления.
 @staticmethod
 def launch_chrome(settings: BrowserSettings) -> subprocess.Popen | None:
  if settings.cdp_port <= 0:
   LOG.info("[CHROME] cdp disabled")
   return None
  # Если браузер уже запущен с этим CDP-портом, повторный запуск с тем же
  # --user-data-dir лишь откроет вкладку и проигнорирует --remote-debugging-port.
  try:
   with urllib.request.urlopen(
     f"http://127.0.0.1:{settings.cdp_port}/json/version", timeout=1) as r:
    if r.status == 200:
     LOG.info("[CHROME] CDP port %s already open, reusing", settings.cdp_port)
     return None
  except Exception:
   pass
  settings.profile.mkdir(parents=True, exist_ok=True)
  ZaiWorker.clean_profile_locks(settings.profile)
  chrome = (shutil.which("google-chrome-stable") or
            shutil.which("google-chrome") or
            shutil.which("chromium"))
  if not chrome:
   raise RuntimeError("Chrome not found in PATH")
  cmd = [
   chrome,
   f"--user-data-dir={settings.profile}",
   f"--remote-debugging-port={settings.cdp_port}",
   "--remote-allow-origins=*",
   # --disable-blink-features=AutomationControlled убран намеренно: Chrome 157
   # показывает предупреждение о неподдерживаемом флаге. navigator.webdriver
   # скрывается мягко — через ctx.add_init_script() в run().
   # WebRtcHideLocalIpsWithMdns удалён: в Chrome 157 он вызывает баннер
   # «неподдерживаемый флаг командной строки» и агенту не нужен.
   f"--user-agent={DEFAULT_UA}",
   "--no-first-run",
   "--no-default-browser-check",
   "--disable-background-timer-throttling",
   "--disable-backgrounding-occluded-windows",
   "--disable-renderer-backgrounding",
   "--password-store=basic",
   "--use-fake-ui-for-media-stream",
   "--disable-popup-blocking",
   "--disable-dev-shm-usage",
   "--window-size=1200,900",
   "--new-window",
   settings.url,
  ]
  if not settings.headed:
   cmd.insert(1, "--headless=new")
  LOG.info("[CHROME] launching: %s", chrome)
  # Лог Chrome нужен, чтобы при медленном холодном старте (профиль 8 ГБ на FUSE)
  # было видно, что именно мешает открыть CDP.
  try:
   LOCAL_MODEL_STATE_DIR.mkdir(parents=True, exist_ok=True)
   chrome_log = (LOCAL_MODEL_STATE_DIR / "chrome.log").open("ab")
  except Exception:
   chrome_log = subprocess.DEVNULL
  proc = subprocess.Popen(cmd, stdout=chrome_log, stderr=subprocess.STDOUT)
  wait = float(os.environ.get("QWEN_CHROME_CDP_WAIT", "180"))
  deadline = time.time() + wait
  next_log = time.time() + 15
  while time.time() < deadline:
   if proc.poll() is not None:
    raise RuntimeError(f"Chrome exited early (rc={proc.returncode}), see {LOCAL_MODEL_STATE_DIR / 'chrome.log'}")
   try:
    with urllib.request.urlopen(f"http://127.0.0.1:{settings.cdp_port}/json/version", timeout=1) as r:
     if r.status == 200:
      LOG.info("[CHROME] CDP port open")
      return proc
   except Exception:
    pass
   if time.time() >= next_log:
    LOG.info("[CHROME] waiting for CDP port %s (%.0fs left)",
             settings.cdp_port, deadline - time.time())
    next_log = time.time() + 15
   time.sleep(0.5)
  proc.kill()
  raise RuntimeError(f"Chrome did not open CDP port in {wait:.0f}s, "
                     f"see {LOCAL_MODEL_STATE_DIR / 'chrome.log'}")
 
 # __init__: метод/функция агента.
 def __init__(self, settings: BrowserSettings, work_dir: Path,
              tool_timeout: float = 300, max_tool_iters: int = 6) -> None:
  super().__init__(name="zai-browser-worker", daemon=True)
  self.settings = settings
  self.work_dir = work_dir
  self.tool_timeout = tool_timeout
  self.max_tool_iters = max_tool_iters
  self.local_url = None
  self.local_model = None
  # Локальная модель-исполнитель («руки»). Создаётся в main() после автозапуска.
  self.local_tools: LocalToolAgent | None = None
  # Если модель не поднялась за отведённое время — не блокируем API навсегда,
  # работаем с прямым исполнением инструментов.
  self.local_model_optional = False
  self.max_exec_iters = 12
  self.jobs: queue.Queue[Job] = queue.Queue()
  self.stop_event = threading.Event()
  self.ready = threading.Event()
  # API открывается только когда страница полностью загружена и все нужные
  # элементы чата найдены (см. _wait_page_ready).
  self.page_ready = False
  self.start_error: BaseException | None = None
  self.page: Any = None
  self.browser: Any = None
  self.pw: Any = None
  self.selected_model = settings.model
  self._first_message = True
  self._system_profile = self._load_system_profile()
  self._last_stream_cmd = ""
  self._last_ask_cmd = ""
 
 # ---- Profile ----
 # Загружает текст системного профиля из файла (для прикрепления).
 # 8: _load_system_profile — читает текст системного профиля из файла
 def _load_system_profile(self) -> str:
  # print("8: _load_system_profile — читает текст системного профиля из файла")
  try:
   p = Path(SYSTEM_PROFILE_PATH)
   if p.exists():
    text = p.read_text(encoding="utf-8").strip()
    LOG.info("[PROFILE] loaded %d chars from %s", len(text), SYSTEM_PROFILE_PATH)
    return text
  except Exception as e:
   LOG.warning("[PROFILE] load failed: %s", e)
  return ""
 
 # Прикрепляет локальный файл в чат (эмуляция drag&drop).
 # 10: _attach_file — прикрепляет локальный файл в чат (drag&drop)
 def _attach_file(self, path: str) -> bool:
  # print("10: _attach_file — прикрепляет локальный файл в чат (drag&drop)")
  p = Path(path)
  if not p.exists():
   LOG.info("[ATTACH] nothing to attach: %s", path)
   return False
  try:
   # Qwen: скрытый <input id="filesUpload" aria-label="Upload files" multiple>.
   # Старый селектор input[type="file"] оставлен как фолбэк.
   file_input = self.page.locator(
    '#filesUpload, input[type="file"][aria-label="Upload files"], input[type="file"]').first
   if not file_input.count():
    LOG.warning("[ATTACH] no file input found")
    return False
   file_input.set_input_files(str(p))
   LOG.info("[ATTACH] set_input_files %s", path)
   for _ in range(10):
    self.page.wait_for_timeout(500)
    for sel in (
     f'text="{p.name}"',
     f'.message-input >> text="{p.name}"',
     f'[class*="file" i] >> text="{p.name}"',
     f'[class*="attach" i] >> text="{p.name}"',
    ):
     try:
      chip = self.page.locator(sel).first
      if chip.count() and chip.is_visible():
       LOG.info("[ATTACH] file chip appeared: %s", p.name)
       return True
     except Exception:
      pass
   # Qwen иногда не показывает чип, но файл уже передан в input — считаем
   # загрузку состоявшейся и продолжаем (иначе первый запрос блокировался бы).
   LOG.warning("[ATTACH] file chip not detected; assuming file uploaded: %s", p.name)
   return True
  except Exception as e:
   LOG.warning("[ATTACH] failed: %s", e)
   return False
 
 # Прикрепляет системный профиль как файл в диалог.
 # 7: _attach_system_profile — прикрепляет системный профиль как файл в чат
 def _attach_system_profile(self) -> bool:
  # print("7: _attach_system_profile — прикрепляет системный профиль как файл в чат")
  if not self._system_profile or not Path(SYSTEM_PROFILE_PATH).exists():
   LOG.info("[PROFILE] nothing to attach")
   return False
  return self._attach_file(SYSTEM_PROFILE_PATH)
 
 # Прикрепляет справку по инструментам (zai_tools.md) в диалог.
 # 9: _attach_tools_doc — прикрепляет zai_tools.md (справка по инструментам)
 def _attach_tools_doc(self) -> bool:
  # print("9: _attach_tools_doc — прикрепляет zai_tools.md (справка по инструментам)")
  if not Path(TOOLS_DOC_PATH).exists():
   LOG.info("[TOOLS-DOC] nothing to attach")
   return False
  return self._attach_file(TOOLS_DOC_PATH)
 
 # ---- Job submission ----
 # Синхронная отправка задачи воркеру и ожидание результата.
 def submit(self, kind: str, payload: dict[str, Any], timeout: float = 900) -> Any:
  job = Job(kind, payload, threading.Event())
  self.jobs.put(job)
  if not job.done.wait(timeout):
   raise TimeoutError("Worker timeout")
  if job.error:
   raise job.error
  return job.result
 
 # Отправка стриминговой задачи (результаты идут в очередь).
 # 5: submit_stream — ставит стриминговую задачу в очередь воркеру
 def submit_stream(self, prompt: str, model: str | None, chunk_queue: queue.Queue) -> None:
  print("5: submit_stream — ставит стриминговую задачу в очередь воркеру")
  job = Job("stream", {"prompt": prompt, "model": model, "queue": chunk_queue}, threading.Event())
  self.jobs.put(job)
 
 # ---- Main loop ----
 # Основной цикл воркера: Playwright+Chrome и обработка задач из очереди.
 # 2: run — цикл воркера: Playwright+Chrome, обработка задач из очереди
 def run(self) -> None:
  # print("2: run — цикл воркера: Playwright+Chrome, обработка задач из очереди")
  try:
   LOG.info("[WORKER] starting playwright + chrome")
   self.pw = sync_playwright().start()
   self.browser = self.pw.chromium.connect_over_cdp(
    f"http://127.0.0.1:{self.settings.cdp_port}")
   ctx = self.browser.contexts[0]
   # Берём вкладку, уже открывшую нужный сайт: Chrome запускается с URL чата,
   # поэтому page.goto() по тому же адресу только прерывает загрузку SPA.
   host = urlparse(self.settings.url).netloc
   chat_pages = [p for p in ctx.pages if urlparse(p.url).netloc == host]
   self.page = chat_pages[0] if chat_pages else (ctx.pages[0] if ctx.pages else ctx.new_page())
   # Работаем ровно с одной вкладкой: остальные (от прошлых запусков) закрываем,
   # чтобы воркер не перепутал страницу и чтобы окно было чистым.
   for p in list(ctx.pages):
    if p is not self.page:
     try:
      p.close()
      LOG.info("[WORKER] closed extra tab: %s", p.url)
     except Exception as e:
      LOG.debug("[WORKER] close tab failed: %s", e)
   ctx.add_init_script("""
              Object.defineProperty(navigator,'webdriver',{get:()=>false});
              Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
          """)
   self.page.on("crash", lambda: LOG.error("[PAGE] crashed"))
   self.page.on("pageerror", lambda e: LOG.error("[PAGE] JS error: %s", e))
   
   LOG.info("[WORKER] ensuring chat page: %s (current=%s)", self.settings.url, self.page.url)
   self._ensure_chat_page()
   self._wait_composer()
   # API открываем только после полной готовности страницы и её элементов
   if not self._wait_page_ready():
    LOG.warning("[WORKER] page not fully ready — API will report not ready")
   # self._dump_page_source()
   self.ready.set()
   LOG.info("[WORKER] ready (page_ready=%s)", self.page_ready)
   
   while not self.stop_event.is_set():
    try:
     job = self.jobs.get(timeout=0.5)
    except queue.Empty:
     continue
    try:
     LOG.info("[WORKER] handling job kind=%s", job.kind)
     self._ensure_page_alive()
     if job.kind == "ask":
      job.result = self._ask(job.payload["message"],
                             job.payload.get("model"),
                             job.payload.get("timeout", 300))
     elif job.kind == "model":
      job.result = {"model": self.selected_model}
     elif job.kind == "switch_model":
      job.result = self._switch_model_ui(job.payload["model"])
     elif job.kind == "new_chat":
      job.result = self._new_chat()
     elif job.kind == "dump_source":
      job.result = {"path": self._dump_page_source()}
     elif job.kind == "stream":
      prompt = job.payload["prompt"]
      model = job.payload.get("model")
      q = job.payload["queue"]
      if self._first_message:
       self._first_message = False
       if self._system_profile:
        self._attach_system_profile()
       self._attach_tools_doc()
      for chunk in self._ask_stream_raw(prompt, model, 900):
       q.put(chunk)
      q.put(None)
      job.result = {"ok": True}
     else:
      raise ValueError(f"Unknown job: {job.kind}")
    except BaseException as e:
     LOG.exception("[WORKER] job %s failed", job.kind)
     job.error = e
    finally:
     job.done.set()
  except BaseException as e:
   LOG.exception("[WORKER] FATAL")
   self.start_error = e
   self.ready.set()
 
 # ---- Helpers ----
 # Гарантирует, что активная вкладка находится на странице чата.
 # Chrome запускается сразу с URL чата, поэтому повторный goto по тому же
 # адресу часто падает с net::ERR_ABORTED (SPA сам меняет историю во время
 # загрузки). Если вкладка уже на нужном сайте — goto не делаем вообще.
 def _ensure_chat_page(self, force: bool = False) -> None:
  target = self.settings.url
  same = urlparse(self.page.url).netloc == urlparse(target).netloc
  if same and not force:
   LOG.info("[PAGE] уже на чате (%s), goto пропущен", self.page.url)
  else:
   try:
    # commit: ждём только начала навигации, дальше ждём DOM через _wait_composer
    self.page.goto(target, wait_until="commit", timeout=60000)
   except Exception as e:
    LOG.warning("[PAGE] goto прерван (%s); проверяем состояние вкладки", e)
  # Ждём, пока SPA отрендерит поле ввода (до 60 сек), без события навигации.
  deadline = time.time() + 60
  while time.time() < deadline:
   try:
    if self.page.locator(
      'textarea.message-input-textarea, textarea[placeholder], textarea'
    ).first.is_visible(timeout=500):
     return
   except Exception:
    pass
   self.page.wait_for_timeout(500)
  LOG.warning("[PAGE] поле ввода ещё не видно; продолжаем через _wait_composer")

 # Полная готовность страницы: API открывается ТОЛЬКО после того, как
 # загрузился document и на месте все элементы, с которыми работает агент.
 # Возвращает True, если всё найдено.
 def _wait_page_ready(self, timeout: float = 90) -> bool:
  self.page_ready = False
  required = (
   ("document complete", None),
   ("textarea", 'textarea.message-input-textarea, textarea[placeholder], textarea'),
   ("file input", '#filesUpload, input[type="file"]'),
   ("send area", '.message-input-right-button-send, .messageInputContainer'),
   ("model selector", '[aria-label="Select Model"], .wms-trigger'),
   ("new chat", '[aria-label="Новый чат"], [aria-label*="New chat" i]'),
  )
  deadline = time.time() + timeout
  missing: list[str] = []
  while time.time() < deadline:
   missing = []
   for name, selector in required:
    try:
     if selector is None:
      state = self.page.evaluate("() => document.readyState")
      if state != "complete":
       missing.append(name)
      continue
     loc = self.page.locator(selector).first
     if not loc.count():
      missing.append(name)
      continue
     # input[type=file] у Qwen скрыт (display:none) — для него достаточно наличия
     if "file" in selector:
      continue
     if not loc.is_visible(timeout=300):
      missing.append(name)
    except Exception:
     missing.append(name)
   if not missing:
    self.page_ready = True
    LOG.info("[PAGE] fully ready: document + %d elements", len(required) - 1)
    return True
   self.page.wait_for_timeout(500)
  LOG.warning("[PAGE] not fully ready, missing: %s", ", ".join(missing))
  return False

 # Проверка, что страница ещё жива. Если вкладку закрыли — пытаемся
 # пересоздать её из того же CDP-браузера и снова дождаться готовности.
 def _ensure_page_alive(self) -> None:
  if self.page is not None and not self.page.is_closed() and self.page_ready:
   return
  LOG.warning("[PAGE] page dead/closed, recreating...")
  self.page_ready = False
  if self.browser is None:
   raise RuntimeError("Browser is not connected")
  ctx = self.browser.contexts[0] if self.browser.contexts else None
  if ctx is None:
   raise RuntimeError("No browser context")
  self.page = next((p for p in ctx.pages if not p.is_closed()), None) or ctx.new_page()
  self._ensure_chat_page()
  if not self._wait_page_ready():
   raise RuntimeError("Chat page elements are not ready")
  self.ready.set()

 # Ждёт появления поля ввода (textarea) в чате.
 # 1: _wait_composer — ждёт появления поля ввода (textarea)
 def _wait_composer(self):
  print("1: _wait_composer — ждёт появления поля ввода (textarea)")
  # Qwen: textarea.message-input-textarea placeholder="Спросить Qwen".
  # Остальные селекторы — фолбэки (z.ai и разные версии вёрстки).
  for sel in ('textarea.message-input-textarea', 'textarea[placeholder]',
              'textarea', '#chat-input', '.messageInputContainer textarea'):
   try:
    loc = self.page.locator(sel).first
    loc.wait_for(state="visible", timeout=15000)
    # LOG.info("[COMPOSER] found via selector: %s", sel)
    return loc
   except Exception as e:
    LOG.debug("[COMPOSER] selector %s not found: %s", sel, e)
  raise RuntimeError("Composer (textarea) not found")
 
 # МЕХАНИЗМ «мышление -> агент»:
 # цикл опроса в _ask_stream_raw при каждом новом кусочке мышления вызывает эту функцию,
 # она отдаёт кусочек в стрим (yield), а _stream_generator упаковывает его в SSE-поле
 # reasoning_content + thinking — так мысль доезжает до клиента, как в thinking_server.py.
 # Генератор SSE: преобразует события воркера в чанки чата.
 # 4: _stream_generator — SSE-генератор: события воркера -> чанки чата
 def _stream_generator(self, prompt: str, model: str | None):
  # print("4: _stream_generator — SSE-генератор: события воркера -> чанки чата")
  cmpl_id = "chatcmpl-" + uuid.uuid4().hex
  created = int(time.time())
  model_name = model or self.selected_model or DEFAULT_MODEL
  q: queue.Queue = queue.Queue()
  self.submit_stream(prompt, model, q)
  LOG.info("[STREAM-GEN] started cmpl=%s", cmpl_id)
  try:
   while True:
    chunk = q.get(timeout=600)
    if chunk is None:
     break
    t = chunk.get("type", "delta")
    if t == "thinking_delta":
     data = json.dumps({"id": cmpl_id, "object": "chat.completion.chunk",
                        "created": created, "model": model_name,
                        "choices": [{"index": 0,
                                     "delta": {"thinking": chunk["delta"],
                                               "reasoning_content": chunk["delta"]},
                                     "finish_reason": None}]}, ensure_ascii=False)
     yield f"data: {data}\n\n"
    elif t == "answer_delta":
     data = json.dumps({"id": cmpl_id, "object": "chat.completion.chunk",
                        "created": created, "model": model_name,
                        "choices": [{"index": 0, "delta": {"content": chunk["delta"]},
                                     "finish_reason": None}]}, ensure_ascii=False)
     yield f"data: {data}\n\n"
    elif t == "done":
     data = json.dumps({"id": cmpl_id, "object": "chat.completion.chunk",
                        "created": created, "model": model_name,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                       ensure_ascii=False)
     yield f"data: {data}\n\n"
     yield "data: [DONE]\n\n"
     break
  except GeneratorExit:
   LOG.info("[STREAM-GEN] client disconnected")
  except Exception as e:
   LOG.warning("[STREAM-GEN] error: %s", e)
 
 # 14b: _thought_is_collapsed — True, если блок рассуждений скрыт (его надо раскрыть)
 def _thought_is_collapsed(self) -> bool:
  # Свёрнуто == блок рассуждений не виден. Если не удалось проверить — считаем свёрнутым.
  try:
   return not self.page.locator(".thinking-chain-container blockquote").first.is_visible(timeout=300)
  except Exception:
   return True
 
 def _ask_stream_raw(self, message: str, model: str | None, timeout: float):
  print("6: _ask_stream_raw — стриминговый запрос к модели + цикл инструментов")
  if not message.startswith("[RESULT]"):
   message = AGENT_FS_INSTRUCTION.format(
    max_iters=self.max_tool_iters) + message
  LOG.info("[STREAM] ===== start prompt.len=%d", len(message))
  last_model_answer = ""
  prev_tool_sig: str | None = None
  
  LOG.info("[STREAM-ROUND] sending message (%d chars)", len(message))
  composer = self._wait_composer()
  self._send_reliably(composer, message)
  deadline = time.time() + 1900
  last_answer = ""
  stable_since = 0.0
  poll = 0
  last_thought_click = 0.0
  saved_thought_dom = False
  last_thinking = ""
  for _ in range(30):
   self.page.wait_for_timeout(500)
   data = self._get_last_assistant_message()
   if data and (data.get("answer") or data.get("thinking")):
    thinking = data.get("thinking", "") or ""
    break
  
  print("11: _stream_one_round — раунд стрима: отправка, раскрытие Мышления, поток токенов")
  while time.time() < deadline:
   self.page.wait_for_timeout(300)
   data = self._get_last_assistant_message() or {}
   answer = data.get("answer", "") or ""
   poll += 1
   
   thinking = data.get("thinking", "") or ""
   if poll % 15 == 0:
    LOG.info("[STREAM-ROUND] poll=%d answer.len=%d thinking.len=%d code=%d",
             poll, len(answer), len(thinking), len(data.get("code", []) or []))
   
   # «Мышление»: раскрытие свёрнутой панели. Универсальный JS понимает и
   # Z.ai (.thinking-chain-container + svg.-rotate-90), и Qwen (details без open,
   # aria-expanded=false, панели с классом think/reason).
   # Кликаем только когда текст мышления ещё НЕ извлечён — так не возникает
   # открыл-закрыл-осцилляция на уже раскрытой панели.
   if not thinking and time.time() - last_thought_click > 1.5:
    try:
     opened = self.page.evaluate(THINK_EXPAND_JS)
     if opened:
      LOG.info("[МЫШЛЕНИЕ] раскрыто кликом: %s", opened)
    except Exception:
     pass
    last_thought_click = time.time()
   # сохранение DOM (однократное) отключено — включать при необходимости:
   # self._dump_page_source()
   # print("[DUMP] zai_page_source.html обновлён: реальный DOM с мышлением")
   
   if len(thinking) > len(last_thinking):
    delta = thinking[len(last_thinking):]
    last_thinking = thinking
    yield {"type": "thinking_delta", "delta": delta}
    if answer and len(answer) > len(last_answer):
     delta = answer[len(last_answer):]
     last_answer = answer
     stable_since = time.time()
     print(answer)
     # yield {"type": "answer_delta", "delta": delta}
   
   # if last_answer:
   #  LOG.warning("[STREAM-ROUND] timeout but answer present")
   #  input()
   
   # generating = data.get("generating", False)
   # stable_for = time.time() - stable_since if stable_since else 0
   # if not generating and stable_for >= 2.5 and last_answer:
   #  LOG.info("[STREAM-ROUND] FINAL answer.len=%d thinking.len=%d",
   #           len(last_answer), len(last_thinking))
   #  yield {"type": "done", "answer": self.collapse_tool_tags(last_answer), "thinking": last_thinking}
   #  return
   # yield {"type": "done", "answer": self.collapse_tool_tags(last_answer), "thinking": last_thinking, "complete": False}
   # else:
   #  LOG.warning("[STREAM-ROUND] NO CONTENT FOUND")
   #  try:
   #   self.page.screenshot(path="zai_stream_debug.png")
   #   LOG.warning("[STREAM-ROUND] screenshot -> zai_stream_debug.png")
   #  except Exception:
   #   pass
   # yield {"type": "done", "answer": "", "thinking": last_thinking, "error": "timeout"}
   #
   #
   #
   #
   #
   
   # for chunk in self._stream_one_round(message):
   
   #      if chunk["type"] == "done":
   #          answer = chunk.get("answer", "")
   #          last_thinking = chunk.get("thinking", "")
   # for iteration in range(self.max_tool_iters):
   #     LOG.info("[STREAM] tool-iteration=%d", iteration)
   #     answer = ""
   #     for chunk in self._stream_one_round(message):
   #      if chunk["type"] == "done":
   #          answer = chunk.get("answer", "")
   #          last_thinking = chunk.get("thinking", "")
   #      elif chunk["type"] in ("answer_delta", "thinking_delta"):
   #          yield chunk  # pass through to client
   #     LOG.info("[STREAM] got answer.len=%d", len(answer))
   #     if not answer:
   #         LOG.warning("[STREAM] empty answer and no code -> stop tool loop")
   #         self._dump_last_answer_html()
   #         break
   #     last_model_answer = answer
   #
   #     # Stop if the model emits the exact same actions as the previous round
   #     # (no progress) — avoids re-writing / re-running identical content.
   #     parsed = self._parse_tools(answer)
   #     ops = parsed
   #     cmds = parsed["cmds"]
   #     ops_sig = ops["signature"]
   #     if prev_tool_sig is not None and ops_sig == prev_tool_sig:
   #         LOG.warning("[STREAM] identical tool actions as previous round -> stop (no progress)")
   #         break
   #     prev_tool_sig = ops_sig
   #
   #     # 1) Explicit file WRITE / EDIT (any path, any extension)
   #     explicit = (ops["writes"] or ops["edits"] or ops["appends"]
   #                 or ops["replaces"] or ops["deletes"])
   #     for path, content in ops["writes"] + ops["edits"]:
   #         res = self._do_write_file(path, content, append=False)
   #         if res.get("ok"):
   #             yield {"type": "answer_delta",
   #                    "delta": f"\n[AGENT] Wrote file: {res['path']} ({res['bytes']} bytes)\n"}
   #         else:
   #             yield {"type": "answer_delta",
   #                    "delta": f"\n[AGENT] Write FAILED: {path}: {res.get('error')}\n"}
   #
   #     # 2) APPEND
   #     for path, content in ops["appends"]:
   #         res = self._do_write_file(path, content, append=True)
   #         if res.get("ok"):
   #             yield {"type": "answer_delta",
   #                    "delta": f"\n[AGENT] Appended to: {res['path']} ({res['bytes']} bytes)\n"}
   #         else:
   #             yield {"type": "answer_delta",
   #                    "delta": f"\n[AGENT] Append FAILED: {path}: {res.get('error')}\n"}
   #
   #     # 3) REPLACE (search & replace inside a file, any format)
   #     for path, old, new in ops["replaces"]:
   #         res = self._do_replace_file(path, old, new)
   #         if res.get("ok"):
   #             yield {"type": "answer_delta",
   #                    "delta": f"\n[AGENT] Replaced in: {res['path']}\n"}
   #         else:
   #             yield {"type": "answer_delta",
   #                    "delta": f"\n[AGENT] Replace FAILED: {path}: {res.get('error')}\n"}
   #
   #     # 4) DELETE
   #     for path in ops["deletes"]:
   #         res = self._do_delete_file(path)
   #         if res.get("ok"):
   #             yield {"type": "answer_delta",
   #                    "delta": f"\n[AGENT] Deleted: {res['path']}\n"}
   #         else:
   #             yield {"type": "answer_delta",
   #                    "delta": f"\n[AGENT] Delete FAILED: {path}: {res.get('error')}\n"}
   #
   #     # 5) READ -> feed file content back to the model
   #     if ops["reads"]:
   #         fb = ""
   #         for path in ops["reads"]:
   #             r = self._do_read_file(path)
   #             if r.get("ok"):
   #                 fb += f"\n[FILE]\n{path}\n---\n{r['content']}\n[/FILE]"
   #             else:
   #                 fb += f"\n[FILE-ERROR] {path}: {r.get('error')}"
   #         feedback = f"[RESULT] File contents:{fb}\n[/RESULT]"
   #         # Повторную отправку результата модели отключаем — однократное выполнение.
   #         break
   #
   #     # 6) LIST -> feed listing back to the model
   #     if ops["lists"]:
   #         fb = ""
   #         for path in ops["lists"]:
   #             r = self._do_list_dir(path)
   #             if r.get("ok"):
   #                 fb += f"\n[DIR]\n{path}\n---\n{r['listing']}\n[/DIR]"
   #             else:
   #                 fb += f"\n[DIR-ERROR] {path}: {r.get('error')}"
   #         feedback = f"[RESULT] Directory listing:{fb}\n[/RESULT]"
   #         # Повторную отправку результата модели отключаем — однократное выполнение.
   #         break
   #
   #     # 7) Shell commands (cmds уже распарсен в начале итерации)
   #     if not cmds:
   #         LOG.info("[STREAM] no [EXEC] -> tool loop done")
   #         break
   #     c = cmds[0]
   #     if c == self._last_stream_cmd:
   #         LOG.warning("[STREAM] same command repeated -> stop")
   #         break
   #     self._last_stream_cmd = c
   #     LOG.info("[STREAM-TOOL] exec: %s", c[:200])
   #     rc, out = self.exec_tool_command(c, self.work_dir, self.tool_timeout)
   #     yield {"type": "answer_delta", "delta": f"\n[AGENT] $ {c}\n{out}\n"}
   #     # Однократное выполнение: повторную отправку ошибки модели не делаем.
   #     break
   #
   # LOG.info("[STREAM] ===== finished")
   # yield {"type": "done", "answer": collapse_tool_tags(last_model_answer)}
 
 # Парсит все файловые команды [WRITE]/[EDIT]/[APPEND]/[REPLACE]/[READ]/[LIST]/[DELETE].
 # 16: _parse_tools — парсит [WRITE]/[EDIT]/[READ]/[LIST]/[DELETE] и [EXEC] из ответа за один проход
 def _parse_tools(self, text: str) -> dict[str, Any]:
  print("16: _parse_tools — парсит файловые операции и [EXEC] команды из ответа за один проход")
  ops = {
   "writes": [(m.group(1).strip(), m.group(2)) for m in _FILE_WRITE_RE.finditer(text)],
   "edits": [(m.group(1).strip(), m.group(2)) for m in _FILE_EDIT_RE.finditer(text)],
   "appends": [(m.group(1).strip(), m.group(2)) for m in _FILE_APPEND_RE.finditer(text)],
   "replaces": [(m.group(1).strip(), m.group(2), m.group(3)) for m in _FILE_REPLACE_RE.finditer(text)],
   "reads": [m.group(1).strip() for m in _FILE_READ_RE.finditer(text)],
   "deletes": [m.group(1).strip() for m in _FILE_DELETE_RE.finditer(text)],
   "lists": [m.group(1).strip() for m in _FILE_LIST_RE.finditer(text)],
  }
  cmds = []
  for m in _EXEC_RE.finditer(text):
   c = m.group(1).strip()
   if len(c) > 3:
    cmds.append(c)
  if not cmds:
   for m in _FENCE_BASH_RE.finditer(text):
    c = m.group(1).strip()
    if len(c) > 3:
     cmds.append(c)
  LOG.debug("[EXTRACT] exec commands found: %d", len(cmds))
  ops["cmds"] = cmds
  
  # Сигнатура всех действий одним куском — детект повторов без прогресса
  # (бывшая функция 25: _tool_signature, теперь считается здесь же).
  ops["signature"] = repr((ops["writes"], ops["edits"], ops["appends"],
                           ops["replaces"], ops["reads"], ops["deletes"],
                           ops["lists"], cmds))
  
  # Очищаем текст от тегов команд, чтобы выделить чистые мысли
  clean_thoughts = text
  clean_thoughts = _FILE_WRITE_RE.sub("", clean_thoughts)
  clean_thoughts = _FILE_EDIT_RE.sub("", clean_thoughts)
  clean_thoughts = _EXEC_RE.sub("", clean_thoughts)
  clean_thoughts = _FENCE_BASH_RE.sub("", clean_thoughts)
  ops["thoughts"] = clean_thoughts.strip()
  return ops
 
 # Сохраняет HTML страницы в файл для анализа разметки.
 def _dump_page_source(self, path: Path | None = None) -> str:
  try:
   html = self.page.content()
  except Exception as e:
   LOG.warning("[DUMP] content failed: %s", e)
   return ""
  if path is None:
   path = Path.cwd() / "zai_page_source.html"
  try:
   path.write_text(html, encoding="utf-8")
   LOG.info("[DUMP] written %s (%d bytes)", path, len(html))
  except Exception as e:
   LOG.warning("[DUMP] write failed: %s", e)
  return str(path)
 
 # Надёжно вставляет текст и нажимает кнопку/Enter отправки.
 # 13: _send_reliably — надёжно вставляет текст и жмёт отправку
 def _send_reliably(self, composer, text: str) -> None:
  print("13: _send_reliably — надёжно вставляет текст и жмёт отправку")
  LOG.info("[SEND] chars=%d", len(text))
  button = None
  # Qwen: кнопка отправки появляется в .message-input-right-button-send после ввода
  # текста. Исключаем кнопку голосового ввода (.omb__btn / #voice-input-button),
  # чтобы не нажать её вместо отправки.
  for sel in (
    '.message-input-right-button-send button:not(#voice-input-button)',
    '.message-input-right-button-send [role="button"]:not(.omb__btn)',
    '.message-input-right-button-send [class*="send" i]',
    'button[aria-label*="send" i]',
    'button[aria-label*="отправ" i]',
    'button[aria-label*="发送" i]',
    'button[type="submit"]',
    '.messageInputContainer button',
  ):
   try:
    loc = self.page.locator(sel).last
    if loc.count() and loc.is_visible():
     button = loc
     break
   except Exception:
    pass
  LOG.info("[SEND] send button found: %s", button is not None)
  
  for attempt in range(3):
   LOG.info("[SEND] attempt %d", attempt + 1)
   composer.click()
   composer.fill(text)
   deadline = time.time() + 5
   while time.time() < deadline:
    try:
     val = composer.input_value(timeout=700)
    except Exception:
     try:
      val = composer.inner_text(timeout=700)
     except Exception:
      break
    if val.strip() == text.strip():
     break
    self.page.wait_for_timeout(100)
   
   if button is not None:
    try:
     if button.is_enabled(timeout=2000):
      button.click(timeout=2000, no_wait_after=True)
      self.page.wait_for_timeout(1000)
      if self._wait_composer_cleared(composer, text, 8):
       LOG.info("[SEND] success via button")
       return
    except Exception as e:
     LOG.debug("[SEND] button click failed: %s", e)
   # fallback Enter
   LOG.info("[SEND] pressing Enter (fallback)")
   try:
    composer.press("Enter")
   except Exception:
    pass
   self.page.keyboard.press("Enter")
   self.page.wait_for_timeout(1000)
   if self._wait_composer_cleared(composer, text, 8):
    LOG.info("[SEND] success via Enter")
    return
   try:
    composer.click()
    self.page.keyboard.press("Control+A")
    self.page.keyboard.press("Delete")
   except Exception:
    pass
   self.page.wait_for_timeout(300)
  raise RuntimeError("Message not sent")
 
 # Ждёт, пока поле ввода очистится после отправки.
 def _wait_composer_cleared(self, composer, old_text: str, timeout: float) -> bool:
  deadline = time.time() + timeout
  while time.time() < deadline:
   try:
    val = composer.input_value(timeout=700)
   except Exception:
    try:
     val = composer.inner_text(timeout=700)
    except Exception:
     return True
   if val.strip() != old_text.strip():
    return True
   self.page.wait_for_timeout(200)
  return False

 # Отладка: сохраняет HTML узла ответа для анализа селекторов.
 def _dump_last_answer_html(self) -> None:
  try:
   html = self.page.evaluate(r"""
         () => {
           const all = document.querySelectorAll('[class*="assistant" i], [class*="message" i], [class*="bot" i]');
           for (let k = all.length - 1; k >= 0; k--) {
             const cls = (typeof all[k].className === 'string') ? all[k].className : '';
             if (!cls.toLowerCase().includes('user')) return all[k].outerHTML;
           }
           return '<no-node>';
         }
         """)
   if html:
    Path("zai_last_answer.html").write_text(html, encoding="utf-8")
    LOG.info("[DUMP-ANSWER] written zai_last_answer.html (%d bytes)", len(html))
  except Exception as e:
   LOG.warning("[DUMP-ANSWER] failed: %s", e)

 # 15: _get_last_assistant_message — забирает ответ модели из DOM (thinking/answer/code)
 def _get_last_assistant_message(self) -> dict[str, Any] | None:
  try:
   data = self.page.evaluate(EXTRACT_JS)
   if not data:
    LOG.debug("[EXTRACT] no answer node")
    return None
   LOG.debug("[EXTRACT] thinking.len=%d answer.len=%d generating=%s",
             len(data.get("thinking", "")), len(data.get("answer", "")),
             data.get("generating", False))
   return data
  except Exception as e:
   LOG.warning("[EXTRACT] evaluate failed: %s", e)
   return None


 # ---- Core ask (non-stream) ----
 # Отправляет сообщение и ждёт стабильного ответа модели.
 # 28: _ask_raw — нестрим: отправка и ожидание ответа модели
 def _ask_raw(self, message: str, model: str | None, timeout: float) -> dict[str, Any]:
  print("28: _ask_raw — нестрим: отправка и ожидание ответа модели")
  LOG.info("[ASK] msg.len=%d timeout=%s", len(message), timeout)
  composer = self._wait_composer()
  self._send_reliably(composer, message)
  LOG.info("[ASK] sent, extracting...")

  deadline = time.time() + timeout
  last_answer = ""
  stable_since = 0.0
  last_dbg = 0.0
  appeared = False
  empty_since = 0.0

  while time.time() < deadline:
   if self.page is None or self.page.is_closed():
    LOG.warning("[ANSWER] page closed during extraction")
    self.page_ready = False
    if last_answer:
     return {"model": self.selected_model or DEFAULT_MODEL,
             "answer": self.collapse_tool_tags(last_answer), "code": [], "complete": False}
    raise RuntimeError("Chat page was closed during answer extraction")
   self.page.wait_for_timeout(600)
   data = self._get_last_assistant_message() or {}
   candidate = data.get("answer", "") or ""
   generating = data.get("generating", False)
   stable_for = time.time() - stable_since if stable_since else 0
   # Логируем КАЖДЫЙ опрос, включая пустые — так видно, если экстрактор
   # потерял узел ответа и тихо крутится 5 минут без единой строки в логе.
   if time.time() - last_dbg >= 15:
    LOG.info("[ANSWER] stable=%.1fs generating=%s len=%d best=%d",
             stable_for, generating, len(candidate), len(last_answer))
    last_dbg = time.time()
   if candidate:
    appeared = True
    empty_since = 0.0
    # Никогда не уменьшаем ответ: Qwen может на время показать обрывок.
    # Лучший (самый длинный) текст сохраняем в last_answer.
    if len(candidate) > len(last_answer):
     LOG.info("[ANSWER] grew to %d chars", len(candidate))
     last_answer = candidate
     stable_since = time.time()
     continue
   elif appeared and not empty_since:
    empty_since = time.time()
   if last_answer:
    # Qwen сначала показывает служебные ~10 символов («Thinking…»), причём
    # generating может рано сброситься. Не финализируем короткий ответ:
    # ждём либо настоящий текст (>=40 символов), либо долгое отсутствие роста.
    if stable_for >= 3.0 and not generating and len(last_answer) >= 40:
     LOG.info("[ANSWER] FINAL %d chars", len(last_answer))
     return {"model": self.selected_model or DEFAULT_MODEL,
             "answer": self.collapse_tool_tags(last_answer), "code": data.get("code", [])}
    # generating у Qwen часто не сбрасывается — не ждём 900 секунд зря.
    if stable_for >= 30.0:
     LOG.warning("[ANSWER] no growth %.1fs (generating=%s), finalizing best %d chars",
                 stable_for, generating, len(last_answer))
     return {"model": self.selected_model or DEFAULT_MODEL,
             "answer": self.collapse_tool_tags(last_answer), "code": data.get("code", []),
             "complete": not generating}
    if empty_since and time.time() - empty_since >= 30.0:
     LOG.warning("[ANSWER] answer node disappeared, finalizing best %d chars", len(last_answer))
     return {"model": self.selected_model or DEFAULT_MODEL,
             "answer": self.collapse_tool_tags(last_answer), "code": [], "complete": False}
  if appeared and last_answer:
   LOG.warning("[ANSWER] timeout, returning partial %d chars", len(last_answer))
   return {"model": self.selected_model or DEFAULT_MODEL,
           "answer": self.collapse_tool_tags(last_answer), "code": [], "complete": False}
  raise TimeoutError("No answer from the chat page")
 
 # Нестриминговый запрос с инструментами и циклом правок файлов.
 # 29: _ask — нестриминговый запрос с инструментами
 def _extract_shell_command(self, text: str) -> str:
  """Достаёт из ответа сайта КОНКРЕТНУЮ команду, которую надо выполнить."""
  def clean(c: str) -> str:
   c = (c or "").strip().split("\n")[0].strip()
   # Qwen дописывает после команды прозу:
   # ls -la "/mnt/.../работа"Передать пользователю полный вывод...
   if c.count('"') >= 2:
    c = c[:c.rfind('"') + 1]
   elif c.count("'") >= 2:
    c = c[:c.rfind("'") + 1]
   return c.strip()
  ops = self._parse_tools(text or "")
  if ops["cmds"]:
   return clean(ops["cmds"][0])
  for c in re.findall(r"`([^`\n]+)`", text or ""):
   c = clean(c)
   if len(c) > 2 and re.search(
     r"\b(ls|cat|find|grep|echo|mkdir|cp|mv|rm|pwd|python3?|bash|wc|head|tail|"
     r"du|df|stat|file|chmod|curl|wget|git|sed|awk|tar|unzip|zip)\b|[/\~]", c):
    return c
  m = re.search(r"(?:команд[уы]?|command)\s*[:\-]?\s*[`\"']*(.+)", text or "", re.I)
  if m:
   c = clean(m.group(1).strip().strip("`\"' "))
   if c:
    return c
  return ""

 def _run_local_command(self, command: str, timeout: float) -> dict[str, Any]:
  """Локальная модель исполняет команду ДОСЛОВНО. Если она исказила
  команду — выполняем исходную команду с сайта напрямую."""
  agent = self.local_tools
  expected = command.strip()
  local_result = None
  used_local = False
  if agent is not None and agent.ready:
   try:
    local_result = agent.execute(agent.verbatim_instruction(expected), single_shot=True)
   except Exception as e:
    LOG.warning("[EXEC] локальная модель не справилась: %s", e)
  if local_result and local_result.get("tool_calls"):
   call = local_result["tool_calls"][0]
   got = str((call.get("args") or {}).get("command", "")).strip()
   if got == expected:
    used_local = True
    answer = ("[LOCAL RESULT]\nDONE: команда выполнена локальной моделью\n\n"
              f"[RAW OUTPUT]\n{call.get('output') or ''}\n[/LOCAL RESULT]")
    rc = int(call.get("rc", 1))
   else:
    LOG.warning("[EXEC] локальная модель изменила команду: %r -> %r; исполняю точную",
                got[:200], expected[:200])
  if not used_local:
   rc, out = ZaiWorker.exec_tool_command(expected, self.work_dir, self.tool_timeout)
   answer = ("[LOCAL RESULT]\nDONE: команда выполнена напрямую "
             "(локальная модель не сохранила команду дословно)\n\n"
             f"[RAW OUTPUT]\n{out}\n[/LOCAL RESULT] (rc={rc})")
  return {"model": agent.model if agent else "local", "answer": answer,
          "tool_calls": local_result.get("tool_calls", []) if local_result else [],
          "tool_count": 1, "complete": rc == 0, "command": expected}

 def _ask(self, message: str, model: str | None, timeout: float) -> dict[str, Any]:
  print("29: _ask — нестриминговый запрос (планировщик → локальный исполнитель)")
  if self._first_message:
   self._first_message = False
   if self._system_profile:
    self._attach_system_profile()
   self._attach_tools_doc()
  if self.local_tools is not None and self.local_tools.ready:
   # Облачная модель — «мозги» (планировщик), локальная — «руки» (исполнитель).
   message = LOCAL_PLANNER_INSTRUCTION + message
   raw = self._ask_raw(message, model, timeout)
   command = self._extract_shell_command(raw["answer"])
   if command:
    LOG.info("[ASK] точная команда от сайта: %s", command[:200])
    local = self._run_local_command(command, timeout)
   else:
    local = self._run_local_executor(raw["answer"], timeout)
   # Возвращаем результат локальных рук обратно в чат (как в arena_agent.py):
   # облачная модель даёт итоговый ответ, уже опираясь на реальный rc/stdout.
   try:
    feedback = ("[RESULT]\n" + local["answer"] + "\n[/RESULT]\n"
                "Based on the result above, give the final answer to the user. "
                "Do NOT repeat the instruction and do NOT emit tool commands.")
    final = self._ask_raw(feedback, model, min(timeout, 300))
    final["local_tools"] = local
    return final
   except Exception as e:
    LOG.warning("[ASK] local feedback to chat failed: %s", e)
    local["answer"] += ("\n\n[LOCAL-TOOLS] результат исполнен локальной моделью, "
                        "обратная связь с чатом недоступна.")
    return local
  if not message.startswith("[RESULT]"):
   message = AGENT_FS_INSTRUCTION.format(
    max_iters=self.max_tool_iters) + message
  raw = self._ask_raw(message, model, timeout)
  return self._run_tool_loop(raw["answer"], timeout, model, message)
 
 # ---- Tool helpers ----
 
 # ---- Generic file operations (create / read / edit any file) ----
 # Обёртка resolve_safe для путей из команд модели.
 # Создаёт/перезаписывает (или дописывает) файл по точному пути.
 # 17: _do_write_file — создаёт/перезаписывает файл по точному пути
 def _do_write_file(self, path_str: str, content: str, append: bool = False) -> dict[str, Any]:
  print("17: _do_write_file — создаёт/перезаписывает файл по точному пути")
  try:
   p = self._resolve_fs_path(path_str)
  except Exception as e:
   LOG.warning("[FS-WRITE] resolve failed: %s", e)
   return {"ok": False, "error": str(e)}
  try:
   p.parent.mkdir(parents=True, exist_ok=True)
   if append:
    with open(p, "a", encoding="utf-8") as f:
     f.write(content)
   else:
    p.write_text(content, encoding="utf-8")
  except Exception as e:
   LOG.warning("[FS-WRITE] write failed: %s", e)
   return {"ok": False, "error": str(e)}
  LOG.info("[FS-WRITE] -> %s (%d bytes, append=%s)", p, len(content), append)
  return {"ok": True, "path": str(p), "bytes": len(content)}
 
 def _resolve_fs_path(self, path_str: str) -> Path:
  return self.resolve_safe(path_str, self.work_dir)
 
 # Читает файл и возвращает содержимое (с ограничением размера).
 # 18: _do_read_file — читает файл, возвращает содержимое
 def _do_read_file(self, path_str: str, max_chars: int = 20000) -> dict[str, Any]:
  print("18: _do_read_file — читает файл, возвращает содержимое")
  try:
   p = self._resolve_fs_path(path_str)
  except Exception as e:
   return {"ok": False, "error": str(e)}
  if not p.exists():
   return {"ok": False, "error": f"not found: {p}"}
  try:
   text = p.read_text(encoding="utf-8", errors="replace")
  except Exception as e:
   return {"ok": False, "error": str(e)}
  if len(text) > max_chars:
   text = text[:max_chars] + "\n...[truncated]...\n"
  return {"ok": True, "path": str(p), "content": text}
 
 # Дописывает текст в конец файла.
 # 21: _do_append_file — дописывает текст в конец файла
 def _do_append_file(self, path_str: str, content: str) -> dict[str, Any]:
  print("21: _do_append_file — дописывает текст в конец файла")
  try:
   p = self._resolve_fs_path(path_str)
  except Exception as e:
   LOG.warning("[FS-APPEND] resolve failed: %s", e)
   return {"ok": False, "error": str(e)}
  try:
   p.parent.mkdir(parents=True, exist_ok=True)
   with open(p, "a", encoding="utf-8") as f:
    f.write(content)
  except Exception as e:
   LOG.warning("[FS-APPEND] failed: %s", e)
   return {"ok": False, "error": str(e)}
  LOG.info("[FS-APPEND] -> %s (%d bytes)", p, len(content))
  return {"ok": True, "path": str(p), "bytes": len(content)}
 
 # Точечная замена фрагмента внутри файла (любой формат).
 # 20: _do_replace_file — точечная замена фрагмента в файле
 def _do_replace_file(self, path_str: str, old: str, new: str) -> dict[str, Any]:
  print("20: _do_replace_file — точечная замена фрагмента в файле")
  try:
   p = self._resolve_fs_path(path_str)
  except Exception as e:
   return {"ok": False, "error": str(e)}
  if not p.exists():
   return {"ok": False, "error": f"not found: {p}"}
  try:
   text = p.read_text(encoding="utf-8", errors="replace")
  except Exception as e:
   return {"ok": False, "error": str(e)}
  if old not in text:
   return {"ok": False, "error": "OLD text not found in file (check verbatim match)"}
  text = text.replace(old, new, 1)
  try:
   p.write_text(text, encoding="utf-8")
  except Exception as e:
   return {"ok": False, "error": str(e)}
  LOG.info("[FS-REPLACE] -> %s", p)
  return {"ok": True, "path": str(p)}
 
 # Удаляет файл (пустую папку).
 # 22: _do_delete_file — удаляет файл/пустую папку
 def _do_delete_file(self, path_str: str) -> dict[str, Any]:
  print("22: _do_delete_file — удаляет файл/пустую папку")
  try:
   p = self._resolve_fs_path(path_str)
  except Exception as e:
   return {"ok": False, "error": str(e)}
  if not p.exists():
   return {"ok": False, "error": f"not found: {p}"}
  try:
   if p.is_dir():
    p.rmdir()  # refuses if not empty (safe)
   else:
    p.unlink()
  except Exception as e:
   return {"ok": False, "error": str(e)}
  LOG.info("[FS-DELETE] -> %s", p)
  return {"ok": True, "path": str(p)}
 
 # Возвращает список содержимого каталога.
 # 19: _do_list_dir — список содержимого каталога
 def _do_list_dir(self, path_str: str) -> dict[str, Any]:
  print("19: _do_list_dir — список содержимого каталога")
  try:
   p = self._resolve_fs_path(path_str)
  except Exception as e:
   return {"ok": False, "error": str(e)}
  if not p.exists():
   return {"ok": False, "error": f"not found: {p}"}
  if p.is_file():
   try:
    sz = p.stat().st_size
   except Exception:
    sz = -1
   return {"ok": True, "path": str(p), "listing": f"FILE: {p.name} ({sz} bytes)"}
  try:
   items = sorted(p.iterdir())
  except Exception as e:
   return {"ok": False, "error": str(e)}
  lines = [("D " if it.is_dir() else "F ") + it.name for it in items]
  return {"ok": True, "path": str(p),
          "listing": "\n".join(lines) if lines else "(empty)"}
 
 # Эвристика зацикливания по повторяющемуся хвосту ответа.
 # 26: _is_looping — эвристика зацикливания по хвосту ответа
 def _is_looping(self, text: str) -> bool:
  print("26: _is_looping — эвристика зацикливания по хвосту ответа")
  tail = text[-120:] if len(text) >= 120 else text
  return text.count(tail) >= 4
 
 # ---- Tool loop (non-stream) ----
 # Цикл инструментов (без стрима): пишет/правит файлы и шлёт [EXEC].
 # 30: _run_tool_loop — цикл инструментов (без стрима)
 def _run_tool_loop(self, answer: str, timeout: float, model: str | None, user_request: str = "") -> dict[str, Any]:
  print("30: _run_tool_loop — цикл инструментов (без стрима)")
  last = answer
  prev_tool_sig: str | None = None
  for i in range(self.max_tool_iters):
   LOG.info("[TOOL-LOOP] iter=%d", i)
   
   # Stop if the model emits the exact same actions as the previous round
   # (no progress) — avoids re-writing / re-running identical content.
   parsed = self._parse_tools(answer)
   ops = parsed
   cmds = parsed["cmds"]
   ops_sig = ops["signature"]
   if prev_tool_sig is not None and ops_sig == prev_tool_sig:
    LOG.warning("[TOOL-LOOP] identical tool actions as previous round -> stop (no progress)")
    break
   prev_tool_sig = ops_sig
   
   explicit = (ops["writes"] or ops["edits"] or ops["appends"]
               or ops["replaces"] or ops["deletes"])
   
   # 1) WRITE / EDIT (any path, any extension)
   for path, content in ops["writes"] + ops["edits"]:
    res = self._do_write_file(path, content, append=False)
    if res.get("ok"):
     last += f"\n[AGENT] Wrote file: {res['path']} ({res['bytes']} bytes)"
    else:
     last += f"\n[AGENT] Write FAILED: {path}: {res.get('error')}"
   
   # 2) APPEND
   for path, content in ops["appends"]:
    res = self._do_write_file(path, content, append=True)
    if res.get("ok"):
     last += f"\n[AGENT] Appended to: {res['path']} ({res['bytes']} bytes)"
    else:
     last += f"\n[AGENT] Append FAILED: {path}: {res.get('error')}"
   
   # 3) REPLACE (search & replace inside an existing file, any format)
   for path, old, new in ops["replaces"]:
    res = self._do_replace_file(path, old, new)
    if res.get("ok"):
     last += f"\n[AGENT] Replaced in: {res['path']}"
    else:
     last += f"\n[AGENT] Replace FAILED: {path}: {res.get('error')}"
   
   # 4) DELETE
   for path in ops["deletes"]:
    res = self._do_delete_file(path)
    if res.get("ok"):
     last += f"\n[AGENT] Deleted: {res['path']}"
    else:
     last += f"\n[AGENT] Delete FAILED: {path}: {res.get('error')}"
   
   # 5) READ -> feed content back to the model (another round)
   if ops["reads"]:
    fb = ""
    for path in ops["reads"]:
     r = self._do_read_file(path)
     if r.get("ok"):
      fb += f"\n[FILE]\n{path}\n---\n{r['content']}\n[/FILE]"
     else:
      fb += f"\n[FILE-ERROR] {path}: {r.get('error')}"
    feedback = f"[RESULT] File contents:{fb}\n[/RESULT]"
    # Повторную отправку результата модели отключаем — однократное выполнение.
    break
   
   # 6) LIST -> feed listing back to the model (another round)
   if ops["lists"]:
    fb = ""
    for path in ops["lists"]:
     r = self._do_list_dir(path)
     if r.get("ok"):
      fb += f"\n[DIR]\n{path}\n---\n{r['listing']}\n[/DIR]"
     else:
      fb += f"\n[DIR-ERROR] {path}: {r.get('error')}"
    feedback = f"[RESULT] Directory listing:{fb}\n[/DIR]"
    # Повторную отправку результата модели отключаем — однократное выполнение.
    break
   
   # Shell commands (cmds уже распарсен в начале итерации)
   if not cmds:
    LOG.info("[TOOL-LOOP] no [EXEC] commands -> done")
    break
   if self._is_looping(answer):
    LOG.warning("[TOOL-LOOP] loop detected, stopping")
    break
   c = cmds[0]
   if c == self._last_ask_cmd:
    LOG.warning("[TOOL-LOOP] same command repeated, stopping")
    break
   self._last_ask_cmd = c
   LOG.info("[TOOL-LOOP] exec: %s", c[:200])
   rc, out = self.exec_tool_command(c, self.work_dir, self.tool_timeout)
   # Однократное выполнение: повторную отправку ошибки модели не делаем.
   break
  
  return {"model": self.selected_model or DEFAULT_MODEL, "answer": last}
 
 # ---------------------------------------------------------------------------
 # Local executor (small model) — исполняет инструкцию облачного планировщика.
 # ---------------------------------------------------------------------------
 # Локальная модель (Qwen 1.5B) сама ведёт цикл инструментов: читает инструкцию
 # и через write_file/read_file/list_dir/delete_file/run_cmd реально меняет диск.
 def _run_local_executor(self, instruction: str, timeout: float) -> dict[str, Any]:
  print("EXEC: _run_local_executor — локальная модель исполняет инструкцию")
  agent = self.local_tools
  if agent is None:
   LOG.warning("[EXEC] local_tools не задан, возврат к детерминированному циклу")
   return self._run_tool_loop(instruction, timeout, None, "")
  if not agent.probe(timeout=min(8.0, max(2.0, timeout))):
   LOG.warning("[EXEC] локальная модель недоступна, возврат к детерминированному циклу")
   return self._run_tool_loop(instruction, timeout, None, "")
  result = agent.execute(instruction)
  if result.get("unavailable"):
   LOG.warning("[EXEC] локальный агент вернул ошибку: %s", result.get("answer"))
   return self._run_tool_loop(instruction, timeout, None, "")
  calls = result.get("tool_calls") or []
  raw = []
  for c in calls:
   raw.append(f"[{c.get('name')} rc={c.get('rc')}]\n{str(c.get('output') or '')[:1200]}")
  answer = (
   "[LOCAL RESULT]\n" + str(result.get("answer") or "") + "\n\n"
   "[RAW OUTPUT — фактический вывод инструментов, доверять ему]\n"
   + ("\n".join(raw) if raw else "(инструменты не вызывались)") + "\n"
   f"[/LOCAL RESULT] (tool calls: {len(calls)})"
  )
  LOG.info("[EXEC] локальный исполнитель завершён: model=%s calls=%d",
           agent.model, len(calls))
  return {"model": agent.model, "answer": answer, "tool_calls": calls,
          "tool_count": len(calls), "complete": bool(result.get("complete"))}
 
 # Диспетчер инструментов локальной модели: вызывает реальные FS/exec операции.
 def _local_tool_dispatch(self, name: str, args: dict[str, Any]) -> str:
  try:
   if name == "write_file":
    r = self._do_write_file(str(args.get("path", "")), str(args.get("content", "")), append=False)
    return json.dumps(r, ensure_ascii=False)
   if name == "read_file":
    r = self._do_read_file(str(args.get("path", "")))
    return json.dumps(r, ensure_ascii=False)
   if name == "list_dir":
    r = self._do_list_dir(str(args.get("path", ".")))
    return json.dumps(r, ensure_ascii=False)
   if name == "delete_file":
    r = self._do_delete_file(str(args.get("path", "")))
    return json.dumps(r, ensure_ascii=False)
   if name == "run_cmd":
    rc, out = self.exec_tool_command(str(args.get("command", "")), self.work_dir, self.tool_timeout)
    return json.dumps({"rc": rc, "output": out}, ensure_ascii=False)
   return json.dumps({"ok": False, "error": f"unknown tool: {name}"}, ensure_ascii=False)
  except Exception as e:
   return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
 
 # ---- Model switch ----
 # Надёжность: best-effort. Qwen выбирает модель через выпадающий список
 # [aria-label="Select Model"] (в разметке текущая модель Qwen3.7-Plus).
 # Если список не найден — возвращаем ok=False, но метка в API всё равно
 # обновляется вызывающей стороной.
 def _switch_model_ui(self, model: str) -> dict[str, Any]:
  result: dict[str, Any] = {"model": model, "ok": False}
  try:
   trigger = self.page.locator('[aria-label="Select Model"], .wms-trigger').first
   if not trigger.count():
    result["error"] = "Select Model trigger not found"
    return result
   trigger.click(timeout=3000)
   self.page.wait_for_timeout(400)
   for sel in (
    f'[role="option"]:text-is("{model}")',
    f'[role="listitem"]:text-is("{model}")',
    f'[class*="option" i]:text-is("{model}")',
    f'text="{model}"',
   ):
    try:
     opt = self.page.locator(sel).last
     if opt.count() and opt.is_visible():
      opt.click(timeout=3000)
      result["ok"] = True
      break
    except Exception:
     pass
   current = self.page.locator('.wms-trigger__text').first
   if current.count():
    result["current"] = current.inner_text().strip()
   LOG.info("[MODEL] switch -> %s: %s", model, result)
  except Exception as e:
   result["error"] = str(e)
   LOG.warning("[MODEL] switch failed: %s", e)
  return result

 # ---- New chat ----
 # Внутренний сброс чата (новый диалог) для воркера.
 def _new_chat(self) -> dict[str, Any]:
  self._first_message = True
  try:
   # Qwen: aria-label="Новый чат" (см. разметку страницы). Остальные — фолбэки.
   for sel in ('[aria-label="Новый чат"]', '[aria-label*="New chat" i]',
               'a[href="/chat/new"]', 'a[href="/"]',
               'a:has-text("New chat")', 'button:has-text("New chat")'):
    try:
     loc = self.page.locator(sel).first
     if loc.count() and loc.is_visible():
      loc.click()
      self.page.wait_for_timeout(2000)
      self._wait_composer()
      return {"ok": True}
    except Exception:
     pass
   self._ensure_chat_page(force=True)
   self.page.wait_for_timeout(3000)
   self._wait_composer()
   return {"ok": True}
  except Exception as e:
   LOG.warning("new chat failed: %s", e)
   raise


# ===========================================================================
# FastAPI app
# ===========================================================================
worker: ZaiWorker | None = None
app = FastAPI(title="ZaiChat Agent", version="3.0")


# GET / — проверка живости сервиса.
@app.get("/")
def root():
 return {"ok": True, "service": "qwen-agent"}


# Запросы к модели разрешаем ТОЛЬКО когда страница полностью загружена и
# все её элементы найдены. До этого /health показывает ready=false.
def _require_chat_ready() -> None:
 if worker is None:
  raise HTTPException(503, "Worker not running")
 if (not worker.ready.is_set() or not worker.page_ready or
     worker.page is None or worker.page.is_closed()):
  raise HTTPException(503, "Chat page is not ready yet")
 # Строгий порядок: сначала локальная модель, потом доступ к агенту.
 # Если модель не поднялась за отведённое время (local_model_optional=True)
 # или инструменты отключены — разрешаем прямой режим, иначе API висел бы
 # навсегда с 503 даже после того, как модель загрузится.
 if (worker.local_tools is not None and not worker.local_tools.ready
     and not worker.local_model_optional):
  raise HTTPException(503, "Local executor model is not ready yet")


# GET /health — готовность воркера, страницы и текущая модель.
@app.get("/health")
def health():
 page_alive = bool(worker and worker.page is not None and not worker.page.is_closed())
 page_ready = bool(worker and worker.page_ready and page_alive)
 local = worker.local_tools if worker else None
 local_ready = bool(local and local.ready)
 return {
  "ok": bool(worker and worker.start_error is None and page_ready and local_ready),
  "ready": bool(worker and worker.ready.is_set() and page_ready and local_ready),
  "page_ready": page_ready,
  "page_alive": page_alive,
  "local_model_ready": local_ready,
  "local_tool_model": local.model if local else None,
  "local_tool_url": local.base_url if local else DEFAULT_LOCAL_TOOL_URL,
  "model": worker.selected_model if worker else None,
 }


# GET /v1/models — список моделей (текущая модель).
@app.get("/v1/models")
def models():
 mid = worker.selected_model if worker else DEFAULT_MODEL
 return {"object": "list", "data": [{"id": mid, "object": "model",
                                     "owned_by": "qwen", "created": int(time.time())}]}


# POST /v1/change_model — переключает модель в UI чата.
@app.post("/model")
def change_model(req: ModelRequest):
 _require_chat_ready()
 try:
  result = worker.submit("switch_model", {"model": req.model}, 25)
 except Exception as e:
  LOG.warning("[API] model switch job failed: %s", e)
  result = {"ok": False, "error": str(e)}
 worker.selected_model = req.model
 LOG.info("[API] model changed -> %s (ui=%s)", req.model, result.get("ok"))
 result.setdefault("model", req.model)
 return result


# POST /v1/new_chat — начать новый чат.
@app.post("/new_chat")
def new_chat():
 if worker is None:
  raise HTTPException(503, "Worker not running")
 return worker.submit("new_chat", {}, 30)


# POST /dump_source — сохранить HTML страницы для отладки.
@app.post("/dump_source")
def dump_source():
 if worker is None:
  raise HTTPException(503, "Worker not running")
 return worker.submit("dump_source", {}, 30)


# POST /ask — нестриминговый запрос к модели с инструментами.
# 31: ask — HTTP /ask (нестриминговый вход)
@app.post("/ask")
def ask(req: AskRequest):
 print("31: ask — HTTP /ask (нестриминговый вход)")
 _require_chat_ready()
 LOG.info("[API] /ask message.len=%d", len(req.message))
 return worker.submit("ask", {"message": req.message, "model": req.model,
                              "timeout": req.timeout}, req.timeout + 30)


# POST /v1/chat/completions — OpenAI-совместимый вход (stream/non-stream).
# 3: completions — HTTP /v1/chat/completions (OpenAI-совместимый вход)
@app.post("/v1/chat/completions", response_model=None)
def completions(req: ChatRequest):
 # print("3: completions — HTTP /v1/chat/completions (OpenAI-совместимый вход)")
 _require_chat_ready()
 parts = []
 for item in req.messages:
  content = item.get("content", "")
  if isinstance(content, list):
   content = " ".join(str(x.get("text", x)) if isinstance(x, dict) else str(x)
                      for x in content)
  if str(content).strip():
   parts.append(str(content).strip())
 prompt = "\n\n".join(parts)
 LOG.info("[API] /v1/chat/completions stream=%s prompt.len=%d", req.stream, len(prompt))
 
 if req.stream:
  return StreamingResponse(
   worker._stream_generator(prompt, req.model),
   media_type="text/event-stream",
   headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
  )
 
 result = worker.submit("ask", {"message": prompt, "model": req.model,
                                "timeout": 900}, 930)
 answer = result["answer"]
 return {
  "id": "chatcmpl-" + uuid.uuid4().hex,
  "object": "chat.completion",
  "created": int(time.time()),
  "model": result.get("model", req.model or DEFAULT_MODEL),
  "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
               "finish_reason": "stop"}],
  "usage": {"prompt_tokens": len(prompt.split()),
            "completion_tokens": len(answer.split()),
            "total_tokens": len(prompt.split()) + len(answer.split())},
 }


# ---- File system endpoints ----
# POST /exec — выполнить shell-команду на хосте.
@app.post("/exec")
def exec_cmd(req: ExecRequest):
 if worker is None:
  raise HTTPException(503, "Worker not running")
 rc, out = worker.exec_tool_command(req.command, worker.work_dir, req.timeout or worker.tool_timeout)
 return {"rc": rc, "output": out}


# GET /tools/health — состояние локальной модели-исполнителя («рук»).
@app.get("/tools/health")
def tools_health():
 local = worker.local_tools if worker else None
 if local is None:
  return {"ok": False, "base_url": DEFAULT_LOCAL_TOOL_URL, "model": None,
          "available": [], "error": "local tools disabled"}
 ids = local._get_models(force=False)
 return {"ok": local.ready, "base_url": local.base_url, "model": local.model,
         "available": ids,
         "error": None if local.ready else "llama-server недоступен"}


# POST /tools/exec — прямое задание локальному исполнителю (минуя облачный чат).
@app.post("/tools/exec")
def tools_exec(req: ToolExecRequest):
 if worker is None or worker.local_tools is None:
  raise HTTPException(503, "Local tools unavailable")
 local = worker.local_tools
 if req.tool:
  result = local.execute_direct({"name": req.tool, "arguments": {}})
 else:
  result = local.execute(req.instruction)
 return result


# POST /ingest/thinking — принять кусочки мышления извне и прогнать через инструменты агента.
@app.post("/ingest/thinking")
def ingest_thinking(req: ThinkingIngest):
 if worker is None:
  raise HTTPException(503, "Worker not running")
 return {"ok": True,
         "chunks": [c["delta"] for c in worker.send_thinking_to_agent(req.text)]}


# GET /fs/list — список каталога.
@app.post("/fs/list")
def fs_list(req: FsPathRequest):
 if worker is None:
  raise HTTPException(503, "Worker not running")
 p = worker.resolve_safe(req.path, worker.work_dir)
 if not p.exists():
  raise HTTPException(404, "Not found")
 if p.is_file():
  return {"ok": True, "path": str(p), "type": "file", "size": p.stat().st_size}
 return {"ok": True, "path": str(p), "type": "dir",
         "entries": [{"name": e.name, "type": "dir" if e.is_dir() else "file",
                      "size": e.stat().st_size if e.is_file() else None}
                     for e in sorted(p.iterdir())]}


# GET /fs/read — чтение файла.
@app.post("/fs/read")
def fs_read(req: FsReadRequest):
 if worker is None:
  raise HTTPException(503, "Worker not running")
 p = worker.resolve_safe(req.path, worker.work_dir)
 if not p.is_file():
  raise HTTPException(400, "Not a file")
 text = p.read_text(encoding="utf-8", errors="replace")
 if len(text) > req.max_chars:
  text = text[:req.max_chars] + "\n...(truncated)"
 return {"ok": True, "path": str(p), "content": text}


# POST /fs/write — запись файла.
@app.post("/fs/write")
def fs_write(req: FsWriteRequest):
 if worker is None:
  raise HTTPException(503, "Worker not running")
 p = worker.resolve_safe(req.path, worker.work_dir)
 p.parent.mkdir(parents=True, exist_ok=True)
 with open(p, "a" if req.append else "w", encoding="utf-8") as f:
  f.write(req.content)
 return {"ok": True, "path": str(p), "bytes": len(req.content.encode("utf-8"))}


# POST /fs/mkdir — создание каталога.
@app.post("/fs/mkdir")
def fs_mkdir(req: FsMkdirRequest):
 if worker is None:
  raise HTTPException(503, "Worker not running")
 p = worker.resolve_safe(req.path, worker.work_dir)
 p.mkdir(parents=True, exist_ok=True)
 return {"ok": True, "path": str(p)}


# POST /fs/delete — удаление файла/папки.
@app.post("/fs/delete")
def fs_delete(req: FsDeleteRequest):
 if worker is None:
  raise HTTPException(503, "Worker not running")
 p = worker.resolve_safe(req.path, worker.work_dir)
 if p == worker.work_dir.resolve():
  raise HTTPException(400, "Cannot delete work_dir")
 if p.is_dir():
  shutil.rmtree(p)
 elif p.is_file():
  p.unlink()
 else:
  raise HTTPException(404, "Not found")
 return {"ok": True, "path": str(p)}


# ===========================================================================
# Main
# ===========================================================================
# Точка входа: запуск браузера, воркера и FastAPI-сервера.
# 1: main — запуск: браузер, воркер, FastAPI-сервер
def main():
 # print("1: main — запуск: браузер, воркер, FastAPI-сервер")
 global worker
 parser = argparse.ArgumentParser()
 parser.add_argument("--host", default="127.0.0.1")
 parser.add_argument("--port", type=int, default=8001)
 parser.add_argument("--model", default=DEFAULT_MODEL)
 parser.add_argument("--profile", default=DEFAULT_PROFILE,
                     help="Папка профиля Chrome (по умолчанию: work/google-chrome)")
 parser.add_argument("--url", default=QWEN_URL,
                     help="URL чата (по умолчанию: https://chat.qwen.ai/)")
 parser.add_argument("--cdp-port", type=int, default=DEFAULT_CDP_PORT)
 parser.add_argument("--headless", action="store_true")
 parser.add_argument("--work-dir", default="/")
 parser.add_argument("--tool-timeout", type=float, default=300)
 parser.add_argument("--max-tool-iters", type=int, default=6)
 parser.add_argument("--local-url", default=None,
                     help="Алиас --local-tool-url (обратная совместимость)")
 parser.add_argument("--local-model", default=None,
                     help="Алиас --local-tool-model")
 parser.add_argument("--local-tool-url", default=None,
                     help="OpenAI-совместимый адрес локальной модели-исполнителя "
                          "(по умолчанию http://127.0.0.1:8080/v1)")
 parser.add_argument("--local-tool-model", default=None,
                     help="Алиас модели локального исполнителя (определяется сам)")
 parser.add_argument("--local-autostart-timeout", type=float, default=180.0,
                     help="Сколько секунд ждать загрузку локальной модели")
 parser.add_argument("--no-local-autostart", action="store_true",
                     help="Не запускать локальную модель автоматически")
 parser.add_argument("--max-exec-iters", type=int, default=12)
 args = parser.parse_args()
 
 log_file = Path.cwd() / "zai_agent.log"
 # INFO идёт только в файл zai_agent.log, чтобы не засорять консоль (print-трассировка читается чисто).
 # На консоль выводим только WARNING и выше.
 _console = logging.StreamHandler()
 _console.setLevel(logging.WARNING)
 _file = logging.FileHandler(log_file, encoding="utf-8")
 _file.setLevel(logging.INFO)
 logging.basicConfig(level=logging.INFO,
                     format="%(asctime)s %(levelname)s %(message)s",
                     handlers=[_console, _file])
 logging.getLogger("playwright").setLevel(logging.WARNING)
 LOG.info("[BOOT] logs -> %s", log_file)
 
 profile = Path(args.profile).expanduser()
 work_dir = Path(args.work_dir).expanduser()

 # 1) СНАЧАЛА поднимаем локальную модель-исполнителя («руки»).
 # Это сделано до запуска Chrome: к моменту открытия чата модель уже грузится.
 local_tool_url = args.local_tool_url or args.local_url or DEFAULT_LOCAL_TOOL_URL
 local_tool_model = (args.local_tool_model or args.local_model or
                     DEFAULT_LOCAL_TOOL_MODEL)
 autostart_enabled = (
  not args.no_local_autostart and
  os.environ.get("QWEN_LOCAL_AUTOSTART", "1") != "0" and
  os.environ.get("LOCAL_MODEL_AUTOSTART", "1") != "0"
 )
 local_ready = False
 if autostart_enabled:
  LOG.info("[BOOT] автозапуск локальной модели: %s", local_tool_url)
  local_ready = autostart_local_model(local_tool_url, args.local_autostart_timeout)
 else:
  LOG.info("[BOOT] автозапуск локальной модели отключён")
 if _local_model_process is not None:
  atexit.register(_shutdown_local_model)

 # 2) Создаём воркер (пока без браузера). HTTP API поднимется РАНЬШЕ браузера,
 # чтобы адрес подключения был виден сразу, а запросы до готовности чата
 # получали честный 503 вместо тишины.
 worker = ZaiWorker(
  BrowserSettings(profile, args.model, args.cdp_port, not args.headless, args.url),
  work_dir=work_dir,
  tool_timeout=args.tool_timeout,
  max_tool_iters=args.max_tool_iters,
 )
 # Подключаем «руки» к воркеру. Проба ещё раз проверяет /v1/models.
 worker.local_tools = LocalToolAgent(
  local_tool_url, local_tool_model, work_dir, worker,
  tool_timeout=args.tool_timeout, max_iters=args.max_exec_iters)
 worker.local_url = local_tool_url if local_ready else None
 worker.local_model = local_tool_model
 worker.max_exec_iters = args.max_exec_iters
 if not worker.local_tools.probe():
  LOG.warning("[BOOT] локальная модель недоступна — задачи будут исполняться напрямую")
  worker.local_model_optional = True
  threading.Thread(target=_local_model_watchdog, args=(worker,),
                   name="local-model-watchdog", daemon=True).start()

 # 3) Поднимаем API и сразу печатаем адрес в консоль.
 import uvicorn
 _uv_log_config = {
  "version": 1,
  "disable_existing_loggers": False,
  "formatters": {
   "default": {
    "()": "uvicorn.logging.DefaultFormatter",
    "fmt": "%(levelprefix)s %(message)s",
   },
  },
  "handlers": {
   "default": {
    "formatter": "default",
    "class": "logging.StreamHandler",
    "stream": "ext://sys.stderr",
   },
  },
  "loggers": {
   "uvicorn.error": {"level": "WARNING", "handlers": ["default"], "propagate": False},
   "uvicorn.access": {"level": "INFO", "handlers": ["default"], "propagate": False},
  },
 }
 config = uvicorn.Config(app, host=args.host, port=args.port, log_config=_uv_log_config)
 server = uvicorn.Server(config)
 api_thread = threading.Thread(target=server.run, name="api-server", daemon=True)
 api_thread.start()
 time.sleep(1.5)
 _display_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
 if args.host in ("0.0.0.0", "::"):
  try:
   _ips = [x for x in subprocess.run(
    ["hostname", "-I"], capture_output=True, text=True, timeout=3
   ).stdout.split() if x and not x.startswith("127.")]
   for _ip in _ips:
    print(f"[QWEN-AGENT] Из локальной сети: http://{_ip}:{args.port}/v1/chat/completions",
          flush=True)
  except Exception:
   pass
 print("\n" + "=" * 64, flush=True)
 print(f"[QWEN-AGENT] АДРЕС ПОДКЛЮЧЕНИЯ: http://{_display_host}:{args.port}/v1/chat/completions",
       flush=True)
 print(f"[QWEN-AGENT] Проверка готовности: http://{_display_host}:{args.port}/health",
       flush=True)
 print(f"[QWEN-AGENT] Локальная модель: {local_tool_url} "
       f"({'готова' if worker.local_tools.ready else 'ещё грузится'})", flush=True)
 print("[QWEN-AGENT] Сейчас запускается браузер и открывается чат Qwen...", flush=True)
 print("=" * 64 + "\n", flush=True)
 LOG.info("[SERVER] ready at http://%s:%s", args.host, args.port)

 # 4) Затем браузер и воркер чата.
 if args.cdp_port > 0:
  ZaiWorker.launch_chrome(BrowserSettings(profile, args.model, args.cdp_port,
                                         not args.headless, args.url))
 worker.start()
 if not worker.ready.wait(300):
  raise RuntimeError("Worker not ready")
 if worker.start_error:
  raise worker.start_error
 print(f"[QWEN-AGENT] ГОТОВО. Чат и локальная модель подключены. "
       f"Задавайте вопросы на http://{_display_host}:{args.port}/v1/chat/completions",
       flush=True)
 try:
  api_thread.join()
 except KeyboardInterrupt:
  LOG.info("[SERVER] stopping")
  server.should_exit = True
  api_thread.join(timeout=10)


if __name__ == "__main__":
 main()
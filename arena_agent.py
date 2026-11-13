#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-file Arena Direct agent.

The file owns the visible Chrome process, one Playwright Sync worker thread,
a serialized task queue, model selection, robust message sending, answer
stabilization, and an OpenAI-compatible HTTP API.

Resilience rules:
  * the HTTP API always starts (falls back to a free port), even when Chrome,
    the model or llama-server is unavailable;
  * the worker never exits on browser errors and reconnects with backoff;
  * local tools are executed by llama-server, with direct execution fallback;
  * logs/diagnostics live under ~/.local/state/arena-agent, not in the project.
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright

DIRECT_URL = "https://arena.ai/text/direct"
# Пустая строка = не трогать модель, оставить дефолтную в Arena. Это надёжнее,
# чем жёстко прописанный устаревший алиас: список моделей на Arena меняется.
DEFAULT_MODEL = ""
FALLBACK_MODEL_ID = "arena-default"
DEFAULT_PROFILE = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/work"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.7922.137 Safari/537.36"
DEFAULT_STATE_DIR = Path(
  os.environ.get("ARENA_STATE_DIR", "~/.local/state/arena-agent")
).expanduser()
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 3
LOG = logging.getLogger("arena-monolith")

# Сетевой шум Arena: реклама, капча, rive-анимации, RSC-запросы. Раньше каждое
# такое событие писалось как WARNING и раздувало лог до мегабайтов.
_NOISY_URL_RE = re.compile(
  r"recaptcha|googleusercontent|googletagmanager|web-vitals|"
  r"/rive/|videos/cta|_rsc=|favicon|chrome-extension|analytics",
  re.I,
)

# --- Агентские файловые функции (порт механизма из DeepSeek backend) ---
# Импортируем готовые «сторожа» записи .py и починки JSON. При ошибке
# импорта (напр. запуск не из папки Server Arena) — работаем без них,
# чтобы скрипт гарантированно стартовал.
try:
  from backend import py_write_guard, json_repair_tool  # type: ignore
except Exception:  # noqa: BLE001
  py_write_guard = None
  json_repair_tool = None

import signal
import urllib.request
import json as _json

# Запрет на опасные операции (копия _DENY_TOOL из browser_worker.py).
_DENY_TOOL = re.compile(
  r"\b(mkfs|fdisk|parted)\b|"
  r"\bdd\b[^\n;|]*\bof\s*=\s*/dev/(sd|nvme|hd)[a-z0-9]*\b|"
  r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+(/|/\s*\*|~)(\s|$)"
)
# Явные блоки команд модели.
_EXEC_RE = re.compile(
  r"\[EXEC\][ \t]*\r?\n?([\s\S]*?)[ \t]*\r?\n?[ \t]*\[/(?:EXEC|RESULT)\]"
)
# Фолбэк: fenced bash-блоки (используется только если нет [EXEC]).
_FENCE_BASH_RE = re.compile(
  r"```(?:bash|sh|shell|console|zsh|cmd)\s*\r?\n([\s\S]*?)```", re.I
)
# Regex для блоков [EDIT]path\nold\n---\nnew[/EDIT]
_EDIT_RE = re.compile(
  r"\[EDIT\][ \t]*\r?\n?([\s\S]*?)[ \t]*\r?\n?[ \t]*\[/EDIT\]"
)

# --- Локальный tool-агент (llama-server, Qwen3-4B) ---
# Локальная модель — «руки»: она не думает над стратегией (это умная
# модель на Arena), но исполняет конкретные tool call'ы через
# встроенные инструменты llama-server (exec_shell_command, read_file,
# write_file, edit_file, file_glob_search, grep_search).
# Протокол: OpenAI-совместимый /v1/chat/completions с `tools`.

LOCAL_TOOL_SYSTEM_PROMPT = (
  "You are a local tool-execution agent. You receive a single short "
  "instruction from a smarter model (e.g. \"create folder /tmp/x\", "
  "\"write file /path with content ...\", \"run bash command ...\", "
  "\"find all .py files under /src\"). Your ONLY job is to execute the "
  "instruction using your built-in tools, then report a concise result. "
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

# Формат tool call'ов, который умная модель (Claude и др.) выводит в ответе:
# Основной: ```tool\n[{"name": "exec_shell_command", "arguments": {...}}]\n```
# Фолбэк:  tool\n[{"name": ...}] (без бэктиков — если модель забыла markdown fence)
# Также ловим: [tool]\n[...]\n[/tool] — если модель выбрала свой формат.
_TOOL_BLOCK_RE = re.compile(
  r"```[ \t]*tool[ \t]*\r?\n([\s\S]*?)```",
)
# Фолбэк-форматы без бэктиков: ищем строку, начинающуюся с "tool" и содержащую [
_TOOL_PLAIN_RE = re.compile(
  r"(?:^|\n)\s*tool\s*\n?\s*(\[[\s\S]*?\])\s*$",
  re.M,
)
# Формат [tool]...[/tool]
_TOOL_TAG_RE = re.compile(
  r"\[tool\]\s*\n?([\s\S]*?)\[/tool\]",
)

# Инструменты llama-server, которые мы отдаём локальной модели.
# exec_shell_command, read_file, write_file, edit_file, file_glob_search,
# grep_search — полный набор. Их JSON-схемы передаются в `tools` как
# OpenAI-формат.
LOCAL_TOOLS_OPENAI = [
  {
    "type": "function",
    "function": {
      "name": "exec_shell_command",
      "description": "Execute a shell command in the local environment. Returns stdout/stderr and exit code.",
      "parameters": {
        "type": "object",
        "properties": {
          "command": {"type": "string", "description": "The bash command to execute."}
        },
        "required": ["command"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "read_file",
      "description": "Read the contents of a local file.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string", "description": "Absolute or relative file path."}
        },
        "required": ["path"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "write_file",
      "description": "Create or overwrite a local file with the given content.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string", "description": "Absolute or relative file path."},
          "content": {"type": "string", "description": "Full file content to write."}
        },
        "required": ["path", "content"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "edit_file",
      "description": "Replace an exact unique substring in a local file.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "old_string": {"type": "string", "description": "Exact text to find (must be unique in the file)."},
          "new_string": {"type": "string", "description": "Replacement text."}
        },
        "required": ["path", "old_string", "new_string"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "file_glob_search",
      "description": "Find files matching a glob pattern (e.g. '**/*.py').",
      "parameters": {
        "type": "object",
        "properties": {
          "pattern": {"type": "string", "description": "Glob pattern."},
          "path": {"type": "string", "description": "Base directory (optional)."}
        },
        "required": ["pattern"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "grep_search",
      "description": "Search file contents for a regex or literal string.",
      "parameters": {
        "type": "object",
        "properties": {
          "pattern": {"type": "string", "description": "Regex or literal text to search for."},
          "path": {"type": "string", "description": "File or directory to search in."},
          "case_sensitive": {"type": "boolean", "description": "Default true."}
        },
        "required": ["pattern", "path"]
      }
    }
  },
]

# Системная инструкция для УМНОЙ модели (Claude и др.) на Arena:
# сообщает о наличии локальных инструментов и формате ```tool.
SMART_MODEL_TOOL_INSTRUCTION = (
  "You have access to a local tool-execution agent on the user's machine. "
  "When you need to perform a local action (create folder, write/read/edit "
  "file, run shell command, search files), emit EXACTLY this format "
  "(WITH markdown backticks):\n"
  "```tool\n"
  "[{\"name\": \"<tool>\", \"arguments\": {...}}]\n"
  "```\n"
  "Available tools: exec_shell_command, read_file, write_file, edit_file, "
  "file_glob_search, grep_search, run_local_task. Each call returns a [RESULT] "
  "block. The [RAW OUTPUT] section contains the actual stdout/stderr — trust it "
  "and never re-run a listing/command whose output is already there. You may "
  "call tools at most 12 times total for one task. "
  "For more than 10 items, work in batches of 5-10, verify each batch with a "
  "count/validation command, and make scripts idempotent so a rerun skips "
  "already-created files. Prefer one Python script that processes a whole "
  "batch over hundreds of tiny tool calls. Use run_local_task ({\"task\": "
  "\"...\"}) to delegate a self-contained multi-step job to the local model. "
  "After each [RESULT], continue reasoning or give a final answer. "
  "Never repeat the exact same tool call: the [RESULT] above already contains "
  "its output, so use it and move to the next step. "
  "If a request asks for material you cannot reproduce (for example, "
  "copyrighted lyrics), do NOT stop the whole task: create the file with the "
  "available metadata and clearly marked empty sections for the protected "
  "parts, then continue with the remaining items. "
  "When all actions are done, give a final answer WITHOUT a ```tool block."
)
AGENT_FS_INSTRUCTION = (
  "[SYSTEM] You are a file-system agent with shell access.\n"
  "Working directory: {workdir}\n\n"
  "TOOLS:\n"
  "- [EXEC]command[/EXEC] — run a bash command\n"
  "- [EDIT]path\nold text\n---\nnew text[/EDIT] — edit file (old text must be unique)\n"
  "- [EXEC]json_repair /path/file.json[/EXEC] — repair broken JSON\n"
  "- [EXEC]validate_json /path/file.json[/EXEC] — validate JSON\n\n"
  "RULES:\n"
  "1. After each [EXEC] or [EDIT], you receive [RESULT]. Analyze it.\n"
  "2. If a command fails (rc!=0), analyze error and try another way.\n"
  "3. After creating/editing a file, VERIFY:\n"
  "   - .py: python3 -m py_compile file.py\n"
  "   - .json: python3 -c 'import json; json.load(open(\"file.json\"))'\n"
  "   - Other: cat, wc, or ls to confirm\n"
  "4. For Python files, use base64 to preserve indentation:\n"
  "   echo '<base64>' | base64 -d > file.py\n"
  "5. MAX 6 tool calls total. Plan steps first.\n"
  "6. When done, state 'DONE: <summary>' with verification evidence.\n"
  "7. Never run: rm -rf /, mkfs, fdisk, dd to block devices.\n\n"
  "User request:\n"
)
AGENT_TOOL_TIMEOUT = 300
AGENT_MAX_TOOL_ITERS = 6


def _run_json_tool(command: str) -> tuple[int, str]:
  if not json_repair_tool:
    return 1, "json_repair_tool недоступен"
  parts = command.split(maxsplit=1)
  sub = parts[0]
  arg = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else ""
  if not arg:
    return 1, "Не указан путь к JSON-файлу."
  if sub == "validate_json":
    ok, msg = json_repair_tool.validate_json_file(arg)
    return (0 if ok else 1), f"validate_json {arg}: {msg}"
  r = json_repair_tool.repair_json_file(arg, make_backup=True)
  note = f"json_repair {arg}: {r['message']}"
  if r.get("backed_up"):
    note += f" (бэкап: {r['backed_up']})"
  return (0 if r["ok"] else 1), note


def _post_tool_json_check(command: str) -> list[str]:
  notes: list[str] = []
  if not json_repair_tool:
    return notes
  try:
    targets = json_repair_tool._find_json_write_targets(command)
  except Exception:  # noqa: BLE001
    targets = []
  for p in targets:
    try:
      ok, _ = json_repair_tool.validate_json_file(p)
      if not ok:
        r = json_repair_tool.repair_json_file(p, make_backup=True)
        notes.append(f"json_repair {p}: {r['message']}")
    except Exception as e:  # noqa: BLE001
      notes.append(f"json_repair {p}: ошибка {e}")
  return notes


def _exec_tool_command(cmd: str, work_dir: Path, timeout: float) -> tuple[int, str]:
  """Выполняет bash-команду агента с защитой (порт _exec_tool из DeepSeek)."""
  cmd = cmd.strip()
  if cmd.startswith("json_repair ") or cmd.startswith("validate_json "):
    return _run_json_tool(cmd)
  notes: list[str] = []
  if py_write_guard:
    try:
      rewritten, ns = py_write_guard.rewrite_unsafe_py_writes(cmd)
      notes.extend(ns)
      cmd = rewritten
    except Exception as e:  # noqa: BLE001
      LOG.warning("py_write_guard rewrite failed: %s", e)
  if _DENY_TOOL.search(cmd):
    return 1, ("Команда отклонена: входит в запрещённый список "
               "(mkfs/fdisk/parted, dd в блочное устройство, rm -rf / или ~).")
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
      try:
        os.killpg(proc.pid, signal.SIGKILL)
      except (ProcessLookupError, PermissionError):
        proc.kill()
      output, _ = proc.communicate()
      return 124, f"Команда превысила лимит времени ({timeout} с) и остановлена."
  except Exception as e:  # noqa: BLE001
    return 2, f"Не удалось выполнить: {e}"
  rc = proc.returncode
  if py_write_guard:
    try:
      notes.extend(py_write_guard.guard_written_python_files(cmd))
    except Exception:  # noqa: BLE001
      pass
    try:
      notes.extend(py_write_guard.verify_python_files(cmd))
    except Exception:  # noqa: BLE001
      pass
    try:
      bad = py_write_guard.invalid_python_files(cmd)
      if bad and rc == 0:
        rc = 3
        output = ("СОЗДАН НЕВАЛИДНЫЙ PYTHON: " + "; ".join(bad) +
                  ". Перезапиши файл заново через base64: "
                  "echo '<base64>' | base64 -d > \"<путь>\"")
    except Exception:  # noqa: BLE001
      pass
  if json_repair_tool:
    try:
      notes.extend(_post_tool_json_check(cmd))
    except Exception:  # noqa: BLE001
      pass
  output = (output or "").strip()
  maxc = 6000
  if len(output) > maxc:
    output = output[:maxc] + "\n…(вывод обрезан. Используй grep/sed/head/tail для нужного фрагмента, либо верни структурированную сводку из скрипта)."
  if not output:
    output = "(нет вывода)"
  if notes:
    output = output + "\n\n[py_write_guard]\n" + "\n".join(f"- {n}" for n in notes)
  return rc, output


def _edit_file_tool(spec: str, work_dir: Path) -> tuple[int, str]:
  """Редактирует файл: точная замена old_string → new_string."""
  parts = spec.split("\n---\n", 1)
  if len(parts) != 2:
    return 1, "Формат: [EDIT]путь\nстарое\n---\nновое[/EDIT]"
  header = parts[0].strip()
  body = parts[1]
  sep = body.find("\n")
  if sep == -1:
    return 1, "Формат: old_string (одна строка) --- new_string"
  old_str = body[:sep]
  new_str = body[sep + 1:]
  path = _resolve_safe(header, work_dir)
  if not path.is_file():
    return 1, f"Файл не найден: {path}"
  content = path.read_text(encoding="utf-8")
  if old_str not in content:
    return 1, "old_string не найдена в файле"
  if content.count(old_str) > 1:
    return 1, f"old_string встречается {content.count(old_str)} раз — уточни контекст"
  new_content = content.replace(old_str, new_str, 1)
  if path.suffix == ".py":
    try:
      compile(new_content, str(path), "exec")
    except SyntaxError as e:
      return 1, f"Синтаксическая ошибка после замены, откат: {e}"
  path.write_text(new_content, encoding="utf-8")
  return 0, f"OK: замена в {path.name} ({len(old_str)} → {len(new_str)} байт)"


def _resolve_safe(path_str: str, work_dir: Path) -> Path:
  """Резолвит путь и гарантирует, что он внутри work_dir (безопасность FS API)."""
  p = Path(path_str).expanduser()
  p = p.resolve() if p.is_absolute() else (work_dir / p).resolve()
  wd = work_dir.resolve()
  if p != wd and wd not in p.parents:
    raise ValueError(f"Путь вне рабочей директории {wd}")
  return p


def _tool_call_to_instruction(tc: dict[str, Any], work_dir: Path) -> str:
  """Превращает tool call умной модели ({name, arguments}) в краткое задание
  для локальной модели (Qwen3-4B). Локальная модель сама выберет инструменты.
  """
  name = tc.get("name", "")
  args = tc.get("arguments", {}) or {}
  a = {k: str(v) for k, v in args.items()}
  if name == "exec_shell_command":
    return f"Выполни bash-команду: {a.get('command', '').strip()}\nПосле выполнения проверь результат (rc, вывод)."
  if name == "read_file":
    p = a.get("path", "")
    return f"Прочитай файл {p} (относительно {work_dir}) и вынеси его содержимое."
  if name == "write_file":
    p = a.get("path", "")
    c = a.get("content", "")
    return f"Напиши в файл {p} следующее содержимое (создай каталоги при необходимости):\n{c}"
  if name == "edit_file":
    p = a.get("path", "")
    old = a.get("old_string", "")
    new = a.get("new_string", "")
    return f"В файле {p} замени точную подстроку:\nOLD: {old}\nNA: {new}\nСтарая подстрока должна быть уникальна."
  if name == "file_glob_search":
    pat = a.get("pattern", "")
    base = a.get("path", "") or "."
    return f"Найди файлы по шаблону {pat} (база: {base} относительно {work_dir})."
  if name == "grep_search":
    pat = a.get("pattern", "")
    base = a.get("path", "")
    cs = a.get("case_sensitive", "true")
    return f"Поищи в {base} (относительно {work_dir}) совпадения по регулярке/строке {pat!r} (case_sensitive={cs})."
  # Неизвестный инструмент: передаём как есть.
  return f"Выполни задание: {name} {json.dumps(a, ensure_ascii=False)}"


# --------------------------------------------------------------------------------------
# LocalToolAgent — «руки» на локальной модели (llama-server, Qwen3-4B, OpenAI API)
# --------------------------------------------------------------------------------------
# Умная модель на Arena думает и эмитит ```tool [...] ```. Скрипт парсит
# вызовы и передаёт их сюда. LocalToolAgent сам ведёт tool-loop с локальной
# моделью: поставляет задание → локальная модель вызывает встроенные
# инструменты llama-server → скрипт исполняет (через _exec_tool_command /
# файловые функции) → результат постит обратно (роль "tool") → до финала.
def _strip_tool_blocks(text: str) -> str:
  """Убирает из финального текста служебные ```tool ...``` блоки."""
  cleaned = re.sub(r"```[ \t]*tool[ \t]*\r?\n[\s\S]*?```", "", text or "")
  cleaned = re.sub(r"(?:^|\n)[ \t]*tool[ \t]*:?[ \t]*\r?\n[ \t]*\[[\s\S]*?\]\s*$", "", cleaned, flags=re.M)
  return cleaned.strip()


class LocalToolAgent:
  def __init__(
    self,
    base_url: str,
    model: str,
    work_dir: Path,
    tool_timeout: float = 300,
    max_iters: int = 8,
    request_timeout: float = 300,
  ) -> None:
    self.base_url = base_url.rstrip("/")
    self.model = model
    self.work_dir = work_dir
    self.tool_timeout = tool_timeout
    self.max_iters = max_iters
    self.request_timeout = request_timeout
    self.enabled = True
    self.ready = False
    self.max_instruction_chars = 1800
    self._models_cache: list[str] = []
    self._models_checked_at = 0.0
    LOG.info(
      "[LOCAL-TOOL] ready base=%s model=%s workdir=%s max_iters=%s",
      self.base_url, self.model, work_dir, max_iters,
    )

  def _get_models(self, force: bool = False) -> list[str]:
    """Возвращает список алиасов llama-server. Ошибки не пробрасывает."""
    now = time.time()
    if not force and self._models_cache and now - self._models_checked_at < 30:
      return self._models_cache
    try:
      with urllib.request.urlopen(self.base_url + "/models", timeout=4) as r:
        data = _json.loads(r.read().decode("utf-8"))
      ids = [str(m.get("id", "")) for m in data.get("data", []) if m.get("id")]
      self._models_cache = ids
      self._models_checked_at = now
      return ids
    except Exception as exc:  # noqa: BLE001
      LOG.debug("[LOCAL-TOOL] /models недоступен: %s", exc)
      return []

  def _ensure_model_alias(self, ids: list[str] | None = None) -> bool:
    """Если настроенный алиас не совпадает с сервером, берём реальный.

    Это чинит классическую проблему: в скрипте указан
    `qwen3-4b-instruct-2507-gguf`, а llama-server отдаёт
    `qwen3-4b-instruct-2507`.
    """
    ids = ids if ids is not None else self._get_models(force=True)
    if not ids:
      return False
    if self.model in ids:
      return True
    old = self.model
    self.model = ids[0]
    LOG.warning(
      "[LOCAL-TOOL] модель '%s' не найдена на llama-server; использую '%s' (доступны: %s)",
      old, self.model, ", ".join(ids),
    )
    return True

  def probe(self) -> bool:
    """Быстрая проверка llama-server без падения при недоступности."""
    ids = self._get_models(force=True)
    if not ids:
      self.ready = False
      LOG.warning("[LOCAL-TOOL] llama-server недоступен: %s (работа продолжится, "
                  "tool calls будут исполняться напрямую)", self.base_url)
      return False
    self._ensure_model_alias(ids)
    self.ready = True
    LOG.info("[LOCAL-TOOL] llama-server доступен, модели: %s", ", ".join(ids))
    return True

  def _post_chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
      "model": self.model,
      "messages": messages,
      "temperature": 0.0,
      "max_tokens": 1536,
    }
    if tools:
      payload["tools"] = tools
      payload["tool_choice"] = "auto"
    body = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_exc: BaseException | None = None
    alias_retried = False
    # 3 попытки: llama-server мог ещё не прогреться, а алиас модели — не совпасть.
    for attempt in range(3):
      req = urllib.request.Request(
        self.base_url + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
      )
      try:
        with urllib.request.urlopen(req, timeout=self.request_timeout) as r:
          return _json.loads(r.read().decode("utf-8"))
      except urllib.error.HTTPError as exc:
        detail = ""
        try:
          detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:  # noqa: BLE001
          pass
        last_exc = RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}")
        if not alias_retried and self._ensure_model_alias():
          alias_retried = True
          payload["model"] = self.model
          body = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
          continue
      except Exception as exc:  # noqa: BLE001
        last_exc = exc
      if attempt < 2:
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"llama-server недоступен ({self.base_url}): {last_exc}")

  def _execute_local_tool(self, name: str, args: dict[str, Any]) -> tuple[int, str]:
    """Исполняет tool call локальной модели на этой машине (защита та же, что и _exec_tool_command)."""
    a = {k: str(v) for k, v in args.items()}
    if name == "exec_shell_command":
      cmd = a.get("command", "").strip()
      if not cmd:
        return 1, "exec_shell_command: пустая команда"
      if _DENY_TOOL.search(cmd):
        return 1, "Команда отклонена: входит в запрещённый список."
      return _exec_tool_command(cmd, self.work_dir, self.tool_timeout)
    if name == "read_file":
      p = _resolve_safe(a.get("path", ""), self.work_dir)
      if not p.is_file():
        return 1, f"Файл не найден: {p}"
      text = p.read_text(encoding="utf-8", errors="replace")
      if len(text) > 20000:
        text = text[:20000] + "\n…(обрезано)"
      return 0, text
    if name == "write_file":
      p = _resolve_safe(a.get("path", ""), self.work_dir)
      content = a.get("content", "")
      p.parent.mkdir(parents=True, exist_ok=True)
      p.write_text(content, encoding="utf-8")
      return 0, f"OK: записано {len(content.encode('utf-8'))} байт в {p}"
    if name == "edit_file":
      p = _resolve_safe(a.get("path", ""), self.work_dir)
      old = a.get("old_string", "")
      new = a.get("new_string", "")
      if not p.is_file():
        return 1, f"Файл не найден: {p}"
      content = p.read_text(encoding="utf-8")
      if old not in content:
        return 1, "old_string не найдена в файле"
      if content.count(old) > 1:
        return 1, f"old_string встречается {content.count(old)} раз — уточни контекст"
      new_content = content.replace(old, new, 1)
      if p.suffix == ".py":
        try:
          compile(new_content, str(p), "exec")
        except SyntaxError as e:
          return 1, f"Синтаксическая ошибка после замены, откат: {e}"
      p.write_text(new_content, encoding="utf-8")
      return 0, f"OK: замена в {p.name}"
    if name == "file_glob_search":
      import glob as _glob
      pattern = a.get("pattern", "")
      base = a.get("path", "") or "."
      full = base if _os.path.isabs(base) else str(self.work_dir / base)
      matches = sorted(_glob.glob(_os.path.join(full, pattern), recursive=True))
      out = "\n".join(matches[:200]) if matches else "(нет совпадений)"
      return 0, f"{len(matches)} совпадений:\n{out}"
    if name == "grep_search":
      import subprocess as _sp
      pattern = a.get("pattern", "")
      path = a.get("path", ".")
      cs_flag = "--text" if a.get("case_sensitive", "true").lower() in ("true", "1", "yes") else "-i"
      full = path if _os.path.isabs(path) else str(self.work_dir / path)
      try:
        proc = _sp.run(
          ["grep", "-rn", cs_flag, pattern, full] if _os.path.isdir(full) else ["grep", "-n", cs_flag, pattern, full],
          capture_output=True, text=True, timeout=30,
        )
        out = (proc.stdout or "").strip()
        if len(out) > 3500:
          out = out[:3500] + "\n…(обрезано)"
        return 0, out or "(нет совпадений)"
      except Exception as e:
        return 1, f"grep error: {e}"
    return 1, f"Неизвестный инструмент: {name}"

  def execute(self, instruction: str) -> dict[str, Any]:
    """Одно задание для локальной модели. Возвращает {answer, tool_calls, complete}."""
    if not self.enabled:
      return {"answer": instruction, "tool_calls": [], "complete": True, "skipped": True}
    system = LOCAL_TOOL_SYSTEM_PROMPT.format(workdir=self.work_dir)
    messages: list[dict[str, Any]] = [
      {"role": "system", "content": system},
      {"role": "user", "content": instruction},
    ]
    tool_log: list[dict[str, Any]] = []
    final = instruction
    try:
      for i in range(self.max_iters):
        resp = self._post_chat(messages, LOCAL_TOOLS_OPENAI)
        choice = resp.get("choices", [{}])[0]
        msg = choice.get("message", {}) or {}
        tool_calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        if not tool_calls:
          final = (content or "").strip()
          if not final and tool_log:
            # Не тратим ещё один запрос к локальной модели: отдаём сырой
            # результат выполненного инструмента. Именно он нужен умной
            # модели, а не пересказ.
            last = tool_log[-1]
            final = (
              f"DONE: {last['name']} rc={last['rc']}\n"
              f"{str(last.get('output') or '')[:1500]}"
            )
          if not final:
            final = "(локальная модель не вернула текст)"
          break
        # Фиксируем ход модели в истории
        messages.append({
          "role": "assistant",
          "content": content or "",
          "tool_calls": tool_calls,
        })
        # Исполняем каждый tool call и постим результаты (роль "tool")
        for tc in tool_calls:
          fn = (tc.get("function") or {})
          tname = fn.get("name", "")
          raw_args = fn.get("arguments", "{}")
          try:
            targs = _json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
          except Exception:
            targs = {}
          tc_id = tc.get("id") or f"call_{i}_{len(tool_log)}"
          LOG.info("[LOCAL-TOOL] iter=%s call=%s args=%s", i + 1, tname, _json.dumps(targs, ensure_ascii=False)[:200])
          rc, out = self._execute_local_tool(tname, targs)
          tool_log.append({"iter": i + 1, "name": tname, "args": targs, "rc": rc, "output": out[:500]})
          messages.append({
            "role": "user",
            "content": f"[RESULT {tc_id}] rc={rc}\n{out}",
          })
      else:
        final = "(бюджет tool-loop исчерпан)"
    except Exception as exc:
      LOG.warning("[LOCAL-TOOL] error: %s", exc)
      return {
        "answer": f"ОШИБКА локального tool-агента: {exc}",
        "tool_calls": tool_log,
        "complete": False,
        "unavailable": True,
      }
    return {"answer": final, "tool_calls": tool_log, "complete": True}

  def execute_direct(self, tc: dict[str, Any]) -> dict[str, Any]:
    """Запасной путь: исполняет tool call умной модели без локальной LLM.

    Нужен, когда llama-server выключен/не отвечает. Основной режим —
    выполнение через локальную модель; этот метод не даёт задаче упасть.
    """
    name = str(tc.get("name", ""))
    args = tc.get("arguments") or {}
    if not isinstance(args, dict):
      args = {}
    try:
      rc, out = self._execute_local_tool(name, args)
      ok = rc == 0
      return {
        "answer": f"{'DONE' if ok else 'FAIL'}: прямое исполнение {name} (rc={rc})\n{out}",
        "tool_calls": [{"iter": 0, "name": name, "args": args, "rc": rc, "output": out[:500]}],
        "complete": ok,
        "direct": True,
      }
    except Exception as exc:  # noqa: BLE001
      return {
        "answer": f"ОШИБКА прямого исполнения {name}: {exc}",
        "tool_calls": [],
        "complete": False,
        "direct": True,
      }


# Объявляем _os здесь (после импорта), чтобы _execute_local_tool мог использовать
# path-функции без повторного импорта в каждый вызов.
import os as _os


# --------------------------------------------------------------------------------------
# Парсинг ```tool [...]``` из ответа умной модели
# --------------------------------------------------------------------------------------

def _extract_balanced_json(text: str) -> str:
  """Возвращает первый сбалансированный JSON-объект/массив из текста."""
  m = re.search(r"[\[{]", text)
  if not m:
    return ""
  start = m.start()
  stack: list[str] = []
  in_str = False
  quote = ""
  escaped = False
  for i in range(start, len(text)):
    ch = text[i]
    if in_str:
      if escaped:
        escaped = False
      elif ch == "\\":
        escaped = True
      elif ch == quote:
        in_str = False
      continue
    if ch in ('"', "'"):
      in_str = True
      quote = ch
    elif ch in "[{":
      stack.append(ch)
    elif ch in "]}":
      if not stack:
        continue
      opening = stack.pop()
      if (opening == "[" and ch != "]") or (opening == "{" and ch != "}"):
        return ""
      if not stack:
        return text[start:i + 1]
  return text[start:]


def _normalize_json_text(text: str) -> str:
  return (
    text.replace("\u201c", '"').replace("\u201d", '"')
    .replace("\u00a0", " ").replace("\u200b", "").strip()
  )


_TOOL_NAMES = (
  "exec_shell_command", "read_file", "write_file", "edit_file",
  "file_glob_search", "grep_search",
)


def _json_unescape_lenient(text: str) -> str:
  """Мягко раскодирует строку, которую модель вставила в JSON без экранирования."""
  out: list[str] = []
  i = 0
  while i < len(text):
    ch = text[i]
    if ch != "\\" or i + 1 >= len(text):
      out.append(ch)
      i += 1
      continue
    nxt = text[i + 1]
    mapping = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
    if nxt in mapping:
      out.append(mapping[nxt])
      i += 2
    elif nxt == "u" and i + 5 < len(text):
      try:
        out.append(chr(int(text[i + 2:i + 6], 16)))
        i += 6
      except ValueError:
        out.append(ch)
        i += 1
    else:
      out.append(ch)
      i += 1
  return "".join(out)


def _parse_tool_block_lenient(body: str) -> list[dict[str, Any]]:
  """Аварийный разбор tool call'а, если JSON битый.

  Модели часто вставляют в `exec_shell_command` большой heredoc-скрипт
  с настоящими переносами строк и неэкранированными кавычками. Строгий
  json.loads такое не принимает. Здесь мы вытаскиваем имя и аргументы
  эвристически, сохраняя содержимое команды как есть.
  """
  m_name = re.search(r'"name"\s*:\s*"([^"]+)"', body)
  if not m_name:
    return []
  name = m_name.group(1)
  args: dict[str, Any] = {}

  def extract_string(key: str) -> str | None:
    m = re.search(r'"' + re.escape(key) + r'"\s*:\s*"', body)
    if not m:
      return None
    raw = body[m.end():]
    # Закрывающая кавычка значения перед закрытием объекта/массива.
    end = re.search(r'"\s*\}\s*\]?\s*$', raw)
    if end:
      value = raw[:end.start()]
    else:
      value = raw[:raw.rfind('"')] if '"' in raw else raw
    return _json_unescape_lenient(value)

  if name in ("exec_shell_command", "read_file", "write_file", "edit_file",
              "file_glob_search", "grep_search"):
    for key in ("command", "path", "content", "old_string", "new_string",
                "pattern", "case_sensitive"):
      value = extract_string(key)
      if value is not None:
        args[key] = value
  if name == "exec_shell_command" and "command" not in args:
    return []
  if not args:
    return []
  LOG.warning("[TOOL-PARSE] JSON битый — применил мягкий разбор для '%s'", name)
  return [{"name": name, "arguments": args}]


def parse_tool_block(answer: str) -> list[dict[str, Any]]:
  """Извлекает список tool call'ов из ответа Arena-модели.

  Поддерживает форматы:
    1. ```tool [...]```   (markdown fence, основной)
    2. [tool]...[/tool]   (тег-формат)
    3. ```json [...]```   (модель перепутала имя fence)
    4. tool\\n[...]        (без бэктиков)
    5. JSON-массив с известным именем инструмента без маркера `tool`

  Возвращает список {"name": str, "arguments": dict}. Пустой список,
  если блок не найден или JSON не распарсился.
  """
  body = ""
  # Формат 1: ```tool [...]```
  m = _TOOL_BLOCK_RE.search(answer)
  if m:
    body = m.group(1).strip()
  # Формат 2: [tool]...[/tool]
  if not body:
    m = _TOOL_TAG_RE.search(answer)
    if m:
      body = m.group(1).strip()
  # Формат 3: ```json [...]``` (только если внутри есть tool call)
  if not body:
    for jm in re.finditer(r"```[ \t]*(?:json|javascript|js)[ \t]*\r?\n([\s\S]*?)```", answer, re.I):
      candidate = jm.group(1)
      if '"name"' in candidate or "'name'" in candidate:
        body = candidate.strip()
        break
  # Формат 4: tool\\n[...] без бэктиков. Не требуем конца строки/текста:
  # модель может дописать пояснение после JSON. Берём весь остаток ответа:
  # балансировка скобок ломается на больших shell-скриптах с кавычками.
  if not body:
    m = re.search(r"(?:^|\n)[ \t]*tool[ \t]*:?[ \t]*(?:\r?\n)?[ \t]*(?=[\[{])", answer, re.M)
    if m:
      rest = answer[m.end():].strip()
      if rest:
        body = rest
  # Формат 5: JSON с известным инструментом, но без слова tool.
  if not body:
    positions = [answer.find(f'"{n}"') for n in _TOOL_NAMES if f'"{n}"' in answer]
    positions = [p for p in positions if p >= 0]
    if positions:
      idx = min(positions)
      start = max(answer.rfind("[", 0, idx), answer.rfind("{", 0, idx))
      if start >= 0:
        body = _extract_balanced_json(answer[start:]).strip()
  if not body:
    return []
  body = _normalize_json_text(body)
  # Быстрый фильтр: если тело не содержит "name" — это не tool call'и.
  if '"name"' not in body and "'name'" not in body:
    return []
  try:
    data = _json.loads(body)
  except Exception:
    LOG.warning("[TOOL-PARSE] invalid JSON: %s", body[:200])
    candidate = _extract_balanced_json(body)
    if not candidate:
      lenient = _parse_tool_block_lenient(body)
      if lenient:
        return lenient
      return []
    try:
      data = _json.loads(candidate)
    except Exception:
      lenient = _parse_tool_block_lenient(body)
      if lenient:
        return lenient
      LOG.warning("[TOOL-PARSE] cannot fix JSON: %s", candidate[:200])
      return []
  if isinstance(data, dict):
    data = [data]
  if not isinstance(data, list):
    return []
  out: list[dict[str, Any]] = []
  for item in data:
    if not isinstance(item, dict):
      continue
    name = str(item.get("name", "")).strip()
    args = item.get("arguments", {})
    if not isinstance(args, dict):
      args = {"raw": args}
    if name:
      out.append({"name": name, "arguments": args})
  return out

# Arena Direct рендерит и вопрос, и ответ внутри div.prose. Различаем по
# «пузырю»: сообщение пользователя лежит внутри div.bg-surface-raised
# (справа), ответ ассистента — в div.flex.flex-col без bg-surface-raised (слева).
_ASSISTANT_XPATH = (
  "xpath=//div[contains(concat(' ', normalize-space(@class), ' '), ' prose ')"
  " and not(ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' bg-surface-raised ')])]"
)
_USER_XPATH = (
  "xpath=//div[contains(concat(' ', normalize-space(@class), ' '), ' prose ')"
  " and ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' bg-surface-raised ')]]"
)


class AskRequest(BaseModel):
  message: str = Field(min_length=1)
  model: str | None = None
  timeout: float = Field(default=300, ge=10, le=900)
  file: str | None = None


class ModelRequest(BaseModel):
  model: str = Field(min_length=1)


class IndexRequest(BaseModel):
  index: int | None = None


class ChatRequest(BaseModel):
  model: str | None = None
  messages: list[dict[str, Any]] = Field(min_length=1)
  file: str | None = None
  stream: bool = False
  temperature: float | None = None
  max_tokens: int | None = None


class ExecRequest(BaseModel):
  command: str = Field(min_length=1)
  timeout: float | None = None


class FsPathRequest(BaseModel):
  path: str = "."


class FsReadRequest(BaseModel):
  path: str = Field(min_length=1)
  max_chars: int = 20000


class FsWriteRequest(BaseModel):
  path: str = Field(min_length=1)
  content: str = ""
  append: bool = False


class FsMkdirRequest(BaseModel):
  path: str = Field(min_length=1)


class FsDeleteRequest(BaseModel):
  path: str = Field(min_length=1)


@dataclass
class Job:
  kind: str
  payload: dict[str, Any]
  done: threading.Event
  result: Any = None
  error: BaseException | None = None


@dataclass
class BrowserSettings:
  profile: Path
  model: str
  cdp_port: int
  headed: bool
  state_dir: Path = DEFAULT_STATE_DIR
  debug_artifacts: bool = False
  dump_on_start: bool = False
  launch_chrome: bool = True
  # Какой ответ брать, если Arena показывает два варианта (A/B, Battle).
  # auto: при двух колонках — левая (A); иначе самый длинный/первый.
  answer_column: str = "auto"
  # Принудительно открывать Direct-режим (одна модель) перед отправкой.
  force_direct: bool = False


def clean_stale_profile_lock(profile: Path) -> None:
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
    return
  for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
    try:
      (profile / name).unlink()
    except (FileNotFoundError, OSError):
      pass


def _cdp_alive(port: int, timeout: float = 1.0) -> bool:
  try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=timeout) as r:
      return r.status == 200
  except Exception:
    return False


def launch_visible_chrome(settings: BrowserSettings) -> subprocess.Popen | None:
  if settings.cdp_port <= 0:
    return None
  # Если Chrome уже слушает CDP — не запускаем второй, просто используем его.
  if _cdp_alive(settings.cdp_port):
    LOG.info("[CHROME] CDP %s уже доступен — переиспользую запущенный Chrome", settings.cdp_port)
    return None
  settings.profile.mkdir(parents=True, exist_ok=True)
  clean_stale_profile_lock(settings.profile)
  chrome = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or shutil.which("chromium")
  if not chrome:
    raise RuntimeError("Chrome/Chromium не найден в PATH")
  cmd = [
    chrome,
    f"--user-data-dir={settings.profile}",
    f"--remote-debugging-port={settings.cdp_port}",
    "--remote-allow-origins=*",
    # "--disable-blink-features=AutomationControlled",
    "--enable-features=WebRtcHideLocalIpsWithMdns",
    f"--user-agent={DEFAULT_UA}",
    "--accept-lang=en-US,en;q=0.9",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=site-per-process",
    "--password-store=basic",
    # "--lang=en-US",
    # "--use-fake-ui-for-media-stream",
    "--disable-popup-blocking",
    "--disable-dev-shm-usage",
    # VM/нет GPU: отключаем аппаратный GPU, но НЕ отключаем софтверный
    # растеризатор (раньше были и --disable-gpu, и --disable-software-rasterizer
    # одновременно — в VM без GPU страница не имела НИКАКОГО растеризатора,
    # рендерер падал, и каждый send давал "Target page ... closed" → 502).
    # --use-gl=swiftshader даёт надёжный софтверный GL, когда GPU недоступен.
    "--disable-gpu",
    "--use-gl=swiftshader",
    "--disable-infobars",
    "--window-size=1200,900",
    "--new-window",
    DIRECT_URL,
  ]
  if not settings.headed:
    cmd.insert(1, "--headless=new")
  LOG.info("Открываю Chrome и Arena")
  proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  deadline = time.time() + 45
  while time.time() < deadline:
    if _cdp_alive(settings.cdp_port):
      return proc
    time.sleep(0.25)
  try:
    proc.kill()
  except Exception:  # noqa: BLE001
    pass
  raise RuntimeError("Chrome не поднял CDP-порт")


class ArenaWorker(threading.Thread):
  def __init__(self, settings: BrowserSettings, agent_fs: bool = True,
               work_dir: Path = Path("/home/egor/Downloads"),
               tool_timeout: float = 300, max_tool_iters: int = 6,
               local_agent: "LocalToolAgent | None" = None,
               local_max_iters: int = 8,
               smart_model_tools: bool = True) -> None:
    super().__init__(name="arena-browser-worker", daemon=True)
    self.settings = settings
    self.agent_fs = agent_fs
    self.work_dir = work_dir
    self.tool_timeout = tool_timeout
    self.max_tool_iters = max_tool_iters
    self.local_agent = local_agent
    self.local_max_iters = local_max_iters
    self.smart_model_tools = smart_model_tools
    self.jobs: queue.Queue[Job] = queue.Queue()
    self.stop_event = threading.Event()
    self.ready = threading.Event()
    self.start_error: BaseException | None = None
    self.last_error: BaseException | None = None
    self._browser_ready = False
    self._backoff = 5.0
    self._next_attempt = 0.0
    self.page: Any = None
    self.browser: Any = None
    self.pw: Any = None
    self.selected_model = settings.model
    self.available_models: list[str] = []

  def submit(self, kind: str, payload: dict[str, Any], timeout: float = 900) -> Any:
    LOG.info("[QUEUE] submit kind=%s payload_keys=%s timeout=%s", kind, list(payload), timeout)
    job = Job(kind, payload, threading.Event())
    self.jobs.put(job)
    LOG.info("[QUEUE] job queued kind=%s queue_size=%s", kind, self.jobs.qsize())
    if not job.done.wait(timeout):
      raise TimeoutError("worker не ответил за отведённое время")
    if job.error:
      raise job.error
    return job.result

  def run(self) -> None:
    """Worker живёт постоянно: браузер подключается с повторами, ошибки не фатальны."""
    LOG.info("[WORKER] запущен; подключение к Arena в фоне")
    self._backoff = 5.0
    self._next_attempt = 0.0
    while not self.stop_event.is_set():
      if not self._browser_ready and time.time() >= self._next_attempt:
        if self._start_browser():
          self._browser_ready = True
          self._backoff = 5.0
          self.ready.set()
        else:
          self._schedule_retry()
      try:
        job = self.jobs.get(timeout=0.5)
      except queue.Empty:
        continue
      browser_job = True
      try:
        LOG.info("[WORKER] job started kind=%s", job.kind)
        if job.kind == "ask":
          if not self._ensure_browser():
            raise RuntimeError("Arena не готова: браузер ещё не подключён")
          job.result = self._ask(job.payload["message"], job.payload.get("model"), job.payload.get("timeout", 300))
        elif job.kind == "model":
          if not self._ensure_browser():
            raise RuntimeError("Arena не готова: браузер ещё не подключён")
          actual = self._select_model_safe(job.payload["model"])
          job.result = {"model": actual, "requested": job.payload["model"], "ok": actual == job.payload["model"]}
        elif job.kind == "new_chat":
          if not self._ensure_browser():
            raise RuntimeError("Arena не готова: браузер ещё не подключён")
          job.result = self._new_chat()
        elif job.kind == "delete_chat":
          if not self._ensure_browser():
            raise RuntimeError("Arena не готова: браузер ещё не подключён")
          job.result = self._delete_chat(job.payload.get("index"))
        elif job.kind == "pin_chat":
          if not self._ensure_browser():
            raise RuntimeError("Arena не готова: браузер ещё не подключён")
          job.result = self._pin_chat(job.payload.get("index"))
        else:
          browser_job = False
          raise ValueError(f"unknown job: {job.kind}")
      except BaseException as exc:
        job.error = exc
        if browser_job and self._looks_like_browser_failure(exc):
          LOG.warning("[WORKER] похоже на потерю браузера: %s; переподключаюсь", exc)
          self._browser_ready = False
          self.ready.clear()
          self._next_attempt = 0.0
      finally:
        LOG.info("[WORKER] job finished kind=%s error=%s", job.kind, bool(job.error))
        job.done.set()

  def _schedule_retry(self) -> None:
    self._next_attempt = time.time() + self._backoff
    LOG.warning("[WORKER] следующая попытка подключения через %.0f с", self._backoff)
    self._backoff = min(self._backoff * 2, 60.0)

  @staticmethod
  def _looks_like_browser_failure(exc: BaseException) -> bool:
    text = str(exc).lower()
    markers = (
      "target page", "context or browser", "browser has been closed",
      "connection closed", "econnrefused", "websocket", "page crashed",
      "disconnected", "target closed", "browser closed", "not connected",
    )
    return any(m in text for m in markers)

  def _page_closed(self) -> bool:
    if self.page is None:
      return True
    try:
      return bool(self.page.is_closed())
    except Exception:  # noqa: BLE001
      return True

  def _cleanup_browser(self) -> None:
    for obj, method in ((self.browser, "close"), (self.pw, "stop")):
      if obj is None:
        continue
      try:
        getattr(obj, method)()
      except Exception:  # noqa: BLE001
        pass
    self.page = None
    self.browser = None
    self.pw = None

  def _start_browser(self) -> bool:
    """Подключение/переподключение к Arena. Возвращает True при успехе."""
    self._browser_ready = False
    self._cleanup_browser()
    try:
      if self.settings.cdp_port > 0 and self.settings.launch_chrome:
        try:
          launch_visible_chrome(self.settings)
        except Exception as exc:  # noqa: BLE001
          # Chrome мог не подняться, но CDP уже доступен — попробуем подключиться.
          LOG.warning("[CHROME] запуск не удался: %s; пробую CDP всё равно", exc)
      self.pw = sync_playwright().start()
      self.browser = self.pw.chromium.connect_over_cdp(
        f"http://127.0.0.1:{self.settings.cdp_port}", timeout=15000
      )
      context = self.browser.contexts[0]
      self.page = context.pages[0] if context.pages else context.new_page()
      # Не даём отдельным Playwright-операциям висеть по 30 секунд.
      try:
        self.page.set_default_timeout(10000)
      except Exception:  # noqa: BLE001
        pass
      # Антидетект: прячем следы автоматизации от Arena.
      context.add_init_script(
        """
        try { Object.defineProperty(navigator, 'webdriver', { get: () => false }); } catch (e) {}
        try { Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] }); } catch (e) {}
        try {
            Object.defineProperty(navigator, 'plugins', { get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojklgcpolnddimaf' },
                { name: 'Native Client', filename: 'ppapi' }
            ] });
        } catch (e) {}
        try {
            const orig = window.chrome;
            window.chrome = orig || {};
            window.chrome.runtime = window.chrome.runtime || {};
        } catch (e) {}
        """
      )
      self.page.on("crash", self._on_page_crash)
      self.page.on("pageerror", self._on_page_error)
      self.page.on("console", lambda msg: LOG.debug("[PAGE-CONSOLE] %s: %s", msg.type, msg.text))
      self.page.on("requestfailed", self._on_request_failed)
      try:
        self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=60000)
      except Exception as exc:  # noqa: BLE001
        LOG.warning("[PAGE] переход на Arena не удался: %s; пробую работать с текущей страницей", exc)
      self.page.wait_for_timeout(3500)
      self._wait_composer()
      if self.settings.dump_on_start:
        self._dump_page_source()
      # Сначала подтягиваем список доступных моделей — это наполнит
      # self.available_models. Затем пытаемся выбрать запрошенную модель.
      # Если модель не задана, пикер вообще не открываем: это лишний
      # UI-шаг, который может зависнуть и задержать старт worker'а.
      requested_model = (self.settings.model or "").strip()
      self.selected_model = ""
      if requested_model:
        try:
          self.available_models = self._fetch_available_models()
          LOG.info("[MODELS] available=%s", self.available_models)
        except Exception as exc:  # noqa: BLE001
          LOG.warning("[MODELS] fetch error: %s", exc)
          self.available_models = []
        try:
          self._select_model_safe(requested_model)
        except Exception as exc:  # noqa: BLE001
          LOG.warning("[MODEL] select failed: %s", exc)
          self.selected_model = ""
      else:
        LOG.info("[MODEL] модель не задана — работаю с текущей/дефолтной моделью Arena, пикер не открываю")
      self.last_error = None
      LOG.info("Arena готова, модель=%s (запрошена=%s)", self.selected_model or "дефолт", self.settings.model or "дефолт")
      return True
    except BaseException as exc:
      self.last_error = exc
      LOG.warning("[WORKER] браузер не готов: %s", exc)
      self._cleanup_browser()
      return False

  def _ensure_browser(self) -> bool:
    if self._browser_ready and not self._page_closed():
      return True
    if self._start_browser():
      self._browser_ready = True
      self._backoff = 5.0
      self.ready.set()
      return True
    self.ready.clear()
    self._schedule_retry()
    return False

  def _on_page_crash(self) -> None:
    LOG.error("[PAGE] Playwright сообщает: страница Arena crashed")
    self._browser_ready = False
    self.ready.clear()

  def _on_page_error(self, exc: Any) -> None:
    text = str(exc)
    if "recaptcha" in text.lower():
      LOG.debug("[PAGE] reCAPTCHA: %s", text)
    else:
      LOG.error("[PAGE] JavaScript error: %s", text)

  def _on_request_failed(self, req: Any) -> None:
    try:
      url = req.url
    except Exception:  # noqa: BLE001
      url = ""
    if _NOISY_URL_RE.search(url):
      LOG.debug("[NET] request failed (шум): %s", url)
      return
    try:
      LOG.warning("[NET] request failed: %s -> %s", req.failure, url)
    except Exception:  # noqa: BLE001
      pass

  def _wait_composer(self) -> Any:
    deadline = time.time() + 60
    while time.time() < deadline:
      for selector in (
        'textarea[placeholder*="Ask anything"]',
        'textarea[placeholder*="anything"]',
        "textarea",
        '[contenteditable="true"]',
      ):
        try:
          loc = self.page.locator(selector).first
          loc.wait_for(state="visible", timeout=2000)
          return loc
        except Exception:  # noqa: BLE001
          pass
      try:
        self.page.wait_for_timeout(300)
      except Exception:  # noqa: BLE001
        break
    raise RuntimeError("Arena composer не найден")

  @staticmethod
  def _norm_model(model: str | None) -> str:
    return (model or "").strip().lower()

  def _model_search_input(self) -> Any:
    for selector in (
      'input[placeholder="Search models"]',
      'input[placeholder*="search" i]',
      'input[type="search"]',
      'input[aria-label*="search" i]',
    ):
      try:
        loc = self.page.locator(selector).first
        if loc.count():
          return loc
      except Exception:  # noqa: BLE001
        pass
    return None

  def _read_model_options(self) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    opts = self.page.locator('[role="option"]')
    try:
      count = opts.count()
    except Exception:  # noqa: BLE001
      return out
    for i in range(min(count, 400)):
      try:
        t = opts.nth(i).inner_text(timeout=2000).strip().split("\n")[0]
      except Exception:  # noqa: BLE001
        t = ""
      if t:
        out.append((t, opts.nth(i)))
    return out

  def _resolve_model_name(self, model: str) -> str | None:
    """Сопоставляет запрошенное имя с реальным списком Arena.

    Возвращает None, если модели нет и похожей тоже нет. Это позволяет
    не тратить 30 секунд на поиск заведомо отсутствующей модели.
    """
    requested = self._norm_model(model)
    if not requested:
      return None
    options = [m for m in self.available_models if m]
    if not options:
      return model
    for opt in options:
      if self._norm_model(opt) == requested:
        return opt
    # Частичное совпадение (например, запросили без суффикса -high).
    sub = [
      opt for opt in options
      if requested in self._norm_model(opt) or self._norm_model(opt) in requested
    ]
    if sub:
      return sub[0]
    # Семейство: claude-sonnet-4-6 -> claude-sonnet-5-5-high.
    tokens = [
      t for t in re.split(r"[-_.\s]+", requested)
      if t and not t.isdigit()
    ]
    family = tokens[:2]
    if family:
      cands = [opt for opt in options if all(t in self._norm_model(opt) for t in family)]
      if cands:
        if len(cands) > 1:
          LOG.warning("[MODEL] неоднозначное семейство '%s': %s; беру '%s'",
                      model, cands, cands[0])
        return cands[0]
    return None

  def _fetch_available_models(self) -> list[str]:
    names: list[str] = []
    opened = False
    try:
      control = None
      for loc in (
        self.page.locator('button[aria-haspopup="dialog"]').first,
        self.page.locator('button[aria-haspopup="listbox"]').first,
        self.page.get_by_role("button", name=re.compile(r"Max|Direct|claude|gemini|gpt|qwen", re.I)).first,
      ):
        try:
          if loc.count() and loc.is_visible():
            control = loc
            break
        except Exception:  # noqa: BLE001
          pass
      if control is None:
        LOG.warning("[MODELS] переключатель модели не найден")
        return names
      LOG.info("[MODELS] opening model picker")
      control.click(timeout=5000)
      opened = True
      search = self._model_search_input()
      if search is not None:
        try:
          search.fill("", timeout=2000)
        except Exception as exc:  # noqa: BLE001
          LOG.debug("[MODELS] search clear failed: %s", exc)
      self.page.wait_for_timeout(700)
      for _ in range(10):
        if self._read_model_options():
          break
        self.page.wait_for_timeout(300)
      for t, _ in self._read_model_options():
        if t and t not in names:
          names.append(t)
      LOG.info("[MODELS] found %s options", len(names))
    except Exception as exc:  # noqa: BLE001
      LOG.warning("[MODELS] fetch failed: %s", exc)
    finally:
      if opened:
        try:
          self.page.keyboard.press("Escape")
          self.page.wait_for_timeout(300)
        except Exception:  # noqa: BLE001
          pass
    return names

  def _dump_page_source(self, path: Path | None = None) -> str:
    try:
      html = self.page.content()
    except Exception as exc:
      LOG.warning("[DUMP] не удалось получить исходный код страницы: %s", exc)
      return ""
    if path is None:
      path = self.settings.state_dir / "diagnostics" / "arena_page_source.html"
    try:
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(html, encoding="utf-8")
      LOG.info("[DUMP] исходный код страницы записан в %s (%s байт)", path, len(html))
    except Exception as exc:
      LOG.warning("[DUMP] не удалось записать файл %s: %s", path, exc)
    return str(path)

  def _select_model(self, model: str) -> str:
    LOG.info("[MODEL] requested=%s current=%s", model or "дефолт", self.selected_model)
    requested = self._norm_model(model)
    if requested in ("", "current", "arena-current", "*", "auto", "default"):
      return self.selected_model
    if self.selected_model and requested == self._norm_model(self.selected_model):
      return self.selected_model
    resolved = self._resolve_model_name(model)
    if resolved is None:
      available = ", ".join(self.available_models[:20]) or "список пуст"
      raise RuntimeError(f"модель '{model}' отсутствует в Arena; доступны: {available}")
    if self._norm_model(resolved) != requested:
      LOG.warning("[MODEL] модели '%s' нет; использую ближайшую '%s'", model, resolved)
    if self.selected_model and self._norm_model(self.selected_model) == self._norm_model(resolved):
      return self.selected_model
    # Контрол выбора модели: кнопка с aria-haspopup="dialog", содержащая
    # текущее имя модели. Имя может быть любым (glm, grok, mistral, ...),
    # поэтому ищем по атрибуту, а не по конкретным подстрокам.
    control = None
    for loc in (
      self.page.locator('button[aria-haspopup="dialog"]').first,
      self.page.locator('button[aria-haspopup="listbox"]').first,
      self.page.get_by_role("button", name=re.compile(
        r"Max|Direct|claude|gemini|gpt|qwen|glm|grok|mistral|deepseek|kimi|"
        r"minimax|trinity|hunyuan|step|nova|ring|gemma|mercury|ling|inkling|"
        r"intellect|mimo|dola|longcat|amazon|ibm|granite|nvidia|muse",
        re.I,
      )).first,
    ):
      try:
        if loc.count() and loc.is_visible():
          control = loc
          break
      except Exception:  # noqa: BLE001
        pass
    if control is None:
      raise RuntimeError("переключатель модели Arena не найден")
    LOG.info("[MODEL] clicking model control")
    target = None
    try:
      control.click(timeout=5000)
      search = self._model_search_input()
      # Основной путь — прямой клик по варианту из списка (не зависит от
      # поисковой строки, которой у Arena может не быть: раньше fill по
      # "Search models" ждал 30 с на отсутствующем input'е). Сначала читаем
      # опции и ищем точное совпадение с resolved.
      self.page.wait_for_timeout(700)
      options = self._read_model_options()
      want = self._norm_model(resolved)
      for t, loc in options:
        if self._norm_model(t) == want:
          target = (t, loc)
          break
      # Фолбэк: частичное совпадение по тексту варианта.
      if target is None:
        for t, loc in options:
          if want and want in self._norm_model(t):
            target = (t, loc)
            break
      # Фолбэк: поиск через search-строку (если она есть и отфильтровала список).
      if target is None and search is not None:
        try:
          search.fill(resolved, timeout=2000)
          self.page.wait_for_timeout(700)
          for t, loc in self._read_model_options():
            if self._norm_model(t) == want:
              target = (t, loc)
              break
          if target is None:
            search.fill("", timeout=2000)
            self.page.wait_for_timeout(500)
            for t, loc in self._read_model_options():
              if self._norm_model(t) == want:
                target = (t, loc)
                break
        except Exception as exc:  # noqa: BLE001
          LOG.debug("[MODEL] search path failed: %s; продолжаю без поиска", exc)
      if target is None:
        raise RuntimeError(f"модель '{resolved}' не найдена в списке Arena")
      LOG.info("[MODEL] selecting option=%s", target[0])
      target[1].click(timeout=5000)
      self.page.wait_for_timeout(700)
      self.selected_model = target[0]
      return self.selected_model
    except Exception:
      try:
        self.page.keyboard.press("Escape")
      except Exception:  # noqa: BLE001
        pass
      raise

  def _select_model_safe(self, model: str) -> str:
    """Выбирает модель, но не падает при ошибке. Возвращает текущую selected_model."""
    if self._norm_model(model) in ("", "current", "arena-current", "*", "auto", "default"):
      return self.selected_model
    try:
      return self._select_model(model)
    except Exception as exc:
      LOG.warning("[MODEL] не удалось выбрать '%s' (%s); продолжаю с моделью Arena '%s'",
                  model, exc, self.selected_model or "по умолчанию")
      return self.selected_model

  def _new_chat(self) -> dict[str, Any]:
    LOG.info("[CHAT] opening New Chat")
    try:
      link = self.page.get_by_role("link", name="New Chat").first
      if link.count() and link.is_visible():
        link.click()
      else:
        LOG.warning("[CHAT] ссылка New Chat не найдена; переходим по URL")
        self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
      LOG.warning("[CHAT] click New Chat failed: %s; navigating directly", exc)
      self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=60000)
    self.page.wait_for_timeout(2000)
    self._wait_composer()
    # Новый чат на Arena может сбросить модель к дефолту — возвращаем
    # выбранную, чтобы состояние браузера совпадало с selected_model.
    try:
      if self.selected_model:
        self._select_model(self.selected_model)
    except Exception as exc:
      LOG.warning("[CHAT] re-select model after new chat failed: %s", exc)
    LOG.info("[CHAT] new chat ready, model=%s", self.selected_model)
    return {"ok": True, "model": self.selected_model}

  def _chat_menu_action(self, label: str, index: int | None = None) -> dict[str, Any]:
    LOG.info("[CHAT-MENU] action=%s index=%s", label, index)
    items = self.page.locator('[data-sidebar="menu-item"]')
    if index is not None:
      item = items.nth(index)
    else:
      # Текущий чат: sidebar-ссылка, совпадающая с текущим URL страницы.
      path = self.page.url.split("arena.ai", 1)[-1] or "/text/direct"
      cand = self.page.locator(f'a[href="{path}"]').first
      if cand.count():
        item = cand.locator("xpath=ancestor::*[contains(@data-sidebar,'menu-item')][1]")
      else:
        item = items.first
    kebab = item.locator('button[data-sidebar="menu-action"]').first
    if not (kebab.count() and kebab.is_visible()):
      item.hover()
      self.page.wait_for_timeout(300)
    kebab.click()
    menu = self.page.locator('[role="menu"]').first
    try:
      menu.wait_for(state="visible", timeout=3000)
    except Exception:
      pass
    mi = menu.get_by_role("menuitem", name=label, exact=False).first
    if not mi.count():
      mi = self.page.locator('[role="menu"] >> text=' + label).first
    if not mi.count():
      mi = self.page.get_by_text(label, exact=False).first
    mi.click()
    self.page.wait_for_timeout(700)
    # Arena при удалении обычно показывает диалог подтверждения.
    confirm = self.page.locator('[role="alertdialog"] button', has_text="Delete").first
    if confirm.count() and confirm.is_visible():
      LOG.info("[CHAT-MENU] подтверждаем удаление")
      confirm.click()
    self.page.wait_for_timeout(700)
    return {"ok": True, "action": label}

  def _delete_chat(self, index: int | None = None) -> dict[str, Any]:
    return self._chat_menu_action("Delete", index)

  def _pin_chat(self, index: int | None = None) -> dict[str, Any]:
    return self._chat_menu_action("Pin", index)

  def _login_visible(self) -> bool:
    try:
      google = self.page.get_by_role("button", name=re.compile(r"Continue with Google", re.I))
      email = self.page.get_by_role("button", name=re.compile(r"Continue with email", re.I))
      visible = (google.count() and google.first.is_visible()) or (email.count() and email.first.is_visible())
      if visible:
        LOG.warning("[AUTH] Arena login modal detected")
        return True
      body = self.page.locator("body").inner_text(timeout=2000)
      result = bool(re.search(r"Log In or Create Account|Continue with Google|Continue with email", body, re.I))
      LOG.info("[AUTH] login_text_detected=%s", result)
      return result
    except Exception as exc:
      LOG.warning("[AUTH] detection failed: %s", exc)
      return False

  def _send_reliably(self, composer: Any, text: str) -> None:
    LOG.info("[SEND] begin chars=%s preview=%r", len(text), text[:120])
    button = None
    for selector in (
      'button[aria-label="Send message"]',
      'button[aria-label*="send" i]',
      'button[aria-label*="отправ" i]',
      'button[title*="send" i]',
      'button[title*="отправ" i]',
    ):
      try:
        loc = self.page.locator(selector).last
        if loc.count() and loc.is_visible():
          button = loc
          break
      except Exception:
        pass
    for attempt in range(3):
      LOG.info("[SEND] attempt=%s fill", attempt + 1)
      composer.click()
      composer.fill(text)
      deadline = time.time() + 5
      while time.time() < deadline:
        try:
          val = composer.input_value(timeout=700)
        except Exception:
          break
        if val == text:
          break
        self.page.wait_for_timeout(100)
      # Arena Direct имеет явную кнопку Send message. Нажимаем её
      # первой; Enter оставляем только как fallback.
      clicked = False
      if button is not None:
        try:
          LOG.info("[SEND] button found aria=%r", button.get_attribute("aria-label"))
          if button.is_enabled(timeout=2000):
            LOG.info("[SEND] clicking button=Send message no_wait_after=True")
            button.click(timeout=2000, no_wait_after=True)
            clicked = True
            LOG.info("[SEND] click returned")
            if self.settings.debug_artifacts:
              try:
                diag = self.settings.state_dir / "diagnostics"
                diag.mkdir(parents=True, exist_ok=True)
                self.page.screenshot(path=str(diag / f"arena_after_click_{int(time.time())}.png"))
              except Exception as exc:  # noqa: BLE001
                LOG.warning("[SEND] screenshot after click failed: %s", exc)
            self.page.wait_for_timeout(700)
            LOG.info("[SEND] post-click URL=%s composer=%r", self.page.url, self._safe_input_value(composer))
            if self._login_visible():
              raise PermissionError("Arena требует авторизацию для отправки сообщений")
            if self._wait_composer_changed(composer, text, 6):
              LOG.info("[SEND] composer changed after button")
              return
        except PermissionError:
          raise
        except Exception as exc:
          LOG.warning("[SEND] button click failed: %s; trying DOM dispatch", exc)
          try:
            button.dispatch_event("click", timeout=2000)
            clicked = True
            LOG.info("[SEND] DOM click dispatched")
            self.page.wait_for_timeout(700)
            LOG.info("[SEND] post-dispatch URL=%s composer=%r", self.page.url, self._safe_input_value(composer))
            if self._login_visible():
              raise PermissionError("Arena требует авторизацию для отправки сообщений")
            if self._wait_composer_changed(composer, text, 4):
              LOG.info("[SEND] composer changed after DOM dispatch")
              return
          except PermissionError:
            raise
          except Exception as dispatch_exc:
            LOG.warning("[SEND] DOM dispatch failed: %s", dispatch_exc)
      LOG.info("[SEND] button_result=%s; pressing Enter fallback", clicked)
      try:
        composer.press("Enter")
      except Exception:
        pass
      self.page.keyboard.press("Enter")
      self.page.wait_for_timeout(700)
      LOG.info("[SEND] composer value after Enter=%r", self._safe_input_value(composer))
      if self._login_visible():
        raise PermissionError("Arena требует авторизацию для отправки сообщений")
      if self._wait_composer_changed(composer, text, 6):
        LOG.info("[SEND] composer changed after Enter")
        return
      if self._login_visible():
        raise PermissionError("Arena требует авторизацию для отправки сообщений")
      try:
        composer.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
      except Exception:
        pass
      self.page.wait_for_timeout(300)
    raise RuntimeError("Arena не приняла сообщение: текст остался в поле ввода")

  @staticmethod
  def _safe_input_value(composer: Any) -> str:
    try:
      return composer.input_value(timeout=1000)
    except Exception as exc:
      return f"<unavailable:{type(exc).__name__}>"

  def _wait_composer_changed(self, composer: Any, old_text: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
      try:
        val = composer.input_value(timeout=700)
      except Exception:
        # поле отвязалось/исчезло — значит сообщение ушло
        return True
      if val != old_text:
        return True
      self.page.wait_for_timeout(200)
    return False

  def _user_blocks(self) -> list[str]:
    blocks: list[str] = []
    try:
      loc = self.page.locator(_USER_XPATH)
      for i in range(loc.count()):
        text = loc.nth(i).inner_text().strip()
        if text and text not in blocks:
          blocks.append(text)
    except Exception as exc:
      LOG.warning("[USER] xpath read failed: %s", exc)
    if not blocks:
      # фолбэк: любой div.prose, если структура изменилась
      try:
        fall = self.page.locator("div.prose")
        for i in range(fall.count()):
          text = fall.nth(i).inner_text().strip()
          if text and text not in blocks:
            blocks.append(text)
      except Exception:
        pass
    return blocks

  def _answer_blocks(self) -> list[str]:
    blocks: list[str] = []
    try:
      loc = self.page.locator(_ASSISTANT_XPATH)
      for i in range(loc.count()):
        text = loc.nth(i).inner_text().strip()
        if text and text not in blocks:
          blocks.append(text)
    except Exception as exc:
      LOG.warning("[ANSWER] assistant xpath read failed: %s", exc)
    if not blocks:
      # фолбэк: любой div.prose, последний блок
      try:
        fall = self.page.locator("div.prose")
        for i in range(fall.count()):
          text = fall.nth(i).inner_text().strip()
          if text and text not in blocks:
            blocks.append(text)
      except Exception:
        pass
    return blocks

  def _ensure_no_login_modal(self) -> None:
    body = self.page.locator("body").inner_text()
    if re.search(r"Log In or Create Account|Continue with Google|Continue with email", body, re.I):
      raise PermissionError("Arena требует авторизацию для отправки сообщений")

  def _assistant_prose_texts_js(self) -> list[str]:
    return self.page.evaluate(
      "() => [...document.querySelectorAll('div.prose')]"
      ".filter(e => !e.closest('.bg-surface-raised'))"
      ".map(e => (e.innerText||'').trim()).filter(Boolean)"
    )

  def _answer_candidates_js(self, before: list[str], mode: str = "auto") -> dict[str, Any]:
    """Возвращает все новые ответы ассистента и выбранный по режиму.

    В Direct-режиме новый ответ один. В Battle / сравнении моделей Arena
    рисует две колонки: A слева, B справа. Старый код брал первый попавшийся
    `<ol>` и ждал стабилизации обоих вариантов, поэтому «выбор A/B» занимал
    очень долго. Здесь мы сразу выбираем нужную колонку и следим за
    стабильностью только её текста.
    """
    try:
      return self.page.evaluate(
        """(args) => {
            const before = args.before || [];
            const mode = args.mode || 'auto';
            const all = [...document.querySelectorAll('div.prose')]
              .filter(e => !e.closest('.bg-surface-raised'));
            const fresh = [];
            for (const p of all) {
              const t = (p.innerText || '').trim();
              if (!t || before.includes(t)) continue;
              if (fresh.some(x => x.text === t)) continue;
              const r = p.getBoundingClientRect();
              let label = '';
              let node = p;
              for (let k = 0; k < 10 && node; k++) {
                const cand = (node.getAttribute && (
                  node.getAttribute('data-testid') ||
                  node.getAttribute('aria-label') ||
                  node.getAttribute('data-model')
                )) || '';
                if (cand && !label) label = cand;
                node = node.parentElement;
              }
              fresh.push({
                text: t,
                left: Math.round(r.left + r.width / 2),
                top: Math.round(r.top),
                label: label,
                len: t.length
              });
            }
            const candidates = fresh.map(x => ({
              left: x.left, top: x.top, len: x.len, label: x.label,
              preview: x.text.slice(0, 120)
            }));
            if (!fresh.length) return {chosen: '', candidates: []};
            let chosen = null;
            if (mode === 'first') chosen = fresh[0];
            else if (mode === 'longest') {
              chosen = fresh.slice().sort((a, b) => b.len - a.len)[0];
            } else if (mode === 'b') {
              chosen = fresh.slice().sort((a, b) => b.left - a.left)[0];
            } else if (mode === 'a') {
              chosen = fresh.slice().sort((a, b) => a.left - b.left)[0];
            } else {
              const xs = fresh.map(x => x.left);
              const spread = Math.max(...xs) - Math.min(...xs);
              chosen = spread > 120
                ? fresh.slice().sort((a, b) => a.left - b.left)[0]
                : fresh.slice().sort((a, b) => b.len - a.len)[0];
            }
            return {chosen: chosen.text, candidates: candidates};
        }""",
        {"before": before, "mode": mode},
      )
    except Exception as exc:  # noqa: BLE001
      LOG.debug("[ANSWER] candidates js failed: %s", exc)
      return {"chosen": "", "candidates": []}

  def _extract_answer_js(self, message: str, before: list[str]) -> str:
    """Точное извлечение ответа модели по реальной структуре Arena.

    В Arena переписка — <ol class="... flex-col-reverse ...">: DOM-порядок
    инвертирован, вопрос пользователя (div.prose внутри .bg-surface-raised)
    — последний дочерний элемент <ol>, а ответ модели (.prose БЕЗ
    .bg-surface-raised) находится ПЕРЕД ним. Ищем последний вопрос
    пользователя и берём предшествующее ему assistant-сообщение.
    """
    q = message[:40]
    try:
      return self.page.evaluate(
        """(args) => {
            const q = args.q;
            const before = args.before || [];
            const ol = document.querySelector('ol');
            if (!ol) return '';
            const kids = [...ol.children].filter(c => c.querySelector && c.querySelector('.prose'));
            let userIdx = -1;
            for (let i = kids.length - 1; i >= 0; i--) {
                const txt = (kids[i].innerText || '');
                if (kids[i].querySelector('.bg-surface-raised') && txt.includes(q)) { userIdx = i; break; }
            }
            const start = userIdx >= 0 ? userIdx : kids.length;
            for (let i = start - 1; i >= 0; i--) {
                const raised = kids[i].querySelector('.bg-surface-raised');
                const p = kids[i].querySelector('.prose');
                if (p && !raised) {
                    const t = (p.innerText || '').trim();
                    if (t && !before.includes(t)) return t;
                }
            }
            const all = [...document.querySelectorAll('div.prose')].filter(e => !e.closest('.bg-surface-raised'));
            const t = all.length ? (all[all.length - 1].innerText || '').trim() : '';
            return (t && !before.includes(t)) ? t : '';
        }""",
        {"q": q, "before": before},
      )
    except Exception as exc:
      LOG.warning("[ANSWER] js extract failed: %s", exc)
      return ""

  def _ask(self, message: str, model: str | None, timeout: float) -> dict[str, Any]:
    # В режиме агента подсказываем модели формат [EXEC] и прогоняем tool-loop.
    prefix = ""
    if self.agent_fs:
      prefix = AGENT_FS_INSTRUCTION.format(workdir=self.work_dir)
    if self.smart_model_tools and self.local_agent and self.local_agent.enabled:
      # Умная модель на Arena получает инструкцию про ```tool``` блок.
      # Её ответ парсится через parse_tool_block и передаётся LocalToolAgent.
      prefix = SMART_MODEL_TOOL_INSTRUCTION + "\n\n" + prefix + message
      raw = self._ask_raw(prefix, model, timeout)
      return self._run_tool_loop_local(raw["answer"], timeout, model)
    if self.agent_fs:
      prefix = prefix + message
      raw = self._ask_raw(prefix, model, timeout)
      return self._run_tool_loop(raw["answer"], timeout, model)
    # Чистый режим: без локальных инструментов, без AGENT_FS-инструкции.
    return self._ask_raw(message, model, timeout)

  def _ask_raw(self, message: str, model: str | None, timeout: float) -> dict[str, Any]:
    LOG.info("[ASK] begin model=%s timeout=%s message=%r", model, timeout, message[:200])
    # "arena-current"/"current"/"*"/пусто — использовать уже выбранную
    # в браузере модель (позволяет менять модель через /model и не дёргать
    # браузер на каждый вопрос из opencode).
    if model and str(model).strip().lower() not in ("", "current", "arena-current", "*", "auto"):
      # Ошибка выбора модели не должна ронять запрос: остаёмся на текущей.
      self._select_model_safe(model)
    if self.settings.force_direct and "/text/direct" not in (self.page.url or ""):
      try:
        LOG.info("[MODE] открываю Direct-режим вместо Battle: %s", DIRECT_URL)
        self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_timeout(1000)
      except Exception as exc:  # noqa: BLE001
        LOG.warning("[MODE] не удалось открыть Direct: %s; продолжаю на текущей странице", exc)
    self._ensure_no_login_modal()
    before = self._assistant_prose_texts_js()
    LOG.info("[ASK] baseline assistant prose=%s column=%s", len(before), self.settings.answer_column)
    composer = self._wait_composer()
    LOG.info("[ASK] composer found")
    self._send_reliably(composer, message)
    user_loc = self.page.locator("div.bg-surface-raised div.prose", has_text=message[:40])
    user_seen = user_loc.count() > 0
    if user_seen:
      LOG.info("[ASK] user message already in DOM; пропускаем ожидание")
    else:
      user_deadline = time.time() + 3
      while time.time() < user_deadline:
        if user_loc.count() > 0:
          user_seen = True
          break
        self.page.wait_for_timeout(300)
      if not user_seen:
        LOG.warning("[ASK] user message not confirmed in DOM; продолжаем ожидание ответа")
    LOG.info(
      "[ASK] DEBUG total div.prose=%s, div.bg-surface-raised=%s",
      self.page.locator("div.prose").count(),
      self.page.locator("div.bg-surface-raised").count(),
    )
    LOG.info("[ASK] extracting answer from live DOM (ol.flex-col-reverse)...")
    deadline = time.time() + timeout
    last = ""
    stable_since = 0.0
    appeared = False
    logged_variants = ""
    while time.time() < deadline:
      self.page.wait_for_timeout(500)
      cand_info = self._answer_candidates_js(before, self.settings.answer_column)
      candidate = cand_info.get("chosen") or ""
      variants = cand_info.get("candidates") or []
      if len(variants) > 1:
        sig = json.dumps(variants, sort_keys=True, ensure_ascii=False)
        if sig != logged_variants:
          logged_variants = sig
          LOG.info(
            "[ANSWER] вариантов=%d, режим=%s; выбран %s. Колонки: %s",
            len(variants), self.settings.answer_column,
            "A (левая)" if self.settings.answer_column == "auto" else self.settings.answer_column,
            json.dumps(variants, ensure_ascii=False)[:600],
          )
      if not candidate:
        # Фолбэк на старую DOM-логику, если разметка нестандартная.
        candidate = self._extract_answer_js(message, before)
      if not candidate:
        total = self.page.locator("div.prose").count()
        raised = self.page.locator("div.bg-surface-raised").count()
        LOG.debug("[PROBE] answer empty; total prose=%s bg-surface-raised=%s", total, raised)
        continue
      appeared = True
      if candidate != last:
        if last and candidate.startswith(last):
          LOG.info("[ANSWER][js_dom] +%d chars (total %d): %r", len(candidate) - len(last), len(candidate), candidate[len(last):][:240])
        else:
          LOG.info("[ANSWER][js_dom] changed (total %d): %r", len(candidate), candidate[:240])
        last = candidate
        stable_since = time.time()
        continue
      generating = False
      for selector in (
        'button[aria-label*="stop" i]',
        '[data-testid*="stop" i]',
        'button[title*="stop" i]',
        'button[aria-label*="останов" i]',
      ):
        try:
          loc = self.page.locator(selector).first
          if loc.count() and loc.is_visible():
            generating = True
            break
        except Exception:
          pass
      stable_for = time.time() - stable_since if stable_since else 0
      LOG.info("[ANSWER][js_dom] stable_for=%.1fs generating=%s", stable_for, generating)
      if stable_for >= 1.5 and not generating:
        LOG.info("[ANSWER] FINAL (%d chars): %s", len(candidate), candidate[:600])
        return {"model": self.selected_model, "answer": candidate}
    if appeared and last:
      LOG.warning("[ANSWER] timeout; returning partial final text (%d chars)", len(last))
      return {"model": self.selected_model, "answer": last, "complete": False}
    # Диагностика: сохраняем DOM переписки и скриншот только по запросу
    # (--debug-artifacts), чтобы не засорять папку проекта при каждом сбое.
    if self.settings.debug_artifacts:
      try:
        diag = self.settings.state_dir / "diagnostics"
        diag.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        self.page.screenshot(path=str(diag / f"arena_fail_{ts}.png"))
        dump = self.page.evaluate("() => { const ol = document.querySelector('ol'); return (ol || document.body).outerHTML; }")
        (diag / f"arena_conversation_dump_{ts}.html").write_text(dump, encoding="utf-8")
        LOG.error("[ANSWER] таймаут; диагностика сохранена в %s", diag)
      except Exception as exc:
        LOG.error("[ANSWER] не удалось сохранить дамп: %s", exc)
    else:
      LOG.error("[ANSWER] таймаут; для диагностики запустите с --debug-artifacts")
    raise TimeoutError("Arena не вернула ответ")

  @staticmethod
  def _looks_like_refusal(text: str) -> bool:
    """Грубый детектор отказа модели продолжить задачу."""
    t = (text or "").lower()
    markers = (
      "не буду", "не могу", "не стану", "не воспроизвожу",
      "авторским правом", "защищённые авторским", "защищенные авторским",
      "copyright", "copyrighted", "cannot reproduce", "can't reproduce",
      "i won't", "i will not",
    )
    return any(m in t for m in markers)

  def _is_looping(self, text: str) -> bool:
    """Детектирует зацикливание: хвост 120 символов повторяется ≥4 раз."""
    TAIL_LEN = 120
    THRESHOLD = 4
    if len(text) < TAIL_LEN * THRESHOLD:
      return False
    tail = text[-TAIL_LEN:]
    return text.count(tail) >= THRESHOLD

  def _extract_tool_commands(self, text: str) -> list[str]:
    """Извлекает bash-команды из ответа модели (блоки [EXEC]…[/EXEC])."""
    cmds: list[str] = []
    for m in _EXEC_RE.finditer(text):
      c = m.group(1).rstrip("\r\n")
      if c.strip():
        cmds.append(c.strip())
    if not cmds:
      for m in _FENCE_BASH_RE.finditer(text):
        c = m.group(1).strip()
        if c:
          cmds.append(c)
    return cmds

  def _run_tool_loop(self, answer: str, timeout: float, model: str | None) -> dict[str, Any]:
    """Прогоняет цикл: [EDIT]/[EXEC], шлём результат модели, повторяем."""
    loop_deadline = time.time() + min(timeout, 600)
    for i in range(self.max_tool_iters):
      if time.time() > loop_deadline:
        LOG.warning("[TOOL-LOOP] total budget exhausted after %.0fs", timeout)
        break
      if self._is_looping(answer):
        LOG.warning("[TOOL-LOOP] reasoning loop detected at iter %d", i)
        try:
          answer = self._ask_raw(
            "Не рассуждай дальше. Напиши итоговый ответ.", None, 60
          )["answer"]
        except Exception:
          pass
        break

      # [EDIT] имеет приоритет над [EXEC]
      edit_matches = list(_EDIT_RE.finditer(answer))
      if edit_matches:
        c = edit_matches[0].group(1)
        LOG.info("[TOOL-LOOP] edit iter=%d: %s", i, c[:100])
        rc, out = _edit_file_tool(c, self.work_dir)
        feedback = f"[RESULT]\n[EDIT] → (rc={rc})\n{out}\n[/RESULT]"
        try:
          answer = self._ask_raw(feedback, None, timeout)["answer"]
        except Exception as exc:
          LOG.warning("[TOOL-LOOP] feedback failed: %s", exc)
          break
        continue

      cmds = self._extract_tool_commands(answer)
      if not cmds:
        break

      # Только первая команда за итерацию
      c = cmds[0]
      LOG.info("[TOOL-LOOP] exec 1/%d iter=%d: %s", len(cmds), i, c[:100])
      rc, out = _exec_tool_command(c, self.work_dir, self.tool_timeout)
      feedback = f"[RESULT]\n{c}\n→ (rc={rc})\n{out}\n[/RESULT]"
      try:
        answer = self._ask_raw(feedback, None, timeout)["answer"]
      except Exception as exc:
        LOG.warning("[TOOL-LOOP] feedback failed: %s", exc)
        break

    if "DONE:" not in answer and self._extract_tool_commands(answer):
      LOG.warning("[TOOL-LOOP] no DONE marker, task may be incomplete")
    return {"model": self.selected_model, "answer": answer}

  def _run_tool_loop_local(self, answer: str, timeout: float, model: str | None) -> dict[str, Any]:
    """Цикл: умная модель эмитит ```tool [...]``` → LocalToolAgent исполняет →
    результат постим обратно как [RESULT] → умная модель продолжает → до DONE.
    """
    if not self.local_agent or not self.local_agent.enabled:
      LOG.info("[LOCAL-TOOL-LOOP] local agent disabled; returning raw answer")
      return {"model": self.selected_model, "answer": answer}

    # llama-server мог подняться уже после старта агента. Проверяем ещё раз,
    # чтобы локальная модель реально участвовала, а не только числилась.
    if not self.local_agent.ready:
      self.local_agent.probe()

    loop_deadline = time.time() + min(timeout, 900)
    total_calls: list[dict[str, Any]] = []
    prev_signature: list[str] = []
    nudges = 0
    for i in range(self.local_max_iters):
      if time.time() > loop_deadline:
        LOG.warning("[LOCAL-TOOL-LOOP] budget exhausted after %.0fs", timeout)
        break
      tool_calls = parse_tool_block(answer)
      if not tool_calls:
        # Умная модель не требует инструментов. Но если это отказ
        # («не могу воспроизвести текст»), даём ей пинок: задача должна
        # быть закрыта доступным способом, а не брошена на полпути.
        if nudges < 1 and self._looks_like_refusal(answer):
          nudges += 1
          LOG.warning("[LOCAL-TOOL-LOOP] похоже на отказ модели; отправляю корректирующий пинок")
          nudge = (
            "[SYSTEM] Не останавливай задачу из-за ограничений на текст. "
            "Не воспроизводи защищённый авторским правом текст. Вместо этого "
            "создай файлы с доступными данными (название песни, перевод "
            "названия) и явно помеченными пустыми секциями для текста и "
            "построчного перевода. Используй tool calls. Обработай все "
            "альбомы и песни, затем ответь DONE с числом созданных файлов."
          )
          try:
            answer = self._ask_raw(nudge, None, timeout)["answer"]
          except Exception as exc:  # noqa: BLE001
            LOG.warning("[LOCAL-TOOL-LOOP] не удалось отправить пинок: %s", exc)
            break
          continue
        LOG.info("[LOCAL-TOOL-LOOP] no tool block at iter %d; task complete", i)
        break
      # Подпись вызова включает имя И аргументы: два разных shell-вызова
      # не должны считаться повтором только из-за одинакового имени.
      signature = [
        f"{c.get('name', '')}::{json.dumps(c.get('arguments') or {}, sort_keys=True, ensure_ascii=False)}"
        for c in tool_calls
      ]
      if signature == prev_signature:
        # Это действительно повтор. Не обрываем задачу сразу: просим
        # умную модель использовать уже полученный результат.
        if nudges < 2:
          nudges += 1
          LOG.warning("[LOCAL-TOOL-LOOP] повторный вызов на iter %d; отправляю пинок", i)
          nudge = (
            "[SYSTEM] Этот tool call уже выполнен, его результат есть выше "
            "в [RESULT]. Не повторяй его. Используй полученный результат и "
            "переходи к следующему шагу. Если задача выполнена — ответь DONE."
          )
          try:
            answer = self._ask_raw(nudge, None, timeout)["answer"]
          except Exception as exc:  # noqa: BLE001
            LOG.warning("[LOCAL-TOOL-LOOP] не удалось отправить пинок: %s", exc)
            break
          continue
        LOG.warning("[LOCAL-TOOL-LOOP] same tools repeated at iter %d; stopping to avoid ban", i)
        answer = answer + "\n\n[ЛОКАЛЬНЫЙ АГЕНТ: остановлен — повторный вызов тех же инструментов. Задача может быть неполной.]"
        break
      prev_signature = signature
      LOG.info("[LOCAL-TOOL-LOOP] iter=%d tool_calls=%s", i, [c.get("name") for c in tool_calls])
      # Каждый tool call — отдельное задание для локальной модели.
      # Локальная модель сама решает, какие инструменты вызвать.
      for tc in tool_calls:
        name = str(tc.get("name", "") or "")
        args = tc.get("arguments") or {}
        # Явная делегация сложной задачи локальной модели.
        if name == "run_local_task":
          task = str(args.get("task", "") or "").strip()
          LOG.info("[LOCAL-TOOL-LOOP] delegated local task: %s", task[:300])
          if not task:
            res = {"answer": "FAIL: run_local_task без поля task", "tool_calls": [], "complete": False}
          else:
            res = self.local_agent.execute(task)
          instr = f"локальная задача: {task[:300]}"
        else:
          instr = _tool_call_to_instruction(tc, self.work_dir)
          LOG.info("[LOCAL-TOOL-LOOP] local task: %s", instr[:200])
          # Определённые действия надёжнее и быстрее исполнять напрямую.
          # Локальную модель зовём только для коротких инструкций, которые
          # она способна воспроизвести без искажений. Для больших heredoc
          # (частый случай) сразу идёт прямой путь.
          too_big = len(instr) > self.local_agent.max_instruction_chars
          if too_big or not self.local_agent.ready:
            if too_big:
              LOG.info("[LOCAL-TOOL-LOOP] инструкция %d символов > %d — исполняю '%s' напрямую",
                       len(instr), self.local_agent.max_instruction_chars, name)
            res = self.local_agent.execute_direct(tc)
          else:
            res = self.local_agent.execute(instr)
            if (res.get("unavailable") or not res.get("tool_calls")):
              # Локальная модель не справилась (нет tool call / сервер отвалился).
              # Не роняем задачу: исполняем тот же tool call напрямую.
              LOG.warning("[LOCAL-TOOL-LOOP] локальная модель не выполнила '%s' — "
                          "исполняю напрямую", name)
              res = self.local_agent.execute_direct(tc)
        total_calls.extend(res.get("tool_calls", []))
        rc_note = ""
        skipped = res.get("skipped")
        if skipped:
          rc_note = "(локальный агент отключён)"
        raw_parts: list[str] = []
        for call in res.get("tool_calls", []):
          raw_parts.append(
            f"[{call.get('name', '?')} rc={call.get('rc', '?')}]\n"
            f"{str(call.get('output') or '')[:4000]}"
          )
        raw_output = "\n".join(raw_parts) if raw_parts else "(нет tool output)"
        feedback = (
          f"[RESULT]\n"
          f"Локальный tool-агент выполнил: {instr}\n"
          f"Результат: {res['answer']}\n"
          f"{rc_note}\n"
          f"[RAW OUTPUT — используй это как фактический результат]\n"
          f"{raw_output}\n"
          f"[/RESULT]"
        )
        try:
          answer = self._ask_raw(feedback, None, timeout)["answer"]
        except Exception as exc:
          LOG.warning("[LOCAL-TOOL-LOOP] feedback to Arena failed: %s", exc)
          answer = "(не удалось отправить результат в Arena; останавливаемся)"
          break
      else:
        continue
      break
    if total_calls:
      LOG.info("[LOCAL-TOOL-LOOP] total local tool calls=%d", len(total_calls))
    final_answer = answer
    if parse_tool_block(final_answer):
      # Бюджет исчерпан или цикл остановлен, а в ответе остался невыполненный
      # tool block. Клиенту отдаём чистый текст и честную пометку.
      final_answer = _strip_tool_blocks(final_answer)
      note = ("[ЛОКАЛЬНЫЙ АГЕНТ: задача остановлена по лимиту итераций; "
              "последний tool-блок не выполнен. Продолжите задачу новым запросом — "
              "уже созданные файлы и чекпоинты сохранятся.]")
      final_answer = (final_answer + "\n\n" + note).strip()
      LOG.warning("[LOCAL-TOOL-LOOP] незавершённый tool block удалён из финального ответа")
    return {"model": self.selected_model, "answer": final_answer, "local_tool_calls": total_calls}


worker: ArenaWorker | None = None
_api_port: int | None = None
app = FastAPI(title="Arena Monolith", version="1.1")


@app.get("/")
def root() -> dict[str, Any]:
  return {"ok": True, "service": "arena-monolith", "api": "/v1"}


@app.get("/health")
def health() -> dict[str, Any]:
  ready = bool(worker and worker.ready.is_set() and getattr(worker, "_browser_ready", False))
  return {
    "ok": True,
    "service": "arena-monolith",
    "ready": ready,
    "model": worker.selected_model if worker else None,
    "requested_model": worker.settings.model if worker else None,
    "worker_error": str(worker.last_error) if worker and worker.last_error else None,
    "api_port": _api_port,
    "cdp_port": worker.settings.cdp_port if worker else None,
    "local_tools": bool(_get_local_agent() and _get_local_agent().enabled),
    "local_tools_ready": bool(_get_local_agent() and _get_local_agent().enabled and _get_local_agent().ready),
    "local_tool_model": (_get_local_agent().model if _get_local_agent() else None),
  }


@app.get("/v1/models")
def models() -> dict[str, Any]:
  if worker and worker.available_models:
    data = [{"id": m, "object": "model", "owned_by": "arena", "created": int(time.time())} for m in worker.available_models]
  else:
    mid = (worker.selected_model if worker else "") or FALLBACK_MODEL_ID
    data = [{"id": mid, "object": "model", "owned_by": "arena", "created": int(time.time())}]
  return {"object": "list", "data": data}


@app.post("/model")
def change_model(req: ModelRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    return worker.submit("model", {"model": req.model}, 60)
  except PermissionError as exc:
    raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/new_chat")
def new_chat() -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    return worker.submit("new_chat", {}, 30)
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/dump_source")
def dump_source() -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    path = worker._dump_page_source()
    return {"ok": True, "path": path}
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/delete_chat")
def delete_chat(req: IndexRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    return worker.submit("delete_chat", {"index": req.index}, 30)
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/pin_chat")
def pin_chat(req: IndexRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    return worker.submit("pin_chat", {"index": req.index}, 30)
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/exec")
def exec_cmd(req: ExecRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    rc, out = _exec_tool_command(req.command, worker.work_dir, req.timeout or worker.tool_timeout)
    return {"rc": rc, "output": out}
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


class ToolExecRequest(BaseModel):
  instruction: str = Field(min_length=1, description="Задание для локальной модели (например: 'создай папку /tmp/x')")
  timeout: float | None = None


@app.post("/tools/exec")
def tools_exec(req: ToolExecRequest) -> dict[str, Any]:
  """Прямое задание локальной модели (llama-server) без участия Arena.
  Удобно для проверки, что руки работают. Возвращает {answer, tool_calls}.
  """
  agent = _get_local_agent()
  if agent is None:
    raise HTTPException(503, "Локальный tool-агент не запущен (используй --no-local-tools, чтобы отключить)")
  if not agent.enabled:
    raise HTTPException(503, "Локальный tool-агент отключён")
  try:
    return agent.execute(req.instruction)
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.get("/tools/health")
def tools_health() -> dict[str, Any]:
  """Проверяет доступность llama-server. Возвращает {ok, base_url, model}."""
  agent = _get_local_agent()
  if agent is None:
    return {"ok": False, "reason": "local agent not initialized"}
  if not agent.enabled:
    return {"ok": False, "reason": "disabled via --no-local-tools"}
  ids = agent._get_models(force=True)
  if not ids:
    return {
      "ok": False, "base_url": agent.base_url, "model": agent.model,
      "error": "llama-server недоступен",
      "hint": "tool calls будут исполняться напрямую, пока сервер не поднимется",
    }
  agent._ensure_model_alias(ids)
  return {"ok": True, "base_url": agent.base_url, "model": agent.model, "available": ids}


# Глобальная ссылка на LocalToolAgent (заполняется в main()).
_local_agent_ref: LocalToolAgent | None = None


def _get_local_agent() -> "LocalToolAgent | None":
  return _local_agent_ref


@app.post("/fs/list")
def fs_list(req: FsPathRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    p = _resolve_safe(req.path, worker.work_dir)
    if not p.exists():
      raise FileNotFoundError(str(p))
    if p.is_file():
      return {"ok": True, "path": str(p), "type": "file", "size": p.stat().st_size}
    entries = []
    for e in sorted(p.iterdir()):
      entries.append({
        "name": e.name,
        "type": ("dir" if e.is_dir() else "file"),
        "size": (e.stat().st_size if e.is_file() else None),
      })
    return {"ok": True, "path": str(p), "type": "dir", "entries": entries}
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/fs/read")
def fs_read(req: FsReadRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    p = _resolve_safe(req.path, worker.work_dir)
    if not p.is_file():
      raise ValueError("не является файлом: " + str(p))
    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text) > req.max_chars:
      text = text[:req.max_chars] + "\n…(обрезано)"
    return {"ok": True, "path": str(p), "content": text}
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/fs/write")
def fs_write(req: FsWriteRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    p = _resolve_safe(req.path, worker.work_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if req.append else "w"
    p.write_text(req.content, encoding="utf-8")
    return {"ok": True, "path": str(p), "bytes": len(req.content.encode("utf-8"))}
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/fs/mkdir")
def fs_mkdir(req: FsMkdirRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    p = _resolve_safe(req.path, worker.work_dir)
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": str(p)}
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/fs/delete")
def fs_delete(req: FsDeleteRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    p = _resolve_safe(req.path, worker.work_dir)
    if p == worker.work_dir.resolve():
      raise ValueError("нельзя удалить рабочую директорию")
    if p.is_dir():
      shutil.rmtree(p)
    elif p.is_file():
      p.unlink()
    else:
      raise FileNotFoundError(str(p))
    return {"ok": True, "path": str(p)}
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/ask")
def ask(req: AskRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  try:
    return worker.submit("ask", {"message": req.message, "model": req.model, "timeout": req.timeout}, req.timeout + 30)
  except PermissionError as exc:
    raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc


@app.post("/v1/chat/completions")
def completions(req: ChatRequest) -> dict[str, Any]:
  if worker is None:
    raise HTTPException(503, "worker не запущен")
  text_parts = []
  for item in req.messages:
    content = item.get("content", "")
    if isinstance(content, list):
      content = " ".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in content)
    if str(content).strip():
      text_parts.append(str(content).strip())
  prompt = "\n\n".join(text_parts)
  try:
    result = worker.submit("ask", {"message": prompt, "model": req.model, "timeout": 900}, 930)
  except PermissionError as exc:
    raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc
  except Exception as exc:
    raise HTTPException(502, str(exc)) from exc
  answer = result["answer"]
  # Клиент ожидает обычный текст, а не служебный протокол инструментов.
  answer = _strip_tool_blocks(answer) or answer
  return {
    "id": "chatcmpl-" + uuid.uuid4().hex,
    "object": "chat.completion",
    "created": int(time.time()),
    "model": result.get("model", req.model),
    "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": len(answer.split()), "total_tokens": len(prompt.split()) + len(answer.split())},
  }


def send_test_question(base_url: str, question: str) -> dict[str, Any]:
  """Send one question through the HTTP API and log every client step."""
  url = base_url.rstrip("/") + "/v1/chat/completions"
  payload: dict[str, Any] = {"messages": [{"role": "user", "content": question}]}
  if DEFAULT_MODEL:
    payload["model"] = DEFAULT_MODEL
  body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
  LOG.info("[TEST] POST %s", url)
  LOG.info("[TEST] payload=%s", json.dumps(payload, ensure_ascii=False))
  req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer local-agent"}, method="POST")
  started = time.time()
  try:
    with urllib.request.urlopen(req, timeout=330) as response:
      raw = response.read().decode("utf-8")
      LOG.info("[TEST] status=%s elapsed=%.2fs body=%s", response.status, time.time() - started, raw)
      return json.loads(raw)
  except Exception:
    LOG.exception("[TEST] request failed elapsed=%.2fs", time.time() - started)
    raise


def _setup_logging(state_dir: Path, level: str = "INFO", log_file: str = "", no_file: bool = False) -> Path | None:
  """Лог с ротацией в state-dir, а не в папке проекта."""
  log_path: Path | None = None
  if not no_file:
    log_path = Path(log_file).expanduser() if log_file else state_dir / "arena_agent.log"
    try:
      log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
      log_path = Path(os.environ.get("TMPDIR", "/tmp")) / "arena_agent.log"
  handlers: list[logging.Handler] = [logging.StreamHandler()]
  if log_path is not None:
    try:
      handlers.append(
        logging.handlers.RotatingFileHandler(
          log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
        )
      )
    except OSError as exc:
      LOG.warning("[BOOT] не удалось открыть лог %s: %s; пишу только в консоль", log_path, exc)
      log_path = None
  logging.basicConfig(
    level=getattr(logging, str(level).upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=handlers,
    force=True,
  )
  logging.getLogger("playwright").setLevel(logging.WARNING)
  return log_path


def _port_free(host: str, port: int) -> bool:
  if port <= 0:
    return True
  try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
      s.settimeout(0.5)
      s.bind((host, port))
    return True
  except OSError:
    return False


def _find_free_port(host: str, preferred: int, attempts: int = 20,
                    excluded: set[int] | None = None) -> int:
  """Ищет свободный порт около preferred; в крайнем случае — эфемерный."""
  skip = excluded or set()
  if preferred > 0:
    candidates = [preferred] + [preferred + i for i in range(1, attempts + 1)]
    for port in candidates:
      if port in skip:
        continue
      if 0 < port <= 65535 and _port_free(host, port):
        return port
  for _ in range(10):
    try:
      with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        s.bind((host, 0))
        port = int(s.getsockname()[1])
      if port not in skip:
        return port
    except OSError:
      return 0
  return 0


def _probe_existing_agent(host: str, port: int) -> dict[str, Any] | None:
  if port <= 0:
    return None
  try:
    with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1.5) as r:
      data = _json.loads(r.read().decode("utf-8"))
    if isinstance(data, dict) and (
      data.get("service") == "arena-monolith" or ("ready" in data and "model" in data)
    ):
      return data
  except Exception:  # noqa: BLE001
    pass
  return None


def _start_api_server(host: str, port: int) -> tuple[threading.Thread | None, Any, int | None]:
  """Поднимает uvicorn в фоне. Возвращает (thread, server, actual_port)."""
  try:
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="api-server", daemon=True)
    thread.start()
  except Exception as exc:  # noqa: BLE001
    LOG.error("[BOOT] uvicorn не запустился на %s:%s: %s", host, port, exc)
    return None, None, None
  deadline = time.time() + 10
  while time.time() < deadline and thread.is_alive() and not server.started:
    time.sleep(0.1)
  if not server.started:
    LOG.error("[BOOT] uvicorn не смог занять порт %s:%s", host, port)
    try:
      server.should_exit = True
    except Exception:  # noqa: BLE001
      pass
    thread.join(timeout=3)
    return thread, server, None
  actual = port
  try:
    actual = int(server.servers[0].sockets[0].getsockname()[1])
  except Exception:  # noqa: BLE001
    pass
  return thread, server, actual


def _run_self_test_when_ready(worker_obj: ArenaWorker, host: str, port: int, question: str) -> None:
  if not worker_obj.ready.wait(180):
    LOG.warning("[TEST] Arena не готова за 180 с; self-test пропущен")
    return
  try:
    send_test_question(f"http://{host}:{port}", question)
    LOG.info("[TEST] SELF-TEST PASSED")
  except Exception:
    LOG.exception("[TEST] SELF-TEST FAILED; server remains available")


def main() -> None:
  global worker, _local_agent_ref, _api_port
  parser = argparse.ArgumentParser()
  parser.add_argument("--host", default="127.0.0.1")
  parser.add_argument("--port", type=int, default=8000, help="Желаемый порт API; при занятости берётся свободный")
  parser.add_argument("--model", default=DEFAULT_MODEL, help="Модель Arena (пусто = дефолтная; отсутствующая заменяется ближайшей)")
  parser.add_argument("--profile", default=DEFAULT_PROFILE)
  parser.add_argument("--cdp-port", type=int, default=9223, help="0 — использовать уже запущенный Chrome на 9222")
  parser.add_argument("--headless", action="store_true")
  parser.add_argument("--test-question", default="Сколько пальцев на руке человека?", help="Тестовый вопрос для --self-test")
  parser.add_argument("--self-test", action="store_true", help="Отправить автоматический тестовый вопрос сразу после старта (по умолчанию не отправляется)")
  parser.add_argument("--work-dir", default="/home/egor/Downloads", help="Рабочая директория для файловых операций агента")
  parser.add_argument("--no-agent-fs", action="store_true", help="Отключить агентские файловые функции (tool-loop и [EXEC])")
  parser.add_argument("--tool-timeout", type=float, default=600, help="Таймаут выполнения bash-команды агента, сек (по умолчанию 600)")
  parser.add_argument("--max-tool-iters", type=int, default=6, help="Макс. число итераций tool-loop")
  parser.add_argument("--answer-column", default="auto",
                      choices=("auto", "a", "b", "first", "longest"),
                      help="Какой из двух ответов Arena брать: auto/A/B/first/longest (по умолчанию auto = левая колонка A)")
  parser.add_argument("--force-direct", action="store_true",
                      help="Перед отправкой принудительно открывать Direct-режим (одна модель, без A/B)")
  parser.add_argument("--tool-work-dir", default="/home/egor/Downloads",
                      help="Рабочая директория для локального tool-агента (llama-server)")
  parser.add_argument("--local-tool-url", default="http://127.0.0.1:8080/v1",
                      help="OpenAI-совместимый URL llama-server (дефолт: 8080)")
  parser.add_argument("--local-tool-model", default="qwen3-4b-instruct-2507-gguf",
                      help="Алиас модели llama-server; при несовпадении берётся реальный из /v1/models")
  parser.add_argument("--local-tools-max-iters", type=int, default=12,
                      help="Макс. итераций tool-loop внутри LocalToolAgent (по умолчанию 12)")
  parser.add_argument("--no-local-tools", action="store_true",
                      help="Полностью отключить локальный tool-агент (умная модель думает, но руки не работают)")
  parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR),
                      help="Каталог для логов и диагностики (по умолчанию ~/.local/state/arena-agent)")
  parser.add_argument("--log-file", default="", help="Явный путь к файлу лога")
  parser.add_argument("--no-log-file", action="store_true", help="Не писать лог в файл")
  parser.add_argument("--log-level", default="INFO")
  parser.add_argument("--dump-on-start", action="store_true",
                      help="Сохранить HTML страницы при старте в state-dir/diagnostics")
  parser.add_argument("--debug-artifacts", action="store_true",
                      help="Сохранять скриншоты и DOM при сбоях (state-dir/diagnostics)")
  args = parser.parse_args()

  state_dir = Path(args.state_dir).expanduser()
  log_path = _setup_logging(state_dir, args.log_level, args.log_file, args.no_log_file)
  LOG.info("[BOOT] логи пишутся в %s", log_path or "консоль")
  LOG.info("[BOOT] state-dir=%s", state_dir)
  profile = Path(args.profile).expanduser()
  work_dir = Path(args.work_dir).expanduser()
  tool_work_dir = Path(args.tool_work_dir).expanduser()
  for label, directory in (("work-dir", work_dir), ("tool-work-dir", tool_work_dir)):
    try:
      directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
      LOG.warning("[BOOT] не удалось создать %s %s: %s", label, directory, exc)

  if args.cdp_port == 0:
    cdp_port = 9222
    launch_chrome = False
  else:
    cdp_port = args.cdp_port
    launch_chrome = True

  # Локальный tool-агент (llama-server, Qwen3-4B). Если --no-local-tools,
  # агент не создаётся — умная модель думает, но руки не работают.
  local_agent: LocalToolAgent | None = None
  if not args.no_local_tools:
    local_agent = LocalToolAgent(
      base_url=args.local_tool_url,
      model=args.local_tool_model,
      work_dir=tool_work_dir,
      tool_timeout=args.tool_timeout,
      max_iters=args.local_tools_max_iters,
    )
    # Проверка llama-server — в фоне, чтобы не задерживать старт API.
    threading.Thread(target=local_agent.probe, name="local-tool-probe", daemon=True).start()
  else:
    LOG.info("[LOCAL-TOOL] --no-local-tools: локальный tool-агент отключён")
  _local_agent_ref = local_agent

  settings = BrowserSettings(
    profile=profile,
    model=args.model or "",
    cdp_port=cdp_port,
    headed=not args.headless,
    state_dir=state_dir,
    debug_artifacts=args.debug_artifacts,
    dump_on_start=args.dump_on_start,
    launch_chrome=launch_chrome,
    answer_column=args.answer_column,
    force_direct=args.force_direct,
  )
  worker = ArenaWorker(
    settings,
    agent_fs=not args.no_agent_fs,
    work_dir=work_dir,
    tool_timeout=args.tool_timeout,
    max_tool_iters=args.max_tool_iters,
    local_agent=local_agent,
    local_max_iters=args.local_tools_max_iters,
    smart_model_tools=not args.no_local_tools,
  )
  worker.start()
  LOG.info("[BOOT] worker запущен; API стартует независимо от готовности браузера")

  # API всегда поднимается: при занятом порте берём следующий свободный.
  probe_host = "127.0.0.1" if args.host in ("0.0.0.0", "::", "[::]") else args.host
  if not _port_free(args.host, args.port):
    existing = _probe_existing_agent(probe_host, args.port)
    if existing:
      LOG.warning(
        "[BOOT] на http://%s:%s уже работает arena_agent (ready=%s). "
        "Запускаю этот экземпляр на свободном порту; предпочтительно использовать уже запущенный.",
        probe_host, args.port, existing.get("ready"),
      )
    else:
      LOG.warning("[BOOT] порт %s:%s занят другим процессом; выберу свободный", args.host, args.port)

  api_thread: threading.Thread | None = None
  api_server: Any = None
  actual_port: int | None = None
  tried_ports: set[int] = set()
  for attempt in range(6):
    if attempt == 0 and args.port > 0 and _port_free(args.host, args.port):
      port = args.port
    else:
      port = _find_free_port(args.host, args.port if args.port > 0 else 0,
                              excluded=tried_ports)
      if port <= 0:
        LOG.error("[BOOT] не удалось найти свободный порт для API")
        break
    tried_ports.add(port)
    LOG.info("[BOOT] запускаю API на %s:%s", args.host, port)
    api_thread, api_server, actual_port = _start_api_server(args.host, port)
    if actual_port is not None:
      break
    LOG.warning("[BOOT] порт %s не подошёл; больше не пробую его, беру следующий", port)
    time.sleep(0.5)

  _api_port = actual_port
  if actual_port is not None:
    LOG.info("[SERVER] ready for external requests at http://%s:%s", args.host, actual_port)
    if args.self_test:
      threading.Thread(
        target=_run_self_test_when_ready,
        args=(worker, probe_host, actual_port, args.test_question),
        name="self-test",
        daemon=True,
      ).start()
  else:
    LOG.error("[BOOT] API не удалось запустить; worker продолжает работать без HTTP")

  stop_event = threading.Event()

  def _shutdown(signum: int, _frame: Any) -> None:
    LOG.info("[BOOT] получен сигнал %s, останавливаюсь", signum)
    stop_event.set()
    worker.stop_event.set()
    if api_server is not None:
      try:
        api_server.should_exit = True
      except Exception:  # noqa: BLE001
        pass

  for sig in (signal.SIGINT, signal.SIGTERM):
    try:
      signal.signal(sig, _shutdown)
    except Exception:  # noqa: BLE001
      pass

  # Главный поток не выходит, пока не попросят остановку. Даже если API-поток
  # умер, worker остаётся жив, а процесс — тоже; API пробуем поднять заново.
  api_restarts = 0
  try:
    while not stop_event.is_set():
      if api_thread is not None and not api_thread.is_alive():
        LOG.error("[BOOT] API-поток завершился неожиданно; worker продолжает работать")
        api_thread = None
        api_server = None
        _api_port = None
        if api_restarts < 3 and not stop_event.is_set():
          api_restarts += 1
          port = _find_free_port(args.host, args.port if args.port > 0 else 0)
          LOG.warning("[BOOT] перезапускаю API (попытка %s/3) на %s:%s", api_restarts, args.host, port)
          try:
            api_thread, api_server, actual_port = _start_api_server(args.host, port)
          except Exception as exc:  # noqa: BLE001
            LOG.error("[BOOT] не удалось перезапустить API: %s; worker продолжает работать", exc)
            api_thread, api_server, actual_port = None, None, None
          _api_port = actual_port
          if actual_port is not None:
            LOG.info("[SERVER] снова доступен на http://%s:%s", args.host, actual_port)
      stop_event.wait(1.0)
  except KeyboardInterrupt:
    LOG.info("[BOOT] KeyboardInterrupt")
  finally:
    worker.stop_event.set()
    if api_server is not None:
      try:
        api_server.should_exit = True
      except Exception:  # noqa: BLE001
        pass
    worker.join(timeout=5)


if __name__ == "__main__":
  main()

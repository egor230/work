#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZaiChat Agent — rewritten version with verbose logging.

Модель управления та же: FastAPI (поток) -> очередь -> ZaiWorker (поток браузера).
Главное отличие: агент сам извлекает python-блоки из ответа модели и пишет их
на диск, компилирует (py_compile) и запускает. Также поддерживается [EXEC]...[/EXEC].
Везде добавлены логи уровня INFO/DEBUG для отладки.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ZAI_URL = "https://chat.z.ai/"
DEFAULT_MODEL = "GLM-5-Turbo"
DEFAULT_PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36")
LOG = logging.getLogger("zai-agent")

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
# JavaScript: extract {thinking, answer} from the LAST assistant message
# (the sibling that follows the LAST .user-message in the DOM).
# ---------------------------------------------------------------------------
# JS-экстрактор ответа из DOM chat.z.ai.
# Важно: узел ответа ищем от .thinking-chain-container (он есть всегда),
# а код собираем напрямую из <pre>/<code>, т.к. Z.ai рендерит ``` без fence-маркеров.
EXTRACT_JS = r"""
() => {
  // 1) Locate the assistant response node.
  let node = null;
  // Preferred: walk up from the last thought-process container (always present).
  const tcs = document.querySelectorAll('.thinking-chain-container');
  if (tcs.length) {
    let n = tcs[tcs.length - 1];
    let guard = 0;
    while (n && guard < 60) {
      guard++;
      const cls = (typeof n.className === 'string') ? n.className : '';
      if (cls.includes('message') || cls.includes('assistant') ||
          cls.includes('bubble') || cls.includes('response')) { node = n; break; }
      n = n.parentElement;
    }
  }
  // Fallback A: sibling after last .user-message
  if (!node) {
    const users = document.querySelectorAll('.user-message');
    if (users.length) {
      let n = users[users.length - 1].nextElementSibling;
      let guard = 0;
      while (n && guard < 50) {
        guard++;
        const cls = (typeof n.className === 'string') ? n.className : '';
        if (cls.includes('message') || cls.includes('assistant')) { node = n; break; }
        n = n.nextElementSibling;
      }
    }
  }
  // Fallback B: last non-user message-ish element
  if (!node) {
    const all = document.querySelectorAll(
      '[class*="assistant" i], [class*="message" i], [class*="bot" i], [class*="response" i]');
    for (let k = all.length - 1; k >= 0; k--) {
      const cls = (typeof all[k].className === 'string') ? all[k].className : '';
      if (!cls.toLowerCase().includes('user')) { node = all[k]; break; }
    }
  }
  if (!node) return null;

  // 2) Thinking (Thought Process) text
  let thinking = '';
  const bq = node.querySelector('blockquote');
  if (bq) { const t = (bq.innerText || '').trim(); if (t) thinking = t; }
  if (!thinking) {
    const tb = node.querySelector('.thinking-block, .thought-process, [class*="thinking" i]');
    if (tb) { const t = (tb.innerText || '').trim(); if (t) thinking = t; }
  }

  // 3) Answer text (exclude the thinking blockquote / thinking block)
  let answer = '';
  const sel = '.text-start, .markdown-body, .markdown, .message-content, ' +
              '[class*="content" i], [class*="answer" i]';
  const parts = [];
  node.querySelectorAll(sel).forEach(el => {
    if (el.closest('blockquote')) return;
    if (el.closest('[class*="thinking" i]')) return;
    const t = (el.innerText || '').trim();
    if (t && !t.startsWith('Thought Process')) parts.push(t);
  });
  if (parts.length) answer = parts.join('\n\n');
  else {
    const clone = node.cloneNode(true);
    const b = clone.querySelector('blockquote'); if (b) b.remove();
    const th = clone.querySelector('[class*="thinking" i]'); if (th) th.remove();
    const t = (clone.innerText || '').trim();
    if (t) answer = t;
  }

  // 4) Code blocks rendered as <pre>/<code> (Z.ai strips ``` fences in DOM)
  const code = [];
  const seen = new Set();
  const push = (txt) => { const t = (txt || '').trim(); if (t && !seen.has(t)) { seen.add(t); code.push(t); } };
  node.querySelectorAll(
    'pre, pre code, code, [class*="code" i], [class*="hljs" i], [class*="language-" i]'
  ).forEach(el => push(el.innerText));

  // 5) Идёт ли ещё генерация: видна ли кнопка Stop (ранее отдельный _is_generating)
  let generating = false;
  const stopSels = ['button[aria-label*="stop" i]',
                    'button[aria-label*="останов" i]',
                    '[data-testid*="stop" i]'];
  for (const s of stopSels) {
    const el = document.querySelector(s);
    if (el && el.getClientRects().length > 0) { generating = true; break; }
  }

  return {thinking: thinking, answer: answer, code: code, generating: generating};
}
"""


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


# ---------------------------------------------------------------------------
# Shell command executor (with safety + logging)
# ---------------------------------------------------------------------------
# Выполняет shell-команду и возвращает (rc, вывод); блокирует опасные команды.
# 24: exec_tool_command — выполняет shell-команду на хосте
def exec_tool_command(cmd: str, work_dir: Path, timeout: float) -> tuple[int, str]:
    print("24: exec_tool_command — выполняет shell-команду на хосте")
    """Execute a shell command. Returns (returncode, output)."""
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


_SYSTEM_PATH_GUARD = ("/etc", "/usr", "/sys", "/proc", "/boot", "/bin",
                       "/sbin", "/lib", "/lib64", "/var", "/")


# Нормализует путь: абсолютные разрешены везде, кроме системных каталогов.
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
def launch_chrome(settings: BrowserSettings) -> subprocess.Popen | None:
    if settings.cdp_port <= 0:
        LOG.info("[CHROME] cdp disabled")
        return None
    settings.profile.mkdir(parents=True, exist_ok=True)
    clean_profile_locks(settings.profile)
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
        "--disable-blink-features=AutomationControlled",
        "--enable-features=WebRtcHideLocalIpsWithMdns",
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
        ZAI_URL,
    ]
    if not settings.headed:
        cmd.insert(1, "--headless=new")
    LOG.info("[CHROME] launching: %s", chrome)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 45
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{settings.cdp_port}/json/version", timeout=1) as r:
                if r.status == 200:
                    LOG.info("[CHROME] CDP port open")
                    return proc
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("Chrome did not open CDP port")


# ===========================================================================
# ZaiWorker
# ===========================================================================
# Поток-воркер: держит браузер и исполняет запросы к chat.z.ai.
class ZaiWorker(threading.Thread):
# __init__: метод/функция агента.
    def __init__(self, settings: BrowserSettings, work_dir: Path,
                 tool_timeout: float = 300, max_tool_iters: int = 6) -> None:
        super().__init__(name="zai-browser-worker", daemon=True)
        self.settings = settings
        self.work_dir = work_dir
        self.tool_timeout = tool_timeout
        self.max_tool_iters = max_tool_iters
        self.jobs: queue.Queue[Job] = queue.Queue()
        self.stop_event = threading.Event()
        self.ready = threading.Event()
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
            file_input = self.page.locator('input[type="file"]').first
            if not file_input.count():
                LOG.warning("[ATTACH] no file input found")
                return False
            file_input.set_input_files(str(p))
            LOG.info("[ATTACH] set_input_files %s", path)
            for _ in range(10):
                self.page.wait_for_timeout(500)
                chip = self.page.locator(f'text="{p.name}"').first
                if chip.count() and chip.is_visible():
                    LOG.info("[ATTACH] file chip appeared: %s", p.name)
                    return True
            LOG.warning("[ATTACH] file chip did NOT appear: %s", p.name)
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
            self.page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ctx.add_init_script("""
                Object.defineProperty(navigator,'webdriver',{get:()=>false});
                Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
            """)
            self.page.on("crash", lambda: LOG.error("[PAGE] crashed"))
            self.page.on("pageerror", lambda e: LOG.error("[PAGE] JS error: %s", e))

            LOG.info("[WORKER] navigating to %s", ZAI_URL)
            self.page.goto(ZAI_URL, wait_until="domcontentloaded", timeout=60000)
            self._wait_composer()
            # self._dump_page_source()
            self.ready.set()
            LOG.info("[WORKER] ready")

            while not self.stop_event.is_set():
                try:
                    job = self.jobs.get(timeout=0.5)
                except queue.Empty:
                    continue
                try:
                    LOG.info("[WORKER] handling job kind=%s", job.kind)
                    if job.kind == "ask":
                        job.result = self._ask(job.payload["message"],
                                               job.payload.get("model"),
                                               job.payload.get("timeout", 300))
                    elif job.kind == "model":
                        job.result = {"model": self.selected_model}
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
# Ждёт появления поля ввода (textarea) в чате.
    # 12: _wait_composer — ждёт появления поля ввода (textarea)
    def _wait_composer(self):
        print("12: _wait_composer — ждёт появления поля ввода (textarea)")
        for sel in ('textarea[placeholder]', 'textarea', '#chat-input',
                    '.messageInputContainer textarea'):
            try:
                loc = self.page.locator(sel).first
                loc.wait_for(state="visible", timeout=15000)
                LOG.info("[COMPOSER] found via selector: %s", sel)
                return loc
            except Exception as e:
                LOG.debug("[COMPOSER] selector %s not found: %s", sel, e)
        raise RuntimeError("Composer (textarea) not found")

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
        for sel in ('button[aria-label*="send" i]',
                    'button[aria-label*="отправ" i]',
                    'button[type="submit"]',
                    '.messageInputContainer button'):
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
        """Debug: dump the last assistant/message node HTML for DOM inspection."""
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

    # 14: _click_thought_process — раскрывает вкладку 'Мышление' (кликает переключатель)
    def _click_thought_process(self) -> bool:
        print("14: _click_thought_process — раскрывает вкладку 'Мышление' (клик переключателя)")
        for sel in ('.thinking-chain-container button',
                    'button:has-text("Мышление")',
                    'button:has-text("Thought Process")',
                    'button:has-text("Thinking")',
                    'span:has-text("Мышление")',
                    'div:has-text("Мышление")',
                    '[class*="thinking" i] button'):
            try:
                loc = self.page.locator(sel).first
                if loc.count() and loc.is_visible(timeout=1000):
                    loc.click(timeout=2000)
                    LOG.info("[THOUGHT] clicked via %s", sel)
                    return True
            except Exception as e:
                LOG.debug("[THOUGHT] selector %s failed: %s", sel, e)
        return False

    # 14b: _thought_is_collapsed — True, если блок рассуждений скрыт (его надо раскрыть)
    def _thought_is_collapsed(self) -> bool:
        # Свёрнуто == блок рассуждений не виден. Если не удалось проверить — считаем свёрнутым.
        try:
            return not self.page.locator(".thinking-chain-container blockquote").first.is_visible(timeout=300)
        except Exception:
            return True

    # 15: _get_last_assistant_message — забирает ответ модели из DOM (thinking/answer/code)
    #     + флаг генерации (объединено с бывшим _is_generating: один вызов вместо двух)
    def _get_last_assistant_message(self) -> dict[str, Any] | None:
        # print("15: _get_last_assistant_message — забирает ответ модели из DOM (thinking/answer/code) + флаг генерации")
        try:
            data = self.page.evaluate(EXTRACT_JS)
            if not data:
                LOG.debug("[EXTRACT] no .user-message / no data")
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
        appeared = False

        while time.time() < deadline:
            self.page.wait_for_timeout(600)
            data = self._get_last_assistant_message()
            if not data:
                continue
            candidate = data.get("answer", "")
            if not candidate:
                continue
            appeared = True
            if candidate != last_answer:
                LOG.info("[ANSWER] grew to %d chars", len(candidate))
                last_answer = candidate
                stable_since = time.time()
                continue
            generating = data.get("generating", False)
            stable_for = time.time() - stable_since if stable_since else 0
            if stable_for >= 2.0 and not generating:
                LOG.info("[ANSWER] FINAL %d chars", len(candidate))
                return {"model": self.selected_model or DEFAULT_MODEL,
                        "answer": candidate, "code": data.get("code", [])}

        if appeared and last_answer:
            LOG.warning("[ANSWER] timeout, returning partial %d chars", len(last_answer))
            return {"model": self.selected_model or DEFAULT_MODEL,
                    "answer": last_answer, "code": (data or {}).get("code", []), "complete": False}
        raise TimeoutError("No answer from chat.z.ai")

# Парсит все файловые команды [WRITE]/[EDIT]/[APPEND]/[REPLACE]/[READ]/[LIST]/[DELETE].
    # 16: _parse_tools — парсит [WRITE]/[EDIT]/[READ]/[LIST]/[DELETE] и [EXEC] из ответа за один проход
    def _parse_tools(self, text: str) -> dict[str, Any]:
        print("16: _parse_tools — парсит файловые операции и [EXEC] команды из ответа за один проход")
        ops = {
            "writes":   [(m.group(1).strip(), m.group(2)) for m in _FILE_WRITE_RE.finditer(text)],
            "edits":    [(m.group(1).strip(), m.group(2)) for m in _FILE_EDIT_RE.finditer(text)],
            "appends":  [(m.group(1).strip(), m.group(2)) for m in _FILE_APPEND_RE.finditer(text)],
            "replaces": [(m.group(1).strip(), m.group(2), m.group(3)) for m in _FILE_REPLACE_RE.finditer(text)],
            "reads":    [m.group(1).strip() for m in _FILE_READ_RE.finditer(text)],
            "deletes":  [m.group(1).strip() for m in _FILE_DELETE_RE.finditer(text)],
            "lists":    [m.group(1).strip() for m in _FILE_LIST_RE.finditer(text)],
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

        # Очищаем текст от тегов команд, чтобы выделить чистые мысли
        clean_thoughts = text
        clean_thoughts = _FILE_WRITE_RE.sub("", clean_thoughts)
        clean_thoughts = _FILE_EDIT_RE.sub("", clean_thoughts)
        clean_thoughts = _EXEC_RE.sub("", clean_thoughts)
        clean_thoughts = _FENCE_BASH_RE.sub("", clean_thoughts)
        ops["thoughts"] = clean_thoughts.strip()
        return ops

# Нестриминговый запрос с инструментами и циклом правок файлов.
    # 29: _ask — нестриминговый запрос с инструментами
    def _ask(self, message: str, model: str | None, timeout: float) -> dict[str, Any]:
        print("29: _ask — нестриминговый запрос с инструментами")
        if self._first_message:
            self._first_message = False
            if self._system_profile:
                self._attach_system_profile()
            self._attach_tools_doc()
        if not message.startswith("[RESULT]"):
            message = AGENT_FS_INSTRUCTION.format(
                max_iters=self.max_tool_iters) + message
        raw = self._ask_raw(message, model, timeout)
        return self._run_tool_loop(raw["answer"], timeout, model, message)

    # ---- Tool helpers ----

    # ---- Generic file operations (create / read / edit any file) ----
# Обёртка resolve_safe для путей из команд модели.
    def _resolve_fs_path(self, path_str: str) -> Path:
        return resolve_safe(path_str, self.work_dir)

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

    # Ингест внешнего мышления: принимает текст (кусочки/целиком) и прогоняет через
    # те же инструменты, что и ответ модели (WRITE/EDIT/APPEND/REPLACE/DELETE/READ/LIST/EXEC).
    # Возвращает собранные результаты выполнения.
    def ingest_thinking(self, text: str) -> dict[str, Any]:
        parsed = self._parse_tools(text)
        ops = parsed
        cmds = parsed["cmds"]
        results: list[str] = []

        # Если в тексте есть размышления, отправляем их в виде потока мыслей
        thoughts = ops.get("thoughts", "")
        if thoughts:
            results.append(f"[Сервер: поток мыслей]\n{thoughts}")

        for path, content in ops["writes"] + ops["edits"]:
            res = self._do_write_file(path, content, append=False)
            results.append(f"[AGENT] Wrote: {res.get('path')} ({res.get('bytes')})"
                           if res.get("ok") else f"[AGENT] Write FAILED: {path}: {res.get('error')}")
        for path, content in ops["appends"]:
            res = self._do_write_file(path, content, append=True)
            results.append(f"[AGENT] Appended: {res.get('path')} ({res.get('bytes')})"
                           if res.get("ok") else f"[AGENT] Append FAILED: {path}: {res.get('error')}")
        for path, old, new in ops["replaces"]:
            res = self._do_replace_file(path, old, new)
            results.append(f"[AGENT] Replaced: {res.get('path')}"
                           if res.get("ok") else f"[AGENT] Replace FAILED: {path}: {res.get('error')}")
        for path in ops["deletes"]:
            res = self._do_delete_file(path)
            results.append(f"[AGENT] Deleted: {res.get('path')}"
                           if res.get("ok") else f"[AGENT] Delete FAILED: {path}: {res.get('error')}")
        for path in ops["reads"]:
            r = self._do_read_file(path)
            results.append(f"[FILE] {path}\n{r.get('content')}"
                           if r.get("ok") else f"[FILE-ERROR] {path}: {r.get('error')}")
        for path in ops["lists"]:
            r = self._do_list_dir(path)
            results.append(f"[DIR] {path}\n{r.get('listing')}"
                           if r.get("ok") else f"[DIR-ERROR] {path}: {r.get('error')}")
        for c in cmds[:1]:
            if c == self._last_stream_cmd:
                results.append(f"[AGENT] same command skipped: {c}")
                continue
            self._last_stream_cmd = c
            rc, out = exec_tool_command(c, self.work_dir, self.tool_timeout)
            results.append(f"[AGENT] $ {c}\n{out}")

        return {"ok": True,
                "parsed": {"writes": len(ops["writes"]), "edits": len(ops["edits"]),
                           "cmds": len(cmds)},
                "results": results}

    # Потоковая отправка кусочков мышления в агента. Копит дельты и, как только в буфере
    # оказывается завершённый блок инструментов ([/WRITE]/[/EDIT]/[/EXEC]), прогоняет
    # накопленный текст через ingest_thinking — агент исполняет его как свой собственный ответ.
    def send_thinking_to_agent(self, delta: str) -> None:
        if not hasattr(self, "_thinking_buf"):
            self._thinking_buf = ""

        # Добавляем префикс источника к блоку мышления
        tagged_delta = f"[Сервер: поток мыслей]\n{delta}"
        self._thinking_buf += tagged_delta

        if ("[/EXEC]" in self._thinking_buf or "[/WRITE]" in self._thinking_buf
                or "[/EDIT]" in self._thinking_buf or "[/APPEND]" in self._thinking_buf
                or "[/REPLACE]" in self._thinking_buf):
            try:
                self.ingest_thinking(self._thinking_buf)
            except Exception as e:
                LOG.debug("[THINK-FEED] ingest failed: %s", e)
            self._thinking_buf = ""

# Сигнатура действий ответа — детект повторов без прогресса.
    # 25: _tool_signature — сигнатура действий ответа (детект повторов)
    def _tool_signature(self, ops: dict, cmds: list) -> str:
        print("25: _tool_signature — сигнатура действий ответа (детект повторов)")
        """Стабильная сигнатура всех файловых/shell-действий в ответе.
        Принимает уже распарсенные ops и cmds, чтобы не парсить текст дважды.
        """
        return repr((ops["writes"], ops["edits"], ops["appends"], ops["replaces"],
                     ops["reads"], ops["deletes"], ops["lists"], cmds))

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
            ops_sig = self._tool_signature(ops, cmds)
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
            rc, out = exec_tool_command(c, self.work_dir, self.tool_timeout)
            # Однократное выполнение: повторную отправку ошибки модели не делаем.
            break

        return {"model": self.selected_model or DEFAULT_MODEL, "answer": last}

    # ---- Streaming ----
# Один раунд стрима: отправка, раскрытие Мышления, поток токенов.
    # 11: _stream_one_round — раунд стрима: отправка, раскрытие Мышления, поток токенов
    def _stream_one_round(self, message: str):
        LOG.info("[STREAM-ROUND] sending message (%d chars)", len(message))
        composer = self._wait_composer()
        self._send_reliably(composer, message)

        # Ждём появления первого ответа, затем раскрываем вкладку «Мышление» (открыта для просмотра)
        for _ in range(30):
            self.page.wait_for_timeout(500)
            data = self._get_last_assistant_message()
            if data and (data.get("answer") or data.get("thinking")):
                LOG.info("[STREAM-ROUND] first content appeared")
                # self._click_thought_process()  # временно отключено: клик сворачивает «Мышление»
                break

        thinking = data.get("thinking", "") or ""
        deadline = time.time() + 900
        last_thinking = ""
        last_answer = ""
        stable_since = 0.0
        poll = 0
        last_thought_click = 0.0  # защита от дёрганья: не чаще раза в 1.5 с
        # «Мышление»: раскрываем ТОЛЬКО если оно свёрнуто (клик переключателя иначе свернёт)
        if thinking and  self._thought_is_collapsed():# and (time.time() - last_thought_click > 1.5):
           self._click_thought_process()
           last_thought_click = time.time()
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

            if len(thinking) > len(last_thinking):
                delta = thinking[len(last_thinking):]
                last_thinking = thinking
                self.send_thinking_to_agent(delta)
                yield {"type": "thinking_delta", "delta": delta}
                print("МЫШЛЕНИЕ[+]:", delta)
          
            if answer and len(answer) > len(last_answer):
                delta = answer[len(last_answer):]
                last_answer = answer
                stable_since = time.time()
                yield {"type": "answer_delta", "delta": delta}

            generating = data.get("generating", False)
            stable_for = time.time() - stable_since if stable_since else 0
            if not generating and stable_for >= 2.5 and last_answer:
                LOG.info("[STREAM-ROUND] FINAL answer.len=%d thinking.len=%d",
                         len(last_answer), len(last_thinking))
                yield {"type": "done", "answer": last_answer, "thinking": last_thinking}
                return

        if last_answer:
            LOG.warning("[STREAM-ROUND] timeout but answer present")
            yield {"type": "done", "answer": last_answer, "thinking": last_thinking, "complete": False}
        else:
            LOG.warning("[STREAM-ROUND] NO CONTENT FOUND")
            try:
                self.page.screenshot(path="zai_stream_debug.png")
                LOG.warning("[STREAM-ROUND] screenshot -> zai_stream_debug.png")
            except Exception:
                pass
            yield {"type": "done", "answer": "", "thinking": last_thinking, "error": "timeout"}

# Стриминговый запрос с теми же инструментами и циклом правок.
    # 6: _ask_stream_raw — стриминговый запрос к модели + цикл инструментов
    def _ask_stream_raw(self, message: str, model: str | None, timeout: float):
        print("6: _ask_stream_raw — стриминговый запрос к модели + цикл инструментов")
        if not message.startswith("[RESULT]"):
            message = AGENT_FS_INSTRUCTION.format(
                max_iters=self.max_tool_iters) + message
        LOG.info("[STREAM] ===== start prompt.len=%d", len(message))
        
     
        last_model_answer = ""
        last_thinking = ""
        prev_tool_sig: str | None = None
        for iteration in range(self.max_tool_iters):
            LOG.info("[STREAM] tool-iteration=%d", iteration)
            answer = ""
            for chunk in self._stream_one_round(message):
             if chunk["type"] == "done":
                 answer = chunk.get("answer", "")
                 last_thinking = chunk.get("thinking", "")
             elif chunk["type"] in ("answer_delta", "thinking_delta"):
                 yield chunk  # pass through to client
            LOG.info("[STREAM] got answer.len=%d", len(answer))
            if not answer:
                LOG.warning("[STREAM] empty answer and no code -> stop tool loop")
                self._dump_last_answer_html()
                break
            last_model_answer = answer
            
            print("stop")
            input()

            # Stop if the model emits the exact same actions as the previous round
            # (no progress) — avoids re-writing / re-running identical content.
            parsed = self._parse_tools(answer)
            ops = parsed
            cmds = parsed["cmds"]
            ops_sig = self._tool_signature(ops, cmds)
            if prev_tool_sig is not None and ops_sig == prev_tool_sig:
                LOG.warning("[STREAM] identical tool actions as previous round -> stop (no progress)")
                break
            prev_tool_sig = ops_sig

            # 1) Explicit file WRITE / EDIT (any path, any extension)
            explicit = (ops["writes"] or ops["edits"] or ops["appends"]
                        or ops["replaces"] or ops["deletes"])
            for path, content in ops["writes"] + ops["edits"]:
                res = self._do_write_file(path, content, append=False)
                if res.get("ok"):
                    yield {"type": "answer_delta",
                           "delta": f"\n[AGENT] Wrote file: {res['path']} ({res['bytes']} bytes)\n"}
                else:
                    yield {"type": "answer_delta",
                           "delta": f"\n[AGENT] Write FAILED: {path}: {res.get('error')}\n"}

            # 2) APPEND
            for path, content in ops["appends"]:
                res = self._do_write_file(path, content, append=True)
                if res.get("ok"):
                    yield {"type": "answer_delta",
                           "delta": f"\n[AGENT] Appended to: {res['path']} ({res['bytes']} bytes)\n"}
                else:
                    yield {"type": "answer_delta",
                           "delta": f"\n[AGENT] Append FAILED: {path}: {res.get('error')}\n"}

            # 3) REPLACE (search & replace inside a file, any format)
            for path, old, new in ops["replaces"]:
                res = self._do_replace_file(path, old, new)
                if res.get("ok"):
                    yield {"type": "answer_delta",
                           "delta": f"\n[AGENT] Replaced in: {res['path']}\n"}
                else:
                    yield {"type": "answer_delta",
                           "delta": f"\n[AGENT] Replace FAILED: {path}: {res.get('error')}\n"}

            # 4) DELETE
            for path in ops["deletes"]:
                res = self._do_delete_file(path)
                if res.get("ok"):
                    yield {"type": "answer_delta",
                           "delta": f"\n[AGENT] Deleted: {res['path']}\n"}
                else:
                    yield {"type": "answer_delta",
                           "delta": f"\n[AGENT] Delete FAILED: {path}: {res.get('error')}\n"}

            # 5) READ -> feed file content back to the model
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

            # 6) LIST -> feed listing back to the model
            if ops["lists"]:
                fb = ""
                for path in ops["lists"]:
                    r = self._do_list_dir(path)
                    if r.get("ok"):
                        fb += f"\n[DIR]\n{path}\n---\n{r['listing']}\n[/DIR]"
                    else:
                        fb += f"\n[DIR-ERROR] {path}: {r.get('error')}"
                feedback = f"[RESULT] Directory listing:{fb}\n[/RESULT]"
                # Повторную отправку результата модели отключаем — однократное выполнение.
                break

            # 7) Shell commands (cmds уже распарсен в начале итерации)
            if not cmds:
                LOG.info("[STREAM] no [EXEC] -> tool loop done")
                break
            c = cmds[0]
            if c == self._last_stream_cmd:
                LOG.warning("[STREAM] same command repeated -> stop")
                break
            self._last_stream_cmd = c
            LOG.info("[STREAM-TOOL] exec: %s", c[:200])
            rc, out = exec_tool_command(c, self.work_dir, self.tool_timeout)
            yield {"type": "answer_delta", "delta": f"\n[AGENT] $ {c}\n{out}\n"}
            # Однократное выполнение: повторную отправку ошибки модели не делаем.
            break

        LOG.info("[STREAM] ===== finished")
        yield {"type": "done", "answer": last_model_answer}

    # ---- New chat ----
# Внутренний сброс чата (новый диалог) для воркера.
    def _new_chat(self) -> dict[str, Any]:
        self._first_message = True
        try:
            for sel in ('a[href="/"]', 'a:has-text("New chat")', 'button:has-text("New chat")'):
                try:
                    loc = self.page.locator(sel).first
                    if loc.count() and loc.is_visible():
                        loc.click()
                        self.page.wait_for_timeout(2000)
                        self._wait_composer()
                        return {"ok": True}
                except Exception:
                    pass
            self.page.goto(ZAI_URL, wait_until="domcontentloaded", timeout=60000)
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
    return {"ok": True, "service": "zai-agent"}

# GET /health — готовность воркера и текущая модель.
@app.get("/health")
def health():
    return {
        "ok": worker is not None and worker.start_error is None,
        "ready": bool(worker and worker.ready.is_set()),
        "model": worker.selected_model if worker else None,
    }

# GET /v1/models — список моделей (текущая модель).
@app.get("/v1/models")
def models():
    mid = worker.selected_model if worker else DEFAULT_MODEL
    return {"object": "list", "data": [{"id": mid, "object": "model",
            "owned_by": "zai", "created": int(time.time())}]}

# POST /v1/change_model — переключает модель в UI чата.
@app.post("/model")
def change_model(req: ModelRequest):
    if worker is None:
        raise HTTPException(503, "Worker not running")
    worker.selected_model = req.model
    LOG.info("[API] model changed -> %s", req.model)
    return {"model": req.model}

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
    if worker is None:
        raise HTTPException(503, "Worker not running")
    LOG.info("[API] /ask message.len=%d", len(req.message))
    return worker.submit("ask", {"message": req.message, "model": req.model,
                                 "timeout": req.timeout}, req.timeout + 30)

# POST /v1/chat/completions — OpenAI-совместимый вход (stream/non-stream).
# 3: completions — HTTP /v1/chat/completions (OpenAI-совместимый вход)
@app.post("/v1/chat/completions", response_model=None)
def completions(req: ChatRequest):
    # print("3: completions — HTTP /v1/chat/completions (OpenAI-совместимый вход)")
    if worker is None:
        raise HTTPException(503, "Worker not running")
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
            _stream_generator(prompt, req.model),
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

# Генератор SSE: преобразует события воркера в чанки чата.
# 4: _stream_generator — SSE-генератор: события воркера -> чанки чата
def _stream_generator(prompt: str, model: str | None):
    # print("4: _stream_generator — SSE-генератор: события воркера -> чанки чата")
    cmpl_id = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())
    model_name = model or (worker.selected_model if worker else DEFAULT_MODEL)
    q: queue.Queue = queue.Queue()
    worker.submit_stream(prompt, model, q)
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

# ---- File system endpoints ----
# POST /exec — выполнить shell-команду на хосте.
@app.post("/exec")
def exec_cmd(req: ExecRequest):
    if worker is None:
        raise HTTPException(503, "Worker not running")
    rc, out = exec_tool_command(req.command, worker.work_dir, req.timeout or worker.tool_timeout)
    return {"rc": rc, "output": out}

# POST /ingest/thinking — принять кусочки мышления извне и прогнать через инструменты агента.
@app.post("/ingest/thinking")
def ingest_thinking(req: ThinkingIngest):
    if worker is None:
        raise HTTPException(503, "Worker not running")
    return worker.ingest_thinking(req.text)

# GET /fs/list — список каталога.
@app.post("/fs/list")
def fs_list(req: FsPathRequest):
    if worker is None:
        raise HTTPException(503, "Worker not running")
    p = resolve_safe(req.path, worker.work_dir)
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
    p = resolve_safe(req.path, worker.work_dir)
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
    p = resolve_safe(req.path, worker.work_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a" if req.append else "w", encoding="utf-8") as f:
        f.write(req.content)
    return {"ok": True, "path": str(p), "bytes": len(req.content.encode("utf-8"))}

# POST /fs/mkdir — создание каталога.
@app.post("/fs/mkdir")
def fs_mkdir(req: FsMkdirRequest):
    if worker is None:
        raise HTTPException(503, "Worker not running")
    p = resolve_safe(req.path, worker.work_dir)
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": str(p)}

# POST /fs/delete — удаление файла/папки.
@app.post("/fs/delete")
def fs_delete(req: FsDeleteRequest):
    if worker is None:
        raise HTTPException(503, "Worker not running")
    p = resolve_safe(req.path, worker.work_dir)
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
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--cdp-port", type=int, default=9224)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--work-dir", default="/")
    parser.add_argument("--tool-timeout", type=float, default=300)
    parser.add_argument("--max-tool-iters", type=int, default=6)
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

    if args.cdp_port > 0:
        launch_chrome(BrowserSettings(profile, args.model, args.cdp_port, not args.headless))

    worker = ZaiWorker(
        BrowserSettings(profile, args.model, args.cdp_port, not args.headless),
        work_dir=work_dir,
        tool_timeout=args.tool_timeout,
        max_tool_iters=args.max_tool_iters,
    )
    worker.start()
    if not worker.ready.wait(90):
        raise RuntimeError("Worker not ready")
    if worker.start_error:
        raise worker.start_error

    import uvicorn
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    api_thread = threading.Thread(target=server.run, name="api-server", daemon=True)
    api_thread.start()
    time.sleep(1.5)
    LOG.info("[SERVER] ready at http://%s:%s", args.host, args.port)

    try:
        api_thread.join()
    except KeyboardInterrupt:
        LOG.info("[SERVER] stopping")
        server.should_exit = True
        api_thread.join(timeout=10)


if __name__ == "__main__":
    main()

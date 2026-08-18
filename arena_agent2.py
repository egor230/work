# -*- coding: utf-8 -*-
"""Устойчивый локальный gateway к Arena Direct.

Основная идея файла:

1. Chrome и Playwright живут отдельно от HTTP-сервера.
2. Все действия с одной вкладкой выполняются последовательно в одном Sync worker.
3. При сетевой ошибке, падении страницы или потере CDP worker несколько раз
   восстанавливает соединение и продолжает работу.
4. Модель может вызывать инструменты через [EXEC]...[/EXEC]. Результаты
   возвращаются модели через [RESULT]...[/RESULT] до завершения задачи.
5. У tool-loop есть общий deadline, лимиты количества итераций и диагностика.
6. Файловые endpoints также проходят через очередь worker, поэтому они не
   конфликтуют с командами, которые модель выполняет в тот же момент.

Это не официальный API Arena: скрипт управляет веб-интерфейсом через браузер.
Селекторы собраны с fallback-ами, потому что frontend сайта может измениться.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright

DIRECT_URL = "https://arena.ai/text/direct"
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_PROFILE = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/work"
DEFAULT_WORK_DIR = "/home/egor/Downloads"
LOG = logging.getLogger("arena-resilient")

_ASSISTANT_XPATH = (
    "xpath=//div[contains(concat(' ', normalize-space(@class), ' '), ' prose ')"
    " and not(ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' bg-surface-raised ')])]"
)
_USER_XPATH = (
    "xpath=//div[contains(concat(' ', normalize-space(@class), ' '), ' prose ')"
    " and ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' bg-surface-raised ')]]"
)
_EXEC_RE = re.compile(r"\[EXEC\][ \t]*\r?\n?([\s\S]*?)[ \t]*\r?\n?[ \t]*\[/EXEC\]", re.I)
_FENCE_BASH_RE = re.compile(r"```(?:bash|sh|shell|console|zsh|cmd)\s*\r?\n([\s\S]*?)```", re.I)
_DENY_TOOL = re.compile(
    r"\b(mkfs|fdisk|parted)\b|"
    r"\bdd\b[^\n;|]*\bof\s*=\s*/dev/(sd|nvme|hd)[a-z0-9]*\b|"
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+(/|/\s*\*|~)(\s|$)", re.I
)

AGENT_FS_INSTRUCTION = """[SYSTEM]
Ты агент, который может выполнять файловые и shell-инструменты на машине.
Рабочая директория: {workdir}

Когда задача требует посмотреть, создать, изменить, переместить или удалить
файлы, выдай команды строго в блоках:
[EXEC]
команда
[/EXEC]

Можно выдать несколько блоков. После выполнения ты получишь блоки
[RESULT]...[/RESULT]. Проанализируй результат и продолжай до полного
завершения задачи. Не описывай предполагаемый результат вместо выполнения.
В конце дай краткий понятный ответ пользователю.

Запрос пользователя:
"""


@dataclass
class BrowserSettings:
    profile: Path
    model: str
    cdp_port: int
    headed: bool
    direct_url: str = DIRECT_URL
    launch_timeout: float = 60.0
    reconnect_attempts: int = 5
    reconnect_backoff: float = 2.0
    launch_chrome: bool = True


@dataclass
class Job:
    kind: str
    payload: dict[str, Any]
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: BaseException | None = None
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancelled: threading.Event = field(default_factory=threading.Event)


class AskRequest(BaseModel):
    message: str = Field(min_length=1)
    model: str | None = None
    timeout: float = Field(default=900, ge=10, le=7200)
    file: str | None = None


class ModelRequest(BaseModel):
    model: str = Field(min_length=1)


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict[str, Any]] = Field(min_length=1)
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
    max_chars: int = Field(default=50000, ge=1, le=2_000_000)


class FsWriteRequest(BaseModel):
    path: str = Field(min_length=1)
    content: str = ""
    append: bool = False


class FsMkdirRequest(BaseModel):
    path: str = Field(min_length=1)


class FsDeleteRequest(BaseModel):
    path: str = Field(min_length=1)


def clean_stale_profile_lock(profile: Path) -> None:
    """Удаляет lock-файлы только если Chrome с этим profile не запущен."""
    if not profile.exists():
        return
    try:
        running = subprocess.run(
            ["pgrep", "-af", "--", f"--user-data-dir={profile}"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        if running:
            return
    except Exception as exc:
        LOG.warning("Не удалось проверить старый Chrome lock: %s", exc)
        return
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        try:
            (profile / name).unlink()
        except (FileNotFoundError, OSError):
            pass


def cdp_ready(port: int, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def launch_chrome(settings: BrowserSettings) -> subprocess.Popen | None:
    """Запускает видимый/головый Chrome и ждёт готовности CDP."""
    if settings.cdp_port <= 0:
        return None
    settings.profile.mkdir(parents=True, exist_ok=True)
    clean_stale_profile_lock(settings.profile)
    chrome = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        raise RuntimeError("Не найден google-chrome/chromium")
    cmd = [
        chrome, f"--user-data-dir={settings.profile}",
        f"--remote-debugging-port={settings.cdp_port}",
        "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check",
        "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding", "--disable-dev-shm-usage", "--disable-popup-blocking",
        "--password-store=basic", "--window-size=1400,1000", "--new-window", settings.direct_url,
    ]
    if not settings.headed:
        cmd.insert(1, "--headless=new")
    LOG.info("Запуск Chrome: profile=%s cdp=%s headed=%s", settings.profile, settings.cdp_port, settings.headed)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + settings.launch_timeout
    while time.monotonic() < deadline:
        if cdp_ready(settings.cdp_port):
            return proc
        if proc.poll() is not None:
            raise RuntimeError(f"Chrome завершился во время запуска, rc={proc.returncode}")
        time.sleep(0.25)
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        proc.kill()
    raise TimeoutError("Chrome не поднял CDP-порт")


def stop_process(proc: subprocess.Popen | None) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=8)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()


def resolve_safe(path_str: str, work_dir: Path) -> Path:
    """Проверяет, что путь находится внутри рабочей директории."""
    p = Path(path_str).expanduser()
    resolved = p.resolve() if p.is_absolute() else (work_dir / p).resolve()
    root = work_dir.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Путь вне рабочей директории: {resolved}")
    return resolved


def run_command(command: str, work_dir: Path, timeout: float, max_output: int = 10000) -> tuple[int, str]:
    """Выполняет одну команду в отдельной process group и возвращает rc/output."""
    command = command.strip()
    if not command:
        return 0, "(пустая команда)"
    if _DENY_TOOL.search(command):
        return 126, "Команда отклонена базовым фильтром опасных операций"
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            ["bash", "-c", command], cwd=work_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            start_new_session=True, env=dict(os.environ),
        )
        try:
            output, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                proc.kill()
            proc.communicate()
            return 124, f"Команда остановлена после timeout={timeout:.1f}s"
        output = (output or "").strip()
        if len(output) > max_output:
            output = output[:max_output] + "\n…(вывод обрезан)"
        return proc.returncode, output or "(нет вывода)"
    except Exception as exc:
        return 2, f"Ошибка запуска команды: {type(exc).__name__}: {exc}"


def atomic_write(path: Path, content: str, append: bool = False) -> int:
    """Записывает файл атомарно; append действительно добавляет данные."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with path.open("a", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        return len(content.encode("utf-8"))
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
    return len(content.encode("utf-8"))


class ArenaWorker(threading.Thread):
    """Единственный владелец Playwright-объектов и очереди операций."""
    def __init__(self, settings: BrowserSettings, work_dir: Path, agent_fs: bool = True,
                 tool_timeout: float = 300, max_tool_iters: int = 12,
                 max_tool_commands: int = 48, recovery_attempts: int = 4) -> None:
        super().__init__(name="arena-worker", daemon=False)
        self.settings = settings
        self.work_dir = work_dir.resolve()
        self.agent_fs = agent_fs
        self.tool_timeout = tool_timeout
        self.max_tool_iters = max_tool_iters
        self.max_tool_commands = max_tool_commands
        self.recovery_attempts = recovery_attempts
        self.jobs: queue.Queue[Job] = queue.Queue()
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.start_error: BaseException | None = None
        self.state = "STARTING"
        self.state_lock = threading.Lock()
        self.pw: Any = None
        self.browser: Any = None
        self.context: Any = None
        self.page: Any = None
        self.chrome_proc: subprocess.Popen | None = None
        self.selected_model = settings.model
        self.available_models: list[str] = []
        self.last_error = ""
        self.last_progress = time.time()

    def set_state(self, state: str, error: str = "") -> None:
        with self.state_lock:
            self.state = state
            if error:
                self.last_error = error
        LOG.info("[STATE] %s%s", state, f": {error}" if error else "")

    def status(self) -> dict[str, Any]:
        with self.state_lock:
            state, error = self.state, self.last_error
        return {
            "state": state, "ready": state == "READY", "model": self.selected_model,
            "queue_size": self.jobs.qsize(), "last_error": error,
            "alive": self.is_alive(), "last_progress": self.last_progress,
        }

    def submit(self, kind: str, payload: dict[str, Any], timeout: float) -> Any:
        if self.stop_event.is_set():
            raise RuntimeError("worker останавливается")
        job = Job(kind, payload)
        self.jobs.put(job)
        LOG.info("[QUEUE] submit id=%s kind=%s q=%s", job.job_id, kind, self.jobs.qsize())
        if not job.done.wait(timeout):
            job.cancelled.set()
            raise TimeoutError(f"job {job.job_id} превысил timeout={timeout:.1f}s")
        if job.error:
            raise job.error
        return job.result

    def run(self) -> None:
        try:
            self._connect_and_prepare()
            self.set_state("READY")
            self.ready.set()
            try:
                self.available_models = self._fetch_available_models()
            except Exception as exc:
                LOG.warning("Не удалось получить список моделей: %s", exc)
            while not self.stop_event.is_set():
                try:
                    job = self.jobs.get(timeout=0.5)
                except queue.Empty:
                    continue
                self.last_progress = time.time()
                if job.cancelled.is_set():
                    job.error = TimeoutError("job отменён до запуска")
                    job.done.set()
                    continue
                try:
                    self.set_state("BUSY")
                    job.result = self._dispatch(job)
                except Exception as exc:
                    job.error = exc
                    self.set_state("DEGRADED", str(exc))
                    LOG.exception("[JOB] failed id=%s kind=%s", job.job_id, job.kind)
                    # Ошибки браузера восстанавливаем до следующей задачи.
                    if self._looks_like_browser_error(exc):
                        self._recover("ошибка job: " + str(exc))
                finally:
                    self.last_progress = time.time()
                    job.done.set()
                    if not self.stop_event.is_set() and self.state == "BUSY":
                        self.set_state("READY")
        except Exception as exc:
            self.start_error = exc
            self.set_state("FAILED", str(exc))
            self.ready.set()
            LOG.exception("Worker не смог запуститься")
        finally:
            self._close_playwright()
            stop_process(self.chrome_proc)
            self.set_state("STOPPED")

    def _dispatch(self, job: Job) -> Any:
        if job.kind == "ask":
            return self._ask(job.payload["message"], job.payload.get("model"), job.payload.get("timeout", 900), job.cancelled)
        if job.kind == "model":
            return {"model": self._select_model(job.payload["model"])}
        if job.kind == "new_chat":
            return self._new_chat()
        if job.kind == "exec":
            return self._exec_api(job.payload["command"], job.payload.get("timeout") or self.tool_timeout)
        if job.kind == "fs_list":
            return self._fs_list(job.payload["path"])
        if job.kind == "fs_read":
            return self._fs_read(job.payload["path"], job.payload.get("max_chars", 50000))
        if job.kind == "fs_write":
            return self._fs_write(job.payload["path"], job.payload["content"], job.payload.get("append", False))
        if job.kind == "fs_mkdir":
            p = resolve_safe(job.payload["path"], self.work_dir); p.mkdir(parents=True, exist_ok=True); return {"ok": True, "path": str(p)}
        if job.kind == "fs_delete":
            return self._fs_delete(job.payload["path"])
        if job.kind == "recover":
            return {"ok": self._recover("manual request")}
        if job.kind == "dump_source":
            return self._dump_source()
        raise ValueError(f"Неизвестный job: {job.kind}")

    def _connect_and_prepare(self) -> None:
        self.set_state("CONNECTING")
        if self.settings.launch_chrome and (not self.chrome_proc or self.chrome_proc.poll() is not None):
            self.chrome_proc = launch_chrome(self.settings)
        self.pw = sync_playwright().start()
        self._connect_page()

    def _connect_page(self) -> None:
        if not cdp_ready(self.settings.cdp_port, timeout=2):
            raise RuntimeError(f"CDP-порт {self.settings.cdp_port} недоступен")
        self.browser = self.pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self.settings.cdp_port}")
        self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.on("crash", lambda: LOG.error("[BROWSER] page crash"))
        self.page.on("pageerror", lambda exc: LOG.warning("[BROWSER] pageerror: %s", exc))
        self.page.on("requestfailed", lambda req: LOG.warning("[NET] failed=%s url=%s", req.failure, req.url))
        self.page.goto(self.settings.direct_url, wait_until="domcontentloaded", timeout=90000)
        self.page.wait_for_timeout(3000)
        self._wait_composer()
        if self.settings.model:
            self._select_model(self.settings.model)

    def _close_playwright(self) -> None:
        for obj, method in ((self.browser, "close"), (self.pw, "stop")):
            try:
                if obj:
                    getattr(obj, method)()
            except Exception as exc:
                LOG.debug("close %s failed: %s", method, exc)
        self.browser = self.context = self.page = self.pw = None

    def _looks_like_browser_error(self, exc: Exception) -> bool:
        text = f"{type(exc).__name__}: {exc}".lower()
        return any(x in text for x in ("target closed", "browser", "page", "cdp", "timeout", "connection", "net::"))

    def _recover(self, reason: str) -> bool:
        self.set_state("RESTARTING", reason)
        for attempt in range(1, self.recovery_attempts + 1):
            if self.stop_event.is_set():
                return False
            LOG.warning("[RECOVERY] attempt=%s/%s reason=%s", attempt, self.recovery_attempts, reason)
            try:
                self._close_playwright()
                if self.settings.launch_chrome and (not self.chrome_proc or self.chrome_proc.poll() is not None):
                    self.chrome_proc = launch_chrome(self.settings)
                if self.pw is None:
                    self.pw = sync_playwright().start()
                self._connect_page()
                self.set_state("READY")
                return True
            except Exception as exc:
                self.last_error = str(exc)
                LOG.warning("[RECOVERY] failed: %s", exc)
                time.sleep(self.settings.reconnect_backoff * attempt)
        self.set_state("FAILED", "исчерпаны попытки восстановления")
        return False

    def _wait_composer(self) -> Any:
        for selector in ('textarea[placeholder*="Ask anything"]', 'textarea[placeholder*="anything"]', "textarea", '[contenteditable="true"]'):
            try:
                loc = self.page.locator(selector).first
                loc.wait_for(state="visible", timeout=15000)
                return loc
            except Exception:
                pass
        raise RuntimeError("Composer Arena не найден")

    def _fetch_available_models(self) -> list[str]:
        names: list[str] = []
        try:
            control = self.page.locator('button[aria-haspopup="dialog"]').first
            if not control.count() or not control.is_visible():
                control = self.page.locator('button[aria-haspopup="listbox"]').first
            control.click()
            search = self.page.locator('input[placeholder="Search models"]').first
            search.wait_for(state="visible", timeout=5000)
            search.fill("")
            self.page.wait_for_timeout(800)
            opts = self.page.locator('[role="option"]')
            for i in range(opts.count()):
                t = opts.nth(i).inner_text().strip().split("\n")[0]
                if t and t not in names:
                    names.append(t)
            self.page.keyboard.press("Escape")
        except Exception as exc:
            LOG.warning("[MODELS] %s", exc)
        return names

    def _select_model(self, model: str) -> str:
        model = model.strip()
        if not model or model.lower() in ("current", "auto", "*"):
            return self.selected_model
        if model == self.selected_model:
            return model
        control = self.page.locator('button[aria-haspopup="dialog"]').first
        if not control.count() or not control.is_visible():
            control = self.page.get_by_role("button", name=re.compile(r"Max|Direct|claude|gemini|gpt|qwen|glm|grok|deepseek|mistral", re.I)).first
        if not control.count() or not control.is_visible():
            raise RuntimeError("Переключатель модели не найден")
        control.click()
        search = self.page.locator('input[placeholder="Search models"]').first
        search.wait_for(state="visible", timeout=7000)
        search.fill(model)
        self.page.wait_for_timeout(800)
        opts = self.page.locator('[role="option"]')
        target = None
        for i in range(opts.count()):
            text = opts.nth(i).inner_text().strip().split("\n")[0]
            if text.lower() == model.lower() or model.lower() in text.lower():
                target = opts.nth(i); break
        if target is None:
            self.page.keyboard.press("Escape")
            raise RuntimeError(f"Модель не найдена: {model}")
        target.click(); self.page.wait_for_timeout(800)
        self.selected_model = model
        return model

    def _dump_source(self) -> dict[str, Any]:
        """Сохраняет HTML текущей страницы для диагностики изменения DOM Arena."""
        path = self.work_dir / "arena_page_source.html"
        path.write_text(self.page.content(), encoding="utf-8")
        return {"ok": True, "path": str(path), "bytes": path.stat().st_size}

    def _new_chat(self) -> dict[str, Any]:
        try:
            link = self.page.get_by_role("link", name="New Chat").first
            if link.count() and link.is_visible():
                link.click()
            else:
                self.page.goto(self.settings.direct_url, wait_until="domcontentloaded", timeout=90000)
            self.page.wait_for_timeout(2000)
            self._wait_composer()
            if self.selected_model:
                self._select_model(self.selected_model)
            return {"ok": True, "model": self.selected_model}
        except Exception as exc:
            if self._recover("new_chat: " + str(exc)):
                return {"ok": True, "recovered": True, "model": self.selected_model}
            raise

    def _send(self, text: str) -> None:
        composer = self._wait_composer()
        for attempt in range(1, 4):
            composer.click(); composer.fill(text)
            button = None
            for selector in ('button[aria-label="Send message"]', 'button[aria-label*="send" i]', 'button[title*="send" i]'):
                loc = self.page.locator(selector).last
                if loc.count() and loc.is_visible():
                    button = loc; break
            try:
                if button and button.is_enabled(timeout=1500):
                    button.click(timeout=5000, no_wait_after=True)
                else:
                    composer.press("Enter")
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    try:
                        if composer.input_value(timeout=500) != text:
                            return
                    except Exception:
                        return
                    self.page.wait_for_timeout(150)
            except Exception as exc:
                LOG.warning("[SEND] attempt=%s failed: %s", attempt, exc)
                if attempt == 3:
                    raise
                self._recover("send: " + str(exc))
        raise RuntimeError("Arena не приняла сообщение")

    def _assistant_texts(self) -> list[str]:
        try:
            return self.page.evaluate("() => [...document.querySelectorAll('div.prose')].filter(e => !e.closest('.bg-surface-raised')).map(e => (e.innerText||'').trim()).filter(Boolean)")
        except Exception:
            return []

    def _extract_answer(self, question: str, before: list[str]) -> str:
        prefix = question[:60]
        try:
            return self.page.evaluate("""(args) => {
                const q=args.q, before=args.before||[];
                const ol=document.querySelector('ol');
                if (ol) {
                    const kids=[...ol.children].filter(c=>c.querySelector&&c.querySelector('.prose'));
                    let qi=-1;
                    for(let i=kids.length-1;i>=0;i--) if(kids[i].querySelector('.bg-surface-raised') && (kids[i].innerText||'').includes(q)){qi=i;break;}
                    for(let i=(qi>=0?qi:kids.length)-1;i>=0;i--){
                        if(!kids[i].querySelector('.bg-surface-raised')){const p=kids[i].querySelector('.prose'); const t=(p?.innerText||'').trim(); if(t&&!before.includes(t)) return t;}
                    }
                }
                const all=[...document.querySelectorAll('div.prose')].filter(e=>!e.closest('.bg-surface-raised'));
                const t=all.length?(all[all.length-1].innerText||'').trim():'';
                return t&&!before.includes(t)?t:'';
            }""", {"q": prefix, "before": before}) or ""
        except Exception as exc:
            LOG.warning("[ANSWER] extraction failed: %s", exc)
            return ""

    def _is_generating(self) -> bool:
        for selector in ('button[aria-label*="stop" i]', '[data-testid*="stop" i]', 'button[title*="stop" i]'):
            try:
                loc = self.page.locator(selector).first
                if loc.count() and loc.is_visible():
                    return True
            except Exception:
                pass
        return False

    def _ask_raw(self, message: str, model: str | None, deadline: float, cancelled: threading.Event) -> dict[str, Any]:
        if model and model.strip().lower() not in ("", "current", "auto", "*"):
            self._select_model(model)
        before = self._assistant_texts()
        self._send(message)
        last = ""
        stable_since = 0.0
        while time.monotonic() < deadline:
            if cancelled.is_set():
                raise TimeoutError("запрос отменён клиентом")
            self.page.wait_for_timeout(500)
            candidate = self._extract_answer(message, before)
            if not candidate:
                continue
            if candidate != last:
                last, stable_since = candidate, time.monotonic()
                continue
            if time.monotonic() - stable_since >= 2.0 and not self._is_generating():
                return {"model": self.selected_model, "answer": candidate, "complete": True}
        if last:
            return {"model": self.selected_model, "answer": last, "complete": False}
        raise TimeoutError("Arena не вернула ответ до deadline")

    def _extract_commands(self, answer: str) -> list[str]:
        commands = [m.group(1).strip() for m in _EXEC_RE.finditer(answer) if m.group(1).strip()]
        if not commands:
            commands = [m.group(1).strip() for m in _FENCE_BASH_RE.finditer(answer) if m.group(1).strip()]
        return commands

    def _ask(self, message: str, model: str | None, timeout: float, cancelled: threading.Event) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        prompt = AGENT_FS_INSTRUCTION.format(workdir=self.work_dir) + message if self.agent_fs else message
        result = self._ask_raw(prompt, model, deadline, cancelled)
        if not self.agent_fs:
            return result
        answer = result["answer"]
        total_commands = 0
        for iteration in range(self.max_tool_iters):
            if time.monotonic() >= deadline:
                return {"model": self.selected_model, "answer": answer, "complete": False, "reason": "deadline"}
            commands = self._extract_commands(answer)
            if not commands:
                return {"model": self.selected_model, "answer": answer, "complete": result.get("complete", True), "tool_iterations": iteration}
            results = []
            for command in commands:
                total_commands += 1
                if total_commands > self.max_tool_commands:
                    return {"model": self.selected_model, "answer": answer, "complete": False, "reason": "tool_limit"}
                remaining = max(1.0, deadline - time.monotonic())
                rc, output = run_command(command, self.work_dir, min(self.tool_timeout, remaining))
                results.append(f"[RESULT]\n{command}\n→ rc={rc}\n{output}\n[/RESULT]")
                if time.monotonic() >= deadline:
                    return {"model": self.selected_model, "answer": answer, "complete": False, "reason": "deadline"}
            feedback = "Результаты выполнения инструментов. Продолжай задачу, если она ещё не завершена:\n\n" + "\n\n".join(results)
            result = self._ask_raw(feedback, None, deadline, cancelled)
            answer = result["answer"]
        return {"model": self.selected_model, "answer": answer, "complete": False, "reason": "tool_iteration_limit", "tool_iterations": self.max_tool_iters}

    def _exec_api(self, command: str, timeout: float) -> dict[str, Any]:
        rc, out = run_command(command, self.work_dir, timeout)
        return {"rc": rc, "output": out}

    def _fs_list(self, path: str) -> dict[str, Any]:
        p = resolve_safe(path, self.work_dir)
        if not p.exists(): raise FileNotFoundError(str(p))
        if p.is_file(): return {"ok": True, "path": str(p), "type": "file", "size": p.stat().st_size}
        return {"ok": True, "path": str(p), "type": "dir", "entries": [{"name": x.name, "type": "dir" if x.is_dir() else "file", "size": x.stat().st_size if x.is_file() else None} for x in sorted(p.iterdir(), key=lambda x: x.name.lower())]}

    def _fs_read(self, path: str, max_chars: int) -> dict[str, Any]:
        p = resolve_safe(path, self.work_dir)
        if not p.is_file(): raise FileNotFoundError(str(p))
        text = p.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "path": str(p), "content": text[:max_chars] + ("\n…(обрезано)" if len(text) > max_chars else "")}

    def _fs_write(self, path: str, content: str, append: bool) -> dict[str, Any]:
        p = resolve_safe(path, self.work_dir)
        return {"ok": True, "path": str(p), "bytes": atomic_write(p, content, append), "append": append}

    def _fs_delete(self, path: str) -> dict[str, Any]:
        p = resolve_safe(path, self.work_dir)
        if p == self.work_dir: raise ValueError("Нельзя удалить рабочую директорию")
        if p.is_dir(): shutil.rmtree(p)
        elif p.is_file(): p.unlink()
        else: raise FileNotFoundError(str(p))
        return {"ok": True, "path": str(p)}


worker: ArenaWorker | None = None
app = FastAPI(title="Arena Resilient Gateway", version="2.0")


def require_worker() -> ArenaWorker:
    if worker is None:
        raise HTTPException(503, "worker ещё не запущен")
    return worker


def api_call(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(504, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        LOG.exception("API error")
        raise HTTPException(502, str(exc)) from exc


@app.get("/")
def root() -> dict[str, Any]:
    return {"ok": True, "service": "arena-resilient", "api": "/v1"}


@app.get("/health")
def health() -> dict[str, Any]:
    return worker.status() if worker else {"state": "NOT_STARTED", "ready": False}


@app.post("/recover")
def recover() -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("recover", {}, 120))


@app.post("/model")
def model(req: ModelRequest) -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("model", {"model": req.model}, 60))


@app.post("/new_chat")
def new_chat() -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("new_chat", {}, 120))


@app.get("/v1/models")
def models() -> dict[str, Any]:
    w = require_worker()
    names = w.available_models or [w.selected_model]
    return {"object": "list", "data": [{"id": x, "object": "model", "owned_by": "arena", "created": int(time.time())} for x in names]}


@app.post("/dump_source")
def dump_source() -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("dump_source", {}, 60))


@app.post("/exec")
def execute(req: ExecRequest) -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("exec", {"command": req.command, "timeout": req.timeout}, (req.timeout or w.tool_timeout) + 30))


@app.post("/fs/list")
def fs_list(req: FsPathRequest) -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("fs_list", {"path": req.path}, 60))


@app.post("/fs/read")
def fs_read(req: FsReadRequest) -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("fs_read", {"path": req.path, "max_chars": req.max_chars}, 60))


@app.post("/fs/write")
def fs_write(req: FsWriteRequest) -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("fs_write", {"path": req.path, "content": req.content, "append": req.append}, 120))


@app.post("/fs/mkdir")
def fs_mkdir(req: FsMkdirRequest) -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("fs_mkdir", {"path": req.path}, 60))


@app.post("/fs/delete")
def fs_delete(req: FsDeleteRequest) -> dict[str, Any]:
    w = require_worker(); return api_call(lambda: w.submit("fs_delete", {"path": req.path}, 120))


@app.post("/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    w = require_worker()
    return api_call(lambda: w.submit("ask", {"message": req.message, "model": req.model, "timeout": req.timeout}, req.timeout + 60))


@app.post("/v1/chat/completions")
def completions(req: ChatRequest) -> dict[str, Any]:
    w = require_worker()
    parts: list[str] = []
    for item in req.messages:
        content = item.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in content)
        if str(content).strip():
            parts.append(str(content).strip())
    prompt = "\n\n".join(parts)
    result = api_call(lambda: w.submit("ask", {"message": prompt, "model": req.model, "timeout": 7200}, 7260))
    answer = result.get("answer", "")
    complete = result.get("complete", True)
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion", "created": int(time.time()),
        "model": result.get("model", req.model),
        "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop" if complete else "length"}],
        "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
        "x_arena": {"complete": complete, "reason": result.get("reason"), "tool_iterations": result.get("tool_iterations", 0)},
    }


def main() -> None:
    global worker
    parser = argparse.ArgumentParser(description="Resilient Arena Direct browser gateway")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--cdp-port", type=int, default=9223, help="0 — подключиться к уже запущенному Chrome на 9222")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--work-dir", default=DEFAULT_WORK_DIR)
    parser.add_argument("--no-agent-fs", action="store_true")
    parser.add_argument("--tool-timeout", type=float, default=300)
    parser.add_argument("--max-tool-iters", type=int, default=12)
    parser.add_argument("--max-tool-commands", type=int, default=48)
    parser.add_argument("--log-file", default="arena_agent_resilient.log")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(args.log_file, encoding="utf-8")])
    logging.getLogger("playwright").setLevel(logging.WARNING)

    settings = BrowserSettings(
        Path(args.profile).expanduser(), args.model,
        9222 if args.cdp_port == 0 else args.cdp_port,
        not args.headless,
        launch_chrome=(args.cdp_port != 0),
    )
    worker = ArenaWorker(settings, Path(args.work_dir).expanduser(), not args.no_agent_fs, args.tool_timeout, args.max_tool_iters, args.max_tool_commands)
    worker.start()
    if not worker.ready.wait(120):
        raise RuntimeError("worker не стал готов за 120 секунд")
    if worker.start_error:
        raise worker.start_error

    import uvicorn
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    stop = threading.Event()

    def shutdown_handler(signum: int, frame: Any) -> None:
        LOG.info("Получен сигнал %s, начинаю корректную остановку", signum)
        stop.set(); server.should_exit = True; worker.stop_event.set()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    try:
        server.run()
    finally:
        worker.stop_event.set()
        worker.join(timeout=20)
        stop_process(worker.chrome_proc)
        LOG.info("Сервис остановлен")


if __name__ == "__main__":
    main()

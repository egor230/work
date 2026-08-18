#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-file Arena Direct agent.

The file owns the visible Chrome process, one Playwright Sync worker thread,
a serialized task queue, model selection, robust message sending, answer
stabilization, and an OpenAI-compatible HTTP API.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright

DIRECT_URL = "https://arena.ai/text/direct"
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_PROFILE = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/work"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.7922.137 Safari/537.36"
LOG = logging.getLogger("arena-monolith")

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
AGENT_FS_INSTRUCTION = (
    "[SYSTEM] You are a file-system agent with shell access on this machine "
    "(working directory: {workdir}). When the user asks to list, read, create, "
    "write, edit, move, or delete files/folders, respond by emitting the "
    "command(s) inside [EXEC]...[/EXEC] blocks, for example:\n"
    "[EXEC]ls -la {workdir}[/EXEC]\n"
    "You may emit several [EXEC] blocks. After they run you will receive their "
    "output as [RESULT]...[/RESULT]; then continue until the task is complete "
    "and finish with a clear plain-text answer. Prefer safe commands; never run "
    "destructive commands like 'rm -rf /'.\n"
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
    maxc = 3500
    if len(output) > maxc:
        output = output[:maxc] + "\n…(вывод обрезан. Используй grep/sed/head/tail для нужного фрагмента)."
    if not output:
        output = "(нет вывода)"
    if notes:
        output = output + "\n\n[py_write_guard]\n" + "\n".join(f"- {n}" for n in notes)
    return rc, output


def _resolve_safe(path_str: str, work_dir: Path) -> Path:
    """Резолвит путь и гарантирует, что он внутри work_dir (безопасность FS API)."""
    p = Path(path_str).expanduser()
    p = p.resolve() if p.is_absolute() else (work_dir / p).resolve()
    wd = work_dir.resolve()
    if p != wd and wd not in p.parents:
        raise ValueError(f"Путь вне рабочей директории {wd}")
    return p

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


def launch_visible_chrome(settings: BrowserSettings) -> subprocess.Popen | None:
    if settings.cdp_port <= 0:
        return None
    settings.profile.mkdir(parents=True, exist_ok=True)
    clean_stale_profile_lock(settings.profile)
    chrome = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or shutil.which("chromium")
    cmd = [
        chrome,
        f"--user-data-dir={settings.profile}",
        f"--remote-debugging-port={settings.cdp_port}",
        "--remote-allow-origins=*",
        "--disable-blink-features=AutomationControlled",
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
        "--lang=en-US",
        "--use-fake-ui-for-media-stream",
        "--disable-popup-blocking",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-infobars",
        "--window-size=1200,900",
        "--new-window",
        DIRECT_URL,
    ]
    if not settings.headed:
        cmd.insert(1, "--headless=new")
    LOG.info("Открываю Chrome и Arena до запуска HTTP API")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 45
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{settings.cdp_port}/json/version", timeout=1) as r:
                if r.status == 200:
                    return proc
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("Chrome не поднял CDP-порт")


class ArenaWorker(threading.Thread):
    def __init__(self, settings: BrowserSettings, agent_fs: bool = True,
                 work_dir: Path = Path("/home/egor/Downloads"),
                 tool_timeout: float = 300, max_tool_iters: int = 6) -> None:
        super().__init__(name="arena-browser-worker", daemon=True)
        self.settings = settings
        self.agent_fs = agent_fs
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
        try:
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self.settings.cdp_port}")
            context = self.browser.contexts[0]
            self.page = context.pages[0] if context.pages else context.new_page()
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
            self.page.on("crash", lambda: LOG.error("[PAGE] Playwright сообщает: страница Arena crashed"))
            self.page.on("pageerror", lambda exc: LOG.error("[PAGE] JavaScript error: %s", exc))
            self.page.on("console", lambda msg: LOG.debug("[PAGE-CONSOLE] %s: %s", msg.type, msg.text))
            self.page.on("requestfailed", lambda req: LOG.warning("[NET] request failed: %s -> %s", req.failure, req.url))
            self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=60000)
            self.page.wait_for_timeout(3500)
            self._wait_composer()
            self._dump_page_source()
            self.selected_model = ""
            self._select_model(self.settings.model)
            self.ready.set()
            LOG.info("Arena готова, модель=%s", self.selected_model)
            try:
                self.available_models = self._fetch_available_models()
                LOG.info("[MODELS] available=%s", self.available_models)
            except Exception as exc:
                LOG.warning("[MODELS] fetch error: %s", exc)
            while not self.stop_event.is_set():
                try:
                    job = self.jobs.get(timeout=0.5)
                except queue.Empty:
                    continue
                try:
                    LOG.info("[WORKER] job started kind=%s", job.kind)
                    if job.kind == "ask":
                        job.result = self._ask(job.payload["message"], job.payload.get("model"), job.payload.get("timeout", 300))
                    elif job.kind == "model":
                        job.result = {"model": self._select_model(job.payload["model"])}
                    elif job.kind == "new_chat":
                        job.result = self._new_chat()
                    elif job.kind == "delete_chat":
                        job.result = self._delete_chat(job.payload.get("index"))
                    elif job.kind == "pin_chat":
                        job.result = self._pin_chat(job.payload.get("index"))
                    else:
                        raise ValueError(f"unknown job: {job.kind}")
                except BaseException as exc:
                    job.error = exc
                finally:
                    LOG.info("[WORKER] job finished kind=%s error=%s", job.kind, bool(job.error))
                    job.done.set()
        except BaseException as exc:
            self.start_error = exc
            self.ready.set()
            LOG.exception("browser worker failed")

    def _wait_composer(self) -> Any:
        for selector in ('textarea[placeholder*="Ask anything"]', 'textarea[placeholder*="anything"]', "textarea", '[contenteditable="true"]'):
            try:
                loc = self.page.locator(selector).first
                loc.wait_for(state="visible", timeout=15000)
                return loc
            except Exception:
                pass
        raise RuntimeError("Arena composer не найден")

    def _fetch_available_models(self) -> list[str]:
        names: list[str] = []
        try:
            control = None
            for loc in (
                self.page.get_by_role("button", name=re.compile(r"Max|Direct|claude|gemini|gpt|qwen", re.I)).first,
                self.page.locator('button[aria-haspopup="listbox"]').first,
            ):
                try:
                    if loc.count() and loc.is_visible():
                        control = loc
                        break
                except Exception:
                    pass
            if control is None:
                LOG.warning("[MODELS] переключатель модели не найден")
                return names
            LOG.info("[MODELS] opening model picker")
            control.click()
            search = self.page.locator('input[placeholder="Search models"]').first
            search.wait_for(state="visible", timeout=5000)
            search.fill("")
            self.page.wait_for_timeout(700)
            opts = self.page.locator('[role="option"]')
            for i in range(opts.count()):
                try:
                    t = opts.nth(i).inner_text().strip().split("\n")[0]
                except Exception:
                    t = ""
                if t and t not in names:
                    names.append(t)
            LOG.info("[MODELS] found %s options", len(names))
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)
        except Exception as exc:
            LOG.warning("[MODELS] fetch failed: %s", exc)
        return names

    def _dump_page_source(self, path: Path | None = None) -> str:
        try:
            html = self.page.content()
        except Exception as exc:
            LOG.warning("[DUMP] не удалось получить исходный код страницы: %s", exc)
            return ""
        if path is None:
            path = Path.cwd() / "arena_page_source.html"
        try:
            path.write_text(html, encoding="utf-8")
            LOG.info("[DUMP] исходный код страницы записан в %s (%s байт)", path, len(html))
        except Exception as exc:
            LOG.warning("[DUMP] не удалось записать файл %s: %s", path, exc)
        return str(path)

    def _select_model(self, model: str) -> str:
        LOG.info("[MODEL] requested=%s current=%s", model, self.selected_model)
        if self.selected_model == model:
            return model
        # Контрол выбора модели: кнопка с aria-haspopup="dialog", содержащая
        # текущее имя модели. Имя может быть любым (glm, grok, mistral, ...),
        # поэтому ищем по атрибуту, а не по конкретным подстрокам.
        control = None
        for loc in (
            self.page.locator('button[aria-haspopup="dialog"]').first,
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
            except Exception:
                pass
        if control is None:
            raise RuntimeError("переключатель модели Arena не найден")
        LOG.info("[MODEL] clicking model control")
        control.click()
        search = self.page.locator('input[placeholder="Search models"]').first
        try:
            search.wait_for(state="visible", timeout=5000)
            search.click()
            search.fill(model)
        except Exception as exc:
            LOG.warning("[MODEL] search fill failed: %s", exc)
        self.page.wait_for_timeout(700)
        # Опции — элементы с role="option" (проверено в _fetch_available_models);
        # имя модели лежит внутри <span class="font-mono">. Ищем точное совпадение
        # по inner_text, фолбэк — подстрока.
        opts = self.page.locator('[role="option"]')
        target = None
        for i in range(opts.count()):
            try:
                t = opts.nth(i).inner_text().strip().split("\n")[0]
            except Exception:
                t = ""
            if t and t.lower() == model.lower():
                target = opts.nth(i)
                break
        if target is None:
            for i in range(opts.count()):
                try:
                    t = opts.nth(i).inner_text().strip().split("\n")[0]
                except Exception:
                    t = ""
                if t and model.lower() in t.lower():
                    target = opts.nth(i)
                    break
        if target is None:
            raise RuntimeError(f"модель '{model}' не найдена в списке Arena")
        LOG.info("[MODEL] selecting option=%s", model)
        target.click()
        self.page.wait_for_timeout(700)
        self.selected_model = model
        return model

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
                        try:
                            self.page.screenshot(path=f"arena_after_click_{int(time.time())}.png")
                        except Exception as exc:
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
        if self.agent_fs:
            message = AGENT_FS_INSTRUCTION.format(workdir=self.work_dir) + message
        raw = self._ask_raw(message, model, timeout)
        if not self.agent_fs:
            return raw
        return self._run_tool_loop(raw["answer"], timeout, model)

    def _ask_raw(self, message: str, model: str | None, timeout: float) -> dict[str, Any]:
        LOG.info("[ASK] begin model=%s timeout=%s message=%r", model, timeout, message[:200])
        # "arena-current"/"current"/"*"/пусто — использовать уже выбранную
        # в браузере модель (позволяет менять модель через /model и не дёргать
        # браузер на каждый вопрос из opencode).
        if model and str(model).strip().lower() not in ("", "current", "arena-current", "*", "auto"):
            self._select_model(model)
        self._ensure_no_login_modal()
        before = self._assistant_prose_texts_js()
        LOG.info("[ASK] baseline assistant prose=%s", len(before))
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
        while time.time() < deadline:
            self.page.wait_for_timeout(500)
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
        # Диагностика: сохраняем DOM переписки и скриншот, если ответ не найден.
        try:
            self.page.screenshot(path="arena_fail.png")
            dump = self.page.evaluate("() => { const ol = document.querySelector('ol'); return (ol || document.body).outerHTML; }")
            Path("arena_conversation_dump.html").write_text(dump, encoding="utf-8")
            LOG.error("[ANSWER] таймаут; DOM переписки сохранён в arena_conversation_dump.html, скриншот arena_fail.png")
        except Exception as exc:
            LOG.error("[ANSWER] не удалось сохранить дамп: %s", exc)
        raise TimeoutError("Arena не вернула ответ")

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
        """Прогоняет цикл: исполняем [EXEC]-команды, шлём результат модели, повторяем."""
        for _ in range(self.max_tool_iters):
            cmds = self._extract_tool_commands(answer)
            if not cmds:
                break
            LOG.info("[TOOL-LOOP] найдено команд=%s", len(cmds))
            results: list[str] = []
            for c in cmds:
                rc, out = _exec_tool_command(c, self.work_dir, self.tool_timeout)
                results.append(f"[RESULT]\n{c}\n→ (rc={rc})\n{out}\n[/RESULT]")
            feedback = "Результаты выполнения команд:\n" + "\n\n".join(results)
            try:
                answer = self._ask_raw(feedback, None, timeout)["answer"]
            except Exception as exc:  # noqa: BLE001
                LOG.warning("[TOOL-LOOP] шаг обратной связи не удался: %s", exc)
                break
        return {"model": self.selected_model, "answer": answer}


worker: ArenaWorker | None = None
app = FastAPI(title="Arena Monolith", version="1.0")


@app.get("/")
def root() -> dict[str, Any]:
    return {"ok": True, "service": "arena-monolith", "api": "/v1"}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": worker is not None and worker.start_error is None, "ready": bool(worker and worker.ready.is_set()), "model": worker.selected_model if worker else None}


@app.get("/v1/models")
def models() -> dict[str, Any]:
    if worker and worker.available_models:
        data = [{"id": m, "object": "model", "owned_by": "arena", "created": int(time.time())} for m in worker.available_models]
    else:
        mid = worker.selected_model if worker else DEFAULT_MODEL
        data = [{"id": mid, "object": "model", "owned_by": "arena", "created": int(time.time())}]
    return {"object": "list", "data": data}


@app.post("/model")
def change_model(req: ModelRequest) -> dict[str, str]:
    if worker is None:
        raise HTTPException(503, "worker не запущен")
    try:
        return worker.submit("model", {"model": req.model}, 30)
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
            # Role используется только протоколом API и не должен попадать
            # в текст, который Selenium вводит в поле Arena.
            text_parts.append(str(content).strip())
    prompt = "\n\n".join(text_parts)
    try:
        result = worker.submit("ask", {"message": prompt, "model": req.model, "timeout": 900}, 930)
    except PermissionError as exc:
        raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc
    answer = result["answer"]
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
    payload = {"model": DEFAULT_MODEL, "messages": [{"role": "user", "content": question}]}
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
    except Exception as exc:
        LOG.exception("[TEST] request failed elapsed=%.2fs", time.time() - started)
        raise


def main() -> None:
    global worker
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--cdp-port", type=int, default=9223, help="0 — использовать уже запущенный Chrome на 9222")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--test-question", default="Сколько пальцев на руке человека?", help="Тестовый вопрос для --self-test")
    parser.add_argument("--self-test", action="store_true", help="Отправить автоматический тестовый вопрос сразу после старта (по умолчанию не отправляется)")
    parser.add_argument("--work-dir", default="/home/egor/Downloads", help="Рабочая директория для файловых операций агента")
    parser.add_argument("--no-agent-fs", action="store_true", help="Отключить агентские файловые функции (tool-loop и [EXEC])")
    parser.add_argument("--tool-timeout", type=float, default=300, help="Таймаут выполнения bash-команды агента, сек")
    parser.add_argument("--max-tool-iters", type=int, default=6, help="Макс. число итераций tool-loop")
    args = parser.parse_args()
    log_file = Path.cwd() / "arena_agent.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
    )
    logging.getLogger("playwright").setLevel(logging.WARNING)
    LOG.info("[BOOT] логи пишутся в %s", log_file)
    profile = Path(args.profile).expanduser()
    work_dir = Path(args.work_dir).expanduser()
    if args.cdp_port == 0:
        cdp_port = 9222
    else:
        cdp_port = args.cdp_port
        launch_visible_chrome(BrowserSettings(profile, args.model, cdp_port, not args.headless))
    worker = ArenaWorker(
        BrowserSettings(profile, args.model, cdp_port, not args.headless),
        agent_fs=not args.no_agent_fs,
        work_dir=work_dir,
        tool_timeout=args.tool_timeout,
        max_tool_iters=args.max_tool_iters,
    )
    worker.start()
    if not worker.ready.wait(90):
        raise RuntimeError("worker не стал готов за 90 секунд")
    if worker.start_error:
        raise worker.start_error
    import uvicorn
    # Сначала поднимаем HTTP API, затем отправляем тестовый запрос именно
    # через этот API. После теста сервер остаётся доступным для клиента.
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    api_thread = threading.Thread(target=server.run, name="api-server", daemon=True)
    api_thread.start()
    time.sleep(1.5)
    if args.self_test:
        try:
            send_test_question(f"http://{args.host}:{args.port}", args.test_question)
            LOG.info("[TEST] SELF-TEST PASSED")
        except Exception:
            LOG.exception("[TEST] SELF-TEST FAILED; server remains available")
    LOG.info("[SERVER] ready for external requests at http://%s:%s", args.host, args.port)
    try:
        api_thread.join()
    except KeyboardInterrupt:
        LOG.info("[SERVER] stopping")
        server.should_exit = True
        api_thread.join(timeout=10)


if __name__ == "__main__":
    main()

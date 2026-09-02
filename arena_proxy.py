#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arena_proxy.py - server-proxy between external agent and Arena.

Architecture:
    External agent -> HTTP -> this server -> Playwright/CDP -> Chrome + Arena
    Arena returns complete plan with [EXEC] commands and DONE.
    Server executes ALL commands locally (no re-querying Arena),
    verifies result on disk, returns structured JSON to agent.

Key differences from arena_agent2.py:
    1. No tool-loop: server gets full plan and executes it itself.
    2. DONE from model is NOT proof - real verification needed.
    3. SSE streaming for state events.
    4. Idempotency by request_id.
    5. Command execution journal per task.
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
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright

# -- Constants ---------------------------------------------------------------
DIRECT_URL = "https://arena.ai/text/direct"
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_PROFILE = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/work"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.7922.137 Safari/537.36"
)
LOG = logging.getLogger("arena-proxy")

_DENY_TOOL = re.compile(
    r"\b(mkfs|fdisk|parted)\b|"
    r"\bdd\b[^\n;|]*\bof\s*=\s*/dev/(sd|nvme|hd)[a-z0-9]*\b|"
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+(/|/\s*\*|~)(\s|$)"
)
_EXEC_RE = re.compile(
    r"\[EXEC\][ \t]*\r?\n?([\s\S]*?)[ \t]*\r?\n?[ \t]*\[/(?:EXEC|RESULT)\]"
)
_DONE_RE = re.compile(r"(?im)^\s*(?:DONE|\u0413\u041e\u0422\u041e\u0412\u041e)\s*[:\.]?\s*")

BRIDGE_SYSTEM_PROMPT = """[SYSTEM] You are a file-operation planner. Your task: compose a COMPLETE plan of bash commands and return it in ONE message.

Response format:
1. Short description of the step (optional).
2. [EXEC]command[/EXEC] - bash command.
3. Repeat for each command.
4. End with: DONE: brief summary.

RULES:
- For Python files, use: echo '<base64_content>' | base64 -d > "path/file.py"
- base64 encoding is MANDATORY for .py files (preserves indentation).
- Include verification: python3 -m py_compile "file.py"
- Include running the file if it is a script: python3 "file.py"
- Include directory check: ls -d "path"
- Do NOT repeat successfully executed commands.
- Return ALL commands in ONE message. After DONE, do not add commands.
- If directory creation needed - first mkdir -p.
- Target directory: {target_dir}
"""

# -- Request / Response models ------------------------------------------------


class AgentTaskRequest(BaseModel):
    request: str = Field(min_length=1)
    directory: str = Field(min_length=1)
    filename: str = ""
    request_id: str | None = None
    model: str | None = None
    timeout: float = Field(default=300, ge=30, le=900)
    stream: bool = False


class ModelRequest(BaseModel):
    model: str = Field(min_length=1)


# -- Task journal -------------------------------------------------------------

@dataclass
class CommandRecord:
    index: int
    command: str
    rc: int = -1
    output: str = ""
    timestamp: float = 0.0


@dataclass
class TaskJournal:
    request_id: str
    status: str = "created"  # created -> running -> completed | failed
    commands: list[CommandRecord] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    model_answer: str = ""
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "commands_executed": len(self.commands),
            "command_details": [
                {"index": c.index, "command": c.command, "rc": c.rc, "output": c.output[:200]}
                for c in self.commands
            ],
            "created_files": self.created_files,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


# -- Utility functions ---------------------------------------------------------

def _exec_command(cmd: str, work_dir: Path, timeout: float = 120) -> tuple[int, str]:
    """Execute a bash command safely and return (rc, output)."""
    cmd = cmd.strip()
    if _DENY_TOOL.search(cmd):
        return 1, "Command rejected: dangerous operation blocked."
    try:
        proc = subprocess.Popen(
            ["bash", "-c", cmd],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=str(work_dir), start_new_session=True,
        )
        try:
            output, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            output, _ = proc.communicate()
            return 124, f"Command timed out ({timeout}s) and was killed."
    except Exception as e:
        return 2, f"Failed to execute: {e}"
    rc = proc.returncode
    output = (output or "").strip()
    if not output:
        output = "(no output)"
    if len(output) > 3500:
        output = output[:3500] + "\n...(truncated)"
    return rc, output


def _verify_py_file(path: Path) -> tuple[bool, str]:
    """Verify a Python file: exists, readable, passes py_compile."""
    if not path.exists():
        return False, f"File does not exist: {path}"
    if not path.is_file():
        return False, f"Not a file: {path}"
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Cannot read file: {e}"
    if not content.strip():
        return False, "File is empty"
    try:
        compile(content, str(path), "exec")
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    rc, out = _exec_command(f'python3 -m py_compile "{path}"', path.parent, 30)
    if rc != 0:
        return False, f"py_compile failed: {out}"
    return True, "OK"


def _run_py_file(path: Path, timeout: float = 30) -> tuple[int, str]:
    """Run a Python file and return (rc, output)."""
    return _exec_command(f'python3 "{path}"', path.parent, timeout)


def _normalize_cmd(cmd: str) -> str:
    return re.sub(r"\s+", " ", cmd.strip())


def _extract_exec_commands(text: str) -> list[str]:
    """Extract all [EXEC]...[/EXEC] commands from model response."""
    cmds = []
    for m in _EXEC_RE.finditer(text):
        c = m.group(1).strip()
        if c:
            cmds.append(c)
    return cmds


def _has_done(text: str) -> bool:
    return bool(_DONE_RE.search(text or ""))


def _resolve_path(path_str: str, root: Path) -> Path:
    """Resolve path safely within root."""
    p = Path(path_str).expanduser()
    p = p.resolve() if p.is_absolute() else (root / p).resolve()
    r = root.resolve()
    if p != r and r not in p.parents:
        raise ValueError(f"Path outside allowed root {r}")
    return p


def _detect_target_file(cmds: list[str], target_dir: Path, preferred: str) -> Path | None:
    """Detect which file the commands will create."""
    if preferred:
        return target_dir / preferred
    for cmd in cmds:
        m = re.search(r'\>\s*"([^"]+)"', cmd)
        if m:
            p = Path(m.group(1))
            if not p.is_absolute():
                p = target_dir / p
            return p
    return None


# -- Browser Worker -----------------------------------------------------------

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


def launch_chrome(settings: BrowserSettings) -> subprocess.Popen | None:
    if settings.cdp_port <= 0:
        return None
    settings.profile.mkdir(parents=True, exist_ok=True)
    clean_stale_profile_lock(settings.profile)
    chrome = (shutil.which("google-chrome-stable")
              or shutil.which("google-chrome")
              or shutil.which("chromium"))
    if not chrome:
        raise RuntimeError("Chrome/Chromium not found in PATH")
    cmd = [
        chrome,
        f"--user-data-dir={settings.profile}",
        f"--remote-debugging-port={settings.cdp_port}",
        "--remote-allow-origins=*",
        "--enable-features=WebRtcHideLocalIpsWithMdns",
        f"--user-agent={DEFAULT_UA}",
        "--accept-lang=en-US,en;q=0.9",
        "--no-first-run", "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=site-per-process",
        "--password-store=basic",
        "--disable-popup-blocking",
        "--disable-dev-shm-usage",
        "--disable-gpu", "--disable-software-rasterizer",
        "--disable-infobars",
        "--window-size=1200,900",
        "--new-window",
        DIRECT_URL,
    ]
    if not settings.headed:
        cmd.insert(1, "--headless=new")
    LOG.info("Launching Chrome with CDP port %s", settings.cdp_port)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 45
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{settings.cdp_port}/json/version", timeout=1
            ) as r:
                if r.status == 200:
                    return proc
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("Chrome failed to expose CDP port")


def _login_visible(page: Any) -> bool:
    try:
        body = page.locator("body").inner_text(timeout=2000)
        return bool(re.search(
            r"Log In or Create Account|Continue with Google|Continue with email",
            body, re.I,
        ))
    except Exception:
        return False


class ArenaWorker(threading.Thread):
    """Single-threaded Playwright worker that talks to Arena via Chrome CDP."""

    def __init__(
        self,
        settings: BrowserSettings,
        task_root: Path = Path("/home/egor"),
    ) -> None:
        super().__init__(name="arena-proxy-worker", daemon=True)
        self.settings = settings
        self.task_root = task_root.expanduser().resolve()
        self.jobs: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.start_error: BaseException | None = None
        self.page: Any = None
        self.browser: Any = None
        self.pw: Any = None
        self.selected_model = settings.model
        self.available_models: list[str] = []
        self.completed_tasks: dict[str, dict[str, Any]] = {}
        self.journals: dict[str, TaskJournal] = {}

    # -- Job queue -----------------------------------------------------------

    def submit(self, kind: str, payload: dict, timeout: float = 900) -> Any:
        done_event = threading.Event()
        job = {"kind": kind, "payload": payload, "done": done_event,
               "result": None, "error": None}
        self.jobs.put(job)
        if not done_event.wait(timeout):
            raise TimeoutError("Worker did not respond in time")
        if job["error"]:
            raise job["error"]
        return job["result"]

    # -- Thread entry --------------------------------------------------------

    def run(self) -> None:
        try:
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.connect_over_cdp(
                f"http://127.0.0.1:{self.settings.cdp_port}"
            )
            context = self.browser.contexts[0]
            self.page = context.pages[0] if context.pages else context.new_page()

            # Anti-detect injections
            context.add_init_script("""
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
            """)

            self.page.on("crash", lambda: LOG.error("Page crashed"))
            self.page.on("pageerror", lambda exc: LOG.error("JS error: %s", exc))
            self.page.on("console",
                          lambda msg: LOG.debug("Console %s: %s", msg.type, msg.text))

            self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=60000)
            self.page.wait_for_timeout(3500)
            self._wait_composer()
            self.selected_model = ""
            self._select_model(self.settings.model)
            self.ready.set()
            LOG.info("Arena ready, model=%s", self.selected_model)

            try:
                self.available_models = self._fetch_models()
                LOG.info("Available models: %s", self.available_models)
            except Exception as exc:
                LOG.warning("Model fetch error: %s", exc)

            # Main loop
            while not self.stop_event.is_set():
                try:
                    job = self.jobs.get(timeout=0.5)
                except queue.Empty:
                    continue
                try:
                    kind = job["kind"]
                    if kind == "ask_raw":
                        job["result"] = self._ask_raw(**job["payload"])
                    elif kind == "agent_task":
                        job["result"] = self._agent_task_bridge(job["payload"])
                    elif kind == "model":
                        job["result"] = {
                            "model": self._select_model(job["payload"]["model"])
                        }
                    elif kind == "new_chat":
                        job["result"] = self._new_chat()
                    else:
                        raise ValueError(f"Unknown job kind: {kind}")
                except BaseException as exc:
                    job["error"] = exc
                finally:
                    job["done"].set()

        except BaseException as exc:
            self.start_error = exc
            self.ready.set()
            LOG.exception("Worker failed during startup")

    # -- Composer / Model selection -----------------------------------------

    def _wait_composer(self) -> Any:
        for sel in (
            'textarea[placeholder*="Ask anything"]',
            'textarea[placeholder*="anything"]',
            "textarea",
            '[contenteditable="true"]',
        ):
            try:
                loc = self.page.locator(sel).first
                loc.wait_for(state="visible", timeout=15000)
                return loc
            except Exception:
                pass
        raise RuntimeError("Arena composer not found")

    def _select_model(self, model: str) -> str:
        if self.selected_model == model:
            return model
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
            raise RuntimeError("Model selector not found")
        control.click()
        search = self.page.locator('input[placeholder="Search models"]').first
        try:
            search.wait_for(state="visible", timeout=5000)
            search.click()
            search.fill(model)
        except Exception as exc:
            LOG.warning("Model search fill failed: %s", exc)
        self.page.wait_for_timeout(700)
        opts = self.page.locator('[role="option"]')
        target = None
        # Exact match first
        for i in range(opts.count()):
            try:
                t = opts.nth(i).inner_text().strip().split("\n")[0]
            except Exception:
                t = ""
            if t and t.lower() == model.lower():
                target = opts.nth(i)
                break
        # Substring fallback
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
            raise RuntimeError(f"Model '{model}' not found in Arena")
        target.click()
        self.page.wait_for_timeout(700)
        self.selected_model = model
        return model

    def _fetch_models(self) -> list[str]:
        names: list[str] = []
        try:
            control = self.page.locator('button[aria-haspopup="listbox"]').first
            if not (control.count() and control.is_visible()):
                return names
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
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)
        except Exception as exc:
            LOG.warning("Model fetch failed: %s", exc)
        return names

    def _new_chat(self) -> dict[str, Any]:
        try:
            link = self.page.get_by_role("link", name="New Chat").first
            if link.count() and link.is_visible():
                link.click()
            else:
                self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(2000)
        self._wait_composer()
        if self.selected_model:
            try:
                self._select_model(self.selected_model)
            except Exception:
                pass
        return {"ok": True, "model": self.selected_model}

    # -- Message sending -----------------------------------------------------

    def _send_reliably(self, composer: Any, text: str) -> None:
        """Send text to Arena composer, retrying with different methods."""
        LOG.info("[SEND] chars=%s preview=%.120r", len(text), text)
        button = None
        for sel in (
            'button[aria-label="Send message"]',
            'button[aria-label*="send" i]',
            'button[aria-label*="\u043e\u0442\u043f\u0440\u0430\u0432" i]',
            'button[title*="send" i]',
        ):
            try:
                loc = self.page.locator(sel).last
                if loc.count() and loc.is_visible():
                    button = loc
                    break
            except Exception:
                pass

        for attempt in range(3):
            LOG.info("[SEND] attempt=%s", attempt + 1)
            composer.click()
            composer.fill(text)
            # Wait for fill to take effect
            deadline = time.time() + 5
            while time.time() < deadline:
                try:
                    val = composer.input_value(timeout=700)
                except Exception:
                    break
                if val == text:
                    break
                self.page.wait_for_timeout(100)

            clicked = False
            if button is not None:
                try:
                    if button.is_enabled(timeout=2000):
                        button.click(timeout=2000, no_wait_after=True)
                        clicked = True
                        self.page.wait_for_timeout(700)
                        if _login_visible(self.page):
                            raise PermissionError(
                                "Arena requires authorization")
                        if self._composer_changed(composer, text, 6):
                            return
                except PermissionError:
                    raise
                except Exception:
                    pass

            LOG.info("[SEND] button=%s, trying Enter fallback", clicked)
            try:
                composer.press("Enter")
            except Exception:
                pass
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(700)
            if _login_visible(self.page):
                raise PermissionError("Arena requires authorization")
            if self._composer_changed(composer, text, 6):
                return
            # Clear and retry
            try:
                composer.click()
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Delete")
            except Exception:
                pass
            self.page.wait_for_timeout(300)
        raise RuntimeError("Arena did not accept the message")

    @staticmethod
    def _composer_changed(composer: Any, old_text: str,
                          timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                val = composer.input_value(timeout=700)
            except Exception:
                return True  # field disappeared = message sent
            if val != old_text:
                return True
            time.sleep(0.2)
        return False

    # -- Answer extraction --------------------------------------------------

    def _assistant_texts_js(self) -> list[str]:
        return self.page.evaluate(
            "() => [...document.querySelectorAll('div.prose')]"
            ".filter(e => !e.closest('.bg-surface-raised'))"
            ".map(e => (e.innerText||'').trim()).filter(Boolean)"
        )

    def _extract_answer_js(self, message: str, before: list[str]) -> str:
        """Extract the latest assistant answer from Arena DOM.

        Arena uses <ol class="... flex-col-reverse ..."> so DOM order is
        inverted. User message (inside .bg-surface-raised) is the last child,
        assistant message (without .bg-surface-raised) precedes it.
        """
        q = message[:40]
        try:
            return self.page.evaluate(
                """(args) => {
                    const q = args.q;
                    const before = args.before || [];
                    const ol = document.querySelector('ol');
                    if (!ol) return '';
                    const kids = [...ol.children].filter(
                        c => c.querySelector && c.querySelector('.prose')
                    );
                    let userIdx = -1;
                    for (let i = kids.length - 1; i >= 0; i--) {
                        const txt = (kids[i].innerText || '');
                        if (kids[i].querySelector('.bg-surface-raised')
                            && txt.includes(q)) {
                            userIdx = i;
                            break;
                        }
                    }
                    const start = userIdx >= 0 ? userIdx : kids.length;
                    for (let i = start - 1; i >= 0; i--) {
                        const raised = kids[i].querySelector(
                            '.bg-surface-raised');
                        const p = kids[i].querySelector('.prose');
                        if (p && !raised) {
                            const t = (p.innerText || '').trim();
                            if (t && !before.includes(t)) return t;
                        }
                    }
                    const all = [...document.querySelectorAll('div.prose')]
                        .filter(e => !e.closest('.bg-surface-raised'));
                    const t = all.length
                        ? (all[all.length - 1].innerText || '').trim() : '';
                    return (t && !before.includes(t)) ? t : '';
                }""",
                {"q": q, "before": before},
            )
        except Exception as exc:
            LOG.warning("JS extract failed: %s", exc)
            return ""

    # -- Ask Arena (raw, NO tool loop) ---------------------------------------

    def _ask_raw(self, message: str, model: str | None,
                 timeout: float) -> dict[str, Any]:
        """Send message to Arena, wait for COMPLETE stabilized response.

        This method does NOT execute any commands or re-query Arena.
        It simply waits for the full text response to stabilize.
        """
        LOG.info("[ASK_RAW] model=%s timeout=%s msg=%.200r",
                 model, timeout, message)
        if model and str(model).strip().lower() not in (
            "", "current", "arena-current", "*", "auto"
        ):
            self._select_model(model)

        if _login_visible(self.page):
            raise PermissionError("Arena requires authorization")

        before = self._assistant_texts_js()
        composer = self._wait_composer()
        self._send_reliably(composer, message)

        # Wait for answer to appear and stabilize
        deadline = time.time() + timeout
        last = ""
        stable_since = 0.0
        appeared = False

        while time.time() < deadline:
            self.page.wait_for_timeout(500)
            candidate = self._extract_answer_js(message, before)
            if not candidate:
                continue
            appeared = True
            if candidate != last:
                if last and candidate.startswith(last):
                    LOG.info("[ANSWER] +%d chars (total %d)",
                             len(candidate) - len(last), len(candidate))
                else:
                    LOG.info("[ANSWER] changed (total %d)", len(candidate))
                last = candidate
                stable_since = time.time()
                continue

            # Text unchanged -- check if model is still generating
            generating = False
            for sel in (
                'button[aria-label*="stop" i]',
                '[data-testid*="stop" i]',
                'button[title*="stop" i]',
            ):
                try:
                    loc = self.page.locator(sel).first
                    if loc.count() and loc.is_visible():
                        generating = True
                        break
                except Exception:
                    pass

            stable_for = time.time() - stable_since if stable_since else 0
            LOG.info("[ANSWER] stable_for=%.1fs generating=%s",
                     stable_for, generating)

            # Consider response complete when:
            # 1. Text has been stable for 2+ seconds
            # 2. No "stop" button visible (model finished generating)
            # 3. Response contains DONE marker (bonus confidence)
            has_done = _has_done(last)
            min_stable = 1.5 if has_done else 2.0

            if stable_for >= min_stable and not generating:
                LOG.info("[ANSWER] FINAL (%d chars) has_done=%s",
                         len(candidate), has_done)
                return {
                    "model": self.selected_model,
                    "answer": candidate,
                    "complete": True,
                }

        if appeared and last:
            LOG.warning("[ANSWER] timeout, returning last text (%d chars)",
                         len(last))
            return {
                "model": self.selected_model,
                "answer": last,
                "complete": False,
            }

        # Save diagnostics
        try:
            self.page.screenshot(path="arena_proxy_fail.png")
            dump = self.page.evaluate(
                "() => { const ol = document.querySelector('ol');"
                " return (ol || document.body).outerHTML; }"
            )
            Path("arena_proxy_dump.html").write_text(dump, encoding="utf-8")
        except Exception:
            pass
        raise TimeoutError("Arena did not return a response")

    # -- Core: Agent task bridge (NO tool loop!) ----------------------------

    def _agent_task_bridge(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Main method: get plan from Arena, execute locally, verify, return.

        CRITICAL: This method does NOT re-query Arena after executing commands.
        It gets a complete plan, executes all commands locally, then verifies
        the real result on disk.

        Verification truth: NOT what the model says (DONE), but what actually
        exists on disk and passes checks.
        """
        request_text = str(payload["request"]).strip()
        request_id = str(payload.get("request_id") or "").strip()
        if not request_id:
            request_id = uuid.uuid4().hex
        directory = str(payload["directory"]).strip()
        filename = str(payload.get("filename") or "").strip()
        model = payload.get("model")
        timeout = float(payload.get("timeout", 300))

        # -- Idempotency: return cached result for same request_id ----------
        if request_id in self.completed_tasks:
            LOG.info("[TASK] returning cached result for %s", request_id)
            return dict(self.completed_tasks[request_id])

        # -- Create journal ---------------------------------------------------
        journal = TaskJournal(
            request_id=request_id,
            status="running",
            started_at=time.time(),
        )
        self.journals[request_id] = journal

        # Event accumulator (for both sync and SSE responses)
        events: list[str] = [
            "\u043f\u043e\u043b\u0443\u0447\u0435\u043d\u043e \u0437\u0430\u0434\u0430\u043d\u0438\u0435",
        ]

        try:
            # -- Resolve target directory ------------------------------------
            target_dir = _resolve_path(directory, self.task_root)
            target_dir.mkdir(parents=True, exist_ok=True)
            events.append("\u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u0430")

            # -- Step 1: Send task to Arena (ONE time only!) -------------------
            LOG.info("[TASK] step=arena_query request_id=%s", request_id)
            events.append("\u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043a Arena")

            prompt = BRIDGE_SYSTEM_PROMPT.format(target_dir=target_dir)
            prompt += request_text

            arena_result = self._ask_raw(prompt, model, timeout)
            answer = arena_result["answer"]
            journal.model_answer = answer

            LOG.info("[TASK] arena responded len=%d has_done=%s",
                     len(answer), _has_done(answer))
            events.append("\u043c\u043e\u0434\u0435\u043b\u044c \u043e\u0442\u0432\u0435\u0447\u0430\u0435\u0442")
            events.append("\u043e\u0442\u0432\u0435\u0442 \u043f\u043e\u043b\u0443\u0447\u0435\u043d")

            # -- Step 2: Extract ALL commands from the answer -----------------
            commands = _extract_exec_commands(answer)
            LOG.info("[TASK] extracted %d commands", len(commands))

            if not commands:
                journal.status = "failed"
                journal.error = "No [EXEC] commands found in model response"
                journal.finished_at = time.time()
                events.append("\u043a\u043e\u043c\u0430\u043d\u0434\u044b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b")
                result = {
                    "ok": False, "complete": False, "status": "failed",
                    "message": "Model did not return executable commands",
                    "path": str(target_dir / filename) if filename else str(target_dir),
                    "verified": False, "request_id": request_id,
                    "error": "No [EXEC] commands in model response",
                    "events": events,
                }
                self.completed_tasks[request_id] = dict(result)
                return result

            # -- Step 3: Execute ALL commands locally --------------------------
            # CRITICAL: No re-querying Arena! Execute sequentially, skip dupes.
            LOG.info("[TASK] step=execute_commands count=%d", len(commands))
            seen_cmds: dict[str, bool] = {}  # normalized -> success
            all_rc_ok = True
            run_output = ""

            for idx, cmd in enumerate(commands):
                norm = _normalize_cmd(cmd)

                # Skip already successfully executed commands (anti-loop)
                if seen_cmds.get(norm, False):
                    LOG.info("[TASK] skipping duplicate #%d: %.80s", idx, cmd)
                    continue

                LOG.info("[TASK] exec #%d/%d: %.120s",
                         idx + 1, len(commands), cmd)
                rc, output = _exec_command(cmd, target_dir, timeout=120)

                record = CommandRecord(
                    index=idx, command=cmd, rc=rc,
                    output=output, timestamp=time.time(),
                )
                journal.commands.append(record)

                if rc == 0:
                    seen_cmds[norm] = True
                    LOG.info("[TASK] command #%d OK", idx + 1)
                    events.append(f"\u043a\u043e\u043c\u0430\u043d\u0434\u0430 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0430: {cmd[:60]}")
                else:
                    all_rc_ok = False
                    LOG.warning("[TASK] command #%d FAILED rc=%d: %.200s",
                                 idx + 1, rc, output)
                    events.append(f"\u043a\u043e\u043c\u0430\u043d\u0434\u0430 \u043e\u0448\u0438\u0431\u043a\u0430 (rc={rc}): {cmd[:60]}")
                    # Continue: model may have planned recovery steps

                # Detect file run command (to capture output for result)
                if (".py" in cmd
                        and ("python3 " in cmd or "python " in cmd)
                        and ">" not in cmd and "py_compile" not in cmd):
                    if rc == 0:
                        run_output = output

            # -- Step 4: Determine target file and VERIFY on disk ------------
            LOG.info("[TASK] step=verify on disk")
            events.append("\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0444\u0430\u0439\u043b\u0430")

            target_file = _detect_target_file(commands, target_dir, filename)
            verified = False
            verification_details = ""

            if target_file and target_file.suffix.lower() == ".py":
                # Full verification checklist:
                # 1. File exists on disk
                # 2. Path is inside target directory
                # 3. File is readable
                # 4. Python syntax check passes (compile + py_compile)
                ok, msg = _verify_py_file(target_file)
                if ok:
                    verification_details = msg
                    # 5. If not already run, execute it
                    if not run_output:
                        rc, out = _run_py_file(target_file, timeout=30)
                        if rc == 0:
                            run_output = out
                            verified = True
                        else:
                            verification_details += (
                                f"; run failed (rc={rc}): {out[:200]}"
                            )
                    else:
                        verified = True
                    # Track created file
                    if str(target_file) not in journal.created_files:
                        journal.created_files.append(str(target_file))
                else:
                    verification_details = msg

            elif target_file:
                # Non-Python: verify exists and readable
                if target_file.exists() and target_file.is_file():
                    try:
                        target_file.read_text(encoding="utf-8")
                        verified = True
                        verification_details = "File exists and readable"
                        if str(target_file) not in journal.created_files:
                            journal.created_files.append(str(target_file))
                    except Exception as e:
                        verification_details = f"Cannot read: {e}"
                else:
                    verification_details = f"File not found: {target_file}"
            else:
                verification_details = "No specific target file detected"
                # Fallback: if we saw file creation commands succeed,
                # try to use the preferred filename
                if filename and all_rc_ok:
                    fallback = target_dir / filename
                    if fallback.exists():
                        target_file = fallback
                        if target_file.suffix.lower() == ".py":
                            ok, msg = _verify_py_file(target_file)
                            if ok:
                                verified = True
                                verification_details = "Verified via fallback"
                                if str(target_file) not in journal.created_files:
                                    journal.created_files.append(str(target_file))

            # -- Step 5: Determine final status --------------------------------
            # SUCCESS = all commands rc=0 AND file verified on disk
            # DONE from model alone is NOT sufficient!
            is_complete = all_rc_ok and verified

            if is_complete:
                journal.status = "completed"
                events.append("\u0444\u0430\u0439\u043b \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d")
                events.append("\u0437\u0430\u0434\u0430\u0447\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430")
            else:
                journal.status = "failed"
                if not all_rc_ok:
                    failed = [c.command[:80]
                              for c in journal.commands if c.rc != 0]
                    journal.error = f"Commands failed: {failed}"
                elif not verified:
                    journal.error = (
                        f"Verification failed: {verification_details}"
                    )
                events.append("\u0437\u0430\u0434\u0430\u0447\u0430 \u043d\u0435 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430")

            journal.finished_at = time.time()

            # Build final result
            result: dict[str, Any] = {
                "ok": is_complete,
                "complete": is_complete,
                "status": journal.status,
                "message": (
                    "\u0412\u0441\u0451 \u0433\u043e\u0442\u043e\u0432\u043e"
                    if is_complete
                    else "\u0417\u0430\u0434\u0430\u0447\u0430 \u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0430"
                ),
                "path": str(target_file) if target_file else str(target_dir),
                "verified": verified,
                "request_id": request_id,
                "events": events,
            }

            if is_complete and run_output:
                # Extract the useful output (skip "(no output)")
                result["result"] = run_output.strip()
            if not is_complete:
                result["error"] = journal.error
                result["verification_details"] = verification_details

            # Cache for idempotency
            self.completed_tasks[request_id] = dict(result)

            LOG.info(
                "[TASK] final: ok=%s complete=%s verified=%s path=%s",
                is_complete, is_complete, verified, result.get("path"),
            )
            return result

        except Exception as exc:
            LOG.exception("[TASK] exception")
            journal.status = "failed"
            journal.error = str(exc)
            journal.finished_at = time.time()
            events.append("\u043e\u0448\u0438\u0431\u043a\u0430")
            result = {
                "ok": False, "complete": False, "status": "failed",
                "message": str(exc),
                "path": str(target_dir) if 'target_dir' in dir() else "",
                "verified": False, "request_id": request_id,
                "error": str(exc), "events": events,
            }
            self.completed_tasks[request_id] = dict(result)
            raise

# -- HTTP API -----------------------------------------------------------------

worker: ArenaWorker | None = None
app = FastAPI(title="Arena Proxy", version="1.0")


def _require_worker() -> ArenaWorker:
    if worker is None:
        raise HTTPException(503, "Worker not started")
    if worker.start_error:
        raise HTTPException(503, f"Worker failed: {worker.start_error}")
    return worker


@app.get("/")
def root() -> dict[str, Any]:
    return {"ok": True, "service": "arena-proxy", "version": "1.0"}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": worker is not None and worker.start_error is None,
        "ready": bool(worker and worker.ready.is_set()),
        "model": worker.selected_model if worker else None,
    }


@app.get("/v1/models")
def models() -> dict[str, Any]:
    w = _require_worker()
    if w.available_models:
        data = [{"id": m, "object": "model", "owned_by": "arena",
                 "created": int(time.time())} for m in w.available_models]
    else:
        data = [{"id": w.selected_model, "object": "model",
                 "owned_by": "arena", "created": int(time.time())}]
    return {"object": "list", "data": data}


@app.post("/model")
def change_model(req: ModelRequest) -> dict[str, str]:
    w = _require_worker()
    try:
        return w.submit("model", {"model": req.model}, 30)
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/new_chat")
def new_chat() -> dict[str, Any]:
    w = _require_worker()
    try:
        return w.submit("new_chat", {}, 30)
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/agent/task")
def agent_task(req: AgentTaskRequest) -> dict[str, Any] | StreamingResponse:
    """Main endpoint: submit a task, get a verified result.

    If stream=true, returns SSE with state events and final JSON.
    If stream=false (default), returns JSON directly.

    The agent should stop working ONLY when the response contains:
        ok=true AND complete=true AND verified=true
    """
    w = _require_worker()
    payload = req.model_dump()

    if req.stream:
        return _stream_task(w, payload)

    # Synchronous JSON response
    try:
        return w.submit("agent_task", payload, req.timeout + 60)
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


def _stream_task(w: ArenaWorker, payload: dict) -> StreamingResponse:
    """SSE stream: send state events, then final JSON result."""
    request_id = payload.get("request_id") or uuid.uuid4().hex
    cmpl_id = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())
    model_name = (
        payload.get("model") or (w.selected_model if w else DEFAULT_MODEL)
    )

    def generate() -> Iterator[str]:
        def _sse(data: dict, finish: str | None = None) -> str:
            chunk = {
                "id": cmpl_id, "object": "chat.completion.chunk",
                "created": created, "model": model_name,
                "choices": [{
                    "index": 0, "delta": {}, "finish_reason": finish
                }],
            }
            chunk["choices"][0]["delta"] = data
            return "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"

        def _event(event: str, detail: str = "") -> str:
            return _sse({
                "thinking": f"[{event}] {detail}",
                "reasoning_content": f"[{event}] {detail}",
            })

        # Initial status events
        yield _event("status", "\u043f\u043e\u043b\u0443\u0447\u0435\u043d\u043e \u0437\u0430\u0434\u0430\u043d\u0438\u0435")
        yield _event("status", "\u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043a Arena")

        try:
            result = w.submit(
                "agent_task", payload,
                float(payload.get("timeout", 300)) + 60,
            )

            # Stream all events from result
            for ev in result.get("events", []):
                yield _event("status", ev)

            # Final chunk with complete result as JSON string
            yield _sse({
                "content": json.dumps(result, ensure_ascii=False, indent=2),
            }, finish="stop" if result.get("complete") else "length")
            yield "data: [DONE]\n\n"

        except Exception as exc:
            yield _event("error", str(exc))
            err_result = {
                "ok": False, "complete": False, "status": "failed",
                "message": str(exc), "verified": False,
                "request_id": request_id,
            }
            yield _sse({
                "content": json.dumps(err_result, ensure_ascii=False),
            }, finish="stop")
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/agent/journal/{request_id}")
def get_journal(request_id: str) -> dict[str, Any]:
    """Return execution journal for a task."""
    w = _require_worker()
    if request_id in w.journals:
        return w.journals[request_id].to_dict()
    if request_id in w.completed_tasks:
        return {
            "request_id": request_id,
            "status": "cached",
            "result": w.completed_tasks[request_id],
        }
    raise HTTPException(404, f"Task {request_id} not found")


# -- Main ---------------------------------------------------------------------

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
    for cmd in (["fuser", "-k", f"{port}/tcp"],
                ["pkill", "-f", f"arena_proxy.py.*--port {port}"]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
            break
        except Exception:
            continue
    time.sleep(1.5)


def main() -> None:
    global worker
    parser = argparse.ArgumentParser(
        description="Arena Proxy: bridge between external agent and Arena"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--cdp-port", type=int, default=9223,
                        help="CDP port (0 = use existing Chrome on 9222)")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--task-root", default="/home/egor",
                        help="Root directory for allowed file operations")
    args = parser.parse_args()

    log_file = Path.cwd() / "arena_proxy.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    logging.getLogger("playwright").setLevel(logging.WARNING)
    LOG.info("[BOOT] Logs: %s", log_file)

    _free_port(args.host, args.port)

    profile = Path(args.profile).expanduser()
    cdp_port = args.cdp_port if args.cdp_port != 0 else 9222
    if args.cdp_port != 0:
        launch_chrome(BrowserSettings(
            profile, args.model, cdp_port, not args.headless))

    worker = ArenaWorker(
        BrowserSettings(profile, args.model, cdp_port, not args.headless),
        task_root=Path(args.task_root).expanduser(),
    )
    worker.start()

    if not worker.ready.wait(90):
        raise RuntimeError("Worker did not become ready in 90 seconds")
    if worker.start_error:
        raise worker.start_error

    LOG.info("[SERVER] Arena Proxy ready at http://%s:%s", args.host, args.port)
    LOG.info("[SERVER] POST /agent/task         - main task endpoint")
    LOG.info("[SERVER] POST /agent/task stream   - SSE with events")
    LOG.info("[SERVER] GET  /agent/journal/{id}  - task journal")
    LOG.info("[SERVER] POST /model              - change model")
    LOG.info("[SERVER] POST /new_chat           - new Arena chat")

    import uvicorn
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    api_thread = threading.Thread(
        target=server.run, name="api-server", daemon=True)
    api_thread.start()
    time.sleep(1.5)

    try:
        api_thread.join()
    except KeyboardInterrupt:
        LOG.info("[SERVER] shutting down")
        server.should_exit = True
        api_thread.join(timeout=10)


if __name__ == "__main__":
    main()

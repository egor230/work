#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARENA HANDS — «мозги» на Arena (через живой мост LMArena_Bridge) + «руки» локально
(крошечная Gemma-4-e2b-it, GGUF, llama-cpp-python CPU).

Идея:
  1. МОЗГ (Arena, POST /ask raw:true) получает задачу пользователя и выдает СПЕЦИФИКАЦИЮ
     из микро-команд для рук (create file X with text Y / run command Z / read file W).
  2. РУКИ (Gemma-e2b) переводят каждую микро-команду в ТОЧНО ОДИН инструментальный токен
     [WRITE]/[EXEC]/[READ] — GBNF-грамматика физически запрещает модели «думать»:
     декодер может породить только валидный токен или [DONE].
  3. Оркестратор (этот скрипт) исполняет токены, возвращает [RESULT] обратно в чат рук,
     повторяет до [DONE] (бюджет 20 шагов) или эскалации к мозгу.
  4. ЭСКАЛАЦИЯ: руки топчутся на месте (та же ошибка 2 раза подряд) → оркестратор
     просит мозг выдать следующую/исправленную микро-команду.

ЗАПУСКАЕТ ТОЛЬКО ПОЛЬЗОВАТЕЛЬ (агентам запрещено):
  ./arena_hands.sh                     (или: myvenv/bin/python3 arena_hands.py)
  myvenv/bin/python3 arena_hands.py "задача"            — сразу задача
  myvenv/bin/python3 arena_hands.py --self-test         — без Arena, только руки
  myvenv/bin/python3 arena_hands.py --brain-dead        — Arena недоступна: всё делает Gemma

Файлы: PLAN.md / TASK_STATUS.md пишутся в рабочую директорию (--work-dir, дефолт $HOME),
логи — Project/hands_runs/<дата-время>/run.log.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------------------
# Константы
# --------------------------------------------------------------------------------------

MODEL_PATH = Path("/mnt/807EB5FA7EB5E954/Program Files/ai models/suryeon123/AI-soo-Gemma-4/gemma-4-e2b-it.Q4_K_M.gguf")
BRIDGE_URL = "http://127.0.0.1:8000"
WORK_DIR_DEFAULT = Path.home()
RUNS_DIR = Path(__file__).resolve().parent / "hands_runs"

MAX_STEPS = 20                # общий бюджет шагов (требование пользователя)
MAX_GEMMA_RETRY = 3           # попыток генерации токена на один ход рук
HANDS_MAX_ITER = 12           # внутренних итераций рук на одну микро-команду архитектора
HANDS_STALL_LIMIT = 3         # одинаковых [RESULT] подряд → эскалация
EXEC_TIMEOUT = 300            # сек, исполнение [EXEC]
READ_TAIL_LINES = 80          # хвост файла для [RESULT] (чтобы не раздувать контекст)
RESULT_CAP = 3500             # обрезка [RESULT] для контекста Gemma
SYS_LOG = None                # заполнится в main()
MOJIBAKE_FIX = None           # заполнится при первой необходимости (импорт из text_utils)

RE_WRITE = re.compile(r"\[WRITE\]\s*(.+?)\s*\n---\n(.*?)\[/WRITE\]", re.DOTALL)
RE_READ = re.compile(r"\[READ\]\s*(.+?)\s*\[/READ\]", re.DOTALL)
RE_EXEC = re.compile(r"\[EXEC\]\s*(.*?)\s*\[/EXEC\]", re.DOTALL)
RE_DONE = re.compile(r"\[DONE\]", re.DOTALL)

_DENY_RE = re.compile(
    r"(mkfs|fdisk|parted|dd\s+[^|]*of=/dev/|rm\s+-rf\s+/(?:\s|$)|rm\s+-rf\s+~|sudo\s+rm|:\(\)\{.*\};:"
    r"|shutdown|reboot|halt|poweroff|init\s+[06]|chmod\s+-R\s+777\s+/|mv\s+/\s+|>\s*/dev/sd)",
    re.IGNORECASE | re.DOTALL,
)

_SYSTEM_ROOTS = (
    "/etc", "/usr", "/var", "/proc", "/sys", "/boot", "/dev", "/run", "/lib",
    "/lib64", "/bin", "/sbin", "/root", "/opt/snap", "/snap",
)

# GBNF-грамматика: руки могут породить ТОЛЬКО валидный токен или [DONE]. Мышление
# невозможно синтаксически — свободного текста в грамматике нет.
GBNF = r'''root ::= item
item ::= exec | write | read | done
exec ::= "[EXEC]" line "[/EXEC]"
write ::= "[WRITE]" path "\n---\n" wtext "[/WRITE]"
read ::= "[READ]" path "[/READ]"
done ::= "[DONE]"
path ::= [a-zA-Z0-9_./~ -]+
line ::= [^\n]+
wtext ::= ([^[] | "[" [^/])*
'''

# --------------------------------------------------------------------------------------
# Лог
# --------------------------------------------------------------------------------------

def log(msg: str, level: str = "INFO") -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}"
    print(line, flush=True)
    if SYS_LOG is not None:
        try:
            SYS_LOG.write(line + "\n")
            SYS_LOG.flush()
        except Exception:
            pass


# --------------------------------------------------------------------------------------
# Инструменты (исполнение токенов) — защищённые, путь-резолверы, fuzzy
# --------------------------------------------------------------------------------------

def _resolve_fuzzy(path: Path) -> Path:
    """Потерянные ' - '/')' в имени — подобрать ближайшее реальное (SequenceMatcher>=0.75)."""
    if path.exists():
        return path
    parent = path.parent
    if not parent.exists():
        return path
    names = [p.name for p in parent.iterdir()]
    m = difflib.SequenceMatcher(None, "", "")
    best, score = None, 0.0
    for n in names:
        m.set_seq2(n)
        m.set_seq1(path.name)
        s = m.ratio()
        if s > score:
            best, score = n, s
    return parent / best if best and score >= 0.75 else path


def _in_allowed_path(path: Path) -> bool:
    p = str(path.resolve())
    return not any(p == r or p.startswith(r + "/") for r in _SYSTEM_ROOTS)


def _mojibake_repair(text: str) -> str:
    """Порча cp1252/latin-1 → UTF-8. Канонический источник — arena_text_utils."""
    global MOJIBAKE_FIX
    if MOJIBAKE_FIX is None:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent / ".." / "work" / "LMArena_Bridge"))
            from arena_text_utils import _fix_mojibake as _f
            MOJIBAKE_FIX = _f
        except Exception:
            MOJIBAKE_FIX = lambda t: t  # noqa: E731
    return MOJIBAKE_FIX(text)


def _cap(text: str, limit: int = RESULT_CAP) -> str:
    if len(text) <= limit:
        return text
    return text[:limit // 2] + "\n...[обрезано]...\n" + text[-limit // 2:]


def _py_syntax_ok(content: str) -> tuple[bool, str]:
    import ast
    try:
        ast.parse(content)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} (строка {e.lineno})"


def _write_file(path_str: str, content: str) -> tuple[int, str]:
    path_str = _mojibake_repair(path_str.strip())
    p = _resolve_fuzzy(Path(path_str))
    if not _in_allowed_path(p):
        return 1, f"ERROR: путь {p} в системном корне — запрещено"
    if p.suffix == ".py":
        ok, err = _py_syntax_ok(content)
        if not ok:
            return 1, f"ERROR: битый Python ({err}); файл НЕ записан"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            bak = p.with_suffix(p.suffix + ".bak")
            bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        p.write_text(content, encoding="utf-8")
        return 0, f"OK: записан {p} ({len(content)} симв.)"
    except Exception as e:
        return 1, f"ERROR записи {p}: {e}"


def _read_file(path_str: str) -> tuple[int, str]:
    path_str = _mojibake_repair(path_str.strip())
    p = _resolve_fuzzy(Path(path_str))
    if not p.is_file():
        return 1, f"ERROR: файл не найден: {p}"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        return 1, f"ERROR чтения {p}: {e}"
    if len(lines) > READ_TAIL_LINES:
        body = "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines[-READ_TAIL_LINES:], start=len(lines) - READ_TAIL_LINES))
        body = f"...(первые {len(lines)-READ_TAIL_LINES} строк пропущены)...\n" + body
    else:
        body = "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines))
    return 0, body if body else "(пустой файл)"


def _exec_command(cmd: str) -> tuple[int, str]:
    global EXEC_TIMEOUT
    if _DENY_RE.search(cmd):
        return 1, "ERROR: команда в deny-list (mkfs/dd/rm -rf и т.п.)"
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=EXEC_TIMEOUT, cwd=str(WORK_DIR.resolve()),
        )
    except subprocess.TimeoutExpired:
        return 1, f"ERROR: таймаут {EXEC_TIMEOUT}s команды: {cmd[:120]}"
    out = (proc.stdout or "") + (("\n[STDERR]\n" + proc.stderr) if proc.stderr.strip() else "")
    out = out.strip() or "(пустой вывод)"
    return proc.returncode, _cap(out, 6000)


def execute_token(text: str) -> tuple[str, int]:
    """Текст от Gemma → (результат-строка, rc). Возвращает ('NEED_RETRY', -1) если токен не распознан."""
    global WORK_DIR
    m = RE_DONE.search(text)
    if m:
        return "GOAL_COMPLETE", 0
    m = RE_WRITE.search(text)
    if m:
        path, body = m.group(1), m.group(2)
        if body.startswith("```"):  # снятие возможных ограждений
            body = re.sub(r"^```[a-z]*\n?", "", body)
            body = re.sub(r"\n?```\s*$", "", body)
        rc, rep = _write_file(path, body)
        return rep, rc
    m = RE_READ.search(text)
    if m:
        rc, rep = _read_file(m.group(1))
        return rep, rc
    m = RE_EXEC.search(text)
    if m:
        rc, rep = _exec_command(m.group(1))
        return rep, rc
    return "NEED_RETRY: токен не распознан", -1


# --------------------------------------------------------------------------------------
# РУКИ: Gemma-e2b (GBNF + temperature=0)
# --------------------------------------------------------------------------------------

HANDS_SYS = """You are HANDS: a dumb command-to-token converter. You NEVER think, plan, explain or ask. You translate ONE command from the architect into EXACTLY ONE tool token.

TOOLS:
[WRITE]path
---
full text[/WRITE]  - create file
[READ]path[/READ]  - read file
[EXEC]command[/EXEC]  - run bash command
[DONE]  - only when architect says GOAL COMPLETE

RULES:
- Output EXACTLY ONE token, nothing else.
- Copy paths and text from the architect command VERBATIM, byte-exact.
- Multi-line file text: emit real newlines between --- and [/WRITE].
- No markdown, no fences, no comments.

EXAMPLES:
Command: create file /tmp/a.txt with content "hello world"
Answer: [WRITE]/tmp/a.txt
---
hello world[/WRITE]
Command: show me contents of /tmp/a.txt
Answer: [READ]/tmp/a.txt[/READ]
Command: run the shell command that lists /tmp
Answer: [EXEC]ls -la /tmp[/EXEC]
Command: goal complete
Answer: [DONE]"""


class HandsModel:
    """Обёртка llama_cpp.Llama: держит модель в памяти, генерирует строго токены."""

    def __init__(self, model_path: Path, n_ctx: int = 8192, n_threads: int = 8):
        from llama_cpp import Llama, LlamaGrammar
        log(f"загрузка модели рук: {model_path.name} (это до минуты)...")
        t0 = time.time()
        self.llm = Llama(
            str(model_path), n_ctx=n_ctx, n_threads=n_threads,
            n_gpu_layers=0, verbose=False,
        )
        self.grammar = LlamaGrammar.from_string(GBNF)
        log(f"модель рук готова за {time.time()-t0:.1f}s, ctx={n_ctx}")

    def next_token(self, history: list[dict]) -> str:
        """history: [{'role': 'user'|'assistant', 'content': ...}] → строго токен."""
        msgs = [{"role": "system", "content": HANDS_SYS}] + history[-14:]
        r = self.llm.create_chat_completion(
            messages=msgs, grammar=self.grammar,
            max_tokens=1024, temperature=0.0,
        )
        return (r["choices"][0]["message"]["content"] or "").strip()


# --------------------------------------------------------------------------------------
# МОЗГ: Arena через живой мост (клиент, не сервер!)
# --------------------------------------------------------------------------------------

BRAIN_SYS = """You are the BRAIN of a two-agent system. HANDS (a tiny local model) executes micro-commands on the user's machine; HANDS can ONLY: create a file with EXACT text, read a file, run a bash command, or say DONE. HANDS cannot think, plan or answer questions.

Your job:
1. Plan the task into an ordered list of micro-commands for HANDS.
2. When asked "NEXT COMMAND", output EXACTLY ONE micro-command, one of:
   - create file <path> with content:
     <exact full text>
   - run command: <bash one-liner>
   - read file: <path>
   - GOAL COMPLETE
3. If HANDS reports an error, analyze it and output the FIXED next micro-command.
4. Never address the user directly. Never explain. Output ONLY the micro-command itself, no headers, no numbering, no prose.

Working dir for relative paths: the user's home directory. OS: Linux Mint 22.
Files must contain their FULL final text in the micro-command (HANDS cannot invent content)."""


@dataclass
class BrainArena:
    base_url: str = BRIDGE_URL
    timeout: float = 700.0
    available: bool | None = None
    model: str = "current"

    def _post(self, path: str, payload: dict, timeout: float) -> dict:
        import requests
        r = requests.post(f"{self.base_url}{path}", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def check(self) -> bool:
        """Жив ли мост (и только живой — никаких запусков своих!)."""
        try:
            import requests
            r = requests.get(f"{self.base_url}/health", timeout=5)
            data = r.json()
            self.available = bool(data.get("ok") and data.get("ready"))
            self.model = data.get("model") or self.model
            log(f"мост жив: ok={data.get('ok')} ready={data.get('ready')} model={data.get('model')}")
            return self.available
        except Exception as e:
            self.available = False
            log(f"мост недоступен ({e}) — режим только-руки / brain-dead", "WARN")
            return False

    def ask_raw(self, message: str) -> str:
        """Сырой ответ большой модели (без tool-loop моста)."""
        resp = self._post("/ask", {"message": message, "raw": True, "timeout": self.timeout}, self.timeout + 60)
        answer = resp.get("answer", "")
        if not resp.get("complete", True):
            answer += "\n[BRIDGE] ответ мог быть оборван (complete:false)"
        return answer

    def first_prompt(self, task: str) -> str:
        system = f"[SYSTEM]\n{BRAIN_SYS}\n[SYSTEM END]\n\n"
        goal = f"USER TASK: {task}\n\nOutput the FIRST micro-command now."
        return system + goal

    def next_prompt(self, plan_note: str, result: str) -> str:
        return (
            f"Progress note: {plan_note}\n"
            f"HANDS result of last micro-command:\n{result}\n\n"
            f"Output the NEXT single micro-command (or GOAL COMPLETE)."
        )


# --------------------------------------------------------------------------------------
# Оркестратор: цикл мозг↔руки
# --------------------------------------------------------------------------------------

@dataclass
class Orchestrator:
    brain: BrainArena
    hands: HandsModel
    work_dir: Path
    max_steps: int = MAX_STEPS
    hands_max_iter: int = HANDS_MAX_ITER
    stall_limit: int = HANDS_STALL_LIMIT

    # -- состояние ----------------------------------------------------------------------
    step: int = 0
    hands_history: list[dict] = field(default_factory=list)   # локальный чат рук
    actions_log: list[str] = field(default_factory=list)      # журнал действий
    plan_md: str = ""
    status_md: str = ""

    def bump(self) -> bool:
        self.step += 1
        if self.step > self.max_steps:
            log(f"бюджет {self.max_steps} шагов исчерпан — останавливаюсь", "WARN")
            return False
        return True

    def record(self, text: str) -> None:
        self.actions_log.append(f"[шаг {self.step}] {text}")
        self.status_md = "\n".join(self.actions_log)
        try:
            (self.work_dir / "TASK_STATUS.md").write_text(
                "# TASK_STATUS (arena_hands)\n\n" + self.status_md + "\n", encoding="utf-8")
        except Exception:
            pass

    # -- руки: внутренний цикл одной микро-команды --------------------------------------
    def run_hands(self, command: str) -> tuple[str, int]:
        """Гоняет локальный tool-loop рук для одной микро-команды архитектора.
        Возвращает ('GOAL_COMPLETE', 0) | ('STALLED', rc) | (result, rc)."""
        self.hands_history.append({"role": "user", "content": f"Command: {command}"})
        last_results = []
        for it in range(1, self.hands_max_iter + 1):
            if not self.bump():
                return ("БЮДЖЕТ ИСЧЕРПАН", 1)
            raw = ""
            for attempt in range(1, MAX_GEMMA_RETRY + 1):
                try:
                    raw = self.hands.next_token(self.hands_history)
                    break
                except Exception as e:
                    log(f"генерация токена упала ({e}), попытка {attempt}/{MAX_GEMMA_RETRY}", "WARN")
                    time.sleep(1)
            else:
                return ("GEN_FAIL: Gemma не отвечает", 1)
            log(f"руки #{it}: {raw[:160].replace(chr(10), ' ⏎ ')}")
            result, rc = execute_token(raw)
            if result == "GOAL_COMPLETE":
                self.hands_history.append({"role": "assistant", "content": raw})
                self.hands_history.append({"role": "user", "content": "[RESULT] architect says: GOAL COMPLETE"})
                self.record("DONE")
                return ("GOAL_COMPLETE", 0)
            self.hands_history.append({"role": "assistant", "content": raw})
            self.hands_history.append({"role": "user", "content": f"[RESULT]\n{result}\n[/RESULT]"})
            last_results.append(result)
            if len(last_results) >= 2 and last_results[-1] == last_results[-2]:
                if len(last_results) >= self.stall_limit and len(set(last_results[-self.stall_limit:])) == 1:
                    log("руки топчутся (одинаковый RESULT) — эскалация к мозгу", "WARN")
                    return ("STALLED", rc)
                # 2 одинаковых подряд — ещё не катастрофа, дадим ещё ход с пинком
                self.hands_history.append({"role": "user",
                                            "content": "[HINT] same result again — try a DIFFERENT command"})
            if rc == 0 and "ERROR" not in result:
                return (result, 0)  # успех микро-команды
        return ("STALLED", 1)

    # -- эскалация -----------------------------------------------------------------------
    def escalate(self, command: str, result: str) -> str:
        """Руки застряли — мозг разбирает ошибку и выдаёт исправленную команду."""
        if not self.brain.available:
            return ""
        q = self.next_prompt("HANDS is stuck. Analyze the error and give ONE fixed micro-command.", result)
        fixed = self.brain.ask_raw(q).strip()
        log(f"мозг-эскалация: {fixed[:160].replace(chr(10), ' ⏎ ')}")
        return fixed

    # -- главный цикл --------------------------------------------------------------------
    def run(self, task: str, brain_dead: bool = False) -> int:
        log(f"ЗАДАЧА: {task}")
        if not brain_dead and self.brain.available:
            log("фаза 1: мозг (Arena) строит план...")
            try:
                plan = self.brain.ask_raw(self.brain.first_prompt(task))
                self.plan_md = plan
                (self.work_dir / "PLAN.md").write_text(
                    "# PLAN (arena_hands, brain=Arena)\n\n" + plan + "\n", encoding="utf-8")
                log(f"план получен ({len(plan)} симв.):\n{plan[:600]}")
            except Exception as e:
                log(f"мозг недоступен ({e}) — переключаюсь на brain-dead (руки сами)", "WARN")
                brain_dead = True
        if brain_dead or not self.brain.available:
            log("режим BRAIN-DEAD: план и команды формулирует Gemma в роли рук", "WARN")
            self.plan_md = f"(brain-dead) задача: {task}"
            (self.work_dir / "PLAN.md").write_text(self.plan_md, encoding="utf-8")

        # первый ход: команда от мозга или (brain-dead) сама задача
        if not brain_dead and self.brain.available:
            command = self._first_command(task)
        else:
            command = task
        note = "start"
        stalls = 0
        while True:
            if not command:
                break
            log(f"--- микро-команда (шаг {self.step}/{self.max_steps}): {command[:200].replace(chr(10), ' ⏎ ')}")
            result, rc = self.run_hands(command)
            if result == "GOAL_COMPLETE":
                log("ГОТОВО: руки доложили DONE")
                self.record(f"GOAL COMPLETE: {command[:120]}")
                return 0
            if result in ("STALLED", "GEN_FAIL", "БЮДЖЕТ ИСЧЕРПАН") or rc != 0:
                stalls += 1
                self.record(f"STALL/ERR на «{command[:80]}»: {result[:200]}")
                if result == "БЮДЖЕТ ИСЧЕРПАН":
                    return 2
                if stalls >= 3:
                    log("3 эскалации подряд без прогресса — сдаюсь", "WARN")
                    return 3
                fixed = self.escalate(command, result)
                if not fixed:
                    log("мозг недоступен для эскалации — сдаюсь", "WARN")
                    return 3
                command = fixed
                # после эскалации — сброс локального топтания рук
                self.hands_history = self.hands_history[-6:]
                continue
            # успех микро-команды → следующая от мозга
            stalls = 0
            self.record(f"OK: {command[:120]} → {result[:200]}")
            note = "last micro-command succeeded"
            nxt = self.brain.ask_raw(self.brain.next_prompt(note, result)) if (not brain_dead and self.brain.available) else None
            if not nxt:
                if not brain_dead and self.brain.available:
                    log("мозг не вернул следующую команду — завершаю", "WARN")
                    return 1
                break
            if _goal_complete(nxt):
                log("мозг сказал GOAL COMPLETE")
                self.record("BRAIN: GOAL COMPLETE")
                return 0
            command = nxt
        log("цикл завершён без GOAL COMPLETE — проверь TASK_STATUS.md на диске", "WARN")
        return 1

    def _first_command(self, task: str) -> str:
        try:
            ans = self.brain.ask_raw(self.brain.first_prompt(task))
        except Exception as e:
            log(f"мозг недоступен ({e}) — brain-dead fallback", "WARN")
            return task
        if _goal_complete(ans):
            return "GOAL COMPLETE"
        return ans.strip()


def _goal_complete(text: str) -> bool:
    t = text.strip().upper()
    return ("GOAL COMPLETE" in t) or ("GOAL: COMPLETE" in t)


# --------------------------------------------------------------------------------------
# SELF-TEST (без Arena): парсеры, инструменты, грамматика, мини-цикл рук
# --------------------------------------------------------------------------------------

def self_test(hands: HandsModel, work_dir: Path) -> int:
    ok = 0
    fail = 0

    def check(name: str, cond: bool, extra: str = ""):
        nonlocal ok, fail
        if cond:
            ok += 1
            log(f"SELF-TEST {name}: OK {extra}")
        else:
            fail += 1
            log(f"SELF-TEST {name}: FAIL {extra}", "ERROR")

    # 1) токен-парсер
    res, rc = execute_token("[EXEC]echo test-ok[/EXEC]")
    check("exec-echo", rc == 0 and "test-ok" in res, f"rc={rc}")
    res, rc = execute_token("[WRITE]/tmp/opencode/ah_test.txt\n---\nпривет мир 123[/WRITE]")
    check("write-cyr", rc == 0 and Path("/tmp/opencode/ah_test.txt").read_text(encoding="utf-8") == "привет мир 123")
    res, rc = execute_token("[READ]/tmp/opencode/ah_test.txt[/READ]")
    check("read-back", rc == 0 and "привет" in res)
    res, rc = execute_token("[EXEC]python3 -c \"print(5+3)\"[/EXEC]")
    check("exec-python", rc == 0 and "8" in res)
    res, rc = execute_token("[EXEC]rm -rf /[/EXEC]")
    check("deny-rm", rc != 0 and "deny" in res.lower())
    res, rc = execute_token("[WRITE]/tmp/opencode/bad.py\n---\ndef f(:\n    pass[/WRITE]")
    check("py-guard", rc != 0 and "битый" in res)
    res, rc = execute_token("просто текст без токена")
    check("no-token-retry", rc == -1 and "NEED_RETRY" in res)
    check("goal-complete", execute_token("[DONE]")[0] == "GOAL_COMPLETE")

    # 2) fuzzy-путь
    d = work_dir / "hands_fuzzy_test"
    d.mkdir(exist_ok=True)
    (d / "01. test - folder (x)").mkdir(exist_ok=True)
    p = _resolve_fuzzy(d / "01. test folder x")
    check("fuzzy-path", str(p).endswith("01. test - folder (x)"), str(p))

    # 3) мини-цикл рук: Gemma + грамматика (реальная генерация)
    if hands is not None:
        hist = [
            {"role": "user", "content": "Command: create file /tmp/opencode/ah_gemma.txt with content Gemma ruki ok"},
        ]
        raw = hands.next_token(hist)
        log(f"SELF-TEST gemma-gen: {raw!r}")
        check("gemma-grammar", raw.startswith(("[WRITE]", "[EXEC]", "[READ]", "[DONE]")), raw[:80])
        res, rc = execute_token(raw)
        check("gemma-exec", rc == 0, res[:120])
        hist += [{"role": "assistant", "content": raw},
                 {"role": "user", "content": f"[RESULT]\n{res}\n[/RESULT]\nCommand: run command that prints the contents of /tmp/opencode/ah_gemma.txt"}]
        raw2 = hands.next_token(hist)
        check("gemma-second", bool(raw2), raw2[:80])
        res2, rc2 = execute_token(raw2)
        check("gemma-loop", rc2 == 0 and ("Gemma ruki ok" in res2 or "Gemma" in res2), res2[:120])

    log(f"SELF-TEST итого: {ok} OK, {fail} FAIL")
    return 1 if fail else 0


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="arena_hands: Arena-мозг + Gemma-руки")
    ap.add_argument("task", nargs="*", help="задача (если не задана — интерактивный ввод)")
    ap.add_argument("--model", default=str(MODEL_PATH), help="GGUF модели рук")
    ap.add_argument("--bridge", default=BRIDGE_URL, help="URL моста LMArena_Bridge")
    ap.add_argument("--work-dir", default=str(WORK_DIR_DEFAULT), help="рабочая директория")
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS, help=f"бюджет шагов (дефолт {MAX_STEPS})")
    ag = ap.add_mutually_exclusive_group()
    ag.add_argument("--self-test", action="store_true", help="прогон тестов без Arena")
    ag.add_argument("--brain-dead", action="model_converter_path" if False else "store_true",
                    help="Arena недоступна: всё делает Gemma")
    ap.add_argument("--no-model", action="store_true", help="self-test без загрузки Gemma (только инструменты)")
    return ap.parse_args()


def main() -> None:
    global SYS_LOG, WORK_DIR, EXEC_TIMEOUT
    ap = parse_args()
    WORK_DIR = Path(ap.work_dir).expanduser().resolve()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    SYS_LOG = open(run_dir / "run.log", "a", encoding="utf-8")

    log("=" * 80)
    log(f"ARENA HANDS — запуск {datetime.now():%Y-%m-%d %H:%M:%S}")
    log(f"модель рук: {ap.model}")
    log(f"мост: {ap.bridge} | work_dir: {WORK_DIR} | бюджет: {ap.max_steps} шагов")
    log(f"лог каталог: {run_dir}")

    hands = None
    if not ap.no_model:
        if not Path(ap.model).is_file():
            log(f"модель не найдена: {ap.model} — только self-test инструментов", "ERROR")
            sys.exit(2)
        hands = HandsModel(Path(ap.model))
    else:
        log("--no-model: Gemma не загружается (только инструменты/парсеры)", "WARN")

    if ap.self_test:
        sys.exit(self_test(hands, WORK_DIR))

    task = " ".join(ap.task).strip()
    if not task:
        log("интерактивный ввод задачи (пустая строка — выход):")
        task = input("> ").strip()
        if not task:
            sys.exit(0)
    log(f"задача: {task}")

    brain = BrainArena(base_url=ap.bridge)
    brain.check()

    orch = Orchestrator(brain=brain, hands=hands, work_dir=WORK_DIR, max_steps=ap.max_steps)
    rc = orch.run(task, brain_dead=ap.brain_dead)
    log(f"ИТОГ rc={rc}. Статус: {WORK_DIR / 'TASK_STATUS.md'}")
    sys.exit(rc)


if __name__ == "__main__":
    main()

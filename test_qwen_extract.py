#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Регрессионная проверка селекторов ответа Qwen.

Читает zai_last_answer.html (сохраняется агентом после каждого финального
ответа) и проверяет, что экстрактор по-прежнему найдёт полный текст ответа.
Запуск: python3 test_qwen_extract.py
"""
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
DUMP = HERE / "zai_last_answer.html"

REQUIRED_SELECTORS = (
    "response-message-content",
    "qwen-markdown-text-node",
    "qwen-markdown-paragraph",
)


def main() -> int:
    if not DUMP.exists():
        print(f"Нет дампа {DUMP} — сначала задайте агенту вопрос")
        return 2
    html = DUMP.read_text(encoding="utf-8", errors="replace")
    problems = []
    for cls in REQUIRED_SELECTORS:
        if cls not in html:
            problems.append(f"класс {cls!r} не найден в DOM ответа")
    text_nodes = re.findall(
        r'<span[^>]*class="[^"]*qwen-markdown-text-node[^"]*"[^>]*>(.*?)</span>',
        html, flags=re.S,
    )
    text = " ".join(re.sub(r"<[^>]+>", "", t) for t in text_nodes).strip()
    if not text:
        problems.append("текст ответа не извлечён")
    if "[EXEC]" in text and "[/EXEC]" not in text:
        problems.append("обнаружен оборванный [EXEC]-блок")
    if problems:
        print("FAIL:")
        for p in problems:
            print(" -", p)
        return 1
    print(f"OK: ответ извлечён ({len(text)} символов): {text[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
fix_encoding.py — чинит UTF-8 → cp1251 mojibake в тексте.

Берёт путь к файлу из буфера обмена (xclip) или из аргумента командной строки.
Для каждой строки:
  • чисто ASCII            → не трогаем
  • «РїРѕР»СѓС‡…» (UTF-8 байты, прочитанные как cp1251)
                             → reverse: encode('cp1251') → decode('utf-8')
  • нормальная кириллица   → её cp1251-байты не валидный UTF-8 → не трогаем
Перед перезаписью создаёт .bak-копию оригинала.

Использование:
  python3 fix_encoding.py          # путь из буфера обмена (xclip)
  python3 fix_encoding.py ФАЙЛ    # путь как аргумент
"""

import sys
import shutil
import subprocess
from pathlib import Path


def get_clipboard() -> str:
    try:
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except FileNotFoundError:
        print("Ошибка: xclip не установлен. Установите: sudo apt install xclip")
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("Не удалось прочитать буфер обмена.")
        sys.exit(1)


def reverse_line(line: str):
    """
    Возвращает (исправленная_строка, была_ли_испорчена).
    Если строка нормальная (чисто ASCII или настоящая кириллица) — оставляем как есть.
    """
    if all(ord(c) < 128 for c in line):
        return line, False          # ASCII — не трогать

    try:
        orig_bytes = line.encode("cp1251")
    except UnicodeEncodeError:
        # Есть символы, которых нет в cp1251 → строка уже в нормальной кириллице
        return line, False

    try:
        fixed = orig_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # cp1251-байты нормальной кириллицы — не валидный UTF-8 → не трогаем
        return line, False

    # Убедимся, что в результате реально есть кириллица (иначе зря меняли)
    if not any("\u0400" <= c <= "\u04ff" for c in fixed):
        return line, False

    return fixed, True


def strip_bom_artifacts(text: str) -> str:
    """Убирает BOM и его cp1251-модзибек («п»ї») в начале текста."""
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    while text.startswith("п»ї"):
        text = text[3:]
    return text


def main():
    if len(sys.argv) > 1:
        raw_path = sys.argv[1].strip().strip("'\"")
    else:
        raw_path = get_clipboard()

    if not raw_path:
        print("Буфер обмена пуст и аргумент не задан.")
        sys.exit(1)

    file_path = Path(raw_path).expanduser()

    if not file_path.exists():
        print(f"Файл не найден: {file_path}")
        sys.exit(1)
    if not file_path.is_file():
        print(f"Это не файл: {file_path}")
        sys.exit(1)

    print(f"Файл: {file_path}")

    raw = file_path.read_bytes()

    # Определяем, есть ли BOM в начале
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    if has_bom:
        raw = raw[3:]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        print("Файл не является корректным UTF-8 — скрипт не применит.")
        sys.exit(1)

    text = strip_bom_artifacts(text)

    lines = text.split("\n")
    fixed_lines = []
    n_fixed = 0
    for line in lines:
        fixed, was_mojibake = reverse_line(line)
        if was_mojibake:
            n_fixed += 1
        fixed_lines.append(fixed)

    if n_fixed == 0:
        print("Испорченных строк не обнаружено — файл не изменён.")
        sys.exit(0)

    fixed_text = "\n".join(fixed_lines)

    # Бэкап
    bak_path = file_path.with_suffix(file_path.suffix + ".bak")
    shutil.copy2(file_path, bak_path)

    # Записываем обратно (сохраняем BOM, если он был)
    out = b"\xef\xbb\xbf" + fixed_text.encode("utf-8") if has_bom \
          else fixed_text.encode("utf-8")
    file_path.write_bytes(out)

    print(f"Исправлено строк: {n_fixed} из {len(lines)}")
    print(f"Резервная копия: {bak_path.name}")
    print(f"Исправленный файл: {file_path.name}")


if __name__ == "__main__":
    main()

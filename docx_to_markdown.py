#!/usr/bin/env python3
"""
docx_to_markdown.py
~~~~~~~~~~~~~~~~~~~
Скрипт для массовой конвертации .doc / .docx файлов в Markdown (.md).

Как пользоваться:
    python3 docx_to_markdown.py               # текущая папка
    python3 docx_to_markdown.py /путь/к/папке  # указанная папка

Что делает:
    1. Сканирует папку на наличие .doc и .docx файлов (включая вложенные папки)
    2. Создаёт подпапку "markdown_output"
    3. Конвертирует каждый найденный файл в .md с помощью mammoth + python-docx
    4. Сохраняет структуру папок в выходной директории
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ─── Настройки ───────────────────────────────────────────────────────────────
OUTPUT_FOLDER_NAME = "markdown_output"
SUPPORTED_EXTENSIONS = (".doc", ".docx")


def find_doc_files(source_dir: Path) -> list[tuple[Path, Path]]:
    """Найти все .doc/.docx файлы, вернуть список (абсолютный путь, относительный путь)."""
    results = []
    for root, dirs, files in os.walk(source_dir):
        for fname in sorted(files):
            if fname.lower().endswith(SUPPORTED_EXTENSIONS):
                abs_path = Path(root) / fname
                rel_path = abs_path.relative_to(source_dir)
                results.append((abs_path, rel_path))
    return results


def convert_with_mammoth(docx_path: Path, md_path: Path) -> bool:
    """Конвертировать .docx в .md с помощью библиотеки mammoth (лучшее качество)."""
    import mammoth

    try:
        with open(docx_path, "rb") as f:
            result = mammoth.convert_to_markdown(f)
        md_path.write_text(result.value, encoding="utf-8")

        if result.messages:
            print(f"      ⚠ Предупреждения mammoth: {len(result.messages)}")
            for msg in result.messages[:5]:
                print(f"        - {msg}")
        return True
    except Exception as e:
        print(f"      ✗ Ошибка mammoth: {e}")
        return False


def convert_with_pandoc(docx_path: Path, md_path: Path) -> bool:
    """Резервная конвертация через pandoc."""
    try:
        subprocess.run(
            [
                "pandoc",
                "-f", "docx",
                "-t", "markdown",
                "-s",                       # standalone
                "--wrap=none",               # без переноса строк
                str(docx_path),
                "-o", str(md_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except Exception as e:
        print(f"      ✗ Ошибка pandoc: {e}")
        return False


def convert_doc_to_docx(doc_path: Path) -> Path | None:
    """Попробовать конвертировать старый .doc в .docx через libreoffice."""
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "docx", "--outdir",
             str(doc_path.parent), str(doc_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        docx_path = doc_path.with_suffix(".docx")
        if docx_path.exists():
            return docx_path
    except Exception as e:
        print(f"      ✗ Не удалось конвертировать .doc → .docx: {e}")
    return None


def convert_file(docx_path: Path, md_path: Path, is_old_doc: bool = False) -> bool:
    """Конвертировать один файл с fallback-цепочкой."""
    md_path.parent.mkdir(parents=True, exist_ok=True)

    # Шаг 1: mammoth (лучшее качество для .docx)
    if not is_old_doc:
        if convert_with_mammoth(docx_path, md_path):
            return True

    # Шаг 2: pandoc
    if convert_with_pandoc(docx_path, md_path):
        return True

    # Шаг 3: для старых .doc — попытка конвертировать в .docx, потом снова
    if is_old_doc:
        converted = convert_doc_to_docx(docx_path)
        if converted:
            if convert_with_mammoth(converted, md_path):
                converted.unlink(missing_ok=True)  # удалить временный .docx
                return True
            if convert_with_pandoc(converted, md_path):
                converted.unlink(missing_ok=True)
                return True

    return False


def main():
    # ─── Определяем исходную папку ────────────────────────────────────────
    if len(sys.argv) > 1:
        source_dir = Path(sys.argv[1]).resolve()
    else:
        source_dir = Path.cwd()

    if not source_dir.is_dir():
        print(f"❌ Папка не найдена: {source_dir}")
        sys.exit(1)

    print("=" * 60)
    print("  📄 Конвертация DOC/DOCX → MARKDOWN")
    print("=" * 60)
    print(f"  📂 Исходная папка: {source_dir}")
    print()

    # ─── Находим файлы ────────────────────────────────────────────────────
    files = find_doc_files(source_dir)

    if not files:
        print("  ⚠ Файлы .doc / .docx не найдены.")
        sys.exit(0)

    print(f"  🔍 Найдено файлов: {len(files)}")
    print()

    # ─── Создаём выходную папку ───────────────────────────────────────────
    output_dir = source_dir / OUTPUT_FOLDER_NAME
    output_dir.mkdir(parents=True, exist_ok=True)

    # ─── Конвертируем ────────────────────────────────────────────────────
    success_count = 0
    fail_count = 0

    for abs_path, rel_path in files:
        is_old_doc = abs_path.suffix.lower() == ".doc"
        md_rel_path = rel_path.with_suffix(".md")
        md_abs_path = output_dir / md_rel_path

        display_name = rel_path if len(str(rel_path)) < 45 else str(rel_path)[-45:]
        print(f"  📝 {display_name}")

        ok = convert_file(abs_path, md_abs_path, is_old_doc=is_old_doc)

        if ok:
            size = md_abs_path.stat().st_size
            print(f"      ✅ Готово ({size:,} байт)")
            success_count += 1
        else:
            print(f"      ❌ Не удалось конвертировать")
            fail_count += 1

    # ─── Итог ─────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  ✅ Успешно:  {success_count}")
    print(f"  ❌ Ошибки:    {fail_count}")
    print(f"  📁 Результат: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()

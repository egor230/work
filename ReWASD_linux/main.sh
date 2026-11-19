#!/bin/bash
# ReWASD Linux — запуск через основной скрипт
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python"
cd "$DIR" || exit 1
export DISPLAY="${DISPLAY:-:0}"
export PYTHONDONTWRITEBYTECODE=1  # чтобы не появлялась папка __pycache__
exec "$VENV" "$DIR/main.py" "$@"

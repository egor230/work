#!/bin/bash
#gnome-terminal -- bash -c '

set -e

WORK_DIR="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work"
VENV_DIR="$WORK_DIR/.venv"
REQ_FILE="$WORK_DIR/requirements.txt"
REQ_CLEAN="$WORK_DIR/requirements_clean.txt"
HF_CACHE="$WORK_DIR/cache"

echo "==== Переходим в рабочую директорию ===="
cd "$WORK_DIR"
echo "Текущая директория: $(pwd)"

echo ""
echo "==== Шаг 1 — сохраняем список пакетов из старого .venv ===="

if [ -d "$VENV_DIR" ]; then
    echo "Активируем окружение и сохраняем список пакетов..."
    source "$VENV_DIR/bin/activate"
    pip freeze > "$REQ_FILE"
    deactivate
else
    echo "❗ .venv не найден — создадим пустой requirements.txt"
    echo -n "" > "$REQ_FILE"
fi

echo ""
echo "==== Шаг 2 — удаляем старый .venv ===="

if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    echo ".venv удалён."
else
    echo ".venv и так отсутствует."
fi

echo ""
echo "==== Шаг 3 — очистка HuggingFace cache ===="

if [ -d "$HF_CACHE" ]; then
    rm -rf "$HF_CACHE"
    echo "Кэш очищен."
else
    echo "Кэш уже отсутствует."
fi

echo ""
echo "==== Шаг 4 — создаём новое окружение через uv ===="
uv venv

echo ""
echo "==== Шаг 5 — создаём очищенный список пакетов ===="
echo "Проблемные пакеты будут автоматически пропущены."

echo -n "" > "$REQ_CLEAN"

while IFS= read -r pkg; do
    if [ -z "$pkg" ]; then
        continue
    fi

    # Быстрая проверка — доступен ли пакет в uv/pip
    if uv pip install --dry-run "$pkg" >/dev/null 2>&1; then
        echo "$pkg" >> "$REQ_CLEAN"
    else
        echo "⚠ Пропущен проблемный пакет: $pkg"
    fi
done < "$REQ_FILE"

echo ""
echo "==== Шаг 6 — устанавливаем очищенные старые пакеты ===="

if [ -s "$REQ_CLEAN" ]; then
    echo "Устанавливаем исправленный список..."
    uv pip install -r "$REQ_CLEAN"
else
    echo "requirements_clean.txt пуст — пропускаем."
fi

echo ""
echo "==== Шаг 7 — устанавливаем зависимости для GigaAM ===="
uv pip install "torch>=2.6" --index-url https://download.pytorch.org/whl/cpu
uv pip install "torchaudio>=2.6" --index-url https://download.pytorch.org/whl/cpu
uv pip install safetensors transformers accelerate

echo ""
echo "==========================================================="
echo " ✔ Готово! Окружение пересоздано, проблемные пакеты пропущены."
echo "==========================================================="

#exec bash' 


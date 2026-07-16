#!/bin/bash

# Если скрипт запущен без аргумента "run" – открываем новое окно терминала
if [ "$1" != "run" ]; then
    gnome-terminal -- bash -c "$0 run; exec bash"
    exit 0
fi

# ===== Основная логика (внутри нового терминала) =====
#set -euo pipefail

OMNI_PORT=20128
OMNI_URL="http://localhost:$OMNI_PORT/v1/chat/completions"
MODELS_URL="http://localhost:$OMNI_PORT/v1/models"
REPORT_FILE="рабочие модели.md"
TIMEOUT=5

# ---- Определяем, запущен ли OmniRoute ----
OMNI_STARTED_BY_US=false
OMNI_PID=""

function is_omniroute_running() {
    pgrep -f "omniroute.*--port $OMNI_PORT" >/dev/null 2>&1 && return 0
    ss -ltn 2>/dev/null | grep -q ":$OMNI_PORT " && return 0
    return 1
}

function start_omniroute() {
    echo "🔧 OmniRoute не запущен. Запускаем..."
    if ! command -v omniroute >/dev/null 2>&1; then
        echo "❌ Команда omniroute не найдена. Установите её или запустите вручную."
        exit 1
    fi
    omniroute serve --no-open --port $OMNI_PORT > "$TMP_DIR/omniroute.log" 2>&1 &
    OMNI_PID=$!
    OMNI_STARTED_BY_US=true
    echo "   PID: $OMNI_PID"
    for i in {1..30}; do
        if ss -ltn 2>/dev/null | grep -q ":$OMNI_PORT "; then
            echo "✅ OmniRoute готов (порт $OMNI_PORT слушает)"
            return 0
        fi
        sleep 1
    done
    echo "❌ OmniRoute не запустился за 30 секунд. Лог: $TMP_DIR/omniroute.log"
    exit 1
}

function kill_omniroute_if_we_started() {
    if [ "$OMNI_STARTED_BY_US" = true ] && [ -n "$OMNI_PID" ]; then
        echo "🛑 Останавливаем OmniRoute (PID $OMNI_PID)..."
        kill -TERM "$OMNI_PID" 2>/dev/null || true
        sleep 2
        kill -9 "$OMNI_PID" 2>/dev/null || true
    fi
}

# ---- Основная логика ----
if ! is_omniroute_running; then
    start_omniroute
else
    echo "✅ OmniRoute уже запущен."
fi

# Проверяем jq
if ! command -v jq >/dev/null 2>&1; then
    echo "❌ Утилита jq не установлена. Установите: sudo apt install jq"
    exit 1
fi

# Получаем список моделей
echo "📡 Запрашиваем список моделей..."
MODELS_JSON=$(curl -s "$MODELS_URL" || echo "")
if [ -z "$MODELS_JSON" ]; then
    echo "❌ Не удалось получить список моделей."
    exit 1
fi

# Извлекаем ID моделей
mapfile -t MODEL_IDS < <(echo "$MODELS_JSON" | jq -r '.data[].id' 2>/dev/null)
if [ ${#MODEL_IDS[@]} -eq 0 ]; then
    echo "❌ Список моделей пуст."
    exit 1
fi

TOTAL=${#MODEL_IDS[@]}
echo "🔍 Найдено $TOTAL моделей. Начинаем проверку..."

WORKING_FILE="$TMP_DIR/working.txt"
FAILED_FILE="$TMP_DIR/failed.txt"
DETAILS_FILE="$TMP_DIR/details.json"
> "$WORKING_FILE"
> "$FAILED_FILE"
echo '{}' > "$DETAILS_FILE"
# Параметры
TIMEOUT=15
TARGET_WORKING=5

# Файлы для сбора всех рабочих (с контекстом)
ALL_WORKING_FILE="$TMP_DIR/all_working.txt"
> "$ALL_WORKING_FILE"

COUNT=0
for MODEL in "${MODEL_IDS[@]}"; do
    COUNT=$((COUNT+1))
    echo -n "[$COUNT/$TOTAL] Проверка $MODEL ... "

    # Получаем детали модели
    DETAILS=$(echo "$MODELS_JSON" | jq -r ".data[] | select(.id==\"$MODEL\")" 2>/dev/null)
    CONTEXT_LENGTH=$(echo "$DETAILS" | jq -r '.context_length // .max_input_length // 0' 2>/dev/null)
    MAX_TOKENS=$(echo "$DETAILS" | jq -r '.max_tokens // 0' 2>/dev/null)
    CAPABILITIES=$(echo "$DETAILS" | jq -r '.capabilities // {}' 2>/dev/null)
    OWNED_BY=$(echo "$DETAILS" | jq -r '.owned_by // ""' 2>/dev/null)

    # Тестовый запрос
    RESP=$(curl -s -X POST "$OMNI_URL" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":10,\"stream\":false}" \
        --max-time $TIMEOUT 2>/dev/null || echo "ERROR")

    if [ "$RESP" == "ERROR" ]; then
        echo "⚠️  таймаут/ошибка сети"
        echo "$MODEL|таймаут" >> "$FAILED_FILE"
        continue
    fi

    # Проверяем на ошибку SSE
    if echo "$RESP" | grep -q "Stream produced no non-ping SSE event"; then
        echo "❌ ошибка SSE (стриминг не завершён)"
        echo "$MODEL|ошибка SSE" >> "$FAILED_FILE"
        continue
    fi

    CONTENT=$(echo "$RESP" | jq -r '.choices[0].message.content // empty' 2>/dev/null)
    ERROR_MSG=$(echo "$RESP" | jq -r '.error.message // empty' 2>/dev/null)

    if [ -n "$ERROR_MSG" ]; then
        echo "❌ ошибка: $ERROR_MSG"
        echo "$MODEL|$ERROR_MSG" >> "$FAILED_FILE"
        continue
    fi

    if [ -n "$CONTENT" ] && [ "$CONTENT" != "null" ]; then
        echo "✅ работает (ответ: ${CONTENT:0:30}...)"
        # Записываем модель и её контекст (для сортировки)
        echo "$CONTEXT_LENGTH|$MODEL|$MAX_TOKENS|$OWNED_BY|$CAPABILITIES" >> "$ALL_WORKING_FILE"
        # Сохраняем детали в DETAILS_FILE (как раньше)
        MODEL_JSON=$(jq -n \
            --arg name "$MODEL" \
            --argjson context_length "$CONTEXT_LENGTH" \
            --argjson max_tokens "$MAX_TOKENS" \
            --argjson capabilities "$CAPABILITIES" \
            --arg owned_by "$OWNED_BY" \
            '{name: $name, context_length: $context_length, max_tokens: $max_tokens, capabilities: $capabilities, owned_by: $owned_by}')
        jq --arg model "$MODEL" --argjson m "$MODEL_JSON" '.[$model] = $m' "$DETAILS_FILE" > "$TMP_DIR/details_tmp.json" && mv "$TMP_DIR/details_tmp.json" "$DETAILS_FILE"
    else
        echo "❌ пустой ответ или null"
        echo "$MODEL|пустой ответ" >> "$FAILED_FILE"
    fi
done

echo ""
echo "✅ Проверка завершена."

# ---- Выбираем топ-5 моделей с наибольшим context_length ----
if [ -s "$ALL_WORKING_FILE" ]; then
    # Сортируем по первому полю (число, убывание) и берём первые TARGET_WORKING строк
    sort -t'|' -k1 -rn "$ALL_WORKING_FILE" | head -n "$TARGET_WORKING" > "$TMP_DIR/top_working.txt"
    TOP_COUNT=$(wc -l < "$TMP_DIR/top_working.txt" 2>/dev/null | tr -d ' ')
else
    TOP_COUNT=0
fi

echo "📊 Найдено рабочих моделей: $(wc -l < "$ALL_WORKING_FILE" 2>/dev/null | tr -d ' ')"
echo "📌 Выбрано $TOP_COUNT моделей с самым большим контекстным окном."

# ---- Формируем список имён для opencode.jsonc ----
if [ "$TOP_COUNT" -gt 0 ]; then
    # Извлекаем только имена моделей (второе поле) из top_working.txt
    cut -d'|' -f2 "$TMP_DIR/top_working.txt" > "$TMP_DIR/top_names.txt"
    NEW_MODELS_JSON=$(jq -R -s 'split("\n") | map(select(length>0)) | map({ (.): { name: . } }) | add' "$TMP_DIR/top_names.txt" 2>/dev/null)

    echo "📝 Обновляем $OPECODE_FILE ..."
    if [ -z "$NEW_MODELS_JSON" ] || [ "$NEW_MODELS_JSON" == "null" ]; then
        echo "⚠️  Не удалось сформировать JSON для моделей, пропускаем обновление."
    else
        if [ ! -f "$OPECODE_FILE" ]; then
            mkdir -p "$(dirname "$OPECODE_FILE")"
            echo '{"provider":{"ommirorouter":{}}}' > "$OPECODE_FILE"
        fi

        if jq --argjson newmodels "$NEW_MODELS_JSON" '.provider.ommirorouter.models = $newmodels' "$OPECODE_FILE" > "$TMP_DIR/opencode_new.json" 2>/dev/null; then
            mv "$TMP_DIR/opencode_new.json" "$OPECODE_FILE"
            echo "✅ Секция models обновлена в $OPECODE_FILE (топ-$TOP_COUNT моделей)"
        else
            echo "❌ Ошибка при обновлении JSON. Проверьте синтаксис $OPECODE_FILE."
        fi
    fi
else
    echo "⚠️  Нет работающих моделей – opencode.jsonc не изменён."
fi

# ---- Генерация Markdown-отчёта ----
if [ "$WORKING_COUNT" -eq 0 ]; then
    echo "⚠️  Нет работающих моделей. Отчёт не создан."
    exit 0
fi

cat > "$REPORT_FILE" <<EOF
# Рабочие модели OmniRoute

Дата проверки: $(date '+%Y-%m-%d %H:%M:%S %Z')

Всего проверено: **$TOTAL** моделей.  
Работающих: **$WORKING_COUNT**.

---

## Список рабочих моделей

| Модель |
|--------|
EOF

while IFS= read -r MODEL; do
    echo "| \`$MODEL\` |"
done < "$WORKING_FILE" >> "$REPORT_FILE"

FAILED_COUNT=$(wc -l < "$FAILED_FILE" 2>/dev/null | tr -d ' ')
if [ "$FAILED_COUNT" -gt 0 ]; then
    cat >> "$REPORT_FILE" <<EOF

---

## Модели, которые не ответили или вернули ошибку

| Модель | Причина |
|--------|---------|
EOF
    while IFS='|' read -r MODEL REASON; do
        echo "| \`$MODEL\` | $REASON |"
    done < "$FAILED_FILE" >> "$REPORT_FILE"
fi

echo ""
echo "📄 Отчёт сохранён в файл: $REPORT_FILE"
cat "$REPORT_FILE"

echo "✅ Скрипт завершён. Окно закроется через несколько секунд..."
sleep 5

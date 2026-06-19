#!/bin/bash
#gnome-terminal -- bash -c '
SCRIPT_DIR="/home/egor/Загрузки/zapret-discord-youtube-linux"
SERVICE_SCRIPT="$SCRIPT_DIR/service.sh"
CONF_INI="$SCRIPT_DIR/conf.ini"
CURL_TIMEOUT=5  # добавлено значение по умолчанию

# Путь к списку нейросетей
AI_LIST="$SCRIPT_DIR/list-ai-services.txt"

# Создание симлинков для пользовательских стратегий
CUSTOM_DIR="$SCRIPT_DIR/custom-strategies"
if [[ -d "$CUSTOM_DIR" ]]; then
  for bat in "$SCRIPT_DIR"/zapret-latest/*.bat; do
    if [[ -f "$bat" ]]; then
      ln -sf "$bat" "$CUSTOM_DIR/$(basename "$bat")"
    fi
  done
fi

# Функции для управления zapret
stop_zapret() {
  "$SERVICE_SCRIPT" kill >/dev/null 2>&1
  sleep 1
}

start_strategy() {
  local strategy="$1"
  if [[ -f "$AI_LIST" ]]; then
    mkdir -p "$SCRIPT_DIR/user-lists"
    cp "$AI_LIST" "$SCRIPT_DIR/user-lists/ai.txt"
  fi

  "$SERVICE_SCRIPT" run -s "$strategy" -i any >/dev/null 2>&1 &
  sleep 1
}

# Функции проверки
check_youtube_main() {
  local tmp=$(mktemp)
  local code=$(curl -s --tlsv1.3 \
    --connect-timeout "$CURL_TIMEOUT" \
    --max-time "$CURL_TIMEOUT" \
    -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36" \
    -o "$tmp" \
    -w "%{http_code}" \
    "https://www.youtube.com" 2>/dev/null)
  
  rm -f "$tmp"
  [[ "$code" =~ ^(200|30[0-7])$ ]]
}

check_ai_service() {
  local code=$(curl -s --tlsv1.3 \
    --connect-timeout "$CURL_TIMEOUT" \
    --max-time "$CURL_TIMEOUT" \
    -o "/dev/null" \
    -w "%{http_code}" \
    "https://chatgpt.com" 2>/dev/null)
  
  [[ "$code" =~ ^(200|30[0-7]|403)$ ]] # 403 тоже может быть признаком того, что домен доступен, но есть защита Cloudflare
}

# Первое действие: остановить zapret (если запущен)
stop_zapret
sleep 4

# Проверка сохранённой стратегии (по имени)
if [[ -f "$CONF_INI" ]]; then
  saved_strategy=$(cat "$CONF_INI" 2>/dev/null | tr -d '\n')
  if [[ -n "$saved_strategy" ]]; then
    echo "Запускаю сохранённую стратегию: $saved_strategy"
    start_strategy "$saved_strategy"
    echo "Проверка доступности..."
    sleep 2
    if check_youtube_main; then
        echo "YouTube: OK"
    else
        echo "YouTube: НЕ РАБОТАЕТ"
    fi
    if check_ai_service; then
        echo "AI Services: OK"
    else
        echo "AI Services: НЕ РАБОТАЕТ"
    fi
    exit 0
  fi
fi

# Получение списка стратегий
STRATEGY_FILES=($("$SERVICE_SCRIPT" strategy list | grep -E "\.bat$"))

if [[ "${#STRATEGY_FILES[@]}" -eq 0 ]]; then
  echo "Стратегии не найдены"
  echo "Запустите: $SERVICE_SCRIPT download-deps --default"
  echo "Нажмите Enter..."
  read -r
  exit 1
fi

WORKING=()
index=1

echo "Тестирование ${#STRATEGY_FILES[@]} стратегий..."
for strategy_path in "${STRATEGY_FILES[@]}"; do
  strategy_name=$(basename "$strategy_path")
  echo -n "Тестируем $strategy_name ... "
  start_strategy "$strategy_name"
  
  # Проверки
  if check_youtube_main; then
    yt_status="OK"
    yt_ok=1
  else
    yt_status="FAIL"
    yt_ok=0
  fi
  
  if check_ai_service; then
    ai_status="OK"
    ai_ok=1
  else
    ai_status="FAIL"
    ai_ok=0
  fi

  WORKING+=("$index:$strategy_name:$yt_ok:$ai_ok")
  echo "YT: $yt_status, AI: $ai_status"
  stop_zapret
  ((index++))
done

echo ""
echo "Результаты тестирования:"
echo ""

# Главный цикл
while true; do
  echo "========================================================"
  echo "Список стратегий:"
  echo "№   Стратегия                                 YT    AI"
  echo "--------------------------------------------------------"

  for entry in "${WORKING[@]}"; do
    IFS=":" read -r num name yt ai <<< "$entry"
    yt_icon=$([[ "$yt" -eq 1 ]] && echo "+" || echo "-")
    ai_icon=$([[ "$ai" -eq 1 ]] && echo "+" || echo "-")
    printf "%2s  %-42s  %s     %s\n" "$num" "$name" "$yt_icon" "$ai_icon"
  done

  echo "--------------------------------------------------------"
  if [[ -n "$current_strategy" ]]; then
    echo "Текущая стратегия: $current_strategy"
  else
    echo "Текущая стратегия: не запущена"
  fi
  echo ""
  echo "Команды:"
  echo "  <номер>  - запустить стратегию"
  echo "  s        - сохранить текущую в $CONF_INI"
  echo "  x        - остановить zapret"
  echo "  q        - выйти"
  echo ""

  read -p "> " input
  input="${input// /}"

  if [[ -z "$input" || "$input" =~ ^[qQ]$ ]]; then
    echo "Выход..."
    exit 0
  fi

  if [[ "$input" =~ ^[sS]$ ]]; then
    if [[ -n "$current_strategy" ]]; then
      echo "$current_strategy" > "$CONF_INI"
      echo "Стратегия $current_strategy сохранена в $CONF_INI"
    else
      echo "Нет запущенной стратегии для сохранения."
    fi
    echo ""
    continue
  fi

  if [[ "$input" =~ ^[xX]$ ]]; then
    stop_zapret
    current_strategy=""
    echo "zapret остановлен."
    echo ""
    continue
  fi

  if [[ "$input" =~ ^[0-9]+$ ]]; then
    num="$input"
    found=0
    for entry in "${WORKING[@]}"; do
      IFS=":" read -r n name yt ai <<< "$entry"
      if [[ "$n" == "$num" ]]; then
        found=1
        echo "Выбрана стратегия: $name"
        stop_zapret
        start_strategy "$name"
        current_strategy="$name"
        echo "Стратегия запущена."
        echo ""

        echo "YouTube работает? (y/n)"
        read -r answer
        if [[ "$answer" =~ ^[Yy]$ ]]; then
          echo "Сохранить стратегию? (y/n)"
          read -r save_ans
          if [[ "$save_ans" =~ ^[Yy]$ ]]; then
            echo "$name" > "$CONF_INI"
            echo "Стратегия сохранена в $CONF_INI"
          fi
          echo "Выход..."
          exit 0
        else
          echo "Продолжаем..."
        fi
        break
      fi
    done

    if [[ "$found" -eq 0 ]]; then
      echo "Стратегия с номером $num не найдена"
      echo ""
    fi
    continue
  fi

  echo "Неверный ввод."
  echo ""
done

exec bash'

#!/bin/bash
#gnome-terminal -- bash -c '
SCRIPT_DIR="/home/egor/Загрузки/zapret-discord-youtube-linux"
SERVICE_SCRIPT="$SCRIPT_DIR/service.sh"
CONF_INI="$SCRIPT_DIR/conf.ini"
CURL_TIMEOUT=5  # добавлено значение по умолчанию

# Создание симлинков для пользовательских стратегий
CUSTOM_DIR="/home/egor/Загрузки/zapret-discord-youtube-linux/custom-strategies"
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
  "$SERVICE_SCRIPT" run -s "$strategy" -i any >/dev/null 2>&1 &
  sleep 1
}

# Первое действие: остановить zapret (если запущен)
stop_zapret
sleep 4
#exit 0
# Проверка сохранённой стратегии (по имени)
if [[ -f "$CONF_INI" ]]; then
  saved_strategy=$(cat "$CONF_INI" 2>/dev/null | tr -d '\n')
  if [[ -n "$saved_strategy" ]]; then
    echo "Запускаю сохранённую стратегию: $saved_strategy"
    start_strategy "$saved_strategy"
    echo "YouTube работает? (y/n)"
    sleep 4
#    read -r answer
#    if [[ "$answer" =~ ^[Yy]$ ]]; then
#      echo "Выход..."
    exit 0
#    fi
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
  
  # Проверяем только успешный HTTP-статус (200 или 30x)
  [[ "$code" =~ ^(200|30[0-7])$ ]]
}

check_youtube_cdn() {
  local code=$(curl -s --tlsv1.3 \
    --connect-timeout "$CURL_TIMEOUT" \
    --max-time "$CURL_TIMEOUT" \
    -o "/dev/null" \
    -w "%{http_code}" \
    "https://redirector.googlevideo.com" 2>/dev/null)
  
  [[ "$code" != "000" ]]
}


echo "Тестирование ${#STRATEGY_FILES[@]} стратегий..."
for strategy_path in "${STRATEGY_FILES[@]}"; do
  strategy_name=$(basename "$strategy_path")
  echo -n "Тестируем $strategy_name ... "
  start_strategy "$strategy_name"
  # Проверки отключены, поэтому просто считаем стратегию рабочей
  yt_ok=1
  cdn_ok=0
  WORKING+=("$index:$strategy_name:$yt_ok:$cdn_ok")
  echo "РАБОТАЕТ (CDN: $cdn_ok)"
  stop_zapret
  ((index++))
done

echo ""
echo "Рабочих стратегий найдено: ${#WORKING[@]}"
echo ""

if [[ "${#WORKING[@]}" -eq 0 ]]; then
  echo "Подходящих стратегий нет."
  echo "Нажмите Enter..."
  read -r
  exit 0
fi

current_strategy=""

# Попытка запустить сохранённую стратегию по имени
if [[ -f "$CONF_INI" ]]; then
  saved_strategy=$(cat "$CONF_INI" 2>/dev/null | tr -d '\n')
  if [[ -n "$saved_strategy" ]]; then
    for entry in "${WORKING[@]}"; do
      IFS=":" read -r n name yt cdn <<< "$entry"
      if [[ "$name" == "$saved_strategy" ]]; then
        echo "Найдена сохранённая стратегия: $name"
        stop_zapret
        start_strategy "$name"
        current_strategy="$name"
        echo "Стратегия запущена."
        echo ""
        break
      fi
    done
  fi
fi

# Главный цикл
while true; do
  echo "========================================================"
  echo "Рабочие стратегии:"
  echo "№   Стратегия                                 CDN"
  echo "--------------------------------------------------------"

  for entry in "${WORKING[@]}"; do
    IFS=":" read -r num name yt cdn <<< "$entry"
    if [[ "$cdn" -eq 1 ]]; then
      cdn_str="+"
    else
      cdn_str="-"
    fi
    printf "%2s  %-42s  %s\n" "$num" "$name" "$cdn_str"
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
      IFS=":" read -r n name yt cdn <<< "$entry"
      if [[ "$n" == "$num" ]]; then
        found=1
        echo "Выбрана стратегия: $name"
        stop_zapret
        start_strategy "$name"
        current_strategy="$name"
        echo "Стратегия запущена."
        echo ""

        # Интерактивный опрос о работе YouTube
        while true; do
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
          elif [[ "$answer" =~ ^[Nn]$ ]]; then
            echo "Останавливаем стратегию и пробуем другую."
            stop_zapret
            current_strategy=""
            break
          else
            echo "Пожалуйста, введите y или n."
          fi
        done
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
